#!/bin/bash
# Nodanium Linux 打包脚本
# 强制使用系统 Python(3.12) 的 Nuitka，保证 wx/psutil/requests 等第三方依赖能被打包进去
# 用法: bash "Pack .sh"   (在项目根目录运行)

set -e
cd "$(dirname "$0")"

PY=/usr/bin/python3
NUITKA="$PY -m nuitka"

echo "==== 使用系统 Nuitka ===="
$NUITKA --version | grep -E "^[0-9]+\.|Python:" || $NUITKA --version

echo "==== 校验关键依赖（缺失会提前警告）===="
check_dep() {
  if $PY -c "import $1" 2>/dev/null; then
    echo "  [OK] $1"
  else
    echo "  [缺] $1 (运行时该功能将不可用)"
  fi
}
for m in wx psutil requests bs4 PIL urllib3 dns selenium playwright; do
  check_dep "$m"
done

echo "==== 清理旧产物 ===="
rm -rf NodaniumLauncher.build NodaniumLauncher.dist

echo "==== 开始打包 ===="
# 注意: Plugins 里全是 .py 脚本,Nuitka 的 --include-data-dir 只复制数据文件(图片/二进制),
#       会自动跳过纯 .py 目录。必须用 --include-data-files 带通配符才能把 .py 拷进 dist。
$NUITKA --standalone --prefer-source-code --linux-icon=favicon.png \
    --copyright="(C) 2023-2026 YJY-yc" --jobs=6 --lto=yes --follow-imports \
    --nofollow-import-to=selenium,playwright \
    --include-package=dns \
    --include-data-dir=icons=icons \
    --include-data-files='Plugins/*.py=Plugins/' \
    --static-libpython=no NodaniumLauncher.py

echo "==== 打包完成，产物目录 ===="
ls -la NodaniumLauncher.dist/
echo
echo "==== 校验依赖是否都进去了 ===="
# 说明: 纯 Python 包(requests/bs4/urllib3/dns等)会被 Nuitka 编译进主程序 bin,dist 里不一定有目录,
#     因此这里既查 dist 目录也查编译出的 C 文件(.build/module.<pkg>*.c)。
purepy="requests urllib3 dns bs4"
for d in wx psutil PIL; do
  if [ -d "NodaniumLauncher.dist/$d" ]; then echo "  [OK] $d (目录已打包)"; else echo "  [缺] $d(目录)"; fi
done
for d in $purepy; do
  # dns 编译产物名不确定(.build 可能无 module.dns.*),用 dist 目录 || build 内引用判断
  if [ -d "NodaniumLauncher.dist/$d" ] || ls NodaniumLauncher.build/module.${d}*.c >/dev/null 2>&1 \
     || grep -rl "$d" NodaniumLauncher.build/module.*.const >/dev/null 2>&1; then
    echo "  [OK] $d (已编译进主程序/Nuitka bin)"
  else
    echo "  [缺?] $d (请运行 bin 确认;dns/bs4 等纯py包编译进 bin 不一定有 .build 文件)"
  fi
done
echo "==== Plugins 目录 ===="
if [ -d NodaniumLauncher.dist/Plugins ]; then
  echo "  [OK] Plugins 已打包:"
  ls NodaniumLauncher.dist/Plugins/
else
  echo "  [缺] Plugins"
fi
