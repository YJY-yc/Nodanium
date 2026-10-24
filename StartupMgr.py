# Copyright (c) 2024-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import sys
import platform
import logging

sys_type = platform.system()

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
APPROVED32_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32"
RUN_VALUE = "Nodanium"
LEGACY_MARKERS = ("python.exe", "pythonw.exe", "NodaniumLauncher.py")
DISABLED_BYTES = (0x03, 0x07)
ENABLED_BYTES = (0x02, 0x06)


# ========================== 程序路径 ==========================

def is_frozen():
    try:
        return bool(getattr(sys, "frozen", False))
    except Exception:
        return False


def program_dir():
    try:
        if is_frozen():
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def source_dir():
    try:
        d = os.path.dirname(os.path.abspath(__file__))
        if d and os.path.isdir(d):
            return d
    except Exception:
        pass
    return program_dir()


def launcher_path():
    return os.path.join(source_dir(), "NodaniumLauncher.py")


def is_portable_source():
    return os.path.isfile(launcher_path())


def _search_exe():
    import shutil
    d = program_dir()
    cand = [os.path.join(d, "NodaniumLauncher.exe"),
            os.path.join(d, "Nodanium.exe"),
            os.path.join(d, "NodaniumLauncher.bin")]
    for c in cand:
        if os.path.isfile(c):
            return c
    for c in cand:
        try:
            h = shutil.which(os.path.basename(c))
        except Exception:
            h = None
        if h and os.path.isfile(h):
            return h
    return ""


def resolve_launch():
    try:
        if is_frozen():
            exe = os.path.abspath(sys.executable)
            if os.path.isfile(exe):
                return {"exe": exe, "script": "", "console": True, "python": ""}
            return {"error": "当前程序路径不存在: " + exe}
        if is_portable_source():
            here = os.path.abspath(sys.executable)
            pyw = os.path.join(os.path.dirname(here), "pythonw.exe")
            python = pyw if _can_ascii(pyw) else (here if _can_ascii(here) else "")
            return {"exe": python, "script": launcher_path(), "console": False, "python": python}
        exe = _search_exe()
        if exe:
            logging.warning(f"源码启动但程序目录已有可执行文件，启动项指向: {exe}")
            return {"exe": exe, "script": "", "console": True, "python": ""}
        return {"error": "未找到 NodaniumLauncher.exe，且源码目录不可用"}
    except Exception as e:
        return {"error": str(e)}


def _can_ascii(path):
    if not path or not os.path.isfile(path):
        return False
    try:
        path.encode("ascii")
        return True
    except Exception:
        return False


def _quote(path):
    p = os.path.abspath(path).replace('"', '')
    return f'"{p}"'


def build_command(exe, script, args):
    parts = [_quote(exe)]
    if script:
        parts.append(_quote(script))
    a = (args or "").strip()
    if a:
        parts.append(a)
    return " ".join(parts)


def build_autostart_command():
    info = resolve_launch()
    if info.get("error"):
        return None, info["error"]
    return build_command(info["exe"], info["script"], "-s"), None


def build_open_command(args):
    info = resolve_launch()
    if info.get("error"):
        return None, info["error"]
    return build_command(info["exe"], info["script"], args), None


# ========================== 注册表 ==========================

def _winreg():
    import winreg
    return winreg


def _parse_run_value(cmd):
    s = (cmd or "").strip()
    if s.startswith('"'):
        end = s.find('"', 1)
        return s[1:end] if end > 0 else s.strip('"')
    return s.split(" ")[0]


def run_value_state():
    winreg = _winreg()
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            try:
                val, _ = winreg.QueryValueEx(k, RUN_VALUE)
            except FileNotFoundError:
                return "missing", ""
    except FileNotFoundError:
        return "missing", ""
    except Exception as e:
        return "error", str(e)
    exe = _parse_run_value(val)
    if not exe or not os.path.isfile(exe):
        return "stale", val
    return "ok", val


def _approved_state(winreg, value):
    for path in (APPROVED_KEY, APPROVED32_KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ) as k:
                try:
                    raw, _ = winreg.QueryValueEx(k, value)
                except FileNotFoundError:
                    continue
                if isinstance(raw, (bytes, bytearray)) and len(raw) >= 1:
                    b = raw[0]
                    if b in DISABLED_BYTES:
                        return "disabled"
                    if b in ENABLED_BYTES:
                        return "enabled"
        except Exception:
            continue
    return "unknown"


