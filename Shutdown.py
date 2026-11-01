# Copyright (c) 2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import logging
import threading
import time
import wx

GRACE_SECONDS = 3.0
JOIN_SLICE = 0.1

_lock = threading.RLock()
_state = {
    "started": False,
    "finished": False,
    "stopping": False,
    "confirm_ui": True,
    "stages": [],
}
_resources = {}
_activity_sources = []

# -------------------------- 资源登记 --------------------------
def reset():
    with _lock:
        _state["started"] = False
        _state["finished"] = False
        _state["stopping"] = False
        _state["stages"] = []
        _resources.clear()
        del _activity_sources[:]

def register(name, obj):
    if obj is None:
        return
    with _lock:
        _resources[name] = obj

def unregister(name):
    with _lock:
        _resources.pop(name, None)

def resource(name):
    with _lock:
        return _resources.get(name)

def set_confirm_ui(flag):
    with _lock:
        _state["confirm_ui"] = bool(flag)

def is_started():
    with _lock:
        return _state["started"]

def is_finished():
    with _lock:
        return _state["finished"]

# -------------------------- 活跃任务探测 --------------------------
def add_activity_source(func):
    with _lock:
        if func not in _activity_sources:
            _activity_sources.append(func)

def _call_source(func):
    try:
        return int(func() or 0)
    except Exception as e:
        logging.warning(f"活跃任务探测失败: {e}")
        return 0

def _http_active():
    import NewDownloadCore as core
    count = 0
    for ctx in list(core.snapshot_contexts()):
        stop_ev = getattr(ctx, "stop_event", None)
        if stop_ev is not None and stop_ev.is_set():
            continue
        chunks = ctx.chunk_task_list or []
        if ctx.download_completed:
            continue
        if chunks and all(t.finished for t in chunks):
            continue
        count += 1
    return count

def _bt_active():
    try:
        import TorrentDownload as TD
    except Exception:
        return 0
    svc = getattr(TD, "SERVICE", None)
    if svc is None:
        return 0
    try:
        act, _e = svc.client.tell_active(keys=["gid"])
        wait, _e = svc.client.tell_waiting(0, 1000, keys=["gid"])
    except Exception:
        return 0
    return len(act or []) + len(wait or [])

def active_task_count():
    with _lock:
        sources = list(_activity_sources)
    total = _call_source(_http_active) + _call_source(_bt_active)
    for func in sources:
        total += _call_source(func)
    return total

# -------------------------- 进度提示 --------------------------
def _progress(text):
    hook = resource("progress")
    if hook is None:
        return
    try:
        hook(text)
    except Exception:
        pass

# -------------------------- 各阶段清理 --------------------------
def _stop_http_downloads():
    import NewDownloadCore as core
    for ctx in list(core.snapshot_contexts()):
        stop_ev = getattr(ctx, "stop_event", None)
        if stop_ev is not None:
            stop_ev.set()
        try:
            core.kill_active_curls(ctx)
        except Exception as e:
            logging.warning(f"终止 curl 子进程失败: {e}")

def _wait_http_downloads(deadline):
    import NewDownloadCore as core
    threads = [t for t in core.snapshot_threads() if t.is_alive()]
    for t in threads:
        remain = deadline - time.time()
        if remain <= 0:
            break
        t.join(timeout=remain)

def _flush_http_progress():
    import NewDownloadCore as core
    for ctx in list(core.snapshot_contexts()):
        if ctx.download_completed:
            continue
        chunks = ctx.chunk_task_list or []
        if chunks and all(t.finished for t in chunks):
            continue
        if not ctx.ndf_progress_path:
            continue
        try:
            with ctx.file_write_lock if ctx.file_write_lock is not None else _null_lock():
                core.dump_progress_json(ctx)
        except Exception as e:
            logging.warning(f"退出时保存断点失败: {e}")

def _stop_hotkeys():
    hotkeys = resource("hotkeys")
    if hotkeys is not None:
        hotkeys.unregister()

def _stop_aria2(deadline):
    try:
        import TorrentDownload as TD
    except Exception:
        return
    svc = getattr(TD, "SERVICE", None)
    if svc is None:
        return
    if not getattr(svc, "auto_started", False):
        return
    proc = getattr(svc, "proc", None)
    if proc is None or proc.poll() is not None:
        return
    try:
        svc.client.shutdown()
    except Exception as e:
        logging.warning(f"aria2 优雅关闭失败: {e}")
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.05)
    if proc.poll() is None:
        try:
            TD.stop_service()
        except Exception as e:
            logging.warning(f"aria2 强制停止失败: {e}")

def _destroy_tray():
    tray = resource("tray")
    if tray is None:
        return
    stop = getattr(tray, "_shutdown_stop", None)
    if stop is not None:
        try:
            stop()
        except Exception:
            pass
    try:
        tray.Destroy()
    except Exception as e:
        logging.warning(f"托盘销毁失败: {e}")

class _null_lock(object):
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

# -------------------------- 顶层窗口处理 --------------------------
def _top_levels(exclude):
    app = wx.GetApp()
    if app is None:
        return []
    out = []
    try:
        for win in wx.GetTopLevelWindows():
            if win is not exclude and win is not None:
                out.append(win)
    except Exception:
        pass
    return out

