# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import platform

def is_admin():
    sys_type = platform.system()
    if sys_type == "Windows":
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
    elif sys_type == "Linux" or sys_type == "Darwin":
        # Linux/macOS: 检查是否为root用户
        return os.getuid() == 0
    return False