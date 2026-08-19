@echo off
setlocal
chcp 65001 >nul
echo ===============================================
echo   Nodanium 下载器 - 安装 Native Host
echo ===============================================
echo.

set HOST_NAME=com.nodanium.yujy
for %%I in ("%~dp0.") do set "SCRIPT_DIR=%%~fI"
set "TEMPLATE=%SCRIPT_DIR%\%HOST_NAME%.json"
set "TEMPLATE_FF=%SCRIPT_DIR%\%HOST_NAME%-firefox.json"

rem 优先使用 Nuitka 编译出的 host 二进制；否则回退到 host_launcher.py 脚本
set "HOST_BIN="
if exist "%SCRIPT_DIR%\nodanium-host.exe" set "HOST_BIN=%SCRIPT_DIR%\nodanium-host.exe"
if not defined HOST_BIN if exist "%SCRIPT_DIR%\host.exe" set "HOST_BIN=%SCRIPT_DIR%\host.exe"
if not defined HOST_BIN if exist "%SCRIPT_DIR%\NodaniumHost.exe" set "HOST_BIN=%SCRIPT_DIR%\NodaniumHost.exe"
if not defined HOST_BIN set "HOST_BIN=%SCRIPT_DIR%\host_launcher.py"

echo Native Host 入口: %HOST_BIN%

rem 生成带绝对路径的清单并注册到 Chrome
set "CHROME_DIR=%APPDATA%\Google\Chrome\NativeMessagingHosts"
if not exist "%CHROME_DIR%" mkdir "%CHROME_DIR%"
powershell -NoProfile -Command "(Get-Content '%TEMPLATE%' -Raw).Replace('__HOST_PY_PATH__','%HOST_BIN%') | Set-Content -Encoding UTF8 '%CHROME_DIR%\%HOST_NAME%.json'"
echo   Chrome 已注册

set "EDGE_DIR=%LOCALAPPDATA%\Microsoft\Edge\User Data\NativeMessagingHosts"
if not exist "%EDGE_DIR%" mkdir "%EDGE_DIR%"
powershell -NoProfile -Command "(Get-Content '%TEMPLATE%' -Raw).Replace('__HOST_PY_PATH__','%HOST_BIN%') | Set-Content -Encoding UTF8 '%EDGE_DIR%\%HOST_NAME%.json'"
echo   Edge 已注册

set "FF_DIR=%APPDATA%\Mozilla\NativeMessagingHosts"
if not exist "%FF_DIR%" mkdir "%FF_DIR%"
powershell -NoProfile -Command "(Get-Content '%TEMPLATE_FF%' -Raw).Replace('__HOST_PY_PATH__','%HOST_BIN%') | Set-Content -Encoding UTF8 '%FF_DIR%\%HOST_NAME%.json'"
echo   Firefox 已注册

echo.
echo   ============================================
echo   安装完成！
echo   请在扩展设置页复制扩展 ID，并把它填到：
echo   %CHROME_DIR%\%HOST_NAME%.json
echo   的 allowed_origins（形如 chrome-extension://你的ID/ ）
echo   然后重新加载扩展。
echo   ============================================
pause
