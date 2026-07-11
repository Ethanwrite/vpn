from datetime import UTC, datetime, timedelta
import json
from types import SimpleNamespace

from app import node_service


def make_node(**overrides) -> SimpleNamespace:
    base = dict(
        id="n1",
        name="节点1",
        region="日本",
        endpoint="1.2.3.4:443",
        agent_host="1.2.3.4",
        agent_port=51821,
        server_public_key="a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=",
        client_network="10.66.66.0/24",
        dns="1.1.1.1",
        allowed_ips="0.0.0.0/0, ::/0",
        persistent_keepalive=25,
        mtu=1420,
        protocol="awg",
        params_json='{"Jc":"4","Jmin":"40","Jmax":"70","S1":"86","S2":"574","H1":"1111","H2":"2222","H3":"3333","H4":"4444"}',
        weight=100,
        vip_only=False,
        max_clients=0,
        enabled=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def make_health(last_heartbeat_at, peer_count=0, cpu_load=0.0) -> SimpleNamespace:
    return SimpleNamespace(last_heartbeat_at=last_heartbeat_at, peer_count=peer_count, cpu_load=cpu_load)


def test_verify_per_node_signature_and_replay(monkeypatch) -> None:
    secret = "a" * 64
    monkeypatch.setenv("NODE_AGENT_SECRETS_JSON", json.dumps({"n1": secret}))
    node_service.AGENT_SEEN_NONCES.clear()
    payload = {"node_id": "n1", "peer_count": 1}
    timestamp = "1800000000"
    nonce = "nonce-with-enough-entropy"
    signature = node_service.agent_signature(
        secret,
        method="POST",
        path="/internal/nodes/heartbeat",
        node_id="n1",
        timestamp=timestamp,
        nonce=nonce,
        payload=payload,
    )
    kwargs = dict(
        node_id="n1",
        method="POST",
        path="/internal/nodes/heartbeat",
        payload=payload,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        now=1_800_000_000,
    )
    assert node_service.verify_agent_signature(**kwargs)
    assert not node_service.verify_agent_signature(**kwargs)
    node_service.AGENT_SEEN_NONCES.clear()
    assert not node_service.verify_agent_signature(**{**kwargs, "node_id": "n2"})


def test_node_is_online_window() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert node_service.node_is_online(now - timedelta(seconds=30), now, 120)
    assert not node_service.node_is_online(now - timedelta(seconds=300), now, 120)
    assert not node_service.node_is_online(None, now, 120)


def test_node_load_ratio() -> None:
    assert node_service.node_load_ratio(50, 0) == 0.0
    assert node_service.node_load_ratio(50, 100) == 0.5
    assert node_service.node_load_ratio(150, 100) == 1.0


def test_score_node_prefers_capacity_and_low_cpu() -> None:
    idle = node_service.score_node(100, 0, 100, 0.0)
    busy = node_service.score_node(100, 90, 100, 0.0)
    loaded_cpu = node_service.score_node(100, 0, 100, 4.0)
    assert idle > busy
    assert idle > loaded_cpu


def test_select_best_nodes_filters_and_orders() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    online = make_health(now - timedelta(seconds=10), peer_count=10, cpu_load=0.1)
    stale = make_health(now - timedelta(seconds=600))
    candidates = [
        (make_node(id="busy", weight=100, max_clients=100), make_health(now - timedelta(seconds=10), peer_count=90, cpu_load=0.1)),
        (make_node(id="idle", weight=100, max_clients=100), online),
        (make_node(id="disabled", enabled=False), online),
        (make_node(id="zero-weight", weight=0), online),
        (make_node(id="vip", vip_only=True), online),
        (make_node(id="offline"), stale),
        (make_node(id="full", max_clients=10), make_health(now - timedelta(seconds=10), peer_count=10)),
    ]
    result = node_service.select_best_nodes(candidates, vip=False, now=now, offline_after_seconds=120)
    ids = [node.id for node in result]
    assert ids[0] == "idle"
    assert "busy" in ids
    assert "disabled" not in ids
    assert "zero-weight" not in ids
    assert "vip" not in ids
    assert "offline" not in ids
    assert "full" not in ids


def test_select_best_nodes_vip_sees_vip_only() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    online = make_health(now - timedelta(seconds=10))
    candidates = [(make_node(id="vip", vip_only=True), online)]
    assert [n.id for n in node_service.select_best_nodes(candidates, vip=True, now=now, offline_after_seconds=120)] == ["vip"]
    assert node_service.select_best_nodes(candidates, vip=False, now=now, offline_after_seconds=120) == []


def test_parse_node_params_handles_bad_input() -> None:
    assert node_service.parse_node_params('{"Jc":"4"}') == {"Jc": "4"}
    assert node_service.parse_node_params("not json") == {}
    assert node_service.parse_node_params("[1,2]") == {}
    assert node_service.parse_node_params(None) == {}


def test_params_fingerprint_is_order_independent() -> None:
    a = node_service.params_fingerprint({"Jc": "4", "Jmin": "40"})
    b = node_service.params_fingerprint({"Jmin": "40", "Jc": "4"})
    c = node_service.params_fingerprint({"Jc": "5", "Jmin": "40"})
    assert a == b
    assert a != c


def test_render_node_client_config_emits_params_and_peer() -> None:
    node = make_node()
    config = node_service.render_node_client_config(node, "CLIENTPRIV", "10.66.66.2/32")
    assert "[Interface]" in config
    assert "PrivateKey = CLIENTPRIV" in config
    assert "Address = 10.66.66.2/32" in config
    assert "DNS = 1.1.1.1" in config
    assert "Jc = 4" in config
    assert "H1 = 1111" in config
    assert "[Peer]" in config
    assert "PublicKey = a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=" in config
    assert "Endpoint = 1.2.3.4:443" in config
    assert "PersistentKeepalive = 25" in config


def test_vless_config_uses_dynamic_lease_uuid_and_requires_complete_reality() -> None:
    node = make_node(
        protocol="vless",
        endpoint="198.51.100.20:8443",
        params_json=(
            '{"VlessUUID":"legacy-shared","VlessHost":"198.51.100.20",'
            '"VlessPort":"8443","VlessPublicKey":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",'
            '"VlessShortId":"0011223344556677","VlessServerName":"example.com",'
            '"VlessFingerprint":"chrome","VlessFlow":"xtls-rprx-vision"}'
        ),
    )
    dynamic_uuid = "11111111-1111-4111-8111-111111111111"
    config = node_service.build_vless_config(node, dynamic_uuid)
    assert config["uuid"] == dynamic_uuid
    assert config["uuid"] != "legacy-shared"
    assert node_service.node_config_is_complete(node)


def test_awg_completeness_requires_dns_keepalive_and_dual_stack_routes() -> None:
    assert node_service.node_config_is_complete(make_node())
    assert not node_service.node_config_is_complete(make_node(dns=""))
    assert not node_service.node_config_is_complete(make_node(persistent_keepalive=0))
    assert not node_service.node_config_is_complete(make_node(allowed_ips="0.0.0.0/0"))


def test_vless_completeness_rejects_invalid_reality_identity_fields() -> None:
    valid = make_node(
        protocol="vless",
        endpoint="198.51.100.20:8443",
        params_json=(
            '{"VlessHost":"198.51.100.20","VlessPort":"8443",'
            '"VlessPublicKey":"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",'
            '"VlessShortId":"0011223344556677","VlessServerName":"example.com",'
            '"VlessFingerprint":"chrome","VlessFlow":"xtls-rprx-vision"}'
        ),
    )
    assert node_service.node_config_is_complete(valid, "vless")
    params = json.loads(valid.params_json)
    for field, rejected in (
        ("VlessServerName", "198.51.100.20"),
        ("VlessFingerprint", "unsupported"),
        ("VlessFlow", "unsafe-flow"),
        ("VlessShortId", "not-hex"),
    ):
        broken = dict(params)
        broken[field] = rejected
        assert not node_service.node_config_is_complete(
            make_node(protocol="vless", endpoint=valid.endpoint, params_json=json.dumps(broken)),
            "vless",
        )


def test_node_status_label() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert node_service.node_status_label(make_health(now - timedelta(seconds=5)), now, 120) == "online"
    assert node_service.node_status_label(make_health(now - timedelta(seconds=600)), now, 120) == "offline"
    assert node_service.node_status_label(None, now, 120) == "offline"
