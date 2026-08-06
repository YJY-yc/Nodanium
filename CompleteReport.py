# Copyright (c) 2023-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import wx
import os
import shutil
import subprocess
import platform
from typing import Optional
from FileIcon import get_file_icon
class DownloadCompleteReport(wx.Dialog):
    """
    下载完成报告窗口 - Ubuntu 优化版
    使用 XDND 协议实现文件拖拽
    """
    
    def __init__(self, parent: Optional[wx.Window], 
                 filename: str, 
                 save_path: str, 
                 file_size: int, 
                 time_cost: str,
                 average_speed: float,
                 speed_unit: str = "MB/s"): 
        super().__init__(parent, title="下载完成", size=(450, 380), style=wx.DEFAULT_DIALOG_STYLE)
        
        self.filename = filename
        self.save_path = save_path
        self.full_path = os.path.join(save_path, filename)
        self.speed_unit = speed_unit
  
        self.os_type = platform.system()
        self.is_linux = self.os_type == "Linux"
        self.is_windows = self.os_type == "Windows"
        
    
        self.drop_target = FileDropTarget(self)
        self.SetDropTarget(self.drop_target)
        
        self.create_ui()
        self.set_data(file_size, time_cost, average_speed)
        self.Centre()
        
    def create_ui(self):
        """创建UI布局"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
    
        title_text = wx.StaticText(self, label="下载完成")
        title_font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title_text.SetFont(title_font)
        main_sizer.Add(title_text, flag=wx.CENTER | wx.TOP | wx.BOTTOM, border=15)
        
     
        main_sizer.Add(wx.StaticLine(self), flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)
        

        content_box = wx.BoxSizer(wx.HORIZONTAL)
        
   
        self.thumbnail_panel = wx.Panel(self, size=(100, 100), style=wx.BORDER_SUNKEN)
        self.thumbnail_panel.SetBackgroundColour(wx.Colour(245, 245, 245))
        

        self.drag_button = wx.Button(self.thumbnail_panel,size=(100, 100))
        self.drag_button.SetBackgroundColour(wx.Colour(245, 245, 245))
        self.drag_button.Bind(wx.EVT_BUTTON, self.on_drag_button_click)
        
    
        icon = self._create_file_icon()
        self.drag_button.SetBitmap(icon)
        self.drag_button.SetBitmapPosition(wx.BOTTOM)
        
        content_box.Add(self.thumbnail_panel, flag=wx.ALL, border=10)
        
        # 文件信息区域
        info_box = wx.BoxSizer(wx.VERTICAL)
        
        # 文件名
        name_box = wx.BoxSizer(wx.HORIZONTAL)
        name_label = wx.StaticText(self, label="文件名:")
        self.name_value = wx.StaticText(self, label=self.filename)
        name_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.name_value.SetFont(name_font)
        name_box.Add(name_label, flag=wx.RIGHT, border=10)
        name_box.Add(self.name_value, proportion=1)
        info_box.Add(name_box, flag=wx.EXPAND | wx.BOTTOM, border=6)
        
        # 文件大小
        size_box = wx.BoxSizer(wx.HORIZONTAL)
        size_label = wx.StaticText(self, label="文件大小:")
        self.size_value = wx.StaticText(self, label="")
        size_box.Add(size_label, flag=wx.RIGHT, border=10)
        size_box.Add(self.size_value, proportion=1)
        info_box.Add(size_box, flag=wx.EXPAND | wx.BOTTOM, border=6)
        
        # 耗时
        time_box = wx.BoxSizer(wx.HORIZONTAL)
        time_label = wx.StaticText(self, label="耗时:")
        self.time_value = wx.StaticText(self, label="")
        time_box.Add(time_label, flag=wx.RIGHT, border=10)
        time_box.Add(self.time_value, proportion=1)
        info_box.Add(time_box, flag=wx.EXPAND | wx.BOTTOM, border=6)
        
        # 平均速度
        speed_box = wx.BoxSizer(wx.HORIZONTAL)
        speed_label = wx.StaticText(self, label="平均速度:")
        self.speed_value = wx.StaticText(self, label="")
        speed_box.Add(speed_label, flag=wx.RIGHT, border=10)
        speed_box.Add(self.speed_value, proportion=1)
        info_box.Add(speed_box, flag=wx.EXPAND | wx.BOTTOM, border=6)
        
        # 保存路径
        path_box = wx.BoxSizer(wx.HORIZONTAL)
        path_label = wx.StaticText(self, label="保存路径:")
        self.path_value = wx.StaticText(self, label=self.save_path)
        path_font = wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL)
        self.path_value.SetFont(path_font)
        self.path_value.SetForegroundColour(wx.Colour(100, 100, 100))
        path_box.Add(path_label, flag=wx.RIGHT, border=10)
        path_box.Add(self.path_value, proportion=1)
        info_box.Add(path_box, flag=wx.EXPAND)
        
        content_box.Add(info_box, proportion=1, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=10)
        main_sizer.Add(content_box, flag=wx.EXPAND)
        
        # 分隔线
        main_sizer.Add(wx.StaticLine(self), flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)
        
   
        
        # 按钮区域
        button_box = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btn_open = wx.Button(self, label="打开文件")
        self.btn_open.Bind(wx.EVT_BUTTON, self.on_open_file)
        button_box.Add(self.btn_open, flag=wx.RIGHT, border=10)
        
        self.btn_open_folder = wx.Button(self, label="打开文件夹")
        self.btn_open_folder.Bind(wx.EVT_BUTTON, self.on_open_folder)
        button_box.Add(self.btn_open_folder, flag=wx.RIGHT, border=10)
        
        self.btn_copy_path = wx.Button(self, label="复制路径")
        self.btn_copy_path.Bind(wx.EVT_BUTTON, self.on_copy_path)
        button_box.Add(self.btn_copy_path, flag=wx.RIGHT, border=10)
        
        self.btn_close = wx.Button(self, label="关闭")
        self.btn_close.Bind(wx.EVT_BUTTON, self.on_close)
        button_box.Add(self.btn_close)
        
        main_sizer.Add(button_box, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        
        self.SetSizer(main_sizer)
        self.Layout()
        
    def _create_file_icon(self) -> wx.Bitmap:
        """从FileIcon获取系统文件图标"""
        
        bmp = get_file_icon(self.full_path, size=64)
        
  
        if bmp is None:
            bmp = wx.Bitmap(64, 64)
            dc = wx.MemoryDC(bmp)
            dc.SetBackground(wx.Brush(wx.Colour(240, 240, 240)))
            dc.Clear()
            dc.SelectObject(wx.NullBitmap)
        
        return bmp
        
    def set_data(self, file_size: int, time_cost: str, average_speed: float):
        """设置数据显示"""
        self.size_value.SetLabel(self._format_size(file_size))
        self.time_value.SetLabel(time_cost)
        self.speed_value.SetLabel(self._format_speed(average_speed, self.speed_unit))
        
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KiB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MiB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GiB"
        
    def _format_speed(self, speed_bps: float, unit: str = "MB/s") -> str:
        """格式化速度"""
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
            elif speed_bps < 1024 * 1024:
                return f"{speed_bps / 1024:.2f} KiB/s"
            else:
                return f"{speed_bps / (1024 * 1024):.2f} MiB/s"
        
        elif unit == "MBPS":
   
            speed_bps = speed_bps * 8
            if speed_bps < 1000:
                return f"{speed_bps:.2f} bps"
            elif speed_bps < 1000 ** 2:
                return f"{speed_bps / 1000:.2f} Kbps"
            else:
                return f"{speed_bps / (1000**2):.2f} Mbps"
        
        else:
            return self._format_speed(speed_bps, "MB/s")
    
    def _open_file_with_default_app(self, path: str):
        """跨平台打开文件/文件夹"""
        try:
            if self.is_windows:
                os.startfile(path)
            else:
                if platform.system() == "Darwin":
                    subprocess.run(["open", path], check=True)
                else:
                    subprocess.run(["xdg-open", path], check=True)
            return True
        except Exception as e:
            return str(e)
    
    def on_drag_button_click(self, event):
        """拖拽按钮点击处理 - 使用剪贴板实现复制功能"""
        if not os.path.exists(self.full_path):
            wx.MessageBox("文件不存在", "错误", wx.OK | wx.ICON_ERROR)
            return
            
        # 将文件路径复制到剪贴板
        if self.is_linux:
            # Linux: 使用 xclip 命令
            try:
                process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', 'text/uri-list'], 
                                         stdin=subprocess.PIPE)
                process.communicate(input=f"file://{self.full_path}".encode('utf-8'))
                wx.MessageBox("文件路径已复制到剪贴板\n可粘贴到文件管理器中", "提示", wx.OK)
            except Exception as e:
                # 降级方案：复制纯文本路径
                text_data = wx.TextDataObject()
                text_data.SetText(self.full_path)
                if wx.TheClipboard.Open():
                    wx.TheClipboard.SetData(text_data)
                    wx.TheClipboard.Close()
                    wx.MessageBox("文件路径已复制到剪贴板", "提示", wx.OK)
                else:
                    wx.MessageBox(f"无法访问剪贴板: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
        else:
            # Windows: 使用标准剪贴板
            text_data = wx.TextDataObject()
            text_data.SetText(self.full_path)
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(text_data)
                wx.TheClipboard.Close()
                wx.MessageBox("文件路径已复制到剪贴板", "提示", wx.OK)
            else:
                wx.MessageBox("无法访问剪贴板", "错误", wx.OK | wx.ICON_ERROR)
        
    def on_copy_path(self, event):
        """复制文件路径到剪贴板"""
        text_data = wx.TextDataObject()
        text_data.SetText(self.full_path)
        
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(text_data)
            wx.TheClipboard.Close()
            wx.MessageBox("文件路径已复制", "提示", wx.OK)
        else:
            wx.MessageBox("无法访问剪贴板", "错误", wx.OK | wx.ICON_ERROR)
            
    def on_open_file(self, event):
        """打开文件"""
        if os.path.exists(self.full_path):
            result = self._open_file_with_default_app(self.full_path)
            if result is not True:
                wx.MessageBox(f"无法打开文件: {result}", "错误", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("文件不存在", "错误", wx.OK | wx.ICON_ERROR)
            
    def on_open_folder(self, event):
        """打开所在文件夹"""
        if os.path.exists(self.save_path):
            result = self._open_file_with_default_app(self.save_path)
            if result is not True:
                wx.MessageBox(f"无法打开文件夹: {result}", "错误", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("文件夹不存在", "错误", wx.OK | wx.ICON_ERROR)
            
    def on_close(self, event):
        """关闭窗口"""
        self.Close()


class FileDropTarget(wx.DropTarget):
    """文件拖放目标处理"""
    
    def __init__(self, window):
        super().__init__()
        self.window = window
        
    def OnDropFiles(self, x, y, filenames):
        """处理拖放到窗口的文件"""
        if len(filenames) == 0:
            return False
            
        target_path = self.window.save_path
        
        for filename in filenames:
            try:
                base_name = os.path.basename(filename)
                target_full_path = os.path.join(target_path, base_name)
                
                counter = 1
                while os.path.exists(target_full_path):
                    name, ext = os.path.splitext(base_name)
                    target_full_path = os.path.join(target_path, f"{name}_{counter}{ext}")
                    counter += 1
                
                shutil.copy2(filename, target_full_path)
                wx.MessageBox(f"文件已成功复制到:\n{target_full_path}", "复制成功", wx.OK)
            except Exception as e:
                wx.MessageBox(f"复制失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
                
        return True

def show_download_complete_report(parent, filename, save_path, file_size, time_cost, average_speed, speed_unit="MB/s"):
    """显示下载完成报告窗口"""
    dlg = DownloadCompleteReport(parent, filename, save_path, file_size, time_cost, average_speed, speed_unit)
    dlg.ShowModal()
    dlg.Destroy()


# 测试入口

if __name__ == "__main__":
    app = wx.App(False)
    show_download_complete_report(
        parent=None,
        filename="1.rar",
        save_path="/home/yujy/下载",
        file_size=0,
        time_cost="1",
        average_speed=800000
    )
    app.MainLoop()