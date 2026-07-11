"""控制面节点调度与 Agent 通信逻辑（方案 A）。

职责拆分到独立模块，便于纯函数单元测试（评分/选路/指纹/令牌校验），
HTTP 调用使用标准库 urllib，避免新增依赖。
"""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import time
from typing import Any
import urllib.error
import urllib.request
from uuid import UUID

# AmneziaWG 混淆参数下发顺序（client/server 必须一致）。
AMNEZIA_PARAM_KEYS = (
    "Jc",
    "Jmin",
    "Jmax",
    "S1",
    "S2",
    "S3",
    "S4",
    "H1",
    "H2",
    "H3",
    "H4",
    "I1",
    "I2",
    "I3",
    "I4",
    "I5",
)


AGENT_SIGNATURE_WINDOW_SECONDS = 90
AGENT_SEEN_NONCES: dict[tuple[str, str], int] = {}


def _load_agent_secrets() -> dict[str, str]:
    """Load per-node secrets without storing them in the node database."""
    configured_path = os.getenv("NODE_AGENT_SECRETS_FILE", "").strip()
    raw = ""
    if configured_path:
        path = Path(configured_path)
        if path.is_file():
            raw = path.read_text(encoding="utf-8")
    if not raw:
        raw = os.getenv("NODE_AGENT_SECRETS_JSON", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value).strip() for key, value in parsed.items() if str(value).strip()}


def agent_secret_for_node(node_id: str) -> str:
    secret = _load_agent_secrets().get(node_id, "")
    if not secret:
        raise RuntimeError("node agent secret is not configured")
    return secret


def canonical_agent_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def agent_signature(
    secret: str,
    *,
    method: str,
    path: str,
    node_id: str,
    timestamp: str,
    nonce: str,
    payload: dict[str, Any],
) -> str:
    body_hash = hashlib.sha256(canonical_agent_payload(payload)).hexdigest()
    message = "\n".join((method.upper(), path, node_id, timestamp, nonce, body_hash))
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_agent_signature(
    *,
    node_id: str,
    method: str,
    path: str,
    payload: dict[str, Any],
    timestamp: str | None,
    nonce: str | None,
    signature: str | None,
    now: int | None = None,
) -> bool:
    if not timestamp or not nonce or not signature or len(nonce) < 16:
        return False
    try:
        issued_at = int(timestamp)
        secret = agent_secret_for_node(node_id)
    except (ValueError, RuntimeError):
        return False
    current = int(time.time()) if now is None else now
    if abs(current - issued_at) > AGENT_SIGNATURE_WINDOW_SECONDS:
        return False
    cutoff = current - AGENT_SIGNATURE_WINDOW_SECONDS
    for key, seen_at in list(AGENT_SEEN_NONCES.items()):
        if seen_at < cutoff:
            AGENT_SEEN_NONCES.pop(key, None)
    nonce_key = (node_id, nonce)
    if nonce_key in AGENT_SEEN_NONCES:
        return False
    expected = agent_signature(
        secret,
        method=method,
        path=path,
        node_id=node_id,
        timestamp=timestamp,
        nonce=nonce,
        payload=payload,
    )
    if not hmac.compare_digest(signature.strip(), expected):
        return False
    AGENT_SEEN_NONCES[nonce_key] = issued_at
    return True


def node_offline_after_seconds() -> int:
    try:
        return int(os.getenv("NODE_OFFLINE_AFTER_SECONDS", "120"))
    except ValueError:
        return 120


def agent_http_timeout() -> float:
    try:
        return float(os.getenv("AGENT_HTTP_TIMEOUT", "6"))
    except ValueError:
        return 6.0


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def node_is_online(
    last_heartbeat_at: datetime | None,
    now: datetime | None = None,
    offline_after_seconds: int | None = None,
) -> bool:
    seen = _coerce_utc(last_heartbeat_at)
    if seen is None:
        return False
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    window = offline_after_seconds if offline_after_seconds is not None else node_offline_after_seconds()
    return seen >= now - timedelta(seconds=window)


def node_load_ratio(peer_count: int, max_clients: int) -> float:
    """节点负载比 0..1；max_clients<=0 视为不限，返回 0。"""
    if max_clients <= 0:
        return 0.0
    return max(0.0, min(1.0, peer_count / max_clients))


