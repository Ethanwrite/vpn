# 星隧 VPN — 架构与完整业务逻辑文档

> 面向维护者与后续开发的权威参考。涵盖系统组成、完整业务流程、协议与抗封策略、
> 部署方式、数据模型，以及**后续加需求时必须注意的事项**。
> 凭证一律不写入本文，只注明存放位置。最后更新：2026-07-20。

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
- **免费 + VIP**：新账号 **60MB** 免费体验流量（**服务端按节点实测流量计费**，见 §4.2）；VIP 由管理员在后台手动确认订单后开通。
- **节点动态下发**：客户端**不硬编码**节点，全部通过 API 获取，并领取**短期租约**（≤1 小时）。
- **双域名抗封**：`xingsui.org` 与 `xingsuico.com` 均为完整官网/API 入口（互为镜像、不跳转）；客户端内置双域名故障转移（见 §5、§9）。

仓库：`https://github.com/Ethanwrite/vpn`（分支 `main`）。

---

## 2. 组件架构

| 组件 | 技术栈 | 目录 | 说明 |
|---|---|---|---|
| 控制面后端 | Python / FastAPI + SQLAlchemy | `amneziawg-android/backend` | API + 官网 SPA + 管理后台 + 支付页，单一 FastAPI app |
| 数据库 | PostgreSQL 16 | （容器） | 用户/订单/节点/设备/邀请/提现/订阅审计 |
| 反向代理 | Caddy 2 | `deploy/control-plane/Caddyfile` | 自动 TLS，反代到 api；`xingsui.org`+`xingsuico.com` 双域名完整镜像。TCP 443；HTTP/3 关闭、UDP 443 让给大阪 awg |
| Android 客户端 | Kotlin / AmneziaWG | `amneziawg-android`（`ui/.../xingsui`） | awg 协议；一键连接=智能选节点 |
| Windows 客户端 | Tauri (Rust) + React/TS | `xingsui-windows` | VLESS/Reality/Vision（sing-box + wintun） |
| 边缘节点 Agent | Python | `deploy/edge-node/agent.py` | 通过 `awg set` / sing-box 动态增删 user/peer，上报心跳，管理租约；`POST /peer/usage` 返回每-peer 实测流量供服务端计费 |
| 新加坡中转 | nftables + relay service | `deploy/relay` | 日本节点→新加坡 UDP/TCP 中转落地（awg 入口 4500/51823，VLESS 入口 10444） |

**后端子模块**（`backend/app/`）：`main.py`（全部路由/鉴权中间件/节点调度/租约签发）、`site_page.py`（官网 SPA）、`payment_page.py`（支付页）、`admin_page.py`（管理后台）、`payment_config.py`（收款码/深链）、`node_service.py`（节点评分与配置渲染）、`db_models.py`/`database.py`（ORM）。

**Agent 关键函数**：`add_peer/remove_peer`（awg）、`add_vless_user/remove_vless_user`（sing-box）、`register_lease`（本地租约，`expires_at`）、`reconcile_*`（清理不在租约表里的 user/peer）、`static_vless_uuids()`（保留订阅永久 user）、`peer_usage()`（`wg show dump` 每-peer 实测 rx+tx，供后端计费）。

---

## 3. 服务器与网络拓扑

| 主机 | 角色 | 关键监听 |
|---|---|---|
| `64.90.24.84` | **控制面服务器**（2026-07-15 迁移）：Postgres+API+Caddy，纯 API 不做节点；两域名 DNS 均指向此机 | TCP 80/443(Caddy) |
| `64.83.40.66` | **日本节点**（node-japan-02，2026-07-16 新增；user 端显示名 **"大阪 CN2 优化线路"**，接替已下线的 212；**权重 220 = 一键连接默认节点**）：awg(UDP 443) + VLESS(8443) + 承载新加坡中转。awg0=10.70.0.1/24，Ubuntu 22.04 需装 HWE 6.8 内核 amneziawg DKMS 才编得过（老 5.15 内核缺 timer_delete） | 443(awg)、8443(VLESS)、**4500→SG(首选)**、51823→SG(legacy)、10444→SG、51821(agent) |
| `172.86.91.81` | 美国达拉斯边缘节点（node-172，awg + VLESS 8443；显示名"星隧高速线路"；权重 80） | 443、8443 |
| `144.172.97.191` | 美国犹他边缘节点（node-144，awg + VLESS 8443；显示名"星隧高速线路"；权重 150） | 443、8443 |
| `61.13.236.140` | 新加坡节点（node-singapore，显示名"新加坡家宽住宅 BGP（原生双ISP）"；VLESS 10443/awg 51820，经日本节点中转，DB endpoint=`64.83.40.66:4500`；权重 60；SSH 端口 18827；**未装 tcpdump，抓包用 python AF_PACKET**） | 10443、51820 |
| ~~`212.50.232.111`~~ | **已下线**（2026-07-17，带宽耗尽被机房断网）。原主服务器/大阪节点，控制面与新加坡中转此前均已迁走，节点已从 DB 池删除 | — |

