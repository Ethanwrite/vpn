from datetime import UTC, datetime, timedelta
import json

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app import database
from app.database import Base
from app.db_models import AuthSessionRow, UserRow, VpnDeviceRow, VpnNodeRow
from app.main import (
    NodeHeartbeatRequest,
    apply_no_store_headers,
    create_session,
    get_user_subscription_link,
    get_vpn_node_config,
    hash_password,
    hash_token,
    list_vpn_nodes,
    node_heartbeat,
    report_usage,
    render_clash_yaml,
    require_vpn_principal,
    revoke_vpn_devices,
    sensitive_response_path,
    subscription_feed,
    SubscriptionApiException,
    UsageReportRequest,
    acquire_database_schema_read_lock,
    coerce_utc,
)
from app import node_service
from fastapi.responses import Response


@pytest.fixture()
def Session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield Session


def make_user(
    Session,
    *,
    user_id: str = "u1",
    vip_status: str = "active",
    expires_at: datetime | None = None,
    status: str = "active",
) -> str:
    db = Session()
    salt, password_hash = hash_password("xingsui123")
    user = UserRow(
        id=user_id,
        email=f"{user_id}@example.org",
        password_salt=salt,
        password_hash=password_hash,
        nickname=user_id,
        invite_code=f"XS{user_id.upper()}",
        vip_status=vip_status,
        vip_expired_at=expires_at or datetime.now(UTC) + timedelta(days=30),
        status=status,
    )
    db.add(user)
    db.commit()
    token = create_session(db, user.id)
    db.close()
    return token


def bearer(token: str) -> str:
    return f"Bearer {token}"


def request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/user/subscription-link",
            "headers": [(b"host", b"example.org")],
            "client": ("127.0.0.1", 12345),
            "scheme": "https",
        }
    )


def awg_node(node_id: str = "awg-1") -> VpnNodeRow:
    return VpnNodeRow(
        id=node_id,
        name="AWG Node",
        region="Japan",
        protocol="awg",
        endpoint="203.0.113.10:443",
        agent_host="10.0.0.10",
        server_public_key="a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=",
        allowed_ips="0.0.0.0/0, ::/0",
        params_json=(
            '{"Jc":"4","Jmin":"40","Jmax":"70","S1":"86","S2":"574",'
            '"H1":"101","H2":"102","H3":"103","H4":"104"}'
        ),
        enabled=True,
    )


def vless_node(node_id: str = "vless-1") -> VpnNodeRow:
    return VpnNodeRow(
        id=node_id,
        name="VLESS Node",
        region="US",
        protocol="vless",
        endpoint="198.51.100.20:8443",
        agent_host="10.0.0.20",
        server_public_key="unused-for-vless",
        params_json=(
            '{"VlessHost":"198.51.100.20","VlessPort":"8443",'
            '"VlessPublicKey":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",'
            '"VlessShortId":"0011223344556677","VlessServerName":"example.com",'
            '"VlessFingerprint":"chrome","VlessFlow":"xtls-rprx-vision",'
            '"VlessUUID":"shared-legacy-value-must-be-ignored"}'
        ),
        enabled=True,
    )


def test_subscription_link_requires_vip_and_verifies_token(Session) -> None:
    # 未登录 → UNAUTHORIZED（友好提示）
    with pytest.raises(SubscriptionApiException) as exc:
        get_user_subscription_link(request(), authorization=None, db=Session())
    assert exc.value.status_code == 401 and exc.value.code == "UNAUTHORIZED"

    # Non-members receive the explicit VIP_REQUIRED response used by the client.
    guest_token = make_user(Session, user_id="guest", vip_status="inactive")
    with pytest.raises(SubscriptionApiException) as exc:
        get_user_subscription_link(request(), authorization=bearer(guest_token), db=Session())
    assert exc.value.status_code == 403 and exc.value.code == "VIP_REQUIRED"

    # Active members receive an HTTPS subscription URL and a masked token.
    vip_token = make_user(Session, user_id="vip", vip_status="active")
    resp = get_user_subscription_link(request(), authorization=bearer(vip_token), db=Session())
    assert resp.subscription_url.startswith("https://")
    assert "/api/sub?token=" in resp.subscription_url
    assert resp.masked_token and "****" in resp.masked_token

    # Invalid subscription tokens return 401; middleware adds no-store headers.
    response = subscription_feed(token="bogus-token", db=Session())
    assert response.status_code == 401
    assert json.loads(bytes(response.body))["code"] == "UNAUTHORIZED"


