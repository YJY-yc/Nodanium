# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import threading
import wx
import psutil
from wx.lib.newevent import NewEvent
import socket
from collections import defaultdict

ScanCompleteEvent, EVT_SCAN_COMPLETE = NewEvent()

def get_ports():
    port_info = defaultdict(list)
    for conn in psutil.net_connections(kind='inet'):
        if conn.laddr:
            port = conn.laddr.port
            protocol = 'TCP' if conn.type == socket.SOCK_STREAM else 'UDP'
            status = conn.status if conn.status else 'N/A'
            pid = conn.pid if conn.pid else 'N/A'
            
            process_name = 'N/A'
            if pid != 'N/A':
                try:
                    process = psutil.Process(pid)
                    process_name = process.name()
                except:
                    process_name = 'N/A'
            
            local_addr = f"{conn.laddr.ip}:{conn.laddr.port}"
            remote_addr = 'N/A'
            if conn.raddr:
                remote_addr = f"{conn.raddr.ip}:{conn.raddr.port}"
            
            port_info[port].append({
                'port': port,
                'protocol': protocol,
                'status': status,
                'pid': pid,
                'name': process_name,
                'local_addr': local_addr,
                'remote_addr': remote_addr
            })
    
    result = []
    for port, connections in port_info.items():
        result.extend(connections)
    
    return result

def create_list_ctrl(parent):
   
    list_ctrl = wx.ListCtrl(parent, style=wx.LC_REPORT)
    list_ctrl.InsertColumn(0, "端口", width=100)
    list_ctrl.InsertColumn(1, "协议", width=100)
    list_ctrl.InsertColumn(2, "状态", width=150)
    list_ctrl.InsertColumn(3, "PID", width=120)
    list_ctrl.InsertColumn(4, "进程名", width=180)
    list_ctrl.InsertColumn(5, "本地地址", width=250)
    list_ctrl.InsertColumn(6, "远程地址", width=250)
    
    return list_ctrl

def create_search_panel(parent):
    
    panel = wx.Panel(parent)
    sizer = wx.BoxSizer(wx.HORIZONTAL)
    
    refresh_btn = wx.Button(panel, label="刷新")
    search_label = wx.StaticText(panel, label="搜索:")
    search_text = wx.TextCtrl(panel)
    
    sizer.Add(refresh_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    sizer.Add(search_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    sizer.Add(search_text, 1, wx.ALL | wx.EXPAND, 5)
    
    panel.SetSizer(sizer)
    return panel, refresh_btn, search_text

def create_title(parent):
    
    panel = wx.Panel(parent)
    sizer = wx.BoxSizer(wx.VERTICAL)
    
    title = wx.StaticText(panel, label="端口占用情况")
    font = title.GetFont()
    font.SetPointSize(17)
    title.SetFont(font)

    sizer.Add(title, 0, wx.ALL , 10)
    panel.SetSizer(sizer)
    
    return panel

def port_manager_panel(parent):
    panel = parent
    main_sizer = wx.BoxSizer(wx.VERTICAL)
    
    title_panel = create_title(panel)
    main_sizer.Add(title_panel, 0, wx.EXPAND)
    
    search_panel, refresh_btn, search_text = create_search_panel(panel)
    main_sizer.Add(search_panel, 0, wx.EXPAND)
    
    list_ctrl = create_list_ctrl(panel)
    main_sizer.Add(list_ctrl, 1, wx.ALL | wx.EXPAND, 5)
    
    panel.SetSizer(main_sizer)
    

    panel.Bind(EVT_SCAN_COMPLETE, lambda event: update_list(list_ctrl, event.data, search_text.GetValue()))
    
    
    def refresh_list(event=None):
        list_ctrl.DeleteAllItems()
   
        thread = threading.Thread(target=scan_ports_in_background, args=(panel,))
        thread.start()
    

    def scan_ports_in_background(panel):
        port_data = get_ports()

        wx.PostEvent(panel, ScanCompleteEvent(data=port_data))
    

    def update_list(list_ctrl, port_data, search_term):
        for i, info in enumerate(port_data):
            if (search_term and 
                search_term not in str(info['port']).lower() and
                search_term not in info['protocol'].lower() and
                search_term not in info['status'].lower() and
                search_term not in str(info['pid']).lower() and
                search_term not in info['name'].lower() and
                search_term not in info['local_addr'].lower() and
                search_term not in info['remote_addr'].lower()):
                continue
            
            index = list_ctrl.InsertItem(i, str(info['port']))
            list_ctrl.SetItem(index, 1, info['protocol'])
            list_ctrl.SetItem(index, 2, info['status'])
            list_ctrl.SetItem(index, 3, str(info['pid']))
            list_ctrl.SetItem(index, 4, info['name'])
            list_ctrl.SetItem(index, 5, info['local_addr'])
            list_ctrl.SetItem(index, 6, info['remote_addr'])
    
    # 右键菜单
    def on_right_click(event):
        item = list_ctrl.HitTest(event.GetPosition())[0]
        if item != wx.NOT_FOUND:
            menu = wx.Menu()
        
            columns = ['端口', '协议', '状态', 'PID', '进程名', '本地地址', '远程地址']
            for i, col in enumerate(columns):
                copy_item = menu.Append(wx.ID_ANY, f'复制{col}')
                panel.Bind(wx.EVT_MENU, lambda e, idx=i, item=item: copy_cell_content(list_ctrl, item, idx), copy_item)
            
            kill_item = menu.Append(wx.ID_ANY, '结束选中进程')
            panel.Bind(wx.EVT_MENU, lambda e, item=item: kill_process(list_ctrl, item), kill_item)
            
            list_ctrl.PopupMenu(menu)
            menu.Destroy()
    
 
    def copy_cell_content(list_ctrl, item, col):
        content = list_ctrl.GetItemText(item, col)
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(content))
            wx.TheClipboard.Close()
    
   
    def kill_process(list_ctrl, item):
        pid = list_ctrl.GetItemText(item, 3)
        try:
            pid = int(pid)
            process = psutil.Process(pid)
            process.terminate()
            
            refresh_list()
        except (ValueError, psutil.NoSuchProcess):
            wx.MessageBox('无法结束进程，请检查PID是否有效', '错误', wx.OK | wx.ICON_ERROR)
        except psutil.AccessDenied:
            wx.MessageBox('权限不足，无法结束进程', '错误', wx.OK | wx.ICON_ERROR)
    
    list_ctrl.Bind(wx.EVT_RIGHT_DOWN, on_right_click)
    
    refresh_btn.Bind(wx.EVT_BUTTON, refresh_list)
    search_text.Bind(wx.EVT_TEXT, refresh_list)
    
    wx.CallAfter(refresh_list)
    
    return panel

def create_standalone_app():
    
    app = wx.App()
    frame = wx.Frame(None, title="端口管理器", size=(800, 600))
    
 
    port_panel = port_manager_panel(wx.Panel(frame))
    

    frame_sizer = wx.BoxSizer(wx.VERTICAL)
    frame_sizer.Add(port_panel, 1, wx.EXPAND)
    frame.SetSizer(frame_sizer)
    
    frame.Show()
    return app


if __name__ == "__main__":

    ports = get_ports()
    print(f" {len(ports)} 个端口占用")
    

    app = create_standalone_app()
    app.MainLoop()