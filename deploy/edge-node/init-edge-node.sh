#!/usr/bin/env bash
# ============================================================
# 星隧 VPN 边缘节点（数据面）无状态初始化脚本
# 适用：Ubuntu 22.04/24.04 全新边缘节点
# 作用：部署 AmneziaWG 服务端（抗封锁混淆）+ 转发/NAT + 防火墙 + swap
# 节点不存业务数据；用完即可重建。以 root 运行：sudo bash init-edge-node.sh
# ============================================================
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "请以 root 运行"; exit 1; }

# ---------- 可调参数（可用环境变量覆盖）----------
WG_IFACE="${WG_IFACE:-awg0}"
WG_PORT="${WG_PORT:-443}"                 # UDP 443，伪装常见 HTTPS 端口
SERVER_ADDR="${SERVER_ADDR:-10.66.66.1/24}"
CLIENT_NETWORK="${CLIENT_NETWORK:-10.66.66.0/24}"
NODE_NAME="${NODE_NAME:-xingsui-edge}"
CONF_DIR="/etc/amnezia/amneziawg"
CONF="${CONF_DIR}/${WG_IFACE}.conf"

# ---------- 节点 Agent 参数 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XS_NODE_ID="${XS_NODE_ID:-$NODE_NAME}"
XS_AGENT_PORT="${XS_AGENT_PORT:-51821}"
XS_AGENT_LISTEN="${XS_AGENT_LISTEN:-0.0.0.0}"
# 只允许控制面源 IP 访问 Agent；未设置时不对公网放行 Agent 端口。
XS_CONTROL_PLANE_IP="${XS_CONTROL_PLANE_IP:-}"
# 控制面基址（用于心跳上报），如 https://xingsui.org；留空则不上报心跳
XS_CONTROL_PLANE_URL="${XS_CONTROL_PLANE_URL:-}"
# 每节点独立 HMAC secret；只写入 root-only 注册文件，不打印到终端。
XS_NODE_SECRET="${XS_NODE_SECRET:-$(openssl rand -hex 32)}"
XS_AGENT_TLS_CERT="/etc/xingsui/tls/agent.crt"
XS_AGENT_TLS_KEY="/etc/xingsui/tls/agent.key"
XS_VLESS_CONFIG="${XS_VLESS_CONFIG:-}"
XS_VLESS_INBOUND_TAG="${XS_VLESS_INBOUND_TAG:-}"
XS_VLESS_SERVICE="${XS_VLESS_SERVICE:-}"
XS_MANAGED_PROTOCOLS="${XS_MANAGED_PROTOCOLS:-awg}"
XS_SING_BOX_BIN="${XS_SING_BOX_BIN:-/usr/local/bin/sing-box}"

# 混淆参数：Jc/Jmin/Jmax/S1/S2 提供 GFW 优化默认值，可用环境变量覆盖
JC="${AMNEZIA_JC:-4}"; JMIN="${AMNEZIA_JMIN:-40}"; JMAX="${AMNEZIA_JMAX:-70}"
S1="${AMNEZIA_S1:-86}"; S2="${AMNEZIA_S2:-574}"
# 约束：S1+56 必须 != S2
if [[ $((S1 + 56)) -eq $S2 ]]; then S2=$((S2 + 1)); fi

rand_u32() { echo $(( (RANDOM % 250) + 5 )); }
gen_distinct_h() {  # 生成 4 个互不相同、且 >4 的大随机数（避免与 WG 标准消息类型冲突）
  local a b c d
  a=$(rand_u32); b=$(rand_u32); c=$(rand_u32); d=$(rand_u32)
  while [[ "$b" == "$a" ]]; do b=$(rand_u32); done
  while [[ "$c" == "$a" || "$c" == "$b" ]]; do c=$(rand_u32); done
  while [[ "$d" == "$a" || "$d" == "$b" || "$d" == "$c" ]]; do d=$(rand_u32); done
  echo "$a $b $c $d"
}
read -r H1 H2 H3 H4 <<<"${AMNEZIA_H1:-$(gen_distinct_h)}"
if [[ -n "${AMNEZIA_H1:-}" ]]; then H2="${AMNEZIA_H2}"; H3="${AMNEZIA_H3}"; H4="${AMNEZIA_H4}"; fi

