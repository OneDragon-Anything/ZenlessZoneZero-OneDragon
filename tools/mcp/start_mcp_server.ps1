# ZZZ OD Main MCP Server startup script
#
# Starts the backend main server (zzz_od.backend.entry.server, default port 23001),
# redirecting logs to .debug/zzz_od_mcp/main_server.log (same as GUI / daemon start tool).
# The startup shortcut (create_mcp_server_startup_shortcut.ps1) calls this script with a
# hidden window; main server is started directly in the login session (Session 1),
# not spawned via daemon.
#
# Usage:
#   .\start_mcp_server.ps1              # default host 127.0.0.1 / port 23001
#   .\start_mcp_server.ps1 -Port 23002  # custom port

param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 23001
)

$ErrorActionPreference = "Stop"

# This script lives in tools/mcp/, go up 2 levels to project root
$ProjectRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "ZZZ OD Main MCP Server" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project Root: $ProjectRoot"
Write-Host "Listen URL: http://${HostName}:${Port}/mcp"
Write-Host ""

# Log path (same as GUI / daemon start tool); ensure dir exists
$LogPath = Join-Path $ProjectRoot ".debug\zzz_od_mcp\main_server.log"
$LogDir = Split-Path $LogPath -Parent
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}
Write-Host "Log: $LogPath"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Switch to project root
Set-Location $ProjectRoot

# --env-file 仅在 .env 是普通文件时传(目录或缺失都不传;缺失时 uv 启动失败导致自启起不来)
$EnvArg = if (Test-Path ".env" -PathType Leaf) { "--env-file .env" } else { "" }
try {
    # Redirect via cmd /c: merge stdout/stderr into one file as raw bytes (matches
    # daemon subprocess.Popen(stdout=file, stderr=STDOUT); avoids PS native-redirect encoding issues)
    cmd /c "uv run $EnvArg python -m zzz_od.backend.entry.server --host $HostName --port $Port > `"$LogPath`" 2>&1"
    # cmd /c 的非零退出码不会触发 catch(ErrorActionPreference 对原生命令无效),手动检查避免启动失败仍报成功
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Main MCP Server exited with code $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
} catch {
    Write-Host "[ERROR] Main MCP Server failed to start: $_" -ForegroundColor Red
    exit 1
}
