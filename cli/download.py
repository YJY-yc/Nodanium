# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import sys
import json
import time
import threading

from . import ansi, i18n
from .ansi import Ansi, paint


# -------------------------- 终端输出工具 --------------------------
def _term_width(default: int = 100) -> int:
    try:
        return os.get_terminal_size().columns
    except Exception:
        return default


def _fmt_size(n: int) -> str:
    if n < 0:
        n = 0
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KiB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.2f} MiB"
    return f"{n / 1024 ** 3:.2f} GiB"


def _fmt_eta(sec) -> str:
    if sec is None or sec < 0:
        return i18n.t("progress.eta_calc")
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _progress_bar(pct: float, width: int = 30) -> str:
    filled = int(width * pct / 100)
    filled = max(0, min(width, filled))
    bar_done = paint("#" * filled, Ansi.GREEN)
    bar_todo = paint("-" * (width - filled), Ansi.GRAY)
    return f"[{bar_done}{bar_todo}]"


def _info(label: str, value: str) -> None:
    print(f"  {paint(label + ':', Ansi.CYAN)} {value}")


# -------------------------- 引擎 UI 适配器 --------------------------
class _CliFrame:
    """伪装成引擎期望的 ui_frame，把回调写入共享状态。"""

    def __init__(self, state):
        self._s = state

    def set_status_text(self, msg):
        self._s["status"] = msg

    def append_log(self, msg):
        self._s["logs"].append(msg)

    def update_grid_cell(self, idx, pct):
        self._s["chunks"][idx] = pct

    def refresh_speed_info(self, speed_str, time_str, remain_str, pct):
        self._s["speed_str"] = speed_str
        self._s["elapsed"] = time_str
        self._s["remain"] = remain_str
        self._s["pct"] = pct

    def on_paused(self):
        self._s["paused"] = True

    def _handle_completed_close(self):
        pass


class _SyncCallAfter:
    """把 wx.CallAfter 变为同步执行（下载线程内直接调用回调）。"""

    def __init__(self):
        self._orig = None
        self._active = False

    def install(self, wx_module):
        if wx_module is None:
            return
        self._orig = wx_module.CallAfter
        self._active = True

        def _sync(func, *args, **kwargs):
            if self._active:
                try:
                    func(*args, **kwargs)
                except Exception:
                    pass
            else:
                self._orig(func, *args, **kwargs)

        wx_module.CallAfter = _sync

    def restore(self, wx_module):
        self._active = False
        if wx_module is not None and self._orig is not None:
            wx_module.CallAfter = self._orig


# -------------------------- TTY 输出统一出口 --------------------------
class _TtyWriter:
    """替换 sys.stdout：进度条固定在最底行，其他任何输出（含引擎裸 print）
    都先抹掉进度行、写内容、再重画进度行；按行缓冲避免 print 分段 write 产生空行。"""

    def __init__(self, real):
        self._real = real
        self._lock = threading.RLock()
        self._line = ""          # 当前进度行（已上色）
        self._active = False      # 进度行是否已显示
        self._buf = ""            # 行缓冲

    def set_progress(self, text: str):
        with self._lock:
            self._line = text
            self._redraw()

    def clear_progress(self):
        with self._lock:
            self._erase()

    def hide(self):
        with self._lock:
            self._erase()

    def _erase(self):
        if self._active:
            self._real.write("\r\033[K")
            self._real.flush()
            self._active = False

    def _redraw(self):
        if not self._line:
            return
        self._real.write("\r\033[K" + self._line)
        self._real.flush()
        self._active = True

    def _emit_line(self, text: str):
        self._erase()
        self._real.write(text + "\n")
        self._real.flush()
        self._redraw()

    def write(self, text):
        if not text:
            return
        with self._lock:
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                self._emit_line(line)
            # 无换行的残留（如进度行中间态）——若有进度行则先不动
            if self._buf and not self._line:
                self._erase()
                self._real.write(self._buf)
                self._real.flush()
                self._buf = ""

    def flush(self):
        try:
            self._real.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._real, name)


