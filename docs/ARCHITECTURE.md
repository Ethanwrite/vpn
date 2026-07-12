# 星隧 VPN — 项目架构与注意事项

> 面向维护者的总览文档。记录系统组成、数据流、部署方式与关键风险点。
> 最后更新：2026-07-11。凭证一律不写入本文，仅注明存放位置。

---

## 1. 概览

星隧（Xingsui）是一套商业 VPN 服务，由**控制面后端 + 两个客户端 + 多个边缘节点**组成：

- 用户用同一邮箱/密码登录官网、Android、Windows，账户与 VIP/流量状态全部由后端统一下发。
- 免费用户有 30MB 体验流量；VIP 由管理员在后台手动确认订单后开通。
- 节点信息**全部通过 API 动态下发**，客户端不硬编码节点。

代码仓库：`https://github.com/Ethanwrite/vpn`（分支 `main`）。

---

## 2. 组件架构

| 组件 | 技术栈 | 目录 | 说明 |
|---|---|---|---|
| 控制面后端 | Python / FastAPI + SQLAlchemy | `amneziawg-android/backend` | API + 官网 SPA + 管理后台 + 支付页，全在一个 FastAPI app |
| 数据库 | PostgreSQL 16 | （容器） | 用户、订单、节点、设备、邀请、提现等 |
| 反向代理 | Caddy 2 | `deploy/control-plane/Caddyfile` | 自动 TLS，反代到 api |
| Android 客户端 | Kotlin / AmneziaWG | `amneziawg-android`（`ui/.../xingsui`） | 协议 **AmneziaWG (awg)**；一键连接=智能选节点 |
| Windows 客户端 | Tauri (Rust) + React/TS | `xingsui-windows` | 协议 **VLESS**（内置 sing-box + wintun） |
| 边缘节点 Agent | Python | `deploy/edge-node/agent.py` | 通过 `awg set` 动态增删 peer，上报心跳 |
| 新加坡中转 | nftables 转发 | `deploy/relay` | 大阪→新加坡 UDP 中转落地 |

**后端内部子模块**（`backend/app/`）：
- `main.py` — 所有 API 路由、鉴权中间件、节点调度、租约签发。
- `site_page.py` / `payment_page.py` / `admin_page.py` — 官网、支付页、管理后台（内联 HTML/JS）。
- `payment_config.py` — 微信/支付宝深链与收款码 URL。
- `node_service.py` — 节点评分与配置完整性校验。
- `db_models.py` / `database.py` — ORM 模型与初始化。

---

## 3. 服务器与网络拓扑

| 主机 | 角色 | 关键监听 |
|---|---|---|
| `212.50.232.111` | **主服务器**：控制面（Postgres+API+Caddy）、大阪 awg0 就地节点、xingsui-agent、新加坡中转、VLESS 主 | TCP 443（Caddy）、UDP 443→51820（大阪 awg，REDIRECT） |
| `172.86.91.81` | 美国达拉斯边缘节点 | awg / VLESS on 443 |
| `144.172.97.191` | 美国犹他边缘节点 | awg / VLESS on 443 |
| `61.13.236.140:18827` | 新加坡节点 | awg on 51823（经主服务器中转） |

**节点端口策略（重要）**：国内移动网络常封锁高位 UDP 端口，因此能稳定连通的节点都走 **UDP 443**。
- 美国节点：awg 直接监听 443。
- 大阪：awg0 实际监听 51820，主服务器加 nftables `REDIRECT udp/443 → 51820`（规则写在 `/etc/amnezia/amneziawg/awg0.conf` 的 PostUp/PostDown），并**关闭了 Caddy HTTP/3**（腾出 UDP 443）。DB 中 `node-osaka.endpoint = 212.50.232.111:443`。
- 新加坡仍是高位端口 `51823`，移动网可能连不上——如需可比照大阪改 443。

---

## 4. 核心业务规则

**免费流量 vs VIP（连接授权）：**
1. 新账号固定 **30MB** 免费流量。
2. 非 VIP 只要**剩余流量 > 0** 就允许连接。
3. 用完返回 `free_traffic_exhausted`，前端提示「30MB 免费流量已用完，请开通 VIP 后继续使用」。
4. VIP 有效则**不扣减**免费流量。

后端实现见 `main.py::build_entitlement`；`/vpn/authorize`、`/vpn/config`、`/usage/report` 都据此判定 `allowed`。
两个客户端都以 `entitlement.allowed` 为准，**不再要求 `vip_status==active`**（这是历史上误改成 "VIP-only" 的 bug，已修复）。

**VIP 开通：** 用户下单 → 手动付款 → 提交订单（`pending_confirm`）→ 管理员在 `/admin` 确认 → VIP 激活（按套餐天数）。

---

## 5. 关键数据流

### 5.1 认证
`POST /auth/email/register|login` → 返回 `access_token`（Bearer）。客户端本地保存会话。

