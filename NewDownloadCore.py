# Copyright (c) 2023-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import wx
import threading
import requests
import os
import time
import random
import string
import gc
import json
import zipfile
import shutil
from io import BytesIO
import urllib3
import ssl
from queue import Queue
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any

# 网络警告屏蔽
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

# 全局常量
DEFAULT_TIMEOUT = 240
DEFAULT_RETRY = 10
GRID_CELL_SIZE = 12
NDF_SUFFIX = ".ndf"
PROGRESS_JSON_NAME = "download_progress.json"

# -------------------------- 数据结构定义 --------------------------
@dataclass
class ChunkTask:
    """分片任务结构体（调度池单元）"""
    chunk_idx: int                  # 分片索引
    start_byte: int                 # 分片起始偏移
    end_byte: int                   # 分片结束偏移
    finished: bool = False          # 是否下载完成
    downloaded: int = 0             # 当前分片已下载字节(内存统计)
    task_buffer: Optional[BytesIO] = None  # 分片独立内存缓冲
    chunk_lock: Optional[threading.Lock] = None  # 分片专属写入锁

@dataclass
class DownloadCtx:
    """全局下载上下文（跨线程共享数据，锁保护）"""
    url: str
    save_path: str
    filename: str
    jobs: int
    chunk_size: int
    headers: Dict[str, str]
    cache_mb: float
    run_after: Optional[str]
    disable_ssl: bool
    completion_callback: Optional[Any]
    file_total_size: int = 0
    total_downloaded: int = 0
    chunk_task_list: Optional[List[ChunkTask]] = None
    task_queue: Optional[Queue] = None
    stop_event: Optional[threading.Event] = None
    global_lock: Optional[threading.Lock] = None
    file_obj: Optional[Any] = None   # 标准文件对象，替代win32句柄
    last_speed_calc_ts: float = 0.0
    last_total_bytes: int = 0
    start_ts: float = 0.0
    ndf_progress_path: str = ""
    ui_frame: Optional[Any] = None

# -------------------------- 底层纯Python文件工具（无任何Windows API） --------------------------
def pre_allocate_file(file_path: str, total_size: int, resume: bool = False):
    """纯Python预分配完整占位文件，buffering=0禁用缓冲，fsync强制落盘"""
    mode = "r+b" if resume else "wb"
    f = open(file_path, mode, buffering=0)
    if not resume and total_size > 0:
        f.seek(total_size - 1)
        f.write(b"\x00")
        f.flush()
        os.fsync(f.fileno())
    return f

def chunk_seek_write(file_obj, offset: int, data: bytes) -> bool:
    """文件指定偏移写入，强制刷盘防止缓存丢失"""
    if not file_obj or len(data) == 0:
        return False
    try:
        file_obj.seek(offset, os.SEEK_SET)
        write_len = file_obj.write(data)
        file_obj.flush()
        os.fsync(file_obj.fileno())
        return write_len == len(data)
    except Exception:
        return False

def flush_single_chunk_buffer(ctx: DownloadCtx, task: ChunkTask) -> int:
    """刷新单个分片私有缓冲，分片锁隔离并发写入"""
    if task.task_buffer is None or task.task_buffer.getbuffer().nbytes == 0:
        return 0
    with task.chunk_lock:
        data = task.task_buffer.getvalue()
        write_offset = task.start_byte + (task.downloaded - len(data))
        retry = 3
        write_ok = False
        while retry > 0 and not write_ok:
            write_ok = chunk_seek_write(ctx.file_obj, write_offset, data)
            if not write_ok:
                retry -= 1
                time.sleep(0.05)
        task.task_buffer.seek(0)
        task.task_buffer.truncate()
        return len(data)

def safe_delete_file(filepath: str, max_retry: int = 5) -> bool:
    """安全删除文件，捕获占用异常重试"""
    for i in range(max_retry):
        if not os.path.exists(filepath):
            return True
        try:
            gc.collect()
            os.remove(filepath)
            return True
        except Exception:
            if i < max_retry - 1:
                time.sleep(1)
                continue
            return False
    return False

