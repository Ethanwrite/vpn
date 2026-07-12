from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
import pytest
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.db_models import AuthSessionRow, UserRow, VpnNodeRow
from app.main import (
    ADMIN_MAX_GRANT_DAYS,
    ADMIN_SESSION_MAX_AGE_SECONDS,
    AdminGrantVipRequest,
    CreateOrderRequest,
    FREE_TRAFFIC_QUOTA_BYTES,
    admin_password_valid,
    admin_session_token,
    admin_session_valid,
    build_vpn_entitlement,
    create_session,
    effective_vip_status,
    hash_token,
    is_online,
    reject_production_test_user,
    require_owned_order,
    reserved_test_email,
    to_admin_user,
    windows_client_block_reason,
    to_vpn_node_summary,
)
from app.payment_page import render_payment_page
from app.site_page import SITE_HTML


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


def test_admin_session_token_expires(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "session-secret")
    issued_at = 1_800_000_000
    token = admin_session_token(issued_at)

    assert admin_session_valid(token, now=issued_at + ADMIN_SESSION_MAX_AGE_SECONDS)
    assert not admin_session_valid(token, now=issued_at + ADMIN_SESSION_MAX_AGE_SECONDS + 1)


def test_windows_client_kill_switch_is_platform_scoped(monkeypatch) -> None:
    monkeypatch.delenv("WINDOWS_CLIENT_ENABLED", raising=False)
    assert windows_client_block_reason("/vpn/nodes", "curl/8", "windows") == "platform_header"
    assert windows_client_block_reason("/health", "XingsuiWindows/1.0") == "native_user_agent"
    assert windows_client_block_reason("/download/windows", "Mozilla/5.0") == "download_disabled"
    assert windows_client_block_reason("/health", "XingsuiAndroid/2.0") is None

    monkeypatch.setenv("WINDOWS_CLIENT_ENABLED", "true")
    assert windows_client_block_reason("/health", "XingsuiWindows/1.0") is None
    assert windows_client_block_reason("/download/windows", "Mozilla/5.0") is None


def test_sensitive_request_models_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CreateOrderRequest(plan_id="plan_month", pay_channel="wechat", user_id="victim-user")

    with pytest.raises(ValidationError):
        AdminGrantVipRequest(days=ADMIN_MAX_GRANT_DAYS + 1)


def test_reserved_test_email_domains() -> None:
    assert reserved_test_email("free@local.test")
    assert reserved_test_email("demo@xingsui.local")
    assert reserved_test_email("probe@example.com")
    assert not reserved_test_email("customer@example.org")


def test_production_rejects_reserved_test_user(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    user = SimpleNamespace(id="demo_user", email="demo@xingsui.local")
    with pytest.raises(HTTPException) as exc_info:
        reject_production_test_user(user)
    assert exc_info.value.status_code == 403


def test_order_owner_check_hides_other_users_order() -> None:
    order = SimpleNamespace(id="order-1", user_id="owner")

    class FakeSession:
        def get(self, _model, _identifier):
            return order

    assert require_owned_order(FakeSession(), "order-1", SimpleNamespace(id="owner")) is order
    with pytest.raises(HTTPException) as exc_info:
        require_owned_order(FakeSession(), "order-1", SimpleNamespace(id="attacker"))
    assert exc_info.value.status_code == 404


def test_vpn_entitlement_allows_free_trial_then_blocks_when_exhausted_and_allows_active_vip() -> None:
    user = UserRow(
        id="u2",
        email="trial-vpn@example.com",
        password_salt="salt",
        password_hash="hash",
        nickname="trial-vpn",
        invite_code="XSVPN",
        status="active",
        free_traffic_quota_bytes=FREE_TRAFFIC_QUOTA_BYTES,
        free_traffic_used_bytes=0,
    )

    entitlement = build_vpn_entitlement(user)
    assert entitlement.allowed
    assert entitlement.reason == "free_trial"

    user.free_traffic_used_bytes = FREE_TRAFFIC_QUOTA_BYTES
    entitlement = build_vpn_entitlement(user)
    assert not entitlement.allowed
    assert entitlement.reason == "free_traffic_exhausted"

    user.vip_status = "active"
    user.vip_expired_at = datetime.now(UTC) + timedelta(days=1)
    entitlement = build_vpn_entitlement(user)
    assert entitlement.allowed
    assert entitlement.reason == "vip_active"


def test_node_summary_locks_when_entitlement_is_denied() -> None:
    node = VpnNodeRow(
        id="node-free",
        name="Free Node",
        region="Japan",
        endpoint="203.0.113.10:443",
        agent_host="203.0.113.10",
        server_public_key="SRVPUB",
    )

    summary = to_vpn_node_summary(
        node,
        health=None,
        vip=False,
        now=datetime(2026, 1, 1, tzinfo=UTC),
        protocol="awg",
        entitlement_allowed=False,
    )

    assert summary.locked


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
    summary = to_admin_user(user, now, invited_count=3, paid_invite_count=2)
    assert summary.email == "admin-visible@example.com"
    assert summary.vip_status == "active"
    assert summary.online
    assert summary.invited_count == 3
    assert summary.paid_invite_count == 2

    user.last_seen_at = now - timedelta(minutes=8)
    assert not to_admin_user(user, now).online


def test_create_session_keeps_only_two_active_sessions() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[UserRow.__table__, AuthSessionRow.__table__])
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = Session()
    user = UserRow(
        id="u-session",
        email="session@example.com",
        password_salt="salt",
        password_hash="hash",
        nickname="session",
        invite_code="XSSESSION",
    )
    db.add(user)
    db.commit()

    first = create_session(db, user.id)
    second = create_session(db, user.id)
    third = create_session(db, user.id)

    sessions = list(db.scalars(select(AuthSessionRow).where(AuthSessionRow.user_id == user.id)))
    hashes = {row.token_hash for row in sessions}
    assert len(sessions) == 2
    assert hash_token(first) not in hashes
    assert hash_token(second) in hashes
    assert hash_token(third) in hashes
    assert all(row.status == "active" for row in sessions)
    assert all(
        row.expires_at is not None
        and (row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)) > datetime.now(UTC)
        for row in sessions
    )


def test_site_routes_selected_plan_to_mobile_payment_page() -> None:
    assert "location.href = `/payment?${params.toString()}`" in SITE_HTML


def test_payment_page_contains_deep_links_and_qr_fallback() -> None:
    html = render_payment_page()

    assert "选择支付方式" in html
    assert "微信支付" in html
    assert "支付宝支付" in html
    assert "wxp://" in html
    assert "https%3A%2F%2Fqr.alipay.com%2F" in html
    assert "https://xingsui.org/pay/wechat.jpg" in html
    assert "https://xingsui.org/pay/alipay.jpg" in html
    assert "支付完成后，点“我已经完成支付”提交订单。" in html
    assert "订单已提交成功！请等待管理员确认到账，确认后 VIP 会自动开通。" in html
    assert "intent://" in html
    assert "alipays://platformapi/startapp" in html
    assert "https://ulink.alipay.com/" in html
    assert "launchPayment(channel, target)" in html
    assert "xingsui_pending_payment" in html
    assert "二维码直接使用主服务器图片" not in html
    assert "package=com.tencent.mm" not in html
    assert "__PAYMENT_CONFIG__" not in html
