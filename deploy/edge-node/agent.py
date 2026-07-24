#!/usr/bin/env python3
"""Xingsui edge Agent with per-node HMAC authentication and finite leases."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import signal
import ssl
import subprocess
import threading
import time
import urllib.request
from uuid import UUID

AGENT_VERSION = "2.1.2"
MAX_REQUEST_BYTES = 64 * 1024
SIGNATURE_WINDOW_SECONDS = 90
MAX_LEASE_SECONDS = 60 * 60
# Control-plane and Agent clocks are independently synchronized. The control
# plane still signs at most MAX_LEASE_SECONDS, while the Agent accepts the same
# bounded skew already permitted for request signatures.
LEASE_CLOCK_SKEW_SECONDS = SIGNATURE_WINDOW_SECONDS
# Subscription VLESS users are long-lived (bound to the user's VIP expiry) rather
# than short leases: Clash-style clients import a static config and never renew a
# lease. Cap keeps a compromised control plane from minting effectively-permanent
# credentials; 400 days comfortably covers an annual VIP plan plus slack.
MAX_SUBSCRIPTION_SECONDS = 400 * 24 * 60 * 60
NONCES: dict[str, int] = {}
NONCE_LOCK = threading.Lock()
LEASE_LOCK = threading.RLock()
VLESS_LOCK = threading.RLock()
SUBSCRIPTION_LOCK = threading.RLock()
LEASES: dict[str, dict[str, object]] = {}
# uuid -> {"name": str, "expires_at": iso}. Long-lived subscription users that must
# survive reconcile until their VIP expiry, keyed so per-user usage is attributable.
SUBSCRIPTIONS: dict[str, dict[str, object]] = {}
UTC = timezone.utc


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def production_environment() -> bool:
    return env("XS_AGENT_ENV", env("APP_ENV", "production")).lower() in {"prod", "production"}


def node_id() -> str:
    return env("XS_NODE_ID")


def node_secret() -> str:
    return env("XS_NODE_SECRET")


def iface() -> str:
    return env("XS_WG_IFACE", "awg0")


def wg_tool() -> str:
    return env("XS_WG_TOOL", "awg")


def lease_state_path() -> Path:
    return Path(env("XS_LEASE_STATE_PATH", "/var/lib/xingsui-agent/leases.json"))


def canonical_payload(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def signature_for(
    secret: str,
    *,
    method: str,
    path: str,
    signed_node_id: str,
    timestamp: str,
    nonce: str,
    payload: dict,
) -> str:
    body_hash = hashlib.sha256(canonical_payload(payload)).hexdigest()
    message = "\n".join((method.upper(), path, signed_node_id, timestamp, nonce, body_hash))
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_signature(headers, method: str, path: str, payload: dict, now: int | None = None) -> bool:
    signed_node_id = (headers.get("X-Xingsui-Node-Id") or "").strip()
    timestamp = (headers.get("X-Xingsui-Timestamp") or "").strip()
    nonce = (headers.get("X-Xingsui-Nonce") or "").strip()
    provided = (headers.get("X-Xingsui-Signature") or "").strip()
    if signed_node_id != node_id() or not timestamp or len(nonce) < 16 or not provided:
        return False
    try:
        issued_at = int(timestamp)
    except ValueError:
        return False
    current = int(time.time()) if now is None else now
    if abs(current - issued_at) > SIGNATURE_WINDOW_SECONDS:
        return False
    secret = node_secret()
    if not secret:
        return False
    expected = signature_for(
        secret,
        method=method,
        path=path,
        signed_node_id=signed_node_id,
        timestamp=timestamp,
        nonce=nonce,
        payload=payload,
    )
    if not hmac.compare_digest(provided, expected):
        return False
    cutoff = current - SIGNATURE_WINDOW_SECONDS
    with NONCE_LOCK:
        for seen_nonce, seen_at in list(NONCES.items()):
            if seen_at < cutoff:
                NONCES.pop(seen_nonce, None)
        if nonce in NONCES:
            return False
        NONCES[nonce] = issued_at
    return True


def signed_headers(method: str, path: str, payload: dict) -> dict[str, str]:
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(18)
    return {
        "Content-Type": "application/json",
        "X-Xingsui-Node-Id": node_id(),
        "X-Xingsui-Timestamp": timestamp,
        "X-Xingsui-Nonce": nonce,
        "X-Xingsui-Signature": signature_for(
            node_secret(),
            method=method,
            path=path,
            signed_node_id=node_id(),
            timestamp=timestamp,
            nonce=nonce,
            payload=payload,
        ),
    }


def run(args: list[str], input_text: str | None = None) -> str:
    result = subprocess.run(args, input=input_text, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def validate_public_key(value: object) -> str:
    key = str(value or "").strip()
    try:
        decoded = base64.b64decode(key, validate=True)
    except Exception as exc:
        raise ValueError("invalid public key") from exc
    if len(decoded) != 32:
        raise ValueError("invalid public key")
    return key


def validate_ip(value: object) -> str:
    return str(ipaddress.ip_address(str(value or "").split("/", 1)[0].strip()))


def validate_uuid(value: object) -> str:
    return str(UUID(str(value or "").strip()))


def validate_lease_id(value: object) -> str:
    lease_id = str(value or "").strip()
    if not lease_id or len(lease_id) > 64:
        raise ValueError("invalid lease id")
    return lease_id


def parse_expiry(value: object, now: datetime | None = None) -> datetime:
    return _parse_expiry_bounded(value, MAX_LEASE_SECONDS + LEASE_CLOCK_SKEW_SECONDS, now)


def parse_subscription_expiry(value: object, now: datetime | None = None) -> datetime:
    return _parse_expiry_bounded(value, MAX_SUBSCRIPTION_SECONDS, now)


def _parse_expiry_bounded(value: object, max_seconds: int, now: datetime | None) -> datetime:
    now = now or datetime.now(UTC)
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        expires_at = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("invalid lease expiry") from exc
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    expires_at = expires_at.astimezone(UTC)
    if expires_at <= now or expires_at > now + timedelta(seconds=max_seconds):
        raise ValueError("invalid lease expiry")
    return expires_at


def validate_user_name(value: object) -> str:
    """Subscription/lease user label used to attribute per-user usage in sing-box
    logs. Restricted so it can be parsed back out of a log line unambiguously."""
    name = str(value or "").strip()
    if not name or len(name) > 80:
        raise ValueError("invalid user name")
    if any(ch.isspace() for ch in name) or "[" in name or "]" in name:
        raise ValueError("invalid user name")
    return name


def add_peer(public_key: str, allowed_ip: str) -> None:
    address = ipaddress.ip_address(allowed_ip)
    prefix = 32 if address.version == 4 else 128
    run([wg_tool(), "set", iface(), "peer", public_key, "allowed-ips", f"{address}/{prefix}"])


def remove_peer(public_key: str) -> None:
    run([wg_tool(), "set", iface(), "peer", public_key, "remove"])


def vless_config_path() -> Path:
    configured = env("XS_VLESS_CONFIG")
    if not configured:
        raise RuntimeError("VLESS config path is not configured")
    return Path(configured)


def vless_users(config: dict) -> list[dict]:
    inbounds = config.get("inbounds")
    if not isinstance(inbounds, list):
        raise RuntimeError("sing-box inbounds are missing")
    requested_tag = env("XS_VLESS_INBOUND_TAG")
    for inbound in inbounds:
        if not isinstance(inbound, dict) or inbound.get("type") != "vless":
            continue
        if requested_tag and inbound.get("tag") != requested_tag:
            continue
        users = inbound.setdefault("users", [])
        if not isinstance(users, list):
            raise RuntimeError("sing-box VLESS users are invalid")
        return users
    raise RuntimeError("sing-box VLESS inbound was not found")


def reload_vless_service() -> None:
    service = env("XS_VLESS_SERVICE")
    pid_file = env("XS_VLESS_PID_FILE")
    if service:
        run([env("XS_SYSTEMCTL_BIN", "/usr/bin/systemctl"), "reload", service])
        return
    if pid_file:
        pid = int(Path(pid_file).read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGHUP)
        return
    raise RuntimeError("VLESS reload target is not configured")


def write_vless_config(config: dict) -> None:
    path = vless_config_path()
    original = path.read_bytes()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(temporary, path.stat().st_mode & 0o777)
        run([env("XS_SING_BOX_BIN", "/usr/local/bin/sing-box"), "check", "-c", str(temporary)])
        os.replace(temporary, path)
        try:
            reload_vless_service()
        except Exception:
            rollback = path.with_name(f".{path.name}.{os.getpid()}.rollback")
            rollback.write_bytes(original)
            os.chmod(rollback, path.stat().st_mode & 0o777)
            os.replace(rollback, path)
            try:
                reload_vless_service()
            except Exception:
                pass
            raise
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def build_vless_user_entry(user_uuid: str, name: str | None) -> dict[str, str]:
    entry: dict[str, str] = {"uuid": user_uuid}
    flow = env("XS_VLESS_FLOW")
    if flow:
        entry["flow"] = flow
    # sing-box logs the user name in brackets on every accepted connection; it is
    # how per-user source-IP usage is attributed. Always tag when a name is known.
    if name:
        entry["name"] = name
    return entry


def mutate_vless_user(user_uuid: str, *, add: bool, name: str | None = None) -> None:
    with VLESS_LOCK:
        path = vless_config_path()
        config = json.loads(path.read_text(encoding="utf-8"))
        users = vless_users(config)
        desired = build_vless_user_entry(user_uuid, name)
        matching = [entry for entry in users if isinstance(entry, dict) and entry.get("uuid") == user_uuid]
        if add and len(matching) == 1 and matching[0] == desired:
            return
        if not add and not matching:
            return
        users[:] = [entry for entry in users if not isinstance(entry, dict) or entry.get("uuid") != user_uuid]
        if add:
            users.append(desired)
        write_vless_config(config)


def add_vless_user(user_uuid: str, name: str | None = None) -> None:
    mutate_vless_user(user_uuid, add=True, name=name)


def remove_vless_user(user_uuid: str) -> None:
    mutate_vless_user(user_uuid, add=False)


def load_leases() -> None:
    path = lease_state_path()
    if not path.is_file():
        return
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if isinstance(parsed, dict):
        with LEASE_LOCK:
            LEASES.clear()
            LEASES.update({str(key): value for key, value in parsed.items() if isinstance(value, dict)})


def save_leases() -> None:
    path = lease_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with LEASE_LOCK:
        temporary.write_text(json.dumps(LEASES, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def register_lease(lease_id: str, kind: str, identity: str, expires_at: datetime) -> None:
    validate_lease_id(lease_id)
    with LEASE_LOCK:
        for existing_id, lease in list(LEASES.items()):
            if lease.get("kind") == kind and lease.get("identity") == identity:
                LEASES.pop(existing_id, None)
        LEASES[lease_id] = {
            "kind": kind,
            "identity": identity,
            "expires_at": expires_at.astimezone(UTC).isoformat(),
        }
        save_leases()


def remove_lease_by_identity(kind: str, identity: str) -> None:
    with LEASE_LOCK:
        for lease_id, lease in list(LEASES.items()):
            if lease.get("kind") == kind and lease.get("identity") == identity:
                LEASES.pop(lease_id, None)
        save_leases()


def cleanup_expired_leases(now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    with LEASE_LOCK:
        changed = False
        for lease_id, lease in list(LEASES.items()):
            try:
                expires_at = datetime.fromisoformat(str(lease["expires_at"]).replace("Z", "+00:00"))
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                if expires_at > now:
                    continue
                kind = str(lease["kind"])
                identity = str(lease["identity"])
                newer_identity_lease = False
                for other_id, other in LEASES.items():
                    if other_id == lease_id or other.get("kind") != kind or other.get("identity") != identity:
                        continue
                    other_expiry = datetime.fromisoformat(str(other["expires_at"]).replace("Z", "+00:00"))
                    if other_expiry.tzinfo is None:
                        other_expiry = other_expiry.replace(tzinfo=UTC)
                    if other_expiry > now:
                        newer_identity_lease = True
                        break
                if not newer_identity_lease:
                    if kind == "awg":
                        remove_peer(identity)
                    elif kind == "vless":
                        remove_vless_user(identity)
                    else:
                        raise RuntimeError("unknown lease kind")
            except Exception:
                continue
            LEASES.pop(lease_id, None)
            changed = True
        if changed:
            save_leases()


def cleanup_loop() -> None:
    interval = max(5, int(env("XS_LEASE_CLEANUP_INTERVAL", "15") or "15"))
    while True:
        cleanup_expired_leases()
        # Enforce subscription expiry too: reconcile prunes expired subscription
        # users from both the registry and sing-box (they hold no short lease).
        protocols = {item.strip().lower() for item in env("XS_MANAGED_PROTOCOLS", "awg").split(",") if item.strip()}
        if "vless" in protocols:
            try:
                reconcile_vless_users()
            except Exception:
                pass
        time.sleep(interval)


def active_lease_identities(kind: str, now: datetime | None = None) -> set[str]:
    now = now or datetime.now(UTC)
    active: set[str] = set()
    with LEASE_LOCK:
        leases = list(LEASES.values())
    for lease in leases:
        if lease.get("kind") != kind:
            continue
        try:
            expires_at = datetime.fromisoformat(str(lease["expires_at"]).replace("Z", "+00:00"))
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at > now:
                active.add(str(lease["identity"]))
        except Exception:
            continue
    return active


def reconcile_awg_peers() -> None:
    known = active_lease_identities("awg")
    current = {line.strip() for line in run([wg_tool(), "show", iface(), "peers"]).splitlines() if line.strip()}
    for public_key in current - known:
        remove_peer(public_key)


def static_vless_uuids() -> set[str]:
    """Long-lived subscription UUIDs that must survive reconcile (no lease, never
    auto-removed). Sourced from a file so it can be updated without editing code."""
    path = Path(os.getenv("XS_STATIC_VLESS_UUIDS_FILE", "/etc/xingsui/static-vless-uuids.txt"))
    if not path.is_file():
        return set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    return {
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    }


def subscription_state_path() -> Path:
    return Path(os.getenv("XS_SUBSCRIPTION_STATE_PATH", "/var/lib/xingsui-agent/subscriptions.json"))


def load_subscriptions() -> None:
    path = subscription_state_path()
    if not path.is_file():
        return
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if isinstance(parsed, dict):
        with SUBSCRIPTION_LOCK:
            SUBSCRIPTIONS.clear()
            SUBSCRIPTIONS.update(
                {str(uuid): value for uuid, value in parsed.items() if isinstance(value, dict)}
            )


def save_subscriptions() -> None:
    path = subscription_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with SUBSCRIPTION_LOCK:
        temporary.write_text(json.dumps(SUBSCRIPTIONS, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def register_subscription(user_uuid: str, name: str, expires_at: datetime) -> None:
    with SUBSCRIPTION_LOCK:
        SUBSCRIPTIONS[user_uuid] = {"name": name, "expires_at": expires_at.astimezone(UTC).isoformat()}
        save_subscriptions()


def remove_subscription(user_uuid: str) -> None:
    with SUBSCRIPTION_LOCK:
        if SUBSCRIPTIONS.pop(user_uuid, None) is not None:
            save_subscriptions()


def active_subscriptions(now: datetime | None = None) -> dict[str, str]:
    """Return {uuid: name} for subscription users whose expiry is still in the future.
    Expired entries are pruned from the registry (and their sing-box user removed)."""
    now = now or datetime.now(UTC)
    active: dict[str, str] = {}
    changed = False
    with SUBSCRIPTION_LOCK:
        for user_uuid, value in list(SUBSCRIPTIONS.items()):
            try:
                expires_at = datetime.fromisoformat(str(value["expires_at"]).replace("Z", "+00:00"))
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
            except Exception:
                SUBSCRIPTIONS.pop(user_uuid, None)
                changed = True
                continue
            if expires_at > now:
                active[user_uuid] = str(value.get("name") or "")
            else:
                SUBSCRIPTIONS.pop(user_uuid, None)
                changed = True
        if changed:
            save_subscriptions()
    return active


def reconcile_vless_users() -> None:
    lease_uuids = active_lease_identities("vless")
    static_uuids = static_vless_uuids()
    subscriptions = active_subscriptions()
    known = lease_uuids | static_uuids | set(subscriptions.keys())
    with VLESS_LOCK:
        path = vless_config_path()
        config = json.loads(path.read_text(encoding="utf-8"))
        users = vless_users(config)
        desired: list[dict] = []
        seen: set[str] = set()
        for entry in users:
            if not isinstance(entry, dict):
                continue
            user_uuid = entry.get("uuid")
            if user_uuid not in known or user_uuid in seen:
                continue
            seen.add(str(user_uuid))
            # Keep subscription users tagged with their attribution name.
            if user_uuid in subscriptions and subscriptions[user_uuid]:
                desired.append(build_vless_user_entry(str(user_uuid), subscriptions[user_uuid]))
            else:
                desired.append(entry)
        # Re-add any subscription user missing from the config (e.g. after a manual edit).
        for user_uuid, name in subscriptions.items():
            if user_uuid not in seen:
                desired.append(build_vless_user_entry(user_uuid, name or None))
        if desired != users:
            users[:] = desired
            write_vless_config(config)


def reconcile_managed_credentials() -> None:
    protocols = {item.strip().lower() for item in env("XS_MANAGED_PROTOCOLS", "awg").split(",") if item.strip()}
    if "awg" in protocols:
        reconcile_awg_peers()
    if "vless" in protocols:
        reconcile_vless_users()


def collect_status() -> dict[str, float]:
    peer_count = rx = tx = 0
    protocols = {item.strip().lower() for item in env("XS_MANAGED_PROTOCOLS", "awg").split(",") if item.strip()}
    if "awg" in protocols:
        dump = run([wg_tool(), "show", iface(), "dump"])
        lines = [line for line in dump.splitlines() if line.strip()]
        for line in lines[1:]:
            columns = line.split("\t")
            peer_count += 1
            if len(columns) >= 7:
                rx += int(columns[5] or 0)
                tx += int(columns[6] or 0)
    cpu_load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    return {
        "peer_count": peer_count,
        "rx_bytes": rx,
        "tx_bytes": tx,
        "cpu_load": cpu_load,
        "mem_used_percent": mem_used_percent(),
    }


def peer_usage() -> dict[str, int]:
    """Cumulative rx+tx bytes per awg peer public key, read from the live interface.

    This is the authoritative, tamper-proof usage source: it reflects bytes actually
    forwarded for each peer, independent of any client self-report.
    """
    usage: dict[str, int] = {}
    dump = run([wg_tool(), "show", iface(), "dump"])
    for line in dump.splitlines()[1:]:  # first line describes the interface, not a peer
        columns = line.split("\t")
        if len(columns) < 7:
            continue
        public_key = columns[0].strip()
        if not public_key:
            continue
        try:
            usage[public_key] = int(columns[5] or 0) + int(columns[6] or 0)
        except ValueError:
            continue
    return usage


# sing-box (log level info) emits two correlated lines per accepted VLESS connection,
# with the connection id as "[<id> <duration>]" and ANSI colour codes around fields:
#   INFO [<id> 0ms] inbound/vless[<tag>]: inbound connection from <SRC_IP>:<port>
#   INFO [<id> Nms] inbound/vless[<tag>]: [<user_name>] inbound connection to <dst>
# XTLS-vision splices to the kernel after the handshake, so byte counters are not
# available per user; the source IP set per user is, and is the signal that matters
# for detecting shared/leaked subscription credentials.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_CONN_FROM_RE = re.compile(r"\[(\d+) [^\]]*\] inbound/vless\[[^\]]*\]: inbound connection from ([0-9A-Fa-f:.]+):\d+")
_CONN_USER_RE = re.compile(r"\[(\d+) [^\]]*\] inbound/vless\[[^\]]*\]: \[([^\]\s]+)\] inbound connection to ")


def vless_usage(window_seconds: int | None = None) -> dict[str, dict[str, object]]:
    """Per-user (by sing-box user name) connection audit over a recent window.

    Returns {name: {"distinct_source_ips": int, "connections": int,
    "source_ips": [str, ...]}}. Attribution comes from the user name tagged on each
    VLESS user; a subscription credential that is being shared/leaked shows up as an
    abnormally large distinct-source-IP count for a single name.
    """
    window_seconds = window_seconds or int(env("XS_VLESS_USAGE_WINDOW_SECONDS", "1800") or "1800")
    service = env("XS_VLESS_SERVICE")
    if not service:
        return {}
    try:
        log = run(
            [
                env("XS_JOURNALCTL_BIN", "/usr/bin/journalctl"),
                "-u",
                service,
                "--since",
                f"-{int(window_seconds)}s",
                "--no-pager",
                "-o",
                "cat",
            ]
        )
    except Exception:
        return {}
    conn_source: dict[str, str] = {}
    conn_user: dict[str, str] = {}
    for raw_line in log.splitlines():
        line = _ANSI_RE.sub("", raw_line)
        match_from = _CONN_FROM_RE.search(line)
        if match_from:
            conn_source[match_from.group(1)] = match_from.group(2)
            continue
        match_user = _CONN_USER_RE.search(line)
        if match_user:
            conn_user[match_user.group(1)] = match_user.group(2)
    per_user_ips: dict[str, set[str]] = {}
    per_user_conns: dict[str, int] = {}
    for conn_id, name in conn_user.items():
        per_user_conns[name] = per_user_conns.get(name, 0) + 1
        source_ip = conn_source.get(conn_id)
        if source_ip:
            per_user_ips.setdefault(name, set()).add(source_ip)
    usage: dict[str, dict[str, object]] = {}
    for name, count in per_user_conns.items():
        ips = sorted(per_user_ips.get(name, set()))
        usage[name] = {
            "distinct_source_ips": len(ips),
            "connections": count,
            "source_ips": ips[:64],
        }
    return usage


def mem_used_percent() -> float:
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, _, rest = line.partition(":")
                info[key.strip()] = int(rest.strip().split()[0])
        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", 0)
        return round((total - available) / total * 100, 2) if total > 0 else 0.0
    except Exception:
        return 0.0


def control_plane_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=env("XS_CONTROL_PLANE_CA_FILE") or None)
    cert_file = env("XS_CONTROL_PLANE_CLIENT_CERT")
    key_file = env("XS_CONTROL_PLANE_CLIENT_KEY")
    if bool(cert_file) != bool(key_file):
        raise RuntimeError("both control-plane client certificate and key are required")
    if cert_file:
        context.load_cert_chain(cert_file, key_file)
    return context


def heartbeat_loop() -> None:
    base = env("XS_CONTROL_PLANE_URL").rstrip("/")
    interval = max(10, int(env("XS_HEARTBEAT_INTERVAL", "30") or "30"))
    if not base:
        return
    path = "/internal/nodes/heartbeat"
    url = f"{base}{path}"
    while True:
        try:
            payload = {"node_id": node_id(), "agent_version": AGENT_VERSION, **collect_status()}
            request = urllib.request.Request(url, data=canonical_payload(payload), method="POST")
            for key, value in signed_headers("POST", path, payload).items():
                request.add_header(key, value)
            urllib.request.urlopen(request, timeout=8, context=control_plane_ssl_context()).read(65536)
        except Exception:
            pass
        time.sleep(interval)


class Handler(BaseHTTPRequestHandler):
    server_version = f"xingsui-agent/{AGENT_VERSION}"

    def log_message(self, *_args) -> None:
        return

    def _send(self, status: int, payload: dict) -> None:
        body = canonical_payload(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("invalid request size")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        return payload

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send(200, {"status": "ok", "version": AGENT_VERSION})
            return
        self._send(404, {"detail": "not found"})

    def do_POST(self) -> None:
        try:
            payload = self._read_json()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            self._send(400, {"detail": "invalid request"})
            return
        path = self.path.split("?", 1)[0]
        if not verify_signature(self.headers, "POST", path, payload):
            self._send(401, {"detail": "unauthorized"})
            return
        try:
            if path == "/peer/add":
                public_key = validate_public_key(payload.get("public_key"))
                allowed_ip = validate_ip(payload.get("allowed_ip"))
                lease_id = validate_lease_id(payload.get("lease_id"))
                expires_at = parse_expiry(payload.get("expires_at"))
                with LEASE_LOCK:
                    try:
                        add_peer(public_key, allowed_ip)
                        register_lease(lease_id, "awg", public_key, expires_at)
                    except Exception:
                        try:
                            remove_peer(public_key)
                        except Exception:
                            pass
                        raise
                self._send(200, {"status": "added"})
            elif path == "/peer/remove":
                public_key = validate_public_key(payload.get("public_key"))
                with LEASE_LOCK:
                    remove_peer(public_key)
                    remove_lease_by_identity("awg", public_key)
                self._send(200, {"status": "removed"})
            elif path == "/peer/usage":
                # Read-only: authoritative per-peer transfer for server-side free-quota
                # enforcement. No lease lock needed (wg show does not mutate state).
                self._send(200, {"peers": peer_usage()})
            elif path == "/vless/add":
                user_uuid = validate_uuid(payload.get("uuid"))
                lease_id = validate_lease_id(payload.get("lease_id"))
                expires_at = parse_expiry(payload.get("expires_at"))
                name = validate_user_name(payload["name"]) if payload.get("name") else None
                with LEASE_LOCK:
                    try:
                        add_vless_user(user_uuid, name)
                        register_lease(lease_id, "vless", user_uuid, expires_at)
                    except Exception:
                        try:
                            remove_vless_user(user_uuid)
                        except Exception:
                            pass
                        raise
                self._send(200, {"status": "added"})
            elif path == "/vless/remove":
                user_uuid = validate_uuid(payload.get("uuid"))
                with LEASE_LOCK:
                    remove_vless_user(user_uuid)
                    remove_lease_by_identity("vless", user_uuid)
                self._send(200, {"status": "removed"})
            elif path == "/vless/subscription/add":
                user_uuid = validate_uuid(payload.get("uuid"))
                name = validate_user_name(payload.get("name"))
                expires_at = parse_subscription_expiry(payload.get("expires_at"))
                with LEASE_LOCK:
                    try:
                        add_vless_user(user_uuid, name)
                        register_subscription(user_uuid, name, expires_at)
                    except Exception:
                        try:
                            remove_vless_user(user_uuid)
                        except Exception:
                            pass
                        raise
                self._send(200, {"status": "added"})
            elif path == "/vless/subscription/remove":
                user_uuid = validate_uuid(payload.get("uuid"))
                with LEASE_LOCK:
                    remove_vless_user(user_uuid)
                    remove_subscription(user_uuid)
                self._send(200, {"status": "removed"})
            elif path == "/vless/usage":
                # Read-only per-user connection/source-IP audit (see vless_usage).
                self._send(200, {"users": vless_usage()})
            else:
                self._send(404, {"detail": "not found"})
        except (ValueError, RuntimeError, subprocess.CalledProcessError, OSError):
            self._send(503, {"detail": "operation failed"})


def validate_startup_configuration() -> None:
    if not node_id():
        raise SystemExit("XS_NODE_ID is required")
    if len(node_secret()) < 32:
        raise SystemExit("XS_NODE_SECRET must contain at least 32 characters")
    base = env("XS_CONTROL_PLANE_URL")
    if production_environment() and base and not base.lower().startswith("https://"):
        raise SystemExit("production heartbeat requires HTTPS")
    cert_file = env("XS_AGENT_TLS_CERT")
    key_file = env("XS_AGENT_TLS_KEY")
    if bool(cert_file) != bool(key_file):
        raise SystemExit("both XS_AGENT_TLS_CERT and XS_AGENT_TLS_KEY are required")
    if production_environment() and (not cert_file or not key_file):
        raise SystemExit("production Agent requires TLS certificate and key")


def main() -> None:
    validate_startup_configuration()
    load_leases()
    load_subscriptions()
    cleanup_expired_leases()
    reconcile_managed_credentials()
    threading.Thread(target=cleanup_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    listen = env("XS_AGENT_LISTEN", "127.0.0.1")
    port = int(env("XS_AGENT_PORT", "51821") or "51821")
    server = ThreadingHTTPServer((listen, port), Handler)
    cert_file = env("XS_AGENT_TLS_CERT")
    key_file = env("XS_AGENT_TLS_KEY")
    if cert_file:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(cert_file, key_file)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    print(f"xingsui agent {AGENT_VERSION} listening on {listen}:{port} iface={iface()}")
    server.serve_forever()


if __name__ == "__main__":
    main()
