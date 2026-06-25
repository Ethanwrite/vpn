"""控制面节点调度与 Agent 通信逻辑（方案 A）。

职责拆分到独立模块，便于纯函数单元测试（评分/选路/指纹/令牌校验），
HTTP 调用使用标准库 urllib，避免新增依赖。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import os
from typing import Any
import urllib.error
import urllib.request

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


def internal_api_token() -> str:
    return os.getenv("INTERNAL_API_TOKEN", "").strip()


def verify_internal_token(provided: str | None) -> bool:
    """常数时间比较内部令牌；未配置或不匹配一律拒绝。"""
    expected = internal_api_token()
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided.strip(), expected)


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


def build_vless_config(node: Any) -> dict[str, str] | None:
    params = parse_node_params(getattr(node, "params_json", "{}"))
    uuid = params.get("VlessUUID", "").strip()
    public_key = params.get("VlessPublicKey", "").strip()
    short_id = params.get("VlessShortId", "").strip()
    if not uuid or not public_key or not short_id:
        return None
    host = params.get("VlessHost", "").strip() or str(getattr(node, "endpoint", "")).rsplit(":", 1)[0]
    return {
        "server": host,
        "server_port": params.get("VlessPort", "8443").strip() or "8443",
        "uuid": uuid,
        "flow": params.get("VlessFlow", "").strip(),
        "public_key": public_key,
        "short_id": short_id,
        "server_name": params.get("VlessServerName", "www.microsoft.com").strip() or "www.microsoft.com",
        "utls_fingerprint": params.get("VlessFingerprint", "chrome").strip() or "chrome",
    }


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
    allowed_ips = (getattr(node, "allowed_ips", "0.0.0.0/0") or "0.0.0.0/0").strip()
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
    return f"http://{host}:{port}"


def agent_request(node: Any, path: str, payload: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
    """向边缘节点 Agent 发送带内部令牌的 JSON 请求。"""
    url = f"{agent_base_url(node)}{path}"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Internal-Token", internal_api_token())
    timeout = timeout if timeout is not None else agent_http_timeout()
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        raw = response.read().decode("utf-8") or "{}"
    return json.loads(raw)


def agent_add_peer(node: Any, public_key: str, client_ip: str, *, timeout: float | None = None) -> dict[str, Any]:
    return agent_request(node, "/peer/add", {"public_key": public_key, "allowed_ip": client_ip}, timeout=timeout)


def agent_remove_peer(node: Any, public_key: str, *, timeout: float | None = None) -> dict[str, Any]:
    return agent_request(node, "/peer/remove", {"public_key": public_key}, timeout=timeout)