def test_access_token_expiry_and_status_are_enforced(Session) -> None:
    token = make_user(Session)
    db = Session()
    session = db.get(AuthSessionRow, hash_token(token))
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        require_vpn_principal(db, bearer(token), "windows")
    assert exc.value.status_code == 401

    session.expires_at = datetime.now(UTC) + timedelta(hours=1)
    session.status = "revoked"
    db.commit()
    with pytest.raises(HTTPException) as exc:
        require_vpn_principal(db, bearer(token), "android")
    assert exc.value.status_code == 401


def test_legacy_android_session_is_extended_to_fixed_creation_boundary(Session, monkeypatch) -> None:
    token = make_user(Session)
    db = Session()
    session = db.get(AuthSessionRow, hash_token(token))
    created_at = datetime.now(UTC) - timedelta(hours=2)
    session.created_at = created_at
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    monkeypatch.setattr("app.main.ANDROID_ACCESS_TOKEN_TTL_SECONDS", 30 * 24 * 60 * 60)

    principal = require_vpn_principal(db, bearer(token), "android")

    assert principal.session.token_hash == hash_token(token)
    assert abs((coerce_utc(principal.session.expires_at) - (created_at + timedelta(days=30))).total_seconds()) < 1

    first_expiry = coerce_utc(principal.session.expires_at)
    require_vpn_principal(db, bearer(token), "android")
    assert coerce_utc(principal.session.expires_at) == first_expiry


def test_legacy_android_session_upgrade_does_not_revive_old_or_revoked_tokens(Session, monkeypatch) -> None:
    monkeypatch.setattr("app.main.ANDROID_ACCESS_TOKEN_TTL_SECONDS", 30 * 24 * 60 * 60)
    for status in ("active", "revoked"):
        token = make_user(Session, user_id=f"u-{status}")
        db = Session()
        session = db.get(AuthSessionRow, hash_token(token))
        session.created_at = datetime.now(UTC) - timedelta(days=31)
        session.expires_at = datetime.now(UTC) - timedelta(days=30)
        session.status = status
        db.commit()
        with pytest.raises(HTTPException) as exc:
            require_vpn_principal(db, bearer(token), "android")
        assert exc.value.status_code == 401
        db.close()


def test_schema_read_lock_matches_startup_lock_on_postgresql() -> None:
    calls = []

    class FakeBind:
        class dialect:
            name = "postgresql"

    class FakeSession:
        def get_bind(self):
            return FakeBind()

        def execute(self, statement):
            calls.append(str(statement))

    acquire_database_schema_read_lock(FakeSession())
    assert calls == ["select pg_advisory_xact_lock_shared(912050232111)"]


def test_startup_schema_lock_is_held_through_transaction_commit(monkeypatch) -> None:
    events = []

    class FakeConnection:
        def execute(self, statement):
            events.append(str(statement))

    class FakeBegin:
        def __enter__(self):
            events.append("begin")
            return FakeConnection()

        def __exit__(self, exc_type, exc, traceback):
            events.append("commit")

    class FakeEngine:
        class dialect:
            name = "postgresql"

        def begin(self):
            return FakeBegin()

    monkeypatch.setattr(database, "engine", FakeEngine())
    monkeypatch.setattr(database.Base.metadata, "create_all", lambda bind: events.append("create_all"))
    monkeypatch.setattr(database, "run_lightweight_migrations", lambda connection: events.append("migrate"))

    database.init_database()

    assert events == [
        "begin",
        "select pg_advisory_xact_lock(912050232111)",
        "create_all",
        "migrate",
        "commit",
    ]