# -------------------------- 断点续传JSON & NDF导入导出 --------------------------
def dump_progress_json(ctx: DownloadCtx) -> None:
    progress_data = {
        "url": ctx.url,
        "save_path": ctx.save_path,
        "filename": ctx.filename,
        "jobs": ctx.jobs,
        "chunk_size": ctx.chunk_size,
        "file_total_size": ctx.file_total_size,
        "total_downloaded": ctx.total_downloaded,
        "chunks": [
            {
                "idx": t.chunk_idx,
                "start": t.start_byte,
                "end": t.end_byte,
                "finished": t.finished,
                "downloaded": t.downloaded
            } for t in ctx.chunk_task_list
        ]
    }
    with open(ctx.ndf_progress_path, "w", encoding="utf-8") as f:
        json.dump(progress_data, f, ensure_ascii=False, indent=2)

def load_progress_json(json_path: str) -> Dict[str, Any]:
    if not os.path.exists(json_path):
        return {}
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def export_ndf(ctx: DownloadCtx, export_save_path: str) -> str:
    ndf_full_path = os.path.join(export_save_path, f"{ctx.filename}{NDF_SUFFIX}")
    target_file = os.path.join(ctx.save_path, ctx.filename)
    with zipfile.ZipFile(ndf_full_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(target_file):
            zf.write(target_file, arcname=ctx.filename)
        if os.path.exists(ctx.ndf_progress_path):
            zf.write(ctx.ndf_progress_path, arcname=PROGRESS_JSON_NAME)
    return ndf_full_path

def import_ndf(ndf_file_path: str, target_save_dir: str) -> Tuple[bool, Dict[str, Any]]:
    if not ndf_file_path.endswith(NDF_SUFFIX) or not os.path.exists(ndf_file_path):
        return False, {}
    os.makedirs(target_save_dir, exist_ok=True)
    with zipfile.ZipFile(ndf_file_path, "r") as zf:
        zf.extractall(target_save_dir)
    json_path = os.path.join(target_save_dir, PROGRESS_JSON_NAME)
    progress_data = load_progress_json(json_path)
    return True, progress_data

# -------------------------- 分片拆分函数（无递归死循环） --------------------------
def split_file_chunks(total_size: int, jobs: int, single_chunk_bytes: int) -> List[ChunkTask]:
    chunk_list = []
    if total_size <= 0:
        return chunk_list
    MIN_CHUNK_BYTE = 64 * 1024
    offset = 0
    idx = 0
    real_chunk_size = max(single_chunk_bytes, MIN_CHUNK_BYTE)

    while offset < total_size:
        end = min(offset + real_chunk_size - 1, total_size - 1)
        chunk_list.append(ChunkTask(
            chunk_idx=idx,
            start_byte=offset,
            end_byte=end,
            chunk_lock=threading.Lock()
        ))
        offset = end + 1
        idx += 1

    max_try = 10
    try_cnt = 0
    while len(chunk_list) < jobs and try_cnt < max_try:
        try_cnt += 1
        real_chunk_size *= 2
        chunk_list.clear()
        offset = 0
        idx = 0
        while offset < total_size:
            end = min(offset + real_chunk_size - 1, total_size - 1)
            chunk_list.append(ChunkTask(
                chunk_idx=idx,
                start_byte=offset,
                end_byte=end,
                chunk_lock=threading.Lock()
            ))
            offset = end + 1
            idx += 1
    return chunk_list

# -------------------------- 网络分片工作线程 --------------------------
def single_chunk_worker(ctx: DownloadCtx) -> None:
    max_cache_bytes = int(ctx.cache_mb * 1024 * 1024)
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=ctx.jobs, pool_maxsize=ctx.jobs)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    while not ctx.stop_event.is_set():
        try:
            task: ChunkTask = ctx.task_queue.get(timeout=1)
        except Exception:
            continue
        if task.finished:
            ctx.task_queue.task_done()
            continue
        if task.task_buffer is None:
            task.task_buffer = BytesIO()
        current_offset = task.start_byte + task.downloaded
        retry_times = 0
        chunk_finish_flag = False
        total_chunk_len = task.end_byte - task.start_byte + 1

        while retry_times < DEFAULT_RETRY and not ctx.stop_event.is_set() and not chunk_finish_flag:
            try:
                range_header = {"Range": f"bytes={current_offset}-{task.end_byte}"}
                req_headers = {**ctx.headers, **range_header}
                resp = session.get(
                    ctx.url,
                    headers=req_headers,
                    stream=True,
                    timeout=(DEFAULT_TIMEOUT, DEFAULT_TIMEOUT),
                    verify=not ctx.disable_ssl
                )
                resp.raise_for_status()
                for raw_data in resp.iter_content(chunk_size=65536):
                    if ctx.stop_event.is_set():
                        flush_single_chunk_buffer(ctx, task)
                        break
                    if not raw_data:
                        continue
                    task.task_buffer.write(raw_data)
                    data_len = len(raw_data)
                    task.downloaded += data_len
                    if task.task_buffer.getbuffer().nbytes >= max_cache_bytes:
                        flush_single_chunk_buffer(ctx, task)
                        with ctx.global_lock:
                            ctx.total_downloaded += data_len
                    pct = min(int((task.downloaded / total_chunk_len) * 100), 100)
                    ui_push_chunk_progress(ctx, task.chunk_idx, task.downloaded, total_chunk_len)
                    current_offset = task.start_byte + task.downloaded
                    if task.downloaded >= total_chunk_len:
                        chunk_finish_flag = True
                        break
            except Exception as e:
                retry_times += 1
                err_msg = f"分片{task.chunk_idx}异常 重试{retry_times}/{DEFAULT_RETRY}: {str(e)}"
                ui_push_log(ctx, err_msg)
                time.sleep(2)
        write_len = flush_single_chunk_buffer(ctx, task)
        with ctx.global_lock:
            ctx.total_downloaded += write_len
        if task.downloaded >= total_chunk_len:
            with ctx.global_lock:
                task.finished = True
            ui_push_log(ctx, f"分片{task.chunk_idx}数据全部落盘，下载完成")
            dump_progress_json(ctx)
        ctx.task_queue.task_done()
    session.close()

