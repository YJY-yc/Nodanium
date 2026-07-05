@echo off
chcp 65001 >nul
echo ====================================
echo   Nodanium 下载器 - 安装 Native Host
echo ====================================
echo.

set HOST_NAME=com.nodanium.downloader
set SCRIPT_DIR=%~dp0

echo 正在注册到 Chrome...
reg add "HKEY_CURRENT_USER\Software\Google\Chrome\NativeMessagingHosts\%HOST_NAME%" /ve /t REG_SZ /d "%SCRIPT_DIR%%HOST_NAME%.json" /f 2>nul
if %errorlevel% equ 0 (echo   ✅ Chrome 注册成功) else (echo   ⚠️ Chrome 注册失败)

echo 正在注册到 Edge...
reg add "HKEY_CURRENT_USER\Software\Microsoft\Edge\NativeMessagingHosts\%HOST_NAME%" /ve /t REG_SZ /d "%SCRIPT_DIR%%HOST_NAME%.json" /f 2>nul
if %errorlevel% equ 0 (echo   ✅ Edge 注册成功) else (echo   ⚠️ Edge 注册失败)

echo 正在注册到 Firefox...
reg add "HKEY_CURRENT_USER\Software\Mozilla\NativeMessagingHosts\%HOST_NAME%" /ve /t REG_SZ /d "%SCRIPT_DIR%%HOST_NAME%-firefox.json" /f 2>nul
if %errorlevel% equ 0 (echo   ✅ Firefox 注册成功) else (echo   ⚠️ Firefox 注册失败)

echo.
echo ====================================
echo   ✅ 安装完成！
echo ====================================
echo.
echo 📌 注意事项：
echo 1. 请确保 Nodanium.exe 在环境变量 PATH 中
echo 2. 打开 Chrome 插件页面，获取扩展 ID
echo 3. 将扩展 ID 填入清单文件的 allowed_origins
echo 4. 重新加载浏览器扩展
echo.
pause