# Windows 连接排障

## 现象判断

如果官网登录、VIP 同步、节点列表都正常但公网 IP 未变化，优先排查短期 VLESS 租约、Reality 参数、sing-box 启动、TUN 权限和系统代理。

## 本地敏感数据

节点配置只会写入随机命名的临时文件，内核就绪后立即删除；应用启动、断开和退出时也会清理遗留文件。客户端不持久化 sing-box 输出，避免服务器地址、UUID 或 Reality 参数进入本地日志。

## 全局模式检查

用管理员身份运行客户端。点击“全局”模式连接后，在 PowerShell 执行：

```powershell
Get-NetAdapter | Where-Object {$_.Name -like "*xingsui*" -or $_.InterfaceDescription -like "*Wintun*"}
route print
Get-DnsClientServerAddress
```

预期结果：

- 能看到 Wintun/TUN 相关网卡或路由变化。
- 连接状态不能停留在“连接中”，且虚拟网卡应正常出现。

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

如果 `7897/9191` 没有监听，说明 sing-box 没有正常启动；先核对安装包内核和 Wintun 的固定 SHA-256，再检查系统安全软件拦截记录。

## 服务端同步检查

确认配置接口签发的是尚未到期的 Windows VLESS 租约，并在对应节点检查 VLESS 入站、Reality 握手和该租约的用户级 UUID。客户端本地端口正常但没有出口流量时，再排查 SNI、public key、short ID、节点防火墙和中国大陆链路可达性。
