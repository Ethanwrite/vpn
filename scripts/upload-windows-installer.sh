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

host="${XINGSUI_CONTROL_HOST:-212.50.232.111}"
remote_name="${XINGSUI_WINDOWS_REMOTE_NAME:-xingsui-windows-setup.exe}"
remote_path="/opt/xingsui/download/${remote_name}"

if [[ -z "${SSHPASS:-}" ]]; then
  echo "Set SSHPASS before running, or run through Codex with the deploy password loaded." >&2
  exit 2
fi

sshpass -e ssh -o StrictHostKeyChecking=no "root@${host}" "mkdir -p /opt/xingsui/download"
sshpass -e scp -o StrictHostKeyChecking=no "$installer" "root@${host}:${remote_path}.tmp"
sshpass -e ssh -o StrictHostKeyChecking=no "root@${host}" "mv '${remote_path}.tmp' '${remote_path}' && chmod 0644 '${remote_path}' && ls -lh '${remote_path}'"

echo "Uploaded: https://xingsuico.com/download/windows"
