from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from enum import StrEnum
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
from urllib.parse import parse_qs
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import node_service
from app.admin_page import ADMIN_HTML
from app.database import SessionLocal, init_database
from app.db_models import (
    AuthSessionRow,
    InvitationRow,
    OrderRow,
    PaymentSettingRow,
    PromotionActivityRow,
    UserRow,
    VipPlanRow,
    VpnDeviceRow,
    VpnNodeHealthRow,
    VpnNodeRow,
    WithdrawalRow,
)
from app.site_page import SITE_HTML


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    seed_database()
    restore_active_vpn_peers()
    yield


app = FastAPI(title="Xingsui Commercial API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ADMIN_SESSION_COOKIE = "xingsui_admin_session"
ADMIN_SESSION_MAX_AGE_SECONDS = 60 * 60 * 8
APP_VERSION_CODE = int(os.getenv("APP_VERSION_CODE", "13"))
APP_VERSION_NAME = os.getenv("APP_VERSION_NAME", "2.0.3")
MIN_SUPPORTED_APP_VERSION_CODE = int(os.getenv("MIN_SUPPORTED_APP_VERSION_CODE", "13"))


def admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "CHANGE_ME_ADMIN_PASSWORD")


def admin_session_secret() -> str:
    return os.getenv("ADMIN_SESSION_SECRET", admin_password())


