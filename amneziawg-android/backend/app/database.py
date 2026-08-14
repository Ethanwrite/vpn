import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://localhost/xingsui_dev")
DATABASE_SCHEMA_LOCK_ID = 912050232111

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_database() -> None:
    from app import db_models  # noqa: F401

    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            # Transaction-scoped is important: a session lock manually released in a
            # ``finally`` block becomes visible just before ``engine.begin()`` commits,
            # while PostgreSQL still holds the DDL table locks from this transaction.
            connection.execute(text(f"select pg_advisory_xact_lock({DATABASE_SCHEMA_LOCK_ID})"))
        Base.metadata.create_all(bind=connection)
        run_lightweight_migrations(connection)


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
    connection.execute(text("alter table auth_sessions add column if not exists status varchar(24) not null default 'active'"))
    connection.execute(text("update auth_sessions set status = 'revoked' where expires_at is null"))
    connection.execute(text("create index if not exists ix_auth_sessions_status on auth_sessions(status)"))
    connection.execute(text("create index if not exists ix_users_created_at on users(created_at)"))
    connection.execute(text("create index if not exists ix_users_last_seen_at on users(last_seen_at)"))
    connection.execute(text("create index if not exists ix_users_vip_expired_at on users(vip_expired_at)"))
    connection.execute(text("create index if not exists ix_users_subscription_token_hash on users(subscription_token_hash)"))
    connection.execute(
        text(
            """
            create table if not exists node_request_nonces (
                id varchar(128) primary key,
                node_id varchar(64) not null references vpn_nodes(id),
                expires_at timestamptz not null,
                created_at timestamptz not null default now()
            )
            """
        )
    )
    connection.execute(text("create index if not exists ix_node_request_nonces_node_id on node_request_nonces(node_id)"))
    connection.execute(text("create index if not exists ix_node_request_nonces_expires_at on node_request_nonces(expires_at)"))
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
                client_address varchar(64) not null,
                config_text text not null,
                status varchar(24) not null default 'active',
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now()
            )
            """
        )
    )
    connection.execute(text("create index if not exists ix_vpn_devices_user_id on vpn_devices(user_id)"))
    if engine.dialect.name == "postgresql":
        connection.execute(text("drop index if exists ix_vpn_devices_client_address"))
    connection.execute(text("create index if not exists ix_vpn_devices_client_address on vpn_devices(client_address)"))
    connection.execute(text("create index if not exists ix_vpn_devices_status on vpn_devices(status)"))
    connection.execute(text("alter table vpn_devices add column if not exists protocol varchar(16) not null default 'awg'"))
    connection.execute(text("alter table vpn_devices add column if not exists session_token_hash varchar(128) not null default ''"))
    connection.execute(text("alter table vpn_devices add column if not exists lease_id varchar(64) not null default ''"))
    connection.execute(text("alter table vpn_devices add column if not exists lease_expires_at timestamptz"))
    connection.execute(text("alter table vpn_devices add column if not exists vless_uuid varchar(64)"))
    connection.execute(text("create index if not exists ix_vpn_devices_protocol on vpn_devices(protocol)"))
    connection.execute(text("create index if not exists ix_vpn_devices_session_token_hash on vpn_devices(session_token_hash)"))
    connection.execute(text("create index if not exists ix_vpn_devices_lease_expires_at on vpn_devices(lease_expires_at)"))
    connection.execute(text("create unique index if not exists ix_vpn_devices_lease_id_unique on vpn_devices(lease_id) where lease_id <> ''"))
    connection.execute(
        text(
            "update vpn_devices set status = 'revoked', client_private_key = '', config_text = '' "
            "where lease_expires_at is null and status = 'active'"
        )
    )
    connection.execute(
        text("update vpn_devices set client_private_key = '', config_text = '' where status <> 'active'")
    )
    connection.execute(
        text(
            "create unique index if not exists ix_vpn_devices_active_session_node "
            "on vpn_devices(user_id, node_id, protocol, session_token_hash) where status = 'active'"
        )
    )
    connection.execute(
        text(
            "create unique index if not exists ix_vpn_devices_active_node_address "
            "on vpn_devices(node_id, client_address) "
            "where protocol = 'awg' and status in ('active', 'pending_revoke')"
        )
    )
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
                allowed_ips text not null default '0.0.0.0/0, ::/0',
                persistent_keepalive integer not null default 25,
                mtu integer not null default 1280,
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
    connection.execute(text("alter table vpn_nodes add column if not exists protocol varchar(16) not null default 'awg'"))
    connection.execute(
        text(
            "update vpn_nodes set protocol = 'dual' "
            "where params_json like '%VlessPublicKey%' or params_json like '%VlessShortId%'"
        )
    )
    connection.execute(text("update vpn_nodes set allowed_ips = '0.0.0.0/0, ::/0' where trim(allowed_ips) = '0.0.0.0/0'"))
    connection.execute(text("create index if not exists ix_vpn_nodes_protocol on vpn_nodes(protocol)"))
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
