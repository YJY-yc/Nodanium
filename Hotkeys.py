# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import ctypes
import logging
import platform
import threading

import wx

import AppConfig

ACTIONS = [
    ("hotkey_new_download", "新建下载", "Ctrl+Shift+N"),
    ("hotkey_clipboard_download", "从剪贴板新建下载", "Ctrl+Shift+V"),
    ("hotkey_toggle_window", "显示或隐藏主窗口", ""),
    ("hotkey_traffic_mini", "显示流量转盘小窗", ""),
]

ACTION_LABELS = {key: label for key, label, _ in ACTIONS}
DEFAULT_BINDINGS = {key: default for key, _, default in ACTIONS}

MODIFIER_ORDER = ("Ctrl", "Alt", "Shift", "Win")

_MOD_ALIASES = {
    "ctrl": "Ctrl", "control": "Ctrl",
    "alt": "Alt",
    "shift": "Shift",
    "win": "Win", "meta": "Win", "super": "Win", "cmd": "Win", "command": "Win",
}

_KEY_ALIASES = {
    "return": "Enter", "enter": "Enter",
    "esc": "Esc", "escape": "Esc",
    "space": "Space", "spacebar": "Space",
    "del": "Delete", "delete": "Delete",
    "ins": "Insert", "insert": "Insert",
    "pgup": "PageUp", "pageup": "PageUp",
    "pgdn": "PageDown", "pagedown": "PageDown",
    "home": "Home", "end": "End",
    "back": "Backspace", "backspace": "Backspace", "tab": "Tab",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
}


# -------------------------- 文本解析 --------------------------
def parse(text):
    if not text or not isinstance(text, str):
        return None
    mods = set()
    key = ""
    for part in text.split("+"):
        piece = part.strip()
        if not piece:
            continue
        low = piece.lower()
        if low in _MOD_ALIASES:
            mods.add(_MOD_ALIASES[low])
        else:
            key = _KEY_ALIASES.get(low, piece.upper() if len(piece) == 1 else piece[:1].upper() + piece[1:])
    if not key or not mods:
        return None
    return frozenset(mods), key


def format_binding(text):
    parsed = parse(text)
    if parsed is None:
        return ""
    mods, key = parsed
    ordered = [m for m in MODIFIER_ORDER if m in mods]
    return "+".join(ordered + [key])


def is_valid(text):
    return parse(text) is not None


# -------------------------- 按键事件转换 --------------------------
def _mod_flags(mods):
    flags = 0
    if not mods:
        return flags
    if mods & wx.MOD_CONTROL:
        flags |= _MODS["Ctrl"]
    if mods & wx.MOD_ALT:
        flags |= _MODS["Alt"]
    if mods & wx.MOD_SHIFT:
        flags |= _MODS["Shift"]
    cmd = getattr(wx, "MOD_WIN", getattr(wx, "MOD_CMD", wx.MOD_CONTROL))
    if mods & cmd:
        flags |= _MODS["Win"]
    return flags


def binding_from_event(event):
    code = event.GetKeyCode()
    name = code_named(code)
    if not name:
        return None
    flags = _mod_flags(event.GetModifiers())
    if not flags:
        return None
    return "+".join([m for m in MODIFIER_ORDER if flags & _MODS[m]] + [name])


def code_named(code):
    if 65 <= code <= 90 or 48 <= code <= 57:
        return chr(code)
    return _VK_NAMES.get(code, "")


def key_name(code):
    return code_named(code)


# -------------------------- 配置存取 --------------------------
def load_bindings():
    data = AppConfig.load()
    result = {}
    for key, _, default in ACTIONS:
        raw = data.get(key, default)
        result[key] = format_binding(raw) if raw else ""
    return result


def save_bindings(bindings):
    payload = {key: format_binding(bindings.get(key, "")) for key, _, _ in ACTIONS}
    return AppConfig.save(payload)


def find_conflicts(bindings):
    seen = {}
    conflicts = []
    for key, _, _ in ACTIONS:
        parsed = parse(bindings.get(key, ""))
        if parsed is None:
            continue
        if parsed in seen:
            conflicts.append((seen[parsed], key))
        else:
            seen[parsed] = key
    return conflicts


# -------------------------- 平台常量 --------------------------
_MODS = {"Alt": 0x0001, "Ctrl": 0x0002, "Shift": 0x0004, "Win": 0x0008}
_NO_REPEAT = 0x4000
_WINDOW_CLASS = "Message"
_HWND_MESSAGE = -3
_HOTKEY_MESSAGE = 0x0312
_WM_QUIT = 0x0012

