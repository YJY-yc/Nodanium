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
import tempfile
from io import BytesIO
import urllib3
import ssl
from queue import Queue
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any

# 网络警告屏蔽
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context


DEFAULT_TIMEOUT = 240
DEFAULT_RETRY = 100 #重试次数
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
    finished: bool = False          # 是否完成
    downloaded: int = 0             # 已下载
    task_buffer: Optional[BytesIO] = None  #内存缓冲
    chunk_lock: Optional[threading.Lock] = None  # 分片写入锁

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
    uuid: str = "" 
    speed_unit: str = "MB/s"
    file_total_size: int = 0
    total_downloaded: int = 0
    chunk_task_list: Optional[List[ChunkTask]] = None
    task_queue: Optional[Queue] = None
    stop_event: Optional[threading.Event] = None
    global_lock: Optional[threading.Lock] = None
    file_obj: Optional[Any] = None   # 标准文件对象
    last_speed_calc_ts: float = 0.0
    last_total_bytes: int = 0
    start_ts: float = 0.0
    ndf_progress_path: str = ""
    ui_frame: Optional[Any] = None
    original_ndf_path: str = ""
    ndf_extracted_dir: str = ""
    download_completed: bool = False
    _completion_handled: bool = False

# --------------------------  --------------------------

try:
    from DownloadUI import update_download_record_by_uuid
except ImportError:

    def update_download_record_by_uuid(uuid, **kwargs):
        pass

def format_speed(speed_bps: float, unit: str = "MB/s") -> str:
    """格式化速度字符串"""
    unit = unit.upper()
    
    if unit == "MB/S":

        if speed_bps < 1000:
            return f"{speed_bps:.2f} B/s"
        elif speed_bps < 1000 ** 2:
            return f"{speed_bps / 1000:.2f} KB/s"
        else:
            return f"{speed_bps / (1000**2):.2f} MB/s"
    
    elif unit == "MIB/S":
       
        if speed_bps < 1024:
            return f"{speed_bps:.2f} B/s"
        elif speed_bps < 1024 ** 2:
            return f"{speed_bps / 1024:.2f} KiB/s"
        else:
            return f"{speed_bps / (1024**2):.2f} MiB/s"
    
    elif unit == "MBPS":
        
        speed_bps = speed_bps * 8  
        if speed_bps < 1000:
            return f"{speed_bps:.2f} bps"
        elif speed_bps < 1000 ** 2:
            return f"{speed_bps / 1000:.2f} Kbps"
        else:
            return f"{speed_bps / (1000**2):.2f} Mbps"
    
    else:
        
        return format_speed(speed_bps, "MB/s")


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

# --------------------------  --------------------------
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

# -------------------------- 网络分片--------------------------
def single_chunk_worker(ctx: DownloadCtx) -> None:
    max_cache_bytes = int(ctx.cache_mb * 1024 * 1024)
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=ctx.jobs, pool_maxsize=ctx.jobs)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    retry_times = 0
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
        if task.chunk_lock is None:
            task.chunk_lock = threading.Lock()
        
        total_chunk_len = task.end_byte - task.start_byte + 1
        current_offset = task.start_byte + task.downloaded
        chunk_finish_flag = False
        
        while current_offset <= task.end_byte and not ctx.stop_event.is_set():
            try:
                range_header = {"Range": f"bytes={current_offset}-{task.end_byte}"}
                req_headers = {**ctx.headers, **range_header}
                resp = session.get(ctx.url, headers=req_headers, stream=True, timeout=DEFAULT_TIMEOUT, verify=(not ctx.disable_ssl))
                resp.raise_for_status()
                
                for raw_data in resp.iter_content(chunk_size=8192):
                    if ctx.stop_event.is_set():
                        flush_single_chunk_buffer(ctx, task)
                        break
                    if not raw_data:
                        continue
                    task.task_buffer.write(raw_data)
                    data_len = len(raw_data)
                    task.downloaded += data_len
                    
     
                    with ctx.global_lock:
                        ctx.total_downloaded += data_len
                    
                    if task.task_buffer.getbuffer().nbytes >= max_cache_bytes:
                        flush_single_chunk_buffer(ctx, task)
                    
                    pct = min(int((task.downloaded / total_chunk_len) * 100), 100)
                    ui_push_chunk_progress(ctx, task.chunk_idx, task.downloaded, total_chunk_len)
                    current_offset = task.start_byte + task.downloaded
                    if task.downloaded >= total_chunk_len:
                        chunk_finish_flag = True
                        break
            
            except Exception as e:
                retry_times += 1
                err_msg = f"分片{task.chunk_idx}异常 重试{retry_times}/{DEFAULT_RETRY}: {str(e)}"
                print(f"分片{task.chunk_idx}异常 重试{retry_times}/{DEFAULT_RETRY}: {str(e)}")
                ui_push_log(ctx, err_msg)
                time.sleep(2)
        
        
        flush_single_chunk_buffer(ctx, task)
        
        if task.downloaded >= total_chunk_len:
            with ctx.global_lock:
                task.finished = True
            ui_push_log(ctx, f"分片{task.chunk_idx}数据下载完成")

        
        ctx.task_queue.task_done()
    
    session.close()

