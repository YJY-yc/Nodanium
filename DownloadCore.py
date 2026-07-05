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
import ctypes
from ctypes import wintypes
import urllib3
import ssl




urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

class DownloadFrame(wx.Frame):
    def __init__(self, url, filename, save_path, thread_count, disable_ssl=False, completion_callback=None):
        super(DownloadFrame, self).__init__(None, title=f"多线程下载:{filename}", size=(700, 600))
        
        self.url = url
        self.filename = filename
        self.save_path = save_path
        self.thread_count = thread_count
        self.disable_ssl = disable_ssl
        
        self.progress_bars = []
        self.thread_progress = [0] * thread_count
        self.lock = threading.Lock()
        self.total_downloaded = 0
        self.last_total_downloaded = 0
        self.last_update_time = time.time()
        self.downloading = True
        self.threads = []
        self.stop_event = threading.Event()
        self.retry_count = 10
        self.timeout = 240
        self.temp_dir = None
        self.start_time = None
        self.elapsed_time_text = None
        self.chunk_files = []
        self.file_size = 0
        self.completed_chunks = [False] * thread_count
        self.completion_callback = completion_callback 
        
        self.create_ui()
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Show()
        
        self.download_thread = threading.Thread(target=self.start_download)
        self.download_thread.daemon = True
        self.download_thread.start()
    
    def create_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        self.main_progress = wx.Gauge(panel, range=100)
        vbox.Add(self.main_progress, proportion=0, flag=wx.EXPAND | wx.ALL, border=10)
        
        main_label = wx.StaticText(panel, label="状态:")
        vbox.Add(main_label, proportion=0, flag=wx.LEFT, border=3)
        
        self.status_text = wx.StaticText(panel, label="准备开始下载...")
        vbox.Add(self.status_text, proportion=0, flag=wx.ALL, border=3)
        
        self.total_speed_text = wx.StaticText(panel, label="总速度: 0 B/s")
        vbox.Add(self.total_speed_text, proportion=0, flag=wx.ALL, border=3)
        
        self.elapsed_time_text = wx.StaticText(panel, label="耗时: 00:00:00")
        vbox.Add(self.elapsed_time_text, proportion=0, flag=wx.ALL, border=5)

        for i in range(self.thread_count):
            if self.thread_count <= 4:
                w = 18
            elif self.thread_count <= 8:
                w = 15
            elif self.thread_count <= 16:
                w = 12
            elif self.thread_count <= 32:
                w = 8
            elif self.thread_count <= 64:
                w = 6
            elif self.thread_count <= 128:
                w = 3
            else:
                w = 1
            progress = wx.Gauge(panel, range=100, size=(-1, w))
            self.progress_bars.append(progress)
            vbox.Add(progress, proportion=0, flag=wx.EXPAND | wx.ALL, border=0)
        
        self.log_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        vbox.Add(self.log_text, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        panel.SetSizer(vbox)
        self.Centre()
    
    def update_progress(self, thread_index, value):
        if self.stop_event.is_set():
            return
        
        with self.lock:
            self.thread_progress[thread_index] = value
            total = sum(self.thread_progress) / len(self.thread_progress)
            
            wx.CallAfter(self.main_progress.SetValue, int(total))
            
            if thread_index < len(self.progress_bars):
                wx.CallAfter(self.progress_bars[thread_index].SetValue, value)
            
            current_time = time.time()
            time_diff = current_time - self.last_update_time
            
            if time_diff > 0.5:
                speed = (self.total_downloaded - self.last_total_downloaded) / time_diff
                self.last_total_downloaded = self.total_downloaded
                self.last_update_time = current_time
                
                if speed < 1024:
                    speed_str = f"{speed:.2f} B/s"
                elif speed < 1024 * 1024:
                    speed_str = f"{speed / 1024:.2f} KB/s"
                else:
                    speed_str = f"{speed / (1024 * 1024):.2f} MB/s"
                
                wx.CallAfter(self.total_speed_text.SetLabel, f"总速度: {speed_str}")
                
                if self.start_time:
                    elapsed = current_time - self.start_time
                    hours, remainder = divmod(elapsed, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    time_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
                    wx.CallAfter(self.elapsed_time_text.SetLabel, f"耗时: {time_str}")
    
    def update_status(self, message):
        if self.stop_event.is_set():
            return
        wx.CallAfter(self.status_text.SetLabel, message)
    
    def log_message(self, message):
        if self.stop_event.is_set():
            return
        wx.CallAfter(self.log_text.AppendText, message + "\n")
    
    def generate_chunk_filename(self, base_filename, chunk_index):
        name, ext = os.path.splitext(base_filename)
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"{name}_part{chunk_index}_{random_str}{ext}"
    
    def unlock_file(self, filepath):
        try:
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel32.MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
            kernel32.MoveFileExW.restype = wintypes.BOOL
            
            MOVEFILE_DELAY_UNTIL_REBOOT = 0x00000004
            result = kernel32.MoveFileExW(filepath, None, MOVEFILE_DELAY_UNTIL_REBOOT)
            
            if not result:
                error_code = ctypes.get_last_error()
                self.log_message(f"解锁文件失败，错误代码: {error_code}")
                return False
            
            return True
        except Exception as e:
            self.log_message(f"解锁文件异常: {str(e)}")
            return False
    
    def safe_remove_file(self, filepath):
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                if os.path.exists(filepath):
                    gc.collect()
                    os.remove(filepath)
                    return True
            except Exception as e:
                if attempt < max_attempts - 1:
                    self.log_message(f"删除文件 {filepath} 失败 (尝试 {attempt+1}/{max_attempts}): {str(e)}")
                    time.sleep(1)
                else:
                    if self.unlock_file(filepath):
                        self.log_message(f"已标记文件 {filepath} 在系统重启后删除")
                    else:
                        self.log_message(f"无法删除文件 {filepath}: {str(e)}")
                    return False
        return False
    
    def download_chunk(self, url, chunk_file, byte_range, thread_index):
        if self.stop_event.is_set():
            return
        
        headers = {'Range': f'bytes={byte_range[0]}-{byte_range[1]}'}
        retry = 0
        
        while retry < self.retry_count and not self.stop_event.is_set():
            try:
                with requests.Session() as session:
                    session.mount(url, requests.adapters.HTTPAdapter(max_retries=1))
                    
                    with session.get(
                        url, 
                        headers=headers, 
                        stream=True, 
                        timeout=(self.timeout, self.timeout),
                        verify=not self.disable_ssl
                    ) as r:
                        r.raise_for_status()
                        total_size = byte_range[1] - byte_range[0] + 1
                        downloaded = 0
                        
                        if os.path.exists(chunk_file):
                            downloaded = os.path.getsize(chunk_file)
                            if downloaded > 0:
                                headers['Range'] = f'bytes={byte_range[0] + downloaded}-{byte_range[1]}'
                                r = session.get(
                                    url, 
                                    headers=headers, 
                                    stream=True, 
                                    timeout=(self.timeout, self.timeout),
                                    verify=not self.disable_ssl
                                )
                                for _ in range(downloaded // 8192):
                                    next(r.iter_content(chunk_size=8192))
                        
                        with open(chunk_file, 'ab' if downloaded > 0 else 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if self.stop_event.is_set():
                                    f.flush()
                                    break
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    with self.lock:
                                        self.total_downloaded += len(chunk)
                                    progress = int((downloaded / total_size) * 100)
                                    self.update_progress(thread_index, progress)
                        
                        if downloaded == total_size:
                            with self.lock:
                                self.completed_chunks[thread_index] = True
                            self.log_message(f"分块 {thread_index} 下载完成")
                        
                        break
            except Exception as e:
                retry += 1
                if retry < self.retry_count and not self.stop_event.is_set():
                    self.log_message(f"下载块 {byte_range} 出错 (尝试 {retry}/{self.retry_count}): {str(e)}")
                    time.sleep(2)
                elif not self.stop_event.is_set():
                    self.log_message(f"下载块 {byte_range} 失败: {str(e)}")
                    return
    
    def start_download(self):
        if self.stop_event.is_set():
            return
        
        self.start_time = time.time()
        
        try:
            self.update_status("重定向中")
            self.log_message("正在处理重定向...")
            
           
            session = requests.Session()
           
            session.max_redirects = 16
          
            with session.get(
                self.url, 
                allow_redirects=True, 
                timeout=self.timeout, 
                verify=not self.disable_ssl,
                stream=True 
            ) as r:
              
                final_url = r.url
                
                if final_url != self.url:
                    self.log_message(f"已重定向到: {final_url}")
                    self.url = final_url 
            response = requests.head(self.url, timeout=self.timeout, verify=not self.disable_ssl)
            self.file_size = int(response.headers.get('content-length', 0))
            self.update_status(f"文件大小: {self.file_size} 字节,合{self.file_size / 1024 / 1024}MB")
            
            self.temp_dir = os.path.join(self.save_path, "temp")
            os.makedirs(self.temp_dir, exist_ok=True)
            
            self.chunk_files = []
            for i in range(self.thread_count):
                chunk_file = os.path.join(self.temp_dir, self.generate_chunk_filename(self.filename, i))
                self.chunk_files.append(chunk_file)
            
            chunk_size = self.file_size // self.thread_count
            ranges = []
            for i in range(self.thread_count):
                start = i * chunk_size
                end = start + chunk_size - 1 if i < self.thread_count - 1 else self.file_size - 1
                ranges.append((start, end))
            
            self.threads = []
            for i in range(self.thread_count):
                t = threading.Thread(
                    target=self.download_chunk, 
                    args=(self.url, self.chunk_files[i], ranges[i], i)
                )
                self.threads.append(t)
                t.start()
            
            for t in self.threads:
                t.join(timeout=300)
            
            all_completed = all(self.completed_chunks)
            
            if not self.stop_event.is_set() and all_completed:
                end_time = time.time()
                total_time = end_time - self.start_time
                hours, remainder = divmod(total_time, 3600)
                minutes, seconds = divmod(remainder, 60)
                time_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
                
                with open(os.path.join(self.save_path, self.filename), 'wb') as outfile:
                    for chunk_file in self.chunk_files:
                        if os.path.exists(chunk_file):
                            with open(chunk_file, 'rb') as infile:
                                outfile.write(infile.read())
                            self.safe_remove_file(chunk_file)
                
                downloaded_size = os.path.getsize(os.path.join(self.save_path, self.filename))
                if downloaded_size == self.file_size:
                    self.update_status("下载结束")
                    self.log_message(f"所有文件块已合并！下载结束。总耗时: {time_str}")
                    self.log_message(f"文件大小验证通过！ {downloaded_size} 字节")
                    if self.completion_callback:
                        wx.CallAfter(self.completion_callback, True, downloaded_size)
                else:
                    self.update_status("下载完成但文件大小不匹配")
                    self.log_message(f"警告: 下载的文件大小 ({downloaded_size} 字节) 与服务器报告的大小 ({self.file_size} 字节) 不匹配")
                    if self.completion_callback:
                        wx.CallAfter(self.completion_callback, False, downloaded_size)
                wx.CallAfter(self.elapsed_time_text.SetLabel, f"总耗时: {time_str}")
            elif not self.stop_event.is_set():
                self.update_status("下载未完成，部分分块失败")
                self.log_message("警告: 部分分块下载失败，请检查网络连接并重试")
            
                if self.completion_callback:
                    wx.CallAfter(self.completion_callback, False, 0)
        except Exception as e:
            if not self.stop_event.is_set():
                self.update_status(f"下载出错: {str(e)}")
                self.log_message(f"错误: {str(e)}")
     
                if self.completion_callback:
                    wx.CallAfter(self.completion_callback, False, 0)
    
    def on_close(self, event):
        self.downloading = False
        self.stop_event.set()
        self.update_status("正在停止下载...")
        
        for t in self.threads:
            if t.is_alive():
                t.join(timeout=0.5)
        
        if self.temp_dir and os.path.exists(self.temp_dir):
            for file in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, file)
                self.safe_remove_file(file_path)
            
            try:
                if not os.listdir(self.temp_dir):
                    os.rmdir(self.temp_dir)
            except Exception as e:
                self.log_message(f"无法删除临时目录 {self.temp_dir}: {str(e)}")
        
        if self.completion_callback:
            final_file_path = os.path.join(self.save_path, self.filename)
            if os.path.exists(final_file_path):
                file_size = os.path.getsize(final_file_path)
            
                wx.CallAfter(self.completion_callback, False, file_size)
            else:
                wx.CallAfter(self.completion_callback, False, 0)
        self.Destroy()

class DownloadApp(wx.App):
    def OnInit(self):
        return True

def download_window(url, filename, save_path, thread_count=4, disable_ssl=False, completion_callback=None):
    app = DownloadApp()
    if thread_count > 16:
        wx.MessageBox("线程数超过16可能造成卡顿，请勿用大于文件大小的线程下载小文件", "警告", wx.OK)
        
    frame = DownloadFrame(url, filename, save_path, thread_count, disable_ssl, completion_callback)
    app.SetTopWindow(frame)
    app.MainLoop()





if __name__ == "__main__":
    url = ""
    filename = ""
    save_path = os.getcwd()
    thread_count = 64
    disable_ssl = True
    download_window(url, filename, save_path, thread_count, disable_ssl)