# -------------------------- 渲染器 --------------------------
class _Renderer:
    def __init__(self, state, use_tty: bool, as_json: bool):
        self.s = state
        self.use_tty = use_tty
        self.as_json = as_json
        self._last_lines = 0
        self._last_json_ts = 0.0
        self._printed_logs = 0
        self._last_bytes = 0
        self._last_ts = 0.0
        self.writer = None

    def sample_speed(self, done: int):
        now = time.time()
        if self._last_ts and done >= self._last_bytes:
            dt = now - self._last_ts
            if dt >= 0.3:
                self.s["speed_bps"] = (done - self._last_bytes) / dt
        self._last_bytes = done
        self._last_ts = now

    def _json_tick(self, force=False):
        now = time.time()
        if not force and now - self._last_json_ts < 0.5:
            return
        self._last_json_ts = now
        done = self.s["done"]
        total = self.s["total"]
        pct = (done / total * 100) if total > 0 else 0
        payload = {
            "filename": self.s["filename"],
            "status": self.s["status"],
            "done": done,
            "total": total,
            "pct": round(pct, 2),
            "speed": self.s["speed_bps"],
            "speed_str": self.s["speed_str"],
            "eta": self.s["remain"],
            "backend": self.s.get("backend", ""),
            "chunks_done": sum(1 for v in self.s["chunks"].values() if v >= 100),
            "chunks_total": len(self.s["chunks"]),
        }
        print(json.dumps(payload, ensure_ascii=False), flush=True)

    def _flush_logs(self):
        logs = self.s["logs"]
        while self._printed_logs < len(logs):
            msg = logs[self._printed_logs]
            self._printed_logs += 1
            print(f"  {paint('*', Ansi.YELLOW)} {msg}", flush=True)

    def _build_progress(self, width):
        """按终端宽度拼装进度条，保证可见宽度 <= width（避免折行）。"""
        total = self.s["total"]
        done = self.s["done"]
        pct = (done / total * 100) if total > 0 else 0
        name = self.s["filename"]
        chunks_done = sum(1 for v in self.s["chunks"].values() if v >= 100)
        chunks_total = len(self.s["chunks"])
        active = chunks_total - chunks_done
        speed = self.s["speed_str"] or "-"
        eta = self.s["remain"] or "-"
        size_pair = f"{_fmt_size(done)}/{_fmt_size(total) if total > 0 else '?'}"

        # 从完整到精简逐级降级，直到宽度合适
        for bar_w, show_name, show_size, show_chunks, name_max in (
            (30, True, True, True, 28),
            (24, True, True, True, 20),
            (18, True, True, True, 14),
            (14, True, False, True, 12),
            (10, False, False, True, 0),
            (6, False, False, False, 0),
        ):
            bar = _progress_bar(pct, bar_w)
            parts = []
            if show_name:
                parts.append(name[:name_max])
            parts.append(f"{bar} {pct:5.1f}%")
            parts.append(speed)
            parts.append(f"{i18n.t('progress.eta_short')} {eta}")
            if show_size:
                parts.append(f"[{size_pair}]")
            line = "  ".join(parts)
            visible = ansi.strip_len(line)
            if show_chunks:
                chunk_txt = "  " + i18n.t(
                    "progress.chunk_short",
                    finished=chunks_done, total=chunks_total, active=active)
                if visible + ansi.strip_len(chunk_txt) <= width - 1:
                    return line + paint(chunk_txt, Ansi.DIM)
            if visible <= width - 1:
                return line
        return line

    def render(self, final=False):
        self._flush_logs()
        if self.as_json:
            self._json_tick(force=final)
            return

        if self.use_tty:
            width = _term_width()
            full = self._build_progress(width)
            if self.writer is not None:
                self.writer.set_progress(full)
        else:
            if final or not self._last_lines:
                print(self._build_plain(), flush=True)
        self._last_lines += 1

    def _build_plain(self):
        total = self.s["total"]
        done = self.s["done"]
        pct = (done / total * 100) if total > 0 else 0
        chunks_done = sum(1 for v in self.s["chunks"].values() if v >= 100)
        chunks_total = len(self.s["chunks"])
        line = i18n.t(
            "progress.line",
            name=self.s["filename"][:28],
            bar=_progress_bar(pct),
            pct=f"{pct:5.1f}",
            speed=self.s["speed_str"] or "-",
            eta=self.s["remain"] or "-",
            done=_fmt_size(done),
            total=_fmt_size(total) if total > 0 else "?",
        )
        chunk_line = i18n.t(
            "progress.chunk_line",
            finished=chunks_done, total=chunks_total,
            active=chunks_total - chunks_done)
        return line + "\n" + chunk_line

    def clear_progress(self):
        if self.writer is not None:
            self.writer.clear_progress()

    def finish_line(self):
        if self.writer is not None:
            self.writer.clear_progress()
        if self.use_tty and not self.as_json:
            sys.stdout.write("\033[?25h")
            sys.stdout.flush()

    def hide_cursor(self):
        if self.use_tty and not self.as_json:
            sys.stdout.write("\033[?25l")
            sys.stdout.flush()


