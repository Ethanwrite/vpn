Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$TauriDir = Join-Path $Root "src-tauri"
$SingBox = Join-Path $TauriDir "binaries\sing-box-x86_64-pc-windows-msvc.exe"
$Wintun = Join-Path $TauriDir "resources\wintun.dll"

Write-Host "Xingsui Windows build"
Write-Host "Project: $Root"

if (!(Test-Path $SingBox)) {
  throw "Missing sing-box sidecar: $SingBox. Use an AmneziaWG-capable sing-box build."
}

if (!(Test-Path $Wintun)) {
  throw "Missing wintun.dll: $Wintun. Download Wintun and copy amd64\wintun.dll here."
}

if (!(Get-Command node -ErrorAction SilentlyContinue)) {
  throw "Node.js is not installed. Install Node.js 20 LTS first."
}

if (!(Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "npm is not installed. Install Node.js 20 LTS first."
}

if (!(Get-Command rustup -ErrorAction SilentlyContinue)) {
  throw "Rust is not installed. Install rustup first: https://rustup.rs/"
}

Push-Location $Root
try {
  rustup target add x86_64-pc-windows-msvc
  npm install
  npm run tauri build -- --target x86_64-pc-windows-msvc
  Write-Host ""
  Write-Host "Build finished. Check:"
  Write-Host "  src-tauri\target\x86_64-pc-windows-msvc\release\bundle\nsis"
  Write-Host "  src-tauri\target\x86_64-pc-windows-msvc\release\bundle\msi"
} finally {
  Pop-Location
}