**端口策略（抗封关键）**：国内移动网络常封高位 UDP 端口，能稳定连通的都走 **443** 或伪装良好的 Reality。
- 边缘节点 awg 直接监听 UDP 443（无 Caddy 占用，不用 REDIRECT）；日本节点同此。
- VLESS：8443 TCP（新加坡经日本节点 10444 中转到 10443）。
- ⚠️ **高位 UDP 端口禁止设为节点池最高权重**（详见 §5.1 事件记录）。2026-07-19 起新加坡 DB endpoint 已切 `64.83.40.66:4500`（IPsec NAT-T 端口，运营商为 VoWiFi 普遍放行），51823 仅作存量配置兼容保留。
- **全节点 TCP 拥塞算法 = BBR**（2026-07-19 启用并持久化：`/etc/sysctl.d/99-xingsui-bbr.conf` + `/etc/modules-load.d/xingsui-bbr.conf`）。跨境丢包路径上 cubic 会把单流 VLESS/TCP 吞吐打崩，**新建/重装节点必须确认 BBR 开启**（`sysctl net.ipv4.tcp_congestion_control` 应为 `bbr`）。awg/UDP 不受此影响。
- **新加坡经日本节点中转连接**（2026-07-16 从 212 迁至 64.83.40.66，212 下线后为唯一入口）：客户端连 `64.83.40.66:10444`(VLESS)/awg 双入口 `64.83.40.66:4500`（**首选**，IPsec NAT-T 端口、移动网络为 VoWiFi 普遍放行，2026-07-19 加入并抓包验证）与 `:51823`（legacy，兼容存量配置），均中转到 `61.13.236.140:10443`/`:51820`。中转 nft 表 `xingsui_singapore_relay`（systemd `xingsui-singapore-relay.service`），SG 侧 ufw 放行中转机 IP。DB `vpn_nodes.endpoint` 应指向 4500 入口。

---

## 4. 完整业务逻辑

### 4.1 认证
`POST /auth/email/register|login` → 返回 `access_token`（Bearer）。客户端本地保存会话；会话在 DB `auth_sessions`，有独立过期时间。网页/通用默认 24 小时；带 `X-Xingsui-Platform: android` 的新登录默认 30 天（`ANDROID_ACCESS_TOKEN_TTL_SECONDS`），仍受最多 2 个 active 会话、主动登出和后台冻结约束。

### 4.2 免费流量 vs VIP（连接授权，核心规则）
1. 新账号固定 **60MB** 免费流量（`FREE_TRAFFIC_QUOTA_BYTES`；2026-07-14 由 30→60MB，**仅对新注册生效**，老用户保留原配额）。
2. 非 VIP 只要**剩余流量 > 0** 就允许连接（`reason=free_trial`）。
3. 用完返回 `free_traffic_exhausted`；客户端弹「免费流量已用完，前往官网开通会员」卡片（见 §9 客户端）。
4. VIP 有效则**不扣**免费流量（`reason=vip_active`）；VIP 过期 `reason=vip_expired`。

实现：`main.py::build_vpn_entitlement`。`/vpn/authorize`、`/vpn/config`、`/vpn/nodes/{id}/config`、`/usage/report` 均据此判定 `allowed`。两个客户端都以 `entitlement.allowed` 为准，**不再要求 `vip_status==active`**。

**流量计费必须服务端实测，切勿信任客户端自报（2026-07-14 修复重大漏洞）**：`/usage/report` 曾按客户端自报字节扣费、且同一调用负责续租，客户端报 `0` 即可保持租约不断、`used` 永远为 0 → **非 VIP 无限白嫖**。现改为：
- **awg**：后端 `reconcile_node_usage()` 循环（默认 20s，`NODE_USAGE_SWEEP_SECONDS`）向各节点 Agent `POST /peer/usage` 拉取每-peer 实测累计流量，按 `vpn_devices.measured_bytes` 基线扣**真实增量**、用尽即撤销 peer。`/usage/report` 对 awg **不再扣费**（仅续租）。**VIP 永不计费；免费用户按真实字节计费，无速率/时长限制。**
- **VLESS**：sing-box 暂无逐-user 统计，仍走"客户端自报 + 时间下限"兜底（`FREE_TRAFFIC_MIN_BYTES_PER_SEC`，默认 50KB/s，防自报 0 白嫖）；节点实测计费是待办。

### 4.3 VPN 连接
**Android（awg）**：`GET /vpn/authorize`（查授权）→ 一键连接 `GET /vpn/config`（后端 `select_pool_node` 按权重/在线/负载选最优节点，且**自动池只允许 UDP 443/4500**；Agent 远程签发 peer，返回架构上限内的 **1 小时短租约**，`ANDROID_VPN_LEASE_TTL_SECONDS=3600`；支持 `?exclude_node=<id>` 供客户端首次握手失败换节点，排除后池空则忽略排除）；手动选节点 `GET /vpn/nodes/{id}/config`。连接后客户端每 30s `POST /usage/report`；awg 扣费仍由服务端每 20s 拉节点实测流量，只有租约进入最后 10 分钟才写 Agent+DB 续期（`VPN_LEASE_RENEWAL_WINDOW_SECONDS=600`）。明确授权拒绝才断开；I/O/超时/5xx 保持数据面，过期租约唤醒后透明重签。App 自身通过 `ExcludedApplications` 排除出隧道，上报/恢复不依赖隧道内数据面。

