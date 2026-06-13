from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_salt: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str] = mapped_column(String(32), default="")
    nickname: Mapped[str] = mapped_column(String(64))
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    invited_by_user_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"), nullable=True)
    vip_status: Mapped[str] = mapped_column(String(24), default="inactive")
    vip_expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cash_balance_cents: Mapped[int] = mapped_column(Integer, default=0)
    free_traffic_quota_bytes: Mapped[int] = mapped_column(BigInteger, default=31_457_280)
    free_traffic_used_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(24), default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuthSessionRow(Base):
    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VipPlanRow(Base):
    __tablename__ = "vip_plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    duration_days: Mapped[int] = mapped_column(Integer)
    original_price_cents: Mapped[int] = mapped_column(Integer)
    sale_price_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PromotionActivityRow(Base):
    __tablename__ = "promotion_activities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    tag: Mapped[str] = mapped_column(String(32))
    plan_id: Mapped[str] = mapped_column(String(64), ForeignKey("vip_plans.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    promo_price_cents: Mapped[int] = mapped_column(Integer)
    invite_extra_discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    stackable: Mapped[bool] = mapped_column(Boolean, default=False)
    new_user_only: Mapped[bool] = mapped_column(Boolean, default=False)
    countdown_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PaymentSettingRow(Base):
    __tablename__ = "payment_settings"

    channel: Mapped[str] = mapped_column(String(24), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(32))
    qr_url: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class OrderRow(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    plan_id: Mapped[str] = mapped_column(String(64), ForeignKey("vip_plans.id"), index=True)
    promotion_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("promotion_activities.id"), nullable=True)
    invite_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    original_amount_cents: Mapped[int] = mapped_column(Integer)
    discount_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    pay_amount_cents: Mapped[int] = mapped_column(Integer)
    pay_channel: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="pending_payment", index=True)
    payment_qr_url: Mapped[str] = mapped_column(Text)
    paid_marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InvitationRow(Base):
    __tablename__ = "invitations"
    __table_args__ = (UniqueConstraint("inviter_user_id", "invitee_user_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    inviter_user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    invitee_user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("orders.id"), nullable=True)
    reward_cents: Mapped[int] = mapped_column(Integer, default=1000)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    risk_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WithdrawalRow(Base):
    __tablename__ = "withdrawals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    account_type: Mapped[str] = mapped_column(String(24))
    account_masked: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VpnDeviceRow(Base):
    __tablename__ = "vpn_devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    node_id: Mapped[str] = mapped_column(String(64), default="default")
    tunnel_name: Mapped[str] = mapped_column(String(32), default="xingsui")
    client_private_key: Mapped[str] = mapped_column(Text)
    client_public_key: Mapped[str] = mapped_column(Text)
    client_address: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    config_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class VpnNodeRow(Base):
    __tablename__ = "vpn_nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    region: Mapped[str] = mapped_column(String(64), default="智能线路")
    # 客户端连接入口（公网 host:port），下发给 App。
    endpoint: Mapped[str] = mapped_column(String(128))
    # 控制面访问 Agent 的地址与端口（内网/公网 IP）。
    agent_host: Mapped[str] = mapped_column(String(128))
    agent_port: Mapped[int] = mapped_column(Integer, default=51821)
    server_public_key: Mapped[str] = mapped_column(Text)
    client_network: Mapped[str] = mapped_column(String(64), default="10.66.66.0/24")
    dns: Mapped[str] = mapped_column(String(128), default="1.1.1.1")
    allowed_ips: Mapped[str] = mapped_column(Text, default="0.0.0.0/0")
    persistent_keepalive: Mapped[int] = mapped_column(Integer, default=25)
    mtu: Mapped[int] = mapped_column(Integer, default=1420)
    # AmneziaWG 混淆参数（Jc/Jmin/Jmax/S1/S2/H1-H4 等）JSON 序列化存储。
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    # 调度权重越大越优先；0 表示禁止参与普通调度。
    weight: Mapped[int] = mapped_column(Integer, default=100)
    # 仅 VIP 可用（如大阪 CN2 GIA 精品线路）。
    vip_only: Mapped[bool] = mapped_column(Boolean, default=False)
    # 最大承载客户端数，0 表示不限。
    max_clients: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="unknown", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class VpnNodeHealthRow(Base):
    __tablename__ = "vpn_node_health"

    node_id: Mapped[str] = mapped_column(String(64), ForeignKey("vpn_nodes.id"), primary_key=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    peer_count: Mapped[int] = mapped_column(Integer, default=0)
    cpu_load: Mapped[float] = mapped_column(Float, default=0.0)
    mem_used_percent: Mapped[float] = mapped_column(Float, default=0.0)
    rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    agent_version: Mapped[str] = mapped_column(String(32), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
