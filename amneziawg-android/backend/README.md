# 星隧 Backend MVP

FastAPI MVP for the commercial flow:

- active VIP plans
- email/password registration and login
- 18 CNY monthly promotion
- manual WeChat/Alipay QR payment order
- user "paid" submission
- admin confirmation
- invite-code registration and first-order cashback
- cashback balance withdrawal by Alipay account, plus customer-service WeChat flow
- admin payment QR configuration
- App-side one-tap VPN startup backed by server entitlement checks
- VIP-only, platform-scoped VPN lease provisioning through `/vpn/config`
- five-minute, server-revocable AWG/VLESS leases (configurable with `VPN_LEASE_TTL_SECONDS`)
- built-in Admin page for manual review

Run locally after installing dependencies:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

Local PostgreSQL:

```bash
brew install postgresql@17
brew services start postgresql@17
createdb xingsui_dev
```

Create `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg://a1-6@localhost:5432/xingsui_dev
ADMIN_PASSWORD=CHANGE_ME_ADMIN_PASSWORD
ADMIN_SESSION_SECRET=xingsui-local-admin-session
CORS_ALLOW_ORIGINS=*
```

The API creates development tables automatically on startup and seeds the default VIP plans, the 18 CNY promotion, and a demo account.

Android debug builds call `http://10.0.2.2:8000`, which maps the emulator to the host machine. Keep this backend running while testing the membership page in an emulator.

Tunnel startup is blocked unless the bearer session is active and unexpired, the account is active, and VIP is active with a future `vip_expired_at`. Free-traffic counters are never accepted as VPN authorization. Android sends `X-Xingsui-Platform: android` and receives only complete AmneziaWG nodes; Windows sends `X-Xingsui-Platform: windows` and receives only complete VLESS Reality nodes. Every response carries a short lease bounded by both session and VIP expiry.

VPN node provisioning is fail-closed and uses only registered database nodes plus their authenticated edge Agent:

```env
ACCESS_TOKEN_TTL_SECONDS=86400
VPN_LEASE_TTL_SECONDS=300
NODE_AGENT_SCHEME=https
NODE_AGENT_SECRETS_FILE=/run/secrets/xingsui-node-agent-secrets.json
NODE_AGENT_CA_FILE=/run/secrets/xingsui-node-agent-ca.pem
```

There is no static config fallback. Agent errors return `503` and never return a cached/shared node credential. Legacy `/sub?token=...` and subscription-link export endpoints return `410`; node credentials require an Authorization bearer header.

Each `vpn_nodes` row has `protocol=awg|vless`. AWG rows require endpoint, Agent address, server public key and the complete J/S/H parameter set. VLESS rows require host, port, Reality public key, short ID, SNI and fingerprint in `params_json`; `VlessUUID` is ignored because UUIDs are generated per lease and installed/removed through the Agent.

On an AWG node set `XS_MANAGED_PROTOCOLS=awg`. On a VLESS node set `XS_MANAGED_PROTOCOLS=vless`, `XS_VLESS_CONFIG`, `XS_VLESS_INBOUND_TAG`, `XS_VLESS_SERVICE`, and `XS_SING_BOX_BIN`. Agent startup reconciles the dedicated inbound/interface against its root-only lease state and removes unmanaged legacy credentials. VLESS updates are written to a same-directory temporary file, checked with `sing-box check`, atomically replaced, and then reloaded; a reload failure restores the previous JSON.

Website and Admin:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/admin
```

The Admin page uses password-only login and stores an HttpOnly session cookie. Set `ADMIN_PASSWORD` locally before using `/admin`.

For production, set `ADMIN_PASSWORD`, `ADMIN_SESSION_SECRET`, and `CORS_ALLOW_ORIGINS` from the deployment environment, and replace the seeded placeholder payment QR URLs in Admin before accepting orders.

Quick checks:

```bash
curl http://127.0.0.1:8000/health
curl -c /tmp/xingsui-admin.cookie -X POST http://127.0.0.1:8000/admin/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'password=CHANGE_ME_ADMIN_PASSWORD'
curl -b /tmp/xingsui-admin.cookie http://127.0.0.1:8000/admin/dashboard
curl -X POST http://127.0.0.1:8000/auth/email/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"xingsui123"}'
curl http://127.0.0.1:8000/promotions/active
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/email/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","password":"xingsui123"}' | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
curl http://127.0.0.1:8000/usage/authorize -H "Authorization: Bearer $TOKEN"
curl http://127.0.0.1:8000/vpn/authorize -H "Authorization: Bearer $TOKEN" -H "X-Xingsui-Platform: android"
curl http://127.0.0.1:8000/vpn/config -H "Authorization: Bearer $TOKEN" -H "X-Xingsui-Platform: android"
curl -X POST http://127.0.0.1:8000/usage/report \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"tunnel_name":"demo","rx_bytes_delta":1048576,"tx_bytes_delta":1048576}'
curl http://127.0.0.1:8000/invitations/me -H "Authorization: Bearer $TOKEN"
curl -X POST http://127.0.0.1:8000/withdrawals \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount_cents":1000,"account_type":"alipay","account_masked":"user@example.com"}'
curl -X POST http://127.0.0.1:8000/orders \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"plan_id":"plan_month","promotion_id":"promo_18_month","pay_channel":"wechat"}'
curl -b /tmp/xingsui-admin.cookie http://127.0.0.1:8000/admin/orders?status=pending_confirm
```

Invitation cashback rule in the current MVP: a new user may enter an inviter's code during registration. When the invitee's first order is manually confirmed, the inviter receives 1000 cents of cashback balance. Later orders from the same invitee do not repeat the reward.

Withdrawal rule: the App only shows withdrawable balance. Users can either submit an Alipay account for manual withdrawal review, or copy/add customer-service WeChat `xinsuui` to request withdrawal manually.

This development version persists users, finite sessions, plans, promotions, payment QR settings, orders, invitations, cashback balances, withdrawal requests, VIP state, legacy traffic counters (never used for VPN authorization), nodes, and VPN leases in PostgreSQL. Production deployment should apply the checked-in SQL migrations before starting the new application version.