def test_startup_migrations_preserve_exported_subscription_tokens(monkeypatch) -> None:
    statements = []

    class FakeConnection:
        def execute(self, statement):
            statements.append(str(statement))

    database.run_lightweight_migrations(FakeConnection())

    combined = "\n".join(statements).lower()
    assert "subscription_token_hash = null" not in combined
    assert "subscription_token_masked = null" not in combined


@pytest.mark.parametrize(
    ("vip_status", "expires_at"),
    [
        ("inactive", None),
        ("active", datetime.now(UTC) - timedelta(seconds=1)),
    ],
)
def test_non_vip_and_expired_vip_with_free_traffic_can_still_get_a_principal(
    Session,
    vip_status,
    expires_at,
) -> None:
    # Free-trial and expired-VIP accounts are gated on remaining free traffic
    # (via build_vpn_entitlement at each endpoint), not hard-blocked here.
    token = make_user(
        Session,
        vip_status=vip_status,
        expires_at=expires_at,
        status="active",
    )
    db = Session()
    principal = require_vpn_principal(db, bearer(token), "android")
    assert principal.user.id == "u1"


def test_frozen_account_cannot_get_vpn(Session) -> None:
    token = make_user(
        Session,
        vip_status="active",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        status="frozen",
    )
    db = Session()
    with pytest.raises(HTTPException) as exc:
        require_vpn_principal(db, bearer(token), "android")
    assert exc.value.status_code == 403


