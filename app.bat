@echo off
chcp 65001 2>&1

rem 检查是否以管理员权限运行
net session 2>&1
if %errorlevel% neq 0 (
    echo -------------------------------
    echo 尝试获取管理员权限中...
    echo -------------------------------
    rem 增加延迟时间，如遇无限循环，则可在此终止程序运行
    timeout /t 2
    PowerShell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

echo -------------------------------
echo 正在以管理员权限运行...
echo -------------------------------

set "MAINPATH=zzz_od\gui\app.py"
set "ENV_DIR=%~dp0.venv"

REM 调用环境配置脚本
call "%~dp0env.bat"
set "PYTHONPATH=%~dp0src"
set "APPPATH=%PYTHONPATH%\%MAINPATH%"
set "PYTHONUSERBASE=%~dp0.venv"

REM 打印信息
echo [PASS] PYTHON: %PYTHON%
echo [PASS] PYTHONPATH: %PYTHONPATH%
echo [PASS] APPPATH: %APPPATH%
echo [PASS] PYTHONUSERBASE: %PYTHONUSERBASE%

REM 使用 PowerShell 检查路径中是否有中文字符
powershell -command "if ('%~dp0' -match '[\u4e00-\u9fff]') { exit 1 } else { exit 0 }"
if %errorlevel% equ 1 (
    echo [WARN] 当前路径包含中文字符
)

REM 检查路径中是否有空格
set "path_check=%~dp0"
if "%path_check%" neq "%path_check: =%" (
    echo [WARN] 路径中包含空格
)

REM 获取当前日期并格式化为 YYYYMMDD
for /f "tokens=2-4 delims=/ " %%a in ('echo %date%') do (
    set year=%%c
    set month=%%a
    set day=%%b
)

REM 获取当前时间
for /f "tokens=1-3 delims=/: " %%i in ('echo %time%') do (
    set hour=%%i
    set minute=%%j
    set second=%%k
)

REM 将小时和分钟格式化为两位数
set hour=%hour: =0%
set minute=%minute: =0%
set second=%second: =0%

REM 生成日志目录和文件名，格式为 YYYYMMDD 和 HH.MM.SS
set log_dir=%~dp0.log\%year%%month%%day%
set timestamp=%hour%.%minute%.%second%
set "BAT_LOG=%log_dir%\bat_%timestamp%.log"
set "PYTHON_LOG=%log_dir%\python_%timestamp%.log"

REM 检查并创建日志目录
if not exist "%log_dir%" (
    echo [WARN] 日志目录不存在，正在创建...
    mkdir "%log_dir%"
    if %errorlevel% neq 0 (
        echo [WARN] 创建日志目录失败。
        pause
        exit /b 1
    )
    echo [PASS] 日志目录创建成功。
)

REM 删除所有以 'bat_' 开头且以 '.log' 结尾的文件
for /r "%log_dir%" %%F in (bat_*.log) do (
    del "%%F"
    echo [INFO] 删除旧日志文件: %%F
)

REM 检查 Python 可执行文件路径
if not exist "%PYTHON%" (
    echo [WARN] 未配置Python.exe
    pause
    exit /b 1
)

REM 检查 PythonPath 目录
if not exist "%PYTHONPATH%" (
    echo [WARN] PYTHONPATH 未设置
    pause
    exit /b 1
)

REM 检查 PythonUserBase 目录
if not exist "%PYTHONUSERBASE%" (
    echo [WARN] PYTHONUSERBASE 未设置
    pause
    exit /b 1
)

REM 检查应用程序脚本路径
if not exist "%APPPATH%" (
    echo [WARN] PYTHONPATH 设置错误 无法找到 %APPPATH%
    pause
    exit /b 1
)

echo 启动中...大约需要5+秒
powershell -Command "& {Start-Process '%PYTHON%' -ArgumentList '%APPPATH%' -NoNewWindow -RedirectStandardOutput '%PYTHON_LOG%' -PassThru}"

REM 等待一段时间后退出
timeout /t 5

exit 0
