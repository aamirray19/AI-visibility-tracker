import ipaddress
import json
import re
import socket
import uuid
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
import tldextract
from rapidfuzz import fuzz
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_codes import COMPANY_MISMATCH, INVALID_WEBSITE
from app.core.errors import AppError
from app.core.lifecycle import TERMINAL_STATUSES
from app.db.models import Company, Scan
from app.db.repositories.companies import CompanyRepository
from app.db.repositories.scans import ScanRepository

LEGAL_SUFFIXES = {"inc", "ltd", "llc", "corp", "gmbh", "pvt", "pte"}
MAX_REDIRECTS = 2
FETCH_TIMEOUT_S = 5.0
MAX_BODY_BYTES = 1_000_000
BODY_TEXT_CHARS = 4000
ENRICH_CACHE_TTL_S = 7 * 24 * 3600


# --- Normalization (§7.1 steps 2-3) ---------------------------------------


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    tokens = [t for t in cleaned.split() if t not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def normalize_domain(website: str) -> str:
    """Reduces to eTLD+1. Format-only validation -- no DNS lookups here, so
    resolving a company's name never depends on the network or the domain
    being currently reachable. The live SSRF guard runs at fetch time
    (_validate_host_live), which is the boundary that actually opens a
    connection (§7.1 step 1, §14)."""
    url = website if "://" in website else f"https://{website}"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise AppError(INVALID_WEBSITE, "Website must use http or https", status_code=422)
    if not parsed.hostname:
        raise AppError(INVALID_WEBSITE, "Website is missing a host", status_code=422)
    _validate_host_format(parsed.hostname)
    ext = tldextract.extract(url)
    if not ext.domain or not ext.suffix:
        raise AppError(INVALID_WEBSITE, "Website is not a valid domain", status_code=422)
    return f"{ext.domain}.{ext.suffix}".lower()


def _is_unsafe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified


def _validate_host_format(hostname: str) -> None:
    """Fast, network-free rejection of the obvious SSRF targets: localhost and
    IP-literal hosts in private/loopback/link-local ranges."""
    if hostname == "localhost":
        raise AppError(INVALID_WEBSITE, "Website host is not allowed", status_code=422)
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        return  # a DNS name, not an IP literal -- fine at the format-check stage
    if _is_unsafe_ip(literal):
        raise AppError(INVALID_WEBSITE, "Website host is not allowed", status_code=422)


def _validate_host_live(hostname: str) -> bool:
    """DNS-resolution-based SSRF guard, run right before each real connection
    (initial fetch + every redirect hop, §14). Returns False rather than
    raising -- an unresolvable or unsafe host just fails the fetch, which is
    already a non-fatal, best-effort path (§7.1 step 4).
    ponytail: resolve-then-connect has a small DNS-rebinding TOCTOU window;
    acceptable for a single-operator tool entering its own company URL --
    pin the resolved IP through httpx's transport if that ever changes."""
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        return not _is_unsafe_ip(literal)
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    return all(not _is_unsafe_ip(ipaddress.ip_address(info[4][0])) for info in infos)


# --- Homepage fetch + extraction (§7.1 step 4) ----------------------------


class _HomepageParser(HTMLParser):
    SKIP_TAGS = {"script", "style", "nav", "footer"}

    def __init__(self):
        super().__init__()
        self.title = ""
        self.og_site_name = ""
        self.meta_description = ""
        self._in_title = False
        self._skip_depth = 0
        self._body_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (attrs_d.get("name") or "").lower()
            prop = (attrs_d.get("property") or "").lower()
            content = attrs_d.get("content") or ""
            if name == "description":
                self.meta_description = content
            elif prop == "og:site_name":
                self.og_site_name = content

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0:
            text = data.strip()
            if text:
                self._body_parts.append(text)

    @property
    def body_text(self) -> str:
        return " ".join(self._body_parts)[:BODY_TEXT_CHARS]


def _extract(html: str) -> dict:
    parser = _HomepageParser()
    parser.feed(html)
    return {
        "title": parser.title.strip(),
        "site_name": (parser.og_site_name or parser.title).strip(),
        "meta_description": parser.meta_description.strip(),
        "body_text": parser.body_text,
    }


async def fetch_homepage(url: str) -> dict | None:
    """Best-effort. A failure here never blocks onboarding -- the caller falls
    back to name + domain only (§7.1 step 4)."""
    current_url = url
    async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_S, follow_redirects=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            parsed = urlparse(current_url)
            if not parsed.hostname or not _validate_host_live(parsed.hostname):
                return None
            try:
                async with client.stream("GET", current_url) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            return None
                        current_url = str(httpx.URL(current_url).join(location))
                        continue
                    if resp.status_code >= 400:
                        return None
                    body = b""
                    chunks = resp.aiter_bytes()
                    try:
                        async for chunk in chunks:
                            body += chunk
                            if len(body) > MAX_BODY_BYTES:
                                break  # cap hit -- close the generator explicitly rather than abandon it
                    finally:
                        await chunks.aclose()
                    html = body[:MAX_BODY_BYTES].decode(resp.encoding or "utf-8", errors="ignore")
                    return _extract(html)
            except httpx.RequestError:
                return None
    return None  # exhausted MAX_REDIRECTS


async def get_cached_or_fetch_homepage(redis, domain: str) -> dict | None:
    cache_key = f"cache:enrich:{domain}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    homepage = await fetch_homepage(f"https://{domain}")
    if homepage:
        await redis.setex(cache_key, ENRICH_CACHE_TTL_S, json.dumps(homepage))
    return homepage


# --- Mismatch check (§7.1 step 5, hard reject) ----------------------------


def check_mismatch(name_norm: str, site_name: str, domain: str) -> None:
    if not site_name or not name_norm:
        return  # nothing meaningful to compare -- homepage fetch failed, or the
        # name normalized to nothing (e.g. entirely legal-suffix tokens)
    ratio = fuzz.token_set_ratio(name_norm, normalize_name(site_name))
    name_joined = name_norm.replace(" ", "")
    domain_stripped = domain.replace("-", "").replace(".", "")
    domain_contains_name = bool(name_joined) and name_joined in domain_stripped
    if ratio < 60 and not domain_contains_name:
        raise AppError(
            COMPANY_MISMATCH,
            "The website resolves to a different company than the one named.",
            status_code=422,
            details={"resolved_name": site_name},
        )


# --- Company + scan resolution (§7.1 steps 6, and the reuse pseudocode) ---


async def upsert_company(session: AsyncSession, name: str, name_norm: str, domain: str) -> Company:
    repo = CompanyRepository(session)
    existing = await repo.list(domain=domain)
    if existing:
        company = existing[0]
        if company.name != name or company.name_norm != name_norm:
            company.name = name
            company.name_norm = name_norm
            await session.flush()
        return company
    return await repo.create(name=name, name_norm=name_norm, domain=domain)


async def resolve_company(session: AsyncSession, redis, name: str, website: str) -> Company:
    domain = normalize_domain(website)
    name_norm = normalize_name(name)
    homepage = await get_cached_or_fetch_homepage(redis, domain)
    site_name = homepage["site_name"] if homepage else ""
    check_mismatch(name_norm, site_name, domain)
    return await upsert_company(session, name, name_norm, domain)


async def get_or_create_scan(
    session: AsyncSession, redis, company: Company, force: bool = False
) -> tuple[Scan, bool]:
    """§7.1's reuse pseudocode. `reused=True` only for the completed-scan cache
    hit -- an in-progress scan is returned as-is but wasn't "reused"."""
    scans = ScanRepository(session)

    if not force:
        existing = await scans.list(company_id=company.id)
        active = sorted(
            (s for s in existing if s.status not in TERMINAL_STATUSES),
            key=lambda s: s.created_at,
            reverse=True,
        )
        if active:
            return active[0], False

        recent_id = await redis.get(f"scan:recent:{company.domain}")
        if recent_id:
            recent = await scans.get(uuid.UUID(recent_id))
            if recent:
                return recent, True

    scan = await scans.create(company_id=company.id)
    return scan, False
