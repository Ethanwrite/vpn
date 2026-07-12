# 星隧 VPN — 架构与完整业务逻辑文档

> 面向维护者与后续开发的权威参考。涵盖系统组成、完整业务流程、协议与抗封策略、
> 部署方式、数据模型，以及**后续加需求时必须注意的事项**。
> 凭证一律不写入本文，只注明存放位置。最后更新：2026-07-12。

## 目录
1. [概览](#1-概览)
2. [组件架构](#2-组件架构)
3. [服务器与网络拓扑](#3-服务器与网络拓扑)
4. [完整业务逻辑](#4-完整业务逻辑)
5. [协议与抗 GFW 策略](#5-协议与抗-gfw-策略)
6. [数据模型](#6-数据模型)
7. [部署流程](#7-部署流程)
8. [安全模型](#8-安全模型)
9. [⚠️ 后续开发注意事项](#9-后续开发注意事项必读)

---

## 1. 概览

星隧（Xingsui）是一套面向中国大陆用户的商业 VPN。特点：

- **统一账号**：官网、Android、Windows 用同一邮箱/密码登录，账户、VIP、流量状态全部由控制面后端统一下发。
- **两种协议**：Android 走 **AmneziaWG (awg)**；Windows 走 **VLESS + Reality + Vision**（内置 sing-box）。第三方客户端（Clash/mihomo）通过**订阅链接**导入 VLESS 节点。
- **免费 + VIP**：新账号 30MB 免费体验流量；VIP 由管理员在后台手动确认订单后开通。
- **节点动态下发**：客户端**不硬编码**节点，全部通过 API 获取，并领取**短期租约**（≤1 小时）。

仓库：`https://github.com/Ethanwrite/vpn`（分支 `main`）。

---

## 2. 组件架构

| 组件 | 技术栈 | 目录 | 说明 |
|---|---|---|---|
| 控制面后端 | Python / FastAPI + SQLAlchemy | `amneziawg-android/backend` | API + 官网 SPA + 管理后台 + 支付页，单一 FastAPI app |
| 数据库 | PostgreSQL 16 | （容器） | 用户/订单/节点/设备/邀请/提现/订阅审计 |
| 反向代理 | Caddy 2 | `deploy/control-plane/Caddyfile` | 自动 TLS，反代到 api（TCP 443；UDP 443 已让给大阪 awg） |
| Android 客户端 | Kotlin / AmneziaWG | `amneziawg-android`（`ui/.../xingsui`） | awg 协议；一键连接=智能选节点 |
| Windows 客户端 | Tauri (Rust) + React/TS | `xingsui-windows` | VLESS/Reality/Vision（sing-box + wintun） |
| 边缘节点 Agent | Python | `deploy/edge-node/agent.py` | 通过 `awg set` / sing-box 动态增删 user/peer，上报心跳，管理租约 |
| 新加坡中转 | nftables + relay service | `deploy/relay` | 大阪→新加坡 UDP/TCP 中转落地 |

**后端子模块**（`backend/app/`）：`main.py`（全部路由/鉴权中间件/节点调度/租约签发）、`site_page.py`（官网 SPA）、`payment_page.py`（支付页）、`admin_page.py`（管理后台）、`payment_config.py`（收款码/深链）、`node_service.py`（节点评分与配置渲染）、`db_models.py`/`database.py`（ORM）。

**Agent 关键函数**：`add_peer/remove_peer`（awg）、`add_vless_user/remove_vless_user`（sing-box）、`register_lease`（本地租约，`expires_at`）、`reconcile_*`（清理不在租约表里的 user/peer）、`static_vless_uuids()`（保留订阅永久 user）。

---

## 3. 服务器与网络拓扑

| 主机 | 角色 | 关键监听 |
|---|---|---|
| `212.50.232.111` | **主服务器**：控制面（Postgres+API+Caddy）、大阪 awg0、大阪 VLESS(8443)、xingsui-agent、新加坡 VLESS 中转入口(10444)、awg 心跳汇聚 | TCP 443(Caddy)、TCP 8443(大阪 VLESS)、UDP 443→51820(大阪 awg REDIRECT)、TCP 10444(→SG 中转) |
| `172.86.91.81` | 美国达拉斯边缘节点（awg + VLESS 8443） | 443、8443 |
| `144.172.97.191` | 美国犹他边缘节点（awg + VLESS 8443） | 443、8443 |
| `61.13.236.140` | 新加坡节点（VLESS 10443，经主服务器中转；SSH 端口 18827） | 10443 |

**端口策略（抗封关键）**：国内移动网络常封高位 UDP 端口，能稳定连通的都走 **443** 或伪装良好的 Reality。
- 大阪 awg：awg0 实际听 51820，主服务器 nftables `REDIRECT udp/443→51820`（写在 `/etc/amnezia/amneziawg/awg0.conf` PostUp/PostDown），并**关闭了 Caddy HTTP/3** 腾出 UDP 443。
- VLESS：8443 TCP（新加坡经主服务器 10444 中转到 10443）。
- **新加坡只能经大阪（主服务器）中转连接**：客户端连 `212.50.232.111:10444`，主服务器转发到 `61.13.236.140:10443`。

---

## 4. 完整业务逻辑

### 4.1 认证
`POST /auth/email/register|login` → 返回 `access_token`（Bearer）。客户端本地保存会话；会话在 DB `auth_sessions`，有独立过期时间。

### 4.2 免费流量 vs VIP（连接授权，核心规则）
1. 新账号固定 **30MB** 免费流量（`FREE_TRAFFIC_QUOTA_BYTES`）。
2. 非 VIP 只要**剩余流量 > 0** 就允许连接（`reason=free_trial`）。
3. 用完返回 `free_traffic_exhausted`；前端提示「30MB 免费流量已用完，请开通 VIP 后继续使用」。
4. VIP 有效则**不扣**免费流量（`reason=vip_active`）；VIP 过期 `reason=vip_expired`。

实现：`main.py::build_entitlement`。`/vpn/authorize`、`/vpn/config`、`/vpn/nodes/{id}/config`、`/usage/report` 均据此判定 `allowed`。两个客户端都以 `entitlement.allowed` 为准，**不再要求 `vip_status==active`**（历史上误改成 VIP-only 的 bug 已修）。

### 4.3 VPN 连接
**Android（awg）**：`GET /vpn/authorize`（查授权）→ 一键连接 `GET /vpn/config`（后端 `select_pool_node` 按权重/在线/负载选最优节点，Agent 远程签发 peer，返回带 **5 分钟租约**的 awg 配置）；手动选节点 `GET /vpn/nodes/{id}/config`。连接后周期 `POST /usage/report` 上报流量增量 → 扣减免费流量 + 续租；`allowed=false` 即断开。

**Windows（VLESS）**：`GET /vpn/nodes/{id}/config`（仅 `protocol=vless` 节点）→ 后端 `provision_vless_device` 生成 uuid、调 Agent `agent_add_vless_user` 动态注册到 sing-box、返回 Reality 参数。客户端 sing-box 建链。校验在 `src-tauri/src/vless.rs`，续租在 `stats.rs`。

### 4.4 支付 → 开通 VIP
1. 官网选套餐 → 跳转 `/payment?plan_id=...`。
2. `/payment` 显示微信/支付宝深链按钮 + **收款码兜底**（`https://xingsui.org/pay/{wechat,alipay}.jpg`）。
3. 点「我已完成支付」→ `POST /orders` → `POST /orders/{id}/paid` → 订单 `pending_confirm`，前端弹「订单已提交成功…」。
4. 管理员 `POST /admin/orders/{id}/confirm` → 用户 VIP 激活（按套餐天数）。`reject` 亦可。

### 4.5 订阅链接（VIP，供第三方客户端）
- VIP 在用户中心「导出订阅链接」→ `GET /user/subscription-link` → 返回 `https://xingsui.org/api/sub?token=...`。
- Token 为 **HMAC-SHA256** 签名（`user_id:version`，不可枚举）；**限频** 5次/60s（重置 1次/10min）；审计日志对 token **脱敏**；全程 **HTTPS**。
- 第三方拉取 `GET /sub?token=...` → 返回 Clash YAML（节点来自 `subscription-links.txt`）。YAML 首个节点是「⏳ 会员到期 …」信息节点，让用户在客户端节点列表直接看到到期时间。
- 非 VIP 点导出 → 友好提示「开通 VIP 后即可导出订阅链接」；`/sub` 对无效 token 返回 401，非 VIP 返回对应 code。泄露可「重置」（`POST /user/subscription-link/reset`，version+1，旧链接立即失效）。

### 4.6 管理后台
`/admin`（`ADMIN_SESSION` cookie：`Secure`+`SameSite=strict`+`path=/admin`）。功能：概览、订单确认/拒绝、授/撤 VIP、**删除用户**（`DELETE /admin/users/{id}`，级联清理订单/设备/邀请/提现/会话/审计并撤销节点 peer）、节点增删改、收款码配置、促销、财务提现。
所有写操作额外受 **`ADMIN_WRITES_ENABLED`** 开关控制（见 §9）。

---

## 5. 协议与抗 GFW 策略

**Android — AmneziaWG**：在 WireGuard 上加混淆参数（`Jc/Jmin/Jmax/S1/S2/H1-H4`）抗 DPI。客户端 **MTU=1280**（家宽/PPPoE 路径 1420 过大 → 握手成功但数据丢包、短连即断）。

**Windows / 订阅 — VLESS + Reality + Vision**：
- **SNI 用自家域名 `xingsui.org`**（解析到主服务器）。原因：GFW 有 **SNI↔目标 IP 一致性检测**，借用大厂域名（apple.com 等）因 IP 不属于该大厂反而更易被封；`xingsui.org` 443 有真实 Caddy 站点、国内可访问（官网能打开），既 IP 一致又能做 Reality handshake 兜底。**不要改用大厂域名。**
- handshake 兜底：主服务器 `127.0.0.1:443`，边缘节点 `xingsui.org:443`。
- **flow = `xtls-rprx-vision`**，三处必须一致：sing-box 服务端每个 user、DB `params_json.VlessFlow`、订阅链接 `flow=`。Agent 发放动态 user 的 flow 由 `/etc/xingsui/agent.env` 的 `XS_VLESS_FLOW` 控制。
- pbk/sid 是每台服务器的 Reality 密钥对，与 SNI 无关；**DB `VlessPublicKey/VlessShortId` 必须与 sing-box 实际密钥一致**（见 §9）。

---

## 6. 数据模型（关键表）

- **users**：id、email、password_(salt/hash)、invite_code、`invited_by_user_id`（自引用）、`vip_status`/`vip_expired_at`、`cash_balance_cents`、`free_traffic_quota_bytes`/`_used_bytes`、`status`、`subscription_token_*`。
- **vpn_nodes**：id、name、region、`protocol`(awg/vless/dual)、enabled、weight、`vip_only`、max_clients、endpoint、`agent_host`/`agent_port`、awg 字段(server_public_key/allowed_ips/dns/mtu/params_json)、VLESS 字段(在 params_json：VlessHost/VlessPort/VlessPublicKey/VlessShortId/VlessServerName/VlessFlow/VlessUUID)。
- **vpn_node_health**：node_id、last_heartbeat_at、peer_count、cpu_load（节点在线/负载）。
- **vpn_devices**：每个租约一行（user/node/protocol/lease_id/lease_expires_at/vless_uuid/status）。
- **orders / vip_plans / promotion_activities**：下单与套餐。
- **invitations / withdrawals**：邀请返现与提现。
- **auth_sessions / subscription_audit_logs / node_request_nonces**：会话、订阅审计、Agent 防重放。

引用 `users.id` 的表（删用户需按序清理）：auth_sessions、orders、vpn_devices、withdrawals、subscription_audit_logs、invitations(inviter/invitee)、users.invited_by_user_id。

---

## 7. 部署流程

### 7.1 后端（直接同步 + 重建镜像，**不走 CI**）
镜像 `xingsui-backend:latest` 从 `/opt/xingsui/backend` 构建（代码打进镜像，非挂载）：
```bash
scp app/*.py root@212.50.232.111:/opt/xingsui/backend/app/
ssh root@212.50.232.111 'cd /opt/xingsui/deploy/control-plane && docker compose build api && docker compose up -d api'
```
仓库 `amneziawg-android/backend` 与服务器 `/opt/xingsui/backend` 需保持一致。纯 env 改动只需 `docker compose up -d api`。

### 7.2 Android（本地构建 + 签名 + 上传）
```bash
# 环境见 amneziawg-android/docs/android-build.md
./gradlew :ui:assembleRelease -PxingsuiReleaseApiBaseUrl=https://xingsui.org   # 签名走 XINGSUI_KEYSTORE_* 环境变量
../scripts/upload-android-apk.sh    # 校验版本号后 scp 到 /opt/xingsui/download/xingsui.apk
```
之后同步 `.env` 的 `APP_VERSION_CODE/NAME` 并重启 api，App 内更新检查才提示。

### 7.3 Windows（GitHub Actions 构建 + 脚本部署）
推送 `xingsui-windows/**` 触发工作流 → 产出 NSIS/MSI artifact → 下载 → `scripts/upload-windows-installer.sh` 部署到 `/opt/xingsui/download/xingsui-windows-setup.exe`。当前 CI 工作流是 `windows-client.yml`（更严格的 `build.yml` 在 `backup/local-main-b0d584e` 分支，启用需带 `workflow` scope 的 token）。

---

## 8. 安全模型

- **短租约**：Agent 只发放 **≤1 小时** 租约（`MAX_LEASE_SECONDS`），周期 reconcile 清理过期/无租约的 user/peer。这是"不给长期凭据"的核心。
- **订阅永久 user**（与短租约冲突的例外）：写入各节点 `/etc/xingsui/static-vless-uuids.txt`，Agent 的 `static_vless_uuids()` 在 reconcile 时保留。
- **订阅 token**：HMAC 签名、限频、审计脱敏、可重置。
- **Agent 鉴权**：Agent Token + nonce 防重放（`node_request_nonces`）。
- **凭证位置（不含明文）**：Android 签名 `xingsui-release.jks`(别名 `xingsui-release`)+`xingsui-release-password.txt`(CN=Xingsui)；生产 env `/opt/xingsui/deploy/control-plane/.env`；节点 Agent Token `/etc/xingsui/agent.env`；明文清单 `markdown/a.markdown`（**勿提交仓库**）；数据库备份 `~/vpn-backups`。

---

## 9. ⚠️ 后续开发注意事项（必读）

### 运维开关 / 一致性
- **`ADMIN_WRITES_ENABLED`**：为非 `true` 时中间件拦截**所有**管理写操作（确认订单/授 VIP/删用户），返回 503「Admin writes are temporarily disabled during security review」。**管理员任何操作报 503 先查这个开关**（在生产 `.env`）。
- **大阪 UDP 443 依赖**：①Caddy 关闭 HTTP/3（`docker-compose.yml` 不发布 `443:443/udp`）②awg0.conf 的 REDIRECT PostUp。从仓库重新部署 Caddy 或重装大阪节点后务必确认这两点未被还原，否则大阪失联。
- **收款码域名**：`PAYMENT_WECHAT_QR_URL`/`PAYMENT_ALIPAY_QR_URL` 必须指向 `xingsui.org/pay/*.jpg`（`/pay/` 只在 xingsui.org 生效）。
- **订阅节点文件权限**：`/opt/xingsui/download/subscription-links.txt` 必须能被 API 容器用户（`appuser` gid 999）读取，否则 `/sub` 返回 500。设为 `640 root:999`。**手动改该文件后重新 `chown root:999 && chmod 640`**。

### VLESS / Reality（最容易踩坑）
- **DB 的 pbk/sid 必须与 sing-box 实际密钥一致**：任何一次 Reality 密钥轮换，必须**同时**更新 sing-box 配置和 DB 的 `VlessPublicKey`/`VlessShortId`/`VlessHost`，否则动态客户端（Windows/App）握手失败报「账户状态同步失败」，而订阅（链接里硬编码正确密钥）却仍正常——极具迷惑性。验证方法：对该节点 `/vpn/nodes/{id}/config` 取配置，在美国机器起 sing-box 客户端跑通。
- **节点内部一致性**：`VlessHost:VlessPort` 必须指向**实际提供该 VLESS 服务的服务器**，且与该节点 `agent_host`（发放 user 的地方）落到同一台（新加坡例外：入口是主服务器中转口 10444，user 发到新加坡 agent）。历史 bug：node-144 的 VlessHost 误指主服务器而 agent 在犹他 → 认证失败。
- **flow 三处一致**：sing-box user、DB `VlessFlow`、订阅链接 `flow=` 都要 `xtls-rprx-vision`。
- **SNI 保持 `xingsui.org`**，不要改大厂域名（见 §5）。

### 客户端 vs 服务端
- **绝大多数配置改动是服务端驱动、无需重新打包 App**：节点、SNI、flow、MTU、pbk/sid 都来自后端/DB，客户端下次连接自动生效。只有客户端 UI/逻辑（如提示文案、页面）改动才需重新构建（Android 本地打包、Windows 走 CI）。
- **两端业务规则一致**：免费流量/VIP 判定以后端 `entitlement.allowed` 为准；客户端错误提示要按 `reason`（`free_traffic_exhausted`/`vip_expired`/`vip_required`）映射友好文案（Android 在 `XingsuiVipGate`，Windows 在 `api.rs::friendly_reason_message`）。

### 其它
- **GitHub token 无 `workflow` scope**：无法通过 API 改 `.github/workflows/`。
- **测试账号**统一用 `@xingsuitest.dev` 邮箱，便于批量清理（删除逻辑同 `DELETE /admin/users/{id}`）。
- **SSH 限速**：短时间大量 SSH 连接会触发 fail2ban 临时封本机 IP（约 10 分钟自解），表现为 `kex_exchange_identification: Connection closed` 但网站正常。
- **后端改动记得同步仓库**：`/opt/xingsui/backend` 是构建源，改完后把对应文件同步回 `amneziawg-android/backend` 并提交，避免漂移。

---

## 10. 当前已部署版本（2026-07-12）

| 端 | 版本 | 状态 |
|---|---|---|
| 后端 | — | 免费流量规则、支付、删用户、订阅、VLESS(xingsui.org+Vision)、pbk/sid 修正均已上线 |
| Android | `2.0.19 (29)` | 已签名上传官网；后端播报 29 |
| Windows | `1.0.20` | CI 构建；含免费流量友好提示；4 个节点均可用 |
| 节点 | 大阪 / 达拉斯 / 犹他 / 新加坡(经大阪中转) | VLESS 全部 xingsui.org SNI + Vision；awg MTU 1280 |

> 回归建议：非 VIP 真机走 30MB→用尽提示→下单→管理员确认→VIP；VIP 逐个切换 4 个节点确认可连；订阅导入 Clash 确认 4 节点 + 到期节点。
