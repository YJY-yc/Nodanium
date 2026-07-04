#!/bin/bash

echo "===================================="
echo "  Nodanium 下载器 - 安装 Native Host"
echo "===================================="

HOST_NAME="com.nodanium.downloader"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Chrome
mkdir -p "$HOME/.config/google-chrome/NativeMessagingHosts/"
cp "$SCRIPT_DIR/$HOST_NAME.json" "$HOME/.config/google-chrome/NativeMessagingHosts/$HOST_NAME.json"
echo "✅ Chrome 已安装"

# Edge
mkdir -p "$HOME/.config/microsoft-edge/NativeMessagingHosts/"
cp "$SCRIPT_DIR/$HOST_NAME.json" "$HOME/.config/microsoft-edge/NativeMessagingHosts/$HOST_NAME.json"
echo "✅ Edge 已安装"

# Firefox
mkdir -p "$HOME/.mozilla/native-messaging-hosts/"
cp "$SCRIPT_DIR/$HOST_NAME-firefox.json" "$HOME/.mozilla/native-messaging-hosts/$HOST_NAME.json"
echo "✅ Firefox 已安装"

echo "===================================="
echo "✅ 安装完成！"
echo ""
echo "📌 注意事项："
echo "1. 请确保 Nodanium 在环境变量 PATH 中"
echo "2. 获取扩展 ID 并更新清单文件"
echo "===================================="