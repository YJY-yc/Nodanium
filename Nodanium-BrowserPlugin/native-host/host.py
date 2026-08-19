#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2025-2026 YUJY(YJY-yc)
# Licensed under the MIT License.
# SPDX-License-Identifier: MIT
# Nodanium 浏览器插件 Native Host（Nuitka 自包含二进制版）
#
# 职责：
#   - 通过 stdio 原生消息协议接收浏览器插件下发的下载请求；
#   - 定位 Nodanium 主程序可执行文件（Nuitka 打包后的二进制），
#     用子进程方式带上 --download 等参数启动它，由主程序弹出下载窗口；
#   - ping / getConfig 等轻量查询本地处理，无需启动主程序。
#
# 该文件不依赖 wx / requests，仅使用标准库，可用 Nuitka 编译为自包含二进制。

import sys
import os
import json
import struct
import subprocess
import platform
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 数据目录（与主程序/NodaniumLauncher 一致）
# ---------------------------------------------------------------------------
def get_data_folder():
    t = platform.system()
    if t == "Windows":
        return os.path.join(os.getenv('APPDATA', ''), "Nodanium")
    elif t == "Darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Nodanium")
    return os.path.join(os.path.expanduser("~"), ".Nodanium")


def _load_plugin_config_data():
    """读取首选项写入的插件配置 browser-plugin-config.json"""
    try:
        cfg_path = os.path.join(get_data_folder(), "browser-plugin-config.json")
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def load_plugin_config():
    """返回规范化后的插件配置。"""
    data = _load_plugin_config_data()
    limit = int(data.get("nativeSizeLimitBytes", 0) or 0)
    return {
        "nativeSizeLimitBytes": max(limit, 0),
        "enabled": bool(data.get("enabled", True)),
    }


def get_main_program_path():
    """定位 Nodanium 主程序可执行文件路径。

    优先级：
      1. 环境变量 NODANIUM_MAIN
      2. 插件配置 browser-plugin-config.json 的 mainProgramPath（首选项写入）
      3. 本二进制同目录下常见的主程序名（Linux: nodanium；Windows: NodaniumLauncher.exe）
    """
    env_path = os.environ.get("NODANIUM_MAIN")
    if env_path and os.path.exists(env_path):
        return env_path

    cfg = _load_plugin_config_data()
    cfg_path = cfg.get("mainProgramPath")
    if cfg_path and os.path.exists(cfg_path):
        return cfg_path

    # 与 host 二进制同目录的候选主程序
    same_dir = os.path.dirname(HERE)
    candidates = []
    if platform.system() == "Windows":
        candidates = [
            os.path.join(same_dir, "NodaniumLauncher.exe"),
            os.path.join(same_dir, "nodanium.exe"),
        ]
    else:
        candidates = [
            os.path.join(same_dir, "nodanium"),
            os.path.join(same_dir, "NodaniumLauncher"),
            os.path.join(same_dir, "nodanium.bin"),
        ]
    for c in candidates:
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c

    # Linux 已安装到系统 PATH / 标准安装目录时
    if platform.system() != "Windows":
        for c in ("/usr/bin/nodanium", "/usr/local/bin/nodanium",
                  "/usr/lib/nodanium/nodanium.bin", "/opt/nodanium/nodanium.bin"):
            if os.path.exists(c) and os.access(c, os.X_OK):
                return c
        import shutil
        which_path = shutil.which("nodanium")
        if which_path:
            return which_path
    return None


def get_download_dir():
    # 下载目录由主程序 --path 决定；此处提供默认兜底
    p = os.path.join(get_data_folder(), 'dir.txt')
    try:
        with open(p, 'r', encoding='utf-8') as f:
            v = f.read().strip()
            if v:
                return v
    except Exception:
        pass
    if platform.system() == "Windows":
        return "D:/Downloads"
    return os.path.join(os.path.expanduser("~"), "Downloads")


def read_message(fp):
    length_buf = os.read(fp.fileno(), 4)
    if not length_buf or len(length_buf) < 4:
        raise EOFError("no message length")
    length = struct.unpack('<I', length_buf)[0]
    data = b""
    while len(data) < length:
        need = length - len(data)
        chunk = os.read(fp.fileno(), need)
        if not chunk:
            raise EOFError("message truncated")
        data += chunk
    return json.loads(data.decode('utf-8'))


def write_message(fp, obj):
    payload = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    fp.write(struct.pack('<I', len(payload)))
    fp.write(payload)
    fp.flush()


# 供 requests 下载时需要丢弃的请求头：改一个/带一个都可能破坏多线程下载
# 或导致服务端按错误语义处理（压缩、分块、连接管理等交给 requests/主程序处理）。
_SKIP_HEADERS = {
    "accept-encoding",   # 手动带 gzip 会让 requests 不自动解压，写盘数据被压缩
    "host",              # 由 requests 根据 url 自动填充
    "connection",        # http keep-alive 交由底层连接池管理
    "content-length", "content-type", "content-range", "transfer-encoding",  # 实体/分块头
}