# -------------------------- UI异步推送纯函数 --------------------------
def ui_push_global_status(ctx: DownloadCtx, msg: str) -> None:
    if ctx.stop_event.is_set() or ctx.ui_frame is None:
        return
    wx.CallAfter(ctx.ui_frame.set_status_text, msg)

def ui_push_log(ctx: DownloadCtx, msg: str) -> None:
    if ctx.stop_event.is_set() or ctx.ui_frame is None:
        return
    wx.CallAfter(ctx.ui_frame.append_log, msg)

def ui_push_chunk_progress(ctx: DownloadCtx, chunk_idx: int, downloaded: int, chunk_total: int) -> None:
    if ctx.stop_event.is_set() or ctx.ui_frame is None:
        return
    pct = min(int((downloaded / chunk_total) * 100), 100)
    wx.CallAfter(ctx.ui_frame.update_grid_cell, chunk_idx, pct)

def ui_refresh_speed_panel(ctx: DownloadCtx) -> None:
    if ctx.stop_event.is_set() or ctx.ui_frame is None or ctx.file_total_size == 0:
        return
    now_ts = time.time()
    delta_ts = now_ts - ctx.last_speed_calc_ts
    if delta_ts < 0.5:
        return
    with ctx.global_lock:
        delta_bytes = ctx.total_downloaded - ctx.last_total_bytes
        ctx.last_total_bytes = ctx.total_downloaded
        ctx.last_speed_calc_ts = now_ts
    speed_bps = delta_bytes / delta_ts
    if speed_bps < 1024:
        speed_str = f"{speed_bps:.2f} B/s"
    elif speed_bps < 1024 ** 2:
        speed_str = f"{speed_bps / 1024:.2f} KB/s"
    else:
        speed_str = f"{speed_bps / (1024**2):.2f} MB/s"
    global_pct = int((ctx.total_downloaded / ctx.file_total_size) * 100)
    elapsed_sec = now_ts - ctx.start_ts
    h, rem = divmod(elapsed_sec, 3600)
    m, s = divmod(rem, 60)
    time_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
    if speed_bps > 0:
        remain_bytes = ctx.file_total_size - ctx.total_downloaded
        remain_sec = remain_bytes / speed_bps
        rh, rrem = divmod(remain_sec, 3600)
        rm, rs = divmod(rrem, 60)
        remain_str = f"{int(rh):02d}:{int(rm):02d}:{int(rs):02d}"
    else:
        remain_str = "计算中"
    wx.CallAfter(ctx.ui_frame.refresh_speed_info, speed_str, time_str, remain_str, global_pct)

