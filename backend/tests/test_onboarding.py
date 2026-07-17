from datetime import datetime, timedelta, timezone

import pytest

from app.core.error_codes import COMPANY_MISMATCH, INVALID_WEBSITE
from app.core.errors import AppError
from app.db.repositories.scans import ScanRepository
from app.services.onboarding import (
    _validate_host_live,
    check_mismatch,
    get_or_create_scan,
    normalize_domain,
    normalize_name,
    upsert_company,
)


def test_normalize_name_strips_legal_suffix_and_lowercases():
    assert normalize_name("Acme Widgets Inc.") == "acme widgets"


def test_normalize_domain_reduces_to_etld_plus_one():
    assert normalize_domain("https://www.Acme.com/pricing") == "acme.com"


def test_normalize_domain_defaults_missing_scheme_to_https():
    assert normalize_domain("acme.com") == "acme.com"


def test_normalize_domain_rejects_non_http_scheme():
    with pytest.raises(AppError) as exc_info:
        normalize_domain("ftp://acme.com")
    assert exc_info.value.code == INVALID_WEBSITE


def test_normalize_domain_rejects_localhost():
    with pytest.raises(AppError) as exc_info:
        normalize_domain("http://localhost")
    assert exc_info.value.code == INVALID_WEBSITE


def test_normalize_domain_rejects_link_local_ip():
    with pytest.raises(AppError) as exc_info:
        normalize_domain("http://169.254.169.254")
    assert exc_info.value.code == INVALID_WEBSITE


def test_normalize_domain_rejects_loopback_ip():
    with pytest.raises(AppError):
        normalize_domain("http://127.0.0.1")


def test_check_mismatch_passes_when_names_align():
    check_mismatch("acme", "Acme Corp", "acme.com")  # no raise


def test_check_mismatch_rejects_unrelated_company():
    # domain must not contain the name token either, or the domain-evidence
    # escape hatch in check_mismatch forgives a misleading site_name (§7.1 step 5)
    with pytest.raises(AppError) as exc_info:
        check_mismatch("acme", "Totally Different Globex Industries", "globex-industries.io")
    assert exc_info.value.code == COMPANY_MISMATCH


def test_validate_host_live_rejects_loopback_ip_literal():
    assert _validate_host_live("127.0.0.1") is False


def test_validate_host_live_rejects_link_local_ip_literal():
    assert _validate_host_live("169.254.169.254") is False


def test_validate_host_live_rejects_unresolvable_host():
    assert _validate_host_live("this-domain-should-not-exist-abcxyz123.invalid") is False


def test_check_mismatch_skips_when_site_name_unavailable():
    check_mismatch("acme", "", "acme.com")  # no raise -- unverified homepage (§7.1 step 4)


def test_check_mismatch_skips_when_name_norm_is_empty():
    # a name that normalizes to nothing (e.g. entirely legal-suffix tokens)
    # has no token to compare -- must not vacuously "contain" every domain
    check_mismatch("", "Totally Unrelated Company", "unrelated-domain.io")  # no raise


async def test_upsert_company_updates_name_on_existing_domain(db_session):
    first = await upsert_company(db_session, "Acme Inc", "acme", "acme.com")
    updated = await upsert_company(db_session, "Acme Corp International", "acme corp international", "acme.com")
    assert updated.id == first.id
    assert updated.name == "Acme Corp International"
    assert updated.name_norm == "acme corp international"


async def test_get_or_create_scan_creates_new_when_none_exists(db_session, redis_client):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scan, reused = await get_or_create_scan(db_session, redis_client, company)
    assert reused is False
    assert scan.company_id == company.id


async def test_get_or_create_scan_returns_active_scan_without_creating_new(db_session, redis_client):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    first = await scans.create(company_id=company.id)  # status defaults to "created" (active)

    scan, reused = await get_or_create_scan(db_session, redis_client, company)
    assert scan.id == first.id
    assert reused is False

    remaining = await scans.list(company_id=company.id)
    assert len(remaining) == 1


async def test_get_or_create_scan_reuses_completed_scan_from_redis_cache(db_session, redis_client):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    completed = await scans.create(company_id=company.id, status="completed")
    await redis_client.set(f"scan:recent:{company.domain}", str(completed.id))

    scan, reused = await get_or_create_scan(db_session, redis_client, company)
    assert scan.id == completed.id
    assert reused is True


async def test_get_or_create_scan_returns_most_recent_active_scan(db_session, redis_client):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    now = datetime.now(timezone.utc)
    await scans.create(company_id=company.id, created_at=now - timedelta(minutes=5))
    newer = await scans.create(company_id=company.id, created_at=now)

    scan, reused = await get_or_create_scan(db_session, redis_client, company)
    assert scan.id == newer.id
    assert reused is False


async def test_get_or_create_scan_force_bypasses_reuse(db_session, redis_client):
    company = await upsert_company(db_session, "Acme", "acme", "acme.com")
    scans = ScanRepository(db_session)
    completed = await scans.create(company_id=company.id, status="completed")
    await redis_client.set(f"scan:recent:{company.domain}", str(completed.id))

    scan, reused = await get_or_create_scan(db_session, redis_client, company, force=True)
    assert scan.id != completed.id
    assert reused is False
