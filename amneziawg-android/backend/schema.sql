create table users (
    id varchar(64) primary key,
    email varchar(255) not null unique,
    password_salt varchar(64) not null,
    password_hash varchar(128) not null,
    phone varchar(32) not null default '',
    nickname varchar(64) not null,
    invite_code varchar(16) not null unique,
    invited_by_user_id varchar(64) references users(id),
    vip_status varchar(24) not null default 'inactive',
    vip_expired_at timestamptz,
    cash_balance_cents integer not null default 0,
    free_traffic_quota_bytes bigint not null default 31457280,
    free_traffic_used_bytes bigint not null default 0,
    status varchar(24) not null default 'active',
    subscription_token_version integer not null default 0,
    subscription_token_hash varchar(128),
    subscription_token_masked varchar(32),
    subscription_token_created_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table auth_sessions (
    token_hash varchar(128) primary key,
    user_id varchar(64) not null references users(id),
    status varchar(24) not null default 'active',
    expires_at timestamptz,
    created_at timestamptz not null default now()
);
create index ix_auth_sessions_status on auth_sessions(status);

create table subscription_audit_logs (
    id varchar(64) primary key,
    user_id varchar(64) not null references users(id),
    action varchar(24) not null,
    token_hash_prefix varchar(16) not null default '',
    masked_token varchar(32) not null default '',
    ip_address varchar(64) not null default '',
    user_agent varchar(255) not null default '',
    created_at timestamptz not null default now()
);

create index ix_users_subscription_token_hash on users(subscription_token_hash);
create index ix_subscription_audit_logs_user_id on subscription_audit_logs(user_id);
create index ix_subscription_audit_logs_action on subscription_audit_logs(action);
create index ix_subscription_audit_logs_created_at on subscription_audit_logs(created_at);

create table vip_plans (
    id varchar(64) primary key,
    name varchar(64) not null,
    duration_days integer not null,
    original_price_cents integer not null,
    sale_price_cents integer not null,
    status varchar(24) not null default 'active',
    created_at timestamptz not null default now()
);

create table promotion_activities (
    id varchar(64) primary key,
    name varchar(80) not null,
    tag varchar(32) not null,
    plan_id varchar(64) not null references vip_plans(id),
    starts_at timestamptz not null,
    ends_at timestamptz not null,
    promo_price_cents integer not null,
    invite_extra_discount_cents integer not null default 0,
    stackable boolean not null default false,
    new_user_only boolean not null default false,
    countdown_enabled boolean not null default true,
    status varchar(24) not null default 'active',
    created_at timestamptz not null default now()
);

create table payment_settings (
    channel varchar(24) primary key,
    display_name varchar(32) not null,
    qr_url text not null,
    enabled boolean not null default true,
    updated_at timestamptz not null default now()
);

create table orders (
    id varchar(64) primary key,
    order_no varchar(32) not null unique,
    user_id varchar(64) not null references users(id),
    plan_id varchar(64) not null references vip_plans(id),
    promotion_id varchar(64) references promotion_activities(id),
    invite_code varchar(16),
    original_amount_cents integer not null,
    discount_amount_cents integer not null default 0,
    pay_amount_cents integer not null,
    pay_channel varchar(24) not null,
    status varchar(24) not null default 'pending_payment',
    payment_qr_url text not null,
    payment_proof_url text,
    paid_marked_at timestamptz,
    confirmed_at timestamptz,
    reviewed_by varchar(64),
    review_note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table invitations (
    id varchar(64) primary key,
    inviter_user_id varchar(64) not null references users(id),
    invitee_user_id varchar(64) not null references users(id),
    order_id varchar(64) references orders(id),
    reward_cents integer not null default 1000,
    status varchar(24) not null default 'pending',
    risk_reason text,
    created_at timestamptz not null default now(),
    unique (inviter_user_id, invitee_user_id)
);

create table withdrawals (
    id varchar(64) primary key,
    user_id varchar(64) not null references users(id),
    amount_cents integer not null,
    account_type varchar(24) not null,
    account_masked varchar(80) not null,
    status varchar(24) not null default 'pending',
    reviewed_by varchar(64),
    reviewed_at timestamptz,
    created_at timestamptz not null default now()
);

create table vpn_devices (
    id varchar(64) primary key,
    user_id varchar(64) not null references users(id),
    node_id varchar(64) not null default 'default',
    protocol varchar(16) not null default 'awg',
    session_token_hash varchar(128) not null,
    lease_id varchar(64) not null unique,
    lease_expires_at timestamptz not null,
    vless_uuid varchar(64),
    tunnel_name varchar(32) not null default 'xingsui',
    client_private_key text not null,
    client_public_key text not null,
    client_address varchar(64) not null,
    config_text text not null,
    status varchar(24) not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table vpn_nodes (
    id varchar(64) primary key,
    name varchar(128) not null,
    region varchar(64) not null default '智能线路',
    protocol varchar(16) not null default 'awg',
    endpoint varchar(128) not null,
    agent_host varchar(128) not null,
    agent_port integer not null default 51821,
    server_public_key text not null,
    client_network varchar(64) not null default '10.66.66.0/24',
    dns varchar(128) not null default '1.1.1.1',
    allowed_ips text not null default '0.0.0.0/0, ::/0',
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
create unique index ix_vpn_devices_active_session_node
on vpn_devices(user_id, node_id, protocol, session_token_hash)
where status = 'active';
create index ix_vpn_devices_client_address on vpn_devices(client_address);
create unique index ix_vpn_devices_active_node_address
on vpn_devices(node_id, client_address)
where protocol = 'awg' and status in ('active', 'pending_revoke');

create index ix_vpn_nodes_enabled on vpn_nodes(enabled);
create index ix_vpn_nodes_status on vpn_nodes(status);
create index ix_vpn_nodes_protocol on vpn_nodes(protocol);

create table vpn_node_health (
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

create table node_request_nonces (
    id varchar(128) primary key,
    node_id varchar(64) not null references vpn_nodes(id),
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);
create index ix_node_request_nonces_node_id on node_request_nonces(node_id);
create index ix_node_request_nonces_expires_at on node_request_nonces(expires_at);
