# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import json
import platform
import threading

_lock = threading.RLock()

DEFAULTS = {
    "dl_max_retry": 100,
    "dl_timeout": 240,
    "dl_read_stall": 30,
    "dl_threads": 8,
    "dl_chunk_mb": 10,
    "dl_cache_mb": 32,
    "dl_disable_ssl": False,
    "dl_speed_unit": "MB/s",
}

SPEED_UNITS = ("MB/s", "MiB/s", "Mbps")


def data_folder() -> str:
    if platform.system() == "Windows":
        return os.path.join(os.getenv("APPDATA", ""), "Nodanium")
    return os.path.join(os.path.expanduser("~"), ".Nodanium")


def config_file() -> str:
    return os.path.join(data_folder(), "config.json")


def dir_file() -> str:
    return os.path.join(data_folder(), "dir.txt")


def _default_download_dir() -> str:
    if platform.system() == "Windows":
        return os.path.join(os.path.expanduser("~"), "Downloads")
    return os.path.join(os.path.expanduser("~"), "Downloads")


# -------------------------- 配置读取 --------------------------
def load() -> dict:
    with _lock:
        data = dict(DEFAULTS)
        try:
            with open(config_file(), "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data.update(loaded)
        except Exception:
            pass
        return data


def save(data: dict) -> bool:
    with _lock:
        path = config_file()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            current = {}
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    current = loaded
            except Exception:
                current = {}
            current.update(data)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=4)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp, path)
            return True
        except Exception:
            return False


def get_download_dir() -> str:
    """首选项里保存的默认下载目录；缺失时创建并回退 ~/Downloads。"""
    with _lock:
        path = dir_file()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    value = f.read().strip()
                if value:
                    return os.path.expanduser(value)
        except Exception:
            pass
        value = _default_download_dir()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(value)
        except Exception:
            pass
        return value


def set_download_dir(path: str) -> bool:
    with _lock:
        value = (path or "").strip()
        if not value:
            return False
        value = os.path.expanduser(value)
        try:
            os.makedirs(os.path.dirname(dir_file()), exist_ok=True)
            with open(dir_file(), "w", encoding="utf-8") as f:
                f.write(value)
            return True
        except Exception:
            return False


def speed_unit() -> str:
    unit = load().get("dl_speed_unit", "MB/s")
    return unit if unit in SPEED_UNITS else "MB/s"


# -------------------------- 下载参数 --------------------------
def download_defaults() -> dict:
    """CLI/TUI 建下载参数时套用的首选项值。"""
    data = load()
    try:
        jobs = max(1, min(int(data.get("dl_threads", 8)), 128))
    except Exception:
        jobs = 8
    try:
        chunk_mb = max(1, int(data.get("dl_chunk_mb", 10)))
    except Exception:
        chunk_mb = 10
    try:
        cache_mb = max(1, int(data.get("dl_cache_mb", 32)))
    except Exception:
        cache_mb = 32
    return {
        "jobs": jobs,
        "chunk_size": float(chunk_mb),
        "cache": float(cache_mb),
        "no_ssl_check": bool(data.get("dl_disable_ssl", False)),
        "speed_unit": data.get("dl_speed_unit", "MB/s")
        if data.get("dl_speed_unit") in SPEED_UNITS else "MB/s",
        "timeout": float(data.get("dl_timeout", 240) or 240),
    }
