# Create ZZZ OD MCP Server Startup Shortcut
#
# Creates a shortcut in the Windows Startup folder so the main MCP server (port 23001)
# starts automatically after login, without being spawned by daemon.
# Independent of the daemon startup shortcut (tools/mcp/daemon/create_startup_shortcut.ps1);
# both can coexist: daemon manages server lifecycle, this shortcut keeps the server ready
# right after login.

$ErrorActionPreference = "Stop"

# This script lives in tools/mcp/, go up 2 levels to project root
$ProjectRoot = Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent
$StartScript = Join-Path $ProjectRoot "tools\mcp\start_mcp_server.ps1"

# Startup folder
$StartupFolder = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$ShortcutPath = Join-Path $StartupFolder "ZZZ OD MCP Server.lnk"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "ZZZ OD MCP Server - Startup Shortcut Creator" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project Root: $ProjectRoot"
Write-Host "Start Script: $StartScript"
Write-Host "Shortcut Path: $ShortcutPath"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if start_mcp_server.ps1 exists
if (-not (Test-Path $StartScript)) {
    Write-Host "[ERROR] start_mcp_server.ps1 not found: $StartScript" -ForegroundColor Red
    exit 1
}

# Create WScript.Shell object
$WshShell = New-Object -ComObject WScript.Shell

# Create shortcut
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartScript`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = "ZZZ OD MCP Server - backend main server (game operation)"
$Shortcut.Save()

# Release COM object
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($WshShell) | Out-Null

Write-Host "[SUCCESS] Shortcut created!" -ForegroundColor Green
Write-Host ""
Write-Host "Shortcut location: $ShortcutPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "ZZZ OD MCP Server will now automatically start when you log in." -ForegroundColor Green
Write-Host ""
Write-Host "To remove:" -ForegroundColor Yellow
Write-Host "  Delete the shortcut file: $ShortcutPath"
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