# -------------------------- 顶层调度核心函数 --------------------------
def schedule_download_task(ctx: DownloadCtx) -> None:
    ctx.start_ts = time.time()
    ctx.last_speed_calc_ts = ctx.start_ts
    ctx.task_queue = Queue(maxsize=len(ctx.chunk_task_list))
    if ctx.file_total_size <= 0:
        ui_push_global_status(ctx, "错误：未获取到文件总大小，无法分片下载")
        ui_push_log(ctx, "服务器未返回content-length，不支持多线程下载")
        if ctx.completion_callback:
            wx.CallAfter(ctx.completion_callback, False, 0)
        return
    for task in ctx.chunk_task_list:
        ctx.task_queue.put(task)
    target_full_path = os.path.join(ctx.save_path, ctx.filename)
    has_resume_data = sum(t.downloaded for t in ctx.chunk_task_list) > 0
    try:
        ctx.file_obj = pre_allocate_file(target_full_path, ctx.file_total_size, resume=has_resume_data)
    except Exception as e:
        ui_push_global_status(ctx, f"文件创建失败: {str(e)}")
        ui_push_log(ctx, f"目标路径：{target_full_path}")
        if ctx.completion_callback:
            wx.CallAfter(ctx.completion_callback, False, 0)
        return
    ui_push_global_status(ctx, f"已预分配文件，总大小：{ctx.file_total_size / 1024 / 1024:.2f}MB")
    worker_threads = []
    for _ in range(ctx.jobs):
        t = threading.Thread(target=single_chunk_worker, args=(ctx,), daemon=True)
        worker_threads.append(t)
        t.start()
    while not ctx.stop_event.is_set():
        ui_refresh_speed_panel(ctx)
        all_done = all(t.finished for t in ctx.chunk_task_list)
        if all_done:
            break
        time.sleep(0.3)
    ctx.task_queue.join()
    for t in worker_threads:
        if t.is_alive():
            t.join(timeout=2)
    if ctx.file_obj is not None:
        ctx.file_obj.flush()
        os.fsync(ctx.file_obj.fileno())
        ctx.file_obj.close()
        ctx.file_obj = None
    dump_progress_json(ctx)
    final_file_size = os.path.getsize(target_full_path) if os.path.exists(target_full_path) else 0
    all_chunk_finished = all(t.finished for t in ctx.chunk_task_list)
    file_complete = (final_file_size == ctx.file_total_size)
    binary_valid = True
    if file_complete:
        try:
            with open(target_full_path, "rb") as f:
                head = f.read(1024)
                f.seek(-1024, os.SEEK_END)
                tail = f.read(1024)
                if all(b == 0 for b in head) and all(b == 0 for b in tail):
                    binary_valid = False
        except Exception:
            binary_valid = False
    time_cost_sec = time.time() - ctx.start_ts
    h, rem = divmod(time_cost_sec, 3600)
    m, s = divmod(rem, 60)
    time_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
    if all_chunk_finished and file_complete and binary_valid and not ctx.stop_event.is_set():
        ui_push_global_status(ctx, "全部分片下载完成，磁盘文件校验通过")
        ui_push_log(ctx, f"下载完成，文件完整，大小：{final_file_size}字节")
        if ctx.run_after == "Open":
            os.startfile(target_full_path)
        elif ctx.run_after == "Shutdown":
            ui_push_log(ctx, "10秒后执行关机，可关闭窗口取消")
            time.sleep(10)
            os.system("shutdown /s /t 0")
        if ctx.completion_callback:
            wx.CallAfter(ctx.completion_callback, True, final_file_size)
        def show_complete_dialog():
            dlg = DownloadCompleteDialog(ctx.ui_frame, ctx, final_file_size, time_str)
            dlg.ShowModal()
        wx.CallAfter(show_complete_dialog)
    elif not ctx.stop_event.is_set():
        if not file_complete or not binary_valid:
            ui_push_global_status(ctx, "警告：分片显示完成，但磁盘文件数据缺失/损坏！")
            ui_push_log(ctx, f"内存统计总字节:{ctx.total_downloaded}，磁盘真实大小:{final_file_size}，原始文件大小:{ctx.file_total_size}")
            wx.CallAfter(wx.MessageBox, "文件分片显示完成，但磁盘文件存在空洞/数据损坏，请重新下载！", "文件校验失败", wx.ICON_ERROR)
        else:
            ui_push_global_status(ctx, "下载中断，存在未完成分片，支持续传")
            ui_push_log(ctx, f"已保存断点文件：{ctx.ndf_progress_path}")
        if ctx.completion_callback:
            wx.CallAfter(ctx.completion_callback, False, final_file_size)
    ui_push_global_status(ctx, "调度线程退出")

