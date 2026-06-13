#!/usr/bin/env python3
"""星隧 VPN 边缘节点轻量 Agent（仅标准库，无第三方依赖）。

职责：
  - 接受控制面经 X-Internal-Token 鉴权的 peer 增删请求（awg set ...）。
  - 周期性向控制面 /internal/nodes/heartbeat 上报负载与流量。
配置来自环境变量（建议写入 /etc/xingsui/agent.env，由 systemd 加载）：
  XS_AGENT_TOKEN          与控制面 INTERNAL_API_TOKEN 完全一致（必填）
  XS_NODE_ID              本节点在 vpn_nodes 表中的 id（必填）
  XS_CONTROL_PLANE_URL    控制面基址，如 https://xingsuico.com（必填，用于心跳）
  XS_AGENT_PORT           监听端口（默认 51821）
  XS_WG_IFACE             AmneziaWG 接口名（默认 awg0）
  XS_WG_TOOL              awg / wg（默认 awg）
  XS_HEARTBEAT_INTERVAL   心跳间隔秒（默认 30）
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
import subprocess
import threading
import time
import urllib.request

AGENT_VERSION = "1.0.0"


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def token() -> str:
    return env("XS_AGENT_TOKEN")


def iface() -> str:
    return env("XS_WG_IFACE", "awg0")


def wg_tool() -> str:
    return env("XS_WG_TOOL", "awg")


def run(args: list[str], input_text: str | None = None) -> str:
    result = subprocess.run(args, input=input_text, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def add_peer(public_key: str, allowed_ip: str) -> None:
    ip = allowed_ip.split("/")[0]
    run([wg_tool(), "set", iface(), "peer", public_key, "allowed-ips", f"{ip}/32"])


def remove_peer(public_key: str) -> None:
    run([wg_tool(), "set", iface(), "peer", public_key, "remove"])


def collect_status() -> dict[str, float]:
    peer_count = rx = tx = 0
    try:
        dump = run([wg_tool(), "show", iface(), "dump"])
        lines = [ln for ln in dump.splitlines() if ln.strip()]
        for line in lines[1:]:  # 第一行为接口自身
            cols = line.split("\t")
            peer_count += 1
            if len(cols) >= 7:
                rx += int(cols[5] or 0)
                tx += int(cols[6] or 0)
    except Exception:
        pass
    cpu_load = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    return {
        "peer_count": peer_count,
        "rx_bytes": rx,
        "tx_bytes": tx,
        "cpu_load": cpu_load,
        "mem_used_percent": mem_used_percent(),
    }


def mem_used_percent() -> float:
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, _, rest = line.partition(":")
                info[key.strip()] = int(rest.strip().split()[0])
        total = info.get("MemTotal", 0)
        available = info.get("MemAvailable", 0)
        if total <= 0:
            return 0.0
        return round((total - available) / total * 100, 2)
    except Exception:
        return 0.0


def heartbeat_loop() -> None:
    base = env("XS_CONTROL_PLANE_URL").rstrip("/")
    node_id = env("XS_NODE_ID")
    interval = int(env("XS_HEARTBEAT_INTERVAL", "30") or "30")
    if not base or not node_id:
        return
    url = f"{base}/internal/nodes/heartbeat"
    while True:
        try:
            payload = {"node_id": node_id, "agent_version": AGENT_VERSION, **collect_status()}
            body = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(url, data=body, method="POST")
            request.add_header("Content-Type", "application/json")
            request.add_header("X-Internal-Token", token())
            urllib.request.urlopen(request, timeout=8).read()
        except Exception:
            pass
        time.sleep(interval)


class Handler(BaseHTTPRequestHandler):
    server_version = f"xingsui-agent/{AGENT_VERSION}"

    def log_message(self, *_args) -> None:  # 静默默认访问日志
        return

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = token()
        provided = (self.headers.get("X-Internal-Token") or "").strip()
        return bool(expected) and bool(provided) and hmac.compare_digest(provided, expected)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._send(200, {"status": "ok", "version": AGENT_VERSION})
            return
        if not self._authorized():
            self._send(401, {"detail": "unauthorized"})
            return
        if self.path == "/status":
            self._send(200, {"version": AGENT_VERSION, **collect_status()})
            return
        self._send(404, {"detail": "not found"})

    def do_POST(self) -> None:
        if not self._authorized():
            self._send(401, {"detail": "unauthorized"})
            return
        try:
            payload = self._read_json()
        except (json.JSONDecodeError, ValueError):
            self._send(400, {"detail": "invalid json"})
            return
        try:
            if self.path == "/peer/add":
                add_peer(payload["public_key"], payload["allowed_ip"])
                self._send(200, {"status": "added"})
            elif self.path == "/peer/remove":
                remove_peer(payload["public_key"])
                self._send(200, {"status": "removed"})
            else:
                self._send(404, {"detail": "not found"})
        except KeyError as exc:
            self._send(422, {"detail": f"missing field: {exc}"})
        except subprocess.CalledProcessError as exc:
            self._send(503, {"detail": (exc.stderr or str(exc)).strip()})


def main() -> None:
    if not token():
        raise SystemExit("XS_AGENT_TOKEN is required")
    port = int(env("XS_AGENT_PORT", "51821") or "51821")
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)  # noqa: S104
    print(f"xingsui agent listening on :{port} iface={iface()}")
    server.serve_forever()


if __name__ == "__main__":
    main()
