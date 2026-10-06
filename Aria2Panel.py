# Copyright (c) 2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import json
import time
import platform
import threading

import wx

try:
    import TorrentDownload as TD
except Exception:
    TD = None

SYS = platform.system()

_BLUE = wx.Colour(0, 120, 215)


def _data_dir():
    if SYS == "Windows":
        base = os.path.join(os.getenv('APPDATA', ''), "Nodanium")
    else:
        base = os.path.join(os.path.expanduser("~"), ".Nodanium")
    os.makedirs(base, exist_ok=True)
    return base


def _config_path():
    return os.path.join(_data_dir(), "config.json")


def load_config():
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(_config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False


def _fmt(n):
    try:
        n = float(n or 0)
    except Exception:
        return "0 B"
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return "%.1f %s" % (n, u)
        n /= 1024.0
    return "%.1f B" % n


def _status_cn(st):
    return {"active": "下载中", "waiting": "等待", "paused": "已暂停",
            "complete": "已完成", "error": "错误", "removed": "已移除"}.get(st, st or "未知")


def wrap_cjk(win, text, width):
    """按像素宽度手动换行(兼容无法断行的中文)：逐字测量并插入\n。"""
    if width <= 40:
        return text
    dc = wx.ClientDC(win)
    dc.SetFont(win.GetFont())
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""
            continue
        trial = cur + ch
        if dc.GetTextExtent(trial)[0] > width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    lines.append(cur)
    return "\n".join(lines)


def app_download_dir():
    """读取软件统一决定的默认下载目录(dir.txt)。"""
    try:
        with open(os.path.join(_data_dir(), "dir.txt"), "r") as f:
            d = f.read().strip()
        if d:
            return d
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Downloads")


FIXED_ARGS = [
    "--summary-interval=0",
    "--console-log-level=error",
    "--rpc-listen-all=false",
]

DEFAULT_OPTS = {
    "continue": "true",
    "seed_time": "0",
    "seed_ratio": "1.0",
    "bt_max_peers": "55",
    "enable_dht": "true",
    "listen_port": "6881-6999",
    "dht_listen_port": "6881-6999",
    "file_allocation": "prealloc",
}

OPT_FIELDS = [
    ("listen_port", "BT 监听端口", "str", "如 6881-6999"),
    ("dht_listen_port", "DHT 监听端口", "str", "如 6881-6999"),
    ("seed_time", "做种时间(分钟)", "int", "0=不做种"),
    ("seed_ratio", "做种分享率", "float", "0=不限制"),
    ("bt_max_peers", "BT 最大连接节点", "int", ""),
    ("file_allocation", "文件分配方式", "str", "prealloc / none / trunc"),
]


class Aria2Panel(object):
    """aria2 管理面板(挂载到传入的 wx.Panel)。"""

    def __init__(self, parent, frame=None):
        self.parent = parent
        self.frame = frame
        self.cfg = load_config()
        _allowed = set(DEFAULT_OPTS.keys())
        self.opts = dict(DEFAULT_OPTS)
        saved = self.cfg.get("aria2_options") or {}
        self.opts.update({k: str(v) for k, v in saved.items() if k in _allowed})
        self.download_dir = app_download_dir()
        self.rpc_port = int(self.cfg.get("aria2_rpc_port", 6800) or 6800)
        self.rpc_secret = self.cfg.get("aria2_rpc_secret", "") or ""
        self.entries = []
        self.timer = None
        self._refresh_busy = False
        self.engine_enabled = TD.aria2_enabled() if TD else False
        try:
            self._base_pt = parent.GetFont().GetPointSize()
        except Exception:
            self._base_pt = 10
        self._base_pt = max(9, min(self._base_pt, 12))
        self._build()

    def _build(self):
        p = self.parent
        self.root = wx.BoxSizer(wx.VERTICAL)
        self.book = wx.Simplebook(p)
        try:
            self.book.SetBackgroundColour(wx.Colour(255, 255, 255))
        except Exception:
            pass
        self.disabled_panel = self._build_disabled_view(self.book)
        self.starting_panel = self._build_starting_view(self.book)
        self.enabled_panel = wx.Panel(self.book)
        self.enabled_panel.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.book.AddPage(self.disabled_panel, "disabled")
        self.book.AddPage(self.starting_panel, "starting")
        self.book.AddPage(self.enabled_panel, "enabled")
        self.root.Add(self.book, 1, wx.EXPAND)
        p.SetSizer(self.root)
        self._starting = False
        need_start = bool(self.engine_enabled)
        try:
            self.book.SetSelection(1 if self.engine_enabled else 0)
            if self.engine_enabled:
                self._set_start_text("正在加载 BT 下载面板...", "请稍候…")
            self.book.Layout()
        except Exception:
            pass
        self._need_start = need_start
        try:
            p.Bind(wx.EVT_SIZE, self._on_parent_size)
            p.Bind(wx.EVT_SHOW, self._on_parent_show)
        except Exception:
            pass
        self._build_heavy()

    def _on_parent_size(self, evt):
        evt.Skip()
        self._layout_chain()

    def _on_parent_show(self, evt):
        evt.Skip()
        if evt.IsShown():
            wx.CallAfter(self._layout_chain)

    def _build_heavy(self):
        """构建较重的笔记本（在 frame.Show() 前同步完成）。"""
        try:
            self._build_enabled_ui(self.enabled_panel)
            try:
                self._gauge_timer.Stop()
            except Exception:
                pass
            if getattr(self, "_need_start", False):
                self._begin_starting()
        except Exception as e:
            import logging
            logging.error("BT 面板构建失败: %s" % e)
        self.finalize_layout()
        self._layout_chain()
        self._sync_mode()
        wx.CallAfter(self._layout_chain)
        self._ensure_rendered(0)

    def _ensure_rendered(self, tries=0):
        """确保内部笔记本已拿到真实尺寸；未就绪则下一帧重试（最多约 2s）。"""
        if tries > 40:
            return
        nb = getattr(self, "nb", None)
        if nb is None:
            return
        sz = nb.GetSize()
        if sz.width > 50 and sz.height > 50:
            return
        self._layout_chain()
        wx.CallLater(50, self._ensure_rendered, tries + 1)

    def _layout_chain(self):
        """按当前尺寸重新布局 父面板 → Simplebook → 启用页 → Notebook → 各选项卡页。

        带重入保护，避免 Layout() 触发 EVT_SIZE 导致无限递归。
        """
        if getattr(self, "_in_layout", False):
            return
        self._in_layout = True
        try:
            for w in (self.parent, self.book, self.enabled_panel):
                try:
                    w.Layout()
                except Exception:
                    pass
            nb = getattr(self, "nb", None)
            if nb is not None:
                nb.Layout()
                for i in range(nb.GetPageCount()):
                    try:
                        nb.GetPage(i).Layout()
                    except Exception:
                        pass
        finally:
            self._in_layout = False

    def _set_start_text(self, title, desc):
        try:
            self.start_title.SetLabel(title)
            self.start_desc.SetLabel(desc)
            self.starting_panel.Layout()
        except Exception:
            pass

    def _begin_starting(self):
        """后台等待常驻服务就绪，就绪后刷新任务列表（不遮挡已展示的笔记本）。"""
        self._starting = True
        self._start_ticks = 0
        if not getattr(self, "_start_poll", None):
            self._start_poll = wx.Timer(self.parent)
            self.parent.Bind(wx.EVT_TIMER, self._on_start_poll, self._start_poll)
        self._start_poll.Start(400)
        self._on_start_poll(None)

    def _stop_start_timers(self):
        self._starting = False
        for t in (getattr(self, "_start_poll", None), getattr(self, "_gauge_timer", None)):
            try:
                if t:
                    t.Stop()
            except Exception:
                pass

    def _on_start_poll(self, evt):
        """轮询常驻服务是否已就绪；就绪后刷新任务列表。"""
        if not self._starting:
            self._stop_start_timers()
            return
        self._start_ticks = getattr(self, "_start_ticks", 0) + 1
        svc = getattr(TD, "SERVICE", None) if TD else None
        ready = bool(svc and svc.is_running())
        if ready:
            self._stop_start_timers()
            self.engine_enabled = True
            self._sync_mode()
            self._layout_chain()
            self._apply_enabled_state()
            self.on_find()
            self.refresh_tasks()
            self._refresh_stats()
            return
        if not TD or not TD.aria2_enabled():
            self._stop_start_timers()
            return
        if self._start_ticks >= 62:
            self._stop_start_timers()

    def _build_starting_view(self, host):
        """启动态：显示“正在启动 aria2 服务...”，避免出现灰色空页。"""
        page = wx.Panel(host)
        page.SetBackgroundColour(wx.Colour(255, 255, 255))
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.AddStretchSpacer(1)

        self.start_title = wx.StaticText(page, label="正在启动 aria2 服务...")
        self._set_font(self.start_title, self._base_pt + 3, bold=True)
        self.start_title.SetForegroundColour(wx.Colour(60, 60, 60))
        outer.Add(self.start_title, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 8)

        self.start_desc = wx.StaticText(page, label="正在拉起 BT 下载 / 做种引擎，请稍候…")
        self._set_font(self.start_desc, self._base_pt - 1)
        self.start_desc.SetForegroundColour(wx.Colour(120, 120, 120))
        outer.Add(self.start_desc, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 6)

        self.start_gauge = wx.Gauge(page, range=100, size=(260, 16))
        if not getattr(self, "_gauge_timer", None):
            self._gauge_timer = wx.Timer(self.parent)
            self.parent.Bind(wx.EVT_TIMER, self._on_gauge_tick, self._gauge_timer)
        outer.Add(self.start_gauge, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 10)

        outer.AddStretchSpacer(1)
        page.SetSizer(outer)
        return page

    def _on_gauge_tick(self, evt):
        try:
            self.start_gauge.Pulse()
        except Exception:
            self._gauge_timer.Stop()

    def _build_enabled_ui(self, host):
        """启用态：标题 + 三个选项卡。"""
        root = wx.BoxSizer(wx.VERTICAL)
        title = wx.StaticText(host, label="BT 下载")
        self._set_font(title, self._base_pt + 2)
        root.Add(title, 0, wx.ALL, 10)
        self.nb = wx.Notebook(host)
        try:
            f = host.GetFont(); f.SetPointSize(self._base_pt); self.nb.SetFont(f)
        except Exception:
            pass
        root.Add(self.nb, 1, wx.EXPAND | wx.ALL, 5)
        host.SetSizer(root)
        self._build_service_tab()
        self._build_settings_tab()
        self._build_tasks_tab()
        wx.CallAfter(self.refresh_tasks)
        wx.CallAfter(self._refresh_stats)

    def _set_font(self, win, pt, bold=False):
        """按给定磅值设置字体(使用继承的字体族，避免与主窗字体冲突)。"""
        try:
            f = win.GetFont()
            f.SetPointSize(max(8, int(pt)))
            f.SetWeight(wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL)
            win.SetFont(f)
        except Exception:
            pass

    @staticmethod
    def _buffered_best(win, pad_w=6, pad_h=2):
        """控件推荐尺寸 + 余量，避免多行文本因取整被裁切。"""
        try:
            bs = win.GetBestSize()
            return (bs.width + pad_w, bs.height + pad_h)
        except Exception:
            return (-1, -1)

    def _fixup_desc_size(self):
        try:
            self.dis_desc.SetMinSize(self._buffered_best(self.dis_desc))
            self.dis_desc.GetParent().Layout()
        except Exception:
            pass

    def _build_disabled_view(self, host):
        """禁用态：居中显示醒目的蓝色“启用”按钮与说明。"""
        page = wx.Panel(host)
        page.SetBackgroundColour(wx.Colour(255, 255, 255))
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.AddStretchSpacer(1)

        self.dis_title = wx.StaticText(page, label="aria2 已禁用")
        self._set_font(self.dis_title, self._base_pt + 4, bold=True)
        self.dis_title.SetForegroundColour(wx.Colour(60, 60, 60))
        outer.Add(self.dis_title, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 8)

        self.dis_desc = wx.StaticText(
            page, label="aria2 提供 BT / 磁力链下载与统一任务管理，\n"
                        "启用后即可使用服务、设置与任务功能。")
        self._set_font(self.dis_desc, self._base_pt - 1)
        self.dis_desc.SetForegroundColour(wx.Colour(120, 120, 120))
        self.dis_desc.SetWindowStyle(wx.ALIGN_CENTER)
        desc_row = wx.BoxSizer(wx.HORIZONTAL)
        desc_row.AddStretchSpacer(1)
        desc_row.Add(self.dis_desc, 0, wx.ALIGN_CENTER_VERTICAL)
        desc_row.AddStretchSpacer(1)
        outer.Add(desc_row, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 6)
        self.dis_desc.SetMinSize(self._buffered_best(self.dis_desc))
        wx.CallAfter(self._fixup_desc_size)

        outer.AddSpacer(20)
        self.btn_enable = wx.Button(page, label="启 用  aria2", size=(220, 56))
        self._set_font(self.btn_enable, self._base_pt + 1, bold=True)
        try:
            self.btn_enable.SetBackgroundColour(_BLUE)
            self.btn_enable.SetForegroundColour(wx.Colour(255, 255, 255))
        except Exception:
            pass
        outer.Add(self.btn_enable, 0, wx.ALIGN_CENTER_HORIZONTAL)

        self.dis_hint = wx.StaticText(page, label="启用后可随时在“服务”页关闭")
        self._set_font(self.dis_hint, self._base_pt - 3)
        self.dis_hint.SetForegroundColour(wx.Colour(160, 160, 160))
        outer.Add(self.dis_hint, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 8)

        outer.AddStretchSpacer(1)
        page.SetSizer(outer)
        self.btn_enable.Bind(wx.EVT_BUTTON, self.on_enable_clicked)
        return page

    def on_enable_clicked(self, evt):
        if hasattr(self, "chk_enable"):
            self.chk_enable.SetValue(True)
        self._play_enable_animation(self._after_enable)

    def _after_enable(self):
        self._set_enabled(True, persist=True)

    def _play_enable_animation(self, on_done):
        if getattr(self, "_anim_timer", None) and self._anim_timer.IsRunning():
            self._anim_timer.Stop()
        self._anim_step = 0
        self._anim_len = 12
        self._anim_done_cb = on_done
        self.btn_enable.Disable()
        if not getattr(self, "_anim_timer", None):
            self._anim_timer = wx.Timer(self.parent)
            self.parent.Bind(wx.EVT_TIMER, self._on_anim_tick, self._anim_timer)
        self._anim_timer.Start(16)
        self._on_anim_tick(None)

    def _on_anim_tick(self, evt):
        self._anim_step += 1
        t = min(1.0, self._anim_step / float(self._anim_len))
        t = 1 - (1 - t) ** 3
        from_c = wx.Colour(210, 225, 240)
        try:
            c = wx.Colour(int(from_c.Red() + (_BLUE.Red() - from_c.Red()) * t),
                          int(from_c.Green() + (_BLUE.Green() - from_c.Green()) * t),
                          int(from_c.Blue() + (_BLUE.Blue() - from_c.Blue()) * t))
            self.btn_enable.SetBackgroundColour(c)
            self.btn_enable.SetForegroundColour(
                wx.Colour(*([255] * 3)) if t > 0.5 else wx.Colour(90, 90, 90))
            self.btn_enable.Refresh()
        except Exception:
            pass
        if self._anim_step >= self._anim_len:
            self._anim_timer.Stop()
            self.btn_enable.SetBackgroundColour(_BLUE)
            self.btn_enable.SetForegroundColour(wx.Colour(255, 255, 255))
            self.btn_enable.Enable()
            cb = getattr(self, "_anim_done_cb", None)
            if cb:
                cb()

    def _sync_mode(self):
        """根据启用状态切换 禁用占位页 / 完整笔记本。"""
        try:
            self.book.SetSelection(2 if self.engine_enabled else 0)
            self.book.Layout()
            self.parent.Layout()
        except Exception:
            pass
        self._layout_chain()

    def _set_enabled(self, flag, persist=True):
        self.engine_enabled = bool(flag)
        if hasattr(self, "chk_enable"):
            self.chk_enable.SetValue(self.engine_enabled)
        if TD and persist:
            TD.set_aria2_enabled(self.engine_enabled)
        if not self.engine_enabled and TD:
            self._stop_start_timers()
            try:
                TD.stop_service()
            except Exception:
                pass
            if hasattr(self, "list"):
                self.list.DeleteAllItems()
        self._sync_mode()
        self._apply_enabled_state()
        if self.engine_enabled:
            self.on_find()

    def finalize_layout(self):
        """字体继承稳定后：按当前字体设置标签/提示的最小尺寸，防止被压缩截断。"""
        try:
            for win, text in getattr(self, "_min_refs", []):
                dc = wx.ClientDC(win)
                dc.SetFont(win.GetFont())
                win.SetMinSize((dc.GetTextExtent(text)[0], -1))
            if getattr(self, "_tips", None):
                self._wrap_tips(self._tips[0].GetParent())
            self.nb.Layout()
            for i in range(self.nb.GetPageCount()):
                self.nb.GetPage(i).Layout()
        except Exception:
            pass

    @staticmethod
    def _scrolled(nb, title):
        """创建可滚动选项卡页，返回 (外层页, 内容面板, 内容竖直 sizer)。"""
        page = wx.Panel(nb)
        outer = wx.BoxSizer(wx.VERTICAL)
        content = wx.ScrolledWindow(page, style=wx.VSCROLL | wx.HSCROLL)
        content.SetScrollRate(10, 10)
        try:
            content.SetCanFocus(False)
        except Exception:
            pass
        s = wx.BoxSizer(wx.VERTICAL)
        content.SetSizer(s)
        outer.Add(content, 1, wx.EXPAND)
        page.SetSizer(outer)
        nb.AddPage(page, title)

        def _clamp_virtual(evt=None):
            try:
                best = content.GetBestVirtualSize()
                cw, ch = content.GetClientSize()
                content.SetVirtualSize((max(best.width, cw), max(best.height, ch)))
            except Exception:
                pass
            if evt is not None:
                evt.Skip()

        content.Bind(wx.EVT_SIZE, _clamp_virtual)

        def _late():
            try:
                content.FitInside()
                content.Layout()
                page.Layout()
                _clamp_virtual()
            except Exception:
                pass
        wx.CallAfter(_late)
        return page, content, s

    def _build_service_tab(self):
        _page, p, s = self._scrolled(self.nb, "服务")

        top = wx.StaticBoxSizer(wx.VERTICAL, p, "aria2 引擎")
        self.chk_enable = wx.CheckBox(p, label="启用 aria2 (BT 下载 / 管理服务)")
        self.chk_enable.SetValue(self.engine_enabled)
        top.Add(self.chk_enable, 0, wx.ALL, 6)
        self.svc_txt = wx.StaticText(p, label="服务状态: 未运行")
        top.Add(self.svc_txt, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        svc_tip = wx.StaticText(
            p, label="启用后随软件启动拉起；也可在此页手动启停。\n"
                      "服务未运行时不会做种。")
        svc_tip.SetForegroundColour(wx.Colour(130, 130, 130))
        top.Add(svc_tip, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        s.Add(top, 0, wx.EXPAND | wx.ALL, 8)

        stat_box = wx.StaticBoxSizer(wx.VERTICAL, p, "传输统计")
        self.stat_txt = wx.StaticText(p, label="累计上传: -   本次会话上传: -   上传速度: -   下载速度: -")
        stat_box.Add(self.stat_txt, 0, wx.ALL, 6)
        stat_hint = wx.StaticText(p, label="累计上传为软件跨重启记录的做种上传总量；数据来自 aria2 常驻服务。")
        stat_hint.SetForegroundColour(wx.Colour(130, 130, 130))
        stat_box.Add(stat_hint, 0, wx.LEFT | wx.RIGHT, 6)
        self.btn_reset_stat = wx.Button(p, label="清零累计上传")
        stat_box.Add(self.btn_reset_stat, 0, wx.ALL, 6)
        s.Add(stat_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        src_box = wx.StaticBoxSizer(wx.VERTICAL, p, "引擎来源 (优先级从高到低)")
        self.src_txt = wx.StaticText(p, label="检测中...")
        src_box.Add(self.src_txt, 0, wx.ALL, 6)
        s.Add(src_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        p.Bind(wx.EVT_SIZE, self._on_service_resize)
        self.chk_enable.Bind(wx.EVT_CHECKBOX, self.on_toggle_enable)

        g = wx.FlexGridSizer(2, 2, 8, 8)
        g.AddGrowableCol(1, 1)
        g.Add(wx.StaticText(p, label="RPC 端口:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.port_txt = wx.TextCtrl(p, value=str(self.rpc_port))
        g.Add(self.port_txt, 1, wx.EXPAND)
        g.Add(wx.StaticText(p, label="RPC 密钥:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.secret_txt = wx.TextCtrl(p, value=self.rpc_secret, style=wx.TE_PASSWORD)
        g.Add(self.secret_txt, 1, wx.EXPAND)
        s.Add(g, 0, wx.EXPAND | wx.ALL, 8)

        hs = wx.WrapSizer(wx.HORIZONTAL)
        self.btn_find = wx.Button(p, label="重新检测引擎")
        self.btn_start = wx.Button(p, label="启动服务")
        self.btn_stop = wx.Button(p, label="停止服务")
        self.btn_probe = wx.Button(p, label="测试 RPC")
        for b in (self.btn_find, self.btn_start, self.btn_stop, self.btn_probe):
            hs.Add(b, 0, wx.ALL, 4)
        s.Add(hs, 0, wx.EXPAND | wx.ALL, 4)

        self.log = wx.TextCtrl(p, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
                               size=(-1, 160))
        s.Add(self.log, 0, wx.EXPAND | wx.ALL, 8)

        self.btn_find.Bind(wx.EVT_BUTTON, lambda e: self.on_find())
        self.btn_start.Bind(wx.EVT_BUTTON, self.on_start)
        self.btn_stop.Bind(wx.EVT_BUTTON, self.on_stop)
        self.btn_probe.Bind(wx.EVT_BUTTON, self.on_probe)
        self.btn_reset_stat.Bind(wx.EVT_BUTTON, self.on_reset_stat)
        wx.CallAfter(self.on_find)
        wx.CallAfter(self._apply_enabled_state)

    def _log(self, msg):
        try:
            self.log.AppendText(time.strftime("[%H:%M:%S] ") + str(msg) + "\n")
        except Exception:
            pass

    def _on_service_resize(self, evt):
        evt.Skip()
        try:
            tc = evt.GetEventObject()
            w = max(300, tc.GetClientSize().width - 30)
            for t in (self.src_txt, self.svc_txt):
                src = getattr(t, "_orig_label", t.GetLabel())
                t.SetLabel(wrap_cjk(t, src, w))
                t.InvalidateBestSize()
                t.SetMinSize((-1, -1))
                t.SetMinSize((max(1, t.GetBestSize().width), t.GetBestSize().height))
            tc.Layout()
        except Exception:
            pass

    def _build_settings_tab(self):
        _page, p, s = self._scrolled(self.nb, "BT 下载设置")

        head = wx.StaticText(p, label="下载目录由软件统一决定: " + self.download_dir)
        head.SetForegroundColour(wx.Colour(90, 90, 90))
        head._orig_label = head.GetLabel()
        s.Add(head, 0, wx.EXPAND | wx.ALL, 10)

        box = wx.StaticBoxSizer(wx.VERTICAL, p, "BT 参数")
        grid = wx.FlexGridSizer(0, 3, 6, 10)
        grid.AddGrowableCol(2, 1)
        self.opt_ctrls = {}
        self._min_refs = []
        for key, label, kind, hint in OPT_FIELDS:
            lab = wx.StaticText(p, label=label)
            grid.Add(lab, 0, wx.ALIGN_CENTER_VERTICAL)
            self._min_refs.append((lab, label))
            val = str(self.opts.get(key, DEFAULT_OPTS.get(key, "")))
            ctrl = wx.TextCtrl(p, value=val, size=(120, -1))
            ctrl.SetMinSize((120, -1))
            ctrl.SetMaxSize((120, -1))
            grid.Add(ctrl, 0, wx.ALIGN_CENTER_VERTICAL)
            h = wx.StaticText(p, label=hint)
            h.SetForegroundColour(wx.Colour(130, 130, 130))
            grid.Add(h, 0, wx.ALIGN_CENTER_VERTICAL)
            if hint:
                self._min_refs.append((h, hint))
            self.opt_ctrls[key] = ctrl
        box.Add(grid, 0, wx.EXPAND | wx.ALL, 8)
        s.Add(box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        sw = wx.StaticBoxSizer(wx.VERTICAL, p, "其他")
        self.chk_dht = wx.CheckBox(p, label="启用 DHT / PEX (BT 无追踪器也能找节点)")
        self.chk_dht.SetValue(str(self.opts.get("enable_dht", "true")).lower() in ("true", "1", "yes"))
        sw.Add(self.chk_dht, 0, wx.ALL, 5)
        self.chk_continue = wx.CheckBox(p, label="断点续传 (continue)")
        self.chk_continue.SetValue(str(self.opts.get("continue", "true")).lower() in ("true", "1", "yes"))
        sw.Add(self.chk_continue, 0, wx.ALL, 5)
        s.Add(sw, 0, wx.EXPAND | wx.ALL, 10)

        hs = wx.WrapSizer(wx.HORIZONTAL)
        self.btn_save = wx.Button(p, label="保存设置")
        self.btn_apply = wx.Button(p, label="保存并应用")
        self.btn_reload = wx.Button(p, label="从服务读取")
        for b in (self.btn_save, self.btn_apply, self.btn_reload):
            hs.Add(b, 0, wx.ALL, 5)
        s.Add(hs, 0, wx.ALL, 5)

        tip = wx.StaticText(p, label="提示: 端口等部分参数对已运行服务需重启才生效。")
        tip.SetForegroundColour(wx.Colour(120, 120, 120))
        s.Add(tip, 0, wx.EXPAND | wx.ALL, 8)
        for t in (head, tip):
            t._orig_label = t.GetLabel().replace("\n", " ")
        self._tips = [head, tip]
        p.Bind(wx.EVT_SIZE, self._on_settings_resize)

        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)
        self.btn_apply.Bind(wx.EVT_BUTTON, self.on_apply)
        self.btn_reload.Bind(wx.EVT_BUTTON, self.on_reload_from_service)

    def _on_settings_resize(self, evt):
        evt.Skip()
        try:
            self._wrap_tips(evt.GetEventObject())
        except Exception:
            pass

    def _wrap_tips(self, content):
        """根据内容区宽度重排提示文字：先还原原文再逐字换行(兼容中文)。"""
        try:
            w = max(240, content.GetClientSize().width - 40)
        except Exception:
            return
        for t in getattr(self, "_tips", []):
            try:
                t.SetLabel(wrap_cjk(t, getattr(t, "_orig_label", t.GetLabel()), w))
                t.InvalidateBestSize()
                t.SetMinSize((-1, -1))
                t.SetMinSize((max(1, t.GetBestSize().width), t.GetBestSize().height))
            except Exception:
                pass
        try:
            content.FitInside()
            content.Layout()
        except Exception:
            pass

    def _build_tasks_tab(self):
        page = wx.Panel(self.nb)
        s = wx.BoxSizer(wx.VERTICAL)

        hs = wx.WrapSizer(wx.HORIZONTAL)
        self.btn_refresh = wx.Button(page, label="刷新")
        self.btn_seed = wx.Button(page, label="开始做种")
        self.btn_seed_all = wx.Button(page, label="全部做种")
        self.btn_unseed = wx.Button(page, label="停止做种")
        self.btn_purge = wx.Button(page, label="清除做种记录")
        self.auto_chk = wx.CheckBox(page, label="自动刷新(2s)")
        for b in (self.btn_refresh, self.btn_seed, self.btn_seed_all, self.btn_unseed, self.btn_purge):
            hs.Add(b, 0, wx.ALL, 4)
        hs.Add(self.auto_chk, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 4)
        s.Add(hs, 0, wx.EXPAND | wx.ALL, 4)

        tip = wx.StaticText(page, label="本页仅列出可做种的已完成 BT 任务；下载中的任务请到「下载管理」查看/暂停/继续。选中任务可在下方查看每个文件的做种状态。")
        tip.SetForegroundColour(wx.Colour(120, 120, 120))
        s.Add(tip, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)

        split = wx.SplitterWindow(page, style=wx.SP_LIVE_UPDATE | wx.SP_3DSASH)
        split.SetMinimumPaneSize(120)
        top = wx.Panel(split)
        ts = wx.BoxSizer(wx.VERTICAL)
        self.list = wx.ListCtrl(top, style=wx.LC_REPORT)
        for i, (t, w) in enumerate([("做种状态", 90), ("名称", 240), ("大小", 90),
                                    ("上传速度", 90), ("已上传", 90), ("连接数", 70),
                                    ("保存路径", 220), ("GID", 90)]):
            self.list.InsertColumn(i, t, width=w)
        ts.Add(self.list, 1, wx.EXPAND)
        top.SetSizer(ts)
        bottom = wx.Panel(split)
        bs = wx.BoxSizer(wx.VERTICAL)
        fhead = wx.StaticText(bottom, label="文件明细（选中上方任务查看每个文件的做种状态）")
        fhead.SetForegroundColour(wx.Colour(90, 90, 90))
        bs.Add(fhead, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        self.file_list = wx.ListCtrl(bottom, style=wx.LC_REPORT)
        for i, (t, w) in enumerate([("文件", 420), ("大小", 110), ("进度", 100), ("做种", 90)]):
            self.file_list.InsertColumn(i, t, width=w)
        bs.Add(self.file_list, 1, wx.EXPAND | wx.ALL, 4)
        bottom.SetSizer(bs)
        split.SplitHorizontally(top, bottom, 200)
        s.Add(split, 1, wx.EXPAND | wx.ALL, 5)
        self.sum_txt = wx.StaticText(page, label="就绪")
        s.Add(self.sum_txt, 0, wx.ALL, 6)
        self._min_refs.append((self.sum_txt, "就绪"))

        page.SetSizer(s)
        self.nb.AddPage(page, "做种管理")
        wx.CallAfter(page.Layout)

        self.btn_refresh.Bind(wx.EVT_BUTTON, lambda e: self.refresh_tasks())
        self.btn_seed.Bind(wx.EVT_BUTTON, lambda e: self.on_seed())
        self.btn_seed_all.Bind(wx.EVT_BUTTON, lambda e: self.on_seed_all())
        self.btn_unseed.Bind(wx.EVT_BUTTON, lambda e: self.on_unseed())
        self.btn_purge.Bind(wx.EVT_BUTTON, self.on_purge)
        self.auto_chk.Bind(wx.EVT_CHECKBOX, self.on_auto_toggle)
        self.list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_task_selected)
        page.Bind(wx.EVT_SHOW, self._on_tasks_show)
        self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_nb_page_changed)

    def _find_exe(self):
        return TD.find_aria2c() if TD else None

    def on_toggle_enable(self, evt):
        """启用/禁用 aria2：禁用时停止服务并切到禁用占位页。"""
        flag = self.chk_enable.GetValue()
        self._set_enabled(flag, persist=True)
        self._log("已启用 aria2" if flag else "已禁用 aria2 (BT 下载与服务均不可用)")

    def _apply_enabled_state(self):
        """根据启用状态与引擎可用性刷新按钮可用性。"""
        on = self.engine_enabled
        for b in (getattr(self, "btn_start", None),
                  getattr(self, "btn_stop", None), getattr(self, "btn_probe", None),
                  getattr(self, "btn_refresh", None), getattr(self, "btn_seed", None),
                  getattr(self, "btn_seed_all", None),
                  getattr(self, "btn_unseed", None),
                  getattr(self, "btn_purge", None), getattr(self, "auto_chk", None)):
            if b is not None:
                b.Enable(on)
        if hasattr(self, "port_txt"):
            self.port_txt.Enable(on)
            self.secret_txt.Enable(on)

    def on_find(self):
        if not hasattr(self, "src_txt"):
            return
        if not TD:
            self.src_txt.SetLabel("引擎: TorrentDownload 模块不可用")
            self.src_txt._orig_label = self.src_txt.GetLabel()
            return
        rep = TD.engine_report()
        lines = []
        for c in rep.get("candidates", []):
            mark = "✓" if c["exists"] else "✗"
            lines.append("%s %s: %s" % (mark, c["label"], c["path"]))
        if not rep.get("enabled"):
            lines.append("当前状态: 已禁用 (启用后才会使用引擎)")
        elif rep.get("exe"):
            lines.append("生效引擎: " + rep["exe"])
            if rep.get("version"):
                lines.append("版本: " + rep["version"])
        else:
            lines.append("生效引擎: 未找到 (请安装 aria2 后重试)")
        self.src_txt._orig_label = "\n".join(lines)
        self._refresh_wrapped(self.src_txt)
        self._apply_enabled_state()
        self._update_svc_label()
        self._refresh_stats()

    def _refresh_wrapped(self, t, pad=40, minimum=300):
        """重排多行文本并同步最小尺寸(避免行数变化被裁切)。"""
        try:
            w = max(minimum, t.GetParent().GetClientSize().width - pad)
            t.SetLabel(wrap_cjk(t, getattr(t, "_orig_label", t.GetLabel()), w))
            t.InvalidateBestSize()
            t.SetMinSize((-1, -1))
            t.SetMinSize((max(1, t.GetBestSize().width), t.GetBestSize().height))
            t.GetParent().Layout()
        except Exception:
            pass

    def _update_svc_label(self):
        if not hasattr(self, "svc_txt"):
            return
        svc = getattr(TD, "SERVICE", None) if TD else None
        if svc and svc.is_running():
            self.svc_txt._orig_label = "服务状态: 运行中  (端口 %d)" % svc.port
        elif not self.engine_enabled:
            self.svc_txt._orig_label = "服务状态: 已禁用"
        else:
            self.svc_txt._orig_label = "服务状态: 未运行"
        self._refresh_wrapped(self.svc_txt)

    def _refresh_stats(self):
        """后台读取全局统计并刷新“传输统计”标签（累计上传/下载、实时速度）。"""
        if not TD:
            return

        def work():
            stat = None
            try:
                svc = getattr(TD, "SERVICE", None)
                if svc and svc.is_running():
                    stat = svc.global_stat()
            except Exception:
                pass

            def done():
                if not hasattr(self, "stat_txt"):
                    return
                try:
                    if not stat:
                        self.stat_txt.SetLabel("累计上传: -   本次会话上传: -   上传速度: -   下载速度: -")
                        return
                    acc = int(stat.get("accumulated", 0) or 0)
                    sess = int(stat.get("uploadLength", 0) or 0)
                    us = int(stat.get("uploadSpeed", 0) or 0)
                    ds = int(stat.get("downloadSpeed", 0) or 0)
                    self.stat_txt.SetLabel(
                        "累计上传: %s   本次会话上传: %s   上传速度: %s/s   下载速度: %s/s"
                        % (_fmt(acc), _fmt(sess), _fmt(us), _fmt(ds)))
                except Exception:
                    pass
            wx.CallAfter(done)
        threading.Thread(target=work, daemon=True).start()

    def on_reset_stat(self, evt):
        """清零软件记录的累计上传字节。"""
        if not TD:
            return
        if wx.MessageBox("确定清空累计上传统计吗？", "BT 下载",
                         wx.YES_NO | wx.ICON_QUESTION, self.parent) != wx.YES:
            return
        try:
            TD.reset_accumulated_upload()
            self._log("已清零累计上传统计")
        except Exception as e:
            self._log("清零失败: " + str(e))
        self._refresh_stats()

    def _collect_service_args(self):
        try:
            port = int(self.port_txt.GetValue().strip() or self.rpc_port)
        except Exception:
            port = self.rpc_port
        secret = self.secret_txt.GetValue().strip()
        if not secret:
            import random as _r
            secret = "".join(_r.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(16))
            self.secret_txt.SetValue(secret)
        self.rpc_port, self.rpc_secret = port, secret
        cfg = load_config()
        cfg["aria2_rpc_port"] = port
        cfg["aria2_rpc_secret"] = secret
        save_config(cfg)
        return port, secret

    def on_start(self, evt):
        if not TD:
            return
        if not self.engine_enabled:
            wx.MessageBox("aria2 已禁用，请先在上方勾选启用。", "aria2",
                          wx.OK | wx.ICON_INFORMATION, self.parent)
            return
        exe = self._find_exe()
        if not exe:
            wx.MessageBox("未找到 aria2 引擎，请先安装 aria2。", "aria2", wx.OK | wx.ICON_ERROR, self.parent)
            return
        port, secret = self._collect_service_args()
        self._sync_opts_from_ui()
        self.btn_start.Disable()
        self._log("启动 aria2 服务 (端口 %d) ..." % port)

        def work():
            svc = TD.get_service(exe=exe, port=port, secret=secret, options=self.opts)
            ok, err = svc.start()
            if ok:
                try:
                    svc.auto_started = False
                except Exception:
                    pass
            def done():
                self.btn_start.Enable()
                if ok:
                    self._log("服务已启动")
                    self.refresh_tasks()
                    self._refresh_stats()
                else:
                    self._log("启动失败: " + str(err))
                self._update_svc_label()
            wx.CallAfter(done)
        threading.Thread(target=work, daemon=True).start()

    def on_stop(self, evt):
        if not TD:
            return
        TD.stop_service()
        self._log("服务已停止")
        self._update_svc_label()
        self.list.DeleteAllItems()
        try:
            if getattr(self, "file_list", None) and not self.file_list.IsBeingDeleted():
                self.file_list.DeleteAllItems()
        except Exception:
            pass
        self.entries = []
        self.sum_txt.SetLabel("服务已停止")
        try:
            self.stat_txt.SetLabel("累计上传: -   本次会话上传: -   上传速度: -   下载速度: -")
        except Exception:
            pass

    def on_probe(self, evt):
        if not TD:
            return
        if not self.engine_enabled:
            self._log("aria2 已禁用")
            return
        port, secret = self._collect_service_args()
        svc = TD.get_service(port=port, secret=secret)
        ok, info = svc.probe()
        if ok:
            self._log("RPC 连接成功: aria2 %s" % (info or {}).get("version", ""))
        else:
            self._log("RPC 连接失败: " + str(info))
        self._update_svc_label()

    def _sync_opts_from_ui(self):
        for key, _label, kind, _hint in OPT_FIELDS:
            c = self.opt_ctrls.get(key)
            if not c:
                continue
            v = c.GetValue().strip()
            if kind in ("int", "float") and v == "":
                v = DEFAULT_OPTS.get(key, "")
            self.opts[key] = v
        if hasattr(self, "chk_dht"):
            self.opts["enable_dht"] = "true" if self.chk_dht.GetValue() else "false"
        if hasattr(self, "chk_continue"):
            self.opts["continue"] = "true" if self.chk_continue.GetValue() else "false"
        self.opts.pop("dir", None)
        self.opts.pop("bt_enable_dht", None)

    def _persist(self):
        self._sync_opts_from_ui()
        cfg = load_config()
        cfg["aria2_options"] = self.opts
        cfg["aria2_rpc_port"] = self.rpc_port
        cfg["aria2_rpc_secret"] = self.rpc_secret
        return save_config(cfg)

    def on_save(self, evt):
        ok = self._persist()
        wx.MessageBox("设置已保存" if ok else "保存失败", "aria2",
                      wx.OK | (wx.ICON_INFORMATION if ok else wx.ICON_ERROR), self.parent)

    def on_apply(self, evt):
        self._persist()
        if not TD:
            return
        svc = getattr(TD, "SERVICE", None)
        if not (svc and svc.is_running()):
            wx.MessageBox("服务未运行，设置已保存，将在下次启动生效。", "aria2",
                          wx.OK | wx.ICON_INFORMATION, self.parent)
            return
        hot = {}
        hot = {k: v for k, v in hot.items() if v not in (None, "")}
        if not hot:
            wx.MessageBox("设置已保存，BT 参数需重启服务生效。", "BT 下载",
                          wx.OK | wx.ICON_INFORMATION, self.parent)
            return
        r, e = svc.client.change_global_option(hot)
        if e:
            wx.MessageBox("应用失败: " + str(e.get("message", e)), "BT 下载",
                          wx.OK | wx.ICON_ERROR, self.parent)
        else:
            wx.MessageBox("已应用到运行中服务。", "BT 下载",
                          wx.OK | wx.ICON_INFORMATION, self.parent)

    def on_reload_from_service(self, evt):
        if not TD:
            return
        svc = getattr(TD, "SERVICE", None)
        if not (svc and svc.is_running()):
            wx.MessageBox("服务未运行。", "aria2", wx.OK | wx.ICON_INFORMATION, self.parent)
            return
        r, e = svc.client.get_global_option()
        if e or not isinstance(r, dict):
            wx.MessageBox("读取失败: " + str((e or {}).get("message", e)), "aria2",
                          wx.OK | wx.ICON_ERROR, self.parent)
            return
        for key, _label, _kind, _hint in OPT_FIELDS:
            if key in r and key in self.opt_ctrls:
                self.opt_ctrls[key].SetValue(str(r[key]))
        if hasattr(self, "chk_dht"):
            self.chk_dht.SetValue(str(r.get("enable-dht", "true")).lower() == "true")
        if hasattr(self, "chk_continue"):
            self.chk_continue.SetValue(str(r.get("continue", "true")).lower() == "true")
        self._log("已从服务读取当前设置")

    def on_auto_toggle(self, evt):
        if self.auto_chk.GetValue():
            if not self.timer:
                self.timer = wx.Timer(self.parent)
                self.parent.Bind(wx.EVT_TIMER, self._on_auto_tick, self.timer)
            self.timer.Start(2000)
            self._on_auto_tick(None)
        else:
            if self.timer:
                self.timer.Stop()

    def _on_auto_tick(self, evt):
        self.refresh_tasks()
        self._refresh_stats()

    def _on_tasks_show(self, evt):
        evt.Skip()
        if evt.IsShown():
            wx.CallAfter(self.refresh_tasks)
            wx.CallAfter(self._refresh_stats)

    def _on_nb_page_changed(self, evt):
        evt.Skip()
        try:
            sel = self.nb.GetSelection()
            if sel == self.nb.GetPageCount() - 1:
                wx.CallAfter(self.refresh_tasks)
            if sel == 0:
                wx.CallAfter(self._refresh_stats)
        except Exception:
            pass

    def _load_seed_records(self):
        recs = []
        try:
            import DownloadUI
            hist = list(getattr(DownloadUI, "download_history", []) or [])
        except Exception:
            hist = []
        seen = set()
        for r in hist:
            if r.get("proto") != "bt":
                continue
            st = str(r.get("status", ""))
            if not (st.startswith("已完成") or r.get("bt_name") or r.get("bt_gid")):
                continue
            if st.startswith("失败") or st.startswith("已取消"):
                continue
            nm = str(r.get("bt_name") or r.get("filename") or "")
            if nm.startswith("[METADATA]"):
                continue
            src = r.get("source") or r.get("url") or ""
            if not src:
                continue
            key = self._infohash_of(src) or r.get("bt_gid") or src
            if key in seen:
                continue
            if not self._record_files_exist(r):
                continue
            seen.add(key)
            recs.append(r)
        return recs

    @staticmethod
    def _record_files_exist(r):
        files = r.get("bt_files") or []
        if files:
            sp = r.get("save_path") or ""
            for f in files:
                p = f.get("path") or ""
                if not p:
                    continue
                full = p if os.path.isabs(p) else os.path.join(sp, p)
                if os.path.exists(full):
                    return True
            return False
        sp = r.get("save_path") or ""
        fn = r.get("filename") or ""
        if sp and fn:
            return os.path.exists(os.path.join(sp, fn))
        return True

    def refresh_tasks(self):
        if not TD:
            return
        if not getattr(self, "list", None) or self.list.IsBeingDeleted():
            return
        if not self.engine_enabled:
            self.sum_txt.SetLabel("aria2 已禁用。")
            return
        if getattr(self, "_refresh_busy", False):
            return
        self._refresh_busy = True
        recs = self._load_seed_records()

        def work():
            seeding = []
            try:
                svc = getattr(TD, "SERVICE", None)
                if svc and svc.is_running():
                    seeding = svc.seeding_tasks()
            except Exception:
                pass
            finally:
                self._refresh_busy = False
            wx.CallAfter(self._fill_rows, recs, seeding)
        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _infohash_of(source):
        """从磁力链中提取 btih(去大写、去 urn 前缀)；非磁力返回空。"""
        s = (source or "").lower()
        i = s.find("urn:btih:")
        if i >= 0:
            return s[i + 9:].split("&")[0]
        return ""

    def _live_of(self, rec, seeding):
        """根据历史记录 + 服务返回的做种任务列表，匹配出实时任务字典(无则 None)。

        优先按 infohash 匹配；再退化到 bt_gid；最后尝试磁力/源串包含。
        """
        src = rec.get("source") or rec.get("url") or ""
        ih = self._infohash_of(src)
        gid = str(rec.get("bt_gid") or "")
        for d in (seeding or []):
            if ih and (d.get("infoHash") or "").lower() == ih:
                return d
        for d in (seeding or []):
            if gid and d.get("gid") == gid:
                return d
        if src:
            low = src.lower()
            for d in (seeding or []):
                dih = (d.get("infoHash") or "").lower()
                if dih and dih in low:
                    return d
        return None

    @staticmethod
    def _live_files(d):
        """从服务任务字典提取选中的文件（统一 path/length/completed）。"""
        out = []
        for f in ((d or {}).get("files") or []):
            if not f.get("selected", True):
                continue
            out.append({"path": f.get("path", ""),
                        "length": int(f.get("length", 0) or 0),
                        "completed": int(f.get("completedLength", 0) or 0)})
        return out

    def _render_files(self, files, seeding=False, hint=None):
        """把文件列表渲染到下方文件明细列表。

        seeding=True 时数据来自服务中正在做种的任务（每文件已完成即已做种）。
        files 为空时可在首行显示提示(hint)。
        """
        fl = getattr(self, "file_list", None)
        if fl is None or fl.IsBeingDeleted():
            return
        try:
            fl.DeleteAllItems()
        except Exception:
            return
        if not files and hint:
            try:
                fl.InsertItem(0, hint)
            except Exception:
                pass
            return
        for i, f in enumerate(files or []):
            path = f.get("path", "")
            length = int(f.get("length", 0) or 0)
            done = int(f.get("completed", 0) or 0)
            name = os.path.basename(path) or path or "(未命名)"
            pct = int(done * 100 // length) if length > 0 else (100 if done else 0)
            if seeding:
                state = "做种中" if (length <= 0 or done >= length) else ("%d%%" % pct)
            else:
                state = "已完成" if (length <= 0 or done >= length) else ("%d%%" % pct)
            idx = fl.InsertItem(i, name)
            fl.SetItem(idx, 1, _fmt(length))
            fl.SetItem(idx, 2, "%d%%" % pct)
            fl.SetItem(idx, 3, state)
        try:
            if fl.GetItemCount():
                fl.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        except Exception:
            pass

    def _on_task_selected(self, evt):
        """选中任务行时刷新下方文件明细。"""
        evt.Skip()
        idx = evt.GetIndex()
        if not (0 <= idx < len(self.entries)):
            return
        rec, live = self.entries[idx]
        if live:
            self._render_files(self._live_files(live), seeding=True)
        else:
            bf = rec.get("bt_files") or []
            if bf:
                self._render_files(bf, seeding=False)
            elif rec.get("bt_gid"):
                self._render_files([], hint="该任务的文件明细未记录（可能是旧版本下载的记录）。")
            else:
                self._render_files([], hint="无文件明细；开始做种后可从服务读取。")

    def _select_row(self, i):
        """选中指定行并渲染其文件明细。"""
        try:
            self.list.Select(i)
            self.list.Focus(i)
            self.list.EnsureVisible(i)
        except Exception:
            pass
        rec, live = self.entries[i]
        if live:
            self._render_files(self._live_files(live), seeding=True)
        else:
            bf = rec.get("bt_files") or []
            if bf:
                self._render_files(bf, seeding=False)
            else:
                self._render_files([], hint="无文件明细；该任务开始做种后可从服务实时读取每个文件。")

    def _first_row_with_files(self):
        """返回最适合展示文件明细的行号：优先实时且文件多的任务，否则历史含明细者。"""
        best, best_n = None, -1
        for i, (rec, live) in enumerate(self.entries):
            if live:
                n = len(self._live_files(live))
                active = str(live.get("status")) == "active"
                score = n + (1000 if active else 0)
                if n and score > best_n:
                    best, best_n = i, score
            elif rec.get("bt_files"):
                n = len(rec.get("bt_files"))
                if best is None and n > best_n:
                    best, best_n = i, n
        return best if best is not None else 0

    def _fill_rows(self, recs, seeding):
        if not getattr(self, "list", None) or self.list.IsBeingDeleted():
            return
        try:
            self.entries = []
            self.list.DeleteAllItems()
        except Exception:
            return
        used = set()
        rows = []
        for r in recs:
            live = self._live_of(r, seeding)
            if live is not None:
                used.add(id(live))
            rows.append((r, live))
        for d in (seeding or []):
            if id(d) in used:
                continue
            info = (d.get("bittorrent") or {}).get("info") or {}
            name = (info.get("name") if isinstance(info, dict) else "") or "(服务中任务)"
            rec = {"bt_name": name, "filename": name,
                   "file_size": int(d.get("totalLength", 0) or 0),
                   "save_path": d.get("dir", ""),
                   "source": "", "bt_seeding": True}
            rows.append((rec, d))
            used.add(id(d))
        seed_cnt = 0
        for i, (r, live) in enumerate(rows):
            try:
                if live:
                    seed_cnt += 1
                    up = int(live.get("uploadSpeed", 0) or 0)
                    st = "做种中" if str(live.get("status")) == "active" else "已停止做种"
                    uspd = _fmt(up) + "/s" if up else "0 B/s"
                    upl = _fmt(int(live.get("uploadLength", 0) or 0))
                    conns = str(live.get("connections", 0) or 0)
                    gid = live.get("gid", "")
                else:
                    st = "可做种" if r.get("bt_seeding") else "未做种"
                    uspd = "-"
                    upl = "-"
                    conns = "-"
                    gid = ""
                name = r.get("bt_name") or r.get("filename") or "(未命名)"
                if live:
                    info = (live.get("bittorrent") or {}).get("info") or {}
                    lname = info.get("name") if isinstance(info, dict) else ""
                    if lname and str(lname).lower() != str(name).lower():
                        name = lname
                size = _fmt((live.get("totalLength") if live else r.get("file_size")) or 0)
                idx = self.list.InsertItem(i, st)
                self.list.SetItem(idx, 1, name)
                self.list.SetItem(idx, 2, size)
                self.list.SetItem(idx, 3, uspd)
                self.list.SetItem(idx, 4, upl)
                self.list.SetItem(idx, 5, conns)
                self.list.SetItem(idx, 6, r.get("save_path", ""))
                self.list.SetItem(idx, 7, gid)
                self.entries.append((r, live))
            except Exception:
                continue
        try:
            self.sum_txt.SetLabel("共 %d 个可做种任务（做种中 %d）" % (len(rows), seed_cnt))
        except Exception:
            pass
        if self.entries:
            try:
                self._select_row(self._first_row_with_files())
            except Exception:
                pass
        else:
            self._render_files([], seeding=False)

    def _selected_records(self):
        recs = []
        idx = self.list.GetFirstSelected()
        while idx != -1:
            if 0 <= idx < len(self.entries):
                recs.append(self.entries[idx][0])
            idx = self.list.GetNextSelected(idx)
        return recs

    def _service_running(self):
        svc = getattr(TD, "SERVICE", None) if TD else None
        return bool(svc and svc.is_running())

    def _require_service(self):
        """做种前检查服务是否运行；未运行则提示（绝不自动拉起）。"""
        if self._service_running():
            return True
        wx.MessageBox("aria2 服务未运行，无法做种。\n\n"
                      "做种需先启动服务：请在「服务」页点“启动服务”，\n"
                      "或发起一次 BT 下载时会自动拉起。",
                      "BT 下载", wx.OK | wx.ICON_INFORMATION, self.parent)
        return False

    def on_seed(self):
        if not TD:
            return
        if not self._require_service():
            return
        recs = self._selected_records()
        if not recs:
            wx.MessageBox("请先选择要做种的任务。", "BT 下载", wx.OK | wx.ICON_INFORMATION, self.parent)
            return
        started = 0
        for r in recs:
            src = r.get("source") or r.get("url") or ""
            ok, info = TD.start_seed(src, r.get("save_path") or self.download_dir, force=True)
            if ok:
                started += 1
            else:
                self._log("做种失败(%s): %s" % (r.get("bt_name") or r.get("filename"), info))
        self.sum_txt.SetLabel("已开始做种 %d 个任务" % started)
        self.refresh_tasks()

    def on_seed_all(self):
        """为所有已完成 BT 任务做种（强制无限做种，不自动拉起服务）。"""
        if not TD:
            return
        if not self.engine_enabled:
            wx.MessageBox("aria2 已禁用，请先在“服务”页启用。", "BT 下载",
                          wx.OK | wx.ICON_INFORMATION, self.parent)
            return
        if not self._require_service():
            return
        self.btn_seed_all.Disable()
        self.sum_txt.SetLabel("正在为全部任务做种...")

        def work():
            try:
                n, fails = TD.seed_all(force=True)
            except Exception as e:
                n, fails = 0, [("-", str(e))]

            def done():
                self.btn_seed_all.Enable()
                self.sum_txt.SetLabel("全部做种完成：%d 个任务在做种" % n)
                for name, info in (fails or [])[:10]:
                    self._log("做种失败(%s): %s" % (name, info))
                self.refresh_tasks()
                self._refresh_stats()
            wx.CallAfter(done)
        threading.Thread(target=work, daemon=True).start()

    def on_unseed(self):
        if not TD:
            return
        recs = self._selected_records()
        if not recs:
            wx.MessageBox("请先选择要停止做种的任务。", "BT 下载", wx.OK | wx.ICON_INFORMATION, self.parent)
            return
        sel = self.list.GetFirstSelected()
        gid = self.list.GetItemText(sel, 7) if sel != -1 else ""
        if not gid:
            src = recs[0].get("source") or recs[0].get("url") or ""
            gid = TD.find_seed_gid(src)
        if gid:
            TD.cancel_service_task(gid)
        self.refresh_tasks()

    def on_purge(self, evt):
        if not TD:
            return
        svc = getattr(TD, "SERVICE", None)
        if svc and svc.is_running():
            try:
                svc.client.purge_download_result()
            except Exception:
                pass
        self.refresh_tasks()


def create_aria2_panel(parent, frame=None):
    """在给定 Panel 上构建 aria2 管理面板，返回面板对象。"""
    global PANEL
    try:
        PANEL = Aria2Panel(parent, frame)
        return PANEL
    except Exception as e:
        import logging
        logging.error("aria2 面板创建失败: %s" % e)
        print("aria2 面板创建失败:", e)
        return None


PANEL = None
