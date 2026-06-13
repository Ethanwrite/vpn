-- 0001_vpn_nodes.sql
-- 节点池（方案 A：控制面 + 边缘节点 Agent）所需的表结构。
-- 幂等：可重复执行；应用启动时 run_lightweight_migrations() 也会自动创建。
-- 手动执行：psql "$DATABASE_URL" -f migrations/0001_vpn_nodes.sql

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
);

create index if not exists ix_vpn_nodes_enabled on vpn_nodes(enabled);
create index if not exists ix_vpn_nodes_status on vpn_nodes(status);

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
);
