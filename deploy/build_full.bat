@echo off
chcp 65001 2>&1

cd %~dp0

rem Build exe
uv run pyinstaller "OneDragon Installer.spec"
uv run pyinstaller "OneDragon Launcher.spec"

set "DIST_DIR=%~dp0dist"
set "TARGET_DIR=%DIST_DIR%\ZenlessZoneZero-OneDragon"
if not exist "%TARGET_DIR%" (
    mkdir "%TARGET_DIR%"
)

copy "%DIST_DIR%\OneDragon Installer.exe" "%TARGET_DIR%"
copy "%DIST_DIR%\OneDragon Launcher.exe" "%TARGET_DIR%"

rem Copy additional resources from spec file
copy "..\config\project.yml" "%TARGET_DIR%\config\"
xcopy /E /I /Y "..\assets\text" "%TARGET_DIR%\assets\text\"
xcopy /E /I /Y "..\assets\ui" "%TARGET_DIR%\assets\ui\"
copy "..\pyproject.toml" "%TARGET_DIR%\"
copy "..\uv.toml" "%TARGET_DIR%\"

rem Make zip file
powershell -Command "Compress-Archive -Path '%TARGET_DIR%' -DestinationPath '%DIST_DIR%\ZenlessZoneZero-OneDragon.zip' -Force"

echo Done
pause