def _clear_approved(winreg, value):
    for path in (APPROVED_KEY, APPROVED32_KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as k:
                try:
                    winreg.DeleteValue(k, value)
                except FileNotFoundError:
                    pass
        except Exception:
            pass


def repair_approved():
    winreg = _winreg()
    _clear_approved(winreg, RUN_VALUE)
    _clear_approved(winreg, RUN_VALUE + ".exe")
    legacy = _legacy_values(winreg)
    for name in legacy:
        _clear_approved(winreg, name)


def _legacy_values(winreg):
    found = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            i = 0
            while True:
                try:
                    name, val, _ = winreg.EnumValue(k, i)
                except OSError:
                    break
                i += 1
                low = (val or "").lower()
                if name == RUN_VALUE:
                    continue
                if "nodanium" in low and any(m.lower() in low for m in LEGACY_MARKERS):
                    found.append(name)
    except Exception:
        pass
    return found


def get_autostart_status():
    if sys_type == "Windows":
        try:
            state, _ = run_value_state()
            if state == "ok":
                sub = _approved_state(_winreg(), RUN_VALUE)
                if sub == "disabled":
                    try:
                        repair_approved()
                        logging.info("已清除启动项禁用标记")
                    except Exception as e:
                        logging.warning(f"清除禁用标记失败: {e}")
                return True
            return False
        except Exception:
            return False
    if sys_type == "Linux":
        return os.path.exists(linux_desktop_path())
    return False


def set_autostart(enable):
    if sys_type == "Windows":
        return _set_autostart_win(enable)
    if sys_type == "Linux":
        return _set_autostart_linux(enable)
    return False, "当前系统不支持"


def _set_autostart_win(enable):
    try:
        winreg = _winreg()
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as k:
            for name in _legacy_values(winreg):
                try:
                    winreg.DeleteValue(k, name)
                except Exception:
                    pass
            if enable:
                cmd, err = build_autostart_command()
                if err:
                    return False, err
                winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(k, RUN_VALUE)
                except FileNotFoundError:
                    pass
        repair_approved()
        if enable:
            state, val = run_value_state()
            if state != "ok":
                return False, f"写入后校验失败: {val}"
            logging.info(f"开机自启已写入: {val}")
        else:
            logging.info("开机自启已取消")
        return True, None
    except Exception as e:
        logging.warning(f"写注册表失败: {e}")
        return False, str(e)


# ========================== 单实例锁 ==========================

def get_lock_path():
    import tempfile
    return os.path.join(tempfile.gettempdir(), ".Nodanium.lock")


def legacy_lock_paths():
    import tempfile
    d = tempfile.gettempdir()
    return [os.path.join(d, n) for n in
            (".NodaniumLauncher.py.lock", ".NodaniumLauncher.exe.lock",
             f".{os.path.basename(sys.argv[0])}.lock")]


def clear_locks():
    removed = 0
    for p in [get_lock_path()] + legacy_lock_paths():
        try:
            if os.path.exists(p):
                os.remove(p)
                removed += 1
        except Exception:
            pass
    return removed


# ========================== Linux ==========================

def linux_desktop_path():
    return os.path.expanduser("~/.config/autostart/nodanium.desktop")


def _linux_exec_line(args):
    info = resolve_launch()
    if info.get("error"):
        return None, info["error"]
    parts = [info["exe"]]
    if info.get("script"):
        parts.append(info["script"])
    if args:
        parts.append(args)
    return " ".join(_quote(p) for p in parts), None


def _set_autostart_linux(enable):
    try:
        desktop_path = linux_desktop_path()
        if enable:
            exec_line, err = _linux_exec_line("-s")
            if err:
                return False, err
            os.makedirs(os.path.dirname(desktop_path), exist_ok=True)
            with open(desktop_path, "w") as f:
                f.write("[Desktop Entry]\nType=Application\nName=Nodanium\n"
                        f"Exec={exec_line}\nX-GNOME-Autostart-enabled=true\nTerminal=false\n")
        else:
            if os.path.exists(desktop_path):
                os.remove(desktop_path)
        return True, None
    except Exception as e:
        return False, str(e)