# -------------------------- 主流程 --------------------------
def _probe_with_progress(core, ctx, state, timeout: float = 60.0) -> bool:
    """后台探测文件大小；主线程显示旋转动画与耗时。

    探测阶段引擎日志（含 curl 兜底切换）实时打印；超过 timeout 后不再中止探测，
    而是继续等待 curl 兜底结果（引擎内部探测链自有超时），只有引擎返回才结束。
    """
    import itertools
    done = {"flag": False, "err": None}

    def _run():
        try:
            core.fetch_file_size_and_setup_chunks(ctx)
        except Exception as e:
            done["err"] = str(e) or type(e).__name__
        finally:
            done["flag"] = True

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    printed = {"n": 0}

    def _drain_logs():
        logs = state["logs"]
        while printed["n"] < len(logs):
            msg = logs[printed["n"]]
            printed["n"] += 1
            print(f"  {paint('*', Ansi.YELLOW)} {msg}", flush=True)

    if not sys.stdout.isatty():
        while not done["flag"]:
            t.join(timeout=0.2)
            _drain_logs()
        _drain_logs()
        return done["flag"]

    frames = itertools.cycle("|/-\\")
    start = time.time()
    soft_warned = False
    while not done["flag"]:
        _drain_logs()
        waited = time.time() - start
        line = (f"{i18n.t('info.fetching')} {next(frames)} "
                f"({waited:4.1f}s)")
        if waited >= timeout:
            ctx.stop_event.clear()
            if not soft_warned:
                soft_warned = True
                sys.stdout.write("\r\033[K")
                print(paint(i18n.t("info.probe_slow"), Ansi.YELLOW), flush=True)
            line = (f"{i18n.t('info.probe_slow')} {next(frames)} "
                    f"({waited:4.1f}s)")
        sys.stdout.write("\r\033[K" + paint(line, Ansi.DIM))
        sys.stdout.flush()
        time.sleep(0.1)
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()
    _drain_logs()
    return done["flag"]


def _resolve_filename(url: str, given: str) -> str:
    if given:
        return given
    base = url.split("?", 1)[0].rstrip("/").split("/")[-1]
    return base or "download.bin"


def _apply_probe_result(core, ctx, res) -> None:
    """把探测结果写入 ctx 并建分片。res 需含 ok/status/final_url/total_size/use_curl。"""
    if not res.get("ok"):
        status = int(res.get("status") or 0)
        if status >= 400:
            ctx.info_error = i18n.t("error.http_status", status=status)
        else:
            ctx.info_error = res.get("error") or i18n.t("error.curl_probe_failed")
        return
    ctx.use_curl = bool(res.get("use_curl"))
    final_url = (res.get("final_url") or "").strip()
    if final_url and final_url != ctx.url:
        ctx.url = final_url
    ctx.file_total_size = int(res.get("total_size") or res.get("size") or 0)
    if ctx.file_total_size <= 0:
        ctx.info_error = i18n.t("error.no_content_length")
        return
    ctx.chunk_task_list = core.split_file_chunks(
        ctx.file_total_size, ctx.jobs, ctx.chunk_size)
    ctx.total_downloaded = sum(t.downloaded for t in ctx.chunk_task_list)


def _probe_forced_curl(core, ctx) -> None:
    """强制用 curl 探测文件大小并建分片，跳过 requests 双路探测。"""
    if not core.curl_available():
        ctx.info_error = i18n.t("error.curl_missing")
        return
    res = core.curl_probe(ctx.url, ctx.headers, ctx.disable_ssl)
    if res.get("ok"):
        res["use_curl"] = True
        res["total_size"] = res.get("total_size") or 0
    _apply_probe_result(core, ctx, res)