# -------------------------- 初始化下载上下文 --------------------------
def init_download_context(
    url: str,
    save_path: str,
    filename: str,
    jobs: int,
    chunk_size: int,
    headers: dict,
    cache_mb: float,
    run_after: str = None,
    disable_ssl: bool = False,
    completion_callback = None,
    resume_json_path: str = ""
) -> DownloadCtx:
    ctx = DownloadCtx(
        url=url,
        save_path=save_path,
        filename=filename,
        jobs=jobs,
        chunk_size=chunk_size,
        headers=headers if headers else {},
        cache_mb=cache_mb,
        run_after=run_after,
        disable_ssl=disable_ssl,
        completion_callback=completion_callback,
        stop_event=threading.Event(),
        global_lock=threading.Lock()
    )
    ctx.ndf_progress_path = os.path.join(save_path, f"{filename}_{PROGRESS_JSON_NAME}")
    resume_data = {}
    if resume_json_path and os.path.exists(resume_json_path):
        resume_data = load_progress_json(resume_json_path)
    try:
        head_resp = requests.head(url, headers=ctx.headers, timeout=DEFAULT_TIMEOUT, verify=not disable_ssl)
        ctx.file_total_size = int(head_resp.headers.get("content-length", 0))
        if ctx.file_total_size <= 0:
            with requests.get(url, headers=ctx.headers, stream=True, timeout=DEFAULT_TIMEOUT, verify=not disable_ssl) as r:
                ctx.file_total_size = int(r.headers.get("content-length", 0))
    except Exception:
        ctx.file_total_size = resume_data.get("file_total_size", 0)
    if resume_data and "chunks" in resume_data:
        ctx.chunk_task_list = [
            ChunkTask(
                chunk_idx=c["idx"],
                start_byte=c["start"],
                end_byte=c["end"],
                finished=c["finished"],
                downloaded=c["downloaded"],
                chunk_lock=threading.Lock()
            ) for c in resume_data["chunks"]
        ]
    else:
        ctx.chunk_task_list = split_file_chunks(ctx.file_total_size, jobs, chunk_size)
    ctx.last_speed_calc_ts = 0.0
    ctx.last_total_bytes = 0
    ctx.total_downloaded = sum(t.downloaded for t in ctx.chunk_task_list)
    ctx.file_obj = None
    return ctx

