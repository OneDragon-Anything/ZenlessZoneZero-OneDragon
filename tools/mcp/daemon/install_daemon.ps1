# ZZZ OD Daemon Installation Script
#
# Usage:
#   .\install_daemon.ps1              # Install (default port 23002)
#   .\install_daemon.ps1 -Port 9001   # Specify port
#   .\install_daemon.ps1 -Uninstall   # Uninstall
#   .\install_daemon.ps1 -Check       # Check status

param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 23002,
    [switch]$Uninstall,
    [switch]$Check
)

$ErrorActionPreference = "Stop"

# Get project root
$ProjectRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent
$DaemonScript = Join-Path $ProjectRoot "tools\mcp\daemon\zzz_od_daemon.py"

$DaemonKey = "zzz_od_daemon"

function Install-Daemon {
    param([string]$HostName, [int]$Port)

    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host "ZZZ OD Daemon MCP Server Installation" -ForegroundColor Cyan
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Project Root: $ProjectRoot"
    Write-Host "Daemon Script: $DaemonScript"
    Write-Host "Listen URL: http://${HostName}:${Port}/mcp"
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host ""

    # Check script file
    if (-not (Test-Path $DaemonScript)) {
        Write-Host "[ERROR] Daemon script not found: $DaemonScript" -ForegroundColor Red
        return $false
    }

    # Use claude mcp command to add daemon
    $McpUrl = "http://${HostName}:${Port}/mcp"

    Write-Host "Adding Daemon MCP server to Claude Code..." -ForegroundColor Cyan
    $Cmd = "claude mcp add --transport http $DaemonKey $McpUrl"
    Write-Host "[CMD] $Cmd" -ForegroundColor Yellow

    try {
        $Output = Invoke-Expression $Cmd 2>&1
        Write-Host $Output

        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "[SUCCESS] $DaemonKey installed to Claude Code" -ForegroundColor Green
            Write-Host ""
            Write-Host "Next steps:" -ForegroundColor Cyan
            Write-Host "  1. Start Daemon: .\start_daemon.ps1"
            Write-Host "  2. Use Daemon tools in Claude Code to manage ZZZ OD MCP Server"
            Write-Host ""
            return $true
        } else {
            Write-Host "[ERROR] Installation failed" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "[ERROR] Installation failed: $_" -ForegroundColor Red
        return $false
    }
}

function Uninstall-Daemon {
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host "ZZZ OD Daemon MCP Server Uninstallation" -ForegroundColor Cyan
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host ""

    Write-Host "Removing Daemon MCP server from Claude Code..." -ForegroundColor Cyan
    $Cmd = "claude mcp remove $DaemonKey"
    Write-Host "[CMD] $Cmd" -ForegroundColor Yellow

    try {
        $Output = Invoke-Expression $Cmd 2>&1
        Write-Host $Output

        if ($LASTEXITCODE -eq 0) {
            Write-Host "[SUCCESS] $DaemonKey uninstalled" -ForegroundColor Green
            return $true
        } else {
            Write-Host "[WARN] Uninstall command completed with errors" -ForegroundColor Yellow
            return $true
        }
    } catch {
        Write-Host "[ERROR] Uninstall failed: $_" -ForegroundColor Red
        return $false
    }
}

function Check-Installation {
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host "ZZZ OD Daemon MCP Server Installation Status" -ForegroundColor Cyan
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host ""

    $AllGood = $true

    # Check script file
    if (Test-Path $DaemonScript) {
        Write-Host "[OK] Daemon script exists: $DaemonScript" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Daemon script not found: $DaemonScript" -ForegroundColor Red
        $AllGood = $false
    }

    # Check port
    $PortCheck = netstat -ano | Select-String ":$($Port).*LISTENING"
    if ($PortCheck) {
        Write-Host "[OK] Port $Port is listening" -ForegroundColor Green
        Write-Host $PortCheck -ForegroundColor Cyan
    } else {
        Write-Host "[WARN] Port $Port not listening, Daemon may not be started" -ForegroundColor Yellow
    }

    # Check claude mcp list
    Write-Host ""
    Write-Host "Checking Claude Code MCP servers..." -ForegroundColor Cyan
    $Cmd = "claude mcp list"
    Write-Host "[CMD] $Cmd" -ForegroundColor Yellow
    try {
        $Output = Invoke-Expression $Cmd 2>&1
        Write-Host $Output

        if ($Output -match $DaemonKey) {
            Write-Host "[OK] $DaemonKey is configured in Claude Code" -ForegroundColor Green
        } else {
            Write-Host "[WARN] $DaemonKey not found in Claude Code" -ForegroundColor Yellow
            $AllGood = $false
        }
    } catch {
        Write-Host "[WARN] Could not check Claude Code config" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host ""

    return $AllGood
}

# Main logic
if ($Check) {
    $Success = Check-Installation
    if ($Success) { exit 0 } else { exit 1 }
}

if ($Uninstall) {
    $Success = Uninstall-Daemon
    if ($Success) { exit 0 } else { exit 1 }
}

# Default: install
$Success = Install-Daemon -HostName $HostName -Port $Port
if ($Success) { exit 0 } else { exit 1 }
