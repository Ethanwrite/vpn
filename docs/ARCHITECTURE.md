# Xingsui Production Architecture

## System overview

Xingsui separates commercial control-plane responsibilities from protocol termination. The control plane authenticates users, evaluates entitlement, schedules healthy nodes, issues bounded credentials, serves subscriptions, records commercial state, and provides administrative workflows. Edge agents apply and revoke credentials on selected VPN servers.

```text
Android / Windows / Clash-compatible client
                 |
          HTTPS (Caddy)
                 |
     FastAPI control plane + PostgreSQL
          |                  |
 authenticated agent API    | account, membership,
          |                  | order and lease state
          v
 Utah / Sydney / Singapore edge nodes
```

## Production inventory

### Control plane and Hong Kong relay

- Host: `64.90.24.84`
- Domains: `xingsui.org` and `xingsuico.com`
- Services: Caddy 2, FastAPI, SQLAlchemy, PostgreSQL 16, website, administration console, and download distribution.
- Relay ingress: AmneziaWG on UDP `4500` and VLESS Reality on TCP `10444`.
- Forwarding invariant: Docker sets the host `FORWARD` policy to `DROP`, so relay permits must be installed in `DOCKER-USER`; a separate nftables accept chain alone is insufficient.

### Active edge nodes

| Node ID | Region | Landing address | Published endpoints | Weight |
| --- | --- | --- | --- | ---: |
| `node-144` | Utah, US | `144.172.97.191` | AWG UDP `443`; VLESS TCP `8443` | 150 |
| `node-sydney` | Sydney, AU | `144.172.65.152` | AWG UDP `443`; VLESS TCP `8443` | 120 |
| `node-singapore` | Singapore | `61.13.236.31` | Public via Hong Kong `64.90.24.84:4500` and `:10444`; landing AWG `51820`, VLESS `10443` | 60 |

Singapore administration uses SSH port `20020`. Credentials are operational secrets and must never be committed.

All active nodes run edge Agent 2.1.2, BBR, AmneziaWG with MTU 1280, and VLESS Reality/Vision using `xtls-rprx-vision` with `xingsui.org` as the server name.

The legacy `node-japan-02` and `node-172` records, along with the previous Singapore landing host, are disabled. They must not be returned by scheduling or subscription APIs.

## Client access paths

### Android

The Android client requests a managed AmneziaWG lease. The control plane selects a healthy enabled node, generates a client key pair and address, asks the edge agent to install the peer, and returns a complete configuration. No shared static client configuration is used.

### Windows

The Windows client requests a VLESS Reality lease. The control plane creates a user-specific UUID, installs it through the node agent, and returns the VLESS, Reality, SNI, fingerprint, and Vision flow parameters required by sing-box.

### Third-party subscriptions

Active members can export a revocable Clash/mihomo subscription URL. The feed contains the three active VLESS nodes and an informational entry that shows membership expiry. Tokens are persisted as hashes and are bound to the owning account's membership expiry.

## Identity and entitlement

The server is authoritative for account state, session expiry, membership expiry, and free allowance. Clients cannot grant or extend access locally.

- New accounts have a 60 MB server-measured free allowance.
- Active membership removes the product traffic cap.
- Device and subscription credentials cannot outlive membership.
- Agent leases are capped at one hour and can be revoked earlier.
- Disabled users, expired sessions, or expired memberships fail closed.

## Node health and scheduling

Agents report version, capacity, load, protocol readiness, and heartbeats. Normal scheduling requires an enabled, protocol-compatible, healthy node with complete parameters. Weight provides the stable preference order while load and recent health prevent sending users to a degraded server.

Subscription output excludes offline nodes whenever at least one healthy node exists. A recovery fallback may retain enabled nodes briefly when all heartbeats are stale, preventing a structurally empty subscription immediately after services restart.

## Credential lifecycle

1. The client presents a finite bearer session.
2. The control plane validates the account, platform, allowance or membership, and requested action.
3. A healthy compatible node is selected.
4. A user- or device-specific credential is generated.
5. The authenticated edge agent installs the peer or UUID.
6. The control plane persists the bounded lease and returns the client configuration.
7. Expiry, disconnect, account action, or reconciliation removes the credential.

Agent state is root-only. VLESS configuration updates are written to a same-directory temporary file, validated with `sing-box check`, atomically replaced, and rolled back if reload fails.

## Commercial data model

PostgreSQL stores users, sessions, plans, promotions, payment settings, orders, invitations, cashback balances, withdrawal requests, membership state, usage counters, node inventory, heartbeats, subscription credentials, devices, and VPN leases.

Current plans are CNY 18 for 30 days, CNY 48 for 90 days, and CNY 158 for 365 days.

Database migrations must preserve subscription token hashes and user credentials. Before membership grants or bulk compensation, create a full database backup and a per-user audit record.

## Deployment and networking

Caddy terminates TLS for both canonical domains and proxies the FastAPI application. PostgreSQL is private to the deployment network. Node-agent endpoints and secrets are not exposed in public documentation or client payloads.

The Singapore path uses destination NAT and masquerading on the Hong Kong host:

- UDP `64.90.24.84:4500` to `61.13.236.31:51820`
- TCP `64.90.24.84:10444` to `61.13.236.31:10443`

The relay systemd unit is ordered after Docker and replays `DOCKER-USER` rules because Docker can rebuild that chain during restart.

## Security invariants

- Never commit passwords, private keys, API tokens, databases, payment QR assets, or generated client credentials.
- Hash subscription tokens at rest and make them individually revocable.
- Authenticate and authorize every provisioning request.
- Use authenticated node-agent communication and rotate agent secrets.
- Do not return cached or shared credentials after an agent error.
- Restrict PostgreSQL, administration, and SSH access by network policy.
- Keep backups encrypted and test restoration procedures.
- Treat client logs as sensitive and avoid persisting tunnel credentials.

## Release state and verification

Current production clients are Android 2.0.29 (version code 39) and Windows 1.0.23. A release is ready only after:

- Backend tests pass against PostgreSQL behavior.
- Android debug compilation and release assembly pass.
- Both domains serve the expected API, website, and download artifact.
- APK checksums match across mirrors.
- All three agents report version 2.1.2 and healthy protocol state.
- Direct and Hong Kong-relayed connectivity is verified.
- Clash/mihomo import produces three usable nodes plus the expiry information entry.
- Disabled legacy nodes are absent from scheduling and subscriptions.
