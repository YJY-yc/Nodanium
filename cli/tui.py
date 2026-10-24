# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import sys
import time
import argparse

from . import i18n, download
from .ansi import Ansi, paint

if os.name != "nt":
    import select
    import termios
    import tty

FIELDS = ("url", "output", "filename", "jobs", "chunk_size", "limit")
LIST_SIZE = 12


# -------------------------- 终端按键 --------------------------
class _Term:
    """cbreak 模式开关，下载前后可以反复挂起/恢复。"""

    def __init__(self):
        self._fd = None
        self._saved = None

    def enter(self):
        if os.name == "nt":
            return
        try:
            self._fd = sys.stdin.fileno()
        except Exception:
            return
        if not sys.stdin.isatty() or self._saved:
            return
        try:
            self._saved = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
        except Exception:
            self._saved = None

    def leave(self):
        if self._saved is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
            except Exception:
                pass
            self._saved = None

    def _read_byte(self, timeout=None) -> bytes:
        """从 fd 直接读一个字节（绕过 sys.stdin 缓冲），超时返回空 bytes。"""
        fd = self._fd
        if fd is None:
            data = sys.stdin.buffer.read(1) if hasattr(sys.stdin, "buffer") \
                else sys.stdin.read(1).encode("utf-8", "ignore")
            return data or b""
        if timeout is not None:
            ready, _, _ = select.select([fd], [], [], timeout)
            if not ready:
                return b""
        return os.read(fd, 1)

    def read(self) -> str:
        try:
            first = self._read_byte()
            if not first:
                return ""
            if first != b"\x1b":
                return _decode_utf8(self, first)
            return _read_escape(self)
        except KeyboardInterrupt:
            return "\x03"
        except OSError:
            return "\x04"


# -------------------------- 通用绘制 --------------------------
def _decode_utf8(term, first: bytes) -> str:
    """按 UTF-8 首字节长度补齐多字节字符，避免中文输入丢失。"""
    head = first[0]
    if head < 0x80:
        return first.decode("latin-1")
    need = 1 if head >> 5 == 0b110 else 2 if head >> 4 == 0b1110 else 3
    raw = first
    for _ in range(need):
        nxt = term._read_byte(timeout=0.05)
        if not nxt:
            break
        raw += nxt
    return raw.decode("utf-8", "replace")


def _read_escape(term) -> str:
    """解析 ESC 序列。单独 ESC（80ms 内无后续）才视为取消键。"""
    nxt = term._read_byte(timeout=0.08)
    if not nxt:
        return "\x1b"
    ch = nxt.decode("latin-1")
    if ch == "[":
        body = ""
        for _ in range(8):
            raw = term._read_byte(timeout=0.08)
            if not raw:
                break
            body += raw.decode("latin-1")
            if body[-1].isalpha() or body[-1] == "~":
                return "\x1b[" + body
        return "\x1b[" + body
    if ch == "O":
        raw = term._read_byte(timeout=0.08)
        return "\x1bO" + raw.decode("latin-1")
    return "\x1b" + ch


def _width(default: int = 60) -> int:
    try:
        return max(40, min(os.get_terminal_size().columns, 78))
    except Exception:
        return default


def _term_rows(default: int = 30) -> int:
    try:
        return max(12, os.get_terminal_size().lines)
    except Exception:
        return default


def _fmt_size(n) -> str:
    try:
        n = int(n or 0)
    except Exception:
        n = 0
    if n <= 0:
        return "-"
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KiB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MiB"
    return f"{n / 1024 ** 3:.2f} GiB"


def _status_color(status: str) -> str:
    if status.startswith("已完成"):
        return Ansi.GREEN
    if status.startswith("下载中"):
        return Ansi.CYAN
    if status.startswith("已中断") or status.startswith("部分"):
        return Ansi.YELLOW
    if status.startswith("失败"):
        return Ansi.RED
    return Ansi.GRAY


def _frame(title: str, body):
    width = _width()
    lines = [paint("  " + title, Ansi.BOLD, Ansi.CYAN),
             paint("  " + "-" * (width - 4), Ansi.GRAY)]
    lines.extend(body)
    lines.append(paint("  " + "-" * (width - 4), Ansi.GRAY))
    sys.stdout.write("\033[H\033[2J" + "\n".join(lines) + "\n")
    sys.stdout.flush()


# -------------------------- 下载记录 --------------------------
MENU_ITEMS = ("new", "refresh", "settings", "quit")
FOCUS_MENU = "menu"
FOCUS_LIST = "list"
FOCUS_CMD = "cmd"


def _load_records():
    try:
        import DownloadHistory
        return DownloadHistory.load()
    except Exception:
        return []


_ROWS_CACHE = {"value": LIST_SIZE}


def _list_rows_now() -> int:
    return _ROWS_CACHE["value"]


def _list_rows(reserve: int = 16) -> int:
    """列表可见行数：按终端高度留出菜单/命令行/提示的固定占用。"""
    return max(3, min(LIST_SIZE, _term_rows() - reserve))


def _visible_records(records, offset, rows=None):
    """返回 (start, shown)：offset 表示从最新往旧的位移，shown 保持倒序显示。"""
    total = len(records)
    if total == 0:
        return 0, []
    rows = rows or _list_rows()
    offset = max(0, min(offset, total - 1))
    end = max(0, total - offset)
    start = max(0, end - rows)
    return start, list(reversed(records[start:end]))


def _record_line(rec, selected):
    name = (rec.get("filename") or "-")[:24]
    status = rec.get("status") or "-"
    size = _fmt_size(rec.get("file_size"))
    ts = (rec.get("timestamp") or "")[:16]
    src = rec.get("source") or "gui"
    mark = paint(">", Ansi.GREEN) if selected else " "
    head = paint(f"{name:<24}", Ansi.WHITE)
    if selected:
        head = paint("\033[7m" + f"{name:<24}" + "\033[0m", Ansi.WHITE)
    return ("  " + mark + " " + head
            + " " + paint(f"{status:<14}", _status_color(status))
            + " " + paint(f"{size:>10}", Ansi.GRAY)
            + " " + paint(f"{src:<4}", Ansi.MAGENTA)
            + " " + paint(ts, Ansi.DIM))


