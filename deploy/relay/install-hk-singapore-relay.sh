#!/usr/bin/env bash
# Install the Hong Kong-to-Singapore relay on the control-plane host (64.90.24.84).
#
# Docker sets the filter FORWARD policy to DROP. An accept verdict in a separate
# nftables base chain does not prevent a later base chain on the same hook from
# dropping the packet, so permits must also be installed in DOCKER-USER.
#
# The installer is idempotent. Rollback instructions are printed at the end.
set -euo pipefail

UPSTREAM_IP="61.13.236.31"      # Singapore landing node (SSH port 20020)
AWG_LISTEN_PORT=4500            # Public relay ingress
AWG_UPSTREAM_PORT=51820
VLESS_LISTEN_PORT=10444
VLESS_UPSTREAM_PORT=10443

NFT_FILE=/etc/xingsui/xingsui-singapore-relay.nft
UNIT=/etc/systemd/system/xingsui-singapore-relay.service

echo "==> 1/5 Installing the nftables relay table"
mkdir -p /etc/xingsui
cat > "$NFT_FILE" <<EOF
# Hong Kong control plane to Singapore relay.
# This table does not modify Docker's ip nat or ip filter tables.
table ip xingsui_singapore_relay {
    chain prerouting {
        type nat hook prerouting priority dstnat - 10; policy accept;
        udp dport ${AWG_LISTEN_PORT} dnat to ${UPSTREAM_IP}:${AWG_UPSTREAM_PORT}
        tcp dport ${VLESS_LISTEN_PORT} dnat to ${UPSTREAM_IP}:${VLESS_UPSTREAM_PORT}
    }

    chain postrouting {
        type nat hook postrouting priority srcnat + 10; policy accept;
        ip daddr ${UPSTREAM_IP} udp dport ${AWG_UPSTREAM_PORT} masquerade
        ip daddr ${UPSTREAM_IP} tcp dport ${VLESS_UPSTREAM_PORT} masquerade
    }
}
EOF
nft -c -f "$NFT_FILE"
echo "    Syntax OK"

echo "==> 2/5 Installing the systemd unit and DOCKER-USER replay"
cat > "$UNIT" <<EOF
[Unit]
Description=Xingsui Hong Kong to Singapore relay
After=network-online.target docker.service
Wants=network-online.target
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=-/usr/sbin/nft delete table ip xingsui_singapore_relay
ExecStart=/usr/sbin/nft -f ${NFT_FILE}
# Docker's default FORWARD policy is DROP, so permits belong in DOCKER-USER.
# Delete before insert to keep repeated runs idempotent.
ExecStart=/usr/local/sbin/xingsui-relay-docker-user.sh add
ExecReload=/bin/sh -c '/usr/sbin/nft delete table ip xingsui_singapore_relay 2>/dev/null || true; /usr/sbin/nft -f ${NFT_FILE}; /usr/local/sbin/xingsui-relay-docker-user.sh add'
ExecStop=-/usr/sbin/nft delete table ip xingsui_singapore_relay
ExecStop=-/usr/local/sbin/xingsui-relay-docker-user.sh del

[Install]
WantedBy=multi-user.target
EOF

echo "==> 3/5 Installing the DOCKER-USER rule helper"
cat > /usr/local/sbin/xingsui-relay-docker-user.sh <<EOF
#!/usr/bin/env bash
# Permit Hong Kong-to-Singapore traffic in Docker's DOCKER-USER chain.
set -u
UPSTREAM_IP="${UPSTREAM_IP}"
AWG_UPSTREAM_PORT=${AWG_UPSTREAM_PORT}
VLESS_UPSTREAM_PORT=${VLESS_UPSTREAM_PORT}

rules=(
  "-d \${UPSTREAM_IP}/32 -p udp --dport \${AWG_UPSTREAM_PORT} -j ACCEPT"
  "-s \${UPSTREAM_IP}/32 -p udp --sport \${AWG_UPSTREAM_PORT} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT"
  "-d \${UPSTREAM_IP}/32 -p tcp --dport \${VLESS_UPSTREAM_PORT} -j ACCEPT"
  "-s \${UPSTREAM_IP}/32 -p tcp --sport \${VLESS_UPSTREAM_PORT} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT"
)

case "\${1:-add}" in
  add)
    for r in "\${rules[@]}"; do
      # Delete before insert so the rule is unique.
      iptables -D DOCKER-USER \$r 2>/dev/null || true
      iptables -I DOCKER-USER \$r
    done
    ;;
  del)
    for r in "\${rules[@]}"; do
      iptables -D DOCKER-USER \$r 2>/dev/null || true
    done
    ;;
esac
EOF
chmod 0755 /usr/local/sbin/xingsui-relay-docker-user.sh

echo "==> 4/5 Enabling and starting the relay"
sysctl -w net.ipv4.ip_forward=1 >/dev/null
grep -q '^net.ipv4.ip_forward=1' /etc/sysctl.d/99-xingsui-relay.conf 2>/dev/null \
  || echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-xingsui-relay.conf
systemctl daemon-reload
systemctl enable --now xingsui-singapore-relay >/dev/null 2>&1 || systemctl restart xingsui-singapore-relay
systemctl is-active xingsui-singapore-relay

echo "==> 5/5 Verifying the relay"
nft list chain ip xingsui_singapore_relay prerouting
iptables -S DOCKER-USER | grep -c "${UPSTREAM_IP}" | xargs -I{} echo "DOCKER-USER rule count: {} (expected: 4)"

cat <<'NOTE'

Installation complete. On the Singapore host (61.13.236.31, SSH port 20020), allow relay traffic:
  ufw allow from 64.90.24.84 to any port 51820 proto udp comment 'HK relay'
  ufw allow from 64.90.24.84 to any port 10443 proto tcp comment 'Xingsui VLESS from HK relay'

Rollback:
  systemctl disable --now xingsui-singapore-relay
  This removes the nftables table and the DOCKER-USER rules.
NOTE
