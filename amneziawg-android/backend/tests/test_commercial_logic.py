from datetime import UTC, datetime, timedelta

from app.db_models import UserRow
from app.main import (
    FREE_TRAFFIC_QUOTA_BYTES,
    admin_password_valid,
    admin_session_token,
    admin_session_valid,
    build_entitlement,
    build_vpn_entitlement,
    effective_vip_status,
    free_traffic_remaining,
    is_online,
    to_admin_user,
)


def test_effective_vip_status_requires_future_expiry() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    assert effective_vip_status("inactive", now + timedelta(days=1), now) == "inactive"
    assert effective_vip_status("active", None, now) == "inactive"
    assert effective_vip_status("active", now - timedelta(seconds=1), now) == "expired"
    assert effective_vip_status("active", now + timedelta(seconds=1), now) == "active"


def test_admin_password_and_session_token(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "session-secret")

    assert admin_password_valid("secret")
    assert admin_session_valid(admin_session_token())
    assert not admin_password_valid(None)
    assert not admin_password_valid("bad")
    assert not admin_session_valid(None)
    assert not admin_session_valid("bad-token")


def test_free_trial_entitlement_allows_30mb_then_blocks() -> None:
    user = UserRow(
        id="u1",
        email="trial@example.com",
        password_salt="salt",
        password_hash="hash",
        nickname="trial",
        invite_code="XSTRIAL",
        free_traffic_quota_bytes=FREE_TRAFFIC_QUOTA_BYTES,
        free_traffic_used_bytes=FREE_TRAFFIC_QUOTA_BYTES - 1,
    )

    assert free_traffic_remaining(user) == 1
    assert build_entitlement(user).allowed

    user.free_traffic_used_bytes = FREE_TRAFFIC_QUOTA_BYTES
    entitlement = build_entitlement(user)
    assert not entitlement.allowed
    assert entitlement.reason == "free_traffic_exhausted"


def test_vpn_entitlement_allows_free_trial_and_vip() -> None:
    user = UserRow(
        id="u2",
        email="trial-vpn@example.com",
        password_salt="salt",
        password_hash="hash",
        nickname="trial-vpn",
        invite_code="XSVPN",
        free_traffic_quota_bytes=FREE_TRAFFIC_QUOTA_BYTES,
        free_traffic_used_bytes=0,
    )

    entitlement = build_vpn_entitlement(user)
    assert entitlement.allowed
    assert entitlement.reason == "free_trial"

    user.vip_status = "active"
    user.vip_expired_at = datetime.now(UTC) + timedelta(days=1)
    entitlement = build_vpn_entitlement(user)
    assert entitlement.allowed
    assert entitlement.reason == "vip_active"


def test_admin_user_summary_prefers_email_and_online_window() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    user = UserRow(
        id="u3",
        email="admin-visible@example.com",
        password_salt="salt",
        password_hash="hash",
        nickname="admin-visible",
        invite_code="XSADMIN",
        vip_status="active",
        vip_expired_at=now + timedelta(days=2),
        created_at=now - timedelta(days=1),
        last_login_at=now - timedelta(minutes=2),
        last_seen_at=now - timedelta(minutes=1),
    )

    assert is_online(user.last_seen_at, now)
    summary = to_admin_user(user, now)
    assert summary.email == "admin-visible@example.com"
    assert summary.vip_status == "active"
    assert summary.online

    user.last_seen_at = now - timedelta(minutes=8)
    assert not to_admin_user(user, now).online