# -------------------------- 下载完成弹窗UI --------------------------
class DownloadCompleteDialog(wx.Dialog):
    def __init__(self, parent, ctx: DownloadCtx, total_bytes: int, cost_time: str):
        super().__init__(parent, title="下载完成", size=(520, 260))
        self.ctx = ctx
        self.total_bytes = total_bytes
        self.cost_time = cost_time
        self.target_file = os.path.join(ctx.save_path, ctx.filename)
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        title = wx.StaticText(panel, label=f"文件 {ctx.filename} 下载完成！")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        vbox.Add(title, flag=wx.ALL | wx.ALIGN_CENTER, border=10)
        size_mb = total_bytes / 1024 / 1024
        info_text = wx.StaticText(panel, label=f"文件大小：{size_mb:.2f} MB\n总耗时：{cost_time}")
        vbox.Add(info_text, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=12)
        btn_box = wx.BoxSizer(wx.HORIZONTAL)
        btn_open_file = wx.Button(panel, label="打开文件")
        btn_open_dir = wx.Button(panel, label="打开保存目录")
        btn_export = wx.Button(panel, label="导出.ndf")
        btn_close = wx.Button(panel, label="关闭")
        btn_open_file.Bind(wx.EVT_BUTTON, self.on_open_file)
        btn_open_dir.Bind(wx.EVT_BUTTON, self.on_open_folder)
        btn_export.Bind(wx.EVT_BUTTON, self.on_export_ndf)
        btn_close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        btn_box.Add(btn_open_file, proportion=0, flag=wx.RIGHT, border=6)
        btn_box.Add(btn_open_dir, proportion=0, flag=wx.RIGHT, border=6)
        btn_box.Add(btn_export, proportion=0, flag=wx.RIGHT, border=6)
        btn_box.Add(btn_close, proportion=0)
        vbox.Add(btn_box, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=10)
        panel.SetSizer(vbox)
        self.Centre()
    def on_open_file(self, evt):
        if os.path.exists(self.target_file):
            os.startfile(self.target_file)
        else:
            wx.MessageBox("文件不存在", "提示", wx.OK)
    def on_open_folder(self, evt):
        os.startfile(self.ctx.save_path)
    def on_export_ndf(self, evt):
        dlg = wx.DirDialog(self, "选择.ndf导出目录", self.ctx.save_path)
        if dlg.ShowModal() == wx.ID_OK:
            path = export_ndf(self.ctx, dlg.GetPath())
            wx.MessageBox(f"导出成功：{path}", "导出完成", wx.OK)
        dlg.Destroy()

