from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.requests import Request
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.db_models import SubscriptionAuditLogRow, UserRow
from app.main import (
    SUBSCRIPTION_RATE_LIMITS,
    create_session,
    get_user_subscription_link,
    get_vpn_node_config,
    hash_password,
    list_vpn_nodes,
    reset_user_subscription_link,
    subscription_feed,
    SubscriptionApiException,
)
from app.site_page import SITE_HTML


@pytest.fixture()
def Session():
    SUBSCRIPTION_RATE_LIMITS.clear()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield Session
    SUBSCRIPTION_RATE_LIMITS.clear()


def make_user(Session, *, user_id="u1", vip_status="inactive", expires_at=None, status="active"):
    db = Session()
    salt, password_hash = hash_password("xingsui123")
    user = UserRow(
        id=user_id,
        email=f"{user_id}@example.com",
        password_salt=salt,
        password_hash=password_hash,
        nickname=user_id,
        invite_code=f"XS{user_id.upper()}",
        vip_status=vip_status,
        vip_expired_at=expires_at,
        status=status,
    )
    db.add(user)
    db.commit()
    token = create_session(db, user.id)
    db.close()
    return token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def token_from_subscription_url(url: str) -> str:
    return parse_qs(urlparse(url).query)["token"][0]


def write_proxy_links(monkeypatch, tmp_path) -> None:
    links = tmp_path / "subscription-links.txt"
    links.write_text(
        "vless://3a1c76bf-9320-4118-aa57-b141981b0e72@212.50.232.111:8443"
        "?encryption=none&security=reality&type=tcp&sni=xingsui.org&fp=chrome"
        "&pbk=zAcSb2zn5YHeTcjXodV-ap3cQqLztZkBaedA_SMCKmY&sid=f3c148bef780f76d&spx=%2F#Xingsui-Osaka\n"
        "vless://828d3436-13fa-47e1-ad00-5fed4526f16f@172.86.91.81:8443"
        "?encryption=none&security=reality&type=tcp&sni=xingsui.org&fp=chrome"
        "&pbk=TBSJrOiZhh3TMGz0oU1e61WVRgMJSpEL4dMucJJ5Txg&sid=71f5a0cc237b49cb&spx=%2F#Xingsui-Edge-172\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SUBSCRIPTION_PROXY_LINKS_PATH", str(links))


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/user/subscription-link",
            "headers": [(b"host", b"xingsuico.com"), (b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 12345),
            "scheme": "https",
        }
    )


def test_subscription_link_requires_login(Session) -> None:
    db = Session()
    with pytest.raises(SubscriptionApiException) as exc:
        get_user_subscription_link(make_request(), authorization=None, db=db)
    db.close()
    assert exc.value.status_code == 401
    assert exc.value.code == "UNAUTHORIZED"


def test_subscription_link_requires_vip(Session) -> None:
    token = make_user(Session, vip_status="inactive")
    db = Session()
    with pytest.raises(SubscriptionApiException) as exc:
        get_user_subscription_link(make_request(), authorization=bearer(token)["Authorization"], db=db)
    db.close()
    assert exc.value.status_code == 403
    assert exc.value.code == "VIP_REQUIRED"