def build_headers(msg):
    headers = {}
    ua = msg.get("userAgent") or msg.get("user_agent")
    if ua:
        headers["User-Agent"] = ua
    else:
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    headers["Accept"] = "*/*"
    headers["Accept-Language"] = "zh-CN,zh;q=0.9,en;q=0.8"
    cookies = msg.get("cookies")
    if cookies:
        headers["Cookie"] = cookies
    referer = msg.get("referer") or msg.get("referrer")
    if referer:
        headers["Referer"] = referer

    # 合并浏览器捕获到的真实请求头（优先，弥补 cookies/referer 无法覆盖的
    # Authorization / Accept / X-* 等），丢弃不适合下发给 requests 的头。
    extra = msg.get("headers") or {}
    if isinstance(extra, dict):
        for k, v in extra.items():
            kl = str(k).lower()
            if kl in _SKIP_HEADERS or v is None:
                continue
            headers[str(k)] = str(v)
        # 若捕获头里带了 Cookie 且 msg 未显式提供，则使用捕获到的 Cookie
        if not cookies and extras_extract_cookie(extra):
            headers["Cookie"] = extras_extract_cookie(extra)
    return headers


def extras_extract_cookie(extra):
    for k, v in extra.items():
        if str(k).lower() == "cookie" and v:
            return str(v)
    return ""


def fetch_remote_size(url, header, timeout=8):
    """HEAD 请求获取文件大小；无 requests 时返回 None（此时不做本地判断）。"""
    try:
        import requests  # 若打包时未携带 requests，则返回 None，走主程序下载
        r = requests.head(url, headers=header, timeout=timeout, allow_redirects=True)
        if r.ok:
            cl = r.headers.get("Content-Length")
            if cl:
                try:
                    return int(cl)
                except (TypeError, ValueError):
                    return None
    except Exception:
        pass
    return None


def _default_filename(url):
    from urllib.parse import unquote, urlparse
    try:
        u = unquote(os.path.basename(urlparse(url).path))
        if u:
            return u
    except Exception:
        pass
    return "nodanium_download.bin"


def should_use_native(url, header):
    """判断是否放行浏览器原生下载（小于等于阈值时不占用 Nodanium 多线程）。"""
    cfg = load_plugin_config()
    limit = cfg.get("nativeSizeLimitBytes", 0)
    if limit <= 0:
        return False
    size = fetch_remote_size(url, header)
    if size is None:
        return False
    return size > 0 and size <= limit


def spawn_main_program(args):
    """以子进程方式启动主程序可执行文件，不阻塞本进程。"""
    main = get_main_program_path()
    if not main:
        raise RuntimeError("未找到 Nodanium 主程序，请在首选项中设置主程序路径")
    cmd = [main] + args
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    if platform.system() == "Windows":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | \
                        getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen(cmd, env=env,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True,
                         creationflags=creationflags)
    else:
        subprocess.Popen(cmd, env=env,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True,
                         start_new_session=True)


def do_download(msg):
    url = msg.get("url") or msg.get("URL")
    if not url:
        raise ValueError("缺少下载链接 url")
    filename = msg.get("filename") or _default_filename(url)
    from urllib.parse import unquote
    filename = os.path.basename(unquote(filename))
    save_path = msg.get("path") or msg.get("save_path") or get_download_dir()
    header = build_headers(msg)
    mime = msg.get("mime") or msg.get("type")
    if mime:
        header["Accept"] = mime

    # 小于等于阈值的小文件放行浏览器原生下载
    if should_use_native(url, header):
        return {
            "status": "use_native",
            "message": "文件较小，已放行浏览器原生下载",
            "url": url,
            "filename": filename,
        }

    # 组装 --download 命令行参数
    dl_args = ["--download"]
    dl_args.append("--url=%s" % url)
    dl_args.append("--filename=%s" % filename)
    dl_args.append("--path=%s" % save_path)
    if header:
        dl_args.append("--header=%s" % json.dumps(header, ensure_ascii=False))
    spawn_main_program(dl_args)

    return {
        "status": "ok",
        "message": "已转交 Nodanium 主程序下载",
        "url": url,
        "filename": filename,
        "save_path": save_path,
    }


def handle_message(msg, out):
    mtype = msg.get("type")
    if mtype == "ping":
        write_message(out, {"status": "ok", "service": "nodanium", "message": "pong"})
        return None
    if mtype == "getConfig":
        write_message(out, {"status": "ok", "config": load_plugin_config()})
        return None
    try:
        result = do_download(msg)
        if isinstance(result, dict) and result.get("status") == "use_native":
            write_message(out, result)
        else:
            write_message(out, {"status": "ok", "result": result})
    except Exception as e:
        write_message(out, {"status": "error", "error": str(e)})
        try:
            traceback.print_exc()
        except Exception:
            pass
    return None


def main():
    os.environ["PYTHONUNBUFFERED"] = "1"
    stdin_fp = sys.stdin.buffer
    stdout_fp = sys.stdout.buffer
    while True:
        try:
            msg = read_message(stdin_fp)
        except EOFError:
            break
        except Exception:
            break
        if msg is None:
            break
        try:
            handle_message(msg, stdout_fp)
        except Exception:
            try:
                write_message(stdout_fp, {"status": "error", "error": "handler failed"})
            except Exception:
                break


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            traceback.print_exc()
        except Exception:
            pass