# -------------------------- 下载主窗口UI（无业务逻辑，仅渲染） --------------------------
class DownloadFrame(wx.Frame):
    def __init__(self, ctx: DownloadCtx):
        super().__init__(None, title=f"多协程下载器 - {ctx.filename}", size=(780, 680))
        self.ctx = ctx
        self.ctx.ui_frame = self
        self.grid_cell_pct: List[int] = [0] * len(ctx.chunk_task_list)
        self.panel = wx.Panel(self)
        self.offscreen_bmp: Optional[wx.Bitmap] = None
        self.grid_col_count = 1
        self.cell_w = GRID_CELL_SIZE
        self.cell_h = GRID_CELL_SIZE
        self.grid_w = 0
        self.grid_h = 0
        self.create_ui_layout()
        self.Bind(wx.EVT_CLOSE, self.on_window_close)
        self.start_schedule_thread()
        self.Centre()
        self.Show()
    def create_ui_layout(self):
        main_vbox = wx.BoxSizer(wx.VERTICAL)
        top_box = wx.BoxSizer(wx.HORIZONTAL)
        self.global_gauge = wx.Gauge(self.panel, range=100, size=(-1, 22))
        top_box.Add(self.global_gauge, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=10)
        self.status_label = wx.StaticText(self.panel, label="准备初始化下载...")
        top_box.Add(self.status_label, proportion=0)
        main_vbox.Add(top_box, flag=wx.EXPAND | wx.ALL, border=8)
        speed_box = wx.BoxSizer(wx.HORIZONTAL)
        self.speed_text = wx.StaticText(self.panel, label="总速度: 0 B/s")
        self.elapsed_text = wx.StaticText(self.panel, label="已耗时: 00:00:00")
        self.remain_text = wx.StaticText(self.panel, label="预计剩余: --")
        speed_box.Add(self.speed_text, flag=wx.RIGHT, border=15)
        speed_box.Add(self.elapsed_text, flag=wx.RIGHT, border=15)
        speed_box.Add(self.remain_text)
        main_vbox.Add(speed_box, flag=wx.LEFT | wx.BOTTOM, border=8)
        self.grid_scroll = wx.ScrolledWindow(self.panel)
        self.grid_scroll.SetScrollRate(GRID_CELL_SIZE, GRID_CELL_SIZE)
        grid_inner_sizer = wx.BoxSizer(wx.VERTICAL)
        self.grid_canvas = wx.Panel(self.grid_scroll, size=(720, 220))
        self.grid_canvas.Bind(wx.EVT_PAINT, self.on_grid_paint)
        self.grid_canvas.Bind(wx.EVT_SIZE, lambda e: setattr(self, "offscreen_bmp", None))
        grid_inner_sizer.Add(self.grid_canvas, proportion=1, flag=wx.EXPAND)
        self.grid_scroll.SetSizer(grid_inner_sizer)
        main_vbox.Add(self.grid_scroll, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        self.log_ctrl = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 120))
        main_vbox.Add(self.log_ctrl, proportion=0, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=5)
        btn_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_pause = wx.Button(self.panel, label="暂停/终止")
        self.btn_export = wx.Button(self.panel, label="导出.ndf")
        self.btn_export.Bind(wx.EVT_BUTTON, self.on_export_ndf_click)
        btn_box.Add(self.btn_pause, flag=wx.RIGHT, border=10)
        btn_box.Add(self.btn_export)
        main_vbox.Add(btn_box, flag=wx.ALL | wx.ALIGN_CENTER, border=8)
        self.panel.SetSizer(main_vbox)
    def start_schedule_thread(self):
        schedule_t = threading.Thread(target=schedule_download_task, args=(self.ctx,), daemon=True)
        schedule_t.start()
    def set_status_text(self, msg: str):
        self.status_label.SetLabel(msg)
        self.panel.Layout()
    def append_log(self, msg: str):
        self.log_ctrl.AppendText(f"{time.strftime('%H:%M:%S')} | {msg}\n")
    def update_grid_cell(self, chunk_idx: int, pct: int):
        if chunk_idx >= len(self.grid_cell_pct):
            return
        old_val = self.grid_cell_pct[chunk_idx]
        if old_val == pct:
            return
        self.grid_cell_pct[chunk_idx] = pct
        col_cnt = max(1, self.grid_col_count)
        col = chunk_idx % col_cnt
        row = chunk_idx // col_cnt
        x = col * self.cell_w
        y = row * self.cell_h
        rect = wx.Rect(x, y, self.cell_w, self.cell_h)
        self.grid_canvas.RefreshRect(rect)
    def on_grid_paint(self, event):
        dc = wx.PaintDC(self.grid_canvas)
        client_w, client_h = self.grid_canvas.GetClientSize()
        self.grid_col_count = max(1, client_w // self.cell_w)
        total_cols = self.grid_col_count
        total_rows = (len(self.grid_cell_pct) + total_cols - 1) // total_cols
        self.grid_w = total_cols * self.cell_w
        self.grid_h = total_rows * self.cell_h
        if self.offscreen_bmp is None or self.offscreen_bmp.GetWidth() != self.grid_w or self.offscreen_bmp.GetHeight() != self.grid_h:
            self.offscreen_bmp = wx.Bitmap(self.grid_w, self.grid_h)
        mem_dc = wx.MemoryDC(self.offscreen_bmp)
        mem_dc.SetBackground(wx.WHITE_BRUSH)
        mem_dc.Clear()
        mem_dc.SetPen(wx.GREY_PEN)
        for idx, pct in enumerate(self.grid_cell_pct):
            row = idx // total_cols
            col = idx % total_cols
            x = col * self.cell_w
            y = row * self.cell_h
            if pct >= 100:
                mem_dc.SetBrush(wx.GREEN_BRUSH)
            else:
                mem_dc.SetBrush(wx.LIGHT_GREY_BRUSH)
            mem_dc.DrawRectangle(x, y, self.cell_w - 1, self.cell_h - 1)
        dc.Blit(0, 0, self.grid_w, self.grid_h, mem_dc, 0, 0)
        mem_dc.SelectObject(wx.NullBitmap)
    def refresh_speed_info(self, speed_str: str, elapsed: str, remain: str, global_pct: int):
        self.speed_text.SetLabel(f"总速度: {speed_str}")
        self.elapsed_text.SetLabel(f"已耗时: {elapsed}")
        self.remain_text.SetLabel(f"预计剩余: {remain}")
        self.global_gauge.SetValue(global_pct)
        self.panel.Layout()
    def on_export_ndf_click(self, event):
        dlg = wx.DirDialog(self, "选择.ndf导出目录", self.ctx.save_path, wx.DD_DEFAULT_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            export_dir = dlg.GetPath()
            ndf_path = export_ndf(self.ctx, export_dir)
            self.append_log(f"已导出断点压缩包：{ndf_path}")
        dlg.Destroy()
    def on_window_close(self, event):
        self.ctx.stop_event.set()
        self.append_log("窗口关闭信号触发，正在终止所有下载线程...")
        with self.ctx.global_lock:
            for task in self.ctx.chunk_task_list:
                flush_single_chunk_buffer(self.ctx, task)
        time.sleep(0.6)
        if self.ctx.file_obj is not None:
            self.ctx.file_obj.flush()
            os.fsync(self.ctx.file_obj.fileno())
            self.ctx.file_obj.close()
            self.ctx.file_obj = None
        self.Destroy()

# -------------------------- 对外唯一入口函数 Download --------------------------
def Download(
    URL: str,                    # 文件下载链接
    SavePath: str,               # 文件保存目录
    FileName: str,               # 输出文件名（带后缀）
    Jobs: int = 8,               # 并发分片线程数
    Size: int = 10 * 1024 * 1024,# 单分片字节大小 默认10MB
    Head: dict = None,           # HTTP请求头字典
    Cache: float = 32.0,         # 内存缓冲MB
    Run: str = None,             # 完成动作 Open / Shutdown
    disable_ssl: bool = False,   # 关闭SSL校验
    completion_callback = None,  # 完成回调(success:bool, size:int)
    ResumePath: str = ""         # 断点续传JSON路径
):
    os.makedirs(SavePath, exist_ok=True)
    if Jobs > 128:
        wx.MessageBox("并发线程最大限制128，已自动修正为128", "参数警告", wx.OK)
        Jobs = 128
    if Jobs < 1:
        Jobs = 1
    download_ctx = init_download_context(
        url=URL,
        save_path=SavePath,
        filename=FileName,
        jobs=Jobs,
        chunk_size=Size,
        headers=Head,
        cache_mb=Cache,
        run_after=Run,
        disable_ssl=disable_ssl,
        completion_callback=completion_callback,
        resume_json_path=ResumePath
    )
    app = wx.App(False)
    DownloadFrame(ctx=download_ctx)
    app.MainLoop()

# -------------------------- 测试入口 --------------------------
if __name__ == "__main__":
    test_url = ""
    test_save = "D:\downloads"
    test_name = ""
    custom_header = {
        "User-Agent": "Mozilla/5.0 Windows MultiDownloader"
    }
    Download(
        URL=test_url,
        SavePath=test_save,
        FileName=test_name,
        Jobs=16,
        Size=128*1024,
        Head=custom_header,
        Cache=4,
        Run=None,
        disable_ssl=True
    )