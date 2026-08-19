#!/usr/bin/env bash
set -e
echo "==============================================="
echo "  Nodanium 下载器 - 安装 Native Host"
echo "==============================================="

HOST_NAME="com.nodanium.yujy"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/$HOST_NAME.json"
TEMPLATE_FF="$SCRIPT_DIR/$HOST_NAME-firefox.json"

# 优先使用 Nuitka 编译出的 host 二进制；否则回退到 host_launcher.py 脚本
HOST_BIN=""
for cand in "$SCRIPT_DIR/nodanium-host" "$SCRIPT_DIR/nodanium-host.exe" "$SCRIPT_DIR/host" "$SCRIPT_DIR/host.exe"; do
    if [ -f "$cand" ]; then
        HOST_BIN="$(cd "$(dirname "$cand")" && pwd)/$(basename "$cand")"
        break
    fi
done
if [ -z "$HOST_BIN" ]; then
    HOST_BIN="$SCRIPT_DIR/host_launcher.py"
fi
chmod +x "$HOST_BIN" 2>/dev/null || true
if [ "$HOST_BIN" = "$SCRIPT_DIR/host_launcher.py" ]; then
    chmod +x "$SCRIPT_DIR/host.py"
fi

echo "Native Host 入口： $HOST_BIN"

# 把清单中的 __HOST_PY_PATH__ 替换成真实路径，写入浏览器注册目录
install_manifest() {
    local dest="$1"
    local tmpl="$2"
    mkdir -p "$dest"
    sed "s|__HOST_PY_PATH__|$HOST_BIN|g" "$tmpl" > "$dest/$HOST_NAME.json"
    echo "[OK] 写入 $dest/$HOST_NAME.json (path=$HOST_BIN)"
}

# 注意：必须用绝对路径，否则 Chrome 抛 "Specified native messaging host not found"
if [ -d "$HOME/.config/google-chrome" ]; then
    install_manifest "$HOME/.config/google-chrome/NativeMessagingHosts" "$TEMPLATE"
fi
if [ -d "$HOME/.config/chromium" ]; then
    install_manifest "$HOME/.config/chromium/NativeMessagingHosts" "$TEMPLATE"
fi
if [ -d "$HOME/.config/microsoft-edge" ]; then
    install_manifest "$HOME/.config/microsoft-edge/NativeMessagingHosts" "$TEMPLATE"
fi
if [ -d "$HOME/.mozilla" ]; then
    install_manifest "$HOME/.mozilla/native-messaging-hosts" "$TEMPLATE_FF"
fi
# Firefox 可能使用 XDG 数据目录(~/.config/mozilla) 而非 ~/.mozilla
if [ -d "$HOME/.config/mozilla" ]; then
    install_manifest "$HOME/.config/mozilla/native-messaging-hosts" "$TEMPLATE_FF"
fi
# 无浏览器目录时仍写入标准位置（Chrome 默认读取该目录）
install_manifest "$HOME/.config/google-chrome/NativeMessagingHosts" "$TEMPLATE"

echo ""
echo "==============================================="
echo "  安装完成！"
echo "  已将 Native Host 注册到浏览器。"
echo ""
echo "  下一步（重要）："
echo "  在 chrome://extensions 复制扩展 ID，编辑："
echo "  $HOME/.config/google-chrome/NativeMessagingHosts/$HOST_NAME.json"
echo "  把 allowed_origins 中的占位 ID 替换为你真实的扩展 ID，形如："
echo '    chrome-extension://YOUR_REAL_ID/'
echo "  并在首选项中确认主程序路径，确保 --download 能启动 Nodanium。"
echo "==============================================="