def test_vpn_config_blocks_non_vip_once_free_traffic_is_exhausted(Session) -> None:
    token = make_user(Session, vip_status="inactive", expires_at=None)
    db = Session()
    db.add(awg_node())
    user = db.scalar(select(UserRow))
    user.free_traffic_used_bytes = user.free_traffic_quota_bytes
    db.commit()

    with pytest.raises(HTTPException) as exc:
        get_vpn_node_config(
            "awg-1",
            authorization=bearer(token),
            x_xingsui_platform="android",
            db=db,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == "free_traffic_exhausted"


def test_platform_filter_returns_only_complete_matching_nodes(Session) -> None:
    token = make_user(Session)
    db = Session()
    db.add_all([awg_node(), vless_node()])
    db.commit()

    android = list_vpn_nodes(authorization=bearer(token), x_xingsui_platform="android", db=db)
    windows = list_vpn_nodes(authorization=bearer(token), x_xingsui_platform="windows", db=db)
    assert [node.id for node in android] == ["awg-1"]
    assert [node.id for node in windows] == ["vless-1"]
    assert "probe_host" not in android[0].model_dump()
    assert "probe_port" not in android[0].model_dump()


def test_dual_node_is_exposed_as_platform_specific_protocol(Session) -> None:
    token = make_user(Session)
    db = Session()
    node = awg_node("dual-1")
    node.protocol = "dual"
    node.params_json = json.dumps(
        {
            "Jc": "4",
            "Jmin": "40",
            "Jmax": "70",
            "S1": "86",
            "S2": "574",
            "H1": "101",
            "H2": "102",
            "H3": "103",
            "H4": "104",
            "VlessHost": "198.51.100.20",
            "VlessPort": "8443",
            "VlessPublicKey": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "VlessShortId": "0011223344556677",
            "VlessServerName": "example.com",
            "VlessFingerprint": "chrome",
            "VlessFlow": "xtls-rprx-vision",
        }
    )
    db.add(node)
    db.commit()

    android = list_vpn_nodes(authorization=bearer(token), x_xingsui_platform="android", db=db)
    windows = list_vpn_nodes(authorization=bearer(token), x_xingsui_platform="windows", db=db)
    assert [(item.id, item.protocol) for item in android] == [("dual-1", "amneziawg")]
    assert [(item.id, item.protocol) for item in windows] == [("dual-1", "vless")]


def test_android_awg_lease_is_bound_to_session(Session, monkeypatch) -> None:
    token = make_user(Session)
    db = Session()
    db.add(awg_node())
    db.commit()
    calls = []
    monkeypatch.setattr("app.main.generate_wireguard_keypair", lambda: ("client-private", "client-public"))
    monkeypatch.setattr(
        "app.node_service.agent_add_peer",
        lambda node, public_key, client_ip, lease_id, expires_at, **kwargs: calls.append(
            (node.id, public_key, client_ip, lease_id, expires_at)
        ) or {"status": "added"},
    )

    config = get_vpn_node_config(
        "awg-1",
        authorization=bearer(token),
        x_xingsui_platform="android",
        db=db,
    )
    row = db.scalar(select(VpnDeviceRow))
    assert config.protocol == "amneziawg"
    assert config.vless_config is None
    assert config.expires_at > config.issued_at
    assert timedelta(minutes=59) <= config.expires_at - config.issued_at <= timedelta(hours=1)
    assert row.session_token_hash == hash_token(token)
    assert row.lease_id == config.lease_id
    assert calls and calls[0][3] == config.lease_id


def test_android_config_refresh_preserves_live_lease_identity(Session, monkeypatch) -> None:
    token = make_user(Session)
    db = Session()
    db.add(awg_node())
    db.commit()
    calls = []
    monkeypatch.setattr("app.main.generate_wireguard_keypair", lambda: ("client-private", "client-public"))
    monkeypatch.setattr(
        "app.node_service.agent_add_peer",
        lambda node, public_key, client_ip, lease_id, expires_at, **kwargs: calls.append(lease_id)
        or {"status": "added"},
    )

    first = get_vpn_node_config(
        "awg-1", authorization=bearer(token), x_xingsui_platform="android", db=db
    )
    second = get_vpn_node_config(
        "awg-1", authorization=bearer(token), x_xingsui_platform="android", db=db
    )

    assert first.lease_id == second.lease_id
    assert calls == [first.lease_id, first.lease_id]
    assert len(list(db.scalars(select(VpnDeviceRow)).all())) == 1


def test_expired_vip_with_free_quota_gets_full_android_lease(Session, monkeypatch) -> None:
    token = make_user(
        Session,
        vip_status="active",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db = Session()
    db.add(awg_node())
    db.commit()
    monkeypatch.setattr("app.main.generate_wireguard_keypair", lambda: ("client-private", "client-public"))
    monkeypatch.setattr(
        "app.node_service.agent_add_peer",
        lambda *args, **kwargs: {"status": "added"},
    )

    config = get_vpn_node_config(
        "awg-1", authorization=bearer(token), x_xingsui_platform="android", db=db
    )
    assert config.entitlement.allowed
    assert config.entitlement.reason == "free_trial"
    assert config.expires_at > datetime.now(UTC) + timedelta(minutes=59)


def test_usage_renewal_is_bound_to_token_platform_and_lease(Session, monkeypatch) -> None:
    token = make_user(Session)
    db = Session()
    db.add(awg_node())
    db.commit()
    calls = []
    monkeypatch.setattr("app.main.generate_wireguard_keypair", lambda: ("client-private", "client-public"))
    monkeypatch.setattr(
        "app.node_service.agent_add_peer",
        lambda node, public_key, client_ip, lease_id, expires_at, **kwargs: calls.append(
            (public_key, lease_id, expires_at)
        ) or {"status": "added"},
    )
    config = get_vpn_node_config(
        "awg-1",
        authorization=bearer(token),
        x_xingsui_platform="android",
        db=db,
    )
    initial_expiry = config.expires_at
    entitlement = report_usage(
        UsageReportRequest(lease_id=config.lease_id, tunnel_name="xingsui"),
        authorization=bearer(token),
        x_xingsui_platform="android",
        db=db,
    )
    assert entitlement.allowed
    assert entitlement.lease_expires_at is not None
    assert entitlement.lease_expires_at >= initial_expiry
    assert calls[-1][1] == config.lease_id

    second_token = create_session(db, "u1")
    with pytest.raises(HTTPException) as exc:
        report_usage(
            UsageReportRequest(lease_id=config.lease_id),
            authorization=bearer(second_token),
            x_xingsui_platform="android",
            db=db,
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        report_usage(
            UsageReportRequest(lease_id=config.lease_id),
            authorization=bearer(token),
            x_xingsui_platform="windows",
            db=db,
        )
    assert exc.value.status_code == 403


def test_windows_vless_uses_new_uuid_for_each_lease(Session, monkeypatch) -> None:
    token = make_user(Session)
    db = Session()
    db.add(vless_node())
    db.commit()
    added = []
    removed = []
    monkeypatch.setattr(
        "app.node_service.agent_add_vless_user",
        lambda node, user_uuid, lease_id, expires_at, **kwargs: added.append(user_uuid) or {"status": "added"},
    )
    monkeypatch.setattr(
        "app.node_service.agent_remove_vless_user",
        lambda node, user_uuid, **kwargs: removed.append(user_uuid) or {"status": "removed"},
    )

    first = get_vpn_node_config(
        "vless-1",
        authorization=bearer(token),
        x_xingsui_platform="windows",
        db=db,
    )
    second = get_vpn_node_config(
        "vless-1",
        authorization=bearer(token),
        x_xingsui_platform="windows",
        db=db,
    )
    assert first.protocol == second.protocol == "vless"
    assert first.config_text == second.config_text == ""
    assert first.vless_config["uuid"] != second.vless_config["uuid"]
    assert "shared-legacy" not in first.vless_config["uuid"]
    assert removed == [first.vless_config["uuid"]]
    assert added == [first.vless_config["uuid"], second.vless_config["uuid"]]


def test_platform_protocol_mismatch_is_rejected_before_agent_call(Session, monkeypatch) -> None:
    token = make_user(Session)
    db = Session()
    db.add(vless_node())
    db.commit()
    monkeypatch.setattr(
        "app.node_service.agent_add_vless_user",
        lambda *args, **kwargs: pytest.fail("Agent must not be called"),
    )
    with pytest.raises(HTTPException) as exc:
        get_vpn_node_config(
            "vless-1",
            authorization=bearer(token),
            x_xingsui_platform="android",
            db=db,
        )
    assert exc.value.status_code == 403


def test_agent_failure_is_fail_closed_without_static_fallback(Session, monkeypatch) -> None:
    token = make_user(Session)
    db = Session()
    db.add(awg_node())
    db.commit()
    monkeypatch.setattr("app.main.generate_wireguard_keypair", lambda: ("client-private", "client-public"))
    monkeypatch.setattr(
        "app.node_service.agent_add_peer",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    with pytest.raises(HTTPException) as exc:
        get_vpn_node_config(
            "awg-1",
            authorization=bearer(token),
            x_xingsui_platform="android",
            db=db,
        )
    assert exc.value.status_code == 503
    assert db.scalar(select(VpnDeviceRow)) is None


def test_revoke_calls_owning_agent_even_when_auto_provision_is_false(Session, monkeypatch) -> None:
    token = make_user(Session)
    db = Session()
    node = awg_node()
    db.add(node)
    db.add(
        VpnDeviceRow(
            id="device-1",
            user_id="u1",
            node_id=node.id,
            protocol="awg",
            session_token_hash=hash_token(token),
            lease_id="lease-1",
            lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
            tunnel_name="xingsui",
            client_private_key="private",
            client_public_key="public",
            client_address="10.66.66.2/32",
            config_text="sensitive",
            status="active",
        )
    )
    db.commit()
    removed = []
    monkeypatch.setenv("VPN_AUTO_PROVISION", "false")
    monkeypatch.setattr(
        "app.node_service.agent_remove_peer",
        lambda owning_node, key, **kwargs: removed.append((owning_node.id, key)) or {"status": "removed"},
    )
    user = db.get(UserRow, "u1")
    revoke_vpn_devices(db, user)
    row = db.get(VpnDeviceRow, "device-1")
    assert removed == [(node.id, "public")]
    assert row.status == "revoked"
    assert row.config_text == ""
    assert row.client_private_key == ""


def test_sensitive_responses_are_no_store() -> None:
    assert sensitive_response_path("/vpn/config")
    assert sensitive_response_path("/vpn/nodes/node-1/config")
    response = Response()
    apply_no_store_headers(response)
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"


def test_heartbeat_signature_is_persistently_replay_protected(Session, monkeypatch) -> None:
    secret = "h" * 64
    monkeypatch.setenv("NODE_AGENT_SECRETS_JSON", json.dumps({"awg-1": secret}))
    node_service.AGENT_SEEN_NONCES.clear()
    db = Session()
    db.add(awg_node())
    db.commit()
    payload = NodeHeartbeatRequest(node_id="awg-1", peer_count=1, agent_version="test")
    signed_payload = payload.model_dump(mode="json")
    timestamp = str(int(datetime.now(UTC).timestamp()))
    nonce = "persistent-replay-nonce"
    signature = node_service.agent_signature(
        secret,
        method="POST",
        path="/internal/nodes/heartbeat",
        node_id="awg-1",
        timestamp=timestamp,
        nonce=nonce,
        payload=signed_payload,
    )
    heartbeat_request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/internal/nodes/heartbeat",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "scheme": "https",
        }
    )
    assert node_heartbeat(
        payload,
        heartbeat_request,
        x_xingsui_node_id="awg-1",
        x_xingsui_timestamp=timestamp,
        x_xingsui_nonce=nonce,
        x_xingsui_signature=signature,
        db=db,
    ) == {"status": "ok"}
    node_service.AGENT_SEEN_NONCES.clear()  # Simulate a different Uvicorn worker.
    with pytest.raises(HTTPException) as exc:
        node_heartbeat(
            payload,
            heartbeat_request,
            x_xingsui_node_id="awg-1",
            x_xingsui_timestamp=timestamp,
            x_xingsui_nonce=nonce,
            x_xingsui_signature=signature,
            db=db,
        )
    assert exc.value.status_code == 401


def test_eligible_subscription_nodes_skips_offline(Session) -> None:
    """Subscriptions omit offline nodes and retain an all-stale recovery fallback."""
    from app.db_models import VpnNodeHealthRow
    from app.main import eligible_subscription_nodes

    db = Session()
    live, dead = vless_node("live"), vless_node("dead")
    db.add_all([live, dead])
    now = datetime.now(UTC)
    db.add(VpnNodeHealthRow(node_id="live", last_heartbeat_at=now, peer_count=0, cpu_load=0.0))
    db.add(
        VpnNodeHealthRow(
            node_id="dead", last_heartbeat_at=now - timedelta(days=2), peer_count=0, cpu_load=0.0
        )
    )
    db.commit()

    assert [n.id for n in eligible_subscription_nodes(db)] == ["live"]

    # When all nodes are stale, retain enabled nodes to avoid an empty feed.
    db.query(VpnNodeHealthRow).filter(VpnNodeHealthRow.node_id == "live").update(
        {"last_heartbeat_at": now - timedelta(days=2)}
    )
    db.commit()
    assert sorted(n.id for n in eligible_subscription_nodes(db)) == ["dead", "live"]
    db.close()


def test_subscription_direct_ip_rule_precedes_proxy_fallback(Session) -> None:
    db = Session()
    token = make_user(Session, user_id="direct-rule")
    del token
    user = db.get(UserRow, "direct-rule")
    yaml = render_clash_yaml(
        user,
        [
            {
                "name": "星隧-新加坡",
                "type": "vless",
                "server": "64.90.24.84",
                "port": 10444,
            }
        ],
    )

    direct_rule = "  - IP-CIDR,153.75.95.10/32,DIRECT,no-resolve"
    fallback_rule = "  - MATCH,星隧"
    assert direct_rule in yaml
    assert yaml.index(direct_rule) < yaml.index(fallback_rule)
    db.close()