def _record_lines(records, offset, sel, rows=None):
    body = []
    if not records:
        body.append("  " + paint(i18n.t("tui.list_empty"), Ansi.DIM))
        return body
    body.append("  " + paint(i18n.t("tui.list_head"), Ansi.BOLD, Ansi.WHITE))
    start, shown = _visible_records(records, offset, rows)
    for idx, rec in enumerate(shown):
        body.append(_record_line(rec, idx == sel))
    total = len(records)
    if total > len(shown):
        body.append("  " + paint(i18n.t("tui.list_range",
                                        start=start + 1,
                                        end=start + len(shown),
                                        total=total), Ansi.DIM))
    return body


def _current_record(records, offset, sel, rows=None):
    start, shown = _visible_records(records, offset, rows)
    if 0 <= sel < len(shown):
        return shown[sel]
    return None


def _delete_record(rec) -> bool:
    """删除记录；若有未完成断点则一问删除。"""
    _TERM.leave()
    sys.stdout.write("\033[H\033[2J")
    print(paint("  " + i18n.t("tui.confirm_delete",
                             name=rec.get("filename") or "-"), Ansi.YELLOW))
    print("  " + paint(i18n.t("tui.confirm_yes_no"), Ansi.DIM))
    sys.stdout.flush()
    _TERM.enter()
    key = _TERM.read()
    if key not in ("y", "Y"):
        return False
    try:
        import DownloadHistory
        return DownloadHistory.delete_record(rec.get("uuid") or "")
    except Exception:
        return False


# -------------------------- 命令行 --------------------------
CLI_COMMANDS = ("download", "tui", "help", "version")

# (短选项, 长选项, 值占位符, 值类型, i18n 帮助键, 是否可重复)
DOWNLOAD_OPTIONS = (
    ("-o", "--output", "<dir>", "path", "opt.output", False),
    ("-f", "--filename", "<name>", "text", "opt.filename", False),
    ("-j", "--jobs", "<N>", "int", "opt.jobs", False),
    ("-s", "--chunk-size", "<MB>", "float", "opt.chunk_size", False),
    (None, "--cache", "<MB>", "float", "opt.cache", False),
    (None, "--limit", "<KB/s>", "float", "opt.limit", False),
    (None, "--timeout", "<sec>", "float", "opt.timeout", False),
    ("-H", "--header", '"K: V"', "text", "opt.header", True),
    (None, "--header-json", "<json>", "text", "opt.header_json", False),
    (None, "--no-ssl-check", "", "flag", "opt.no_ssl_check", False),
    (None, "--backend", "<auto|requests|curl>", "choice", "opt.backend", False),
    (None, "--run", "<open|shutdown>", "choice", "opt.run", False),
    (None, "--speed-unit", "<MB/s|MiB/s|Mbps>", "choice", "opt.speed_unit", False),
    (None, "--json", "", "flag", "opt.json", False),
)

GLOBAL_OPTIONS = (
    (None, "--lang", "<en|ch_zn>", "choice", "cli.opt_lang", False),
    (None, "--color", "<auto|always|never>", "choice", "cli.opt_color", False),
)

COMMAND_HELP = {
    "download": ("cli.cmd_download", "nodanium download <url> [options]",
                 DOWNLOAD_OPTIONS),
    "tui": ("cli.cmd_tui", "nodanium tui", ()),
    "help": ("cli.cmd_help", "nodanium help [command]", ()),
    "version": ("cli.opt_version", "nodanium version", ()),
}

OPTION_HINTS = {}
for _opt in DOWNLOAD_OPTIONS + GLOBAL_OPTIONS:
    _short, _long = _opt[0], _opt[1]
    if _short:
        OPTION_HINTS[_short] = _long
    OPTION_HINTS[_long] = ""


def _opt_forms(opt):
    short, long_name = opt[0], opt[1]
    return [f for f in (short, long_name) if f]


def _opt_display(opt):
    short, long_name, value = opt[0], opt[1], opt[2]
    name = f"{short}, {long_name}" if short else long_name
    return f"{name} {value}".strip()


def _opt_lookup(token: str):
    for opt in DOWNLOAD_OPTIONS + GLOBAL_OPTIONS:
        if token in _opt_forms(opt):
            return opt
    return None


def _usage_used(command: str):
    """从命令行里提取已出现的选项 token（跳过选项值）。"""
    tokens = command.split()[1:]
    used = []
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if not token.startswith("-"):
            idx += 1
            continue
        name = token.split("=", 1)[0]
        used.append(name)
        opt = _opt_lookup(name)
        if opt is not None and opt[3] != "flag" and "=" not in token:
            idx += 2
        else:
            idx += 1
    return used


def _usage_remaining(command: str):
    """返回 (可用选项, 可重复选项, 已用选项, 未知 token)。"""
    used = _usage_used(command)
    used_canonical = set()
    unknown = []
    for token in used:
        opt = _opt_lookup(token)
        if opt is None:
            if token not in ("-", "--"):
                unknown.append(token)
            continue
        used_canonical.add(opt[1])
    available, repeatable, applied = [], [], []
    for opt in DOWNLOAD_OPTIONS + GLOBAL_OPTIONS:
        if opt[1] in used_canonical:
            if opt[5]:
                repeatable.append(opt)
            else:
                applied.append(opt)
        else:
            available.append(opt)
    return available, repeatable, applied, unknown


def _command_arg_error(command: str) -> str:
    """轻量校验：未知选项、选项缺值、数值类型错误。"""
    tokens = command.split()[1:]
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if not token.startswith("-"):
            idx += 1
            continue
        name, eq, inline = token.partition("=")
        opt = _opt_lookup(name)
        if opt is None:
            return i18n.t("tui.usage_unknown_opt", opt=name)
        kind = opt[3]
        if kind == "flag":
            idx += 1
            continue
        if eq:
            value = inline
            idx += 1
        else:
            if idx + 1 >= len(tokens):
                return i18n.t("tui.usage_missing_value", opt=name)
            value = tokens[idx + 1]
            idx += 2
        if kind in ("int", "float"):
            try:
                if kind == "int":
                    int(value)
                else:
                    float(value)
            except ValueError:
                return i18n.t("tui.usage_bad_number", opt=name, value=value)
    return ""


def _usage_limit() -> int:
    rows = _term_rows()
    if rows < 20:
        return 3
    if rows < 28:
        return 4
    return 6


