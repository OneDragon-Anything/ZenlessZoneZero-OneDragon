@echo off
chcp 65001 >nul 2>&1
title ZODE 每日任务（管理员）
net session >nul 2>&1
if errorlevel 1 (
    echo 正在请求管理员权限，请在弹窗点「是」...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
set "PYTHONPATH=E:\Z1D\zode\src"
cd /d E:\Z1D\zode
echo === 启动卡住监控（后台）===
start "monitor" /min .venv\Scripts\pythonw.exe .debug\monitor_stuck.py
echo === 每日任务开始 %date% %time% ===
echo.
.venv\Scripts\python.exe -m zzz_od.application.zzz_application_launcher --instance 1
echo.
echo === 已结束 %date% %time% 退出码 %ERRORLEVEL% ===
timeout /t 30