def test_subscription_link_rejects_expired_vip(Session) -> None:
    token = make_user(
        Session,
        vip_status="active",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db = Session()
    with pytest.raises(SubscriptionApiException) as exc:
        get_user_subscription_link(make_request(), authorization=bearer(token)["Authorization"], db=db)
    db.close()
    assert exc.value.status_code == 403
    assert exc.value.code == "VIP_EXPIRED"


def test_subscription_link_rejects_frozen_account(Session) -> None:
    token = make_user(
        Session,
        vip_status="active",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        status="frozen",
    )
    db = Session()
    with pytest.raises(SubscriptionApiException) as exc:
        get_user_subscription_link(make_request(), authorization=bearer(token)["Authorization"], db=db)
    db.close()
    assert exc.value.status_code == 403
    assert exc.value.code == "ACCOUNT_FROZEN"


def test_active_vip_gets_subscription_link_and_feed(Session, monkeypatch, tmp_path) -> None:
    write_proxy_links(monkeypatch, tmp_path)
    token = make_user(
        Session,
        vip_status="active",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db = Session()
    response = get_user_subscription_link(make_request(), authorization=bearer(token)["Authorization"], db=db)
    assert response.success is True
    assert "/api/sub?token=" in response.subscription_url
    assert "****" in response.masked_token

    sub_token = token_from_subscription_url(response.subscription_url)
    feed = subscription_feed(token=sub_token, db=db)
    db.close()
    assert feed.status_code == 200
    assert feed.media_type.startswith("text/yaml")
    body = feed.body.decode("utf-8")
    assert "星隧订阅" in body
    assert "type: \"vless\"" in body
    assert "Xingsui-Osaka" in body
    assert "      - \"Xingsui-Osaka\"" in body
    assert "      - DIRECT" not in body
    assert "type: direct" not in body
    assert "星隧 App 内置线路" not in body


def test_reset_invalidates_old_subscription_token(Session, monkeypatch, tmp_path) -> None:
    write_proxy_links(monkeypatch, tmp_path)
    token = make_user(
        Session,
        vip_status="active",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db = Session()
    old_payload = get_user_subscription_link(make_request(), authorization=bearer(token)["Authorization"], db=db)
    old_sub_token = token_from_subscription_url(old_payload.subscription_url)

    reset_response = reset_user_subscription_link(make_request(), authorization=bearer(token)["Authorization"], db=db)
    new_sub_token = token_from_subscription_url(reset_response.subscription_url)
    assert new_sub_token != old_sub_token

    assert subscription_feed(token=old_sub_token, db=db).status_code == 401
    assert subscription_feed(token=new_sub_token, db=db).status_code == 200
    db.close()


def test_reset_does_not_touch_other_users_subscription(Session, monkeypatch, tmp_path) -> None:
    write_proxy_links(monkeypatch, tmp_path)
    token_a = make_user(
        Session,
        user_id="ua",
        vip_status="active",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    token_b = make_user(
        Session,
        user_id="ub",
        vip_status="active",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db = Session()
    payload_a = get_user_subscription_link(make_request(), authorization=bearer(token_a)["Authorization"], db=db)
    sub_token_a = token_from_subscription_url(payload_a.subscription_url)

    response_b = reset_user_subscription_link(make_request(), authorization=bearer(token_b)["Authorization"], db=db)
    assert response_b.success is True
    assert subscription_feed(token=sub_token_a, db=db).status_code == 200
    db.close()


def test_subscription_feed_without_real_nodes_returns_error(Session, monkeypatch, tmp_path) -> None:
    empty_links = tmp_path / "empty-links.txt"
    empty_links.write_text("", encoding="utf-8")
    monkeypatch.setenv("SUBSCRIPTION_PROXY_LINKS_PATH", str(empty_links))
    token = make_user(
        Session,
        vip_status="active",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db = Session()
    payload = get_user_subscription_link(make_request(), authorization=bearer(token)["Authorization"], db=db)
    sub_token = token_from_subscription_url(payload.subscription_url)
    response = subscription_feed(token=sub_token, db=db)
    db.close()
    assert response.status_code == 503
    assert b"NO_AVAILABLE_NODES" in response.body


def test_vpn_nodes_prefer_osaka_vless_for_vip(Session, monkeypatch, tmp_path) -> None:
    write_proxy_links(monkeypatch, tmp_path)
    token = make_user(
        Session,
        vip_status="active",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db = Session()
    nodes = list_vpn_nodes(
        authorization=bearer(token)["Authorization"],
        x_xingsui_version_code="2",
        db=db,
    )
    assert nodes[0].id == "vless-osaka"
    assert nodes[0].name == "大阪 CN2 优化线路"
    assert nodes[0].status == "online"
    assert nodes[0].vip_only is False
    assert nodes[0].locked is False
    assert nodes[0].probe_host == "212.50.232.111"
    assert nodes[0].probe_port == 8443

    config = get_vpn_node_config("vless-osaka", authorization=bearer(token)["Authorization"], db=db)
    db.close()
    assert config.config_text.startswith("vless://")
    assert "212.50.232.111:8443" in config.config_text


def test_osaka_vless_allows_non_vip_with_entitlement(Session, monkeypatch, tmp_path) -> None:
    write_proxy_links(monkeypatch, tmp_path)
    token = make_user(Session, vip_status="inactive")
    db = Session()
    nodes = list_vpn_nodes(
        authorization=bearer(token)["Authorization"],
        x_xingsui_version_code="2",
        db=db,
    )
    assert nodes[0].id == "vless-osaka"
    assert nodes[0].vip_only is False
    assert nodes[0].locked is False
    config = get_vpn_node_config("vless-osaka", authorization=bearer(token)["Authorization"], db=db)
    db.close()
    assert config.config_text.startswith("vless://")


def test_subscription_export_rate_limit(Session) -> None:
    token = make_user(
        Session,
        vip_status="active",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db = Session()
    for _ in range(5):
        assert get_user_subscription_link(make_request(), authorization=bearer(token)["Authorization"], db=db).success
    with pytest.raises(SubscriptionApiException) as exc:
        get_user_subscription_link(make_request(), authorization=bearer(token)["Authorization"], db=db)
    db.close()
    assert exc.value.status_code == 429
    assert exc.value.code == "RATE_LIMITED"


def test_subscription_audit_log_does_not_store_full_token(Session) -> None:
    token = make_user(
        Session,
        vip_status="active",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db = Session()
    payload = get_user_subscription_link(make_request(), authorization=bearer(token)["Authorization"], db=db)
    sub_token = token_from_subscription_url(payload.subscription_url)

    logs = db.scalars(select(SubscriptionAuditLogRow)).all()
    db.close()
    assert logs
    serialized = "\n".join(
        f"{log.token_hash_prefix} {log.masked_token} {log.ip_address} {log.user_agent}"
        for log in logs
    )
    assert sub_token not in serialized


def test_site_contains_subscription_copy_controls() -> None:
    assert "我的订阅链接" in SITE_HTML
    assert "centerSubscriptionButton" in SITE_HTML
    assert "复制链接" in SITE_HTML
    assert "resetSubscriptionLink" in SITE_HTML
    assert "订阅链接导入教程" in SITE_HTML
    assert "Clash、sing-box、v2rayN、Shadowrocket、Stash、Quantumult X" in SITE_HTML
