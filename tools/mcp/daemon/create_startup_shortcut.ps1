# Create ZZZ OD Daemon Startup Shortcut
#
# This script creates a shortcut in the Windows Startup folder
# to automatically start ZZZ OD Daemon when user logs in.

$ErrorActionPreference = "Stop"

# Get paths
$ProjectRoot = Split-Path -Path (Split-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -Parent) -Parent
$StartDaemonScript = Join-Path $ProjectRoot "tools\mcp\daemon\start_daemon.ps1"

# Startup folder
$StartupFolder = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$ShortcutPath = Join-Path $StartupFolder "ZZZ OD Daemon.lnk"

Write-Host "============================================================"  -ForegroundColor Cyan
Write-Host "ZZZ OD Daemon - Startup Shortcut Creator" -ForegroundColor Cyan
Write-Host "============================================================"  -ForegroundColor Cyan
Write-Host ""
Write-Host "Project Root: $ProjectRoot"
Write-Host "Start Script: $StartDaemonScript"
Write-Host "Shortcut Path: $ShortcutPath"
Write-Host "============================================================"  -ForegroundColor Cyan
Write-Host ""

# Check if start_daemon.ps1 exists
if (-not (Test-Path $StartDaemonScript)) {
    Write-Host "[ERROR] start_daemon.ps1 not found: $StartDaemonScript" -ForegroundColor Red
    exit 1
}

# Create WScript.Shell object
$WshShell = New-Object -ComObject WScript.Shell

# Create shortcut
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$StartDaemonScript`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = "ZZZ OD MCP Server Daemon - Manages game operation server lifecycle"
$Shortcut.Save()

# Release COM object
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($WshShell) | Out-Null

Write-Host "[SUCCESS] Shortcut created!" -ForegroundColor Green
Write-Host ""
Write-Host "Shortcut location: $ShortcutPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "ZZZ OD Daemon will now automatically start when you log in." -ForegroundColor Green
Write-Host ""
Write-Host "To remove:" -ForegroundColor Yellow
Write-Host "  Delete the shortcut file: $ShortcutPath"
Write-Host ""
Write-Host "============================================================"  -ForegroundColor Cyan
