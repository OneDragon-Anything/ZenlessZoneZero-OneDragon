# ZZZ OD Daemon 启动脚本
#
# 使用方式:
#   .\start_daemon.ps1              # 使用默认端口（8001）
#   .\start_daemon.ps1 -Port 9001   # 指定端口

param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 23002
)

$ErrorActionPreference = "Stop"

# 获取项目根目录
$ProjectRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent
$DaemonScript = Join-Path $ProjectRoot "tools\mcp\daemon\zzz_od_daemon.py"

Write-Host "============================================================"  -ForegroundColor Cyan
Write-Host "ZZZ OD Daemon MCP Server" -ForegroundColor Cyan
Write-Host "============================================================"  -ForegroundColor Cyan
Write-Host ""
Write-Host "项目根目录: $ProjectRoot"
Write-Host "Daemon 脚本: $DaemonScript"
Write-Host "Listen URL: http://${HostName}:${Port}/mcp"
Write-Host ""
Write-Host "============================================================"  -ForegroundColor Cyan
Write-Host ""

# 检查脚本文件
if (-not (Test-Path $DaemonScript)) {
    Write-Host "[ERROR] Daemon 脚本不存在: $DaemonScript" -ForegroundColor Red
    exit 1
}

# 切换到项目根目录
Set-Location $ProjectRoot

# 执行 daemon 脚本
try {
    uv run python $DaemonScript --host $HostName --port $Port
} catch {
    Write-Host "[ERROR] Daemon 启动失败: $_" -ForegroundColor Red
    exit 1
}