def admin_session_token() -> str:
    return hmac.new(
        admin_session_secret().encode("utf-8"),
        admin_password().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def admin_password_valid(password: str | None) -> bool:
    return bool(password) and secrets.compare_digest(password, admin_password())


def admin_session_valid(token: str | None) -> bool:
    return bool(token) and secrets.compare_digest(token, admin_session_token())


def render_admin_login(error: bool = False) -> str:
    error_html = "<p class=\"error\">密码错误，请重新输入。</p>" if error else ""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>星隧 Admin 登录</title>
  <style>
    :root {{ color-scheme: dark; --bg: #061120; --panel: #0b1b2f; --line: #24415f; --text: #eef7ff; --muted: #91a8ba; --cyan: #20e6d2; --danger: #ff6b7a; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; display: grid; place-items: center; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: radial-gradient(circle at top, #162f55 0, #061120 48%, #030812 100%); color: var(--text); }}
    form {{ width: min(92vw, 380px); background: rgba(11, 27, 47, .94); border: 1px solid var(--line); border-radius: 8px; padding: 24px; box-shadow: 0 24px 80px rgba(0, 0, 0, .36); }}
    h1 {{ margin: 0 0 6px; font-size: 22px; }}
    p {{ margin: 0 0 18px; color: var(--muted); }}
    label {{ display: block; margin-bottom: 8px; color: var(--muted); font-size: 13px; }}
    input, button {{ width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 12px; font: inherit; }}
    input {{ background: #10243b; color: var(--text); margin-bottom: 14px; }}
    button {{ background: linear-gradient(135deg, #20e6d2, #7c5cff); color: #03101d; border: 0; font-weight: 700; cursor: pointer; }}
    .error {{ color: var(--danger); margin-top: -4px; }}
  </style>
</head>
<body>
  <form method="post" action="/admin/login">
    <h1>星隧 Admin</h1>
    <p>请输入后台管理密码</p>
    {error_html}
    <label for="password">密码</label>
    <input id="password" name="password" type="password" autocomplete="current-password" autofocus />
    <button type="submit">进入后台</button>
  </form>
</body>
</html>"""


@app.middleware("http")
async def protect_admin_routes(request: Request, call_next):
    path = request.url.path
    if path == "/api":
        request.scope["path"] = "/"
        path = "/"
    elif path.startswith("/api/"):
        request.scope["path"] = path[4:]
        path = request.scope["path"]
    if path == "/admin/login" or path == "/admin/logout":
        return await call_next(request)
    if path == "/admin" or path.startswith("/admin/"):
        if not admin_session_valid(request.cookies.get(ADMIN_SESSION_COOKIE)):
            if path == "/admin":
                return HTMLResponse(render_admin_login(), status_code=200)
            return Response("Admin authentication required", status_code=401)
    return await call_next(request)


class PayChannel(StrEnum):
    wechat = "wechat"
    alipay = "alipay"


class OrderStatus(StrEnum):
    pending_payment = "pending_payment"
    pending_confirm = "pending_confirm"
    completed = "completed"
    cancelled = "cancelled"
    rejected = "rejected"


class WithdrawalStatus(StrEnum):
    pending = "pending"
    completed = "completed"
    rejected = "rejected"


class VipPlan(BaseModel):
    id: str
    name: str
    duration_days: int
    original_price_cents: int
    sale_price_cents: int


class PromotionActivity(BaseModel):
    id: str
    name: str
    tag: str
    plan_id: str
    starts_at: datetime
    ends_at: datetime
    promo_price_cents: int
    invite_extra_discount_cents: int = 0
    stackable: bool = False
    new_user_only: bool = False
    countdown_enabled: bool = True
    status: str = "active"


class AdminPromotionRequest(BaseModel):
    id: str | None = None
    name: str
    tag: str = "限时特惠"
    plan_id: str = "plan_month"
    starts_at: datetime
    ends_at: datetime
    promo_price_cents: int
    invite_extra_discount_cents: int = 0
    stackable: bool = False
    new_user_only: bool = False
    countdown_enabled: bool = True
    status: str = "active"


class PaymentSetting(BaseModel):
    channel: PayChannel
    display_name: str
    qr_url: str
    enabled: bool = True
    updated_at: datetime


class AdminPaymentSettingRequest(BaseModel):
    display_name: str | None = None
    qr_url: str
    enabled: bool = True


class CreateOrderRequest(BaseModel):
    plan_id: str
    promotion_id: str | None = None
    pay_channel: PayChannel
    user_id: str | None = None
    invite_code: str | None = None


class Order(BaseModel):
    id: str
    order_no: str
    user_id: str
    user_email: str | None = None
    plan_id: str
    promotion_id: str | None
    invite_code: str | None = None
    original_amount_cents: int
    discount_amount_cents: int
    pay_amount_cents: int
    pay_channel: PayChannel
    status: OrderStatus
    payment_qr_url: str
    created_at: datetime
    paid_marked_at: datetime | None = None
    confirmed_at: datetime | None = None
    reviewed_by: str | None = None
    review_note: str | None = None


class User(BaseModel):
    id: str
    email: str
    phone: str = ""
    nickname: str
    invite_code: str
    vip_status: str = "inactive"
    vip_expired_at: datetime | None = None
    cash_balance_cents: int = 0
    free_traffic_quota_bytes: int = 0
    free_traffic_used_bytes: int = 0
    free_traffic_remaining_bytes: int = 0


class AdminOrderAction(BaseModel):
    reviewed_by: str = "admin"
    note: str | None = None


class DashboardSummary(BaseModel):
    total_users: int
    today_new_users: int
    online_users: int
    vip_users: int
    expiring_soon_users: int
    total_orders: int
    pending_confirm_orders: int
    completed_orders: int
    revenue_cents: int
    active_vip_users: int
    paid_invite_count: int
    total_cashback_cents: int
    pending_withdrawal_count: int
    pending_withdrawal_cents: int


class AppVersionResponse(BaseModel):
    version_code: int
    version_name: str
    min_supported_version_code: int
    download_url: str
    must_update: bool


class AuthRequest(BaseModel):
    email: str
    password: str
    invite_code: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User


class InvitationSummary(BaseModel):
    invite_code: str
    invited_count: int
    paid_invite_count: int
    total_reward_cents: int
    withdrawable_balance_cents: int


class InvitationRecord(BaseModel):
    id: str
    inviter_user_id: str
    invitee_user_id: str
    order_id: str | None
    reward_cents: int
    status: str
    risk_reason: str | None = None
    created_at: datetime


class CreateWithdrawalRequest(BaseModel):
    amount_cents: int
    account_type: str = "alipay"
    account_masked: str


class Entitlement(BaseModel):
    allowed: bool
    reason: str
    vip_status: str
    vip_expired_at: datetime | None = None
    free_traffic_quota_bytes: int
    free_traffic_used_bytes: int
    free_traffic_remaining_bytes: int


class VipStatusResponse(BaseModel):
    user_id: str
    email: str
    vip_status: str
    vip_expired_at: datetime | None = None
    free_traffic_quota_bytes: int
    free_traffic_used_bytes: int
    free_traffic_remaining_bytes: int
    entitlement: Entitlement


class VpnNodeConfig(BaseModel):
    id: str
    name: str
    region: str = "智能线路"
    tunnel_name: str = "xingsui"
    config_text: str
    entitlement: Entitlement


class VpnNodeSummary(BaseModel):
    id: str
    name: str
    region: str
    vip_only: bool
    status: str
    load_percent: int
    locked: bool


class NodeHeartbeatRequest(BaseModel):
    node_id: str
    peer_count: int = 0
    cpu_load: float = 0.0
    mem_used_percent: float = 0.0
    rx_bytes: int = 0
    tx_bytes: int = 0
    agent_version: str = ""


class AdminNodeRequest(BaseModel):
    id: str | None = None
    name: str
    region: str = "智能线路"
    endpoint: str
    agent_host: str
    agent_port: int = 51821
    server_public_key: str
    client_network: str = "10.66.66.0/24"
    dns: str = "1.1.1.1"
    allowed_ips: str = "0.0.0.0/0"
    persistent_keepalive: int = 25
    mtu: int = 1420
    params: dict[str, str] = {}
    weight: int = 100
    vip_only: bool = False
    max_clients: int = 0
    enabled: bool = True


class AdminNodeSummary(BaseModel):
    id: str
    name: str
    region: str
    endpoint: str
    agent_host: str
    agent_port: int
    server_public_key: str
    client_network: str
    dns: str
    allowed_ips: str
    persistent_keepalive: int
    mtu: int
    params: dict[str, str]
    params_fingerprint: str
    weight: int
    vip_only: bool
    max_clients: int
    enabled: bool
    status: str
    online: bool
    peer_count: int
    cpu_load: float
    mem_used_percent: float
    last_heartbeat_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UsageReportRequest(BaseModel):
    tunnel_name: str | None = None
    rx_bytes_delta: int = 0
    tx_bytes_delta: int = 0


class Withdrawal(BaseModel):
    id: str
    user_id: str
    user_email: str | None = None
    amount_cents: int
    account_type: str
    account_masked: str
    status: WithdrawalStatus
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class AdminUserSummary(BaseModel):
    id: str
    email: str
    created_at: datetime
    vip_status: str
    vip_expired_at: datetime | None = None
    last_login_at: datetime | None = None
    last_seen_at: datetime | None = None
    online: bool


class SystemHealthSummary(BaseModel):
    cpu_load_1m: float
    memory_used_percent: float
    network_rx_bytes: int
    network_tx_bytes: int
    active_vpn_devices: int
    wireguard_peers: int
    node_status: str


MONTHLY_PLAN_ID = "plan_month"
PROMOTION_ID = "promo_18_month"
INVITE_REWARD_CENTS = 1000
PAYMENT_QR = {
    PayChannel.wechat: "/pay/wechat.jpg",
    PayChannel.alipay: "/pay/alipay.jpg",
}
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PASSWORD_ITERATIONS = 120_000
FREE_TRAFFIC_QUOTA_BYTES = 30 * 1024 * 1024
ONLINE_WINDOW_SECONDS = 5 * 60
EXPIRING_SOON_DAYS = 7
SEEN_TOUCH_MIN_INTERVAL_SECONDS = 60


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise HTTPException(status_code=422, detail="Invalid email format")
    return normalized


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if len(password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters")
    salt = salt or secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()
    return salt, password_hash


def verify_password(user: UserRow, password: str) -> bool:
    if len(password) < 6:
        return False
    _, actual_hash = hash_password(password, user.password_salt)
    return hmac.compare_digest(actual_hash, user.password_hash)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSessionRow(token_hash=hash_token(token), user_id=user_id))
    db.commit()
    return token


def coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def is_online(last_seen_at: datetime | None, now: datetime | None = None) -> bool:
    seen_at = coerce_utc(last_seen_at)
    if seen_at is None:
        return False
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return seen_at >= now - timedelta(seconds=ONLINE_WINDOW_SECONDS)


def touch_user_seen(
    db: Session,
    user: UserRow,
    *,
    login: bool = False,
    force: bool = False,
) -> None:
    now = datetime.now(UTC)
    last_seen_at = coerce_utc(user.last_seen_at)
    should_touch = force or last_seen_at is None or (now - last_seen_at).total_seconds() >= SEEN_TOUCH_MIN_INTERVAL_SECONDS
    if not should_touch and not login:
        return
    user.last_seen_at = now
    if login:
        user.last_login_at = now
    db.commit()
    db.refresh(user)


def generate_invite_code(db: Session) -> str:
    for _ in range(16):
        code = f"XS{secrets.token_hex(3).upper()}"
        existing = db.scalar(select(UserRow).where(UserRow.invite_code == code))
        if existing is None:
            return code
    return f"XS{uuid4().hex[:8].upper()}"


def resolve_inviter(db: Session, invite_code: str | None) -> UserRow | None:
    code = invite_code.strip().upper() if invite_code else ""
    if not code:
        return None
    inviter = db.scalar(select(UserRow).where(UserRow.invite_code == code))
    if inviter is None:
        raise HTTPException(status_code=404, detail="Invite code not found")
    return inviter


def get_current_user(db: Session, authorization: str | None) -> UserRow:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    session = db.get(AuthSessionRow, hash_token(token))
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    user = db.get(UserRow, session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    touch_user_seen(db, user)
    return user


def to_user(row: UserRow) -> User:
    quota = int(row.free_traffic_quota_bytes or 0)
    used = int(row.free_traffic_used_bytes or 0)
    return User(
        id=row.id,
        email=row.email,
        phone=row.phone,
        nickname=row.nickname,
        invite_code=row.invite_code,
        vip_status=effective_vip_status(row.vip_status, row.vip_expired_at),
        vip_expired_at=row.vip_expired_at,
        cash_balance_cents=row.cash_balance_cents,
        free_traffic_quota_bytes=quota,
        free_traffic_used_bytes=used,
        free_traffic_remaining_bytes=free_traffic_remaining(row),
    )


def effective_vip_status(
    vip_status: str,
    vip_expired_at: datetime | None,
    now: datetime | None = None,
) -> str:
    if vip_status != "active" or vip_expired_at is None:
        return "inactive"
    now = now or datetime.now(UTC)
    expires_at = vip_expired_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return "active" if expires_at > now else "expired"


def ensure_free_traffic_quota(user: UserRow) -> bool:
    changed = False
    if user.free_traffic_quota_bytes is None or user.free_traffic_quota_bytes <= 0:
        user.free_traffic_quota_bytes = FREE_TRAFFIC_QUOTA_BYTES
        changed = True
    if user.free_traffic_used_bytes is None or user.free_traffic_used_bytes < 0:
        user.free_traffic_used_bytes = 0
        changed = True
    return changed


def free_traffic_remaining(user: UserRow) -> int:
    return max(0, int(user.free_traffic_quota_bytes or 0) - int(user.free_traffic_used_bytes or 0))


def build_entitlement(user: UserRow) -> Entitlement:
    ensure_free_traffic_quota(user)
    vip_status = effective_vip_status(user.vip_status, user.vip_expired_at)
    remaining = free_traffic_remaining(user)
    if vip_status == "active":
        allowed = True
        reason = "vip_active"
    elif remaining > 0:
        allowed = True
        reason = "free_trial"
    else:
        allowed = False
        reason = "vip_expired" if vip_status == "expired" else "free_traffic_exhausted"
    return Entitlement(
        allowed=allowed,
        reason=reason,
        vip_status=vip_status,
        vip_expired_at=user.vip_expired_at,
        free_traffic_quota_bytes=int(user.free_traffic_quota_bytes or 0),
        free_traffic_used_bytes=int(user.free_traffic_used_bytes or 0),
        free_traffic_remaining_bytes=remaining,
    )


def build_vpn_entitlement(user: UserRow) -> Entitlement:
    return build_entitlement(user)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def vpn_default_config_template() -> str | None:
    value = os.getenv("VPN_DEFAULT_CONFIG", "").strip()
    return value.replace("\\n", "\n") if value else None


def vpn_required_setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HTTPException(status_code=503, detail=f"{name} is not configured")
    return value


def run_vpn_command(command: list[str], input_text: str | None = None) -> str:
    try:
        result = subprocess.run(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"{command[0]} is not installed") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise HTTPException(status_code=503, detail=f"VPN node command failed: {message}") from exc
    return result.stdout.strip()


def vpn_control_tool() -> str:
    return "awg" if env_flag("AMNEZIAWG_SERVER_ENABLED", False) else "wg"


def vpn_quick_tool() -> str:
    return "awg-quick" if env_flag("AMNEZIAWG_SERVER_ENABLED", False) else "wg-quick"


def ensure_vpn_interface() -> None:
    """Ensure the WG interface is up and manageable with the selected tool.
    If 'wg show' fails (e.g. module/tool mismatch after prior awg use), clean and recreate.
    Safe for both 'wg' and 'awg' control tools. Called before peer ops.
    """
    interface = os.getenv("VPN_WG_INTERFACE", "wg0").strip()
    tool = vpn_control_tool()
    try:
        run_vpn_command([tool, "show", interface, "peers"])
        return
    except Exception:
        pass  # not manageable, clean and up
    # Clean
    try:
        run_vpn_command(["ip", "link", "del", "dev", interface])
    except Exception:
        pass
    try:
        run_vpn_command([vpn_quick_tool(), "down", interface])
    except Exception:
        pass
    # Bring up (will create with correct type for the tool)
    run_vpn_command([vpn_quick_tool(), "up", interface])


def generate_wireguard_keypair() -> tuple[str, str]:
    tool = vpn_control_tool()
    private_key = run_vpn_command([tool, "genkey"])
    public_key = run_vpn_command([tool, "pubkey"], input_text=f"{private_key}\n")
    return private_key, public_key


def allocate_client_address(db: Session) -> str:
    network = ipaddress.ip_network(os.getenv("VPN_CLIENT_NETWORK", "10.66.66.0/24"), strict=False)
    used = {
        ipaddress.ip_interface(row.client_address).ip
        for row in db.scalars(select(VpnDeviceRow)).all()
    }
    for address in network.hosts():
        if address == network.network_address + 1:
            continue
        if address not in used:
            prefix = 32 if network.version == 4 else 128
            return f"{address}/{prefix}"
    raise HTTPException(status_code=503, detail="VPN node address pool is full")


def vpn_endpoint_for_user(user_id: str | None = None) -> str:
    endpoints = [
        item.strip()
        for item in os.getenv("VPN_ENDPOINTS", os.getenv("VPN_ENDPOINT", "xingsuico.com:51820")).split(",")
        if item.strip()
    ]
    if not endpoints:
        raise HTTPException(status_code=503, detail="VPN_ENDPOINT is not configured")
    if user_id and len(endpoints) > 1:
        digest = hashlib.sha256(user_id.encode("utf-8")).digest()
        return endpoints[int.from_bytes(digest[:2], "big") % len(endpoints)]
    return endpoints[0]


def render_client_config(private_key: str, client_address: str, user_id: str | None = None) -> str:
    server_public_key = vpn_required_setting("VPN_SERVER_PUBLIC_KEY")
    endpoint = vpn_endpoint_for_user(user_id)
    dns = os.getenv("VPN_DNS", "1.1.1.1").strip()
    allowed_ips = os.getenv("VPN_ALLOWED_IPS", "0.0.0.0/0").strip()
    persistent_keepalive = os.getenv("VPN_PERSISTENT_KEEPALIVE", "25").strip()
    mtu = os.getenv("VPN_MTU", "1420").strip()
    lines = [
        "[Interface]",
        f"PrivateKey = {private_key}",
        f"Address = {client_address}",
    ]
    if dns:
        lines.append(f"DNS = {dns}")
    if mtu:
        lines.append(f"MTU = {mtu}")
    # Always emit AmneziaWG obfuscation fields (Jc/Jmin/...). The Amnezia client
    # (this app) will use them for DPI resistance on censored networks (China etc.).
    # Server (plain wg or AWG) will see the packets; for full bidirectional, set
    # AMNEZIAWG_SERVER_ENABLED and provide awg/awg-quick tools + matching module.
    amnezia_params = [
        ("Jc", os.getenv("AMNEZIA_JC", "4").strip()),
        ("Jmin", os.getenv("AMNEZIA_JMIN", "40").strip()),
        ("Jmax", os.getenv("AMNEZIA_JMAX", "70").strip()),
        ("S1", os.getenv("AMNEZIA_S1", "0").strip()),
        ("S2", os.getenv("AMNEZIA_S2", "0").strip()),
        ("H1", os.getenv("AMNEZIA_H1", "1").strip()),
        ("H2", os.getenv("AMNEZIA_H2", "2").strip()),
        ("H3", os.getenv("AMNEZIA_H3", "3").strip()),
        ("H4", os.getenv("AMNEZIA_H4", "4").strip()),
    ]
    for key, val in amnezia_params:
        if val:
            lines.append(f"{key} = {val}")
    lines.extend(
        [
            "",
            "[Peer]",
            f"PublicKey = {server_public_key}",
            f"AllowedIPs = {allowed_ips}",
            f"Endpoint = {endpoint}",
        ]
    )
    if persistent_keepalive:
        lines.append(f"PersistentKeepalive = {persistent_keepalive}")
    return "\n".join(lines) + "\n"


def add_wireguard_peer(public_key: str, client_address: str) -> None:
    ensure_vpn_interface()
    interface_name = os.getenv("VPN_WG_INTERFACE", "wg0").strip()
    client_ip = str(ipaddress.ip_interface(client_address).ip)
    run_vpn_command([vpn_control_tool(), "set", interface_name, "peer", public_key, "allowed-ips", f"{client_ip}/32"])
    if env_flag("VPN_SAVE_PEERS", False):
        run_vpn_command([vpn_quick_tool(), "save", interface_name])


def remove_wireguard_peer(public_key: str) -> None:
    ensure_vpn_interface()
    interface_name = os.getenv("VPN_WG_INTERFACE", "wg0").strip()
    run_vpn_command([vpn_control_tool(), "set", interface_name, "peer", public_key, "remove"])


def revoke_vpn_devices(db: Session, user: UserRow) -> None:
    if not env_flag("VPN_AUTO_PROVISION", False):
        return
    rows = db.scalars(
        select(VpnDeviceRow)
        .where(VpnDeviceRow.user_id == user.id)
        .where(VpnDeviceRow.status == "active")
    ).all()
    changed = False
    for row in rows:
        try:
            remove_wireguard_peer(row.client_public_key)
        except HTTPException:
            pass
        row.status = "revoked"
        changed = True
    if changed:
        db.commit()


def get_or_create_vpn_device(db: Session, user: UserRow) -> VpnDeviceRow:
    def get_existing_active_device() -> VpnDeviceRow | None:
        return db.scalar(
            select(VpnDeviceRow)
            .where(VpnDeviceRow.user_id == user.id)
            .where(VpnDeviceRow.status == "active")
            .order_by(VpnDeviceRow.created_at.desc())
        )

    existing = get_existing_active_device()
    if existing is not None:
        add_wireguard_peer(existing.client_public_key, existing.client_address)
        latest_config = render_client_config(existing.client_private_key, existing.client_address, user.id)
        if existing.config_text != latest_config:
            existing.config_text = latest_config
            db.commit()
            db.refresh(existing)
        return existing

    for attempt in range(5):
        private_key, public_key = generate_wireguard_keypair()
        client_address = allocate_client_address(db)
        config_text = render_client_config(private_key, client_address, user.id)
        add_wireguard_peer(public_key, client_address)
        device = VpnDeviceRow(
            id=str(uuid4()),
            user_id=user.id,
            node_id=os.getenv("VPN_NODE_ID", "default"),
            tunnel_name="xingsui",
            client_private_key=private_key,
            client_public_key=public_key,
            client_address=client_address,
            config_text=config_text,
            status="active",
        )
        db.add(device)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            try:
                remove_wireguard_peer(public_key)
            except HTTPException:
                pass
            existing = get_existing_active_device()
            if existing is not None:
                add_wireguard_peer(existing.client_public_key, existing.client_address)
                return existing
            if attempt == 4:
                raise HTTPException(status_code=503, detail="VPN address allocation conflict, please retry")
            continue
        db.refresh(device)
        return device

    raise HTTPException(status_code=503, detail="VPN address allocation failed")


def restore_active_vpn_peers() -> None:
    if not env_flag("VPN_AUTO_PROVISION", False):
        return
    with SessionLocal() as db:
        rows = db.scalars(select(VpnDeviceRow).where(VpnDeviceRow.status == "active")).all()
        for row in rows:
            try:
                add_wireguard_peer(row.client_public_key, row.client_address)
            except HTTPException:
                continue


def user_is_vip(user: UserRow) -> bool:
    return effective_vip_status(user.vip_status, user.vip_expired_at) == "active"


def require_node(db: Session, node_id: str) -> VpnNodeRow:
    node = db.get(VpnNodeRow, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


def select_pool_node(db: Session, vip: bool) -> VpnNodeRow | None:
    """从节点池中选出当前最优的在线节点；池为空或全部离线时返回 None。"""
    nodes = db.scalars(select(VpnNodeRow).where(VpnNodeRow.enabled.is_(True))).all()
    if not nodes:
        return None
    health = node_health_map(db)
    candidates = [(node, health.get(node.id)) for node in nodes]
    ranked = node_service.select_best_nodes(candidates, vip=vip, now=datetime.now(UTC))
    return ranked[0] if ranked else None


def allocate_node_client_address(db: Session, node: VpnNodeRow) -> str:
    network = ipaddress.ip_network(node.client_network or "10.66.66.0/24", strict=False)
    used = {
        ipaddress.ip_interface(row.client_address).ip
        for row in db.scalars(select(VpnDeviceRow).where(VpnDeviceRow.node_id == node.id)).all()
    }
    for address in network.hosts():
        if address == network.network_address + 1:
            continue
        if address not in used:
            prefix = 32 if network.version == 4 else 128
            return f"{address}/{prefix}"
    raise HTTPException(status_code=503, detail="Node address pool is full")


def provision_node_device(db: Session, user: UserRow, node: VpnNodeRow) -> VpnDeviceRow:
    """在指定边缘节点上为用户签发设备：本地生成密钥、分配地址，
    通过 Agent 在该节点添加 peer，并渲染基于节点参数的客户端配置。"""
    existing = db.scalar(
        select(VpnDeviceRow)
        .where(VpnDeviceRow.user_id == user.id)
        .where(VpnDeviceRow.node_id == node.id)
        .where(VpnDeviceRow.status == "active")
        .order_by(VpnDeviceRow.created_at.desc())
    )
    if existing is not None:
        client_ip = str(ipaddress.ip_interface(existing.client_address).ip)
        agent_add_node_peer(node, existing.client_public_key, client_ip)
        latest = node_service.render_node_client_config(node, existing.client_private_key, existing.client_address)
        if existing.config_text != latest:
            existing.config_text = latest
            db.commit()
            db.refresh(existing)
        return existing

    for attempt in range(5):
        private_key, public_key = generate_wireguard_keypair()
        client_address = allocate_node_client_address(db, node)
        config_text = node_service.render_node_client_config(node, private_key, client_address)
        client_ip = str(ipaddress.ip_interface(client_address).ip)
        agent_add_node_peer(node, public_key, client_ip)
        device = VpnDeviceRow(
            id=str(uuid4()),
            user_id=user.id,
            node_id=node.id,
            tunnel_name="xingsui",
            client_private_key=private_key,
            client_public_key=public_key,
            client_address=client_address,
            config_text=config_text,
            status="active",
        )
        db.add(device)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            try:
                node_service.agent_remove_peer(node, public_key)
            except Exception:
                pass
            if attempt == 4:
                raise HTTPException(status_code=503, detail="Node address allocation conflict, please retry")
            continue
        db.refresh(device)
        return device

    raise HTTPException(status_code=503, detail="Node address allocation failed")


def agent_add_node_peer(node: VpnNodeRow, public_key: str, client_ip: str) -> None:
    try:
        node_service.agent_add_peer(node, public_key, client_ip)
    except Exception as exc:  # 网络/Agent 错误统一转 503
        raise HTTPException(status_code=503, detail=f"Node agent unreachable: {exc}") from exc


def to_vpn_node_summary(node: VpnNodeRow, health: VpnNodeHealthRow | None, vip: bool, now: datetime) -> VpnNodeSummary:
    peer_count = int(getattr(health, "peer_count", 0) or 0) if health is not None else 0
    load_percent = int(round(node_service.node_load_ratio(peer_count, node.max_clients) * 100))
    return VpnNodeSummary(
        id=node.id,
        name=node.name,
        region=node.region,
        vip_only=node.vip_only,
        status=node_service.node_status_label(health, now),
        load_percent=load_percent,
        locked=node.vip_only and not vip,
    )


def to_admin_node(node: VpnNodeRow, health: VpnNodeHealthRow | None, now: datetime) -> AdminNodeSummary:
    params = node_service.parse_node_params(node.params_json)
    return AdminNodeSummary(
        id=node.id,
        name=node.name,
        region=node.region,
        endpoint=node.endpoint,
        agent_host=node.agent_host,
        agent_port=node.agent_port,
        server_public_key=node.server_public_key,
        client_network=node.client_network,
        dns=node.dns,
        allowed_ips=node.allowed_ips,
        persistent_keepalive=node.persistent_keepalive,
        mtu=node.mtu,
        params=params,
        params_fingerprint=node_service.params_fingerprint(params),
        weight=node.weight,
        vip_only=node.vip_only,
        max_clients=node.max_clients,
        enabled=node.enabled,
        status=node.status,
        online=node_service.node_status_label(health, now) == "online",
        peer_count=int(getattr(health, "peer_count", 0) or 0) if health is not None else 0,
        cpu_load=float(getattr(health, "cpu_load", 0.0) or 0.0) if health is not None else 0.0,
        mem_used_percent=float(getattr(health, "mem_used_percent", 0.0) or 0.0) if health is not None else 0.0,
        last_heartbeat_at=getattr(health, "last_heartbeat_at", None) if health is not None else None,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


def to_plan(row: VipPlanRow) -> VipPlan:
    return VipPlan(
        id=row.id,
        name=row.name,
        duration_days=row.duration_days,
        original_price_cents=row.original_price_cents,
        sale_price_cents=row.sale_price_cents,
    )


def to_promotion(row: PromotionActivityRow) -> PromotionActivity:
    return PromotionActivity(
        id=row.id,
        name=row.name,
        tag=row.tag,
        plan_id=row.plan_id,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        promo_price_cents=row.promo_price_cents,
        invite_extra_discount_cents=row.invite_extra_discount_cents,
        stackable=row.stackable,
        new_user_only=row.new_user_only,
        countdown_enabled=row.countdown_enabled,
        status=row.status,
    )


def to_payment_setting(row: PaymentSettingRow) -> PaymentSetting:
    return PaymentSetting(
        channel=PayChannel(row.channel),
        display_name=row.display_name,
        qr_url=row.qr_url,
        enabled=row.enabled,
        updated_at=row.updated_at,
    )


def to_order(row: OrderRow, user_email: str | None = None) -> Order:
    return Order(
        id=row.id,
        order_no=row.order_no,
        user_id=row.user_id,
        user_email=user_email,
        plan_id=row.plan_id,
        promotion_id=row.promotion_id,
        invite_code=row.invite_code,
        original_amount_cents=row.original_amount_cents,
        discount_amount_cents=row.discount_amount_cents,
        pay_amount_cents=row.pay_amount_cents,
        pay_channel=PayChannel(row.pay_channel),
        status=OrderStatus(row.status),
        payment_qr_url=row.payment_qr_url,
        created_at=row.created_at,
        paid_marked_at=row.paid_marked_at,
        confirmed_at=row.confirmed_at,
        reviewed_by=row.reviewed_by,
        review_note=row.review_note,
    )


def to_withdrawal(row: WithdrawalRow, user_email: str | None = None) -> Withdrawal:
    return Withdrawal(
        id=row.id,
        user_id=row.user_id,
        user_email=user_email,
        amount_cents=row.amount_cents,
        account_type=row.account_type,
        account_masked=row.account_masked,
        status=WithdrawalStatus(row.status),
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
    )


def to_admin_user(row: UserRow, now: datetime | None = None) -> AdminUserSummary:
    return AdminUserSummary(
        id=row.id,
        email=row.email,
        created_at=row.created_at,
        vip_status=effective_vip_status(row.vip_status, row.vip_expired_at, now),
        vip_expired_at=row.vip_expired_at,
        last_login_at=row.last_login_at,
        last_seen_at=row.last_seen_at,
        online=is_online(row.last_seen_at, now),
    )


def user_email_map(db: Session, user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    rows = db.scalars(select(UserRow).where(UserRow.id.in_(user_ids))).all()
    return {row.id: row.email for row in rows}


def read_memory_used_percent() -> float:
    values: dict[str, int] = {}
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return 0.0
    for line in meminfo.read_text().splitlines():
        parts = line.split()
        if len(parts) >= 2:
            values[parts[0].rstrip(":")] = int(parts[1])
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    if total <= 0:
        return 0.0
    return round((total - available) * 100 / total, 2)


def read_network_total_bytes(kind: str) -> int:
    root = Path("/sys/class/net")
    total = 0
    if not root.is_dir():
        return total
    for interface in root.iterdir():
        if interface.name == "lo":
            continue
        stat = interface / "statistics" / kind
        if stat.is_file():
            total += int(stat.read_text().strip() or "0")
    return total


def wireguard_peer_count() -> int:
    interface_name = os.getenv("VPN_WG_INTERFACE", "wg0").strip()
    ensure_vpn_interface()
    try:
        output = run_vpn_command([vpn_control_tool(), "show", interface_name, "peers"])
    except HTTPException:
        return 0
    return len([line for line in output.splitlines() if line.strip()])


def to_invitation_record(row: InvitationRow) -> InvitationRecord:
    return InvitationRecord(
        id=row.id,
        inviter_user_id=row.inviter_user_id,
        invitee_user_id=row.invitee_user_id,
        order_id=row.order_id,
        reward_cents=row.reward_cents,
        status=row.status,
        risk_reason=row.risk_reason,
        created_at=row.created_at,
    )


def get_invitation_summary(db: Session, user: UserRow) -> InvitationSummary:
    invited_count = db.scalar(
        select(func.count()).select_from(UserRow).where(UserRow.invited_by_user_id == user.id)
    ) or 0
    paid_invite_count = db.scalar(
        select(func.count()).select_from(InvitationRow)
        .where(InvitationRow.inviter_user_id == user.id)
        .where(InvitationRow.status == "rewarded")
    ) or 0
    total_reward_cents = db.scalar(
        select(func.coalesce(func.sum(InvitationRow.reward_cents), 0))
        .where(InvitationRow.inviter_user_id == user.id)
        .where(InvitationRow.status == "rewarded")
    ) or 0
    return InvitationSummary(
        invite_code=user.invite_code,
        invited_count=invited_count,
        paid_invite_count=paid_invite_count,
        total_reward_cents=total_reward_cents,
        withdrawable_balance_cents=user.cash_balance_cents,
    )


def require_payment_setting(db: Session, channel: PayChannel) -> PaymentSettingRow:
    setting = db.get(PaymentSettingRow, channel.value)
    if setting is None or not setting.enabled or not setting.qr_url.strip():
        raise HTTPException(status_code=409, detail=f"{channel.value} payment channel is unavailable")
    return setting


def require_valid_promotion(
    db: Session,
    promotion_id: str | None,
    plan: VipPlanRow,
    user: UserRow,
) -> PromotionActivityRow | None:
    if promotion_id is None:
        return None
    promotion = db.get(PromotionActivityRow, promotion_id)
    now = datetime.now(UTC)
    if promotion is None:
        raise HTTPException(status_code=404, detail="Promotion not found")
    if promotion.plan_id != plan.id:
        raise HTTPException(status_code=409, detail="Promotion does not apply to this plan")
    if promotion.status != "active" or promotion.starts_at > now or promotion.ends_at < now:
        raise HTTPException(status_code=409, detail="Promotion is not active")
    if promotion.new_user_only:
        completed_orders = db.scalar(
            select(func.count()).select_from(OrderRow)
            .where(OrderRow.user_id == user.id)
            .where(OrderRow.status == OrderStatus.completed.value)
        ) or 0
        if completed_orders > 0:
            raise HTTPException(status_code=409, detail="Promotion is only for new users")
    return promotion


def apply_invitation_reward(db: Session, invitee: UserRow, order: OrderRow) -> None:
    if not invitee.invited_by_user_id or invitee.invited_by_user_id == invitee.id:
        return

    previous_completed_orders = db.scalar(
        select(func.count()).select_from(OrderRow)
        .where(OrderRow.user_id == invitee.id)
        .where(OrderRow.status == OrderStatus.completed.value)
        .where(OrderRow.id != order.id)
    ) or 0
    if previous_completed_orders > 0:
        return

    inviter = db.get(UserRow, invitee.invited_by_user_id)
    if inviter is None or inviter.id == invitee.id:
        return

    invitation = db.scalar(
        select(InvitationRow)
        .where(InvitationRow.inviter_user_id == inviter.id)
        .where(InvitationRow.invitee_user_id == invitee.id)
    )
    if invitation is not None and invitation.status == "rewarded":
        return

    if invitation is None:
        invitation = InvitationRow(
            id=str(uuid4()),
            inviter_user_id=inviter.id,
            invitee_user_id=invitee.id,
            reward_cents=INVITE_REWARD_CENTS,
        )
        db.add(invitation)
    invitation.order_id = order.id
    invitation.reward_cents = INVITE_REWARD_CENTS
    invitation.status = "rewarded"
    invitation.risk_reason = None
    inviter.cash_balance_cents += INVITE_REWARD_CENTS


def seed_database() -> None:
    with SessionLocal() as db:
        if db.get(VipPlanRow, MONTHLY_PLAN_ID) is None:
            db.add_all(
                [
                    VipPlanRow(
                        id=MONTHLY_PLAN_ID,
                        name="月度会员",
                        duration_days=30,
                        original_price_cents=2880,
                        sale_price_cents=1800,
                    ),
                    VipPlanRow(
                        id="plan_quarter",
                        name="季度会员",
                        duration_days=90,
                        original_price_cents=8640,
                        sale_price_cents=5800,
                    ),
                    VipPlanRow(
                        id="plan_year",
                        name="年度会员",
                        duration_days=365,
                        original_price_cents=34560,
                        sale_price_cents=19800,
                    ),
                ]
            )
            db.commit()
        if db.get(PromotionActivityRow, PROMOTION_ID) is None:
            db.add(
                PromotionActivityRow(
                    id=PROMOTION_ID,
                    name="星隧首月限时特惠",
                    tag="限时特惠",
                    plan_id=MONTHLY_PLAN_ID,
                    starts_at=datetime.now(UTC) - timedelta(days=1),
                    ends_at=datetime.now(UTC) + timedelta(days=3, hours=8),
                    promo_price_cents=1800,
                    invite_extra_discount_cents=500,
                    stackable=False,
                    new_user_only=True,
                )
            )
            db.commit()
        for channel, display_name in ((PayChannel.wechat, "微信收款码"), (PayChannel.alipay, "支付宝收款码")):
            if db.get(PaymentSettingRow, channel.value) is None:
                db.add(
                    PaymentSettingRow(
                        channel=channel.value,
                        display_name=display_name,
                        qr_url=PAYMENT_QR[channel],
                        enabled=True,
                    )
                )
        db.commit()
        if db.get(UserRow, "demo_user") is None:
            salt, password_hash = hash_password("xingsui123")
            db.add(
                UserRow(
                    id="demo_user",
                    email="demo@xingsui.local",
                    password_salt=salt,
                    password_hash=password_hash,
                    phone="13800000000",
                    nickname="星隧体验用户",
                    invite_code="XS2026",
                )
            )
        db.commit()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/health", include_in_schema=False)
def api_health() -> dict[str, str]:
    return health()


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def landing_page() -> str:
    return SITE_HTML


def app_version_payload(version_code: int | None = None) -> AppVersionResponse:
    return AppVersionResponse(
        version_code=APP_VERSION_CODE,
        version_name=APP_VERSION_NAME,
        min_supported_version_code=MIN_SUPPORTED_APP_VERSION_CODE,
        download_url=f"/download/android?v={APP_VERSION_NAME}-{APP_VERSION_CODE}",
        must_update=version_code is None or version_code < MIN_SUPPORTED_APP_VERSION_CODE,
    )


@app.get("/app/version", response_model=AppVersionResponse, include_in_schema=False)
def public_app_version(version_code: int | None = Query(default=None)) -> AppVersionResponse:
    return app_version_payload(version_code)


@app.get("/api/app/version", response_model=AppVersionResponse, include_in_schema=False)
def api_app_version(version_code: int | None = Query(default=None)) -> AppVersionResponse:
    return app_version_payload(version_code)


def build_android_apk_response() -> FileResponse:
    apk_path = Path(
        os.getenv(
            "APK_PATH",
            str(Path(__file__).resolve().parents[2] / "ui" / "build" / "outputs" / "apk" / "debug" / "ui-debug.apk"),
        )
    )
    if not apk_path.is_file():
        raise HTTPException(status_code=404, detail="APK is not available yet")
    return FileResponse(
        apk_path,
        media_type="application/vnd.android.package-archive",
        filename="xingsui-android.apk",
        headers={
            "Cache-Control": "no-store, max-age=0",
            "X-Xingsui-Version-Code": str(APP_VERSION_CODE),
            "X-Xingsui-Version-Name": APP_VERSION_NAME,
        },
    )


def build_windows_installer_response() -> FileResponse:
    installer_path = Path(
        os.getenv(
            "WINDOWS_INSTALLER_PATH",
            "/opt/xingsui/download/xingsui-windows-setup.exe",
        )
    )
    if not installer_path.is_file():
        raise HTTPException(status_code=404, detail="Windows installer is not available yet")
    return FileResponse(
        installer_path,
        media_type="application/vnd.microsoft.portable-executable",
        filename=installer_path.name,
        headers={
            "Cache-Control": "no-store, max-age=0",
            "X-Xingsui-Platform": "windows",
        },
    )


def payment_asset_dir() -> Path:
    default_dir = Path(os.getenv("APK_PATH", "/opt/xingsui/download/xingsui.apk")).resolve().parent
    return Path(os.getenv("PAYMENT_ASSET_DIR", str(default_dir))).resolve()


def build_payment_image_response(filename: str) -> FileResponse:
    image_path = payment_asset_dir() / filename
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Payment image is not available")
    return FileResponse(
        image_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/download/android", include_in_schema=False)
def download_android_apk() -> FileResponse:
    return build_android_apk_response()


@app.head("/download/android", include_in_schema=False)
def head_android_apk() -> FileResponse:
    return build_android_apk_response()


@app.get("/download/windows", include_in_schema=False)
def download_windows_installer() -> FileResponse:
    return build_windows_installer_response()


@app.head("/download/windows", include_in_schema=False)
def head_windows_installer() -> FileResponse:
    return build_windows_installer_response()


@app.get("/pay/wechat.jpg", include_in_schema=False)
def payment_wechat_qr() -> FileResponse:
    return build_payment_image_response("wechat.jpg")


@app.head("/pay/wechat.jpg", include_in_schema=False)
def head_payment_wechat_qr() -> FileResponse:
    return build_payment_image_response("wechat.jpg")


@app.get("/pay/alipay.jpg", include_in_schema=False)
def payment_alipay_qr() -> FileResponse:
    return build_payment_image_response("alipay.jpg")


@app.head("/pay/alipay.jpg", include_in_schema=False)
def head_payment_alipay_qr() -> FileResponse:
    return build_payment_image_response("alipay.jpg")


@app.get("/admin/login", response_class=HTMLResponse, include_in_schema=False)
def admin_login_page() -> str:
    return render_admin_login()


@app.post("/admin/login", response_model=None, include_in_schema=False)
async def admin_login(request: Request) -> Response:
    body = (await request.body()).decode("utf-8")
    password = parse_qs(body).get("password", [""])[0]
    if not admin_password_valid(password):
        return HTMLResponse(render_admin_login(error=True), status_code=401)
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        admin_session_token(),
        max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/admin/logout", include_in_schema=False)
def admin_logout() -> RedirectResponse:
    response = RedirectResponse("/admin/login", status_code=303)
    response.delete_cookie(ADMIN_SESSION_COOKIE)
    return response


@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page() -> str:
    return ADMIN_HTML


@app.post("/auth/email/register", response_model=AuthResponse, status_code=201)
def register_by_email(payload: AuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = normalize_email(payload.email)
    existing = db.scalar(select(UserRow).where(UserRow.email == email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    inviter = resolve_inviter(db, payload.invite_code)
    salt, password_hash = hash_password(payload.password)
    now = datetime.now(UTC)
    user = UserRow(
        id=str(uuid4()),
        email=email,
        password_salt=salt,
        password_hash=password_hash,
        nickname=email.split("@", 1)[0],
        invite_code=generate_invite_code(db),
        invited_by_user_id=inviter.id if inviter else None,
        free_traffic_quota_bytes=FREE_TRAFFIC_QUOTA_BYTES,
        free_traffic_used_bytes=0,
        last_login_at=now,
        last_seen_at=now,
    )
    db.add(user)
    db.flush()
    if inviter is not None:
        db.add(
            InvitationRow(
                id=str(uuid4()),
                inviter_user_id=inviter.id,
                invitee_user_id=user.id,
                status="pending",
            )
        )
    db.commit()
    db.refresh(user)
    return AuthResponse(access_token=create_session(db, user.id), user=to_user(user))


@app.post("/auth/email/login", response_model=AuthResponse)
def login_by_email(payload: AuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = normalize_email(payload.email)
    user = db.scalar(select(UserRow).where(UserRow.email == email))
    if user is None or not verify_password(user, payload.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if ensure_free_traffic_quota(user):
        db.commit()
        db.refresh(user)
    touch_user_seen(db, user, login=True, force=True)
    return AuthResponse(access_token=create_session(db, user.id), user=to_user(user))


@app.get("/me", response_model=User)
def get_me(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    user = get_current_user(db, authorization)
    if ensure_free_traffic_quota(user):
        db.commit()
        db.refresh(user)
    return to_user(user)


@app.get("/usage/authorize", response_model=Entitlement)
def authorize_usage(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Entitlement:
    user = get_current_user(db, authorization)
    if ensure_free_traffic_quota(user):
        db.commit()
        db.refresh(user)
    return build_entitlement(user)


@app.get("/vpn/authorize", response_model=Entitlement)
def authorize_vpn(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Entitlement:
    user = get_current_user(db, authorization)
    if ensure_free_traffic_quota(user):
        db.commit()
        db.refresh(user)
    entitlement = build_vpn_entitlement(user)
    if not entitlement.allowed:
        revoke_vpn_devices(db, user)
    return entitlement


@app.get("/user/vip/status", response_model=VipStatusResponse)
def get_user_vip_status(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> VipStatusResponse:
    user = get_current_user(db, authorization)
    if ensure_free_traffic_quota(user):
        db.commit()
        db.refresh(user)
    entitlement = build_vpn_entitlement(user)
    return VipStatusResponse(
        user_id=user.id,
        email=user.email,
        vip_status=entitlement.vip_status,
        vip_expired_at=entitlement.vip_expired_at,
        free_traffic_quota_bytes=entitlement.free_traffic_quota_bytes,
        free_traffic_used_bytes=entitlement.free_traffic_used_bytes,
        free_traffic_remaining_bytes=entitlement.free_traffic_remaining_bytes,
        entitlement=entitlement,
    )


@app.get("/api/user/vip/status", response_model=VipStatusResponse, include_in_schema=False)
def api_get_user_vip_status(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> VipStatusResponse:
    return get_user_vip_status(authorization=authorization, db=db)


@app.get("/vpn/config", response_model=VpnNodeConfig)
def get_vpn_config(
    rotate: bool = Query(default=False),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> VpnNodeConfig:
    user = get_current_user(db, authorization)
    if ensure_free_traffic_quota(user):
        db.commit()
        db.refresh(user)
    entitlement = build_vpn_entitlement(user)
    if not entitlement.allowed:
        raise HTTPException(status_code=403, detail=entitlement.reason)

    # 优先走节点池智能调度：选出最优在线节点并经 Agent 远程签发。
    # 节点池为空 / 全部离线 / Agent 不可达时安全回退到下方静态/自动签发逻辑。
    pool_node = select_pool_node(db, user_is_vip(user))
    if pool_node is not None:
        if rotate:
            revoke_vpn_devices(db, user)
        try:
            device = provision_node_device(db, user, pool_node)
        except Exception:
            device = None
        if device is not None:
            return VpnNodeConfig(
                id=pool_node.id,
                name=pool_node.name,
                region=pool_node.region,
                tunnel_name=device.tunnel_name,
                config_text=device.config_text,
                entitlement=entitlement,
            )

    static_config = vpn_default_config_template()
    if static_config and not env_flag("VPN_AUTO_PROVISION", False):
        return VpnNodeConfig(
            id=os.getenv("VPN_NODE_ID", "default"),
            name=os.getenv("VPN_NODE_NAME", "星隧智能节点"),
            region=os.getenv("VPN_NODE_REGION", "智能线路"),
            tunnel_name="xingsui",
            config_text=static_config,
            entitlement=entitlement,
        )

    if not env_flag("VPN_AUTO_PROVISION", False):
        raise HTTPException(status_code=503, detail="VPN node is not configured")

    if rotate:
        revoke_vpn_devices(db, user)

    device = get_or_create_vpn_device(db, user)
    return VpnNodeConfig(
        id=device.node_id,
        name=os.getenv("VPN_NODE_NAME", "星隧智能节点"),
        region=os.getenv("VPN_NODE_REGION", "智能线路"),
        tunnel_name=device.tunnel_name,
        config_text=device.config_text,
        entitlement=entitlement,
    )


@app.post("/usage/report", response_model=Entitlement)
def report_usage(
    payload: UsageReportRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Entitlement:
    user = get_current_user(db, authorization)
    ensure_free_traffic_quota(user)
    if effective_vip_status(user.vip_status, user.vip_expired_at) == "active":
        db.commit()
        db.refresh(user)
        return build_entitlement(user)

    rx_delta = max(0, int(payload.rx_bytes_delta))
    tx_delta = max(0, int(payload.tx_bytes_delta))
    user.free_traffic_used_bytes = int(user.free_traffic_used_bytes or 0) + rx_delta + tx_delta
    db.commit()
    db.refresh(user)
    entitlement = build_entitlement(user)
    if not entitlement.allowed:
        revoke_vpn_devices(db, user)
    return entitlement


@app.get("/invitations/me", response_model=InvitationSummary)
def get_my_invitation(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> InvitationSummary:
    return get_invitation_summary(db, get_current_user(db, authorization))


@app.get("/plans", response_model=list[VipPlan])
def list_plans(db: Session = Depends(get_db)) -> list[VipPlan]:
    rows = db.scalars(select(VipPlanRow).where(VipPlanRow.status == "active")).all()
    return [to_plan(row) for row in rows]


@app.get("/promotions/active", response_model=PromotionActivity)
def get_active_promotion(db: Session = Depends(get_db)) -> PromotionActivity:
    now = datetime.now(UTC)
    promotion = db.scalar(
        select(PromotionActivityRow)
        .where(PromotionActivityRow.status == "active")
        .where(PromotionActivityRow.starts_at <= now)
        .where(PromotionActivityRow.ends_at >= now)
        .order_by(PromotionActivityRow.ends_at.asc())
    )
    if promotion is None:
        raise HTTPException(status_code=404, detail="No active promotion")
    return to_promotion(promotion)


@app.get("/payment-settings", response_model=list[PaymentSetting])
def list_enabled_payment_settings(db: Session = Depends(get_db)) -> list[PaymentSetting]:
    rows = db.scalars(
        select(PaymentSettingRow)
        .where(PaymentSettingRow.enabled.is_(True))
        .order_by(PaymentSettingRow.channel.asc())
    ).all()
    return [to_payment_setting(row) for row in rows]


@app.post("/orders", response_model=Order, status_code=201)
def create_order(
    payload: CreateOrderRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Order:
    plan = db.get(VipPlanRow, payload.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    user = get_current_user(db, authorization)

    promotion = require_valid_promotion(db, payload.promotion_id, plan, user)
    payment_setting = require_payment_setting(db, payload.pay_channel)
    original_amount = plan.original_price_cents
    pay_amount = promotion.promo_price_cents if promotion and promotion.plan_id == plan.id else plan.sale_price_cents

    order = OrderRow(
        id=str(uuid4()),
        order_no=f"{datetime.now(UTC).strftime('XS%Y%m%d%H%M%S')}{uuid4().hex[:6].upper()}",
        user_id=user.id,
        plan_id=plan.id,
        promotion_id=promotion.id if promotion else None,
        invite_code=payload.invite_code,
        original_amount_cents=original_amount,
        discount_amount_cents=original_amount - pay_amount,
        pay_amount_cents=pay_amount,
        pay_channel=payload.pay_channel.value,
        status=OrderStatus.pending_payment.value,
        payment_qr_url=payment_setting.qr_url,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return to_order(order, user.email)


@app.post("/withdrawals", response_model=Withdrawal, status_code=201)
def create_withdrawal(
    payload: CreateWithdrawalRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Withdrawal:
    user = get_current_user(db, authorization)
    account_masked = payload.account_masked.strip()
    account_type = payload.account_type.strip().lower() or "alipay"
    if payload.amount_cents < INVITE_REWARD_CENTS:
        raise HTTPException(status_code=422, detail="Minimum withdrawal is 10 CNY")
    if len(account_masked) < 4:
        raise HTTPException(status_code=422, detail="Withdrawal account is required")
    if user.cash_balance_cents < payload.amount_cents:
        raise HTTPException(status_code=409, detail="Insufficient cashback balance")

    user.cash_balance_cents -= payload.amount_cents
    withdrawal = WithdrawalRow(
        id=str(uuid4()),
        user_id=user.id,
        amount_cents=payload.amount_cents,
        account_type=account_type,
        account_masked=account_masked[:80],
        status=WithdrawalStatus.pending.value,
    )
    db.add(withdrawal)
    db.commit()
    db.refresh(withdrawal)
    return to_withdrawal(withdrawal, user.email)


@app.get("/withdrawals/me", response_model=list[Withdrawal])
def list_my_withdrawals(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[Withdrawal]:
    user = get_current_user(db, authorization)
    rows = db.scalars(
        select(WithdrawalRow)
        .where(WithdrawalRow.user_id == user.id)
        .order_by(WithdrawalRow.created_at.desc())
    ).all()
    return [to_withdrawal(row, user.email) for row in rows]


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: str, db: Session = Depends(get_db)) -> Order:
    return to_order(require_order(db, order_id))


@app.post("/orders/{order_id}/paid", response_model=Order)
def mark_order_paid(order_id: str, db: Session = Depends(get_db)) -> Order:
    order = require_order(db, order_id)
    if order.status == OrderStatus.completed.value:
        return to_order(order)
    order.status = OrderStatus.pending_confirm.value
    order.paid_marked_at = datetime.now(UTC)
    db.commit()
    db.refresh(order)
    return to_order(order)


@app.get("/admin/dashboard", response_model=DashboardSummary)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardSummary:
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    online_since = now - timedelta(seconds=ONLINE_WINDOW_SECONDS)
    expiring_until = now + timedelta(days=EXPIRING_SOON_DAYS)
    total_users = db.scalar(select(func.count()).select_from(UserRow)) or 0
    today_new_users = db.scalar(
        select(func.count()).select_from(UserRow).where(UserRow.created_at >= today_start)
    ) or 0
    online_users = db.scalar(
        select(func.count()).select_from(UserRow).where(UserRow.last_seen_at >= online_since)
    ) or 0
    total_orders = db.scalar(select(func.count()).select_from(OrderRow)) or 0
    pending_confirm_orders = db.scalar(
        select(func.count()).select_from(OrderRow).where(OrderRow.status == OrderStatus.pending_confirm.value)
    ) or 0
    completed_orders = db.scalar(
        select(func.count()).select_from(OrderRow).where(OrderRow.status == OrderStatus.completed.value)
    ) or 0
    revenue_cents = db.scalar(
        select(func.coalesce(func.sum(OrderRow.pay_amount_cents), 0)).where(OrderRow.status == OrderStatus.completed.value)
    ) or 0
    active_vip_users = db.scalar(
        select(func.count())
        .select_from(UserRow)
        .where(UserRow.vip_status == "active")
        .where(UserRow.vip_expired_at > now)
    ) or 0
    expiring_soon_users = db.scalar(
        select(func.count())
        .select_from(UserRow)
        .where(UserRow.vip_status == "active")
        .where(UserRow.vip_expired_at > now)
        .where(UserRow.vip_expired_at <= expiring_until)
    ) or 0
    paid_invite_count = db.scalar(
        select(func.count()).select_from(InvitationRow).where(InvitationRow.status == "rewarded")
    ) or 0
    total_cashback_cents = db.scalar(
        select(func.coalesce(func.sum(InvitationRow.reward_cents), 0)).where(InvitationRow.status == "rewarded")
    ) or 0
    pending_withdrawal_count = db.scalar(
        select(func.count()).select_from(WithdrawalRow).where(WithdrawalRow.status == WithdrawalStatus.pending.value)
    ) or 0
    pending_withdrawal_cents = db.scalar(
        select(func.coalesce(func.sum(WithdrawalRow.amount_cents), 0))
        .where(WithdrawalRow.status == WithdrawalStatus.pending.value)
    ) or 0
    return DashboardSummary(
        total_users=total_users,
        today_new_users=today_new_users,
        online_users=online_users,
        vip_users=active_vip_users,
        expiring_soon_users=expiring_soon_users,
        total_orders=total_orders,
        pending_confirm_orders=pending_confirm_orders,
        completed_orders=completed_orders,
        revenue_cents=revenue_cents,
        active_vip_users=active_vip_users,
        paid_invite_count=paid_invite_count,
        total_cashback_cents=total_cashback_cents,
        pending_withdrawal_count=pending_withdrawal_count,
        pending_withdrawal_cents=pending_withdrawal_cents,
    )


@app.get("/admin/orders", response_model=list[Order])
def list_admin_orders(
    status: OrderStatus | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Order]:
    statement = select(OrderRow)
    if status is not None:
        statement = statement.where(OrderRow.status == status.value)
    rows = db.scalars(statement.order_by(OrderRow.created_at.desc())).all()
    emails = user_email_map(db, {row.user_id for row in rows})
    return [to_order(row, emails.get(row.user_id)) for row in rows]


@app.get("/admin/users", response_model=list[AdminUserSummary])
def list_admin_users(
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[AdminUserSummary]:
    statement = select(UserRow)
    if q:
        keyword = f"%{q.strip().lower()}%"
        statement = statement.where(func.lower(UserRow.email).like(keyword))
    rows = db.scalars(statement.order_by(UserRow.created_at.desc()).limit(500)).all()
    now = datetime.now(UTC)
    return [to_admin_user(row, now) for row in rows]


@app.get("/admin/system-health", response_model=SystemHealthSummary)
def get_system_health(db: Session = Depends(get_db)) -> SystemHealthSummary:
    active_vpn_devices = db.scalar(
        select(func.count()).select_from(VpnDeviceRow).where(VpnDeviceRow.status == "active")
    ) or 0
    peers = wireguard_peer_count()
    load_1m = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    node_status = "online" if peers >= 0 else "unknown"
    return SystemHealthSummary(
        cpu_load_1m=round(float(load_1m), 2),
        memory_used_percent=read_memory_used_percent(),
        network_rx_bytes=read_network_total_bytes("rx_bytes"),
        network_tx_bytes=read_network_total_bytes("tx_bytes"),
        active_vpn_devices=active_vpn_devices,
        wireguard_peers=peers,
        node_status=node_status,
    )


@app.get("/admin/payment-settings", response_model=list[PaymentSetting])
def list_admin_payment_settings(db: Session = Depends(get_db)) -> list[PaymentSetting]:
    rows = db.scalars(select(PaymentSettingRow).order_by(PaymentSettingRow.channel.asc())).all()
    return [to_payment_setting(row) for row in rows]


@app.put("/admin/payment-settings/{channel}", response_model=PaymentSetting)
def update_admin_payment_setting(
    channel: PayChannel,
    payload: AdminPaymentSettingRequest,
    db: Session = Depends(get_db),
) -> PaymentSetting:
    qr_url = payload.qr_url.strip()
    if not qr_url:
        raise HTTPException(status_code=422, detail="QR URL is required")
    setting = db.get(PaymentSettingRow, channel.value)
    if setting is None:
        setting = PaymentSettingRow(
            channel=channel.value,
            display_name=payload.display_name or ("微信收款码" if channel == PayChannel.wechat else "支付宝收款码"),
            qr_url=qr_url,
            enabled=payload.enabled,
        )
        db.add(setting)
    else:
        setting.display_name = payload.display_name or setting.display_name
        setting.qr_url = qr_url
        setting.enabled = payload.enabled
    db.commit()
    db.refresh(setting)
    return to_payment_setting(setting)


@app.get("/admin/promotions", response_model=list[PromotionActivity])
def list_admin_promotions(db: Session = Depends(get_db)) -> list[PromotionActivity]:
    rows = db.scalars(select(PromotionActivityRow).order_by(PromotionActivityRow.ends_at.desc())).all()
    return [to_promotion(row) for row in rows]


@app.post("/admin/promotions", response_model=PromotionActivity, status_code=201)
def create_admin_promotion(payload: AdminPromotionRequest, db: Session = Depends(get_db)) -> PromotionActivity:
    plan = db.get(VipPlanRow, payload.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="Promotion end must be after start")
    promotion_id = payload.id.strip() if payload.id else f"promo_{uuid4().hex[:10]}"
    if db.get(PromotionActivityRow, promotion_id) is not None:
        raise HTTPException(status_code=409, detail="Promotion already exists")
    row = PromotionActivityRow(
        id=promotion_id,
        name=payload.name.strip(),
        tag=payload.tag.strip() or "限时特惠",
        plan_id=payload.plan_id,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        promo_price_cents=payload.promo_price_cents,
        invite_extra_discount_cents=payload.invite_extra_discount_cents,
        stackable=payload.stackable,
        new_user_only=payload.new_user_only,
        countdown_enabled=payload.countdown_enabled,
        status=payload.status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return to_promotion(row)


@app.put("/admin/promotions/{promotion_id}", response_model=PromotionActivity)
def update_admin_promotion(
    promotion_id: str,
    payload: AdminPromotionRequest,
    db: Session = Depends(get_db),
) -> PromotionActivity:
    row = db.get(PromotionActivityRow, promotion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Promotion not found")
    if db.get(VipPlanRow, payload.plan_id) is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="Promotion end must be after start")
    row.name = payload.name.strip()
    row.tag = payload.tag.strip() or "限时特惠"
    row.plan_id = payload.plan_id
    row.starts_at = payload.starts_at
    row.ends_at = payload.ends_at
    row.promo_price_cents = payload.promo_price_cents
    row.invite_extra_discount_cents = payload.invite_extra_discount_cents
    row.stackable = payload.stackable
    row.new_user_only = payload.new_user_only
    row.countdown_enabled = payload.countdown_enabled
    row.status = payload.status
    db.commit()
    db.refresh(row)
    return to_promotion(row)


@app.get("/admin/withdrawals", response_model=list[Withdrawal])
def list_admin_withdrawals(
    status: WithdrawalStatus | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Withdrawal]:
    statement = select(WithdrawalRow)
    if status is not None:
        statement = statement.where(WithdrawalRow.status == status.value)
    rows = db.scalars(statement.order_by(WithdrawalRow.created_at.desc())).all()
    emails = user_email_map(db, {row.user_id for row in rows})
    return [to_withdrawal(row, emails.get(row.user_id)) for row in rows]


@app.post("/admin/withdrawals/{withdrawal_id}/approve", response_model=Withdrawal)
def approve_admin_withdrawal(
    withdrawal_id: str,
    payload: AdminOrderAction | None = None,
    db: Session = Depends(get_db),
) -> Withdrawal:
    row = db.get(WithdrawalRow, withdrawal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    if row.status != WithdrawalStatus.pending.value:
        raise HTTPException(status_code=409, detail=f"Withdrawal status is {row.status}")
    row.status = WithdrawalStatus.completed.value
    row.reviewed_by = payload.reviewed_by if payload else "admin"
    row.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    emails = user_email_map(db, {row.user_id})
    return to_withdrawal(row, emails.get(row.user_id))


@app.post("/admin/withdrawals/{withdrawal_id}/reject", response_model=Withdrawal)
def reject_admin_withdrawal(
    withdrawal_id: str,
    payload: AdminOrderAction | None = None,
    db: Session = Depends(get_db),
) -> Withdrawal:
    row = db.get(WithdrawalRow, withdrawal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    if row.status != WithdrawalStatus.pending.value:
        raise HTTPException(status_code=409, detail=f"Withdrawal status is {row.status}")
    user = db.get(UserRow, row.user_id)
    if user is not None:
        user.cash_balance_cents += row.amount_cents
    row.status = WithdrawalStatus.rejected.value
    row.reviewed_by = payload.reviewed_by if payload else "admin"
    row.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    emails = user_email_map(db, {row.user_id})
    return to_withdrawal(row, emails.get(row.user_id))


@app.get("/admin/invitations", response_model=list[InvitationRecord])
def list_admin_invitations(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[InvitationRecord]:
    statement = select(InvitationRow)
    if status:
        statement = statement.where(InvitationRow.status == status)
    rows = db.scalars(statement.order_by(InvitationRow.created_at.desc())).all()
    return [to_invitation_record(row) for row in rows]


@app.get("/admin/users/{user_id}", response_model=User)
def get_admin_user(user_id: str, db: Session = Depends(get_db)) -> User:
    user = db.get(UserRow, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return to_user(user)


class AdminGrantVipRequest(BaseModel):
    days: int = 30


@app.post("/admin/users/{user_id}/grant-vip", response_model=AdminUserSummary)
def admin_grant_vip(
    user_id: str,
    payload: AdminGrantVipRequest,
    db: Session = Depends(get_db),
) -> AdminUserSummary:
    user = db.get(UserRow, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.days <= 0:
        raise HTTPException(status_code=422, detail="days must be positive")
    now = datetime.now(UTC)
    vip_base = user.vip_expired_at if user.vip_expired_at and user.vip_expired_at > now else now
    user.vip_status = "active"
    user.vip_expired_at = vip_base + timedelta(days=payload.days)
    db.commit()
    db.refresh(user)
    return to_admin_user(user, now)


@app.post("/admin/users/{user_id}/revoke-vip", response_model=AdminUserSummary)
def admin_revoke_vip(
    user_id: str,
    db: Session = Depends(get_db),
) -> AdminUserSummary:
    user = db.get(UserRow, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.vip_status = "inactive"
    user.vip_expired_at = None
    revoke_vpn_devices(db, user)
    db.commit()
    db.refresh(user)
    return to_admin_user(user)


@app.post("/admin/orders/{order_id}/confirm", response_model=Order)
def confirm_order(
    order_id: str,
    payload: AdminOrderAction | None = None,
    db: Session = Depends(get_db),
) -> Order:
    order = require_order(db, order_id)
    if order.status != OrderStatus.pending_confirm.value:
        raise HTTPException(status_code=409, detail=f"Order status is {order.status}")
    plan = db.get(VipPlanRow, order.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    user = db.get(UserRow, order.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    now = datetime.now(UTC)
    vip_base = user.vip_expired_at if user.vip_expired_at and user.vip_expired_at > now else now
    user.vip_status = "active"
    user.vip_expired_at = vip_base + timedelta(days=plan.duration_days)
    apply_invitation_reward(db, user, order)
    order.status = OrderStatus.completed.value
    order.confirmed_at = now
    order.reviewed_by = payload.reviewed_by if payload else "admin"
    order.review_note = payload.note if payload else None
    db.commit()
    db.refresh(order)
    return to_order(order, user.email)


@app.post("/admin/orders/{order_id}/reject", response_model=Order)
def reject_order(
    order_id: str,
    payload: AdminOrderAction | None = None,
    db: Session = Depends(get_db),
) -> Order:
    order = require_order(db, order_id)
    if order.status == OrderStatus.completed.value:
        raise HTTPException(status_code=409, detail="Completed order cannot be rejected")
    order.status = OrderStatus.rejected.value
    order.reviewed_by = payload.reviewed_by if payload else "admin"
    order.review_note = payload.note if payload else None
    db.commit()
    db.refresh(order)
    emails = user_email_map(db, {order.user_id})
    return to_order(order, emails.get(order.user_id))


def require_order(db: Session, order_id: str) -> OrderRow:
    order = db.get(OrderRow, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def node_health_map(db: Session) -> dict[str, VpnNodeHealthRow]:
    return {row.node_id: row for row in db.scalars(select(VpnNodeHealthRow)).all()}


@app.get("/vpn/nodes", response_model=list[VpnNodeSummary])
def list_vpn_nodes(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> list[VpnNodeSummary]:
    user = get_current_user(db, authorization)
    vip = user_is_vip(user)
    now = datetime.now(UTC)
    health = node_health_map(db)
    nodes = db.scalars(
        select(VpnNodeRow).where(VpnNodeRow.enabled.is_(True)).order_by(VpnNodeRow.weight.desc())
    ).all()
    return [to_vpn_node_summary(node, health.get(node.id), vip, now) for node in nodes]


@app.get("/vpn/nodes/{node_id}/config", response_model=VpnNodeConfig)
def get_vpn_node_config(
    node_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> VpnNodeConfig:
    user = get_current_user(db, authorization)
    if ensure_free_traffic_quota(user):
        db.commit()
        db.refresh(user)
    entitlement = build_vpn_entitlement(user)
    if not entitlement.allowed:
        raise HTTPException(status_code=403, detail=entitlement.reason)
    node = require_node(db, node_id)
    if not node.enabled:
        raise HTTPException(status_code=403, detail="node_disabled")
    if node.vip_only and not user_is_vip(user):
        raise HTTPException(status_code=403, detail="vip_required")
    device = provision_node_device(db, user, node)
    return VpnNodeConfig(
        id=node.id,
        name=node.name,
        region=node.region,
        tunnel_name=device.tunnel_name,
        config_text=device.config_text,
        entitlement=entitlement,
    )


@app.post("/internal/nodes/heartbeat", include_in_schema=False)
def node_heartbeat(
    payload: NodeHeartbeatRequest,
    x_internal_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not node_service.verify_internal_token(x_internal_token):
        raise HTTPException(status_code=401, detail="Invalid internal token")
    node = db.get(VpnNodeRow, payload.node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    now = datetime.now(UTC)
    health = db.get(VpnNodeHealthRow, payload.node_id)
    if health is None:
        health = VpnNodeHealthRow(node_id=payload.node_id)
        db.add(health)
    health.last_heartbeat_at = now
    health.peer_count = payload.peer_count
    health.cpu_load = payload.cpu_load
    health.mem_used_percent = payload.mem_used_percent
    health.rx_bytes = payload.rx_bytes
    health.tx_bytes = payload.tx_bytes
    health.agent_version = payload.agent_version
    node.status = "online"
    db.commit()
    return {"status": "ok"}


@app.get("/admin/nodes", response_model=list[AdminNodeSummary])
def list_admin_nodes(db: Session = Depends(get_db)) -> list[AdminNodeSummary]:
    now = datetime.now(UTC)
    health = node_health_map(db)
    nodes = db.scalars(select(VpnNodeRow).order_by(VpnNodeRow.weight.desc())).all()
    return [to_admin_node(node, health.get(node.id), now) for node in nodes]


@app.post("/admin/nodes", response_model=AdminNodeSummary, status_code=201)
def create_admin_node(payload: AdminNodeRequest, db: Session = Depends(get_db)) -> AdminNodeSummary:
    node_id = (payload.id or f"node_{uuid4().hex[:10]}").strip()
    if db.get(VpnNodeRow, node_id) is not None:
        raise HTTPException(status_code=409, detail="Node id already exists")
    node = VpnNodeRow(
        id=node_id,
        name=payload.name,
        region=payload.region,
        endpoint=payload.endpoint,
        agent_host=payload.agent_host,
        agent_port=payload.agent_port,
        server_public_key=payload.server_public_key,
        client_network=payload.client_network,
        dns=payload.dns,
        allowed_ips=payload.allowed_ips,
        persistent_keepalive=payload.persistent_keepalive,
        mtu=payload.mtu,
        params_json=json.dumps(payload.params),
        weight=payload.weight,
        vip_only=payload.vip_only,
        max_clients=payload.max_clients,
        enabled=payload.enabled,
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    return to_admin_node(node, None, datetime.now(UTC))


@app.put("/admin/nodes/{node_id}", response_model=AdminNodeSummary)
def update_admin_node(
    node_id: str,
    payload: AdminNodeRequest,
    db: Session = Depends(get_db),
) -> AdminNodeSummary:
    node = require_node(db, node_id)
    node.name = payload.name
    node.region = payload.region
    node.endpoint = payload.endpoint
    node.agent_host = payload.agent_host
    node.agent_port = payload.agent_port
    node.server_public_key = payload.server_public_key
    node.client_network = payload.client_network
    node.dns = payload.dns
    node.allowed_ips = payload.allowed_ips
    node.persistent_keepalive = payload.persistent_keepalive
    node.mtu = payload.mtu
    node.params_json = json.dumps(payload.params)
    node.weight = payload.weight
    node.vip_only = payload.vip_only
    node.max_clients = payload.max_clients
    node.enabled = payload.enabled
    db.commit()
    db.refresh(node)
    health = db.get(VpnNodeHealthRow, node_id)
    return to_admin_node(node, health, datetime.now(UTC))


@app.delete("/admin/nodes/{node_id}", status_code=204, response_class=Response)
def delete_admin_node(node_id: str, db: Session = Depends(get_db)) -> Response:
    node = require_node(db, node_id)
    health = db.get(VpnNodeHealthRow, node_id)
    if health is not None:
        db.delete(health)
    db.delete(node)
    db.commit()
    return Response(status_code=204)


USER_PAGE_PATHS = {"login", "register", "center", "vip", "download", "guide"}


@app.get("/{page_name}", response_class=HTMLResponse, include_in_schema=False)
def user_site_page(page_name: str) -> str:
    if page_name not in USER_PAGE_PATHS:
        raise HTTPException(status_code=404, detail="Page not found")
    return SITE_HTML