def _command_usage_lines(command: str, limit: int = 0, max_lines: int = 0):
    """生成用法与可并存参数面板。"""
    tokens = command.split()
    if not tokens:
        return []
    entry = COMMAND_HELP.get(tokens[0])
    if entry is None:
        return [paint(i18n.t("tui.usage_unknown_cmd", cmd=tokens[0]), Ansi.RED)]
    limit = limit or _usage_limit()
    if max_lines:
        limit = max(1, min(limit, max_lines - 2))
    _key, usage, opts = entry
    lines = [paint(i18n.t("tui.usage_line") + ": " + usage, Ansi.CYAN)]
    if not opts:
        lines.append(paint(i18n.t("tui.usage_no_opt"), Ansi.DIM))
        return lines
    available, repeatable, applied, unknown = _usage_remaining(" ".join(tokens))
    if unknown:
        unknown = []
    used_state = []
    if applied:
        used_state.append(paint(i18n.t("tui.usage_applied") + ": ", Ansi.YELLOW)
                          + paint(" ".join(o[1] for o in applied), Ansi.YELLOW))
    if repeatable:
        used_state.append(paint(i18n.t("tui.usage_repeat") + ": ", Ansi.MAGENTA)
                          + paint(" ".join(o[1] for o in repeatable), Ansi.MAGENTA))
    if _term_rows() < 22:
        if available:
            names = " ".join(o[1] for o in available[:8])
            more = i18n.t("tui.usage_more", n=len(available) - 8) \
                if len(available) > 8 else ""
            lines.append("    " + paint(names + (" " + more if more else ""),
                                        Ansi.GREEN))
        lines.extend(used_state)
        return lines
    show = max(1, limit - len(used_state))
    lines.append(paint(i18n.t("tui.usage_available") + ":", Ansi.BOLD))
    for opt in available[:show]:
        lines.append("    " + paint(_opt_display(opt), Ansi.GREEN)
                     + "  " + paint(i18n.t(opt[4])[:40], Ansi.DIM))
    if len(available) > show:
        lines.append("    " + paint(i18n.t("tui.usage_more",
                                           n=len(available) - show), Ansi.DIM))
    lines.extend(used_state)
    return lines


def _completions(text: str):
    """根据当前输入给出候选：命令名 / 选项名。"""
    stripped = text.lstrip()
    if not stripped:
        return list(CLI_COMMANDS)
    head, sep, tail = stripped.partition(" ")
    if not sep:
        return [c for c in CLI_COMMANDS if c.startswith(head)]
    if tail.startswith("-") and " " not in tail.strip():
        return [o for o in OPTION_HINTS if o.startswith(tail.strip())]
    return []


def _apply_completion(text: str, candidates) -> str:
    if not candidates:
        return text
    stripped = text.lstrip()
    if " " not in stripped:
        return candidates[0] + " "
    prefix = text[:len(text) - len(text.lstrip())]
    head, sep, tail = stripped.partition(" ")
    if tail.startswith("-") and " " not in tail.strip():
        return f"{prefix}{head} {candidates[0]} "
    return text


def _run_cli(command: str) -> int:
    import shlex
    try:
        argv = shlex.split(command)
    except ValueError as e:
        print(paint(str(e), Ansi.RED))
        return 2
    if not argv:
        return 0
    if argv[0] == "nodanium":
        argv = argv[1:]
    try:
        from .cli import main as cli_main
        return cli_main(argv)
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as e:
        print(paint(f"{type(e).__name__}: {e}", Ansi.RED))
        return 1


def _execute_command(command: str):
    _TERM.leave()
    sys.stdout.write("\033[H\033[2J")
    sys.stdout.flush()
    print(paint("$ " + command, Ansi.BOLD, Ansi.GREEN))
    print()
    try:
        rc = _run_cli(command)
    except KeyboardInterrupt:
        rc = 130
    _TERM.enter()
    print()
    print(paint(i18n.t("tui.cmd_done", code=rc), Ansi.DIM))
    sys.stdout.flush()
    form = _command_form(command)
    if form is not None and rc in (0, 130, 1, 3):
        _after_select(form, rc)
    else:
        print("  " + paint(i18n.t("tui.back_hint"), Ansi.DIM))
        sys.stdout.flush()
        _TERM.read()


def _command_form(command: str):
    """从 `download ...` 命令里解析出后续操作需要的路径信息。"""
    import shlex
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if argv and argv[0] == "nodanium":
        argv = argv[1:]
    if not argv or argv[0] != "download":
        return None
    form = {"url": "", "output": "", "filename": ""}
    idx = 1
    while idx < len(argv):
        token = argv[idx]
        if token in ("-o", "--output") and idx + 1 < len(argv):
            form["output"] = argv[idx + 1]
            idx += 2
            continue
        if token in ("-f", "--filename") and idx + 1 < len(argv):
            form["filename"] = argv[idx + 1]
            idx += 2
            continue
        if token.startswith("--output=") or token.startswith("--filename="):
            key, _, value = token.partition("=")
            form["output" if key == "--output" else "filename"] = value
            idx += 1
            continue
        if not token.startswith("-") and not form["url"]:
            form["url"] = token
        idx += 1
    if not form["url"]:
        return None
    return form


# -------------------------- 记录详情 --------------------------
def _record_detail_lines(rec):
    rows = (
        ("uuid", rec.get("uuid") or "-"),
        ("filename", rec.get("filename") or "-"),
        ("url", rec.get("url") or "-"),
        ("save_path", rec.get("save_path") or "-"),
        ("status", rec.get("status") or "-"),
        ("file_size", _fmt_size(rec.get("file_size"))),
        ("source", rec.get("source") or "gui"),
        ("timestamp", rec.get("timestamp") or "-"),
    )
    body = [""]
    for key, value in rows:
        body.append(f"  {paint(i18n.t('tui.detail_' + key) + ':', Ansi.CYAN)} "
                    + str(value))
    body.append("")
    body.append("  " + paint(i18n.t("tui.detail_resume_hint"), Ansi.DIM))
    return body


def _show_detail(rec):
    body = _record_detail_lines(rec)
    body.append("  " + paint(i18n.t("tui.back_hint"), Ansi.DIM))
    _frame(i18n.t("tui.detail_title"), body)
    _TERM.read()


# -------------------------- 继续下载 --------------------------
def _progress_path_for(rec):
    try:
        import NewDownloadCore as core
    except Exception:
        return ""
    filename = rec.get("filename") or ""
    if not filename:
        return ""
    return os.path.join(core.get_download_process_dir(),
                        f"{filename}_{core.PROGRESS_JSON_NAME}")