_VK = {
    "Enter": 0x0D, "Esc": 0x1B, "Tab": 0x09, "Space": 0x20,
    "Backspace": 0x08, "Delete": 0x2E, "Insert": 0x2D,
    "Home": 0x24, "End": 0x23, "PageUp": 0x21, "PageDown": 0x22,
    "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28,
    "Plus": 0xBB, "Minus": 0xBD, "Comma": 0xBC, "Period": 0xBE,
    "Semicolon": 0xBA, "Slash": 0xBF, "Backslash": 0xDC,
    "LeftBracket": 0xDB, "RightBracket": 0xDD, "Quote": 0xDE, "Backtick": 0xC0,
}

_VK_NAMES = {
    0x09: "Tab", 0x20: "Space", 0x08: "Backspace", 0x0D: "Enter", 0x1B: "Esc",
    0x2D: "Insert", 0x2E: "Delete", 0x24: "Home", 0x23: "End",
    0x21: "PageUp", 0x22: "PageDown", 0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0xBB: "Plus", 0xBD: "Minus", 0xBC: "Comma", 0xBE: "Period", 0xBA: "Semicolon",
    0xBF: "Slash", 0xDC: "Backslash", 0xDB: "LeftBracket", 0xDD: "RightBracket",
    0xDE: "Quote", 0xC0: "Backtick",
}
for _index in range(1, 25):
    _VK_NAMES[0x6F + _index] = "F%d" % _index


def _vk_code(name):
    if name in _VK:
        return _VK[name]
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    if name.startswith("F") and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
        return 0x6F + int(name[1:])
    return 0


class GlobalHotkeys(object):
    def __init__(self):
        self._callbacks = {}
        self._generation = 0
        self._thread = None
        self._errors = []

    def set_callback(self, action, callback):
        self._callbacks[action] = callback

    def errors(self):
        return list(self._errors)

    def active(self):
        return self._thread is not None and self._thread.is_alive()

    def supported(self):
        return platform.system() == "Windows"

    def register(self, bindings):
        self.unregister()
        if not self.supported():
            return
        plan = {}
        for key, _, _ in ACTIONS:
            parsed = parse(bindings.get(key, ""))
            if parsed is not None:
                plan[key] = parsed
        if not plan:
            return
        self._start(self._windows_worker, plan)

    def unregister(self):
        self._generation += 1
        thread = self._thread
        self._thread = None
        self._errors = []
        if thread is not None and thread.is_alive() and self.supported():
            try:
                ctypes.windll.user32.PostThreadMessageW(thread.ident, _WM_QUIT, 0, 0)
            except Exception:
                pass

    def _start(self, worker, plan):
        generation = self._generation

        def fail(key):
            if generation == self._generation:
                self._errors.append(ACTION_LABELS[key])

        def run():
            try:
                worker(plan, generation, fail)
            except Exception as e:
                logging.error("全局快捷键线程异常: %s", e)

        self._thread = threading.Thread(target=run, name="NodaniumHotkeys", daemon=True)
        self._thread.start()

    def _fire(self, action):
        callback = self._callbacks.get(action)
        if callback is None:
            logging.warning("快捷键动作无回调: %s", action)
            return
        try:
            callback()
            logging.info("快捷键已执行: %s", ACTION_LABELS.get(action, action))
        except Exception as e:
            logging.error("快捷键动作执行失败: %s", e)

    # -------------------------- Windows --------------------------
    def _windows_worker(self, plan, generation, fail):
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]

        request = []
        for key, (mods, name) in plan.items():
            vk = _vk_code(name)
            if not vk:
                fail(key)
                continue
            flags = _NO_REPEAT
            for m in mods:
                flags |= _MODS[m]
            request.append((key, vk, flags))

        hwnd = user32.CreateWindowExW(0, _WINDOW_CLASS, None, 0, 0, 0, 0, 0,
                                      wintypes.HWND(_HWND_MESSAGE), None, None, None)
        if not hwnd:
            logging.error("快捷键窗口创建失败")
            for key, _, _ in request:
                fail(key)
            return
        table = {}
        for index, (key, vk, flags) in enumerate(request):
            if user32.RegisterHotKey(hwnd, 1000 + index, flags, vk):
                table[1000 + index] = key
                logging.info("快捷键注册成功: %s", ACTION_LABELS[key])
            else:
                logging.warning("快捷键注册失败: %s", ACTION_LABELS[key])
                fail(key)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == _HOTKEY_MESSAGE and msg.wParam in table and generation == self._generation:
                logging.info("收到快捷键消息: %s", ACTION_LABELS[table[msg.wParam]])
                wx.CallAfter(self._fire, table[msg.wParam])
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        for hot_id in table:
            user32.UnregisterHotKey(hwnd, hot_id)
        user32.DestroyWindow(hwnd)
