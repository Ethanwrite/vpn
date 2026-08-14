# Windows Connectivity Troubleshooting

## Initial diagnosis

If website authentication, membership synchronization, and the node list work but the public IP does not change, inspect the short-lived VLESS lease, Reality parameters, sing-box startup, TUN privileges, and system proxy state.

## Local sensitive data

Node configuration is written only to a randomly named temporary file and removed as soon as the tunnel engine is ready. Startup, disconnect, and application exit also remove stale files. The client does not persist sing-box output, preventing server addresses, UUIDs, or Reality parameters from entering local logs.

## Global mode

Run the client as Administrator, connect in Global mode, and execute:

```powershell
Get-NetAdapter | Where-Object {$_.Name -like "*xingsui*" -or $_.InterfaceDescription -like "*Wintun*"}
route print
Get-DnsClientServerAddress
```

Expected results:

- A Wintun/TUN adapter or corresponding route changes are visible.
- The connection does not remain in a connecting state.
- The virtual adapter is enabled and has valid routes and DNS configuration.

## Proxy mode

Connect in Proxy mode and execute:

```powershell
netstat -ano | findstr 7897
netstat -ano | findstr 9191
curl.exe -x http://127.0.0.1:7897 https://api.ipify.org
```

Expected results:

- Local mixed-proxy port `7897` is listening.
- Clash API port `9191` is listening.
- The proxied request returns the selected node's egress IP.

If neither port is listening, sing-box did not start successfully. Verify the pinned SHA-256 values for the packaged engine and Wintun library, then inspect endpoint-security quarantine or block events.

## Server-side checks

Confirm that the configuration API issued an unexpired Windows VLESS lease. On the selected node, verify the VLESS inbound, Reality handshake, and presence of the lease-specific UUID. If local ports are healthy but traffic has no egress, inspect the SNI, Reality public key, short ID, firewall policy, DNS, and path reachability.
