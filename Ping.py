# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import wx
import subprocess
import threading
import sys
import psutil
import os
def PingPanel(parent):
    panel = parent
    ping_process = None
    stop_event = threading.Event()

    parent_font = parent.GetFont()


    vbox = wx.BoxSizer(wx.VERTICAL)

    hbox_input = wx.BoxSizer(wx.HORIZONTAL)

    title_label = wx.StaticText(panel, label="Ping一个目标")

    title_font = parent_font.Scaled(1.2)
    title_label.SetFont(title_font)
    vbox.Add(title_label, 0, wx.ALL | wx.EXPAND, 10)
    target_label = wx.StaticText(panel, label="目标地址:")

    target_label.SetFont(parent_font)
    hbox_input.Add(target_label, 0, wx.ALL | wx.CENTER, 5)


    target_text = wx.TextCtrl(panel)

    target_text.SetFont(parent_font)
    hbox_input.Add(target_text, 1, wx.ALL | wx.EXPAND, 5)


    packet_size_label = wx.StaticText(panel, label="包大小(字节):")

    packet_size_label.SetFont(parent_font)
    hbox_input.Add(packet_size_label, 0, wx.ALL | wx.CENTER, 5)


    packet_size_text = wx.TextCtrl(panel, value="32", size=(60, -1)) 
  
    packet_size_text.SetFont(parent_font)
    hbox_input.Add(packet_size_text, 0, wx.ALL, 5)

    ping_count_label = wx.StaticText(panel, label="次数:")
 
    ping_count_label.SetFont(parent_font)
    hbox_input.Add(ping_count_label, 0, wx.ALL | wx.CENTER, 5)


    ping_count_text = wx.TextCtrl(panel, value="4", size=(60, -1))
   
    ping_count_text.SetFont(parent_font)
    hbox_input.Add(ping_count_text, 0, wx.ALL, 5)

    
    if os.path.exists("./icons/run.png"):
        try:
            ping_button = wx.BitmapButton(panel, bitmap=wx.Bitmap("./icons/run.png"))
            ping_button.SetToolTip("开始 Ping")
        except:
            ping_button = wx.Button(panel, label="开始 Ping")
    else:
        ping_button = wx.Button(panel, label="开始 Ping")
        

    ping_button.SetFont(parent_font)
    hbox_input.Add(ping_button, 0, wx.ALL, 5)

    if os.path.exists("./icons/stop.png"):
        try:
            stop_button = wx.BitmapButton(panel, bitmap=wx.Bitmap("./icons/stop.png"))
            stop_button.SetToolTip("停止 Ping")
        except:
            stop_button = wx.Button(panel, label="停止 Ping")
    else:
        stop_button = wx.Button(panel, label="停止 Ping")           
        


    hbox_input.Add(stop_button, 0, wx.ALL, 5)

    vbox.Add(hbox_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)


    result_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)

    result_text.SetFont(parent_font)
    vbox.Add(result_text, 1, wx.ALL | wx.EXPAND, 10)


    panel.SetSizer(vbox)

    def run_ping():
        nonlocal ping_process
        target = target_text.GetValue().strip()
        packet_size = packet_size_text.GetValue().strip()
        ping_count = ping_count_text.GetValue().strip()

        if not target:
            wx.MessageBox("请输入目标地址", "提示", wx.OK | wx.ICON_INFORMATION)
            return
        try:
            packet_size = int(packet_size)
            ping_count = int(ping_count)
        except ValueError:
            wx.MessageBox("包大小和 Ping 次数必须是整数", "提示", wx.OK | wx.ICON_INFORMATION)
            return

        try:
            if sys.platform.startswith('win'):
                ping_command = ['ping', '-n', str(ping_count), '-l', str(packet_size), target]
            else:
                ping_command = ['ping', '-c', str(ping_count), '-s', str(packet_size - 8), target]  # Linux 减去 8 字节头部
            ping_process = subprocess.Popen(ping_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while not stop_event.is_set():
                output = ping_process.stdout.readline()
                if output == '' and ping_process.poll() is not None:
                    break
                if output:
                    wx.CallAfter(result_text.AppendText, output)
            _, stderr = ping_process.communicate()
            if stderr:
                wx.CallAfter(result_text.AppendText, stderr)
        except Exception as e:
            wx.CallAfter(result_text.AppendText, f"发生错误: {str(e)}\n")
        finally:
            wx.CallAfter(ping_button.Enable)
            wx.CallAfter(stop_button.Disable)
            ping_process = None
            stop_event.clear()

    def on_ping_button(event):
        ping_button.Disable()
        stop_button.Enable()
        result_text.Clear()
        stop_event.clear()
        ping_thread = threading.Thread(target=run_ping, daemon=True)
        ping_thread.start()

    def on_stop_button(event):
        nonlocal ping_process
        stop_event.set()
        if ping_process:
            try:
                parent = psutil.Process(ping_process.pid)
                children = parent.children(recursive=True)
                for child in children:
                    child.kill()
                parent.kill()
                psutil.wait_procs([parent] + children)
            except psutil.NoSuchProcess:
                pass
            ping_process = None
        ping_button.Enable()
        stop_button.Disable()

    ping_button.Bind(wx.EVT_BUTTON, on_ping_button)
    stop_button.Bind(wx.EVT_BUTTON, on_stop_button)

    return panel