echo "[1/9] 配置 swap（低内存节点必备）"
if ! swapon --show | grep -q . && [[ $(free -m | awk '/^Mem:/{print $2}') -lt 1024 ]]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "[2/9] 开启 IP 转发"
cat >/etc/sysctl.d/99-xingsui-forward.conf <<'EOF'
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF
sysctl --system >/dev/null

echo "[3/9] 安装 AmneziaWG 与 Agent 依赖"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y software-properties-common python3-launchpadlib curl iproute2 ufw openssl python3 dkms gnupg2 ca-certificates linux-headers-"$(uname -r)"
add-apt-repository -y ppa:amnezia/ppa
apt-get update -y
apt-get install -y amneziawg amneziawg-tools

echo "[4/9] 生成服务端密钥"
mkdir -p "$CONF_DIR" && chmod 700 "$CONF_DIR"
umask 077
SERVER_PRIV=$(awg genkey)
SERVER_PUB=$(echo "$SERVER_PRIV" | awg pubkey)
EGRESS=$(ip route show default | awk '/default/{print $5; exit}')
PUBLIC_IP=$(curl -4 -fsS --max-time 8 https://ifconfig.me 2>/dev/null || hostname -I | tr ' ' '\n' | awk '/^[0-9]+\./{print; exit}')

echo "[5/9] 写入 ${CONF}"
cat >"$CONF" <<EOF
[Interface]
Address = ${SERVER_ADDR}
ListenPort = ${WG_PORT}
PrivateKey = ${SERVER_PRIV}
# ---- AmneziaWG 混淆参数（客户端必须完全一致）----
Jc = ${JC}
Jmin = ${JMIN}
Jmax = ${JMAX}
S1 = ${S1}
S2 = ${S2}
H1 = ${H1}
H2 = ${H2}
H3 = ${H3}
H4 = ${H4}
# ---- 转发与 NAT ----
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o ${EGRESS} -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o ${EGRESS} -j MASQUERADE
# 客户端 peer 由控制面通过 Agent/SSH 动态写入（awg set ${WG_IFACE} peer ...）
EOF
chmod 600 "$CONF"

echo "[6/9] 启动服务"
systemctl enable "awg-quick@${WG_IFACE}" >/dev/null 2>&1 || true
systemctl restart "awg-quick@${WG_IFACE}"

echo "[7/9] 防火墙放行 UDP ${WG_PORT}，Agent 仅允许控制面源地址"
if ufw status | grep -q "Status: active"; then
  ufw allow "${WG_PORT}/udp" >/dev/null || true
  ufw --force delete allow "${XS_AGENT_PORT}/tcp" >/dev/null 2>&1 || true
  ufw deny "${XS_AGENT_PORT}/tcp" >/dev/null || true
  if [[ -n "${XS_CONTROL_PLANE_IP}" ]]; then
    ufw insert 1 allow from "${XS_CONTROL_PLANE_IP}" to any port "${XS_AGENT_PORT}" proto tcp >/dev/null
  fi
else
  iptables -C INPUT -p udp --dport "${WG_PORT}" -j ACCEPT 2>/dev/null || \
    iptables -I INPUT -p udp --dport "${WG_PORT}" -j ACCEPT
  while iptables -D INPUT -p tcp --dport "${XS_AGENT_PORT}" -j ACCEPT 2>/dev/null; do :; done
  iptables -C INPUT -p tcp --dport "${XS_AGENT_PORT}" -j DROP 2>/dev/null || \
    iptables -A INPUT -p tcp --dport "${XS_AGENT_PORT}" -j DROP
  if [[ -n "${XS_CONTROL_PLANE_IP}" ]]; then
    iptables -C INPUT -p tcp -s "${XS_CONTROL_PLANE_IP}" --dport "${XS_AGENT_PORT}" -j ACCEPT 2>/dev/null || \
      iptables -I INPUT -p tcp -s "${XS_CONTROL_PLANE_IP}" --dport "${XS_AGENT_PORT}" -j ACCEPT
  fi
fi

echo "[8/9] 部署节点 Agent"
install -d -m 755 /opt/xingsui
install -m 755 "${SCRIPT_DIR}/agent.py" /opt/xingsui/agent.py
install -d -m 700 /etc/xingsui
install -d -m 700 /etc/xingsui/tls
umask 077
if [[ ! -s "${XS_AGENT_TLS_CERT}" || ! -s "${XS_AGENT_TLS_KEY}" ]]; then
  openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
    -subj "/CN=${XS_NODE_ID}" \
    -addext "subjectAltName=IP:${PUBLIC_IP}" \
    -keyout "${XS_AGENT_TLS_KEY}" -out "${XS_AGENT_TLS_CERT}" >/dev/null 2>&1
fi
cat >/etc/xingsui/agent.env <<EOF
XS_AGENT_ENV=production
XS_NODE_SECRET=${XS_NODE_SECRET}
XS_NODE_ID=${XS_NODE_ID}
XS_CONTROL_PLANE_URL=${XS_CONTROL_PLANE_URL}
XS_AGENT_LISTEN=${XS_AGENT_LISTEN}
XS_AGENT_PORT=${XS_AGENT_PORT}
XS_AGENT_TLS_CERT=${XS_AGENT_TLS_CERT}
XS_AGENT_TLS_KEY=${XS_AGENT_TLS_KEY}
XS_WG_IFACE=${WG_IFACE}
XS_WG_TOOL=awg
XS_MANAGED_PROTOCOLS=${XS_MANAGED_PROTOCOLS}
XS_HEARTBEAT_INTERVAL=30
XS_LEASE_STATE_PATH=/var/lib/xingsui-agent/leases.json
XS_VLESS_CONFIG=${XS_VLESS_CONFIG}
XS_VLESS_INBOUND_TAG=${XS_VLESS_INBOUND_TAG}
XS_VLESS_SERVICE=${XS_VLESS_SERVICE}
XS_SING_BOX_BIN=${XS_SING_BOX_BIN}
EOF
chmod 600 /etc/xingsui/agent.env
cat >/etc/xingsui/registration.json <<EOF
{"node_id":"${XS_NODE_ID}","protocol":"awg","node_secret":"${XS_NODE_SECRET}","endpoint":"${PUBLIC_IP}:${WG_PORT}","agent_host":"${PUBLIC_IP}","agent_port":${XS_AGENT_PORT},"agent_ca_file":"${XS_AGENT_TLS_CERT}","server_public_key":"${SERVER_PUB}","client_network":"${CLIENT_NETWORK}","params":{"Jc":"${JC}","Jmin":"${JMIN}","Jmax":"${JMAX}","S1":"${S1}","S2":"${S2}","H1":"${H1}","H2":"${H2}","H3":"${H3}","H4":"${H4}"}}
EOF
chmod 600 /etc/xingsui/registration.json
install -m 644 "${SCRIPT_DIR}/xingsui-agent.service" /etc/systemd/system/xingsui-agent.service

echo "[9/9] 启动 Agent 服务"
systemctl daemon-reload
systemctl enable xingsui-agent >/dev/null 2>&1 || true
systemctl restart xingsui-agent

cat <<EOF

==================== 部署完成：${NODE_NAME} ====================
接口: ${WG_IFACE}  状态: $(systemctl is-active "awg-quick@${WG_IFACE}")
Agent: $(systemctl is-active xingsui-agent)

>>> 每节点注册材料已写入 /etc/xingsui/registration.json（root:600） <<<
>>> 安全传输到控制面的 NODE_AGENT_SECRETS_FILE，不要复制到终端/日志。 <<<

================================================================
EOF
