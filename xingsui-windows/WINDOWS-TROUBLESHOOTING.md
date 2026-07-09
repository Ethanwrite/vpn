# Windows 连接排障

## 现象判断

如果官网登录、VIP 同步、节点列表都正常，但节点服务器 `awg show awg0 latest-handshakes` 中该用户 peer 一直为 `0`，说明 Windows 客户端还没有向节点发出有效 UDP 握手。此时优先排查本机内核启动、TUN 权限、系统代理和下发配置。

## 客户端日志

新版客户端会把 sing-box 输出写入：

```powershell
$env:APPDATA\com.xingsui.vpn.desktop\config\sing-box.log
```

同时会生成当前运行配置：

```powershell
$env:APPDATA\com.xingsui.vpn.desktop\config\config.json
```

反馈问题时优先提供 `sing-box.log` 末尾 80 行。不要公开 `config.json` 里的 `private_key`。

## 全局模式检查

用管理员身份运行客户端。点击“全局”模式连接后，在 PowerShell 执行：

```powershell
Get-NetAdapter | Where-Object {$_.Name -like "*xingsui*" -or $_.InterfaceDescription -like "*Wintun*"}
route print
Get-DnsClientServerAddress
```

预期结果：

- 能看到 Wintun/TUN 相关网卡或路由变化。
- `sing-box.log` 不应出现 `operation not permitted`、`wintun.dll`、`CreateTUN`、`auto_route` 相关错误。

## 代理模式检查

点击“代理”模式连接后执行：

```powershell
netstat -ano | findstr 7897
netstat -ano | findstr 9191
curl.exe -x http://127.0.0.1:7897 https://api.ipify.org
```

预期结果：

- `7897` 本地混合代理端口处于监听状态。
- `9191` Clash API 端口处于监听状态。
- `curl -x` 返回的公网 IP 应为当前选择节点的出口 IP。

如果 `7897/9191` 没有监听，说明 sing-box 没有正常启动，直接看 `sing-box.log`。

## 服务端同步检查

在对应节点上执行：

```bash
awg showconf awg0 | grep -E '^(Jc|Jmin|Jmax|S1|S2|H1|H2|H3|H4)'
awg show awg0 latest-handshakes
awg show awg0 transfer
```

预期结果：

- H1-H4 与控制面数据库 `vpn_nodes.params_json` 一致。
- 客户端连接后，该 peer 的 latest-handshake 从 `0` 变成当前时间戳。
- transfer 字节数开始增长。

如果本地 `7897/9191` 正常，但服务端 latest-handshake 仍为 `0`，再排查 UDP 出口、防火墙、安全软件、运营商链路或内核生成的 WireGuard endpoint 配置。
