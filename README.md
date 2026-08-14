# Xingsui VPN Platform

Xingsui is a production VPN service with managed Android and Windows clients, a FastAPI control plane, short-lived device credentials, subscription delivery, billing, and automated edge-node operations.

## Production topology

| Role | Location | Public address | Service endpoints |
| --- | --- | --- | --- |
| Control plane and relay | Hong Kong | `64.90.24.84` | HTTPS control plane; Singapore relay on UDP `4500` and TCP `10444` |
| Edge node | Utah, US | `144.172.97.191` | AmneziaWG UDP `443`; VLESS Reality TCP `8443` |
| Edge node | Sydney, AU | `144.172.65.152` | AmneziaWG UDP `443`; VLESS Reality TCP `8443` |
| Edge node | Singapore | `61.13.236.31` | AmneziaWG UDP `51820`; VLESS Reality TCP `10443`; published through the Hong Kong relay |

The control plane is mirrored at `xingsui.org` and `xingsuico.com`. Legacy Japan, Dallas, and previous Singapore nodes are disabled and are not included in scheduling or subscription output.

## Components

- `amneziawg-android/`: Android client and the FastAPI control-plane source.
- `amneziawg-android/backend/`: API, website, administration console, membership, orders, subscriptions, and node management.
- `xingsui-windows/`: Tauri and React Windows client using managed VLESS Reality leases.
- `deploy/`: control-plane, edge-agent, and Hong Kong relay deployment assets.
- `docs/`: production architecture and operational invariants.
- `scripts/`: build and release automation.

## Security model

- VPN access is authorized by server-side account and membership state.
- Device credentials are short-lived and bounded by membership expiry.
- Edge agents authenticate control-plane requests and reconcile managed peers or UUIDs.
- Subscription tokens are stored as hashes and can be revoked without changing account credentials.
- Secrets, private keys, payment assets, databases, and release artifacts are intentionally excluded from Git.

## Android build

```bash
cd amneziawg-android
./gradlew :ui:assembleRelease \
  -PxingsuiReleaseApiBaseUrl=https://xingsui.org
```

## Backend development

```bash
cd amneziawg-android/backend
python -m venv .venv
. .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

Production deployment assets are under `deploy/control-plane/`. Copy `.env.example` to `.env`, provide deployment-specific secrets, and start the stack with `docker compose up -d --build`.

## Windows build

Windows releases require an MSVC build environment, the pinned sing-box executable, and `wintun.dll` in the paths documented by the build script.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1
```

See [the production architecture](docs/ARCHITECTURE.md) for the complete design and operating model.
