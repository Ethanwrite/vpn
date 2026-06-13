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
- automatic VPN node config provisioning through `/vpn/config`
- 30MB free trial traffic for logged-in non-VIP users
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

Tunnel startup is blocked in the Android client unless the user is logged in and `/vpn/authorize` returns an active entitlement. Active VIP users are allowed while `vip_expired_at` is in the future. Non-VIP users may use the 30MB free traffic quota. The App fetches `/vpn/config` on first connect, auto-creates the local `xingsui` tunnel, and reports tunnel usage to `/usage/report` while the VPN is running.

VPN node provisioning can run in two modes:

```env
# Production auto-provisioning with a local wg0 interface
VPN_AUTO_PROVISION=true
VPN_WG_INTERFACE=wg0
VPN_SERVER_PUBLIC_KEY=your_server_public_key
VPN_ENDPOINT=xingsuico.com:51820
VPN_CLIENT_NETWORK=10.66.66.0/24
VPN_DNS=1.1.1.1
VPN_ALLOWED_IPS=0.0.0.0/0

# Local/simple fallback, returns the same static config to all users
VPN_AUTO_PROVISION=false
VPN_DEFAULT_CONFIG="[Interface]\\nPrivateKey = ..."
```

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
curl http://127.0.0.1:8000/vpn/authorize -H "Authorization: Bearer $TOKEN"
curl http://127.0.0.1:8000/vpn/config -H "Authorization: Bearer $TOKEN"
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

This development version now persists users, sessions, plans, promotions, payment QR settings, orders, invitations, cashback balances, withdrawal requests, VIP state, and free trial traffic counters in PostgreSQL. Production deployment should replace automatic table creation with Alembic migrations.
