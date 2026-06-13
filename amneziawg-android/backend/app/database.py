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

    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()


def run_lightweight_migrations() -> None:
    with engine.begin() as connection:
        connection.execute(
            text("alter table users add column if not exists free_traffic_quota_bytes bigint not null default 31457280")
        )
        connection.execute(
            text("alter table users add column if not exists free_traffic_used_bytes bigint not null default 0")
        )
        connection.execute(text("alter table users add column if not exists last_login_at timestamptz"))
        connection.execute(text("alter table users add column if not exists last_seen_at timestamptz"))
        connection.execute(text("create index if not exists ix_users_created_at on users(created_at)"))
        connection.execute(text("create index if not exists ix_users_last_seen_at on users(last_seen_at)"))
        connection.execute(text("create index if not exists ix_users_vip_expired_at on users(vip_expired_at)"))
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