### 5.2 VPN 连接（Android，awg）
1. `GET /vpn/authorize` → 返回 entitlement（allowed / reason / 剩余流量）。
2. 一键连接（智能）：`GET /vpn/config` → 后端 `select_pool_node` 选最优节点，Agent 远程签发 peer，返回带 **5 分钟租约**的 awg 配置。
   手动选节点：`GET /vpn/nodes/{id}/config`。
3. 连接后周期性 `POST /usage/report` 上报流量增量 → 后端扣减免费流量并续租；`allowed=false` 时客户端断开。

### 5.3 VPN 连接（Windows，VLESS）
`GET /vpn/nodes/{id}/config`（仅 `protocol=vless` 节点）→ 客户端用 sing-box 建链。校验逻辑在 `src-tauri/src/vless.rs`、续租在 `stats.rs`。

### 5.4 支付 → 开通
1. 官网选套餐 → 跳转 `/payment?plan_id=...`。
2. `/payment` 显示微信/支付宝深链按钮 + **收款码兜底**（`https://xingsui.org/pay/{wechat,alipay}.jpg`）。
3. 点「我已完成支付」→ `POST /orders` → `POST /orders/{id}/paid` → 订单变 `pending_confirm`，前端弹「订单已提交成功…」。
4. 管理员 `POST /admin/orders/{id}/confirm` → 用户 VIP 激活。

### 5.5 订阅链接（VIP）
- VIP 在用户中心「导出订阅链接」→ `GET /user/subscription-link` → 返回 `https://xingsui.org/api/sub?token=...`。
- Token 为 HMAC-SHA256 签名（`user_id:version`，不可枚举）；限频 5 次/60s（重置 1 次/10min）；审计日志对 token 脱敏；全程 HTTPS。
- 第三方客户端拉取 `GET /sub?token=...` → 返回 Clash YAML（节点来自 `SUBSCRIPTION_PROXY_LINKS_PATH`，默认 `/opt/xingsui/download/subscription-links.txt`）。YAML 首个节点为「⏳ 会员到期 …」信息节点，用户在客户端节点列表可直接看到 VIP 到期时间。
- 非 VIP 点击导出 → 前端友好提示「开通 VIP 后即可导出订阅链接」并跳转套餐页；`/sub` 对无效/过期 token 返回 401，对非 VIP 返回对应 code。
- 泄露可「重置」：`POST /user/subscription-link/reset` 递增 version，旧链接立即失效。

### 5.6 管理后台
`/admin`（`ADMIN_SESSION` cookie，`Secure`+`SameSite=strict`+`path=/admin`）。
写操作（POST/PUT/PATCH/DELETE）额外受 `ADMIN_WRITES_ENABLED` 开关控制（见 §7）。
用户管理支持：授/撤 VIP、**删除用户**（`DELETE /admin/users/{id}`，级联清理订单/设备/邀请/提现/会话/审计并撤销节点 peer）。

---

## 6. 部署流程

### 6.1 后端（直接同步 + 重建镜像，**不走 CI**）
后端镜像 `xingsui-backend:latest` 从 `/opt/xingsui/backend` 构建（**代码打进镜像，非挂载**）。发布步骤：
```bash
# 1) 同步改动到服务器源码目录
scp backend/app/*.py root@212.50.232.111:/opt/xingsui/backend/app/
# 2) 重建并重启
ssh root@212.50.232.111 'cd /opt/xingsui/deploy/control-plane && docker compose build api && docker compose up -d api'
```
> 仓库 `amneziawg-android/backend` 与服务器 `/opt/xingsui/backend` 需保持一致（当前为逐文件同步）。纯 env 改动只需 `docker compose up -d api` 重启，无需重建。

### 6.2 Android（本地构建 + 签名 + 上传）
```bash
# 见 amneziawg-android/docs/android-build.md 的环境变量
./gradlew :ui:assembleRelease -PxingsuiReleaseApiBaseUrl=https://xingsui.org \
  # 签名通过环境变量传入：XINGSUI_KEYSTORE_FILE / _PASSWORD / _KEY_ALIAS / _KEY_PASSWORD
../scripts/upload-android-apk.sh   # 校验版本号后 scp 到 /opt/xingsui/download/xingsui.apk
```
上传后需同步 `.env` 的 `APP_VERSION_CODE/NAME` 并重启 api，App 内更新检查才会提示。

### 6.3 Windows（GitHub Actions 构建 + 脚本部署）
推送到 `main`（改动 `xingsui-windows/**`）触发工作流 → 产出 NSIS/MSI → 下载 artifact → `scripts/upload-windows-installer.sh` 部署到 `/opt/xingsui/download/xingsui-windows-setup.exe`。
> 当前 origin 上的工作流是 `windows-client.yml`。仓库另有更严格的 `build.yml`（固定 sing-box/wintun 的 SHA256、cargo fmt/test、危险回退扫描），保存在 `backup/local-main-b0d584e` 分支；启用它需要带 **`workflow` scope** 的 GitHub token。

