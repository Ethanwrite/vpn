#!/usr/bin/env bash
# ============================================================
# 星隧 VPN 边缘节点（数据面）无状态初始化脚本
# 适用：Ubuntu 22.04/24.04 全新节点（172.86.91.81 / 144.172.97.191）
# 作用：部署 AmneziaWG 服务端（抗封锁混淆）+ 转发/NAT + 防火墙 + swap
# 节点不存业务数据；用完即可重建。以 root 运行：sudo bash init-edge-node.sh
# ============================================================
set -euo pipefail

[[ $EUID -eq 0 ]] || { echo "请以 root 运行"; exit 1; }

# ---------- 可调参数（可用环境变量覆盖）----------
WG_IFACE="${WG_IFACE:-awg0}"
WG_PORT="${WG_PORT:-443}"                 # UDP 443，伪装常见 HTTPS 端口
SERVER_ADDR="${SERVER_ADDR:-10.66.66.1/24}"
NODE_NAME="${NODE_NAME:-xingsui-edge}"
CONF_DIR="/etc/amnezia/amneziawg"
CONF="${CONF_DIR}/${WG_IFACE}.conf"

# ---------- 节点 Agent 参数 ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
XS_NODE_ID="${XS_NODE_ID:-$NODE_NAME}"
XS_AGENT_PORT="${XS_AGENT_PORT:-51821}"
# 控制面基址（用于心跳上报），如 https://xingsuico.com；留空则不上报心跳
XS_CONTROL_PLANE_URL="${XS_CONTROL_PLANE_URL:-}"
# 与控制面 INTERNAL_API_TOKEN 必须一致；未提供则自动生成并在结尾打印
XS_AGENT_TOKEN="${XS_AGENT_TOKEN:-$(openssl rand -hex 32)}"

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

echo "[7/9] 防火墙放行 UDP ${WG_PORT} 与 Agent TCP ${XS_AGENT_PORT}"
if ufw status | grep -q "Status: active"; then
  ufw allow "${WG_PORT}/udp" >/dev/null || true
  ufw allow "${XS_AGENT_PORT}/tcp" >/dev/null || true
else
  iptables -C INPUT -p udp --dport "${WG_PORT}" -j ACCEPT 2>/dev/null || \
    iptables -I INPUT -p udp --dport "${WG_PORT}" -j ACCEPT
  iptables -C INPUT -p tcp --dport "${XS_AGENT_PORT}" -j ACCEPT 2>/dev/null || \
    iptables -I INPUT -p tcp --dport "${XS_AGENT_PORT}" -j ACCEPT
fi

echo "[8/9] 部署节点 Agent"
install -d -m 755 /opt/xingsui
install -m 755 "${SCRIPT_DIR}/agent.py" /opt/xingsui/agent.py
install -d -m 700 /etc/xingsui
umask 077
cat >/etc/xingsui/agent.env <<EOF
XS_AGENT_TOKEN=${XS_AGENT_TOKEN}
XS_NODE_ID=${XS_NODE_ID}
XS_CONTROL_PLANE_URL=${XS_CONTROL_PLANE_URL}
XS_AGENT_PORT=${XS_AGENT_PORT}
XS_WG_IFACE=${WG_IFACE}
XS_WG_TOOL=awg
XS_HEARTBEAT_INTERVAL=30
EOF
chmod 600 /etc/xingsui/agent.env
install -m 644 "${SCRIPT_DIR}/xingsui-agent.service" /etc/systemd/system/xingsui-agent.service

echo "[9/9] 启动 Agent 服务"
systemctl daemon-reload
systemctl enable xingsui-agent >/dev/null 2>&1 || true
systemctl restart xingsui-agent

cat <<EOF

==================== 部署完成：${NODE_NAME} ====================
接口: ${WG_IFACE}  状态: $(systemctl is-active "awg-quick@${WG_IFACE}")
Agent: $(systemctl is-active xingsui-agent)  端口: ${XS_AGENT_PORT}
出口网卡: ${EGRESS}  公网IP: ${PUBLIC_IP}

>>> 1) 控制面 .env：INTERNAL_API_TOKEN 必须等于本节点 Agent 令牌 <<<
INTERNAL_API_TOKEN=${XS_AGENT_TOKEN}

>>> 2) 在控制面后台「节点管理」新增/更新该节点（POST /admin/nodes）<<<
id=${XS_NODE_ID}
endpoint=${PUBLIC_IP}:${WG_PORT}
agent_host=${PUBLIC_IP}
agent_port=${XS_AGENT_PORT}
server_public_key=${SERVER_PUB}
params={"Jc":"${JC}","Jmin":"${JMIN}","Jmax":"${JMAX}","S1":"${S1}","S2":"${S2}","H1":"${H1}","H2":"${H2}","H3":"${H3}","H4":"${H4}"}
================================================================
EOF
