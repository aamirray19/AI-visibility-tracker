import httpx

import app.services.onboarding as onboarding

HTML = b"""<html><head><title>Acme Site</title>
<meta property="og:site_name" content="Acme Corp">
<meta name="description" content="We sell widgets">
<script>var x = 1;</script>
</head><body><nav>Home About</nav>Welcome to Acme. We sell the best widgets.<footer>copyright</footer></body></html>"""


def _patch_transport(monkeypatch, handler):
    orig_client = httpx.AsyncClient

    def _patched(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return orig_client(*args, **kwargs)

    monkeypatch.setattr(onboarding.httpx, "AsyncClient", _patched)


async def test_fetch_homepage_extracts_title_og_meta_and_body(monkeypatch):
    async def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, content=HTML)

    _patch_transport(monkeypatch, handler)
    result = await onboarding.fetch_homepage("https://example.com/")
    assert result == {
        "title": "Acme Site",
        "site_name": "Acme Corp",
        "meta_description": "We sell widgets",
        "body_text": "Welcome to Acme. We sell the best widgets.",
    }


async def test_fetch_homepage_follows_redirects(monkeypatch):
    async def handler(request):
        if str(request.url) == "https://example.com/":
            return httpx.Response(301, headers={"location": "https://example.com/home"})
        if str(request.url) == "https://example.com/home":
            return httpx.Response(200, headers={"content-type": "text/html"}, content=HTML)
        return httpx.Response(404)

    _patch_transport(monkeypatch, handler)
    result = await onboarding.fetch_homepage("https://example.com/")
    assert result["site_name"] == "Acme Corp"


async def test_fetch_homepage_bounds_redirect_loops(monkeypatch):
    async def handler(request):
        return httpx.Response(302, headers={"location": str(request.url)})

    _patch_transport(monkeypatch, handler)
    result = await onboarding.fetch_homepage("https://example.com/")
    assert result is None


async def test_fetch_homepage_rejects_redirect_to_private_ip(monkeypatch):
    async def handler(request):
        if str(request.url) == "https://example.com/":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})
        return httpx.Response(200, content=b"should never be reached")

    _patch_transport(monkeypatch, handler)
    result = await onboarding.fetch_homepage("https://example.com/")
    assert result is None


async def test_fetch_homepage_returns_none_on_4xx(monkeypatch):
    async def handler(request):
        return httpx.Response(404)

    _patch_transport(monkeypatch, handler)
    result = await onboarding.fetch_homepage("https://example.com/")
    assert result is None


async def test_fetch_homepage_truncates_body_to_cap(monkeypatch):
    big_html = b"<html><body>" + b"a" * (onboarding.MAX_BODY_BYTES + 1000) + b"</body></html>"

    async def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, content=big_html)

    _patch_transport(monkeypatch, handler)
    result = await onboarding.fetch_homepage("https://example.com/")
    assert result is not None
    assert len(result["body_text"]) <= onboarding.BODY_TEXT_CHARS
