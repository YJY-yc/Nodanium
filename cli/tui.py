# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import sys
import argparse
import termios
import tty

from . import ansi, i18n, download
from .ansi import Ansi, paint

FIELDS = ("url", "output", "filename", "jobs", "chunk_size", "limit")


# -------------------------- 终端按键 --------------------------
class _RawKeys:
    def __init__(self):
        self._fd = None
        self._saved = None

    def __enter__(self):
        self._fd = sys.stdin.fileno()
        if os.name != "nt" and sys.stdin.isatty():
            self._saved = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        return self

    def __exit__(self, *exc):
        if self._saved is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
            self._saved = None
        return False

    def read(self) -> str:
        ch = sys.stdin.read(1)
        if ch != "\x1b":
            return ch
        seq = ""
        if os.name != "nt":
            import select
            for _ in range(2):
                r, _, _ = select.select([sys.stdin], [], [], 0.02)
                if not r:
                    break
                seq += sys.stdin.read(1)
        return "\x1b" + seq


# -------------------------- 表单状态 --------------------------
def _defaults() -> dict:
    return {
        "url": "",
        "output": os.getcwd(),
        "filename": "",
        "jobs": "16",
        "chunk_size": "10",
        "limit": "0",
    }


def _field_label(key: str) -> str:
    return i18n.t(f"tui.field.{key}")


def _validate(form) -> str:
    if not form["url"].strip():
        return i18n.t("tui.err_url")
    for key in ("jobs", "chunk_size"):
        try:
            val = int(form[key])
        except ValueError:
            return i18n.t("tui.err_number", field=_field_label(key))
        if val < 1:
            return i18n.t("tui.err_positive", field=_field_label(key))
    try:
        if float(form["limit"]) < 0:
            return i18n.t("tui.err_positive", field=_field_label("limit"))
    except ValueError:
        return i18n.t("tui.err_number", field=_field_label("limit"))
    return ""


def _build_args(form) -> argparse.Namespace:
    return argparse.Namespace(
        url=form["url"].strip(),
        output=form["output"].strip() or os.getcwd(),
        filename=form["filename"].strip(),
        jobs=max(1, min(int(form["jobs"]), 128)),
        chunk_size=float(form["chunk_size"]),
        cache=32.0,
        limit=float(form["limit"]),
        timeout=60.0,
        header=[],
        header_json="",
        no_ssl_check=False,
        backend="auto",
        run="",
        speed_unit="MB/s",
        json=False,
    )


# -------------------------- 绘制 --------------------------
def _clear():
    sys.stdout.write("\033[H\033[2J")
    sys.stdout.flush()


def _draw(form, cursor: int, focus: int, error: str, width: int):
    _clear()
    title = i18n.t("tui.title")
    print(paint(f"  {title}", Ansi.BOLD, Ansi.CYAN))
    print(paint("  " + "-" * (width - 4), Ansi.GRAY))
    for idx, key in enumerate(FIELDS):
        mark = paint(">", Ansi.GREEN) if idx == focus else " "
        line = form[key]
        if idx == focus:
            head = line[:cursor]
            tail = line[cursor:]
            shown = head + paint("_", Ansi.WHITE) + tail
        else:
            shown = line
        if not shown:
            shown = paint(i18n.t("tui.empty"), Ansi.GRAY)
        label = paint(_field_label(key) + ":", Ansi.CYAN)
        print(f"  {mark} {label} {shown}")
    print(paint("  " + "-" * (width - 4), Ansi.GRAY))
    if error:
        print(paint("  " + error, Ansi.RED))
    else:
        print("  " + paint(i18n.t("tui.hint_entry"), Ansi.DIM))
    print("  " + paint(i18n.t("tui.hint_keys"), Ansi.DIM))
    sys.stdout.flush()


def _draw_result(lines):
    print()
    for text in lines:
        print("  " + text)
    print()
    print("  " + paint(i18n.t("tui.back_hint"), Ansi.DIM))


# -------------------------- 下载执行 --------------------------
def _reopen():
    """下载结束后重新进入按键模式（run_download 会改动终端状态）。"""
    holder = _RawKeys()
    holder.__enter__()
    global _ACTIVE_KEYS
    _ACTIVE_KEYS = holder
    return holder


_ACTIVE_KEYS = None


def _run(form) -> int:
    args = _build_args(form)
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    download._print_welcome_banner()
    rc = download.run_download(args)
    lines = []
    if rc == 0:
        lines.append(paint(i18n.t("tui.result_ok"), Ansi.GREEN))
    elif rc == 130:
        lines.append(paint(i18n.t("done.aborted"), Ansi.YELLOW))
    else:
        lines.append(paint(i18n.t("tui.result_fail", code=rc), Ansi.RED))
    _draw_result(lines)
    return rc


# -------------------------- 主循环 --------------------------
def run_tui() -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(paint(i18n.t("tui.not_tty"), Ansi.RED))
        return 2
    form = _defaults()
    cursor = 0
    focus = 0
    error = ""
    last_rc = 0
    try:
        width = max(40, min(os.get_terminal_size().columns, 78))
    except Exception:
        width = 60

    with _RawKeys() as keys:
        while True:
            _draw(form, cursor, focus, error, width)
            key = keys.read()
            if key in ("\x03", "\x04"):
                return last_rc
            if key in ("\r", "\n"):
                err = _validate(form)
                if err:
                    error = err
                    continue
                with _RawKeys():
                    pass
                last_rc = _run(form)
                with _RawKeys():
                    pass
                last_rc = _run(form)
                keys = _reopen()
                error = ""
                continue
            if key in ("\t", "\x1b[B"):
                focus = (focus + 1) % len(FIELDS)
                cursor = len(form[FIELDS[focus]])
                error = ""
                continue
            if key == "\x1b[A":
                focus = (focus - 1) % len(FIELDS)
                cursor = len(form[FIELDS[focus]])
                error = ""
                continue
            if key in ("\x1b[D", "\x02"):
                cursor = max(0, cursor - 1)
                continue
            if key in ("\x1b[C", "\x06"):
                cursor = min(len(form[FIELDS[focus]]), cursor + 1)
                continue
            if key in ("\x7f", "\x08"):
                name = FIELDS[focus]
                if cursor > 0:
                    form[name] = form[name][:cursor - 1] + form[name][cursor:]
                    cursor -= 1
                error = ""
                continue
            if key in ("\x1b[3~",):
                name = FIELDS[focus]
                form[name] = form[name][:cursor] + form[name][cursor + 1:]
                error = ""
                continue
            if key and key.isprintable():
                name = FIELDS[focus]
                form[name] = form[name][:cursor] + key + form[name][cursor:]
                cursor += 1
                error = ""
    return last_rc
