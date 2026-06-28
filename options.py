# Copyright (c) 2024-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import wx
import os
import json
import sys

config = {
    'font_size': 17,
    'list_button_size': 15,
    'font_name': "微软雅黑",
    'size': (300, 30),
    'size_button': (100, 30),
    'window_pos': (100, 20),  
    'window_size': [800, 550],
    'high_dpi':True
}

def on_go_to_file(event):
    if os.path.isdir(dirs):
        os.startfile(dirs)


def options(event):
    global dirs
    global Pos
    Pos = config.get('window_pos', (100, 20))
    options_window = wx.Frame(None, title="首选项", size=(400, 600))
    options_window.SetBackgroundColour(wx.Colour(255, 255, 255))
    roaming_path = os.getenv('APPDATA')
    target_folder = os.path.join(roaming_path, "Nodanium")
    config_path = os.path.join(target_folder, "config.json")
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

    config_path = os.path.join(target_folder, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config.update(json.load(f))
        except:
        
            pass
    else:
    
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)


    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
    print(target_folder)
    if not os.path.exists(os.path.join(target_folder, "dir.txt")):
        with open(os.path.join(target_folder, "dir.txt"), "w") as f:
            f.write("D:/Downloads/")
    with open(os.path.join(target_folder, "dir.txt"), "r") as f:
        dirs = f.read()

    def on_close(event):
        options_window.Destroy()
        event.Skip()

    options_window.Bind(wx.EVT_CLOSE, on_close)
    notebook = wx.Notebook(options_window)

    window = wx.Panel(notebook)
    window_sizer = wx.BoxSizer(wx.VERTICAL)


    font_label = wx.StaticText(window, label="选择字体:")
    font_choices = wx.FontEnumerator().GetFacenames()
    font_choice = wx.Choice(window, choices=font_choices)
    font_choice.SetStringSelection(config['font_name'])

    font_preview_label = wx.StaticText(window, label="字体浏览:")
    font_preview = wx.StaticText(window, label="中国智造，惠及全球ABC")

    def update_font_preview(event=None):
        selected_font = font_choice.GetStringSelection()
        font_preview.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                                     wx.FONTWEIGHT_NORMAL, faceName=selected_font))
        font_preview.SetLabel("中国智造，惠及全球ABC")

    font_choice.Bind(wx.EVT_CHOICE, update_font_preview)
    update_font_preview()

    font_size_label = wx.StaticText(window, label="字体大小:")
    font_size_ctrl = wx.SpinCtrl(window, value=str(config['font_size']), min=10, max=30)


    pos_label = wx.StaticText(window, label="窗口位置 XY:")
    pos_x_ctrl = wx.SpinCtrl(window, value=str(Pos[0]), min=0, max=1920)
    pos_y_ctrl = wx.SpinCtrl(window, value=str(Pos[1]), min=0, max=1080)
    pos_sizer = wx.BoxSizer(wx.HORIZONTAL)
    pos_sizer.Add(pos_x_ctrl, 1, wx.RIGHT, 5)
    pos_sizer.Add(pos_y_ctrl, 1)

    win_size_label = wx.StaticText(window, label="窗口大小:")
    win_ctrl = wx.SpinCtrl(window, value=str(config['window_size'][0]), min=400, max=1920)
    winht_ctrl = wx.SpinCtrl(window, value=str(config['window_size'][1]), min=300, max=1080)
    win_size_sizer = wx.BoxSizer(wx.HORIZONTAL)
    win_size_sizer.Add(win_ctrl, 1, wx.RIGHT, 5)
    win_size_sizer.Add(winht_ctrl, 1)
    #高DPI
    DPI_set = wx.CheckBox(window, label="使用高DPI获得更清晰的窗口")
    DPI_set.SetValue(config.get('high_dpi', True))

    window_sizer.Add(font_label, 0, wx.ALL | wx.EXPAND, 5)
    window_sizer.Add(font_choice, 0, wx.ALL | wx.EXPAND, 5)
    window_sizer.Add(font_preview_label, 0, wx.ALL | wx.EXPAND, 5)
    window_sizer.Add(font_preview, 0, wx.ALL | wx.EXPAND, 5)
    window_sizer.Add(font_size_label, 0, wx.ALL | wx.EXPAND, 5)
    window_sizer.Add(font_size_ctrl, 0, wx.ALL | wx.EXPAND, 5)
    window_sizer.Add(pos_label, 0, wx.ALL | wx.EXPAND, 5)
    window_sizer.Add(pos_sizer, 0, wx.ALL | wx.EXPAND, 5)
    window_sizer.Add(win_size_label, 0, wx.ALL | wx.EXPAND, 5)
    window_sizer.Add(win_size_sizer, 0, wx.ALL | wx.EXPAND, 5)
    window_sizer.Add(DPI_set, 0, wx.ALL | wx.EXPAND, 5)

    window.SetSizer(window_sizer)

    # 文件面板
    file_panel = wx.Panel(notebook)
    file_sizer = wx.BoxSizer(wx.VERTICAL)

    path_label = wx.StaticText(file_panel, label="当前下载路径:")
    path_text = wx.TextCtrl(file_panel, value=dirs)

    def on_browse(event):
        dialog = wx.DirDialog(file_panel, "选择下载文件夹",
                              style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        if dialog.ShowModal() == wx.ID_OK:
            new_path = dialog.GetPath()
            path_text.SetValue(new_path)
            global dirs
            dirs = new_path + "\\"
            with open(os.path.join(target_folder, "dir.txt"), "w") as f:
                f.write(dirs)
        dialog.Destroy()

    browse_button = wx.Button(file_panel, label="浏览...")
    link_to_2 = wx.Button(file_panel, label="检查文件路径",
                          style=wx.BORDER_NONE, size=(140, 30))
    link_to_2.SetForegroundColour(wx.Colour(0, 0, 255))
    link_to_2.SetBackgroundColour(wx.Colour(249, 249, 249))
    link_to_2.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    link_to_2.SetCursor(wx.Cursor(wx.CURSOR_HAND))
    link_to_2.Bind(wx.EVT_BUTTON, on_go_to_file)
    browse_button.Bind(wx.EVT_BUTTON, on_browse)

    file_sizer.Add(path_label, 0, wx.ALL | wx.EXPAND, 5)
    file_sizer.Add(path_text, 0, wx.ALL | wx.EXPAND, 5)
    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    btn_sizer.Add(browse_button, 0, wx.RIGHT, 5)
    btn_sizer.Add(link_to_2, 0)
    file_sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 5)

    file_panel.SetSizer(file_sizer)

    # 存储面板
    storage_panel = wx.Panel(notebook)
    storage_sizer = wx.BoxSizer(wx.VERTICAL)

    temp_size_label = wx.StaticText(storage_panel, label="临时文件大小:")
    temp_size_text = wx.StaticText(storage_panel, label="")

    def update_temp_size():
        temp_path = os.path.join(dirs, "temp")
        if os.path.exists(temp_path):
            total_size = sum(os.path.getsize(os.path.join(dirpath, filename))
                             for dirpath, _, filenames in os.walk(temp_path)
                             for filename in filenames)
            temp_size_text.SetLabel(f"{total_size / 1024 / 1024:.2f} MB")
        else:
            temp_size_text.SetLabel("0 MB")

    update_temp_size()

    def on_clear_temp(event):
        global dirs
        temp_path = os.path.join(dirs, "temp")
        if os.path.exists(temp_path):
            for root, _, files in os.walk(temp_path):
                for file in files:
                    try:
                        os.remove(os.path.join(root, file))
                    except:
                        pass
            wx.MessageBox("临时文件已清空", "提示", wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox("临时文件夹不存在", "提示", wx.OK | wx.ICON_INFORMATION)

    temp_path = os.path.join(dirs, "temp")
    if os.path.exists(temp_path):
        total_size = sum(os.path.getsize(os.path.join(dirpath, filename))
                         for dirpath, _, filenames in os.walk(temp_path)
                         for filename in filenames)
    try:
        clear_button = wx.Button(storage_panel, label="清空临时文件")
        if total_size > 0:
            clear_button.Bind(wx.EVT_BUTTON, on_clear_temp)
        else:
            clear_button.Disable()
        
    except:
        pass

    def on_clear_history(event):
        history_path = os.path.join(target_folder, "history.json")
        if os.path.exists(history_path):
            os.remove(history_path)
            wx.MessageBox("下载记录已清除", "提示", wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox("没有下载记录", "提示", wx.OK | wx.ICON_INFORMATION)

    clear_history_button = wx.Button(storage_panel, label="清除下载记录")
    clear_history_button.Bind(wx.EVT_BUTTON, on_clear_history)

    storage_sizer.Add(temp_size_label, 0, wx.ALL | wx.EXPAND, 5)
    storage_sizer.Add(temp_size_text, 0, wx.ALL | wx.EXPAND, 5)
    storage_sizer.Add(clear_button, 0, wx.ALL | wx.EXPAND, 5)

    storage_sizer.Add(clear_history_button, 0, wx.ALL | wx.EXPAND, 5)

    storage_panel.SetSizer(storage_sizer)

    # 端口面板
    port_panel = wx.Panel(notebook)
    port_sizer = wx.BoxSizer(wx.VERTICAL)

    port_label = wx.StaticText(port_panel, label="默认端口:")
    port_ctrl = wx.SpinCtrl(port_panel, value=str(config.get('default_port', 1524)), min=1024, max=65535)

    auto_open_browser = wx.CheckBox(port_panel, label="启动后自动打开浏览器")
    auto_open_browser.SetValue(config.get('auto_open_browser', True))

    port_sizer.Add(port_label, 0, wx.ALL | wx.EXPAND, 5)
    port_sizer.Add(port_ctrl, 0, wx.ALL | wx.EXPAND, 5)
    port_sizer.Add(auto_open_browser, 0, wx.ALL | wx.EXPAND, 5)

    port_panel.SetSizer(port_sizer)

    # 请求头面板
    header_panel = wx.Panel(notebook)
    header_sizer = wx.BoxSizer(wx.VERTICAL)

    header_label = wx.StaticText(header_panel, label="请求头User-Agent设置:")
    header_text = wx.TextCtrl(header_panel, style=wx.TE_MULTILINE)

    header_path = os.path.join(target_folder, "Head.ANT")
    if os.path.exists(header_path):
        with open(header_path, 'r', encoding='utf-8') as f:
            header_text.SetValue(f.read())

    default_header_label = wx.StaticText(header_panel, label="默认请求头User-Agent:")
    default_header_text = wx.TextCtrl(header_panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
    default_header_text.SetValue("""Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36""")

    def apply_default_header():
        if wx.MessageBox("确定要用默认请求头覆盖当前请求头吗？", "确认",
                         wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
            header_text.SetValue(default_header_text.GetValue())
            wx.MessageBox("默认请求头已应用", "提示", wx.OK | wx.ICON_INFORMATION)

    apply_header_btn = wx.Button(header_panel, label="应用默认请求头")
    apply_header_btn.Bind(wx.EVT_BUTTON, lambda e: apply_default_header())

    def save_headers():
        with open(header_path, 'w', encoding='utf-8') as f:
            f.write(header_text.GetValue())
        wx.MessageBox("请求头已保存", "提示", wx.OK | wx.ICON_INFORMATION)

    save_header_btn = wx.Button(header_panel, label="保存请求头")
    save_header_btn.Bind(wx.EVT_BUTTON, lambda e: save_headers())

    header_sizer.Add(header_label, 0, wx.ALL | wx.EXPAND, 5)
    header_sizer.Add(header_text, 1, wx.ALL | wx.EXPAND, 5)
    header_sizer.Add(default_header_label, 0, wx.ALL | wx.EXPAND, 5)
    header_sizer.Add(default_header_text, 1, wx.ALL | wx.EXPAND, 5)
    header_sizer.Add(apply_header_btn, 0, wx.ALL | wx.EXPAND, 5)
    header_sizer.Add(save_header_btn, 0, wx.ALL | wx.EXPAND, 5)

    header_panel.SetSizer(header_sizer)

    notebook.AddPage(window, "窗口")
    notebook.AddPage(file_panel, "文件")
    notebook.AddPage(storage_panel, "存储")
    notebook.AddPage(header_panel, "请求头")
    notebook.AddPage(port_panel, "端口")

    def on_save_config(event):
        global Pos
        global fontname, FontSize

        Pos = (pos_x_ctrl.GetValue(), pos_y_ctrl.GetValue())

        fontname = font_choice.GetStringSelection()
        FontSize = font_size_ctrl.GetValue()

        config['default_port'] = port_ctrl.GetValue()
        config['auto_open_browser'] = auto_open_browser.GetValue()
        config['window_pos'] = Pos
        config['window_size'] = [win_ctrl.GetValue(), winht_ctrl.GetValue()]
        config['font_name'] = fontname
        config['font_size'] = FontSize
        config['list_button_size'] = FontSize
        config['size'] = [300, 30]
        config['high_dpi'] = DPI_set.GetValue()
        config['share_path'] =config['share_path']
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

        wx.MessageBox("设置已保存", "提示", wx.OK | wx.ICON_INFORMATION)


    save_button = wx.Button(options_window, label="保存设置")
    save_button.Bind(wx.EVT_BUTTON, on_save_config)


    main_sizer = wx.BoxSizer(wx.VERTICAL)
    main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
    main_sizer.Add(save_button, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

    options_window.SetSizer(main_sizer)
    options_window.Show()
    options_window.Raise()
    options_window.SetFocus()
