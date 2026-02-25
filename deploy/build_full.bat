@echo off
chcp 65001 2>&1

cd %~dp0

rem Build exe
uv run pyinstaller --noconfirm --clean "OneDragon-Installer.spec"
uv run pyinstaller --noconfirm --clean "OneDragon-Launcher.spec"
uv run pyinstaller --noconfirm --clean "OneDragon-RuntimeLauncher.spec"

set "DIST_DIR=%~dp0dist"
set "TARGET_DIR=%DIST_DIR%\ZenlessZoneZero-OneDragon"
if not exist "%TARGET_DIR%" (
    mkdir "%TARGET_DIR%"
)

copy "%DIST_DIR%\OneDragon-Installer.exe" "%TARGET_DIR%"
copy "%DIST_DIR%\OneDragon-Launcher.exe" "%TARGET_DIR%"

rem RuntimeLauncher: exe + .runtime 目录
copy "%DIST_DIR%\OneDragon-RuntimeLauncher\OneDragon-RuntimeLauncher.exe" "%TARGET_DIR%"
xcopy /E /I /Y "%DIST_DIR%\OneDragon-RuntimeLauncher\.runtime" "%TARGET_DIR%\.runtime\"

rem Copy source code for RuntimeLauncher
xcopy /E /I /Y "..\src" "%DIST_DIR%\OneDragon-RuntimeLauncher\src\"

rem Copy additional resources from spec file
copy "..\config\project.yml" "%TARGET_DIR%\config\"
xcopy /E /I /Y "..\assets\text" "%TARGET_DIR%\assets\text\"
xcopy /E /I /Y "..\assets\ui" "%TARGET_DIR%\assets\ui\"
copy "..\pyproject.toml" "%TARGET_DIR%\"
copy "..\uv.toml" "%TARGET_DIR%\"

rem Make zip files
powershell -Command "Compress-Archive -Path '%TARGET_DIR%' -DestinationPath '%DIST_DIR%\ZenlessZoneZero-OneDragon.zip' -Force"
powershell -Command "Compress-Archive -Path '%DIST_DIR%\OneDragon-Launcher.exe' -DestinationPath '%DIST_DIR%\ZenlessZoneZero-OneDragon-Launcher.zip' -Force"
powershell -Command "Compress-Archive -Path '%DIST_DIR%\OneDragon-RuntimeLauncher\OneDragon-RuntimeLauncher.exe','%DIST_DIR%\OneDragon-RuntimeLauncher\.runtime' -DestinationPath '%DIST_DIR%\ZenlessZoneZero-OneDragon-RuntimeLauncher.zip' -Force"

echo Done
pause