def _can_resume(rec):
    if (rec.get("status") or "").startswith("已完成"):
        return False
    path = _progress_path_for(rec)
    return bool(path) and os.path.exists(path)


def _resume_record(rec):
    path = _progress_path_for(rec)
    if not path or not os.path.exists(path):
        return
    form = _defaults()
    form["url"] = rec.get("url") or ""
    form["output"] = rec.get("save_path") or _download_dir()
    form["filename"] = rec.get("filename") or ""
    _run_download(form, resume_path=path)


# -------------------------- 主页 --------------------------
def _draw_menu(menu_idx, focus):
    body = ["  " + paint(i18n.t("tui.menu_title"), Ansi.BOLD, Ansi.WHITE)]
    for idx, key in enumerate(MENU_ITEMS):
        active = idx == menu_idx
        arrow = paint(">", Ansi.GREEN) if active else " "
        text = i18n.t(f"tui.menu_{key}")
        if active:
            text = paint("\033[7m " + text.ljust(28) + "\033[0m", Ansi.WHITE)
        else:
            text = paint("  " + text.ljust(28), Ansi.WHITE)
        body.append("  " + arrow + " " + text)
    return body


def _tokenize_colored(text: str):
    """按 token 切分并标注类型：命令/位置参数/选项/选项值。"""
    spans = []
    idx = 0
    first = True
    pending_opt = False
    for token in text.split(" "):
        if idx:
            spans.append((" ", "space", idx - 1))
        kind = "arg"
        if token.startswith("-") and token != "":
            kind = "opt"
            pending_opt = "=" not in token
        elif first and token:
            kind = "cmd"
            pending_opt = False
        elif pending_opt:
            kind = "value"
            pending_opt = False
        elif first:
            kind = "cmd"
        spans.append((token, kind, idx))
        idx += len(token) + 1
        first = False
    return spans


TOKEN_COLORS = {
    "cmd": (Ansi.BOLD, Ansi.CYAN),
    "arg": (Ansi.WHITE,),
    "opt": (Ansi.GREEN,),
    "value": (Ansi.YELLOW,),
    "space": (Ansi.GRAY,),
}


def _colorize(text: str, cursor: int = -1, active: bool = False) -> str:
    """给命令行着色；active 时在 cursor 处插入光标下划线。"""
    if not text:
        return ""
    spans = _tokenize_colored(text)
    out = []
    for token, kind, start in spans:
        style = TOKEN_COLORS[kind]
        if active and start <= cursor < start + len(token):
            off = cursor - start
            out.append(paint(token[:off], *style) + paint("_", Ansi.WHITE)
                       + paint(token[off:], *style))
        else:
            out.append(paint(token, *style))
    if active and (cursor == len(text) or not text):
        out.append(paint("_", Ansi.WHITE))
    return "".join(out)


def _draw_command(text, cursor, focus, hints, max_lines: int = 0):
    body = ["", "  " + paint(i18n.t("tui.cmd_title"), Ansi.BOLD, Ansi.WHITE)]
    if focus == FOCUS_CMD:
        shown = _colorize(text, cursor, True)
    else:
        shown = _colorize(text) if text else ""
    if not text:
        shown = shown or paint(i18n.t("tui.cmd_placeholder"), Ansi.GRAY)
    body.append("  " + paint("$", Ansi.GREEN) + " " + shown)
    if hints:
        body.append("  " + paint(i18n.t("tui.cmd_hints") + ": "
                                  + "  ".join(hints[:6]), Ansi.DIM))
    stripped = text.strip()
    if stripped and " " not in stripped:
        body.append("  " + paint(i18n.t("tui.cmd_usage_hint"), Ansi.DIM))
    elif stripped:
        for line in _command_usage_lines(stripped, max_lines=max_lines):
            body.append("  " + line)
    return body


def _build_home(records, offset, sel, menu_idx, focus, cmd_text, cmd_cursor,
                error, rows, cmd_budget: int = 12):
    menu = _draw_menu(menu_idx, focus)
    cmd_block = _draw_command(cmd_text, cmd_cursor, focus,
                              _completions(cmd_text) if focus == FOCUS_CMD else [],
                              max_lines=cmd_budget)
    hint_key = {FOCUS_MENU: "tui.hint_menu",
                FOCUS_LIST: "tui.hint_list",
                FOCUS_CMD: "tui.hint_cmd"}[focus]
    body = list(menu)
    body.append("")
    body.append("  " + paint(i18n.t("tui.list_title", n=len(records)),
                             Ansi.BOLD, Ansi.WHITE))
    body.extend(_record_lines(records, offset,
                              sel if focus == FOCUS_LIST else -1, rows))
    body.extend(cmd_block)
    body.append("")
    body.append("  " + paint(error, Ansi.RED) if error
                else "  " + paint(i18n.t(hint_key), Ansi.DIM))
    return body


def _home(records, offset, sel, menu_idx, focus, cmd_text, cmd_cursor, error):
    """渲染主页：先按最大列表行数排布，超屏则逐步收缩列表行数。"""
    total = _term_rows() - 3
    rows = _list_rows()
    body = _build_home(records, offset, sel, menu_idx, focus,
                       cmd_text, cmd_cursor, error, rows)
    cmd_budget = 12
    while len(body) > total and cmd_budget > 2:
        cmd_budget -= 1
        body = _build_home(records, offset, sel, menu_idx, focus,
                           cmd_text, cmd_cursor, error, rows, cmd_budget)
    while len(body) > total and rows > 1:
        rows -= 1
        body = _build_home(records, offset, sel, menu_idx, focus,
                           cmd_text, cmd_cursor, error, rows, cmd_budget)
    _ROWS_CACHE["value"] = rows
    _frame(i18n.t("tui.home_title"), body)


# -------------------------- 按键读取于上下文内 --------------------------
_TERM = _Term()


# -------------------------- 表单状态 --------------------------
def _app_config():
    try:
        import AppConfig
        return AppConfig
    except Exception:
        return None


def _download_dir() -> str:
    cfg = _app_config()
    if cfg is None:
        return os.getcwd()
    try:
        return cfg.get_download_dir() or os.getcwd()
    except Exception:
        return os.getcwd()


