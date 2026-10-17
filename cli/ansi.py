# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import re
import sys

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def strip_len(text: str) -> int:
    return len(_ANSI_RE.sub("", text))


class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"


_MODE = "auto"  # auto | always | never


def set_mode(mode: str) -> None:
    global _MODE
    if mode in ("auto", "always", "never"):
        _MODE = mode


def color_enabled() -> bool:
    if _MODE == "always":
        return True
    if _MODE == "never":
        return False
    if os.environ.get("NO_COLOR") or os.environ.get("NODANIUM_NO_COLOR"):
        return False
    if os.environ.get("TERM", "") == "dumb":
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def paint(text: str, *styles: str) -> str:
    if not color_enabled() or not styles:
        return text
    return "".join(styles) + text + Ansi.RESET
