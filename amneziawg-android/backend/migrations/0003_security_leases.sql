-- Security leases: finite user sessions, platform-specific nodes and revocable VPN credentials.
-- This migration is idempotent and intentionally leaves legacy rows without an active lease.

alter table auth_sessions add column if not exists status varchar(24) not null default 'active';
update auth_sessions set status = 'revoked' where expires_at is null;
create index if not exists ix_auth_sessions_status on auth_sessions(status);

-- Invalidate every legacy query-string subscription credential.
update users
set subscription_token_hash = null,
    subscription_token_masked = null,
    subscription_token_version = subscription_token_version + 1
where subscription_token_hash is not null or subscription_token_masked is not null;

alter table vpn_nodes add column if not exists protocol varchar(16) not null default 'awg';
update vpn_nodes
set protocol = 'dual'
where params_json like '%VlessPublicKey%' or params_json like '%VlessShortId%';
create index if not exists ix_vpn_nodes_protocol on vpn_nodes(protocol);
update vpn_nodes
set allowed_ips = '0.0.0.0/0, ::/0'
where trim(allowed_ips) = '0.0.0.0/0';

alter table vpn_devices add column if not exists protocol varchar(16) not null default 'awg';
alter table vpn_devices add column if not exists session_token_hash varchar(128) not null default '';
alter table vpn_devices add column if not exists lease_id varchar(64) not null default '';
alter table vpn_devices add column if not exists lease_expires_at timestamptz;
alter table vpn_devices add column if not exists vless_uuid varchar(64);

-- Existing credentials were issued without a finite lease and must not be restored.
update vpn_devices
set status = 'revoked',
    client_private_key = '',
    config_text = ''
where lease_expires_at is null;

update vpn_devices
set client_private_key = '',
    config_text = ''
where status <> 'active';

create index if not exists ix_vpn_devices_protocol on vpn_devices(protocol);
create index if not exists ix_vpn_devices_session_token_hash on vpn_devices(session_token_hash);
create index if not exists ix_vpn_devices_lease_expires_at on vpn_devices(lease_expires_at);
create unique index if not exists ix_vpn_devices_lease_id_unique
on vpn_devices(lease_id)
where lease_id <> '';
create unique index if not exists ix_vpn_devices_active_session_node
on vpn_devices(user_id, node_id, protocol, session_token_hash)
where status = 'active';
drop index if exists ix_vpn_devices_client_address;
create index if not exists ix_vpn_devices_client_address
on vpn_devices(client_address);
create unique index if not exists ix_vpn_devices_active_node_address
on vpn_devices(node_id, client_address)
where protocol = 'awg' and status in ('active', 'pending_revoke');

create table if not exists node_request_nonces (
    id varchar(128) primary key,
    node_id varchar(64) not null references vpn_nodes(id),
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);
create index if not exists ix_node_request_nonces_node_id on node_request_nonces(node_id);
create index if not exists ix_node_request_nonces_expires_at on node_request_nonces(expires_at);