def _defaults() -> dict:
    cfg = _app_config()
    try:
        d = cfg.download_defaults() if cfg else {}
    except Exception:
        d = {}
    return {
        "url": "",
        "output": _download_dir(),
        "filename": "",
        "jobs": str(d.get("jobs", 16)),
        "chunk_size": f"{d.get('chunk_size', 10):g}",
        "limit": "0",
    }


def _label(key: str) -> str:
    return i18n.t(f"tui.field.{key}")


def _validate(form) -> str:
    if not form["url"].strip():
        return i18n.t("tui.error_url")
    for key in ("jobs", "chunk_size", "limit"):
        try:
            val = float(form[key])
        except ValueError:
            return i18n.t("tui.error_number", field=_label(key))
        if key != "limit" and val < 1:
            return i18n.t("tui.error_positive", field=_label(key))
        if key == "limit" and val < 0:
            return i18n.t("tui.error_positive", field=_label(key))
    return ""


def _build_args(form) -> argparse.Namespace:
    cfg = _app_config()
    try:
        d = cfg.download_defaults() if cfg else {}
    except Exception:
        d = {}
    return argparse.Namespace(
        url=form["url"].strip(),
        output=form["output"].strip() or _download_dir(),
        filename=form["filename"].strip(),
        jobs=max(1, min(int(form["jobs"]), 128)),
        chunk_size=float(form["chunk_size"]),
        cache=float(d.get("cache", 32.0)),
        limit=float(form["limit"]),
        timeout=float(d.get("timeout", 60.0)),
        header=[f"{k}: {v}" for k, v in _headers_for_download().items()],
        header_json="",
        no_ssl_check=bool(d.get("no_ssl_check", False)),
        backend="auto",
        run="",
        speed_unit=d.get("speed_unit", "MB/s"),
        json=False,
    )


def _draw_form(form, cursor, focus, error):
    width = _width()
    body = [""]
    for idx, key in enumerate(FIELDS):
        mark = paint(">", Ansi.GREEN) if idx == focus else " "
        value = form[key]
        if idx == focus:
            shown = value[:cursor] + paint("_", Ansi.WHITE) + value[cursor:]
        else:
            shown = value
        if not value:
            shown = shown or paint(i18n.t("tui.blank"), Ansi.GRAY)
        body.append(f"  {mark} {paint(_label(key) + ':', Ansi.CYAN)} {shown}")
    body.append("")
    if error:
        body.append("  " + paint(error, Ansi.RED))
    else:
        body.append("  " + paint(i18n.t("tui.hint_entry"), Ansi.DIM))
    body.append("  " + paint(i18n.t("tui.hint_keys"), Ansi.DIM))
    _frame(i18n.t("tui.title"), body)


def _idle(msg: str):
    sys.stdout.write("\033[H\033[2J" + paint("  " + msg, Ansi.DIM) + "\n")
    sys.stdout.flush()


# -------------------------- 完成后的后续操作 --------------------------
AFTER_ACTIONS = ("open_file", "open_dir", "cd", "back")


def _target_path(form) -> str:
    raw = form.get("output") or ""
    save_dir = os.path.abspath(os.path.expanduser(raw)) if raw else _download_dir()
    name = (form.get("filename") or "").strip()
    if name:
        return os.path.join(save_dir, name)
    url = (form.get("url") or "").strip()
    if url:
        return os.path.join(save_dir, download._resolve_filename(url, ""))
    return ""


