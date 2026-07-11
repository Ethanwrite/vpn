#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/xingsui-windows-installer.exe" >&2
  exit 2
fi

installer="$1"
if [[ ! -f "$installer" ]]; then
  echo "Installer not found: $installer" >&2
  exit 1
fi

host="${XINGSUI_CONTROL_HOST:?Set XINGSUI_CONTROL_HOST}"
ssh_key="${XINGSUI_SSH_KEY:?Set XINGSUI_SSH_KEY}"
known_hosts="${XINGSUI_KNOWN_HOSTS:?Set XINGSUI_KNOWN_HOSTS to a pinned known_hosts file}"
ssh_user="${XINGSUI_CONTROL_USER:-root}"
remote_name="${XINGSUI_WINDOWS_REMOTE_NAME:-xingsui-windows-setup.exe}"
remote_path="/opt/xingsui/download/${remote_name}"

if [[ ! "$remote_name" =~ ^[A-Za-z0-9._-]+\.exe$ ]]; then
  echo "XINGSUI_WINDOWS_REMOTE_NAME must be a path-safe .exe filename" >&2
  exit 2
fi
[[ -f "$ssh_key" ]] || { echo "SSH key not found: $ssh_key" >&2; exit 2; }
[[ -f "$known_hosts" ]] || { echo "known_hosts file not found: $known_hosts" >&2; exit 2; }

ssh_options=(-i "$ssh_key" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$known_hosts")

ssh "${ssh_options[@]}" "${ssh_user}@${host}" "install -d -m 0755 /opt/xingsui/download"
scp "${ssh_options[@]}" "$installer" "${ssh_user}@${host}:${remote_path}.tmp"
ssh "${ssh_options[@]}" "${ssh_user}@${host}" "mv '${remote_path}.tmp' '${remote_path}' && chmod 0644 '${remote_path}' && ls -lh '${remote_path}'"

echo "Uploaded: https://xingsui.org/download/windows"
