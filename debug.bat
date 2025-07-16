@echo off
chcp 65001 >nul 2>&1

rem 检查是否以管理员权限运行
net session  >nul 2>&1
if %errorlevel% neq 0 (
    echo -------------------------------
    echo 尝试获取管理员权限中...
    echo -------------------------------
    rem 增加延迟时间，如遇无限循环，则可在此终止程序运行
    timeout /t 2
    PowerShell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

rem 检查路径是否包含中文或空格
powershell -command "if ('%~dp0' -match '[\u4e00-\u9fff]') { exit 1 } else { exit 0 }"
if %errorlevel% equ 1 echo [WARN] 当前路径包含中文字符

set "path_check=%~dp0"
if "%path_check%" neq "%path_check: =%" echo [WARN] 路径中包含空格

:MENU
echo -------------------------------
echo 正在以管理员权限运行...
echo -------------------------------
echo.&echo 1. 强制配置 Python 环境&echo 2. 添加 Git 安全目录&echo 3. 重新安装 Pyautogui 库&echo 4. 检查 PowerShell 路径&echo 5. 重新创建虚拟环境&echo 6. 安装onnxruntime&echo 7. 配置Git SSL后端&echo 8. 以DEBUG模式运行一条龙&echo 9. 退出
echo.
set /p choice=请输入选项数字并按 Enter：

if "%choice%"=="1" goto :CONFIG_PYTHON_ENV
if "%choice%"=="2" goto :ADD_GIT_SAFE_DIR
if "%choice%"=="3" goto :REINSTALL_PY_LIBS_CHOOSE_SOURCE
if "%choice%"=="4" goto :CHECK_PS_PATH
if "%choice%"=="5" goto :VENV
if "%choice%"=="6" goto :ONNX_CHOOSE_SOURCE
if "%choice%"=="7" goto :CONFIG_GIT_SSL
if "%choice%"=="8" goto :DEBUG
if "%choice%"=="9" exit /b
echo [ERROR] 无效选项，请重新选择。

goto :MENU

:CONFIG_PYTHON_ENV
echo -------------------------------
echo 正在配置 Python 环境...
echo -------------------------------

set "MAINPATH=zzz_od\gui\app.py"
set "ENV_DIR=%~dp0.install"

rem 调用环境配置脚本
call "%~dp0env.bat"
setx "PYTHON" "%~dp0.venv\scripts\python.exe"
setx "PYTHONPATH" "%~dp0src"

set "PYTHON=%~dp0.venv\scripts\python.exe"
set "PYTHONPATH=%~dp0src"
set "APPPATH=%PYTHONPATH%\%MAINPATH%"

if not exist "%PYTHON%" echo [WARN] 未配置Python.exe & pause & exit /b 1
if not exist "%PYTHONPATH%" echo [WARN] PYTHONPATH 未设置 & pause & exit /b 1
if not exist "%APPPATH%" echo [WARN] PYTHONPATH 设置错误 无法找到 %APPPATH% & pause & exit /b 1

goto :END

:ADD_GIT_SAFE_DIR
echo -------------------------------
echo 尝试添加 Git 安全目录...
echo -------------------------------
setlocal enabledelayedexpansion
set "GIT_PATH=%~dp0.install\MinGit\bin\git.exe"
set "DIR_PATH=%~dp0"
set "DIR_PATH=%DIR_PATH:\=/%"
set "DIR_PATH=%DIR_PATH:\\=/%"
if "%DIR_PATH:~-1%"=="/" set "DIR_PATH=%DIR_PATH:~0,-1%"
"%GIT_PATH%" config --global --add safe.directory %DIR_PATH%
if %errorlevel% neq 0 echo [ERROR] 添加失败  & pause & exit /b 1
echo [PASS] Git 安全目录添加成功

goto :END

:REINSTALL_PY_LIBS_CHOOSE_SOURCE
echo.&echo 1. 清华源&echo 2. 阿里源&echo 3. 官方源&echo 4. 返回主菜单
echo.
set /p pip_choice=请选择PIP源并按 Enter：
if /i "%pip_choice%"=="1" (
set "PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple"
    set "PIP_TRUSTED_HOST_CMD="
    goto :REINSTALL_PY_LIBS
)
if /i "%pip_choice%"=="2" (
    set "PIP_INDEX_URL=http://mirrors.aliyun.com/pypi/simple"
    set "PIP_TRUSTED_HOST_CMD=--trusted-host mirrors.aliyun.com"
    goto :REINSTALL_PY_LIBS
)
if /i "%pip_choice%"=="3" (
    set "PIP_INDEX_URL=https://pypi.org/simple"
    set "PIP_TRUSTED_HOST_CMD="
goto :REINSTALL_PY_LIBS
)
if /i "%pip_choice%"=="4" goto :MENU
echo [ERROR] 无效选项，请重新选择。
goto :REINSTALL_PY_LIBS_CHOOSE_SOURCE

:REINSTALL_PY_LIBS
echo -------------------------------
echo 重新安装 Pyautogui 库...
echo -------------------------------

call "%~dp0env.bat"

set "PYTHON=%~dp0.venv\scripts\python.exe"
set "PYTHONPATH=%~dp0src"
set "APPPATH=%PYTHONPATH%\%MAINPATH%"
set "UV=%~dp0.install\uv\uv.exe"

if not exist "%PYTHON%" echo [WARN] 未配置Python.exe & pause & exit /b 1
if not exist "%PYTHONPATH%" echo [WARN] PYTHONPATH 未设置 & pause & exit /b 1
if not exist "%APPPATH%" echo [WARN] PYTHONPATH 设置错误 无法找到 %APPPATH% & pause & exit /b 1
if not exist "%UV%" echo [ERROR] 未找到uv工具 & pause & exit /b 1

%UV% pip uninstall pyautogui -y
%UV% pip install -i %PIP_INDEX_URL% %PIP_TRUSTED_HOST_CMD% pyautogui
%UV% pip uninstall pygetwindow -y 
%UV% pip install -i %PIP_INDEX_URL% %PIP_TRUSTED_HOST_CMD% pygetwindow
echo 安装完成...
goto :END

:CHECK_PS_PATH
echo -------------------------------
echo 检查并添加 PowerShell 路径...
echo -------------------------------

set PS_PATH=C:\Windows\System32\WindowsPowerShell\v1.0\
where powershell >nul 2>&1
if %errorlevel% neq 0 (
    echo PowerShell路径未找到，正在尝试添加...
    setx PATH "%PATH%;C:\Windows\System32\WindowsPowerShell\v1.0\"
    echo PowerShell路径已添加到系统路径中...
) else (
    echo PowerShell路径已存在
)

goto :END

:VENV
echo -------------------------------
echo 重新创建虚拟环境...
echo -------------------------------

set "PYTHON=%~dp0.install\python\python.exe"
if not exist "%PYTHON%" echo [WARN] 未配置Python.exe & pause & exit /b 1

set "UV=%~dp0.install\uv\uv.exe"
if not exist "%UV%" echo [ERROR] 未找到uv工具 & pause & exit /b 1

%UV% venv "%~dp0.venv"
echo 创建虚拟环境完成...
goto :END

:ONNX_CHOOSE_SOURCE
echo.&echo 1. 清华源&echo 2. 阿里源&echo 3. 官方源&echo 4. 返回主菜单
echo.
set /p pip_choice=请选择PIP源并按 Enter：
if /i "%pip_choice%"=="1" (
set "PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple"
    set "PIP_TRUSTED_HOST_CMD="
    goto :PIP
)
if /i "%pip_choice%"=="2" (
    set "PIP_INDEX_URL=http://mirrors.aliyun.com/pypi/simple"
    set "PIP_TRUSTED_HOST_CMD=--trusted-host mirrors.aliyun.com"
    goto :PIP
)
if /i "%pip_choice%"=="3" (
    set "PIP_INDEX_URL=https://pypi.org/simple"
    set "PIP_TRUSTED_HOST_CMD="
goto :PIP
)
if /i "%pip_choice%"=="4" goto :MENU
echo [ERROR] 无效选项，请重新选择。
goto :ONNX_CHOOSE_SOURCE

:ONNX
echo -------------------------------
echo 安装onnxruntime
echo -------------------------------

call "%~dp0env.bat"

set "PYTHON=%~dp0.venv\scripts\python.exe"
if not exist "%PYTHON%" echo [WARN] 未配置Python.exe & pause & exit /b 1

set "UV=%~dp0.install\uv\uv.exe"
if not exist "%UV%" echo [ERROR] 未找到uv工具 & pause & exit /b 1

%UV% pip install onnxruntime==1.18.0 -i %PIP_INDEX_URL% %PIP_TRUSTED_HOST_CMD%


echo 安装完成...

goto :END

:DEBUG
set "MAINPATH=zzz_od\gui\app.py"
set "ENV_DIR=%~dp0.install"

rem 调用环境配置脚本
call "%~dp0env.bat"
set "PYTHON=%~dp0.venv\scripts\python.exe"
set "PYTHONPATH=%~dp0src"
set "APPPATH=%PYTHONPATH%\%MAINPATH%"

rem 打印信息
echo [PASS] PYTHON：%PYTHON%
echo [PASS] PYTHONPATH：%PYTHONPATH%
echo [PASS] APPPATH：%APPPATH%

rem 检查 Python 可执行文件路径
if not exist "%PYTHON%" (
    echo [WARN] 未配置Python.exe
    pause
    exit /b 1
)

rem 检查 PythonPath 目录
if not exist "%PYTHONPATH%" (
    echo [WARN] PYTHONPATH 未设置
    pause
    exit /b 1
)

rem 检查应用程序脚本路径
if not exist "%APPPATH%" (
    echo [WARN] PYTHONPATH 设置错误 无法找到 %APPPATH%
    pause
    exit /b 1
)

echo [INFO]启动中...切换到DEBUG模式

%PYTHON% %APPPATH%

goto :END

:CONFIG_GIT_SSL
echo -------------------------------
echo 正在配置Git SSL后端为schannel...
echo -------------------------------
"%ProgramFiles%\Git\bin\git.exe" config --global http.sslBackend schannel
echo Git SSL后端已配置为schannel
goto :MENU

:END
echo 操作已完成。
pause
cls
goto :MENU
