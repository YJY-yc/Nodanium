# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT

import os
import sys
import subprocess
import platform

SYS = platform.system()
IS_WINDOWS = SYS == "Windows"


def get_creationflags():
    
    if IS_WINDOWS:
        return getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return 0


def get_startupinfo():
    """Windows 返回隐藏窗口的 STARTUPINFO，其他平台返回 None。"""
    if not IS_WINDOWS:
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return si


def no_window_kwargs():
    """返回可用于 Popen/run/call 的隐藏窗口参数；Linux 返回空 dict。"""
    if not IS_WINDOWS:
        return {}
    return {"creationflags": get_creationflags(), "startupinfo": get_startupinfo()}


def popen(args, **kwargs):
    kw = no_window_kwargs()
    kw.update(kwargs)
    return subprocess.Popen(args, **kw)


def run(args, **kwargs):
    kw = no_window_kwargs()
    kw.update(kwargs)
    return subprocess.run(args, **kw)


def call(args, **kwargs):
    kw = no_window_kwargs()
    kw.update(kwargs)
    return subprocess.call(args, **kw)


def check_output(args, **kwargs):
    kw = no_window_kwargs()
    kw.update(kwargs)
    return subprocess.check_output(args, **kw)


def open_path(path):
    """用系统默认方式打开文件/目录。"""
    if IS_WINDOWS:
        os.startfile(path)
    else:
        popen(["xdg-open", path])



def detach_kwargs():
    """后台完全脱离的启动参数（Windows 隐藏窗口且不继承控制台）。"""
    if not IS_WINDOWS:
        return {"start_new_session": True}
    return {"creationflags": get_creationflags() | getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            "startupinfo": get_startupinfo(),
            "close_fds": True}
