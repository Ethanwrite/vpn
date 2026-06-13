from datetime import UTC, datetime, timedelta
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
        server_public_key="SRVPUB",
        client_network="10.66.66.0/24",
        dns="1.1.1.1",
        allowed_ips="0.0.0.0/0",
        persistent_keepalive=25,
        mtu=1420,
        params_json='{"Jc":"4","Jmin":"40","H1":"1111","H2":"2222","H3":"3333","H4":"4444"}',
        weight=100,
        vip_only=False,
        max_clients=0,
        enabled=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def make_health(last_heartbeat_at, peer_count=0, cpu_load=0.0) -> SimpleNamespace:
    return SimpleNamespace(last_heartbeat_at=last_heartbeat_at, peer_count=peer_count, cpu_load=cpu_load)


def test_verify_internal_token(monkeypatch) -> None:
    monkeypatch.setenv("INTERNAL_API_TOKEN", "secret-token")
    assert node_service.verify_internal_token("secret-token")
    assert not node_service.verify_internal_token("wrong")
    assert not node_service.verify_internal_token(None)
    monkeypatch.delenv("INTERNAL_API_TOKEN", raising=False)
    assert not node_service.verify_internal_token("secret-token")


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
    assert "PublicKey = SRVPUB" in config
    assert "Endpoint = 1.2.3.4:443" in config
    assert "PersistentKeepalive = 25" in config


def test_node_status_label() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert node_service.node_status_label(make_health(now - timedelta(seconds=5)), now, 120) == "online"
    assert node_service.node_status_label(make_health(now - timedelta(seconds=600)), now, 120) == "offline"
    assert node_service.node_status_label(None, now, 120) == "offline"
