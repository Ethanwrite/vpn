import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://localhost/xingsui_dev")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_database() -> None:
    from app import db_models  # noqa: F401

    with engine.begin() as connection:
        locked = engine.dialect.name == "postgresql"
        if locked:
            connection.execute(text("select pg_advisory_lock(912050232111)"))
        try:
            Base.metadata.create_all(bind=connection)
            run_lightweight_migrations(connection)
        finally:
            if locked:
                connection.execute(text("select pg_advisory_unlock(912050232111)"))


def run_lightweight_migrations(connection=None) -> None:
    if connection is None:
        with engine.begin() as owned_connection:
            run_lightweight_migrations(owned_connection)
        return

    connection.execute(
        text("alter table users add column if not exists free_traffic_quota_bytes bigint not null default 31457280")
    )
    connection.execute(
        text("alter table users add column if not exists free_traffic_used_bytes bigint not null default 0")
    )
    connection.execute(text("alter table users add column if not exists subscription_token_version integer not null default 0"))
    connection.execute(text("alter table users add column if not exists subscription_token_hash varchar(128)"))
    connection.execute(text("alter table users add column if not exists subscription_token_masked varchar(32)"))
    connection.execute(text("alter table users add column if not exists subscription_token_created_at timestamptz"))
    connection.execute(text("alter table users add column if not exists last_login_at timestamptz"))
    connection.execute(text("alter table users add column if not exists last_seen_at timestamptz"))
    connection.execute(text("create index if not exists ix_users_created_at on users(created_at)"))
    connection.execute(text("create index if not exists ix_users_last_seen_at on users(last_seen_at)"))
    connection.execute(text("create index if not exists ix_users_vip_expired_at on users(vip_expired_at)"))
    connection.execute(text("create index if not exists ix_users_subscription_token_hash on users(subscription_token_hash)"))
    connection.execute(
        text(
            """
            create table if not exists subscription_audit_logs (
                id varchar(64) primary key,
                user_id varchar(64) not null references users(id),
                action varchar(24) not null,
                token_hash_prefix varchar(16) not null default '',
                masked_token varchar(32) not null default '',
                ip_address varchar(64) not null default '',
                user_agent varchar(255) not null default '',
                created_at timestamptz not null default now()
            )
            """
        )
    )
    connection.execute(text("create index if not exists ix_subscription_audit_logs_user_id on subscription_audit_logs(user_id)"))
    connection.execute(text("create index if not exists ix_subscription_audit_logs_action on subscription_audit_logs(action)"))
    connection.execute(text("create index if not exists ix_subscription_audit_logs_created_at on subscription_audit_logs(created_at)"))
    connection.execute(
        text(
            """
            create table if not exists vpn_devices (
                id varchar(64) primary key,
                user_id varchar(64) not null references users(id),
                node_id varchar(64) not null default 'default',
                tunnel_name varchar(32) not null default 'xingsui',
                client_private_key text not null,
                client_public_key text not null,
                client_address varchar(64) not null unique,
                config_text text not null,
                status varchar(24) not null default 'active',
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now()
            )
            """
        )
    )
    connection.execute(text("create index if not exists ix_vpn_devices_user_id on vpn_devices(user_id)"))
    connection.execute(text("create index if not exists ix_vpn_devices_client_address on vpn_devices(client_address)"))
    connection.execute(text("create index if not exists ix_vpn_devices_status on vpn_devices(status)"))
    connection.execute(
        text(
            """
            create table if not exists vpn_nodes (
                id varchar(64) primary key,
                name varchar(128) not null,
                region varchar(64) not null default '智能线路',
                endpoint varchar(128) not null,
                agent_host varchar(128) not null,
                agent_port integer not null default 51821,
                server_public_key text not null,
                client_network varchar(64) not null default '10.66.66.0/24',
                dns varchar(128) not null default '1.1.1.1',
                allowed_ips text not null default '0.0.0.0/0',
                persistent_keepalive integer not null default 25,
                mtu integer not null default 1420,
                params_json text not null default '{}',
                weight integer not null default 100,
                vip_only boolean not null default false,
                max_clients integer not null default 0,
                enabled boolean not null default true,
                status varchar(24) not null default 'unknown',
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now()
            )
            """
        )
    )
    connection.execute(text("create index if not exists ix_vpn_nodes_enabled on vpn_nodes(enabled)"))
    connection.execute(text("create index if not exists ix_vpn_nodes_status on vpn_nodes(status)"))
    connection.execute(
        text(
            """
            create table if not exists vpn_node_health (
                node_id varchar(64) primary key references vpn_nodes(id),
                last_heartbeat_at timestamptz,
                peer_count integer not null default 0,
                cpu_load double precision not null default 0,
                mem_used_percent double precision not null default 0,
                rx_bytes bigint not null default 0,
                tx_bytes bigint not null default 0,
                agent_version varchar(32) not null default '',
                updated_at timestamptz not null default now()
            )
            """
        )
    )