**Windows（VLESS）**：`GET /vpn/nodes/{id}/config`（仅 `protocol=vless` 节点）→ 后端 `provision_vless_device` 生成 uuid、调 Agent `agent_add_vless_user` 动态注册到 sing-box、返回 Reality 参数。客户端 sing-box 建链。校验在 `src-tauri/src/vless.rs`，续租在 `stats.rs`。

### 4.4 支付 → 开通 VIP
1. 官网选套餐 → 跳转 `/payment?plan_id=...`。当前套餐：**首月 ¥18 / 季度 ¥48 / 年度 ¥158**（`vip_plans` 表；改价需**同时**改 `main.py` seed 与生产 DB `UPDATE vip_plans`，另 `site_page.py` 有一份 JS 兜底价与文案）。
2. `/payment` 显示微信/支付宝深链按钮 + **收款码兜底**（**站内相对路径** `/pay/{wechat,alipay}.jpg`，随当前域名加载，两个镜像域名均可用）。
3. 点「我已完成支付」→ `POST /orders` → `POST /orders/{id}/paid` → 订单 `pending_confirm`，前端弹「订单已提交成功…」。
4. 管理员 `POST /admin/orders/{id}/confirm` → 用户 VIP 激活（按套餐天数）。`reject` 亦可。

### 4.5 订阅链接（VIP，供第三方客户端）
- VIP 在用户中心「导出订阅链接」→ `GET /user/subscription-link` → 返回 `https://xingsui.org/api/sub?token=...`。
- Token 为 **HMAC-SHA256** 签名（`user_id:version`，不可枚举）；**限频** 5次/60s（重置 1次/10min）；审计日志对 token **脱敏**；全程 **HTTPS**。
- 第三方拉取 `GET /sub?token=...` → 返回 Clash YAML。YAML 首个节点是「⏳ 会员到期 …」信息节点，让用户在客户端节点列表直接看到到期时间。
- **每用户独立 UUID（2026-07-16 改造，取代共享静态 UUID）**：`/sub` 渲染时 `provision_subscription_credentials` 为该用户在每个可用 VLESS 节点 get-or-create 一个**专属 UUID**（`subscription_credentials` 表，每 user×node 一行），经 Agent `POST /vless/subscription/add` 注册到节点，**绑定 VIP 到期时间**（`expires_at`，节点 Agent 侧到期自动撤销，`MAX_SUBSCRIPTION_SECONDS`=400天）。每个 UUID 用 `name=u-{user_id}` 标记。**重置**（`/user/subscription-link/reset`）会先 `revoke_subscription_credentials` 逐节点 `POST /vless/subscription/remove` 撤销旧 UUID 再 version+1 → **旧配置（含已复制/泄漏的）立即失效**（旧共享静态 UUID 时代重置无效，因静态 UUID 永久存活）。
- **按 UUID 计量（源 IP 审计）**：XTLS-vision 握手后 splice 到内核，sing-box 的 v2ray_api（本二进制未编译）/clash_api 都拿不到逐-user 字节。改用**节点 sing-box `info` 日志**：每条有效连接打印 `[u-{user_id}] inbound connection to ...` 与源 IP，Agent `/vless/usage` 按 UUID 聚合**不同源 IP 数/连接数**，后端 `audit_subscription_usage()` 循环（`SUBSCRIPTION_AUDIT_SWEEP_SECONDS`，默认 300s）拉取并写入 `subscription_credentials.last_distinct_source_ips` 及**当日峰值** `daily_peak_source_ips`，超 `SUBSCRIPTION_SHARING_ALERT_IPS`（默认 5）告警——**一个 UUID 多源 IP = 共享/泄漏信号**。字节级配额对不计费的 VIP 无意义，故不做。
- **共享自动撤销**（`enforce_subscription_sharing_revocation`）：某用户单节点源 IP 峰值 ≥ `SUBSCRIPTION_REVOKE_SOURCE_IPS`（默认 10，远高于告警 5）**连续 2 次审计**（strike 防抖，回落即清零）→ 自动 `revoke_subscription_credentials`+`reset_subscription_token`（version+1 杀旧链接）+ 写 `auto_revoke_share` 审计日志。开关 `SUBSCRIPTION_AUTO_REVOKE_ENABLED`（默认 on）。
- **发放容错**：`provision_subscription_credentials` 遍历节点时单个节点 Agent 不可达（如带宽耗尽）会**跳过该节点**、用其余节点照常出配置，不再整单 503（212 下线时验证）。
- 非 VIP 点导出 → 友好提示「开通 VIP 后即可导出订阅链接」；`/sub` 对无效 token 返回 401，非 VIP 返回对应 code。**撤销 VIP（`revoke-vip`）与删除用户（`DELETE /admin/users/{id}`）均会撤销其节点侧订阅 UUID。**

