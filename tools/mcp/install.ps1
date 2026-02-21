# ZZZ OD MCP Server Installation Script
#
# Usage:
#   .\install.ps1                      # Install (default port 23001)
#   .\install.ps1 -Port 9001           # Specify port
#   .\install.ps1 -Uninstall           # Uninstall
#   .\install.ps1 -Check               # Check status

param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 23001,
    [switch]$Uninstall,
    [switch]$Check
)

$ErrorActionPreference = "Stop"

# Get project root
$ProjectRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent
$ServerScript = "src\zzz_mcp\zzz_mcp_server.py"

# Claude Code config path
$ConfigPath = "$env:USERPROFILE\.claude.json"
$ServerKey = "zzz_od"

function Install-Server {
    param([string]$HostName, [int]$Port)

    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host "ZZZ OD MCP Server Installation" -ForegroundColor Cyan
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Project Root: $ProjectRoot"
    Write-Host "Server Script: $ServerScript"
    Write-Host "Listen URL: http://${HostName}:${Port}/mcp"
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host ""

    # Check script file
    $ScriptPath = Join-Path $ProjectRoot $ServerScript
    if (-not (Test-Path $ScriptPath)) {
        Write-Host "[ERROR] Server script not found: $ScriptPath" -ForegroundColor Red
        return $false
    }

    # Use claude mcp command to add server
    $McpUrl = "http://${HostName}:${Port}/mcp"

    Write-Host "Adding MCP server to Claude Code..." -ForegroundColor Cyan
    $Cmd = "claude mcp add --transport http $ServerKey $McpUrl"
    Write-Host "[CMD] $Cmd" -ForegroundColor Yellow

    try {
        $Output = Invoke-Expression $Cmd 2>&1
        Write-Host $Output

        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "[SUCCESS] $ServerKey installed to Claude Code" -ForegroundColor Green
            Write-Host ""
            Write-Host "Next steps:" -ForegroundColor Cyan
            Write-Host "  1. Start MCP Server: uv run python $ServerScript --host $HostName --port $Port"
            Write-Host "  2. Or use Daemon to manage: .\tools\mcp\daemon\start_daemon.ps1"
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

function Uninstall-Server {
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host "ZZZ OD MCP Server Uninstallation" -ForegroundColor Cyan
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host ""

    Write-Host "Removing MCP server from Claude Code..." -ForegroundColor Cyan
    $Cmd = "claude mcp remove $ServerKey"
    Write-Host "[CMD] $Cmd" -ForegroundColor Yellow

    try {
        $Output = Invoke-Expression $Cmd 2>&1
        Write-Host $Output

        if ($LASTEXITCODE -eq 0) {
            Write-Host "[SUCCESS] $ServerKey uninstalled" -ForegroundColor Green
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
    Write-Host "ZZZ OD MCP Server Installation Status" -ForegroundColor Cyan
    Write-Host "============================================================"  -ForegroundColor Cyan
    Write-Host ""

    $AllGood = $true

    # Check script file
    $ScriptPath = Join-Path $ProjectRoot $ServerScript
    if (Test-Path $ScriptPath) {
        Write-Host "[OK] Server script exists: $ScriptPath" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Server script not found: $ScriptPath" -ForegroundColor Red
        $AllGood = $false
    }

    # Check port
    $PortCheck = netstat -ano | Select-String ":$($Port).*LISTENING"
    if ($PortCheck) {
        Write-Host "[OK] Port $Port is listening" -ForegroundColor Green
        Write-Host $PortCheck -ForegroundColor Cyan
    } else {
        Write-Host "[WARN] Port $Port not listening, Server may not be started" -ForegroundColor Yellow
    }

    # Check claude mcp list
    Write-Host ""
    Write-Host "Checking Claude Code MCP servers..." -ForegroundColor Cyan
    $Cmd = "claude mcp list"
    Write-Host "[CMD] $Cmd" -ForegroundColor Yellow
    try {
        $Output = Invoke-Expression $Cmd 2>&1
        Write-Host $Output

        if ($Output -match $ServerKey) {
            Write-Host "[OK] $ServerKey is configured in Claude Code" -ForegroundColor Green
        } else {
            Write-Host "[WARN] $ServerKey not found in Claude Code" -ForegroundColor Yellow
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
    $Success = Uninstall-Server
    if ($Success) { exit 0 } else { exit 1 }
}

# Default: install
$Success = Install-Server -HostName $HostName -Port $Port
if ($Success) { exit 0 } else { exit 1 }
