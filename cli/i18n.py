# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import sys
import configparser


def _resolve_lang_dir() -> str:
    """定位 lang 目录，源码运行与 Nuitka/PyInstaller 打包后均可找到。"""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [os.path.join(here, "lang")]
    base = getattr(sys, "_MEIPASS", "") or os.path.dirname(
        os.path.abspath(sys.argv[0] or sys.executable))
    candidates.extend((
        os.path.join(base, "cli", "lang"),
        os.path.join(base, "lang"),
        os.path.join(os.path.dirname(here), "lang"),
    ))
    for path in candidates:
        if os.path.isdir(path):
            return path
    return candidates[0]


_LANG_DIR = _resolve_lang_dir()
_FORCED_LANG = ""
_TABLE = {}
_CURRENT = "en"

# 常见中文写法的别名，统一指向 ch_zn.lang
_LANG_ALIASES = {
    "zh": "ch_zn", "zh_cn": "ch_zn", "zh-cn": "ch_zn",
    "ch_zh": "ch_zn", "cn": "ch_zn", "chinese": "ch_zn",
    "en_us": "en", "en-us": "en", "english": "en",
}


def _normalize(code: str) -> str:
    key = (code or "").strip().lower()
    return _LANG_ALIASES.get(key, code)


def _terminal_supports_unicode() -> bool:
    enc = (getattr(sys.stdout, "encoding", "") or "").lower()
    if "utf" in enc:
        return True
    for key in ("LC_ALL", "LC_CTYPE", "LANG"):
        if os.environ.get(key, "").upper().find("UTF-8") >= 0:
            return True
    return False


def _pick_locale_code() -> str:
    loc = (os.environ.get("LC_ALL") or os.environ.get("LC_CTYPE")
           or os.environ.get("LANG") or "").lower()
    if loc.startswith("zh"):
        return "ch_zn"
    return "en"


def available_langs():
    result = []
    try:
        for name in sorted(os.listdir(_LANG_DIR)):
            if name.endswith(".lang"):
                result.append(name[: -len(".lang")])
    except Exception:
        pass
    return result


def resolve_lang(forced: str = "") -> str:
    if forced:
        return _normalize(forced)
    env = os.environ.get("NODANIUM_LANG", "").strip()
    if env:
        return _normalize(env)
    if not _terminal_supports_unicode():
        return "en"
    return _pick_locale_code()


def load(lang: str = "") -> str:
    global _TABLE, _CURRENT, _FORCED_LANG
    code = resolve_lang(lang)
    path = os.path.join(_LANG_DIR, f"{code}.lang")
    if not os.path.exists(path):
        code = "en"
        path = os.path.join(_LANG_DIR, "en.lang")
    table = {}
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(path, encoding="utf-8")
        for section in parser.sections():
            for key, value in parser.items(section):
                table[f"{section}.{key}"] = value
    except Exception:
        pass
    _TABLE = table
    _CURRENT = code
    _FORCED_LANG = lang
    return code


def current() -> str:
    return _CURRENT


def t(key: str, **kwargs) -> str:
    val = _TABLE.get(key)
    if val is None:
        return key
    if kwargs:
        try:
            return val.format(**kwargs)
        except Exception:
            return val
    return val