def score_node(weight: int, peer_count: int, max_clients: int, cpu_load: float) -> float:
    """评分越高越优先：综合权重、剩余容量、CPU 负载。"""
    capacity_factor = 1.0 - node_load_ratio(peer_count, max_clients)
    cpu_factor = max(0.0, 1.0 - min(max(cpu_load, 0.0), 4.0) / 4.0)
    return max(0, weight) * (0.7 * capacity_factor + 0.3 * cpu_factor)


def parse_node_params(params_json: str | None) -> dict[str, str]:
    if not params_json:
        return {}
    try:
        data = json.loads(params_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def params_fingerprint(params: dict[str, str]) -> str:
    """对混淆参数生成稳定指纹，用于校验各节点配置一致性。"""
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def build_vless_config(node: Any, lease_uuid: str) -> dict[str, str] | None:
    params = parse_node_params(getattr(node, "params_json", "{}"))
    public_key = params.get("VlessPublicKey", "").strip()
    short_id = params.get("VlessShortId", "").strip()
    server_name = params.get("VlessServerName", "").strip()
    fingerprint = params.get("VlessFingerprint", "").strip()
    host = params.get("VlessHost", "").strip() or str(getattr(node, "endpoint", "")).rsplit(":", 1)[0]
    port = params.get("VlessPort", "").strip()
    if not lease_uuid or not host or not port or not public_key or not short_id or not server_name or not fingerprint:
        return None
    flow = params.get("VlessFlow", "").strip()
    try:
        UUID(lease_uuid)
        parsed_port = int(port)
        decoded_public_key = base64.urlsafe_b64decode(public_key + "=" * (-len(public_key) % 4))
    except (ValueError, TypeError, binascii.Error):
        return None
    if (
        not 1 <= parsed_port <= 65535
        or len(public_key) != 43
        or not re.fullmatch(r"[A-Za-z0-9_-]+", public_key)
        or len(decoded_public_key) != 32
    ):
        return None
    if not short_id or len(short_id) > 16 or len(short_id) % 2 or not re.fullmatch(r"[0-9A-Fa-f]+", short_id):
        return None
    if not valid_server_address(host) or not valid_dns_name(server_name):
        return None
    if fingerprint not in {"chrome", "firefox", "edge", "safari", "ios", "android", "360", "qq"}:
        return None
    if flow not in {"", "xtls-rprx-vision"}:
        return None
    return {
        "server": host,
        "server_port": port,
        "uuid": lease_uuid,
        "flow": flow,
        "public_key": public_key,
        "short_id": short_id,
        "server_name": server_name,
        "utls_fingerprint": fingerprint,
    }


def valid_dns_name(value: str) -> bool:
    value = str(value or "").strip()
    if not value or len(value) > 253 or "." not in value:
        return False
    try:
        ipaddress.ip_address(value)
        return False
    except ValueError:
        pass
    return all(
        0 < len(label) <= 63
        and not label.startswith("-")
        and not label.endswith("-")
        and re.fullmatch(r"[A-Za-z0-9-]+", label) is not None
        for label in value.split(".")
    )


def valid_server_address(value: str) -> bool:
    value = str(value or "").strip()
    if not value or any(character.isspace() for character in value):
        return False
    try:
        ipaddress.ip_address(value.strip("[]"))
        return True
    except ValueError:
        return valid_dns_name(value)


def node_protocol(node: Any) -> str:
    return str(getattr(node, "protocol", "awg") or "awg").strip().lower()


def node_supports_protocol(node: Any, protocol: str) -> bool:
    requested = str(protocol or "").strip().lower()
    configured = node_protocol(node)
    return requested in {"awg", "vless"} and configured in {requested, "dual"}


def valid_wireguard_key(value: object) -> bool:
    try:
        decoded = base64.b64decode(str(value or "").strip(), validate=True)
    except (ValueError, binascii.Error):
        return False
    return len(decoded) == 32


def node_config_is_complete(node: Any, protocol: str | None = None) -> bool:
    protocol = str(protocol or node_protocol(node)).strip().lower()
    if not node_supports_protocol(node, protocol):
        return False
    if protocol == "vless":
        return build_vless_config(node, "00000000-0000-4000-8000-000000000000") is not None
    endpoint = str(getattr(node, "endpoint", "") or "").strip()
    host, separator, port_text = endpoint.rpartition(":")
    if not separator or not host:
        return False
    if not str(getattr(node, "agent_host", "") or "").strip():
        return False
    if not valid_wireguard_key(getattr(node, "server_public_key", "")):
        return False
    try:
        ipaddress.ip_network(str(getattr(node, "client_network", "") or ""), strict=False)
        if not 1 <= int(port_text) <= 65535:
            return False
        if not 576 <= int(getattr(node, "mtu", 0) or 0) <= 9000:
            return False
        if not 1 <= int(getattr(node, "persistent_keepalive", 0) or 0) <= 65535:
            return False
    except (TypeError, ValueError):
        return False
    dns = str(getattr(node, "dns", "") or "").strip()
    allowed_ips = {
        item.strip()
        for item in str(getattr(node, "allowed_ips", "") or "").split(",")
        if item.strip()
    }
    if not dns or not {"0.0.0.0/0", "::/0"}.issubset(allowed_ips):
        return False
    params = parse_node_params(getattr(node, "params_json", "{}"))
    required = ("Jc", "Jmin", "Jmax", "S1", "S2", "H1", "H2", "H3", "H4")
    try:
        parsed = {key: int(str(params.get(key, "")).strip()) for key in required}
    except ValueError:
        return False
    headers = [parsed[key] for key in ("H1", "H2", "H3", "H4")]
    return (
        1 <= parsed["Jc"] <= 128
        and 0 <= parsed["Jmin"] <= parsed["Jmax"] <= 1280
        and parsed["S1"] >= 0
        and parsed["S2"] >= 0
        and parsed["S1"] + 56 != parsed["S2"]
        and len(set(headers)) == 4
        and all(value > 4 for value in headers)
    )


def node_status_label(health: Any, now: datetime | None = None, offline_after_seconds: int | None = None) -> str:
    last = getattr(health, "last_heartbeat_at", None) if health is not None else None
    return "online" if node_is_online(last, now, offline_after_seconds) else "offline"


def select_best_nodes(
    candidates: list[tuple[Any, Any]],
    *,
    vip: bool,
    now: datetime | None = None,
    offline_after_seconds: int | None = None,
) -> list[Any]:
    """从 (node, health) 列表中筛选可用节点并按评分降序返回。

    过滤规则：禁用 / 权重<=0 / vip_only 但非 VIP / 离线 / 已满 的节点剔除。
    """
    now = now or datetime.now(UTC)
    scored: list[tuple[float, int, Any]] = []
    for index, (node, health) in enumerate(candidates):
        if not getattr(node, "enabled", False):
            continue
        weight = int(getattr(node, "weight", 0) or 0)
        if weight <= 0:
            continue
        if getattr(node, "vip_only", False) and not vip:
            continue
        last = getattr(health, "last_heartbeat_at", None) if health is not None else None
        if not node_is_online(last, now, offline_after_seconds):
            continue
        peer_count = int(getattr(health, "peer_count", 0) or 0) if health is not None else 0
        max_clients = int(getattr(node, "max_clients", 0) or 0)
        if max_clients > 0 and peer_count >= max_clients:
            continue
        cpu_load = float(getattr(health, "cpu_load", 0.0) or 0.0) if health is not None else 0.0
        score = score_node(weight, peer_count, max_clients, cpu_load)
        scored.append((score, index, node))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [node for _, _, node in scored]


def render_node_client_config(node: Any, private_key: str, client_address: str) -> str:
    """基于节点存储参数（而非全局 env）渲染客户端配置。"""
    lines = [
        "[Interface]",
        f"PrivateKey = {private_key}",
        f"Address = {client_address}",
    ]
    dns = (getattr(node, "dns", "") or "").strip()
    if dns:
        lines.append(f"DNS = {dns}")
    mtu = getattr(node, "mtu", None)
    if mtu:
        lines.append(f"MTU = {mtu}")
    params = parse_node_params(getattr(node, "params_json", "{}"))
    for key in AMNEZIA_PARAM_KEYS:
        value = str(params.get(key, "")).strip()
        if value:
            lines.append(f"{key} = {value}")
    allowed_ips = (getattr(node, "allowed_ips", "0.0.0.0/0, ::/0") or "0.0.0.0/0, ::/0").strip()
    keepalive = getattr(node, "persistent_keepalive", None)
    lines.extend(
        [
            "",
            "[Peer]",
            f"PublicKey = {getattr(node, 'server_public_key', '')}",
            f"AllowedIPs = {allowed_ips}",
            f"Endpoint = {getattr(node, 'endpoint', '')}",
        ]
    )
    if keepalive:
        lines.append(f"PersistentKeepalive = {keepalive}")
    return "\n".join(lines) + "\n"


def agent_base_url(node: Any) -> str:
    host = getattr(node, "agent_host", "").strip()
    port = int(getattr(node, "agent_port", 0) or int(os.getenv("NODE_AGENT_PORT", "51821")))
    production = os.getenv("APP_ENV", "production").strip().lower() in {"prod", "production"}
    scheme = os.getenv("NODE_AGENT_SCHEME", "https" if production else "http").strip().lower()
    if production and scheme != "https":
        raise RuntimeError("plaintext node agent transport is disabled in production")
    if scheme not in {"http", "https"}:
        raise RuntimeError("invalid node agent scheme")
    return f"{scheme}://{host}:{port}"


def agent_ssl_context() -> ssl.SSLContext | None:
    if os.getenv("NODE_AGENT_SCHEME", "").strip().lower() != "https" and not (
        os.getenv("APP_ENV", "production").strip().lower() in {"prod", "production"}
    ):
        return None
    ca_file = os.getenv("NODE_AGENT_CA_FILE", "").strip() or None
    context = ssl.create_default_context(cafile=ca_file)
    cert_file = os.getenv("NODE_AGENT_CLIENT_CERT", "").strip()
    key_file = os.getenv("NODE_AGENT_CLIENT_KEY", "").strip()
    if bool(cert_file) != bool(key_file):
        raise RuntimeError("both node agent client certificate and key are required")
    if cert_file:
        context.load_cert_chain(cert_file, key_file)
    return context


def agent_request(node: Any, path: str, payload: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
    """Send an authenticated, replay-resistant request to one node Agent."""
    url = f"{agent_base_url(node)}{path}"
    node_id = str(getattr(node, "id", "") or "").strip()
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(18)
    secret = agent_secret_for_node(node_id)
    body = canonical_agent_payload(payload)
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Xingsui-Node-Id", node_id)
    request.add_header("X-Xingsui-Timestamp", timestamp)
    request.add_header("X-Xingsui-Nonce", nonce)
    request.add_header(
        "X-Xingsui-Signature",
        agent_signature(
            secret,
            method="POST",
            path=path,
            node_id=node_id,
            timestamp=timestamp,
            nonce=nonce,
            payload=payload,
        ),
    )
    timeout = timeout if timeout is not None else agent_http_timeout()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=agent_ssl_context()) as response:  # noqa: S310
            raw = response.read(65537)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("node agent request failed") from exc
    if len(raw) > 65536:
        raise RuntimeError("node agent response is too large")
    try:
        decoded = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("invalid node agent response") from exc
    if not isinstance(decoded, dict):
        raise RuntimeError("invalid node agent response")
    return decoded


def agent_add_peer(
    node: Any,
    public_key: str,
    client_ip: str,
    lease_id: str,
    expires_at: datetime,
    *,
    timeout: float | None = None,
) -> dict[str, Any]:
    return agent_request(
        node,
        "/peer/add",
        {
            "public_key": public_key,
            "allowed_ip": client_ip,
            "lease_id": lease_id,
            "expires_at": expires_at.astimezone(UTC).isoformat(),
        },
        timeout=timeout,
    )


def agent_remove_peer(node: Any, public_key: str, *, timeout: float | None = None) -> dict[str, Any]:
    return agent_request(node, "/peer/remove", {"public_key": public_key}, timeout=timeout)


def agent_add_vless_user(
    node: Any,
    user_uuid: str,
    lease_id: str,
    expires_at: datetime,
    *,
    timeout: float | None = None,
) -> dict[str, Any]:
    return agent_request(
        node,
        "/vless/add",
        {
            "uuid": user_uuid,
            "lease_id": lease_id,
            "expires_at": expires_at.astimezone(UTC).isoformat(),
        },
        timeout=timeout,
    )


def agent_remove_vless_user(node: Any, user_uuid: str, *, timeout: float | None = None) -> dict[str, Any]:
    return agent_request(node, "/vless/remove", {"uuid": user_uuid}, timeout=timeout)