def _probe_forced_requests(core, ctx) -> None:
    """强制仅用 requests 探测，不触发 curl 兜底（对应 --backend requests）。"""
    box = {"status": 0, "final_url": "", "size": 0, "error": "", "done": False}
    ev = threading.Event()
    core._probe_with_requests(ctx.url, ctx.headers, ctx.disable_ssl, box, ev)
    res = {"ok": False, "status": int(box.get("status") or 0), "final_url": "",
           "total_size": 0, "use_curl": False, "error": ""}
    if box.get("done") and not box.get("error"):
        if int(box.get("status") or 0) < 400:
            res["ok"] = True
            res["final_url"] = box.get("final_url", "")
            res["total_size"] = int(box.get("size") or 0)
    else:
        res["error"] = box.get("error") or ""
    _apply_probe_result(core, ctx, res)


def _parse_headers(header_list, header_json):
    headers = {}
    if header_json:
        try:
            headers.update(json.loads(header_json))
        except Exception:
            print(paint("invalid --header-json", Ansi.RED))
    for item in header_list or []:
        if ":" in item:
            k, v = item.split(":", 1)
            headers[k.strip()] = v.strip()
    return headers


def run_download(args, resume_path: str = "") -> int:
    import NewDownloadCore as core

    # 首选项（AppConfig）作为默认值，命令行显式传参优先
    try:
        import AppConfig
        defaults = AppConfig.download_defaults()
        default_dir = AppConfig.get_download_dir()
    except Exception:
        defaults = {"jobs": 16, "chunk_size": 10.0, "cache": 32.0,
                    "no_ssl_check": False, "speed_unit": "MB/s",
                    "timeout": 60.0}
        default_dir = os.getcwd()

    url = args.url
    save_path = os.path.abspath(os.path.expanduser(
        args.output or default_dir or os.getcwd()))
    filename = _resolve_filename(url, args.filename)
    jobs = max(1, min(int(args.jobs if args.jobs is not None
                          else defaults["jobs"]), 128))
    chunk_mb = float(args.chunk_size if args.chunk_size is not None
                     else defaults["chunk_size"])
    chunk_size = max(1, int(chunk_mb * 1024 * 1024))
    cache = float(args.cache if args.cache is not None else defaults["cache"])
    timeout = float(args.timeout if args.timeout is not None
                    else defaults.get("timeout", 60.0))
    speed_unit = args.speed_unit or defaults["speed_unit"]
    no_ssl = bool(args.no_ssl_check) or bool(defaults["no_ssl_check"])
    limit_bps = float(args.limit) * 1024 if args.limit else 0.0
    # 首选项里保存的自定义请求头先垫底，命令行 -H 优先覆盖同名项
    preset_headers = {}
    try:
        import AppConfig
        raw = AppConfig.load().get("dl_headers", [])
        if isinstance(raw, dict):
            preset_headers = {str(k): str(v) for k, v in raw.items()}
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    preset_headers[str(item[0])] = str(item[1])
    except Exception:
        preset_headers = {}
    cli_headers = _parse_headers(getattr(args, "header", None),
                                 getattr(args, "header_json", None))
    headers = {**preset_headers, **cli_headers}
    run_after = {"open": "Open", "shutdown": "Shutdown"}.get(
        (args.run or "").lower())

    try:
        os.makedirs(save_path, exist_ok=True)
    except Exception as e:
        print(paint(i18n.t("error.path_create_failed", path=save_path), Ansi.RED))
        return 2

    # 与 GUI 的 Download() 一致：叠加站点式默认请求头（UA/Cookie 等），
    # 命令行显式传入的 headers 优先级最高。
    try:
        import SiteHeaders
        headers = SiteHeaders.resolve_headers(url, filename, save_path, headers)
    except Exception:
        pass

    ctx = core.init_download_context(
        url=url, save_path=save_path, filename=filename, jobs=jobs,
        chunk_size=chunk_size, headers=headers, cache_mb=cache,
        run_after=run_after, disable_ssl=no_ssl,
        completion_callback=None, speed_unit=speed_unit,
        resume_json_path=resume_path or "",
    )
    ctx.speed_limit_bps = limit_bps

    state = {
        "filename": filename,
        "total": 0,
        "done": 0,
        "pct": 0,
        "chunks": {},
        "speed_str": "",
        "speed_bps": 0.0,
        "remain": "",
        "elapsed": "00:00:00",
        "status": "",
        "logs": [],
        "paused": False,
    }
    ctx.ui_frame = _CliFrame(state)

    import wx as _wx
    sync = _SyncCallAfter()
    sync.install(_wx)

    backend = (getattr(args, "backend", "auto") or "auto").lower()
    # 先取文件大小以展示分块信息（后台探测 + 旋转动画 + curl 兜底）
    if backend == "curl":
        _probe_forced_curl(core, ctx)
    elif backend == "requests":
        _probe_forced_requests(core, ctx)
    else:
        _probe_with_progress(core, ctx, state, timeout=timeout)
    use_curl = bool(getattr(ctx, "use_curl", False))
    if not ctx.file_total_size:
        sync.restore(_wx)
        reason = ctx.info_error or i18n.t("error.no_content_length")
        print(paint(i18n.t("error.fetch_failed", reason=reason), Ansi.RED))
        if not core.curl_available():
            print("  " + paint(i18n.t("error.curl_missing"), Ansi.YELLOW))
            print("  " + paint(i18n.t("error.curl_missing_hint"), Ansi.DIM))
        return 3

    target_path = os.path.join(save_path, filename)
    disk_ok, disk_free, disk_required = core.check_disk_space(
        target_path, ctx.file_total_size, core.get_existing_file_size(target_path))
    if not disk_ok:
        sync.restore(_wx)
        print(paint(i18n.t("error.disk_space", free=_fmt_size(disk_free),
                           need=_fmt_size(disk_required)), Ansi.RED))
        return 4

    chunks = len(ctx.chunk_task_list)
    record_uuid = _history_start(url, filename, save_path, ctx.file_total_size)
    print()
    print(paint(i18n.t("info.header"), Ansi.BOLD, Ansi.MAGENTA))
    _info(i18n.t("info.url"), paint(url, Ansi.BLUE))
    _info(i18n.t("info.filename"), filename)
    _info(i18n.t("info.save_path"), save_path)
    _info(i18n.t("info.total_size"), _fmt_size(ctx.file_total_size))
    _info(i18n.t("info.chunk_size"), _fmt_size(chunk_size))
    _info(i18n.t("info.chunks"), str(chunks))
    _info(i18n.t("info.threads"), str(jobs))
    _info(i18n.t("info.buffer"), f"{cache:g} MiB")
    _info(i18n.t("info.limit"),
          "unlimited" if not limit_bps else f"{limit_bps / 1024:.0f} KB/s")
    _info(i18n.t("info.supported"), paint("yes", Ansi.GREEN))
    backend = (i18n.t("info.backend_curl") if use_curl
               else i18n.t("info.backend_requests"))
    _info(i18n.t("info.backend"),
          paint(backend, Ansi.YELLOW if use_curl else Ansi.GREEN))
    print()

    state.update({
        "total": ctx.file_total_size,
        "backend": "curl" if use_curl else "requests",
        "chunks": {t.chunk_idx: 0 for t in ctx.chunk_task_list},
    })
    state["done"] = ctx.total_downloaded
    state["chunks"] = {
        t.chunk_idx: (100 if t.finished else min(100, int(
            t.downloaded / max(1, t.end_byte - t.start_byte + 1) * 100)))
        for t in ctx.chunk_task_list
    }

    as_json = bool(getattr(args, "json", False))
    use_tty = sys.stdout.isatty() and not as_json
    renderer = _Renderer(state, use_tty, as_json)
    renderer._printed_logs = len(state["logs"])

    real_stdout = sys.stdout
    if use_tty:
        tty_writer = _TtyWriter(real_stdout)
        sys.stdout = tty_writer
        renderer.writer = tty_writer

    result = {"ok": False, "err": None}

    def _engine():
        try:
            core.schedule_download_task(ctx)
            result["ok"] = ctx.download_completed
        except Exception as e:
            result["err"] = str(e)

    worker = threading.Thread(target=_engine, daemon=True)
    worker.start()

    start = time.time()
    interrupted = {"flag": False}
    renderer.hide_cursor()
    try:
        while worker.is_alive():
            state["done"] = ctx.total_downloaded
            renderer.sample_speed(ctx.total_downloaded)
            state["speed_str"] = core.format_speed(
                state["speed_bps"], speed_unit)
            state["remain"] = _fmt_eta(_eta_from(state, ctx))
            renderer.render()
            time.sleep(0.3)
    except KeyboardInterrupt:
        interrupted["flag"] = True
        ctx.stop_event.set()
        core.kill_active_curls(ctx)
        _wait_engine_stop(worker, renderer, state)
    finally:
        while worker.is_alive():
            worker.join(timeout=0.2)
        sync.restore(_wx)
        if use_tty:
            renderer.clear_progress()
            sys.stdout = real_stdout

    state["done"] = ctx.total_downloaded
    renderer.render(final=True)

    print()
    if interrupted["flag"] and not ctx.download_completed:
        renderer.finish_line()
        print(paint(i18n.t("done.aborted"), Ansi.YELLOW))
        if ctx.ndf_progress_path and os.path.exists(ctx.ndf_progress_path):
            print("  " + paint(i18n.t("log.pause_saved"), Ansi.DIM))
        return 130

    if result["err"]:
        _history_finish(record_uuid, "失败", ctx)
        print(paint(i18n.t("done.failed", reason=result["err"]), Ansi.RED))
        return 5 if "磁盘可用空间不足" in str(result["err"]) else 1

    if ctx.download_completed:
        _history_finish(record_uuid, "已完成", ctx)
        path = os.path.join(save_path, filename)
        elapsed = time.time() - start
        avg = ctx.file_total_size / elapsed if elapsed > 0 else 0
        renderer.finish_line()
        print(paint(i18n.t("done.success", path=path), Ansi.BOLD, Ansi.GREEN))
        _info(i18n.t("done.time_cost"), _fmt_eta(elapsed))
        _info(i18n.t("done.avg_speed"), core.format_speed(avg, speed_unit))
        return 0

    if ctx.pause_requested:
        _history_finish(record_uuid, "已中断", ctx)
        renderer.finish_line()
        print(paint(i18n.t("done.aborted"), Ansi.YELLOW))
        return 130

    if ctx.disk_space_error:
        _history_finish(record_uuid, "失败", ctx)
        renderer.finish_line()
        print(paint(ctx.disk_space_error, Ansi.RED))
        if ctx.ndf_progress_path and os.path.exists(ctx.ndf_progress_path):
            print("  " + paint(i18n.t("log.pause_saved"), Ansi.DIM))
        return 5

    _history_finish(record_uuid, "失败", ctx)
    renderer.finish_line()
    print(paint(i18n.t("done.failed", reason=state["status"]), Ansi.RED))
    return 1


