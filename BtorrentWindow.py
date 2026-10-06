# Copyright (c) 2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT

import wx
import os
import platform
try:
    import TorrentDownload as TD
except Exception:
    TD = None


def _fmt(n):
    if n is None:
        return "未知"
    try:
        n = float(n or 0)
    except Exception:
        return "未知"
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return "%.1f %s" % (n, u)
        n /= 1024.0
    return "%.1f B" % n


class BtNewTaskDialog(wx.Dialog):
    """BT 下载前的确认对话框：选择保存位置与做种参数。"""

    def __init__(self, parent, source, save_path):
        super(BtNewTaskDialog, self).__init__(parent, title="新建 BT 下载", size=(560, 320))
        self.result = None

        p = wx.Panel(self)
        vs = wx.BoxSizer(wx.VERTICAL)

        info_box = wx.StaticBoxSizer(wx.VERTICAL, p, "任务信息")
        grid = wx.FlexGridSizer(cols=2, hgap=8, vgap=8)
        grid.AddGrowableCol(1, 1)

        grid.Add(wx.StaticText(p, label="来源:"), 0, wx.ALIGN_CENTER_VERTICAL)
        src_name = os.path.basename(source) if os.path.isfile(source) else source
        src_txt = wx.StaticText(p, label=src_name or src_name)
        src_txt.Wrap(400)
        grid.Add(src_txt, 1, wx.EXPAND)

        grid.Add(wx.StaticText(p, label="保存目录:"), 0, wx.ALIGN_CENTER_VERTICAL)
        path_row = wx.BoxSizer(wx.HORIZONTAL)
        self.path_ctrl = wx.TextCtrl(p, value=save_path or "")
        browse_btn = wx.Button(p, label="浏览...", size=(64, -1))
        path_row.Add(self.path_ctrl, 1, wx.EXPAND | wx.RIGHT, 5)
        path_row.Add(browse_btn, 0)
        grid.Add(path_row, 1, wx.EXPAND)

        info_box.Add(grid, 1, wx.EXPAND | wx.ALL, 8)

        seed_row = wx.FlexGridSizer(cols=4, hgap=8, vgap=8)
        seed_row.Add(wx.StaticText(p, label="做种时间(分):"), 0, wx.ALIGN_CENTER_VERTICAL)
        try:
            _st = int(TD.bt_seed_time()) if TD else 0
        except Exception:
            _st = 0
        self.seed_time_ctrl = wx.SpinCtrl(p, value=str(max(_st, 0)), min=0, max=100000,
                                          size=(110, -1))
        seed_row.Add(self.seed_time_ctrl, 0, wx.ALIGN_CENTER_VERTICAL)

        seed_row.Add(wx.StaticText(p, label="做种率:"), 0, wx.ALIGN_CENTER_VERTICAL)
        try:
            _sr = float(TD.bt_seed_ratio()) if TD else 1.0
        except Exception:
            _sr = 1.0
        self.seed_ratio_ctrl = wx.SpinCtrlDouble(p, value=str(_sr), min=0.0, max=100.0,
                                                 inc=0.1, size=(110, -1))
        self.seed_ratio_ctrl.SetDigits(1)
        seed_row.Add(self.seed_ratio_ctrl, 0, wx.ALIGN_CENTER_VERTICAL)
        info_box.Add(seed_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        vs.Add(info_box, 1, wx.EXPAND | wx.ALL, 10)

        tip = wx.StaticText(p, label="提示：做种时间/做种率为 0 表示下载完成后不做种。")
        tip.SetForegroundColour(wx.Colour(120, 120, 120))
        vs.Add(tip, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        self.ok_btn = wx.Button(p, wx.ID_OK, label="开始下载")
        cancel_btn = wx.Button(p, wx.ID_CANCEL, label="取消")
        btn_sizer.AddButton(self.ok_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        vs.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        p.SetSizer(vs)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(p, 1, wx.EXPAND)
        self.SetSizer(outer)
        self.Centre()

        browse_btn.Bind(wx.EVT_BUTTON, self.on_browse)
        self.ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
        self.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL), id=wx.ID_CANCEL)

    def on_browse(self, evt):
        cur = self.path_ctrl.GetValue().strip()
        dlg = wx.DirDialog(self, "选择保存目录", cur,
                           style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dlg.ShowModal() == wx.ID_OK:
            self.path_ctrl.SetValue(dlg.GetPath())
        dlg.Destroy()

    def on_ok(self, evt):
        path = self.path_ctrl.GetValue().strip()
        if not path:
            wx.MessageBox("请选择保存目录", "提示", wx.OK | wx.ICON_WARNING)
            return
        try:
            st = int(self.seed_time_ctrl.GetValue())
        except Exception:
            st = 0
        try:
            sr = float(self.seed_ratio_ctrl.GetValue())
        except Exception:
            sr = 0.0
        self.result = {"save_path": path, "seed_time": max(st, 0), "seed_ratio": max(sr, 0.0)}
        self.EndModal(wx.ID_OK)


class BtDownloadFrame(wx.Frame):
    """BT 下载独立进度窗口。storage 由引擎线程与主窗共享。"""

    def __init__(self, parent, title_src, save_path, storage, on_done=None):
        super(BtDownloadFrame, self).__init__(parent, title="BT下载", size=(460, 210))
        self.storage = storage
        self.gid_hint = None
        self.on_done = on_done
        self.paused = False
        self._closing = False
        p = wx.Panel(self)
        vs = wx.BoxSizer(wx.VERTICAL)

        self.name_txt = wx.StaticText(p, label="标题: 正在获取种子信息...")
        self.name_txt.Wrap(430)
        vs.Add(self.name_txt, 0, wx.ALL | wx.EXPAND, 6)

        self.status_txt = wx.StaticText(p, label="状态: 连接中")
        vs.Add(self.status_txt, 0, wx.ALL, 4)

        self.gauge = wx.Gauge(p, range=1000)
        vs.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

        self.info_txt = wx.StaticText(p, label="进度计算中...")
        vs.Add(self.info_txt, 0, wx.ALL, 4)

        hs = wx.BoxSizer(wx.HORIZONTAL)
        self.pause_btn = wx.Button(p, label="暂停")
        self.cancel_btn = wx.Button(p, label="取消")
        hs.Add(self.pause_btn, 0, wx.ALL, 5)
        hs.Add(self.cancel_btn, 0, wx.ALL, 5)
        hs.AddStretchSpacer(1)
        vs.Add(hs, 0, wx.EXPAND, 4)

        tip = wx.StaticText(p, label="下载保存在: " + save_path)
        tip.SetForegroundColour(wx.Colour(120, 120, 120))
        vs.Add(tip, 0, wx.ALL, 6)

        p.SetSizer(vs)
        self.Centre()
        self.Bind(wx.EVT_BUTTON, self.on_pause, self.pause_btn)
        self.Bind(wx.EVT_BUTTON, self.on_cancel, self.cancel_btn)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_tick, self.timer)
        self.timer.Start(300)
        self.Show()

    # ---------------- 内部 ---------------- 
    def _gid(self):
        try:
            return self.storage.get("gid")
        except Exception:
            return None

    def on_tick(self, evt):
    
        if self._closing or not self:
            return
        s = self.storage or {}
        status = s.get("status", "下载中")
        name = s.get("name") or ""
        if name:
            self.name_txt.SetLabel("标题: " + name)
        total = s.get("total") or 0
        done = s.get("done") or 0
        speed = s.get("speed") or 0
        if status == "完成":
            p_bas = 1000  
            done = total or done
            speed = 0
        elif status == "做种中":
            p_bas = 1000
            done = total or done
        else:

            p_bas = (done * 1000 // total) if (total and total > 0) else 0
            if total and done >= total:
                p_bas = 990
        self.gauge.SetValue(min(1000, int(p_bas)))
        if status == "做种中":
            self.info_txt.SetLabel("%s / %s  上传 %s/s" %
                                   (_fmt(done), _fmt(total), _fmt(speed)))
        else:
            self.info_txt.SetLabel(
                "%s / %s  %s/s" % (_fmt(done), _fmt(total), _fmt(speed)))
        if status == "下载中":
            stxt = "下载中 ..."
            if total and done >= total and done > 0:
                stxt = "数据已下满，收尾校验中..."
        elif status == "做种中":
            stxt = "已完成，做种中 ..."
        elif status == "完成":
            stxt = "已完成"
        elif status == "失败":
            stxt = "失败: " + s.get("err", "")
        elif status == "取消":
            stxt = "已取消"
        else:
            stxt = str(status)
        self.status_txt.SetLabel("状态: " + stxt)
        if status in ("完成", "失败", "取消"):
            self._closing = True
            self.timer.Stop()
            if self.on_done:
                try:
                    self.on_done(status)
                except Exception:
                    pass
            wx.CallAfter(self._safe_destroy)
        elif self._gid() and not self.paused and \
                (s.get("engine_status") or "").lower() == "paused":
       
            self.paused = True
            self.pause_btn.SetLabel("继续")

    def _safe_destroy(self):
        try:
            if not self.IsBeingDeleted():
                self.Destroy()
        except Exception:
            pass

    def on_pause(self, evt):
        if self._closing:
            return
        gid = self._gid()
        if not gid or not TD:
            return
        if not self.paused:
            TD.set_pause(gid, True)
            self.paused = True
            self.pause_btn.SetLabel("继续")
        else:
            TD.set_pause(gid, False)
            self.paused = False
            self.pause_btn.SetLabel("暂停")

    def on_cancel(self, evt):
        if self._closing:
            return
        gid = self._gid()
        if gid and TD:
            TD.cancel_task(gid)
        self.status_txt.SetLabel("状态: 正在取消...")
        self.pause_btn.Disable()
        self.cancel_btn.Disable()

    def on_close(self, evt):
        self._closing = True
        try:
            self.timer.Stop()
        except Exception:
            pass
        evt.Skip()


def show_bt_window(parent, storage, save_path):
    """在主线程创建进度窗口（非阻塞）。"""
    win = BtDownloadFrame(None if parent is None else (parent.GetTopLevelParent() or parent),
                          "", save_path, storage)
    return win


def run_standalone(source, save_path="", on_finish=None, ask=True):
    """独立启动一个 BT 下载窗口（不拉起主窗口）。

    仿照 .ndf 恢复下载的做法：仅弹出一个下载进度窗口，
    后台线程执行 BT 任务，完成后窗口自动关闭并结束进程。
    ask=True 时先在下载前弹出确认对话框（保存位置/做种参数）。
    返回进程退出码（0 成功，1 失败，2 用户取消）。
    """
    if TD is None:
        print("BT 引擎不可用：无法导入 TorrentDownload")
        return 1

    import threading

    src = source
    if not src:
        print("错误: 缺少 BT 来源")
        return 1
    if os.path.isfile(src):
        src = os.path.abspath(src)

 
    app = wx.GetApp()
    if app is None:
        app = wx.App(False)

    if not save_path or not str(save_path).strip():
        try:
            save_path = TD.app_download_dir()
        except Exception:
            save_path = os.path.join(os.path.expanduser("~"), "Downloads")

    seed_time = None
    seed_ratio = None


    if ask:
        dlg = BtNewTaskDialog(None, src, save_path)
        try:
            if dlg.ShowModal() != wx.ID_OK or not dlg.result:
                print("已取消 BT 下载")
                return 2
            save_path = dlg.result["save_path"]
            seed_time = dlg.result["seed_time"]
            seed_ratio = dlg.result["seed_ratio"]
        finally:
            dlg.Destroy()

    try:
        os.makedirs(save_path, exist_ok=True)
    except Exception as e:
        print(f"创建保存目录失败: {save_path} - {e}")

    use_service = bool(getattr(TD, "bt_use_service", lambda: False)())
    storage = {"status": "连接中", "gid": None, "engine_status": "active",
               "name": "", "done": 0, "total": 0, "speed": 0,
               "via_service": use_service}
    result = {"ok": False, "msg": ""}

    def on_state(state, gid):
        try:
            status = state.get("status", "下载中")
            storage["status"] = "完成" if status == "完成" else ("失败" if status == "失败" else status)
            if gid:
                storage["gid"] = gid
            if state.get("name"):
                storage["name"] = state["name"]
            storage["done"] = state.get("done", 0)
            storage["total"] = state.get("total", 0)
            storage["speed"] = state.get("speed", 0)
            if state.get("err"):
                storage["err"] = state["err"]
            storage["engine_status"] = state.get("engine_status", storage.get("engine_status", "active"))
        except Exception:
            pass

    def worker():
        try:
            if use_service:
                ok = TD.run_bt_task_via_service(src, save_path, on_state,
                                                seed_time=seed_time, seed_ratio=seed_ratio)
            else:
                exe, err = _find_aria2c()
                if not exe:
                    storage["status"] = "失败"
                    storage["err"] = err
                    return
                ok = TD.run_bt_task(src, save_path, exe, on_state)
            result["ok"] = bool(ok)
        except Exception as e:
            storage["status"] = "失败"
            storage["err"] = str(e)
            result["msg"] = str(e)

    def on_done(status):
        result["msg"] = result["msg"] or status
        if on_finish:
            try:
                on_finish(status, result["ok"])
            except Exception:
                pass
        wx.CallLater(400, app.ExitMainLoop)

    win = BtDownloadFrame(None, src, save_path, storage, on_done=on_done)
    threading.Thread(target=worker, daemon=True).start()
    app.MainLoop()


    if not result["ok"]:
        msg = storage.get("err") or result["msg"] or "BT 下载未完成"
        print(f"BT 下载失败: {msg}")
        return 1
    return 0


def _find_aria2c():
    """查找本机 aria2c，返回 (exe, error)。"""
    try:
        exe = TD.find_aria2c() if TD else None
    except Exception:
        exe = None
    if exe:
        return exe, None
    return None, ("未找到 aria2 引擎。请先安装 aria2 后重试。\n"
                  "Linux: sudo apt install aria2 / sudo pacman -S aria2\n"
                  "Windows: 从 aria2 官网下载 aria2c.exe 放入程序目录或 PATH")
