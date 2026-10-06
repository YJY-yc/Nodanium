# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import shutil
import logging
import platform
import subprocess
import tempfile
import threading

SYS = platform.system()

_ICON_CACHE = {}

_COLOR_MAP = {
    '.txt': (100, 149, 237), '.pdf': (220, 53, 69),
    '.doc': (0, 112, 192), '.docx': (0, 112, 192),
    '.xls': (34, 197, 94), '.xlsx': (34, 197, 94),
    '.ppt': (251, 146, 60), '.pptx': (251, 146, 60),
    '.html': (251, 191, 36), '.zip': (168, 85, 247),
    '.rar': (168, 85, 247), '.7z': (168, 85, 247),
    '.jpg': (6, 182, 212), '.jpeg': (6, 182, 212),
    '.png': (6, 182, 212), '.gif': (6, 182, 212),
    '.mp3': (236, 72, 153), '.wav': (236, 72, 153),
    '.mp4': (139, 92, 246), '.avi': (139, 92, 246),
    '.exe': (220, 53, 69),
}


def _draw_png(file_path, size):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    ext = os.path.splitext(file_path or "")[1].lower()
    color = _COLOR_MAP.get(ext, (160, 160, 160))
    if file_path and os.path.isdir(file_path):
        color = (251, 191, 36)
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, size - 3, size - 3], radius=4,
                        fill=(240, 240, 240, 255), outline=(180, 180, 180, 255))
    d.rectangle([2, 2, size // 3 + 2, 8], fill=color + (255,))
    for i in range(3):
        y = size // 2 - 4 + i * 6
        d.line([size // 5, y, size - size // 5, y], fill=(200, 200, 200, 255), width=2)
    return img


def icon_path_for_file(file_path, size=48):
    if not file_path:
        return None
    key = (os.path.abspath(file_path), size)
    if key in _ICON_CACHE and os.path.exists(_ICON_CACHE[key] or ""):
        return _ICON_CACHE[key]
    path = None
    try:
        tmp = os.path.join(tempfile.gettempdir(), "Nodanium", "icons")
        os.makedirs(tmp, exist_ok=True)
        path = os.path.join(tmp, f"icon_{abs(hash(key)) & 0xffffffff:x}.png")
        img = None
        ext = os.path.splitext(file_path)[1].lower()
        if os.path.isfile(file_path) and ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.ico', '.tif', '.tiff'):
            try:
                from PIL import Image
                with Image.open(file_path) as src:
                    src.load()
                    img = src.convert("RGBA").resize((size, size))
            except Exception:
                img = None
        if img is None:
            img = _draw_png(file_path, size)
        if img is not None:
            img.save(path, format="PNG")
        else:
            path = None
    except Exception as e:
        logging.debug(f"生成通知图标失败: {e}")
        path = None
    _ICON_CACHE[key] = path
    return path


class Notification:
    def __init__(self, app_id="Nodanium", title="", msg="", duration="short",
                 icon=None, file_path=None, on_click=None):
        self.app_id = app_id
        self.title = title
        self.msg = msg
        self.duration = duration
        self.on_click = on_click
        self.file_path = file_path or (icon if isinstance(icon, str) else None)
        self.icon = self.file_path or icon

    def set_audio(self, sound=None, loop=False):
        self._audio = sound
        return self

    def _icon_png(self):
        if self.icon and os.path.isfile(self.icon) and self.icon.lower().endswith(".png"):
            return self.icon
        return icon_path_for_file(self.file_path or self.icon)

    def show(self):
        try:
            if SYS == "Windows":
                self._show_windows()
            else:
                self._show_linux()
        except Exception as e:
            logging.warning(f"发送通知失败: {e}")

    def show_async(self):
        if SYS == "Linux":
            threading.Thread(target=self.show, daemon=True).start()
        else:
            self.show()

    def _show_windows(self):
        try:
            from winotify import Notification as _Toast
        except ImportError:
            self._show_fallback()
            return
        kwargs = dict(app_id=self.app_id, title=self.title, msg=self.msg,
                      duration=self.duration, icon=self._icon_png() or "")
        if self.on_click:
            kwargs["on_click"] = self.on_click
        toast = _Toast(**kwargs)
        if getattr(self, "_audio", None) is not None:
            try:
                from winotify import audio as _wa
                toast.set_audio(_wa.Default, loop=False)
            except Exception:
                pass
        toast.show()

    def _show_linux(self):
        notify_send = shutil.which("notify-send")
        if notify_send:
            try:
                self._notify_send(notify_send)
                return
            except Exception:
                pass
        gdbus = shutil.which("gdbus")
        if gdbus:
            try:
                self._gdbus_notify(gdbus)
                return
            except Exception:
                pass
        self._show_fallback()

    def _notify_send(self, notify_send):
        args = [notify_send, "-a", self.app_id, "-t",
                "5000" if self.duration == "long" else "3000"]
        icon = self._icon_png()
        if icon:
            args += ["-i", icon]
        if self.on_click:
            args += ["--wait", "--action=default=打开"]
        args += [self.title, self.msg]
        if self.on_click:
            try:
                out = subprocess.run(args, capture_output=True, text=True, timeout=3600)
                if out.stdout.strip() == "default":
                    self._fire()
            except Exception:
                subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _gdbus_notify(self, gdbus):
        icon = self._icon_png() or ""
        actions = "['default', '打开']" if self.on_click else "[]"
        args = [
            gdbus, "call", "--session",
            "--dest", "org.freedesktop.Notifications",
            "--object-path", "/org/freedesktop/Notifications",
            "--method", "org.freedesktop.Notifications.Notify",
            self.app_id, "0", icon,
            self.title, self.msg,
            actions, "{}",
            "5000" if self.duration == "long" else "3000",
        ]
        if self.on_click:
            threading.Thread(target=self._gdbus_watch, args=(gdbus,), daemon=True).start()
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _gdbus_watch(self, gdbus):
        try:
            proc = subprocess.Popen(
                [gdbus, "monitor", "--session",
                 "--dest", "org.freedesktop.Notifications"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            for line in proc.stdout:
                if "ActionInvoked" in line and "'default'" in line:
                    proc.terminate()
                    self._fire()
                    return
        except Exception:
            pass

    def _fire(self):
        try:
            self.on_click()
        except Exception as e:
            logging.warning(f"通知点击回调失败: {e}")

    def _show_fallback(self):
        if SYS == "Windows":
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "New-BurntToastNotification -Text @('{}','{}')".format(
                         self.title.replace("'", "''"), self.msg.replace("'", "''"))],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                pass
        print(f"[通知] {self.title}: {self.msg}")


def show_notification(title, message, app_id="Nodanium", duration="short"):
    Notification(app_id=app_id, title=title, msg=message, duration=duration).show()
