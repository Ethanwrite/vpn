# Xingsui Commercial Product Model

## Product scope

Xingsui combines native Android and Windows clients with a FastAPI control plane, PostgreSQL persistence, an administration console, a public website, membership billing, invitations, and managed VPN edge nodes.

The clients retain protocol-specific tunnel engines while delegating identity, entitlement, node selection, and credential lifecycle to the control plane. Product pages are isolated under the `org.amnezia.awg.xingsui` package so upstream AmneziaWG code remains maintainable.

## Membership and payments

| Plan | Term | Price |
| --- | --- | --- |
| Monthly | 30 days | CNY 18 |
| Quarterly | 90 days | CNY 48 |
| Annual | 365 days | CNY 158 |

WeChat and Alipay orders use operator-managed QR codes and manual confirmation. A confirmed first purchase can award the inviter CNY 10 in cashback. Withdrawals are reviewed manually through Alipay account details or customer support.

All prices, promotions, order transitions, and membership expiry dates are authoritative on the server. Clients display this state but do not calculate or grant entitlement locally.

## Access policy

- New accounts receive a server-measured 60 MB free allowance.
- Active members receive unlimited service within the product's acceptable-use policy.
- Tunnel credentials are user- or device-specific, short-lived, revocable, and capped at one hour.
- Third-party subscriptions are available only to active members and expire with membership.
- Disabled or unhealthy nodes are excluded from normal scheduling.

## Client strategy

The Android application uses `com.xingsui.vpn` as its application ID while retaining upstream native package names to avoid destabilizing JNI and the native build chain. The Windows application uses Tauri, React, sing-box, and Wintun. Both clients consume the same account, membership, and node-health state.

## Operational and compliance requirements

Before commercial operation, verify all required business licenses, payment-channel terms, privacy disclosures, user agreements, server-use policies, retention limits, and incident-response procedures for every jurisdiction in which the service is offered. Marketing claims must remain accurate and should emphasize privacy, secure remote work, and reliable connectivity.