---

## 7. 重点注意事项 / 风险

### 运维开关
- **`ADMIN_WRITES_ENABLED`（关键）**：为 `false` 时，中间件拦截**所有**管理写操作（确认订单、授 VIP、删用户），返回 503「Admin writes are temporarily disabled during security review」。若管理员点任何操作报 503，先查这个开关。当前为 `true`。
- **大阪 UDP 443**：依赖 ①Caddy 关闭 HTTP/3（`docker-compose.yml` 不再发布 `443:443/udp`）②awg0.conf 的 REDIRECT PostUp。若从仓库重新部署 Caddy 或重装大阪节点，务必确认这两点不被还原，否则大阪失联。
- **收款码域名**：`PAYMENT_WECHAT_QR_URL` / `PAYMENT_ALIPAY_QR_URL` 必须指向 `xingsui.org/pay/*.jpg`（`/pay/` 路由只在 xingsui.org 生效，xingsuico.com 会 404）。
- **订阅节点文件权限**：`/opt/xingsui/download/subscription-links.txt` 必须能被 API 容器用户（`appuser`，gid 999）读取，否则 `/sub` 返回 500。当前设为 `640 root:999`（不对外可读，且该文件未被 Caddy 静态暴露）。**手动更新该文件后请重新 `chown root:999 && chmod 640`**，不要留成 `600 root`。
- **VLESS Reality（GFW 相关）**：TCP 8443（新加坡 10443，经主服务器 10444 中转）。SNI/handshake 用**自家域名 `xingsui.org`**（解析到主服务器，满足 GFW 的 SNI-目标 IP 一致性检测；主服务器 443 的 Caddy 提供真实站点做 handshake 兜底）。**不要**改用大厂域名（如 apple.com/microsoft.com）——SNI 与 IP 不一致反而更易被封。协议栈：VLESS + Reality + **Vision（`xtls-rprx-vision`）**，服务端每个 user、DB `VlessFlow`、订阅链接 `flow=` 三处必须一致。
- **动态 vs 订阅用户**：节点 Agent 只发放**≤1 小时**短租约（`MAX_LEASE_SECONDS`），并周期性 reconcile 清理不在租约表里的 vless user。因此长期订阅需要**永久 user**：写进各节点 `/etc/xingsui/static-vless-uuids.txt`（agent 的 `static_vless_uuids()` 会在 reconcile 时保留），并手动加进 sing-box 的 users。Agent 发放动态 user 的 flow 由 `XS_VLESS_FLOW`（在 `/etc/xingsui/agent.env`）控制，须为 `xtls-rprx-vision`。
- **awg MTU**：各 awg 节点 MTU 设为 **1280**（家宽/Wi-Fi PPPoE 路径过大的 1420 会导致握手成功但数据丢包、短连即断）。改动在 DB `vpn_nodes.mtu`。

### 安全（来自事故排查，待收敛）
- 多个节点共用同一个内部 **Agent Token**，单点泄露会横向扩大。
- 新加坡仍开启 `PasswordAuthentication` 和 root 密码登录。
- 主服务器与两台美国节点的 Agent（51821/tcp）监听公网，美国节点 UFW 未启用；云安全组限制情况待确认。
- 明文凭证清单在 `markdown/a.markdown`（SSH 密码、GitHub token、各节点私钥位置）——**勿提交进仓库**。
- GitHub token 目前**无 `workflow` scope**，无法通过 API 改动 `.github/workflows/`。

### 凭证与签名（仅位置，不含明文）
- Android 签名：`xingsui-release.jks`（别名 `xingsui-release`），口令 `xingsui-release-password.txt`；证书 `CN=Xingsui`。
- 生产环境变量：`/opt/xingsui/deploy/control-plane/.env`。
- 各节点 Agent Token：节点 `/etc/xingsui/agent.env`。
- 数据库备份：`/Users/a1-6/vpn-backups`。

### 测试与数据卫生
- 测试账号统一用 `@xingsuitest.dev` 邮箱，便于批量清理（删除逻辑与 `DELETE /admin/users/{id}` 一致）。
- 客户端「检查更新」依赖后端 `/app/version` 与 `.env` 的 `APP_VERSION_*`。

---

## 8. 当前已部署版本（2026-07-11）

| 端 | 版本 | 状态 |
|---|---|---|
| 后端 | — | 免费流量规则、支付 QR、删用户、大阪 443 均已上线 |
| Android | `2.0.19 (29)` | 已签名上传官网；后端已播报 29 |
| Windows | `1.0.19` | CI 构建后 NSIS 已部署官网 |

> 建议用**非 VIP 真机**回归：连接（走免费流量）→ 我的页显示剩余 MB → 用尽提示 → 官网下单→管理员确认→VIP 激活。
