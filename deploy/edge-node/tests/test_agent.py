from datetime import UTC, datetime, timedelta
import base64
import importlib.util
import json
from pathlib import Path

import pytest


AGENT_PATH = Path(__file__).resolve().parents[1] / "agent.py"
SPEC = importlib.util.spec_from_file_location("xingsui_edge_agent", AGENT_PATH)
agent = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(agent)


@pytest.fixture(autouse=True)
def agent_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("XS_AGENT_ENV", "test")
    monkeypatch.setenv("XS_NODE_ID", "node-a")
    monkeypatch.setenv("XS_NODE_SECRET", "s" * 64)
    monkeypatch.setenv("XS_LEASE_STATE_PATH", str(tmp_path / "leases.json"))
    agent.NONCES.clear()
    agent.LEASES.clear()


def signed_headers(payload, *, timestamp="1800000000", nonce="nonce-with-enough-entropy"):
    return {
        "X-Xingsui-Node-Id": "node-a",
        "X-Xingsui-Timestamp": timestamp,
        "X-Xingsui-Nonce": nonce,
        "X-Xingsui-Signature": agent.signature_for(
            "s" * 64,
            method="POST",
            path="/peer/add",
            signed_node_id="node-a",
            timestamp=timestamp,
            nonce=nonce,
            payload=payload,
        ),
    }


def test_hmac_signature_is_node_bound_and_replay_safe() -> None:
    payload = {"lease_id": "lease-1", "allowed_ip": "10.0.0.2"}
    headers = signed_headers(payload)
    assert agent.verify_signature(headers, "POST", "/peer/add", payload, now=1_800_000_000)
    assert not agent.verify_signature(headers, "POST", "/peer/add", payload, now=1_800_000_000)
    agent.NONCES.clear()
    headers["X-Xingsui-Node-Id"] = "node-b"
    assert not agent.verify_signature(headers, "POST", "/peer/add", payload, now=1_800_000_000)


def test_public_key_ip_and_expiry_validation() -> None:
    key = base64.b64encode(b"k" * 32).decode()
    assert agent.validate_public_key(key) == key
    assert agent.validate_ip("10.0.0.2/32") == "10.0.0.2"
    now = datetime.now(UTC)
    assert agent.parse_expiry((now + timedelta(minutes=5)).isoformat(), now) > now
    assert agent.parse_expiry((now + timedelta(hours=1)).isoformat(), now) > now
    assert agent.parse_expiry(
        (now + timedelta(seconds=agent.MAX_LEASE_SECONDS + agent.LEASE_CLOCK_SKEW_SECONDS)).isoformat(),
        now,
    ) > now
    with pytest.raises(ValueError):
        agent.parse_expiry(
            (
                now
                + timedelta(
                    seconds=agent.MAX_LEASE_SECONDS + agent.LEASE_CLOCK_SKEW_SECONDS + 1,
                )
            ).isoformat(),
            now,
        )


def test_awg_status_and_usage_fail_closed_when_interface_read_fails(monkeypatch) -> None:
    monkeypatch.setenv("XS_MANAGED_PROTOCOLS", "awg")
    monkeypatch.setattr(agent, "run", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("awg down")))
    with pytest.raises(RuntimeError):
        agent.collect_status()
    with pytest.raises(RuntimeError):
        agent.peer_usage()


def test_expired_awg_lease_is_removed(monkeypatch) -> None:
    removed = []
    monkeypatch.setattr(agent, "remove_peer", lambda public_key: removed.append(public_key))
    agent.LEASES["lease-1"] = {
        "kind": "awg",
        "identity": "public-key",
        "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    }
    agent.cleanup_expired_leases()
    assert removed == ["public-key"]
    assert agent.LEASES == {}


def test_startup_reconciliation_removes_unmanaged_awg_peers(monkeypatch) -> None:
    managed = base64.b64encode(b"m" * 32).decode()
    legacy = base64.b64encode(b"l" * 32).decode()
    agent.LEASES["lease-managed"] = {
        "kind": "awg",
        "identity": managed,
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    }
    monkeypatch.setattr(agent, "run", lambda args, input_text=None: f"{managed}\n{legacy}\n")
    removed = []
    monkeypatch.setattr(agent, "remove_peer", lambda public_key: removed.append(public_key))
    agent.reconcile_awg_peers()
    assert removed == [legacy]


def test_vless_json_update_is_checked_and_atomic(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "sing-box.json"
    config_path.write_text(
        json.dumps({"inbounds": [{"type": "vless", "tag": "vless-in", "users": []}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("XS_VLESS_CONFIG", str(config_path))
    monkeypatch.setenv("XS_VLESS_INBOUND_TAG", "vless-in")
    checks = []
    monkeypatch.setattr(agent, "run", lambda args, input_text=None: checks.append(args) or "")
    monkeypatch.setattr(agent, "reload_vless_service", lambda: None)
    user_uuid = "11111111-1111-4111-8111-111111111111"

    agent.add_vless_user(user_uuid)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["inbounds"][0]["users"] == [{"uuid": user_uuid}]
    assert any("check" in args for args in checks)

    checks.clear()
    agent.add_vless_user(user_uuid)
    assert checks == []

    agent.remove_vless_user(user_uuid)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["inbounds"][0]["users"] == []


def test_expired_snapshot_does_not_remove_identity_with_newer_lease(monkeypatch) -> None:
    now = datetime.now(UTC)
    removed = []
    monkeypatch.setattr(agent, "remove_peer", lambda public_key: removed.append(public_key))
    agent.LEASES.update(
        {
            "old": {
                "kind": "awg",
                "identity": "same-public-key",
                "expires_at": (now - timedelta(seconds=1)).isoformat(),
            },
            "new": {
                "kind": "awg",
                "identity": "same-public-key",
                "expires_at": (now + timedelta(minutes=5)).isoformat(),
            },
        }
    )

    agent.cleanup_expired_leases(now)

    assert removed == []
    assert set(agent.LEASES) == {"new"}


def test_production_rejects_plaintext_agent(monkeypatch) -> None:
    monkeypatch.setenv("XS_AGENT_ENV", "production")
    monkeypatch.delenv("XS_AGENT_TLS_CERT", raising=False)
    monkeypatch.delenv("XS_AGENT_TLS_KEY", raising=False)
    with pytest.raises(SystemExit):
        agent.validate_startup_configuration()
