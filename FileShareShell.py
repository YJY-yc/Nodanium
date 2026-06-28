# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import wx
import os
import json
import time
import threading
import logging
import webbrowser
from TPort import start_file_server, stop_file_server

# 设置全局变量
server_thread = None

# 获取配置和目录信息
target_folder = os.path.join(os.getenv('APPDATA', ''), "Nodanium")
if not os.path.exists(target_folder):
    os.makedirs(target_folder)

# 读取配置
def load_config():
    config_path = os.path.join(target_folder, "config.json")
    default_config = {
        'font_size': 17,
        'list_button_size': 15,
        'font_name': "微软雅黑",
        'size': (300, 30),
        'size_button': (100, 30),
        'window_pos': (100, 20),  
        'window_size': [1020, 700],
        'high_dpi': True,
        'share_path': "D:/SharedFiles",
        'default_port': 1524,
        'auto_open_browser': True
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                default_config.update(config)
        except:
            pass
    else:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
    
    return default_config

config = load_config()
FontSize = config['font_size']
fontname = config['font_name']

def MainPanel(parent):

    panel_sizer = wx.BoxSizer(wx.VERTICAL)
    
    title_label = wx.StaticText(parent, label="转发文件到端口")
    title_label.SetFont(wx.Font(FontSize + 7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=fontname))
    panel_sizer.Add(title_label, 0, wx.ALL | wx.EXPAND, 10)

    hbox_port = wx.BoxSizer(wx.HORIZONTAL)
    port_label = wx.StaticText(parent, label="端口号:")
    port_label.SetFont(wx.Font(FontSize, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=fontname))
    port_text = wx.TextCtrl(parent, size=(100, -1))
    port_text.SetValue(str(config['default_port']))
    
    hbox_port.Add(port_label, 0, wx.ALL | wx.CENTER, 5)
    hbox_port.Add(port_text, 0, wx.ALL | wx.EXPAND, 5)
    panel_sizer.Add(hbox_port, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
    
    hbox_file = wx.BoxSizer(wx.HORIZONTAL)
    file_label = wx.StaticText(parent, label="文件路径:")
    file_label.SetFont(wx.Font(FontSize, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=fontname))
    file_text = wx.TextCtrl(parent, size=(200, -1))
    link_icon = wx.Bitmap("./icons/view.png", wx.BITMAP_TYPE_PNG)
    browse_button = wx.Button(parent, label="浏览...", size=(-1, -1))
    browse_button.SetBitmap(link_icon, wx.LEFT)
    
    hbox_file.Add(file_label, 0, wx.ALL | wx.CENTER, 5)
    hbox_file.Add(file_text, 1, wx.ALL | wx.EXPAND, 5)
    hbox_file.Add(browse_button, 0, wx.ALL | wx.EXPAND, 5)
    panel_sizer.Add(hbox_file, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
    
    # 控制按钮
    hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)
    link_icon = wx.Bitmap("./icons/run.png", wx.BITMAP_TYPE_PNG)
    start_button = wx.Button(parent, label="启动", size=(-1, -1))
    start_button.SetBitmap(link_icon, wx.LEFT)
    link_icon = wx.Bitmap("./icons/stop.png", wx.BITMAP_TYPE_PNG)
    stop_button = wx.Button(parent, label="停止", size=(-1, -1))
    stop_button.SetBitmap(link_icon, wx.LEFT)
    
    stop_button.Disable()
    hbox_buttons.Add(start_button, 0, wx.ALL | wx.EXPAND, 5)
    hbox_buttons.Add(stop_button, 0, wx.ALL | wx.EXPAND, 5)
    
    panel_sizer.Add(hbox_buttons, 0, wx.ALL | wx.ALIGN_LEFT, 10)
    
    # 日志显示区域
    log_text = wx.TextCtrl(parent, style=wx.TE_MULTILINE | wx.TE_READONLY)
    log_text.SetFont(wx.Font(FontSize - 4, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=fontname))
    panel_sizer.Add(log_text, 1, wx.EXPAND | wx.ALL, 10)
    
    # 绑定事件处理函数
    def on_browse(event):
        dlg = wx.FileDialog(parent, "选择要共享的文件", wildcard="All files (*.*)|*.*")
        if dlg.ShowModal() == wx.ID_OK:
            file_text.SetValue(dlg.GetPath())
        dlg.Destroy()
            
    def on_start(event):
        global server_thread
        try:
            port = int(port_text.GetValue())
        except ValueError:
            wx.MessageBox("请输入有效的端口号！", "错误", wx.OK | wx.ICON_ERROR)
            return
        
        file_path = file_text.GetValue()
        
        if not os.path.exists(file_path):
            wx.MessageBox("文件不存在！", "错误", wx.OK | wx.ICON_ERROR)
            return
        
        # 获取本机IP地址
        import socket
        hostname = socket.gethostname()
        addrinfo = socket.getaddrinfo(hostname, None)
        
        ip_addresses = []
        for addr in addrinfo:
            if addr[0] == socket.AF_INET:  # 只获取IPv4地址
                ip_address = addr[4][0]
                ip_addresses.append(ip_address)
        
        if not ip_addresses:
            wx.MessageBox("无法获取IP地址", "错误", wx.OK | wx.ICON_ERROR)
            return
        
        # 显示服务器信息
        wx.CallAfter(log_text.AppendText, f"服务器启动在以下地址:\n")
        for ip in ip_addresses:
            wx.CallAfter(log_text.AppendText, f"{ip}:{port}\n")
        
        # 保存到历史记录
        history_path = os.path.join(target_folder, "history.json")
        history = []
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except:
                pass
        
        history.append({
            "url": f"{ip_addresses[0]}:{port}", 
            "filename": os.path.basename(file_path),
            "time": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        
        try:
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
        except:
            pass
        
        start_button.Disable()
        stop_button.Enable()
        
        # 启动文件服务器线程
        server_thread = threading.Thread(
            target=start_file_server,
            args=(port, file_path, os.path.dirname(file_path), lambda msg: wx.CallAfter(log_text.AppendText, msg)),
            daemon=True
        )
        server_thread.start()
        
        # 自动打开浏览器
        if config.get('auto_open_browser', True):
            webbrowser.open(f"http://localhost:{port}")
            logging.info(f'自动打开浏览器: http://localhost:{port}')
    
    def on_stop(event):
        stop_file_server(lambda msg: wx.CallAfter(log_text.AppendText, msg))
        start_button.Enable()
        stop_button.Disable()
    
    # 绑定按钮事件
    browse_button.Bind(wx.EVT_BUTTON, on_browse)
    start_button.Bind(wx.EVT_BUTTON, on_start)
    stop_button.Bind(wx.EVT_BUTTON, on_stop)
    
    # 设置面板的布局
    parent.SetSizer(panel_sizer)
    
    return parent

if __name__ == "__main__":
    # 用于测试的代码
    app = wx.App()
    frame = wx.Frame(None, title="文件共享", size=(500, 400))
    panel = wx.Panel(frame)
    MainPanel(panel)
    frame.Center()
    frame.Show()
    app.MainLoop()