# -------------------------- UI异步推送--------------------------
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
    """刷新速度面板 - 使用滑动窗口平均算法"""
    if ctx.stop_event.is_set() or ctx.ui_frame is None or ctx.file_total_size == 0:
        return
    
    now_ts = time.time()
    delta_ts = now_ts - ctx.last_speed_calc_ts
    

    if delta_ts < 0.3:  
        return
    
    with ctx.global_lock:
        delta_bytes = ctx.total_downloaded - ctx.last_total_bytes
        ctx.last_total_bytes = ctx.total_downloaded
        ctx.last_speed_calc_ts = now_ts
    
  
    if not hasattr(ctx, 'speed_history'):
        ctx.speed_history = []
    
    current_speed = delta_bytes / delta_ts if delta_ts > 0 else 0
    ctx.speed_history.append(current_speed)
    

    if len(ctx.speed_history) > 8:
        ctx.speed_history.pop(0)
    

    valid_speeds = [s for s in ctx.speed_history if s > 0]
    if valid_speeds:
        valid_speeds.sort()
        if len(valid_speeds) % 2 == 0:
            avg_speed = (valid_speeds[len(valid_speeds)//2 - 1] + valid_speeds[len(valid_speeds)//2]) / 2
        else:
            avg_speed = valid_speeds[len(valid_speeds)//2]
    else:
        avg_speed = current_speed
    

    if hasattr(ctx, 'last_avg_speed') and ctx.last_avg_speed > 0:
        max_increase = ctx.last_avg_speed * 1.5
        max_decrease = ctx.last_avg_speed * 0.5
        avg_speed = max(min(avg_speed, max_increase), max_decrease)
    
    ctx.last_avg_speed = avg_speed
    

    speed_str = format_speed(avg_speed, ctx.speed_unit)
    
    # 计算已耗时
    elapsed_sec = now_ts - ctx.start_ts
    h, rem = divmod(elapsed_sec, 3600)
    m, s = divmod(rem, 60)
    time_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
    
    # 计算剩余时间
    if avg_speed > 0:
        remain_bytes = ctx.file_total_size - ctx.total_downloaded
        remain_sec_raw = remain_bytes / avg_speed
        remain_sec_raw = max(0, remain_sec_raw)
        
        if not hasattr(ctx, 'last_remain_sec'):
            ctx.last_remain_sec = remain_sec_raw
        else:

            ctx.last_remain_sec = 0.5 * remain_sec_raw + 0.5 * ctx.last_remain_sec
        
        remain_sec = ctx.last_remain_sec
        
        rh, rrem = divmod(remain_sec, 3600)
        rm, rs = divmod(rrem, 60)
        remain_str = f"{int(rh):02d}:{int(rm):02d}:{int(rs):02d}"
    else:
        remain_str = "计算中"
    
    global_pct = min(int((ctx.total_downloaded / ctx.file_total_size) * 100), 100)
    
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
            wx.CallAfter(ctx.completion_callback, False, 0, ctx.uuid)
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
            wx.CallAfter(ctx.completion_callback, False, 0, ctx.uuid)
        return
    
    ui_push_global_status(ctx, f"{ctx.file_total_size / 1024 / 1024:.2f}MiB")
    

    worker_threads = []
    for _ in range(ctx.jobs):
        t = threading.Thread(target=single_chunk_worker, args=(ctx,), daemon=True)
        worker_threads.append(t)
        t.start()
    

    while not ctx.stop_event.is_set():
        all_chunk_finished = all(t.finished for t in ctx.chunk_task_list)
        if all_chunk_finished:
            break
        ui_refresh_speed_panel(ctx)
        time.sleep(0.1)
    

    ctx.stop_event.set()
    

    if ctx.file_obj is not None:
        ctx.file_obj.flush()
        os.fsync(ctx.file_obj.fileno())
        ctx.file_obj.close()
        ctx.file_obj = None

    def background_cleanup():
        try:
            ctx.task_queue.join()
            for t in worker_threads:
                if t.is_alive():
                    t.join(timeout=2)
         
        except Exception as e:
            ui_push_log(ctx, f"后台清理失败: {str(e)}")
    
    threading.Thread(target=background_cleanup, daemon=True).start()
    

    final_file_size = os.path.getsize(target_full_path) if os.path.exists(target_full_path) else 0
    all_chunk_finished = all(t.finished for t in ctx.chunk_task_list)
    file_complete = (final_file_size == ctx.file_total_size)
    binary_valid = True
    
    if file_complete and final_file_size > 0:
        try:
            with open(target_full_path, "rb") as f:
                check_size = min(1024, final_file_size)
                head = f.read(check_size)
                
                if final_file_size > check_size:
                    f.seek(-check_size, os.SEEK_END)
                    tail = f.read(check_size)
                    if all(b == 0 for b in head) and all(b == 0 for b in tail):
                        binary_valid = False
                else:
                    if all(b == 0 for b in head):
                        binary_valid = False
        except Exception as e:
            ui_push_log(ctx, f"文件校验警告: {str(e)}")
    
    time_cost_sec = time.time() - ctx.start_ts
    h, rem = divmod(time_cost_sec, 3600)
    m, s = divmod(rem, 60)
    time_str = f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
    
  
    if all_chunk_finished and file_complete and binary_valid:
        ui_push_global_status(ctx, "全部分片下载完成，磁盘文件校验通过")
        ui_push_log(ctx, f"下载完成，文件完整，大小：{final_file_size}字节")
        
        if ctx.run_after == "Open":
            try:
                os.startfile(target_full_path)
            except:
                pass
        elif ctx.run_after == "Shutdown":
            ui_push_log(ctx, "10秒后执行关机，可关闭窗口取消")
            time.sleep(10)
            os.system("shutdown /s /t 0")
        
        if ctx.uuid:
            update_download_record_by_uuid(ctx.uuid, status="已完成", file_size=final_file_size)
        
        download_result = {
            'success': True,
            'file_size': final_file_size,
            'save_path': ctx.save_path,
            'filename': ctx.filename,
            'time_cost': time_str,
            'threads': ctx.jobs
        }

        if ctx.completion_callback:
            wx.CallAfter(ctx.completion_callback, True, final_file_size, ctx.uuid)
        
        avg_speed = final_file_size / time_cost_sec if time_cost_sec > 0 else 0
        
        ctx.download_completed = True

        def show_complete_dialog_and_close():
            if ctx._completion_handled:
                return
            from CompleteReport import show_download_complete_report
            show_download_complete_report(
                parent=ctx.ui_frame,
                filename=ctx.filename,
                save_path=ctx.save_path,
                file_size=final_file_size,
                time_cost=time_str,
                average_speed=avg_speed,
                speed_unit=ctx.speed_unit 
            )
            if ctx.ui_frame and not ctx._completion_handled:
                ctx.ui_frame._handle_completed_close()
        
        wx.CallAfter(show_complete_dialog_and_close)
    
    # 下载失败
    elif not ctx.stop_event.is_set():
        if not file_complete or not binary_valid:
            ui_push_global_status(ctx, "警告：分片显示完成，但磁盘文件数据缺失/损坏！")
            ui_push_log(ctx, f"内存统计总字节:{ctx.total_downloaded}，磁盘真实大小:{final_file_size}，原始文件大小:{ctx.file_total_size}")
            wx.CallAfter(wx.MessageBox, "文件分片显示完成，但磁盘文件存在空洞/数据损坏，请重新下载！", "文件校验失败", wx.ICON_ERROR)
        else:
            ui_push_global_status(ctx, "下载中断，存在未完成分片，支持续传")
            ui_push_log(ctx, f"已保存断点文件：{ctx.ndf_progress_path}")
        
        if ctx.uuid:
            update_download_record_by_uuid(ctx.uuid, status="失败：下载中断", file_size=final_file_size)
        if ctx.completion_callback:
            wx.CallAfter(ctx.completion_callback, False, final_file_size, ctx.uuid)
    
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
    resume_json_path: str = "",
    uuid: str = "",
    speed_unit: str = "MB/s"
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
        uuid=uuid, 
        speed_unit=speed_unit,
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
    def __init__(self, ctx: DownloadCtx):
        super().__init__(None, title=f"下载 - {ctx.filename}", size=(500, 400))
        
        self.SetDoubleBuffered(True)
        
        self.ctx = ctx
        self.ctx.ui_frame = self
        self.grid_cell_pct: List[int] = [
            100 if t.finished else min(100, int(t.downloaded / max(1, t.end_byte - t.start_byte + 1) * 100))
            for t in ctx.chunk_task_list
        ]
        self.panel = wx.Panel(self)
        self.panel.SetDoubleBuffered(True)
        self.offscreen_bmp: Optional[wx.Bitmap] = None
        self.grid_col_count = 1
        self.cell_w = GRID_CELL_SIZE
        self.cell_h = GRID_CELL_SIZE
        self.grid_w = 0
        self.grid_h = 0
        self.updating_grid = False
        self.refresh_pending = False
        self.last_refresh_time = 0
        self.is_painting = False
        self.is_layouting = False 
        self.is_refreshing = False  
        
    
        self.Bind(wx.EVT_SIZE, self.on_window_size)
        
        self.create_ui_layout()
        self.Bind(wx.EVT_CLOSE, self.on_window_close)
        self.start_schedule_thread()
        self.Centre()
        self.Show()
# -------------------------- 下载主窗口UI（无业务逻辑，仅渲染） --------------------------
class DownloadFrame(wx.Frame):
    def __init__(self, ctx: DownloadCtx):
        super().__init__(None, title=f"下载 - {ctx.filename}", size=(500, 400))
        

        self.SetDoubleBuffered(True)
        
        self.ctx = ctx
        self.ctx.ui_frame = self
        self.grid_cell_pct: List[int] = [
            100 if t.finished else min(100, int(t.downloaded / max(1, t.end_byte - t.start_byte + 1) * 100))
            for t in ctx.chunk_task_list
        ]
        self.panel = wx.Panel(self)
        self.panel.SetDoubleBuffered(True)
        self.cell_w = GRID_CELL_SIZE
        self.cell_h = GRID_CELL_SIZE
        

        self.Bind(wx.EVT_SIZE, self.on_window_size)
        
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
        self.speed_text.SetMinSize((150, -1))
        self.elapsed_text = wx.StaticText(self.panel, label="已耗时: 00:00:00")
        self.remain_text = wx.StaticText(self.panel, label="预计剩余: --")
        speed_box.Add(self.speed_text, flag=wx.RIGHT, border=20)
        speed_box.Add(self.elapsed_text, flag=wx.RIGHT, border=15)
        speed_box.Add(self.remain_text)
        main_vbox.Add(speed_box, flag=wx.LEFT | wx.BOTTOM, border=10)
        
   
        self.grid_scroll = wx.ScrolledWindow(self.panel, style=wx.VSCROLL | wx.HSCROLL)
        self.grid_scroll.SetDoubleBuffered(True)
        self.grid_scroll.SetScrollRate(GRID_CELL_SIZE, GRID_CELL_SIZE)
        self.grid_scroll.SetBackgroundColour(wx.WHITE)
        
        self.grid_panel = wx.Panel(self.grid_scroll)
        self.grid_panel.SetDoubleBuffered(True)
        self.grid_panel.SetBackgroundColour(wx.WHITE)
        self.grid_panel.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.grid_panel.Bind(wx.EVT_PAINT, self.on_grid_paint)
        
        grid_sizer = wx.BoxSizer(wx.VERTICAL)
        grid_sizer.Add(self.grid_panel, proportion=1, flag=wx.EXPAND)
        self.grid_scroll.SetSizer(grid_sizer)
        
        main_vbox.Add(self.grid_scroll, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        

        self.log_ctrl = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 120))
        self.log_ctrl.SetDoubleBuffered(True)
        main_vbox.Add(self.log_ctrl, proportion=0, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=5)
        

        btn_box = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_pause = wx.Button(self.panel, label="暂停/终止")
        self.btn_export = wx.Button(self.panel, label="导出.ndf")
        self.btn_export.Bind(wx.EVT_BUTTON, self.on_export_ndf_click)
        btn_box.Add(self.btn_pause, flag=wx.RIGHT, border=10)
        btn_box.Add(self.btn_export)
        main_vbox.Add(btn_box, flag=wx.ALL | wx.ALIGN_CENTER, border=8)
        
        if self.grid_cell_pct:
            total_cols = max(1, 400 // self.cell_w)
            total_rows = (len(self.grid_cell_pct) + total_cols - 1) // total_cols
            init_grid_w = total_cols * self.cell_w
            init_grid_h = total_rows * self.cell_h
            self.grid_scroll.SetVirtualSize((init_grid_w, init_grid_h))
            self.grid_panel.SetMinSize((init_grid_w, init_grid_h))
            self.grid_scroll.Layout()
        
        self.panel.SetSizer(main_vbox)
        self.panel.Layout()
        
        if self.ctx.file_total_size > 0:
            init_pct = min(int((self.ctx.total_downloaded / self.ctx.file_total_size) * 100), 100)
            self.global_gauge.SetValue(init_pct)
        
        self.grid_panel.Refresh()
    
    def append_log(self, msg: str):
        """添加日志（与 ui_push_log 函数配合使用）"""
        self.add_log(msg)

    def set_status_text(self, msg: str):
        """设置状态文本"""
        self.status_label.SetLabel(msg)

    def on_grid_paint(self, event):
        """绘制网格 - 自适应窗口大小"""
        dc = wx.AutoBufferedPaintDC(self.grid_panel)
        

        scroll_w, scroll_h = self.grid_scroll.GetClientSize()
        
        if scroll_w == 0 or scroll_h == 0:
            if self.grid_cell_pct:
                total_cols = max(1, 400 // self.cell_w)
                total_rows = (len(self.grid_cell_pct) + total_cols - 1) // total_cols
                self.grid_scroll.SetVirtualSize((total_cols * self.cell_w, total_rows * self.cell_h))
                self.grid_panel.SetMinSize((total_cols * self.cell_w, total_rows * self.cell_h))
            return
        

        panel_w, panel_h = self.grid_panel.GetClientSize()
        
        total_cols = max(1, scroll_w // self.cell_w)
        total_rows = (len(self.grid_cell_pct) + total_cols - 1) // total_cols
        grid_w = total_cols * self.cell_w
        grid_h = total_rows * self.cell_h
        

        self.grid_scroll.SetVirtualSize((grid_w, grid_h))
    
        self.grid_panel.SetMinSize((grid_w, max(grid_h, scroll_h)))

        self.grid_scroll.Layout()

        dc.SetBrush(wx.WHITE_BRUSH)
        dc.SetPen(wx.WHITE_PEN)
        dc.DrawRectangle(0, 0, panel_w, panel_h)
  
        dc.SetPen(wx.GREY_PEN)
        for idx, pct in enumerate(self.grid_cell_pct):
            row = idx // total_cols
            col = idx % total_cols
            x = col * self.cell_w
            y = row * self.cell_h

            if y < panel_h and x < panel_w:
                if pct >= 100:
                    dc.SetBrush(wx.GREEN_BRUSH)
                else:
                    dc.SetBrush(wx.LIGHT_GREY_BRUSH)
                
                dc.DrawRectangle(x, y, self.cell_w - 1, self.cell_h - 1)
    
    def on_window_size(self, event):
        """窗口大小变化时刷新网格"""
        if hasattr(self, 'grid_panel') and hasattr(self, 'grid_scroll'):

            self.grid_panel.Refresh()
        
        event.Skip()
    
    def update_grid_cell(self, chunk_idx: int, pct: int):
        """更新单个网格单元"""
        if chunk_idx >= len(self.grid_cell_pct):
            return
        
        old_val = self.grid_cell_pct[chunk_idx]
        if old_val == pct:
            return
        
        self.grid_cell_pct[chunk_idx] = pct
        
        if hasattr(self, 'grid_panel'):
            self.grid_panel.Refresh()
    
    def refresh_speed_info(self, speed_str: str, elapsed: str, remain: str, global_pct: int):
        """刷新速度信息"""
        self.panel.Freeze()
        self.speed_text.SetLabel(f"总速度: {speed_str}")
        self.elapsed_text.SetLabel(f"已耗时: {elapsed}")
        self.remain_text.SetLabel(f"预计剩余: {remain}")
        self.global_gauge.SetValue(global_pct)
        self.panel.Thaw()
    
    def add_log(self, text: str):
        """添加日志"""
        current_time = time.strftime("%H:%M:%S", time.localtime())
        self.log_ctrl.AppendText(f"[{current_time}] {text}\n")
        self.log_ctrl.ShowPosition(self.log_ctrl.GetLastPosition())
    
    def on_export_ndf_click(self, event):
        """导出.ndf文件 - 立即停止下载，后台导出带进度"""
        try:
            if self.ctx.stop_event:
                self.ctx.stop_event.set()
            
            self.btn_export.Enable(False)
            self.btn_pause.Enable(False)
            self.status_label.SetLabel("正在停止下载并准备导出...")
            self.panel.Layout()
            
            dump_progress_json(self.ctx)
            
            with wx.DirDialog(self, "选择导出目录", style=wx.DD_DEFAULT_STYLE) as dlg:
                if dlg.ShowModal() == wx.ID_OK:
                    export_save_path = dlg.GetPath()
                    
                    export_dialog = wx.ProgressDialog(
                        "导出中",
                        "正在打包下载文件...",
                        maximum=100,
                        parent=self
                    )
                    export_dialog.SetRange(100)
                    
                    def do_export():
                        try:
                            ndf_full_path = os.path.join(export_save_path, f"{self.ctx.filename}{NDF_SUFFIX}")
                            target_file = os.path.join(self.ctx.save_path, self.ctx.filename)
                            progress_path = self.ctx.ndf_progress_path
                            
                            file_size = os.path.getsize(target_file) if os.path.exists(target_file) else 0
                            chunk_size = max(1024 * 1024, file_size // 50) if file_size > 0 else 1024 * 1024
                            current_pos = 0
                            
                            def update_export_progress(pct):
                                wx.CallAfter(export_dialog.Update, pct)
                            
                            import io
                            with zipfile.ZipFile(ndf_full_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                                if os.path.exists(target_file):
                                    file_info = zipfile.ZipInfo(self.ctx.filename)
                                    file_info.compress_type = zipfile.ZIP_DEFLATED
                                    with open(target_file, "rb") as f_src:
                                        with zf.open(file_info, 'w') as f_dst:
                                            while True:
                                                buf = f_src.read(chunk_size)
                                                if not buf:
                                                    break
                                                f_dst.write(buf)
                                                current_pos += len(buf)
                                                pct = min(95, int((current_pos / max(1, file_size)) * 95))
                                                update_export_progress(pct)
                                
                                if os.path.exists(progress_path):
                                    with open(progress_path, "rb") as pf:
                                        zf.writestr(PROGRESS_JSON_NAME, pf.read())
                            
                            update_export_progress(99)
                            time.sleep(0.2)
                            wx.CallAfter(self._on_export_done, export_dialog, ndf_full_path, True)
                        except Exception as e:
                            wx.CallAfter(self._on_export_done, export_dialog, str(e), False)
                    
                    threading.Thread(target=do_export, daemon=True).start()
                else:
                    self.btn_export.Enable()
                    self.btn_pause.Enable()
                    self.status_label.SetLabel("准备初始化下载...")
        except Exception as e:
            wx.MessageBox(f"导出失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            self.btn_export.Enable()
            self.btn_pause.Enable()

    def _on_export_done(self, export_dialog, result, success):
        """导出完成回调"""
        try:
            export_dialog.Update(100)
            wx.Yield()
            export_dialog.Update(101)
            export_dialog.Hide()
            export_dialog.Destroy()
        except Exception:
            pass
        
        if success:
            self.status_label.SetLabel("导出完成")
            wx.MessageBox(f"导出成功！\n文件路径: {result}", "导出成功", wx.OK)
            
            target_file = os.path.join(self.ctx.save_path, self.ctx.filename)
            if os.path.exists(target_file):
                dlg = wx.MessageDialog(
                    self,
                    f"是否删除原下载文件？\n\n源文件: {target_file}\n.ndf 文件已包含该内容。",
                    "保留源文件",
                    wx.YES_NO | wx.ICON_QUESTION
                )
                if dlg.ShowModal() == wx.ID_NO:
                    safe_delete_file(target_file)
                    if os.path.exists(self.ctx.ndf_progress_path):
                        safe_delete_file(self.ctx.ndf_progress_path)
                dlg.Destroy()
        else:
            self.status_label.SetLabel("导出失败")
            wx.MessageBox(f"导出失败: {result}", "错误", wx.OK | wx.ICON_ERROR)
        
        self.Close()


    def on_window_close(self, event):
        """窗口关闭处理"""
        ctx = self.ctx

        if ctx._completion_handled:
            self.Destroy()
            return

        is_completed = ctx.download_completed
        if not is_completed:
            if ctx.file_total_size > 0 and ctx.total_downloaded >= ctx.file_total_size:
                all_done = all(t.finished for t in ctx.chunk_task_list) if ctx.chunk_task_list else True
                if all_done:
                    is_completed = True
                    ctx.download_completed = True
            elif ctx.file_total_size <= 0 and ctx.chunk_task_list:
                all_done = all(t.finished for t in ctx.chunk_task_list)
                if all_done and ctx.total_downloaded > 0:
                    is_completed = True
                    ctx.download_completed = True

        if is_completed:
            dump_progress_json(ctx)
            self._handle_completed_close()
            return

        dump_progress_json(ctx)
        if ctx.stop_event:
            ctx.stop_event.set()

        if ctx.original_ndf_path and os.path.exists(ctx.original_ndf_path):
            dlg = wx.MessageDialog(
                self,
                f"是否将当前进度写回原 NDF 文件？\n\n"
                f"原文件: {ctx.original_ndf_path}\n"
                f"将使用当前下载进度覆盖原 NDF 内容。",
                "更新 NDF",
                wx.YES_NO | wx.ICON_QUESTION
            )
            result = dlg.ShowModal()
            dlg.Destroy()
            
            if result == wx.ID_YES:
                self._update_ndf_and_close()
                return
        
        if ctx.completion_callback:
            try:
                ctx.completion_callback(success=False, size=0)
            except Exception:
                pass
        
        self.Destroy()
    
    def _handle_completed_close(self):
        """下载完成"""
        ctx = self.ctx

        if ctx._completion_handled:
            self.Destroy()
            return

        ctx._completion_handled = True


        if ctx.ndf_extracted_dir and os.path.exists(ctx.ndf_extracted_dir):
            src_file = os.path.join(ctx.ndf_extracted_dir, ctx.filename)
            dst_file = os.path.join(ctx.save_path, ctx.filename)
            
            if os.path.exists(src_file) and src_file != dst_file:
                self._move_file_with_progress(src_file, dst_file, "移动文件到保存目录")
            

            shutil.rmtree(ctx.ndf_extracted_dir, ignore_errors=True)
            ctx.ndf_extracted_dir = ""

       
        if ctx.original_ndf_path and os.path.exists(ctx.original_ndf_path):
            dlg = wx.MessageDialog(
                self,
                f"下载完成！是否删除原 NDF 文件？\n\n"
                f"原文件: {ctx.original_ndf_path}\n"
                f"下载文件已保存到: {ctx.save_path}",
                "删除 NDF",
                wx.YES_NO | wx.ICON_QUESTION
            )
            result = dlg.ShowModal()
            dlg.Destroy()
            
            if result == wx.ID_YES:
                safe_delete_file(ctx.original_ndf_path)
                if os.path.exists(ctx.ndf_progress_path):
                    safe_delete_file(ctx.ndf_progress_path)
        

        if ctx.completion_callback:
            try:
                ctx.completion_callback(success=False, size=0)
            except Exception:
                pass
        
        self.Destroy()
    
    def _move_file_with_progress(self, src, dst, title):
        """带进度的文件移动"""
        file_size = os.path.getsize(src)
        chunk_size = max(1024 * 1024, file_size // 50) if file_size > 0 else 1024 * 1024
        current_pos = 0
        
        progress_dlg = wx.ProgressDialog(
            title,
            "正在移动文件...",
            maximum=100,
            parent=self
        )
        progress_dlg.SetRange(100)
        
        try:
            if os.path.exists(dst):
                os.remove(dst)
            
            with open(src, "rb") as f_src:
                with open(dst, "wb") as f_dst:
                    while True:
                        buf = f_src.read(chunk_size)
                        if not buf:
                            break
                        f_dst.write(buf)
                        current_pos += len(buf)
                        pct = min(99, int((current_pos / max(1, file_size)) * 99))
                        progress_dlg.Update(pct)
                        wx.Yield()
            
            progress_dlg.Update(100)
            wx.Yield()
        except Exception:
            pass
        finally:
            try:
                progress_dlg.Update(100)
                progress_dlg.Hide()
                progress_dlg.Destroy()
            except Exception:
                pass
    
    def _update_ndf_and_close(self):
        """后台更新 NDF，完成后关闭窗口"""
        ctx = self.ctx

        ctx._completion_handled = True

        ndf_path = ctx.original_ndf_path
        target_file = os.path.join(ctx.save_path, ctx.filename)
        
        file_size = os.path.getsize(target_file) if os.path.exists(target_file) else 0
        chunk_size = max(1024 * 1024, file_size // 50) if file_size > 0 else 1024 * 1024
        
        progress_dlg = wx.ProgressDialog(
            "更新 NDF",
            "正在重新打包下载进度...",
            maximum=100,
            parent=self
        )
        progress_dlg.SetRange(100)
        
        self._ndf_update_done = False
        self._ndf_update_success = False
        self._ndf_update_result = ""
        
        def do_update():
            try:
                tmp_ndf = ndf_path + ".tmp"
                current_pos = 0
                with zipfile.ZipFile(tmp_ndf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    if os.path.exists(target_file):
                        file_info = zipfile.ZipInfo(ctx.filename)
                        file_info.compress_type = zipfile.ZIP_DEFLATED
                        with open(target_file, "rb") as f_src:
                            with zf.open(file_info, 'w') as f_dst:
                                while True:
                                    buf = f_src.read(chunk_size)
                                    if not buf:
                                        break
                                    f_dst.write(buf)
                                    current_pos += len(buf)
                                    pct = min(95, int((current_pos / max(1, file_size)) * 95))
                                    wx.CallAfter(progress_dlg.Update, pct)
                    
                    if os.path.exists(ctx.ndf_progress_path):
                        with open(ctx.ndf_progress_path, "rb") as pf:
                            zf.writestr(PROGRESS_JSON_NAME, pf.read())
                
                wx.CallAfter(progress_dlg.Update, 99)
                time.sleep(0.1)
                
                if os.path.exists(ndf_path):
                    os.remove(ndf_path)
                shutil.move(tmp_ndf, ndf_path)
                
                self._ndf_update_success = True
                self._ndf_update_result = ndf_path
            except Exception as e:
                if os.path.exists(ndf_path + ".tmp"):
                    os.remove(ndf_path + ".tmp")
                self._ndf_update_success = False
                self._ndf_update_result = str(e)
            finally:
                self._ndf_update_done = True
        
        threading.Thread(target=do_update, daemon=True).start()
        
      
        while not self._ndf_update_done:
            wx.Yield()
            time.sleep(0.05)
        
        try:
            progress_dlg.Update(100)
            wx.Yield()
            progress_dlg.Update(100)
            progress_dlg.Hide()
            progress_dlg.Destroy()
        except Exception:
            pass
        
        if self._ndf_update_success:
            wx.MessageBox(f"NDF 文件已更新！\n路径: {self._ndf_update_result}", "更新成功", wx.OK)
        else:
            wx.MessageBox(f"NDF 更新失败: {self._ndf_update_result}", "错误", wx.OK | wx.ICON_ERROR)
        
        # 清理
        if ctx.ndf_extracted_dir and os.path.exists(ctx.ndf_extracted_dir):
            shutil.rmtree(ctx.ndf_extracted_dir, ignore_errors=True)
            ctx.ndf_extracted_dir = ""
        
        if ctx.completion_callback:
            try:
                ctx.completion_callback(success=False, size=0)
            except Exception:
                pass
        
        self.Destroy()

    def start_schedule_thread(self):
        """启动调度线程"""

        download_thread = threading.Thread(target=schedule_download_task, args=(self.ctx,))
        download_thread.daemon = True
        download_thread.start()
# -------------------------- 对外唯一入口函数 Download --------------------------
def Download(
    uuid: str,
    URL: str,                    # 文件下载链接
    SavePath: str,               # 文件保存目录
    FileName: str,               # 输出文件名
    Jobs: int = 8,               # 并发分片线程数
    Size: int = 10 * 1024 * 1024,# 单分片字节大小 默认10MB
    Head: dict = None,           # HTTP请求头字典
    Cache: float = 32.0,         # 内存缓冲MB
    Run: str = None,             # 完成动作 Open/Shutdown
    disable_ssl: bool = False,   # 关闭SSL校验
    completion_callback = None,  # 完成回调
    ResumePath: str = ""  ,       # 断点续传JSON路径
     SpeedUnit: str = "MB/s"
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
        resume_json_path=ResumePath,
        uuid=uuid,
        speed_unit=SpeedUnit
    )
    app = wx.App(False)
    DownloadFrame(ctx=download_ctx)
    app.MainLoop()

# -------------------------- 断点续传恢复入口 --------------------------
def _safe_message(msg, title="提示", style=wx.OK):
    if wx.GetApp() is not None:
        wx.MessageBox(msg, title, style)
    else:
        print(f"[{title}] {msg}")

def ResumeDownload(
    ResumePath: str,            # .ndf 文件路径
    SavePath: str = "",         
    uuid: str = "",
    SpeedUnit: str = "MB/s",
    completion_callback = None,
    Jobs: int = 0,              # 可选：覆盖线程数，0 表示使用进度文件中的值
    Size: int = 0,              # 可选：覆盖单分片大小，0 表示使用进度文件中的值
    Cache: float = 0.0,         # 可选：覆盖缓存大小(MB)，0 表示使用默认 32MB
    Head: dict = None,          # 可选：自定义请求头
    disable_ssl: bool = False,  # 可选：关闭SSL校验
    InputPath: str = ""         # 可选：恢复对话框中填入的保存路径（优先使用）
) -> bool:
    """
    断点续传恢复函数
    - 支持 .ndf 文件（自动解压导入）
    - 支持 .json 进度文件（直接恢复）
    - Jobs/Size/Cache/Head/disable_ssl 传入则覆盖进度文件中的旧值
    - InputPath 为用户在恢复界面填入的保存路径，优先于其他路径
    返回是否成功启动续传
    """
    try:
        app = wx.App(False)
    except Exception:
        app = wx.GetApp()
    
    resume_json_path = ""
    extracted_dir = ""
    progress_data = {}


    if ResumePath.lower().endswith(NDF_SUFFIX):
        # 解压
        extracted_dir = tempfile.mkdtemp(prefix="ndf_resume_")
        success, progress_data = import_ndf(ResumePath, extracted_dir)
        if not success:
            _safe_message("NDF文件导入失败，文件可能已损坏", "恢复失败", wx.OK | wx.ICON_ERROR)
            if app:
                app.MainLoop()
            return False

        resume_json_path = os.path.join(extracted_dir, PROGRESS_JSON_NAME)
    elif ResumePath.lower().endswith(".json"):

        if not os.path.exists(ResumePath):
            _safe_message(f"进度文件不存在: {ResumePath}", "恢复失败", wx.OK | wx.ICON_ERROR)
            if app:
                app.MainLoop()
            return False
        progress_data = load_progress_json(ResumePath)
        resume_json_path = ResumePath
    else:
        _safe_message("无效的恢复文件类型，请使用 .ndf 或 .json 文件", "恢复失败", wx.OK | wx.ICON_ERROR)
        if app:
            app.MainLoop()
        return False


    if not progress_data or "url" not in progress_data:
        _safe_message("进度文件损坏或缺少必要信息", "恢复失败", wx.OK | wx.ICON_ERROR)

        if extracted_dir and os.path.exists(extracted_dir):
            shutil.rmtree(extracted_dir, ignore_errors=True)
        if app:
            app.MainLoop()
        return False


    url = progress_data["url"]
    original_save_path = progress_data.get("save_path", "")
    filename = progress_data["filename"]
    file_total_size = progress_data.get("file_total_size", 0)


    jobs = Jobs if Jobs > 0 else progress_data.get("jobs", 8)
    chunk_size = Size if Size > 0 else progress_data.get("chunk_size", 10 * 1024 * 1024)
    cache_mb = Cache if Cache > 0 else 32.0
    headers = Head if Head else {}


    if jobs > 128:
        _safe_message("并发线程最大限制128，已自动修正为128", "参数警告", wx.OK)
        jobs = 128
    if jobs < 1:
        jobs = 1

   
    if InputPath:
        final_save_path = InputPath
    elif SavePath:
        final_save_path = SavePath
    elif ResumePath.lower().endswith(NDF_SUFFIX):
        final_save_path = os.path.dirname(os.path.abspath(ResumePath))
    elif original_save_path:
        final_save_path = original_save_path
    else:
        final_save_path = os.getcwd()
    
    os.makedirs(final_save_path, exist_ok=True)
    

    ndf_file_was_moved = False
    if extracted_dir:
        src_file = os.path.join(extracted_dir, filename)
        dst_file = os.path.join(final_save_path, filename)
        if os.path.exists(src_file):
            if not os.path.exists(dst_file):
                shutil.move(src_file, dst_file)
                ndf_file_was_moved = True
            elif os.path.isdir(dst_file):
                shutil.rmtree(dst_file, ignore_errors=True)
                shutil.move(src_file, dst_file)
                ndf_file_was_moved = True
            elif os.path.getsize(src_file) != os.path.getsize(dst_file):
                os.remove(dst_file)
                shutil.move(src_file, dst_file)
                ndf_file_was_moved = True
            else:
                ndf_file_was_moved = True
        

        if os.path.exists(resume_json_path):
            dst_json = os.path.join(final_save_path, f"{filename}_{PROGRESS_JSON_NAME}")
            shutil.copy2(resume_json_path, dst_json)
            resume_json_path = dst_json
    
    save_path = final_save_path


    target_file = os.path.join(save_path, filename)
    if not os.path.exists(target_file):
   
        if extracted_dir and os.path.exists(extracted_dir):
            src_file_check = os.path.join(extracted_dir, filename)
            if os.path.exists(src_file_check):
                _safe_message(
                    f"文件移动失败！源文件仍在: {src_file_check}\n"
                    f"目标位置: {target_file}",
                    "恢复失败", wx.OK | wx.ICON_ERROR
                )
                shutil.rmtree(extracted_dir, ignore_errors=True)
                if app:
                    app.MainLoop()
                return False
        
        _safe_message(
            f"未找到已下载的文件: {target_file}\n"
            f"请确保下载文件与进度文件在同一目录下",
            "恢复失败", wx.OK | wx.ICON_ERROR
        )
        if extracted_dir and os.path.exists(extracted_dir):
            shutil.rmtree(extracted_dir, ignore_errors=True)
        if app:
            app.MainLoop()
        return False

    os.makedirs(save_path, exist_ok=True)
    download_ctx = init_download_context(
        url=url,
        save_path=save_path,
        filename=filename,
        jobs=jobs,
        chunk_size=chunk_size,
        headers=headers,
        cache_mb=cache_mb,
        run_after=None,
        disable_ssl=disable_ssl,
        completion_callback=completion_callback,
        resume_json_path=resume_json_path,
        uuid=uuid,
        speed_unit=SpeedUnit
    )
    
    if ResumePath.lower().endswith(NDF_SUFFIX):
        download_ctx.original_ndf_path = ResumePath

        if not ndf_file_was_moved:
            download_ctx.ndf_extracted_dir = extracted_dir
        else:
         
            download_ctx.ndf_extracted_dir = ""

            if os.path.exists(extracted_dir):
                shutil.rmtree(extracted_dir, ignore_errors=True)
                extracted_dir = ""


    if not download_ctx.chunk_task_list:
        _safe_message("恢复失败：无法创建分片任务", "恢复失败", wx.OK | wx.ICON_ERROR)
        if extracted_dir and os.path.exists(extracted_dir):
            shutil.rmtree(extracted_dir, ignore_errors=True)
        if app:
            app.MainLoop()
        return False


    if app is None:
        app = wx.GetApp()
    if app is None:
        app = wx.App(False)
    DownloadFrame(ctx=download_ctx)
    app.MainLoop()

  
    if extracted_dir and os.path.exists(extracted_dir):
        shutil.rmtree(extracted_dir, ignore_errors=True)
    
    return True

# -------------------------- 测试入口 --------------------------
if __name__ == "__main__":

    if input("是否测试下载？(y/n)") == "y":
        print("测试下载模式")
        test_url = ""
        test_save = ""
        test_name = ""
        custom_header = {
            "User-Agent": "Mozilla/5.0 Windows MultiDownloader"
        }
        Download(
            uuid="11",
            URL=test_url,
            SavePath=test_save,
            FileName=test_name,
            Jobs=18,
            Size=1*1024*1024,
            Head=custom_header,
            Cache=10,
            Run=None,
            disable_ssl=True,
            SpeedUnit="MiB"
        )
    else:
        ResumeDownload("/home/yujy/下载/code.deb.ndf", Jobs=16, Cache=20.0)