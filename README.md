# 星隧 VPN

星隧 VPN 商业化客户端与控制面项目，包含 Android 客户端、Windows 客户端原型、FastAPI 控制面、官网页面、管理后台和部署脚本。

## 目录

- `amneziawg-android/`：Android 客户端与后端控制面源码。
- `amneziawg-android/backend/`：FastAPI API、官网、Admin 后台、订单/VIP/节点管理。
- `deploy/`：控制面与边缘节点部署配置。
- `xingsui-windows/`：Tauri + React Windows 客户端。
- `scripts/`：发布辅助脚本。

## 本地敏感文件

以下文件不会提交到仓库，需要在本地或服务器单独配置：

- `.env` / `*.env`
- Android release keystore 与密码文件
- 服务器密码、节点初始化输出
- APK/Windows 安装包等构建产物
- 微信/支付宝收款码图片

## Android 构建

```bash
cd amneziawg-android
./gradlew :ui:assembleRelease -PxingsuiReleaseApiBaseUrl=https://xingsuico.com/api
```

## 后端部署

控制面部署配置位于 `deploy/control-plane/`。复制 `.env.example` 为 `.env` 后填写真实数据库密码、Admin 密码、内部通信 token、节点参数等。

```bash
cd deploy/control-plane
docker compose up -d --build
```

## Windows 构建

Windows 客户端需要在 Windows/MSVC 环境构建，并提前放置：

- `xingsui-windows/src-tauri/binaries/sing-box-x86_64-pc-windows-msvc.exe`
- `xingsui-windows/src-tauri/resources/wintun.dll`

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1
```