# -------------------------- 下载记录 --------------------------
def _history_start(url, filename, save_path, total_size) -> str:
    try:
        import DownloadHistory
        rec = DownloadHistory.add_record(
            url, filename, save_path, status="下载中",
            file_size=int(total_size or 0), source="cli")
        return rec.get("uuid", "")
    except Exception:
        return ""


def _history_finish(record_uuid, status, ctx) -> None:
    if not record_uuid:
        return
    try:
        import DownloadHistory
        DownloadHistory.update_record(record_uuid, status=status)
    except Exception:
        pass


def _approx_speed(ctx, start):
    elapsed = time.time() - start
    if elapsed <= 0:
        return 0.0
    return ctx.total_downloaded / elapsed


def _eta_from(state, ctx):
    speed = state.get("speed_bps") or 0.0
    total = state.get("total") or 0
    done = state.get("done") or 0
    if speed <= 0 or total <= 0:
        return None
    return (total - done) / speed


def _wait_engine_stop(worker, renderer, state):
    """等待引擎线程保存断点并退出；期间保持渲染，再按一次 Ctrl+C 则放弃等待。"""
    if not renderer.as_json:
        try:
            renderer.clear_progress()
            print(paint(i18n.t("log.pause_saved"), Ansi.YELLOW), flush=True)
        except Exception:
            pass
    while worker.is_alive():
        try:
            worker.join(timeout=0.3)
        except KeyboardInterrupt:
            break
