@echo off
chcp 65001 >nul 2>&1

rem 检查是否以管理员权限运行
net session >nul 2>&1
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
echo.&echo 1. 强制配置 Python 环境&echo 2. 添加 Git 安全目录&echo 3. 重新安装 Pyautogui 库&echo 4. 检查 PowerShell 路径&echo 5. 重新创建虚拟环境&echo 6. 安装onnxruntime&echo 7. 配置Git SSL后端&echo 8. 以DEBUG模式运行一条龙&echo 9. 检查当前版本是否为受支持版本&echo 10. 删除日志和缓存文件&echo 11. 退出

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
if "%choice%"=="9" goto :CHECK_VERSION
if "%choice%"=="10" goto :CLEAN_FILES
if "%choice%"=="11" exit /b
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
if %errorlevel% neq 0 echo [ERROR] 添加失败 & pause & exit /b 1
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

:CHECK_VERSION
echo -------------------------------
echo 正在检查当前版本...
echo -------------------------------
echo.

set "is_old_version=false"
set "is_uv_exist=false"
set "is_mingit_exist=false"

rem --- 检查 OneDragon-Launcher.exe 文件 ---
if not exist "%~dp0OneDragon-Launcher.exe" (
    if exist "%~dp0OneDragon Launcher.exe" (
        echo [警告] 发现旧版启动器 "OneDragon Launcher.exe"，新版应为 "OneDragon-Launcher.exe"。
        set "is_old_version=true"
    ) else (
        echo [警告] 找不到 "OneDragon-Launcher.exe" 文件，可能不是正确的目录。
        set "is_old_version=true"
    )
) else (
    echo 找到 "OneDragon-Launcher.exe"。
)

echo.
echo --- 检查 .install 文件夹 ---
if exist "%~dp0.install\uv" (
    echo [PASS] 找到 "uv" 文件夹。
    set "is_uv_exist=true"
) else (
    echo [警告] 未在 .install 文件夹中找到 "uv" 文件夹。
)

if exist "%~dp0.install\MinGit" (
    echo [PASS] 找到 "MinGit" 文件夹。
    set "is_mingit_exist=true"
) else (
    echo [警告] 未在 .install 文件夹中找到 "MinGit" 文件夹。
)

rem 根据检查结果判断是否为旧版本
if "%is_uv_exist%"=="false" (
    set "is_old_version=true"
)

echo.
echo --- 结果总结 ---
if "%is_old_version%"=="true" (
    echo.
    echo ------------------------------------------
    echo.
    echo 结论：根据以上检查，你可能正在使用**暂停支持的旧版本**，请重新下载最新安装包。
    echo ------------------------------------------
    
    rem --- 自动打开浏览器跳转下载页面 ---
    echo.
    echo 正在为您打开下载页面...
    start "" "https://one-dragon.com/zzz/zh/quickstart.html#%E5%AE%89%E8%A3%85"
    
) else (
    echo.
    echo 结论：初步检查未发现旧版特征，你可能正在使用**2.0以上版本**。
    echo.
    echo ------------------------------------------
)

rem 针对 MinGit 的特殊提示
if "%is_uv_exist%"=="true" if "%is_mingit_exist%"=="false" (
    echo.
    echo [提示] 未找到MinGit，如果您正在使用自己的Git工具，那么版本可能没有错误。
)

goto :END

:CLEAN_FILES
echo -------------------------------
echo 正在删除日志和缓存文件...
echo -------------------------------
echo.

set /p confirm=此操作将删除日志和缓存文件，是否继续？ (Y/N): 

if /i "%confirm%"=="Y" (
    echo 正在清理...
    
    rem 删除 .debug/images/ 文件夹的内容 (保留文件夹本身)
    if exist "%~dp0.debug\images\" (
        del /q "%~dp0.debug\images\*"
        for /d %%d in ("%~dp0.debug\images\*") do rmdir /s /q "%%d"
        echo [PASS] 已清理 .debug\images\ 文件夹内容。
    ) else (
        echo [INFO] .debug\images\ 文件夹不存在，跳过。
    )

    rem 删除 .log/ 文件夹的内容 (保留文件夹本身)
    if exist "%~dp0.log\" (
        del /q "%~dp0.log\*"
        for /d %%d in ("%~dp0.log\*") do rmdir /s /q "%%d"
        echo [PASS] 已清理 .log 文件夹内容。
    ) else (
        echo [INFO] .log\ 文件夹不存在，跳过。
    )

    rem 删除 .install/ 文件夹内的zip压缩包
    if exist "%~dp0.install\" (
        del /q "%~dp0.install\*.zip"
        echo [PASS] 已删除 .install\ 文件夹内的安装残留压缩包。
    ) else (
        echo [INFO] .install\ 文件夹不存在，跳过zip清理。
    )

    rem 删除所有 .temp_clone* 文件夹
    for /d %%i in ("%~dp0.temp_clone*") do (
        if exist "%%i\" (
            rmdir /s /q "%%i\"
            if not exist "%%i\" (
                echo [PASS] 已删除 %%i\ 文件夹。
            ) else (
                echo [ERROR] 无法删除 %%i\ 文件夹。
            )
        )
    )
    
    echo.
    echo 清理完成。
) else (
    echo 操作已取消。
)

goto :END

:END
echo 操作已完成。
pause
cls
goto :MENU