### 4.6 管理后台
`/admin`（`ADMIN_SESSION` cookie：`Secure`+`SameSite=strict`+`path=/admin`）。功能：概览、订单确认/拒绝、授/撤 VIP、**删除用户**（`DELETE /admin/users/{id}`，级联清理订单/设备/邀请/提现/会话/审计/**订阅凭证**并撤销节点 peer 与订阅 UUID）、节点增删改、收款码配置、促销、财务提现。
用户列表含 **「订阅用量」列**：显示每用户当日订阅源 IP 峰值（`subscription_source_ips_today`=各节点 `daily_peak_source_ips` 的 max），≥5 标红「疑似共享」——供人工识别泄漏/共享（自动撤销见 §4.5）。
所有写操作额外受 **`ADMIN_WRITES_ENABLED`** 开关控制（见 §9）。

---

## 5. 协议与抗 GFW 策略

**Android — AmneziaWG**：在 WireGuard 上加混淆参数（`Jc/Jmin/Jmax/S1/S2/H1-H4`）抗 DPI。客户端 **MTU=1280**（家宽/PPPoE 路径 1420 过大 → 握手成功但数据丢包、短连即断）。

**Windows / 订阅 — VLESS + Reality + Vision**：
- **SNI 用自家域名 `xingsui.org`**（解析到主服务器）。原因：GFW 有 **SNI↔目标 IP 一致性检测**，借用大厂域名（apple.com 等）因 IP 不属于该大厂反而更易被封；`xingsui.org` 443 有真实 Caddy 站点、国内可访问（官网能打开），既 IP 一致又能做 Reality handshake 兜底。**不要改用大厂域名。**
- handshake 兜底：主服务器 `127.0.0.1:443`，边缘节点 `xingsui.org:443`。
- **flow = `xtls-rprx-vision`**，三处必须一致：sing-box 服务端每个 user、DB `params_json.VlessFlow`、订阅链接 `flow=`。Agent 发放动态 user 的 flow 由 `/etc/xingsui/agent.env` 的 `XS_VLESS_FLOW` 控制。
- pbk/sid 是每台服务器的 Reality 密钥对，与 SNI 无关；**DB `VlessPublicKey/VlessShortId` 必须与 sing-box 实际密钥一致**（见 §9）。

**双域名镜像 `xingsuico.com`（抗封冗余）**：与 `xingsui.org` 同一后端、完整镜像官网/API/下载/`/pay`，**不做互相跳转**（跳转到被封域名等于没修，冗余要求两域名各自独立可用）。两域名 DNS 均指向控制面 `64.90.24.84`（2026-07-15 迁移后）。**Reality SNI 仍固定 `xingsui.org`，不要把镜像域名设成 Reality `serverName`**。用途仅是网站/API 抗 DNS 污染/SNI 阻断的备用入口；若 `xingsui.org` 名称本身遭 SNI 阻断进而影响 VLESS，可服务端轮换 DB `VlessServerName`（无需重打包）。客户端 API 双域名故障转移见 §9。

### 5.1 网络稳定性事件与修复记录（2026-07-18/19，必读）

**事件一：Android「连上约 1 分钟自动断开」（多名用户反馈，含 VIP）**
- **根因链**：212 下线后 select_pool_node（确定性取最高分）把全体一键连接用户送到当时权重最高（180）的新加坡节点，其 awg 入口是高位 UDP 51823（日本中转）。部分移动网络掐高位 UDP：握手小包能过、数据流几十秒内被断 → App 每 10s 的 `/usage/report` 走隧道内、超时（5s/7s × 双域名）→ 旧版客户端**单次上报失败即断隧道** ≈ 连接后 1 分钟。诊断依据：受影响会话节点实测仅 7KB（纯握手无数据）但租约持续续期（`/vpn/config` 复用同 user×node 设备行，反复重连合并为一行）；健康表 peer 全部堆在新加坡。
- **修复**：①权重 japan-02 50→220 / 新加坡 180→60（服务端即时生效）；②新加坡中转加 UDP 4500 入口并把 DB endpoint 切过去（标记探测包全链路抓包验证）；③客户端 2.0.23 三项加固（见下）；④后端 `/vpn/config?exclude_node=` 换线重连支持。
- **教训**：任何入口端口调整/节点上下线后，必须检查**一键连接实际落点**（健康表 peer 分布）是否符合端口策略；节点池最高权重必须是 443/4500 类端口。

**事件二：Windows 端所有代理模式卡顿（晚高峰）**
- **排查**：节点全部空闲（load 0.08、内网实测 1.1Gbps、sing-box 无错误），服务器侧排除；判定为跨境链路晚高峰拥塞/运营商 QoS。
- **发现并修复**：四节点 TCP 拥塞算法全是 cubic 且 tcp_bbr 未加载——跨境丢包路径上这是 VLESS/TCP 吞吐崩盘的放大器（awg/UDP 不受影响，与"只有 Windows 卡"吻合）。已全节点启用并持久化 BBR。
- **测量陷阱**：从本地测跨境吞吐前，先测国内基准（如清华镜像）校准观测点——本地宽带慢会让所有方向都显示 ~2Mbps，误判为链路问题。
- **长期项**：晚高峰持续差则考虑真 CN2 GIA/IPLC 入口（"大阪 CN2 优化线路"是显示名，实际路由未必 CN2）。

**事件三：Android 仍随机自动断开（2026-07-20 深度排查）**
- **线上证据**：节点与 Agent 持续健康、2.0.27 的 `/usage/report` 全部 200；同时观察到健康空闲 peer 的握手年龄超过 180s，证明“历史握手 >180s 即判死”会误杀。旧版本控制面请求仍从 VPN 出口发出，说明 2.0.23 以前客户端没有 App 排除，必须强制升级。
- **复合根因**：①Android Doze 会暂停普通 10s 协程，原 5 分钟租约在休眠中被 Agent 删除；②首页 `/me`、状态统计或连续 3 次上报的瞬时失败均会删除隧道；③网络回调先 DOWN 再拉新配置，取消窗口可永久留下 DOWN；④重复 `GET /vpn/config` 覆盖同一设备行的 `lease_id`，旧连接下一次上报立刻 403；⑤GoBackend 热切换先 `stopSelf()`，排队的 `onDestroy()` 会关掉刚创建的新 handle；⑥native Go 的全局 tunnel handle map 无锁，状态读取/上报与热切换并发时可直接触发 `concurrent map read and map write` 杀进程；⑦旧 Android token 仅 24 小时且无刷新，活跃用户到点被 401 断开；⑧控制面重启错误地只恢复 VIP peer，误撤仍有免费流量的用户；⑨多 Uvicorn worker 的启动迁移、节点心跳、租约清理与实测计费缺少完整事务栅栏。
- **2.0.28 修复**：配置先取后切、连接/断开统一 Mutex、backend+lease 元数据不可取消原子提交；热切换保留前台 VpnService，仅最终 DOWN 才停止，Service generation/future 与激活/销毁统一加锁；native handle map 用 RWMutex 保护且读锁覆盖整个 handle 使用周期；网络候选稳定去抖并保留最新切换事件；Service 被系统重启后按用户已连接意图拉新短租约；瞬时控制面/统计错误不再断，租约过期透明重签；只用“真实 peer 连接 60s 仍从未握手”触发一次智能换线，空统计与陈旧历史握手不判死。服务端同一 AWG 连接重取配置保留 `lease_id`，Android 短租约放宽至 1 小时并在最后 10 分钟续租；新登录 token 为 30 天，旧活跃 Android token 一次性提升到其创建时间+30天（非滑动）；启动迁移/心跳使用同一 PostgreSQL 事务级共享/独占栅栏，清理/计费另加 advisory/row lock；免费授权、MTU 1280、keepalive 25 与安全端口成为硬约束。

**客户端弹性（Android 2.0.28 起）**：①App 自身排除出隧道，配置 API 双域名故障转移；②仅 401/明确 entitlement 拒绝立即断，I/O/超时/5xx 无限重试且不拆数据面；③真实 peer 连接 60s 从未握手才提示并自动带 `exclude_node` 换节点一次，**陈旧历史握手不再判死**；④网络切换原子换配置，失败保留原隧道；⑤Doze/Service 重启后透明重签恢复。

---

## 6. 数据模型（关键表）

- **users**：id、email、password_(salt/hash)、invite_code、`invited_by_user_id`（自引用）、`vip_status`/`vip_expired_at`、`cash_balance_cents`、`free_traffic_quota_bytes`/`_used_bytes`、`status`、`subscription_token_*`。除 ORM 的 `ix_users_email` 唯一索引外，另有**手工加的 `ix_users_email_lower`（lower(email) 唯一）**防大小写变体重复注册——`create_all` 不会创建它，重建库需手动补。
- **vpn_nodes**：id、name、region、`protocol`(awg/vless/dual)、enabled、weight、`vip_only`、max_clients、endpoint、`agent_host`/`agent_port`、awg 字段(server_public_key/allowed_ips/dns/mtu/params_json)、VLESS 字段(在 params_json：VlessHost/VlessPort/VlessPublicKey/VlessShortId/VlessServerName/VlessFlow/VlessUUID)。
- **vpn_node_health**：node_id、last_heartbeat_at、peer_count、cpu_load（节点在线/负载）。
- **vpn_devices**：每个租约一行（user/node/protocol/lease_id/lease_expires_at/vless_uuid/status/**`measured_bytes`**=该 peer 上次节点实测累计 rx+tx，awg 计费基线，2026-07-14 新增，需 `ALTER TABLE` 手动迁移）。
- **subscription_credentials**（2026-07-16 新增，订阅每用户独立 UUID）：每 user×node 一行（唯一约束 `uq_subscription_user_node`）：`vless_uuid`、`user_name`(=u-{user_id})、`token_version`、`expires_at`(=VIP 到期)、`last_distinct_source_ips`/`last_audit_at`、`daily_peak_source_ips`/`daily_peak_day`（当日源 IP 峰值，管理后台用量列）。**新表由 `create_all` 自动建；后加的 daily_peak_* 两列须手动 `ALTER TABLE ADD COLUMN IF NOT EXISTS`。**
- **orders / vip_plans / promotion_activities**：下单与套餐。
- **invitations / withdrawals**：邀请返现与提现。
- **auth_sessions / subscription_audit_logs / node_request_nonces**：会话、订阅审计（含 `auto_revoke_share`）、Agent 防重放。**设备登录限制**：`MAX_ACTIVE_AUTH_SESSIONS`（默认 2）——登录时 `prune_user_sessions` 只保留最新 2 个 active 会话（手机+电脑），第 3 次登录踢最老。**注意：订阅链接用 HMAC token 认证、不占会话，不受此限制**（可无限第三方客户端同时用；靠订阅源 IP 审计+自动撤销兜底，见 §4.5）。

引用 `users.id` 的表（删用户需按序清理）：auth_sessions、orders、vpn_devices、**subscription_credentials**、withdrawals、subscription_audit_logs、invitations(inviter/invitee)、users.invited_by_user_id。

---

## 7. 部署流程

### 7.1 后端（直接同步 + 重建镜像，**不走 CI**）
镜像 `xingsui-backend:latest` 从 `/opt/xingsui/backend` 构建（代码打进镜像，非挂载）：
```bash
scp app/*.py root@64.90.24.84:/opt/xingsui/backend/app/
ssh root@64.90.24.84 'cd /opt/xingsui/deploy/control-plane && docker compose build api && docker compose up -d api'
```
仓库 `amneziawg-android/backend` 与服务器 `/opt/xingsui/backend` 需保持一致。纯 env 改动只需 `docker compose up -d api`。**长时构建易被 SSH 会话截断**：可 `nohup docker compose build api >/tmp/b.log 2>&1 &` 后台跑再 `up -d api`。
**表结构变更无 Alembic**：新增列须手动 `docker compose exec -T db psql -U <u> -d <d> -c "ALTER TABLE ... ADD COLUMN IF NOT EXISTS ..."`（`create_all` 不会改已存在表），且**先迁移再上新代码**。

### 7.2 Android（本地构建 + 签名 + 上传）
```bash
# 环境见 amneziawg-android/docs/android-build.md
./gradlew :ui:assembleRelease -PxingsuiReleaseApiBaseUrl=https://xingsui.org   # 签名走 XINGSUI_KEYSTORE_* 环境变量
../scripts/upload-android-apk.sh    # 校验版本号后 scp 到 /opt/xingsui/download/xingsui.apk
```
之后同步 `.env` 的 `APP_VERSION_CODE/NAME` 并重启 api，App 内更新检查才提示。

### 7.3 Windows（GitHub Actions 构建 + 脚本部署）
推送 `xingsui-windows/**` 触发工作流 → 产出 NSIS/MSI artifact → 下载 → `scripts/upload-windows-installer.sh` 部署到 `/opt/xingsui/download/xingsui-windows-setup.exe`。当前 CI 工作流是 `windows-client.yml`（更严格的 `build.yml` 在 `backup/local-main-b0d584e` 分支，启用需带 `workflow` scope 的 token）。版本改 `src-tauri/{tauri.conf.json,Cargo.toml,Cargo.lock}` 与 `api.rs` 的 `VERSION_*`。**macOS 上无法本地 `cargo build`**（externalBin 只提供 Windows 版 sing-box，tauri-build 会因缺 `binaries/sing-box-<mac-triple>` 报错）——Windows 端只能靠 CI 构建验证。
- ⚠️ **`tauri.conf.json` 的 `bundle.windows.webviewInstallMode` 必须是 `downloadBootstrapper`，切勿改回 `skip`**：skip 时安装包不保证目标机有 WebView2 运行时，纯净 Windows（LTSC/精简装机/移除过 Edge 的系统）下应用一启动即闪退（2026-07-24 事故根因）。
- **崩溃排查**：客户端 panic 会写 `%LOCALAPPDATA%\com.xingsui.vpn.desktop\crash.log`，向用户索取此文件即可定位 Rust 侧崩溃。

### 7.4 节点 Agent（手动 scp + 重启）
Agent 代码部署到每个节点 `/opt/xingsui/agent.py`，systemd 服务 `xingsui-agent.service`：
```bash
scp deploy/edge-node/agent.py root@<节点>:/opt/xingsui/agent.py
ssh root@<节点> 'systemctl restart xingsui-agent'   # 重启不动 wg 接口，现有 peer 不掉
```
改 Agent 须部署到**所有节点**（日本 64.83.40.66 / 达拉斯 172.86.91.81 / 犹他 144.172.97.191 / 新加坡 61.13.236.140；212 已下线），否则漏部署的节点上免费用户不计费、订阅端点缺失（见 §9）。部署前 `diff` 服务器现有 `agent.py` 与仓库版本确认一致。**当前 Agent 版本 2.1.2**（AWG 状态/用量失败时 fail-closed；1 小时租约允许与签名窗口一致的 90s 时钟偏差；含 `/vless/subscription/{add,remove}`、`/vless/usage` 源 IP 审计）；订阅计量依赖各节点 **sing-box 日志级别 = `info`**（`/vless/usage` 解析日志），新建/重装节点须确认。新建 VLESS 节点的 sing-box service **必须有 `ExecReload=/bin/kill -HUP $MAINPID`**，否则 Agent 的 `systemctl reload` 失败、`/vless/add` 报 "Node agent unavailable"。

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
- **大阪 UDP 443 依赖**：①Caddy 关闭 HTTP/3（`docker-compose.yml` 不发布 `443:443/udp`，**且 Caddyfile 全局 `servers { protocols h1 h2 }`** 使其不再广播 `alt-svc h3`）②awg0.conf 的 REDIRECT PostUp。从仓库重新部署 Caddy 或重装大阪节点后务必确认这几点未被还原，否则大阪失联。
- **双域名镜像 `xingsuico.com`**：Caddyfile 里 `xingsuico.com`(含 `www.`) 是与 `{$SITE_DOMAIN}` 完全一致的 `reverse_proxy api` 块（不是只转 `/api/*` 的旧兼容桩）。两域名**各自独立可用、不互相跳转**；`CORS_ALLOW_ORIGINS`、`SITE_DOMAIN` 需含两域名。改 Caddyfile 后 `caddy validate` 再 `reload`（就地 `cp`，勿 `mv`，绑定挂载认 inode）。
- **收款码用相对路径**：`PAYMENT_WECHAT_QR_URL`/`PAYMENT_ALIPAY_QR_URL` 与 DB `payment_settings.qr_url` 一律用**站内相对** `/pay/*.jpg`（勿写死绝对域名，否则镜像页在主域名被封时二维码挂）；`/pay/` 由 API 提供，两域名都生效。
- **免费流量按节点实测计费（勿退回自报）**：awg 计费依赖各节点 Agent 的 `/peer/usage` + 后端 `reconcile_node_usage()` 循环 + `vpn_devices.measured_bytes` 列。**所有 awg 节点 Agent 必须同步含 `/peer/usage`**（见 §7.4），漏部署的节点上 awg 免费用户**不计费也无 floor 兜底**。`measured_bytes` 列缺失会导致后端启动/查询报错——新库或重建库须确认已 `ALTER TABLE`。VLESS 仍靠 `FREE_TRAFFIC_MIN_BYTES_PER_SEC` 时间下限兜底。
- **订阅节点文件权限**：`/opt/xingsui/download/subscription-links.txt` 必须能被 API 容器用户（`appuser` gid 999）读取，否则 `/sub` 返回 500。设为 `640 root:999`。**手动改该文件后重新 `chown root:999 && chmod 640`**。

### VLESS / Reality（最容易踩坑）
- **DB 的 pbk/sid 必须与 sing-box 实际密钥一致**：任何一次 Reality 密钥轮换，必须**同时**更新 sing-box 配置和 DB 的 `VlessPublicKey`/`VlessShortId`/`VlessHost`，否则动态客户端（Windows/App）握手失败报「账户状态同步失败」，而订阅（链接里硬编码正确密钥）却仍正常——极具迷惑性。验证方法：对该节点 `/vpn/nodes/{id}/config` 取配置，在美国机器起 sing-box 客户端跑通。
- **节点内部一致性**：`VlessHost:VlessPort` 必须指向**实际提供该 VLESS 服务的服务器**，且与该节点 `agent_host`（发放 user 的地方）落到同一台（新加坡例外：入口是主服务器中转口 10444，user 发到新加坡 agent）。历史 bug：node-144 的 VlessHost 误指主服务器而 agent 在犹他 → 认证失败。
- **flow 三处一致**：sing-box user、DB `VlessFlow`、订阅链接 `flow=` 都要 `xtls-rprx-vision`。
- **SNI 保持 `xingsui.org`**，不要改大厂域名（见 §5）。

### 客户端 vs 服务端
- **绝大多数配置改动是服务端驱动、无需重新打包 App**：节点、SNI、flow、MTU、pbk/sid 都来自后端/DB，客户端下次连接自动生效。只有客户端 UI/逻辑（如提示文案、页面）改动才需重新构建（Android 本地打包、Windows 走 CI）。
- **两端业务规则一致**：免费流量/VIP 判定以后端 `entitlement.allowed` 为准；客户端错误提示按 `reason`（`free_traffic_exhausted`/`vip_expired`/`vip_required`）映射友好文案：**Android** 用尽时弹 `XingsuiHomeActivity.showPaywallCard`（与节点选择卡片同风格的底部卡片，提示前往官网开通，**不再自动跳 App 内充值页**）；连接期 403 原因由 `XingsuiManagedConfig` 的 `XingsuiEntitlementException` 透传。**Windows** 在 `api.rs::friendly_reason_message`（文案指向官网）。
- **客户端双域名故障转移**：Android `XingsuiApiClient.buildApiBaseUrls`（含 `xingsuico.com`，sticky `activeBaseUrl`）+ `activeWebOrigin()`（官网/下载/充值走当前可达域名）；Windows `api.rs BASE_URLS` + sticky `preferred_base`。加/改镜像域名两端都要动、各自出新包。

### 其它
- **GitHub token 无 `workflow` scope**：无法通过 API 改 `.github/workflows/`。
- **测试账号**统一用 `@xingsuitest.dev` 邮箱，便于批量清理（删除逻辑同 `DELETE /admin/users/{id}`）。
- **SSH 限速**：短时间大量 SSH 连接会触发 fail2ban 临时封本机 IP（约 10 分钟自解），表现为 `kex_exchange_identification: Connection closed` 但网站正常。
- **后端改动记得同步仓库**：`/opt/xingsui/backend` 是构建源，改完后把对应文件同步回 `amneziawg-android/backend` 并提交，避免漂移。

---

## 10. 当前已部署版本（2026-07-20 更新）

| 端 | 版本 | 状态 |
|---|---|---|
| 控制面 | 独立服务器 `64.90.24.84`（2026-07-15 迁移，纯 API/DB/Caddy）| 2026-07-20 断连服务端修复已部署：Android 租约 1 小时/最后 10 分钟续租、同连接稳定 lease ID、Android token 固定 30 天边界、免费授权恢复、启动迁移/心跳事务栅栏、并发清理/计费锁、MTU 1280 与安全端口硬约束。双域名 `/health` 正常且两 worker 冷启动无 deadlock；回滚文件在 `/opt/xingsui/backups/android-disconnect-20260720` 与 `/opt/xingsui/backups/android-disconnect-pre-final-20260720T1450Z`。 |
| Android | **线上 `2.0.28 (38)`** | 2026-07-20 已完成 R8 签名 release 构建并上传，版本接口已切到 38；双域名下载 SHA-256 均为 `e47151e3e790d7a32dfcb95bdb204b4375b419162a0b5ae29655fc916d29e96c`，证书与 2.0.27 一致。断连专项版包含：原子热切换且不销毁 VpnService；网络/Doze/租约过期/Service 重启透明恢复；瞬时 API/统计错误不拆隧道；native handle 并发安全；移除陈旧握手误杀；配置 API 双域名故障转移；严格 MTU 1280/keepalive 25。2.0.27 回滚包在 `/opt/xingsui/backups/android-apk/xingsui-2.0.27-37-before-2.0.28.apk`。 |
| Windows | `1.0.23` | CI 构建。**2026-07-24 修复"下载后/登录后闪退"**：①`webviewInstallMode` 由 `skip` 改 `downloadBootstrapper`（skip 时无 WebView2 运行时的纯净 Windows 一启动即崩，头号原因）；②`setup()` 去除 `.expect()`（app_dir 解析/清理遗留配置失败不再 panic，改为记录并继续）；③新增 panic 钩子写 `%LOCALAPPDATA%\com.xingsui.vpn.desktop\crash.log`（静默闪退变可诊断）；④`ApiClient` 构建失败回退默认客户端不 panic。sing-box 二进制 SHA256 完整性固定；含官网文案、`xingsuico.com` API 故障转移。**缺 API 证书固定** |
| 节点 | 日本 64.83.40.66（显示"大阪 CN2 优化线路"，**权重 220 一键连接默认**）/ 犹他 144（150）/ 达拉斯 172（80）/ 新加坡（60，经日本中转 awg 入口 **4500**）| **4 节点均已部署 Agent 2.1.2**（控制面实测 `/healthz` 全部返回 2.1.2；AWG 状态/用量读取失败即停止健康心跳并返回 503；1 小时租约允许 90s 时钟偏差；含 `/peer/usage`、`/vless/subscription/*`、`/vless/usage`）；sing-box 日志级 `info`；VLESS 全部 xingsui.org SNI + Vision；awg MTU 1280；全节点 BBR。 |

> 回归建议：非 VIP 真机走 60MB→**真机跑满 60MB（节点实测）应被切断，客户端自报 0 也应被切**→用尽弹卡片→官网下单→管理员确认→VIP；VIP 逐个切 4 节点确认可连且 `used` **不增长**（不计费）；主域名被 DNS 污染/封锁时确认 `xingsuico.com` 可打开且 App 仍能登录/连接；订阅导入 Clash 确认 4 节点 + 到期节点，**重置订阅后旧配置立即失效**，同一订阅多源 IP 触发共享告警/自动撤销；**一键连接应落日本 443**（`/vpn/config` 冒烟 Endpoint=64.83.40.66:443，`?exclude_node=node-japan-02` 应降级 node-144），手动选新加坡 Endpoint 应为 `:4500`；节点上下线/权重调整后查健康表 peer 分布是否符合预期。
