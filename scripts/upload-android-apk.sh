#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
apk="${1:-${repo_root}/amneziawg-android/ui/build/outputs/apk/release/ui-release.apk}"

[[ -f "$apk" ]] || { echo "APK not found: $apk" >&2; exit 2; }

expected_code="$(sed -n 's/^amneziawgVersionCode=//p' "${repo_root}/amneziawg-android/gradle.properties")"
expected_name="$(sed -n 's/^amneziawgVersionName=//p' "${repo_root}/amneziawg-android/gradle.properties")"

aapt="${ANDROID_AAPT:-}"
if [[ -z "$aapt" ]]; then
  android_home="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
  [[ -n "$android_home" ]] || { echo "Set ANDROID_HOME, ANDROID_SDK_ROOT, or ANDROID_AAPT" >&2; exit 2; }
  aapt="$(find "${android_home}/build-tools" -type f -name aapt 2>/dev/null | sort -V | tail -n 1)"
fi
[[ -x "$aapt" ]] || { echo "aapt not found: $aapt" >&2; exit 2; }

badging="$($aapt dump badging "$apk" | head -n 1)"
actual_code="$(sed -nE "s/.*versionCode='([0-9]+)'.*/\1/p" <<<"$badging")"
actual_name="$(sed -nE "s/.*versionName='([^']+)'.*/\1/p" <<<"$badging")"
[[ "$actual_code" == "$expected_code" && "$actual_name" == "$expected_name" ]] || {
  echo "Refusing upload: APK is ${actual_name} (${actual_code}), expected ${expected_name} (${expected_code})" >&2
  exit 1
}

host="${XINGSUI_CONTROL_HOST:?Set XINGSUI_CONTROL_HOST}"
ssh_key="${XINGSUI_SSH_KEY:?Set XINGSUI_SSH_KEY}"
known_hosts="${XINGSUI_KNOWN_HOSTS:?Set XINGSUI_KNOWN_HOSTS to a pinned known_hosts file}"
ssh_user="${XINGSUI_CONTROL_USER:-root}"
remote_path="/opt/xingsui/download/xingsui.apk"
ssh_options=(-i "$ssh_key" -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$known_hosts")

local_sha="$(shasum -a 256 "$apk" | awk '{print $1}')"
scp "${ssh_options[@]}" "$apk" "${ssh_user}@${host}:${remote_path}.tmp"
remote_sha="$(ssh "${ssh_options[@]}" "${ssh_user}@${host}" "mv '${remote_path}.tmp' '${remote_path}' && chmod 0644 '${remote_path}' && sha256sum '${remote_path}' | awk '{print \$1}'")"
[[ "$local_sha" == "$remote_sha" ]] || { echo "Remote APK checksum mismatch" >&2; exit 1; }

echo "Uploaded Android ${actual_name} (${actual_code}): https://xingsui.org/download/android"
echo "SHA-256: ${local_sha}"