def _stop_timers(window, seen):
    try:
        children = [window] + list(window.GetChildren())
    except Exception:
        children = [window]
    for child in children:
        if id(child) in seen:
            continue
        seen.add(id(child))
        timers = getattr(child, "timer", None)
        if isinstance(timers, wx.Timer):
            timers = [timers]
        for timer in (timers or []):
            if isinstance(timer, wx.Timer) and timer.IsRunning():
                try:
                    timer.Stop()
                except Exception:
                    pass

def _destroy_windows(exclude):
    if exclude is not None and hasattr(exclude, "timer"):
        exclude.timer.Stop()
    seen = set()
    for window in _top_levels(exclude):
        _stop_timers(window, seen)
        _progress_target(window)
    for window in _top_levels(exclude):
        has_ctx = hasattr(window, "ctx")
        if has_ctx:
            try:
                targets = window.shutdown_targets()
            except Exception:
                targets = []
            for target in targets:
                try:
                    target.Destroy()
                except Exception:
                    pass
        try:
            window.Hide()
        except Exception:
            pass
        try:
            window.Destroy()
        except Exception as e:
            logging.warning(f"销毁顶层窗口失败: {e}")
    if exclude is not None:
        try:
            exclude.Hide()
        except Exception:
            pass
        try:
            exclude.Destroy()
        except Exception as e:
            logging.warning(f"销毁主窗口失败: {e}")

def _progress_target(window):
    setter = getattr(window, "set_status_text", None)
    if not callable(setter):
        return
    current = resource("progress")
    if current is None:
        register("progress", setter)

# -------------------------- 确认与入口 --------------------------
def _confirm(count):
    with _lock:
        ui = _state["confirm_ui"]
    if not ui:
        return True
    dlg = wx.MessageDialog(
        None,
        f"当前有 {count} 个下载任务正在进行。\n退出将停止任务并保存断点，下次启动可继续。",
        "退出确认",
        wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
    try:
        res = dlg.ShowModal()
    finally:
        dlg.Destroy()
    return res == wx.ID_YES

def request_exit(owner=None):
    with _lock:
        if _state["started"]:
            return
        _state["started"] = True
    wx.CallAfter(_request_exit_confirmed, owner)

def _request_exit_confirmed(owner):
    try:
        count = active_task_count()
    except Exception as e:
        logging.warning(f"活跃任务统计失败: {e}")
        count = 0
    if count > 0 and not _confirm(count):
        with _lock:
            _state["started"] = False
        return
    begin(owner)

def request_restart(owner=None):
    with _lock:
        if _state["started"]:
            return
        _state["started"] = True
    wx.CallAfter(begin, owner, True)

def begin(owner=None, restart=False):
    deadline = time.time() + GRACE_SECONDS
    logging.info("开始退出流程")
    _progress("正在停止下载任务...")
    _stage("stop_http", _stop_http_downloads)
    _stage("wait_http", _wait_http_downloads, deadline)
    _stage("flush_http", _flush_http_progress)
    _progress("正在停止 aria2 服务...")
    _stage("stop_aria2", _stop_aria2, deadline)
    _stage("stop_hotkeys", _stop_hotkeys)
    _stage("destroy_tray", _destroy_tray)
    _stage("destroy_windows", _destroy_windows, owner)
    _stage("quit_mainloop", _quit_mainloop)
    with _lock:
        _state["finished"] = True
    logging.info(f"退出流程完成: {list(_state['stages'])}")
    if restart:
        _restart_process()
    return True

def _quit_mainloop():
    app = wx.GetApp()
    if app is not None:
        app.ExitMainLoop()

def _restart_process():
    import os
    import sys
    import subprocess
    args = [a for a in sys.argv[1:] if not str(a).startswith("--elevated")]
    if getattr(sys, "frozen", False):
        cmd = [sys.executable] + args
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        script = os.path.abspath(sys.argv[0])
        cmd = [sys.executable, script] + [a for a in args if os.path.abspath(a) != script]
        base = os.path.dirname(script)
    if sys.platform.startswith("win"):
        import ctypes
        import subprocess as sp
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", cmd[0], sp.list2cmdline(cmd[1:]), base, 1)
        if int(ret or 0) <= 32:
            logging.error(f"重启进程失败: {ret}")
    else:
        try:
            subprocess.Popen(["pkexec"] + cmd, cwd=base)
        except Exception as e:
            logging.error(f"重启进程失败: {e}")

def _stage(name, func, *args):
    try:
        func(*args)
        result = "ok"
    except Exception as e:
        result = f"error: {e}"
        logging.warning(f"退出阶段 {name} 失败: {e}")
    with _lock:
        _state["stages"].append((name, result))

# -------------------------- 结尾对账 --------------------------
def is_stopping():
    with _lock:
        return _state["stopping"]

def finish(deadline):
    with _lock:
        _state["stopping"] = True
    import NewDownloadCore as core
    threads = [t for t in core.snapshot_threads() if t.is_alive()]
    http_ok = True
    for t in threads:
        remain = deadline - time.time()
        if remain <= 0:
            http_ok = False
            break
        t.join(timeout=remain)
    try:
        _flush_http_progress()
    except Exception as e:
        logging.warning(f"结尾断点写入失败: {e}")
    bt = 0
    try:
        bt = _call_source(_bt_active)
    except Exception:
        pass
    if not http_ok or bt > 0:
        logging.warning(f"退出未完全等待: HTTP线程残留={not http_ok} BT活动={bt}")
    else:
        logging.info("退出对账完成：无残留任务")
