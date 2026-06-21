#!/usr/bin/env bash
set -euo pipefail

# Hotfix for AmneziaWG data-plane "received message with unknown type".
# It regenerates H1-H4 in the 5..255 range, reloads awg0 without a full restart,
# and optionally updates vpn_nodes.params_json when DATABASE_URL and NODE_ID are set.

WG_IFACE="${WG_IFACE:-awg0}"
CONF="${CONF:-/etc/amnezia/amneziawg/${WG_IFACE}.conf}"
NODE_ID="${NODE_ID:-${XS_NODE_ID:-}}"
DATABASE_URL="${DATABASE_URL:-}"

[[ $EUID -eq 0 ]] || { echo "Please run as root"; exit 1; }
[[ -f "$CONF" ]] || { echo "Config not found: $CONF"; exit 1; }
command -v awg >/dev/null || { echo "awg command not found"; exit 1; }
command -v awg-quick >/dev/null || { echo "awg-quick command not found"; exit 1; }

rand_h() {
  echo $(( (RANDOM % 250) + 5 ))
}

gen_distinct_h() {
  local a b c d
  a=$(rand_h); b=$(rand_h); c=$(rand_h); d=$(rand_h)
  while [[ "$b" == "$a" ]]; do b=$(rand_h); done
  while [[ "$c" == "$a" || "$c" == "$b" ]]; do c=$(rand_h); done
  while [[ "$d" == "$a" || "$d" == "$b" || "$d" == "$c" ]]; do d=$(rand_h); done
  echo "$a $b $c $d"
}

extract_param() {
  local key="$1"
  awk -F '=' -v key="$key" '
    BEGIN { in_iface = 0 }
    /^\[Interface\]/ { in_iface = 1; next }
    /^\[/ { in_iface = 0 }
    in_iface && $1 ~ "^[[:space:]]*" key "[[:space:]]*$" {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2)
      print $2
      exit
    }
  ' "$CONF"
}

read -r H1 H2 H3 H4 <<<"$(gen_distinct_h)"
backup="${CONF}.bak.$(date +%Y%m%d%H%M%S)"
cp -a "$CONF" "$backup"

tmp="$(mktemp)"
awk -v h1="$H1" -v h2="$H2" -v h3="$H3" -v h4="$H4" '
  function emit_missing() {
    if (!seen_h1) print "H1 = " h1
    if (!seen_h2) print "H2 = " h2
    if (!seen_h3) print "H3 = " h3
    if (!seen_h4) print "H4 = " h4
  }
  BEGIN { in_iface = 0; flushed = 0 }
  /^\[Interface\]/ { in_iface = 1; print; next }
  /^\[/ && in_iface {
    emit_missing()
    flushed = 1
    in_iface = 0
    print
    next
  }
  in_iface && /^[[:space:]]*H1[[:space:]]*=/ { print "H1 = " h1; seen_h1 = 1; next }
  in_iface && /^[[:space:]]*H2[[:space:]]*=/ { print "H2 = " h2; seen_h2 = 1; next }
  in_iface && /^[[:space:]]*H3[[:space:]]*=/ { print "H3 = " h3; seen_h3 = 1; next }
  in_iface && /^[[:space:]]*H4[[:space:]]*=/ { print "H4 = " h4; seen_h4 = 1; next }
  { print }
  END {
    if (in_iface && !flushed) emit_missing()
  }
' "$CONF" >"$tmp"
install -m 600 "$tmp" "$CONF"
rm -f "$tmp"

echo "Updated H params in $CONF"
grep -E '^H[1-4][[:space:]]*=' "$CONF"

echo "Hot reloading ${WG_IFACE}"
awg syncconf "$WG_IFACE" <(awg-quick strip "$WG_IFACE")

PARAMS_JSON="$(
  CONF="$CONF" python3 - <<'PY'
import json
import os
import re

keys = ("Jc", "Jmin", "Jmax", "S1", "S2", "S3", "S4", "H1", "H2", "H3", "H4", "I1", "I2", "I3", "I4", "I5")
params = {}
in_iface = False
with open(os.environ["CONF"], encoding="utf-8") as fh:
    for raw in fh:
        line = raw.strip()
        if line == "[Interface]":
            in_iface = True
            continue
        if line.startswith("[") and line.endswith("]"):
            in_iface = False
        if not in_iface or "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        if key in keys and value:
            params[key] = value
print(json.dumps(params, separators=(",", ":")))
PY
)"

echo "params_json=${PARAMS_JSON}"

if [[ -n "$DATABASE_URL" && -n "$NODE_ID" ]]; then
  if command -v psql >/dev/null; then
    PSQL_URL="${DATABASE_URL/postgresql+psycopg:/postgresql:}"
    psql "$PSQL_URL" \
      --set=ON_ERROR_STOP=1 \
      --set=node_id="$NODE_ID" \
      --set=params="$PARAMS_JSON" \
      -c "update vpn_nodes set params_json = :'params', updated_at = now() where id = :'node_id';"
    echo "Database updated for node ${NODE_ID}"
  else
    echo "DATABASE_URL is set, but psql is not installed. Run this on the control plane database:"
    printf "update vpn_nodes set params_json = '%s', updated_at = now() where id = '%s';\n" \
      "${PARAMS_JSON//\'/\'\'}" "${NODE_ID//\'/\'\'}"
  fi
else
  echo "Database not updated because DATABASE_URL or NODE_ID is empty."
  echo "Run this on the control plane database:"
  printf "update vpn_nodes set params_json = '%s', updated_at = now() where id = '<NODE_ID>';\n" \
    "${PARAMS_JSON//\'/\'\'}"
fi

