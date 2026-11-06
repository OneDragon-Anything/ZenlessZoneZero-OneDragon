@echo off
chcp 65001 >nul
cd /d E:\Z1D\zode
set PYTHONPATH=E:\Z1D\zode\src;E:\Z1D\plugins-src\zzzod-plugin-inventory-scan
set PYTHONIOENCODING=utf-8
"E:\Z1D\zode\.venv\Scripts\python.exe" E:\Z1D\zode-agent\run-e2e-v6.py > E:\Z1D\zode-agent\reports\e2e-v6.log 2>&1
