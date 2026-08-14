# Xingsui Control Plane

The Xingsui control plane is a FastAPI and PostgreSQL service for account authentication, membership, payments, managed VPN credentials, third-party subscriptions, node health, and administration.

## Capabilities

- Email registration and finite bearer sessions.
- Monthly, quarterly, and annual membership plans.
- Manual WeChat or Alipay order confirmation.
- Invitation codes, first-order cashback, and withdrawal review.
- Android AmneziaWG and Windows VLESS Reality provisioning.
- Revocable device leases with expiry bounded by the session and membership.
- Clash/mihomo-compatible subscription links for active members.
- Authenticated node-agent registration, heartbeats, and lease reconciliation.
- Website, download endpoint, and an HttpOnly-cookie administration console.

The API is fail-closed: it never falls back to static shared credentials. A provisioning failure returns `503`, and expired or inactive membership cannot authorize a tunnel.

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

Create `.env` with local values:

```env
DATABASE_URL=postgresql+psycopg://xingsui@localhost:5432/xingsui_dev
ADMIN_PASSWORD=CHANGE_ME
ADMIN_SESSION_SECRET=CHANGE_ME
CORS_ALLOW_ORIGINS=http://localhost:3000
ACCESS_TOKEN_TTL_SECONDS=86400
VPN_LEASE_TTL_SECONDS=3600
NODE_AGENT_SCHEME=https
NODE_AGENT_SECRETS_FILE=/run/secrets/xingsui-node-agent-secrets.json
NODE_AGENT_CA_FILE=/run/secrets/xingsui-node-agent-ca.pem
```

Development startup creates the required tables and seeds the default membership plans. Production must use the checked-in migrations and deployment secrets.

## Authorization and provisioning

Android requests use `X-Xingsui-Platform: android` and receive complete AmneziaWG configurations. Windows requests use `X-Xingsui-Platform: windows` and receive VLESS Reality configurations. Each credential is generated for one user or device and installed through the authenticated edge agent.

AmneziaWG nodes require endpoint, agent address, server public key, and complete protocol parameters. VLESS nodes require host, port, Reality public key, short ID, SNI, fingerprint, and flow. UUIDs are generated per lease and are never read from static node configuration.

Edge agents reconcile managed state on startup and remove unmanaged legacy credentials. VLESS changes are validated with `sing-box check`, atomically installed, and rolled back if reload fails.

## Subscription delivery

Active members can create revocable subscription URLs. The public feed supports Clash/mihomo clients and contains the three enabled production VLESS nodes plus an informational expiry entry. Offline nodes are excluded when at least one healthy node is available; a bounded fallback prevents an empty feed while fresh heartbeats arrive after recovery.

Subscription credentials are stored as hashes. Startup migrations must preserve those hashes so previously exported URLs remain valid.

## Plans and commercial workflow

The current seeded plans are CNY 18 for 30 days, CNY 48 for 90 days, and CNY 158 for 365 days. Payment QR settings and order confirmation are managed through the administration console. An inviter receives CNY 10 after an invitee's first confirmed paid order; later orders do not repeat the reward.

## Useful endpoints

```text
GET  /health
POST /auth/email/register
POST /auth/email/login
GET  /plans
POST /orders
GET  /vpn/authorize
GET  /vpn/config
GET  /subscription-link
GET  /sub/{token}
GET  /admin
```

## Verification

```bash
PYTHONPATH=. uv run pytest -q
```

Production also requires PostgreSQL backups, node-agent secret rotation, Caddy TLS health checks, and validation of both canonical domains before a release is promoted.