def _open_path(path: str, folder: bool = False) -> None:
    import subprocess
    target = path if not folder else os.path.dirname(path)
    try:
        if os.name == "nt":
            os.startfile(target)
        else:
            subprocess.Popen(["xdg-open", target],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    except Exception:
        pass


def _after_select(form, rc: int) -> None:
    """下载完成后的操作菜单。"""
    file_path = _target_path(form)
    save_dir = os.path.dirname(file_path) if file_path else _download_dir()
    exists = bool(file_path) and os.path.exists(file_path)
    items = []
    if rc == 0 and exists:
        items.append("open_file")
    items.extend(("open_dir", "cd", "back"))
    idx = 0

    while True:
        body = ["", "  " + paint(i18n.t("tui.after_title"), Ansi.BOLD, Ansi.CYAN)]
        if file_path:
            body.append("  " + paint(i18n.t("tui.after_path"), Ansi.DIM)
                        + " " + paint(file_path, Ansi.WHITE))
        body.append("")
        for i, key in enumerate(items):
            active = i == idx
            arrow = paint(">", Ansi.GREEN) if active else " "
            text = i18n.t("tui.after_" + key)
            if active:
                text = paint("\033[7m " + text.ljust(30) + "\033[0m", Ansi.WHITE)
            else:
                text = paint("  " + text.ljust(30), Ansi.WHITE)
            body.append("  " + arrow + " " + text)
        body.append("")
        body.append("  " + paint(i18n.t("tui.after_hint"), Ansi.DIM))
        _frame(i18n.t("tui.after_header"), body)
        key = _TERM.read()
        if key in ("\x03", "\x04", "q", "\x1b"):
            return
        if key in ("\x1b[A", "k"):
            idx = (idx - 1) % len(items)
            continue
        if key in ("\x1b[B", "j"):
            idx = (idx + 1) % len(items)
            continue
        if key in ("\r", "\n"):
            action = items[idx]
            if action == "back":
                return
            if action == "open_file":
                _open_path(file_path)
            elif action == "open_dir":
                _open_path(file_path, folder=True)
            elif action == "cd":
                target = save_dir if os.path.isdir(save_dir) else ""
                if target:
                    _TERM.leave()
                    sys.stdout.write("\033[H\033[2J")
                    print(paint("$ cd " + target, Ansi.BOLD, Ansi.GREEN))
                    print("  " + paint(i18n.t("tui.after_cd_done",
                                              path=os.getcwd()), Ansi.DIM))
                    print("  " + paint(i18n.t("tui.after_cd_note"), Ansi.YELLOW))
                    print()
                    print("  " + paint(i18n.t("tui.back_hint"), Ansi.DIM))
                    sys.stdout.flush()
                    _TERM.read()
            continue


def _show_result(rc: int):
    if rc == 0:
        text = paint(i18n.t("tui.result_ok"), Ansi.GREEN)
    elif rc == 130:
        text = paint(i18n.t("done.aborted"), Ansi.YELLOW)
    elif rc == 4:
        text = paint(i18n.t("tui.result_disk_space"), Ansi.RED)
    else:
        text = paint(i18n.t("tui.result_fail", code=rc), Ansi.RED)
    print()
    print("  " + text)
    sys.stdout.flush()


# -------------------------- 下载 --------------------------
def _run_download(form, resume_path: str = "") -> int:
    _TERM.leave()
    _idle(i18n.t("tui.starting"))
    try:
        rc = download.run_download(_build_args(form), resume_path=resume_path)
    except KeyboardInterrupt:
        rc = 130
    _TERM.enter()
    _show_result(rc)
    _after_select(form, rc)
    return rc


def _edit_form(form, focus, cursor, error):
    while True:
        _draw_form(form, cursor, focus, error)
        key = _TERM.read()
        name = FIELDS[focus]
        if key in ("\x03", "\x04", "\x1b"):
            return None
        if key in ("\r", "\n"):
            return "submit"
        if key in ("\t", "\x1b[B"):
            focus = (focus + 1) % len(FIELDS)
            cursor = len(form[FIELDS[focus]])
            error = ""
        elif key == "\x1b[A":
            focus = (focus - 1) % len(FIELDS)
            cursor = len(form[FIELDS[focus]])
            error = ""
        elif key in ("\x1b[D", "\x02"):
            cursor = max(0, cursor - 1)
        elif key in ("\x1b[C", "\x06"):
            cursor = min(len(form[name]), cursor + 1)
        elif key in ("\x7f", "\x08"):
            if cursor > 0:
                form[name] = form[name][:cursor - 1] + form[name][cursor:]
                cursor -= 1
            error = ""
        elif key == "\x1b[3~":
            form[name] = form[name][:cursor] + form[name][cursor + 1:]
            error = ""
        elif key.isprintable() and not key.startswith("\x1b"):
            form[name] = form[name][:cursor] + key + form[name][cursor:]
            cursor += 1
            error = ""


def _new_download():
    form = _defaults()
    focus = 0
    cursor = 0
    error = ""
    while True:
        action = _edit_form(form, focus, cursor, error)
        if action is None:
            return
        err = _validate(form)
        if err:
            error = err
            continue
        error = ""
        _run_download(form)
        return


# -------------------------- 设置页 --------------------------
SETTING_FIELDS = (
    "download_dir", "dl_threads", "dl_chunk_mb", "dl_cache_mb",
    "dl_timeout", "dl_read_stall", "dl_max_retry", "dl_speed_unit",
    "dl_disable_ssl", "custom_headers",
)
NUMERIC_FIELDS = {"dl_threads", "dl_chunk_mb", "dl_cache_mb",
                  "dl_timeout", "dl_read_stall", "dl_max_retry"}


def _setting_label(key: str) -> str:
    return i18n.t(f"tui.setting_{key}")


def _settings_state() -> dict:
    cfg = _app_config()
    data = cfg.load() if cfg else {}
    state = {"download_dir": _download_dir(), "dl_speed_unit": cfg.speed_unit()
             if cfg else "MB/s"}
    for key in NUMERIC_FIELDS:
        state[key] = str(data.get(key, ""))
    state["dl_disable_ssl"] = bool(data.get("dl_disable_ssl", False))
    state["custom_headers"] = len(_load_headers())
    return state


def _setting_display(state, key) -> str:
    if key == "dl_disable_ssl":
        return i18n.t("tui.setting_on") if state[key] else i18n.t("tui.setting_off")
    if key == "custom_headers":
        return i18n.t("tui.setting_headers_count", n=state[key])
    return state[key]


def _draw_settings(state, focus, cursor, error, saved):
    body = [""]
    for idx, key in enumerate(SETTING_FIELDS):
        mark = paint(">", Ansi.GREEN) if idx == focus else " "
        value = _setting_display(state, key)
        col = Ansi.GRAY if key == "dl_disable_ssl" else Ansi.WHITE
        if idx == focus and key != "dl_disable_ssl":
            shown = (paint(value[:cursor], col) + paint("_", Ansi.WHITE)
                     + paint(value[cursor:], col))
        else:
            shown = paint(value, col)
        if not value:
            shown = paint(i18n.t("tui.blank"), Ansi.GRAY)
        body.append(f"  {mark} {paint(_setting_label(key) + ':', Ansi.CYAN)} {shown}")
    body.append("")
    if error:
        body.append("  " + paint(error, Ansi.RED))
    elif saved:
        body.append("  " + paint(i18n.t("tui.setting_saved"), Ansi.GREEN))
    else:
        body.append("  " + paint(i18n.t("tui.setting_hint"), Ansi.DIM))
    body.append("  " + paint(i18n.t("tui.setting_keys"), Ansi.DIM))
    _frame(i18n.t("tui.setting_title"), body)


def _load_headers() -> list:
    """首选项中的自定义请求头，返回 [[name, value], ...]。"""
    cfg = _app_config()
    if cfg is None:
        return []
    try:
        data = cfg.load().get("dl_headers", [])
    except Exception:
        return []
    result = []
    if isinstance(data, dict):
        for name, value in data.items():
            result.append([str(name), str(value)])
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                result.append([str(item[0]), str(item[1])])
    return result


def _save_headers(headers) -> bool:
    cfg = _app_config()
    if cfg is None:
        return False
    return cfg.save({"dl_headers": [list(h) for h in headers]})


def _headers_for_download() -> dict:
    return {name: value for name, value in _load_headers() if name.strip()}


def _draw_headers(headers, focus, editing, cursor, error, saved):
    body = ["", "  " + paint(i18n.t("tui.headers_title"), Ansi.BOLD, Ansi.WHITE)]
    if not headers:
        body.append("  " + paint(i18n.t("tui.headers_empty"), Ansi.DIM))
    for idx, (name, value) in enumerate(headers):
        mark = paint(">", Ansi.GREEN) if idx == focus else " "
        name_col = Ansi.CYAN
        val_col = Ansi.WHITE
        if idx == focus and editing == "name":
            shown_name = (paint(name[:cursor], name_col) + paint("_", Ansi.WHITE)
                          + paint(name[cursor:], name_col))
        else:
            shown_name = paint(name or i18n.t("tui.blank"), name_col)
        if idx == focus and editing == "value":
            shown_val = (paint(value[:cursor], val_col) + paint("_", Ansi.WHITE)
                         + paint(value[cursor:], val_col))
        else:
            shown_val = paint(value or i18n.t("tui.blank"), val_col)
        body.append(f"  {mark} {shown_name}: {shown_val}")
    body.append("")
    if error:
        body.append("  " + paint(error, Ansi.RED))
    elif saved:
        body.append("  " + paint(i18n.t("tui.setting_saved"), Ansi.GREEN))
    else:
        body.append("  " + paint(i18n.t("tui.headers_hint"), Ansi.DIM))
    body.append("  " + paint(i18n.t("tui.headers_keys"), Ansi.DIM))
    _frame(i18n.t("tui.headers_header"), body)


def _edit_headers():
    headers = _load_headers()
    focus = 0
    editing = ""
    cursor = 0
    error = ""
    saved = False
    while True:
        _draw_headers(headers, focus, editing, cursor, error, saved)
        key = _TERM.read()
        saved = False
        if key in ("\x03", "\x04"):
            if editing:
                editing, error = "", ""
                continue
            return
        if key == "\x1b":
            if editing:
                editing = ""
                continue
            return
        if not headers:
            if key in ("a", "A", "\r", "\n"):
                headers.append(["", ""])
                focus, editing, cursor = 0, "name", 0
                error = ""
            continue
        if editing:
            name, value = headers[focus]
            if key in ("\t", "\r", "\n"):
                if editing == "name":
                    editing, cursor = "value", len(value)
                else:
                    editing = ""
                    if not name.strip():
                        headers.pop(focus)
                        focus = max(0, focus - 1)
                        error = i18n.t("tui.headers_err_name")
                continue
            if key in ("\x1b[D",):
                cursor = max(0, cursor - 1)
                continue
            if key in ("\x1b[C",):
                cursor = min(len(name if editing == "name" else value), cursor + 1)
                continue
            if key in ("\x7f", "\x08"):
                if editing == "name":
                    if cursor > 0:
                        headers[focus][0] = name[:cursor - 1] + name[cursor:]
                        cursor -= 1
                else:
                    if cursor > 0:
                        headers[focus][1] = value[:cursor - 1] + value[cursor:]
                        cursor -= 1
                continue
            if key.isprintable() and not key.startswith("\x1b"):
                if editing == "name":
                    headers[focus][0] = name[:cursor] + key + name[cursor:]
                else:
                    headers[focus][1] = value[:cursor] + key + value[cursor:]
                cursor += 1
                error = ""
            continue
        if key in ("\x1b[A", "k"):
            focus = (focus - 1) % len(headers)
        elif key in ("\x1b[B", "j"):
            focus = (focus + 1) % len(headers)
        elif key in ("\r", "\n", "e", "E"):
            editing = "name"
            cursor = len(headers[focus][0])
        elif key in ("a", "A"):
            headers.append(["", ""])
            focus = len(headers) - 1
            editing, cursor = "name", 0
        elif key in ("d", "D"):
            headers.pop(focus)
            focus = max(0, min(focus, len(headers) - 1))
        elif key in ("s", "S"):
            saved = _save_headers(headers)
            if not saved:
                error = i18n.t("tui.setting_save_failed")


def _validate_settings(state) -> str:
    if not state["download_dir"].strip():
        return i18n.t("tui.error_dir")
    path = os.path.expanduser(state["download_dir"].strip())
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        return i18n.t("tui.error_dir_create", path=path)
    for key in NUMERIC_FIELDS:
        try:
            val = int(state[key])
        except Exception:
            return i18n.t("tui.error_number", field=_setting_label(key))
        if val < 1:
            return i18n.t("tui.error_positive", field=_setting_label(key))
    return ""


def _save_settings(state) -> bool:
    cfg = _app_config()
    if cfg is None:
        return False
    ok = cfg.set_download_dir(os.path.expanduser(state["download_dir"].strip()))
    data = {key: int(state[key]) for key in NUMERIC_FIELDS}
    data["dl_disable_ssl"] = bool(state["dl_disable_ssl"])
    data["dl_speed_unit"] = state["dl_speed_unit"]
    return cfg.save(data) and ok


def _edit_settings():
    state = _settings_state()
    focus = 0
    cursor = len(str(state[SETTING_FIELDS[0]]))
    error = ""
    saved = False
    while True:
        _draw_settings(state, focus, cursor, error, saved)
        key = _TERM.read()
        name = SETTING_FIELDS[focus]
        saved = False
        if key in ("\x03", "\x04", "\x1b"):
            return
        if name == "custom_headers" and key in ("\r", "\n", "e", "E", " "):
            _edit_headers()
            state["custom_headers"] = len(_load_headers())
            error = ""
            continue
        if key in ("\r", "\n"):
            err = _validate_settings(state)
            if err:
                error = err
                continue
            error = ""
            saved = _save_settings(state)
            if not saved:
                error = i18n.t("tui.setting_save_failed")
            continue
        if key in ("\t", "\x1b[B"):
            focus = (focus + 1) % len(SETTING_FIELDS)
            cursor = len(str(_setting_display(state, SETTING_FIELDS[focus])))
            error = ""
        elif key == "\x1b[A":
            focus = (focus - 1) % len(SETTING_FIELDS)
            cursor = len(str(_setting_display(state, SETTING_FIELDS[focus])))
            error = ""
        elif name == "custom_headers":
            continue
        elif name == "dl_disable_ssl" and key in (" ", "\r"):
            state[name] = not state[name]
        elif name == "dl_speed_unit" and key in ("\x1b[C", "\x1b[D", " ",
                                                 "\x06", "\x02"):
            cfg = _app_config()
            units = cfg.SPEED_UNITS if cfg else ("MB/s", "MiB/s", "Mbps")
            idx = units.index(state[name]) if state[name] in units else 0
            state[name] = units[(idx + 1) % len(units)]
            cursor = len(state[name])
        elif name in ("dl_disable_ssl", "dl_speed_unit"):
            continue
        elif key in ("\x1b[D", "\x02"):
            cursor = max(0, cursor - 1)
        elif key in ("\x1b[C", "\x06"):
            cursor = min(len(state[name]), cursor + 1)
        elif key in ("\x7f", "\x08"):
            if cursor > 0:
                state[name] = state[name][:cursor - 1] + state[name][cursor:]
                cursor -= 1
            error = ""
        elif key == "\x1b[3~":
            state[name] = state[name][:cursor] + state[name][cursor + 1:]
            error = ""
        elif key.isprintable() and not key.startswith("\x1b"):
            state[name] = state[name][:cursor] + key + state[name][cursor:]
            cursor += 1
            error = ""


# -------------------------- 主页事件循环 --------------------------
def _run_action(action, rec):
    """执行菜单/列表动作，返回 True 表示需要刷新记录。"""
    if action == "new":
        _new_download()
        return True
    if action == "settings":
        _edit_settings()
        return True
    if action == "detail" and rec:
        _show_detail(rec)
        return False
    if action == "resume" and rec:
        if _can_resume(rec):
            _resume_record(rec)
        return True
    return False


def _loop_home(records, state):
    """主页主循环，返回 'quit' 时退出。"""
    offset = state["offset"]
    sel = state["sel"]
    menu_idx = state["menu"]
    focus = state["focus"]
    cmd_text = state["cmd"]
    cmd_cursor = state["cursor"]
    error = ""
    recon = True

    while True:
        if recon:
            records = _load_records()
            start, shown = _visible_records(records, offset, _list_rows_now())
            if shown:
                if focus == FOCUS_LIST:
                    sel = min(sel, len(shown) - 1)
                else:
                    sel = 0
            recon = False
        _home(records, offset, sel, menu_idx, focus, cmd_text, cmd_cursor, error)
        key = _TERM.read()
        if key in ("\x03", "\x04"):
            if focus == FOCUS_CMD and cmd_text:
                cmd_text, cmd_cursor, error = "", 0, ""
                continue
            return "quit"
        if key == "\t":
            if focus == FOCUS_CMD:
                cands = _completions(cmd_text)
                if cands:
                    cmd_text = _apply_completion(cmd_text, cands)
                    cmd_cursor = len(cmd_text)
                    error = ""
                    continue
            order = (FOCUS_MENU, FOCUS_LIST, FOCUS_CMD)
            focus = order[(order.index(focus) + 1) % len(order)]
            error = ""
            continue
        if key == "\x1b[Z":
            order = (FOCUS_MENU, FOCUS_LIST, FOCUS_CMD)
            focus = order[(order.index(focus) - 1) % len(order)]
            continue

        if focus == FOCUS_CMD:
            if key in ("\r", "\n"):
                command = cmd_text.strip()
                if not command:
                    cmd_text, cmd_cursor, error = "", 0, ""
                    focus = FOCUS_MENU
                    continue
                cands = _completions(command)
                if cands and " " not in command.lstrip() and not command.lstrip().startswith("-"):
                    command = cands[0]
                arg_err = _command_arg_error(command)
                if arg_err:
                    error = arg_err
                    continue
                cmd_text, cmd_cursor, error = "", 0, ""
                _execute_command(command)
                recon = True
                continue
            if key == "\x1b[A":
                focus = FOCUS_LIST
                continue
            if key == "\x1b[D":
                cmd_cursor = max(0, cmd_cursor - 1)
                continue
            if key == "\x1b[C":
                cmd_cursor = min(len(cmd_text), cmd_cursor + 1)
                continue
            if key in ("\x7f", "\x08"):
                if cmd_cursor > 0:
                    cmd_text = cmd_text[:cmd_cursor - 1] + cmd_text[cmd_cursor:]
                    cmd_cursor -= 1
                error = ""
                continue
            if key == "\x1b[3~":
                cmd_text = cmd_text[:cmd_cursor] + cmd_text[cmd_cursor + 1:]
                continue
            if key == "\x01":
                cmd_cursor = 0
                continue
            if key == "\x05":
                cmd_cursor = len(cmd_text)
                continue
            if key in ("\x1b[H",):
                cmd_cursor = 0
                continue
            if key in ("\x1b[F",):
                cmd_cursor = len(cmd_text)
                continue
            if key.isprintable() and not key.startswith("\x1b"):
                cmd_text = cmd_text[:cmd_cursor] + key + cmd_text[cmd_cursor:]
                cmd_cursor += 1
                error = ""
                continue
            continue

        if key in ("q", "Q") and focus != FOCUS_CMD:
            return "quit"
        if key in ("\r", "\n"):
            if focus == FOCUS_MENU:
                action = MENU_ITEMS[menu_idx]
                if action == "quit":
                    return "quit"
                if _run_action(action, None):
                    recon = True
                continue
            rec = _current_record(records, offset, sel)
            if rec is None:
                continue
            if _run_action("detail", rec):
                recon = True
            continue

        if key in ("\x1b[A", "k"):
            if focus == FOCUS_LIST:
                if sel > 0:
                    sel -= 1
                else:
                    offset = min(max(0, len(records) - 1), offset + 1)
                    sel = 0
            else:
                menu_idx = (menu_idx - 1) % len(MENU_ITEMS)
        elif key in ("\x1b[B", "j"):
            if focus == FOCUS_LIST:
                _, shown = _visible_records(records, offset)
                if sel < len(shown) - 1:
                    sel += 1
                else:
                    offset = max(0, offset - 1)
                    sel = max(0, len(shown) - 1)
            else:
                menu_idx = (menu_idx + 1) % len(MENU_ITEMS)
        elif key == "\x1b[D":
            focus = FOCUS_MENU
        elif key == "\x1b[C":
            focus = FOCUS_LIST if records else FOCUS_CMD
        elif key == "/":
            focus = FOCUS_CMD
        elif key == "\x0e":
            rec = _current_record(records, offset, sel)
            if rec:
                _show_detail(rec)
        elif key in ("r", "R", "\x12"):
            rec = _current_record(records, offset, sel)
            if rec:
                if _can_resume(rec):
                    _resume_record(rec)
                    recon = True
                else:
                    error = i18n.t("tui.no_progress")
            else:
                recon = True
        elif key in ("d", "D"):
            rec = _current_record(records, offset, sel)
            if rec and _delete_record(rec):
                offset, sel = 0, 0
                recon = True


# -------------------------- 主循环 --------------------------
def run_tui() -> int:
    if os.name == "nt":
        print(paint(i18n.t("tui.unsupported_windows"), Ansi.RED))
        return 2
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(paint(i18n.t("tui.not_tty"), Ansi.RED))
        return 2
    sys.stdout.write("\033[?25h")
    state = {"offset": 0, "sel": 0, "menu": 0,
             "focus": FOCUS_MENU, "cmd": "", "cursor": 0}
    _TERM.enter()
    try:
        _loop_home([], state)
    finally:
        _TERM.leave()
        sys.stdout.write("\033[H\033[2J")
        sys.stdout.flush()
    return 0
