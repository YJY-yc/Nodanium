# Copyright (c) 2024-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import wx
import os
import json
import sys
import platform
import subprocess
import glob

config = {
    'font_size': 17,
    'list_button_size': 15,
    'font_name': "微软雅黑",
    'size': (300, 30),
    'size_button': (100, 30),
    'window_pos': (100, 20),
    'window_size': [800, 550],
    'high_dpi': True,
    'dl_max_retry': 100,
    'dl_timeout': 240,
    'dl_threads': 8,
    'dl_chunk_mb': 10,
    'dl_cache_mb': 32,
    'dl_disable_ssl': False,
    'dl_speed_unit': 'MB/s',
}

LABEL_W = 150
CTRL_W = 180


def get_data_folder():
    """获取跨平台数据目录"""
    sys_type = platform.system()
    if sys_type == "Windows":
        return os.path.join(os.getenv('APPDATA', ''), "Nodanium")
    elif sys_type == "Linux":
        return os.path.join(os.path.expanduser("~"), ".Nodanium")
    elif sys_type == "Darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Nodanium")
    else:
        return os.path.join(os.path.expanduser("~"), ".Nodanium")


def on_go_to_file(event):
    if os.path.isdir(dirs):
        # 跨平台打开文件夹
        if platform.system() == "Windows":
            os.startfile(dirs)
        else:
            import subprocess
            subprocess.run(["xdg-open", dirs])


def options(event):
    global dirs
    global Pos
    Pos = config.get('window_pos', (100, 20))
    options_window = wx.Frame(None, title="首选项", size=(560, 640))
    options_window.SetBackgroundColour(wx.Colour(255, 255, 255))

    target_folder = get_data_folder()
    config_path = os.path.join(target_folder, "config.json")
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)

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

    scroll_panels = []

    def make_scroll_panel(parent):
        content = wx.BoxSizer(wx.VERTICAL)
        sp = wx.ScrolledWindow(parent)
        sp.SetSizer(content)
        sp.SetScrollRate(5, 5)
        scroll_panels.append(sp)
        return sp, content

    def add_static_box(panel, sizer, title, child_factory):
        """在滚动面板内创建一个带标题槽的分组容器，返回其内容 sizer"""
        box = wx.StaticBox(panel, label=title)
        box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
        inner = box_sizer
        child_factory(inner)
        sizer.Add(box_sizer, 0, wx.EXPAND | wx.ALL, 8)
        return inner

    # ========================== 窗口 ==========================
    window, window_sizer = make_scroll_panel(notebook)

    def window_content(s):
        global font_choice, font_size_ctrl, pos_x_ctrl, pos_y_ctrl, win_w, win_h, dpi_set
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
        grid.AddGrowableCol(1, 1)

        font_label = wx.StaticText(window, label="字体")
        font_choices = wx.FontEnumerator().GetFacenames()
        font_choice = wx.Choice(window, choices=font_choices, size=(CTRL_W, -1))
        font_choice.SetStringSelection(config['font_name'])

        font_preview = wx.StaticText(window, label="中国智造，惠及全球ABC", style=wx.ALIGN_LEFT)

        def update_font_preview(event=None):
            selected_font = font_choice.GetStringSelection()
            font_preview.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                                         wx.FONTWEIGHT_NORMAL, faceName=selected_font))

        font_choice.Bind(wx.EVT_CHOICE, update_font_preview)
        update_font_preview()

        font_size_label = wx.StaticText(window, label="字体大小")
        font_size_ctrl = wx.SpinCtrl(window, value=str(config['font_size']), min=10, max=40, size=(CTRL_W, -1))

        pos_label = wx.StaticText(window, label="窗口位置 XY")
        pos_x_ctrl = wx.SpinCtrl(window, value=str(Pos[0]), min=0, max=1920)
        pos_y_ctrl = wx.SpinCtrl(window, value=str(Pos[1]), min=0, max=1080)
        pos_row = wx.BoxSizer(wx.HORIZONTAL)
        pos_row.Add(pos_x_ctrl, 1, wx.RIGHT, 5)
        pos_row.Add(pos_y_ctrl, 1)

        win_label = wx.StaticText(window, label="窗口大小")
        win_w = wx.SpinCtrl(window, value=str(config['window_size'][0]), min=400, max=1920)
        win_h = wx.SpinCtrl(window, value=str(config['window_size'][1]), min=300, max=1080)
        win_row = wx.BoxSizer(wx.HORIZONTAL)
        win_row.Add(win_w, 1, wx.RIGHT, 5)
        win_row.Add(win_h, 1)

        dpi_label = wx.StaticText(window, label="高DPI")
        dpi_set = wx.CheckBox(window, label="使用高DPI获得更清晰的窗口")
        dpi_set.SetValue(config.get('high_dpi', True))

        for lbl, ctrl in [(font_label, font_choice), (font_size_label, font_size_ctrl),
                          (pos_label, pos_row), (win_label, win_row), (dpi_label, dpi_set)]:
            grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        s.Add(grid, 0, wx.EXPAND | wx.ALL, 6)
        s.Add(wx.StaticText(window, label="字体预览"), 0, wx.ALL, 5)
        s.Add(font_preview, 0, wx.ALL, 5)

    add_static_box(window, window_sizer, "界面设置", window_content)

    # ========================== 文件 ==========================
    file_panel, file_sizer = make_scroll_panel(notebook)

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

    file_sizer.Add(wx.StaticText(file_panel, label="选择文件保存位置"), 0, wx.ALL, 8)
    file_sizer.Add(path_text, 0, wx.EXPAND | wx.ALL, 5)
    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    btn_sizer.Add(browse_button, 0, wx.RIGHT, 5)
    btn_sizer.Add(link_to_2, 0)
    file_sizer.Add(btn_sizer, 0, wx.ALL, 5)

    # ========================== 下载 ==========================
    down_panel, down_sizer = make_scroll_panel(notebook)

    def down_content(s):
        global retry_ctrl, timeout_ctrl, threads_ctrl, chunk_ctrl, cache_ctrl, unit_ctrl, ssl_ctrl
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
        grid.AddGrowableCol(1, 1)

        retry_label = wx.StaticText(down_panel, label="重试次数")
        retry_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('dl_max_retry', 100)), min=1, max=1000, size=(CTRL_W, -1))

        timeout_label = wx.StaticText(down_panel, label="超时时间(秒)")
        timeout_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('dl_timeout', 240)), min=10, max=600, size=(CTRL_W, -1))

        threads_label = wx.StaticText(down_panel, label="并发线程数")
        threads_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('dl_threads', 8)), min=1, max=128, size=(CTRL_W, -1))

        chunk_label = wx.StaticText(down_panel, label="单分片大小(MB)")
        chunk_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('dl_chunk_mb', 10)), min=1, max=1024, size=(CTRL_W, -1))

        cache_label = wx.StaticText(down_panel, label="内存缓冲(MB)")
        cache_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('dl_cache_mb', 32)), min=1, max=2048, size=(CTRL_W, -1))

        unit_label = wx.StaticText(down_panel, label="速度单位")
        unit_ctrl = wx.Choice(down_panel, choices=['MB/s', 'MIB/s', 'KB/s', 'GB/s'], size=(CTRL_W, -1))
        unit_default = config.get('dl_speed_unit', 'MB/s')
        if unit_default in unit_ctrl.GetStrings():
            unit_ctrl.SetStringSelection(unit_default)
        else:
            unit_ctrl.SetStringSelection('MB/s')

        for lbl, ctrl in [(retry_label, retry_ctrl), (timeout_label, timeout_ctrl),
                          (threads_label, threads_ctrl), (chunk_label, chunk_ctrl),
                          (cache_label, cache_ctrl), (unit_label, unit_ctrl)]:
            grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        ssl_ctrl = wx.CheckBox(down_panel, label="忽略SSL证书校验（适用于自签名证书）")
        ssl_ctrl.SetValue(config.get('dl_disable_ssl', False))

        s.Add(grid, 0, wx.EXPAND | wx.ALL, 6)
        s.Add(ssl_ctrl, 0, wx.ALL, 8)

    add_static_box(down_panel, down_sizer, "多线程下载设置", down_content)

    # ========================== 存储 ==========================
    storage_panel, storage_sizer = make_scroll_panel(notebook)

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

    storage_sizer.Add(temp_size_label, 0, wx.ALL, 8)
    storage_sizer.Add(temp_size_text, 0, wx.ALL, 5)
    storage_sizer.Add(clear_button, 0, wx.ALL | wx.EXPAND, 5)
    storage_sizer.Add(clear_history_button, 0, wx.ALL | wx.EXPAND, 5)

    # ========================== 请求头 ==========================
    header_panel, header_sizer = make_scroll_panel(notebook)

    def header_content(s):
        header_label = wx.StaticText(header_panel, label="自定义请求头:")
        header_text = wx.TextCtrl(header_panel, style=wx.TE_MULTILINE, size=(400, 120))

        header_path = os.path.join(target_folder, "Head.ANT")
        if os.path.exists(header_path):
            with open(header_path, 'r', encoding='utf-8') as f:
                header_text.SetValue(f.read())

        default_header_label = wx.StaticText(header_panel, label="默认请求头:")
        default_header_text = wx.TextCtrl(header_panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(400, 80))
        default_header_text.SetValue(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")

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

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_row.Add(apply_header_btn, 0, wx.RIGHT, 5)
        btn_row.Add(save_header_btn, 0)

        s.Add(header_label, 0, wx.ALL, 5)
        s.Add(header_text, 0, wx.ALL | wx.EXPAND, 5)
        s.Add(default_header_label, 0, wx.ALL, 5)
        s.Add(default_header_text, 0, wx.ALL | wx.EXPAND, 5)
        s.Add(btn_row, 0, wx.ALL, 5)

    add_static_box(header_panel, header_sizer, "请求头设置", header_content)

    # ========================== 端口 ==========================
    port_panel, port_sizer = make_scroll_panel(notebook)

    def port_content(s):
        global port_ctrl, auto_open_browser
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
        grid.AddGrowableCol(1, 1)
        port_label = wx.StaticText(port_panel, label="默认端口")
        port_ctrl = wx.SpinCtrl(port_panel, value=str(config.get('default_port', 1524)), min=1024, max=65535, size=(CTRL_W, -1))
        grid.Add(port_label, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(port_ctrl, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        auto_open_browser = wx.CheckBox(port_panel, label="启动后自动打开浏览器")
        auto_open_browser.SetValue(config.get('auto_open_browser', True))

        s.Add(grid, 0, wx.EXPAND | wx.ALL, 6)
        s.Add(auto_open_browser, 0, wx.ALL, 8)

    add_static_box(port_panel, port_sizer, "服务设置", port_content)

    # ========================== 浏览器插件 ==========================
    plugin_panel, plugin_sizer = make_scroll_panel(notebook)
    PLUGIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Nodanium-BrowserPlugin")

    # 检测 Native Host 是否已注册
    def host_installed():
        host_name = "com.nodanium.yujy"
        if platform.system() == "Windows":
            dirs = [os.path.join(os.getenv('LOCALAPPDATA', ''), "Google", "Chrome", "NativeMessagingHosts"),
                    os.path.join(os.getenv('APPDATA', ''), "Mozilla", "NativeMessagingHosts")]
            # Edge 使用独立目录
            dirs.append(os.path.join(os.getenv('LOCALAPPDATA', ''), "Microsoft", "Edge", "User Data", "NativeMessagingHosts"))
            return any(os.path.exists(os.path.join(d, host_name + ".json")) for d in dirs)
        # Linux / macOS
        dirs = ["$HOME/.config/google-chrome/NativeMessagingHosts",
                "$HOME/.config/chromium/NativeMessagingHosts",
                "$HOME/.config/microsoft-edge/NativeMessagingHosts",
                "$HOME/.mozilla/native-messaging-hosts",
                "$HOME/.config/mozilla/native-messaging-hosts"]
        home = os.path.expanduser("~")
        return any(os.path.exists(os.path.join(d.replace("$HOME", home), host_name + ".json")) for d in dirs)

    # 读取已有插件配置作为默认值
    plugin_cfg_path = os.path.join(target_folder, "browser-plugin-config.json")
    plugin_cfg = {"nativeSizeLimitBytes": 0, "enabled": True}
    if os.path.exists(plugin_cfg_path):
        try:
            with open(plugin_cfg_path, 'r', encoding='utf-8') as f:
                plugin_cfg.update(json.load(f))
        except:
            pass

    plugin_intro = wx.StaticText(
        plugin_panel,
        label="在首选项中安装/管理 Nodanium 浏览器下载插件。\n"
              "Native Host：com.nodanium.yujy（浏览器与软件间桥接进程）。")
    plugin_intro.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    plugin_sizer.Add(plugin_intro, 0, wx.ALL, 8)

    host_status_txt = wx.StaticText(plugin_panel, label="Native Host 状态：检测中...")
    plugin_sizer.Add(host_status_txt, 0, wx.ALL, 8)

    def refresh_host_status():
        ok = host_installed()
        host_status_txt.SetLabel("Native Host 状态：✅ 已安装" if ok else "❌ 未安装（点击下方按钮一键安装）")
        host_status_txt.SetForegroundColour(wx.Colour(0, 128, 0) if ok else wx.Colour(200, 0, 0))
        host_status_txt.Refresh()

    refresh_host_status()

    def save_plugin_config_file():
        """把插件配置写回数据目录，供 Native Host 读取。"""
        try:
            native_limit = int(limit_ctrl.GetValue()) * 1024 * 1024  # MB -> bytes
        except Exception:
            native_limit = 0
        data = {
            "nativeSizeLimitBytes": native_limit,
            "enabled": bool(plugin_enabled.GetValue()),
            "mainProgramPath": main_ctrl.GetValue().strip(),
            "hostBinaryPath": host_bin_ctrl.GetValue().strip(),
        }
        with open(plugin_cfg_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    install_btn = wx.Button(plugin_panel, label="安装 / 重新安装 Native Host")
    install_btn.SetToolTip("注册 com.nodanium.yujy 到浏览器\n(Chrome / Edge / Firefox)")
    plugin_sizer.Add(install_btn, 0, wx.EXPAND | wx.ALL, 5)

    def on_install_host(event):
        if not os.path.isdir(PLUGIN_DIR):
            wx.MessageBox("未找到浏览器插件目录：\n" + PLUGIN_DIR, "错误", wx.OK | wx.ICON_ERROR)
            return
        # 先写入当前配置，再运行安装脚本
        save_plugin_config_file()
        install_script = os.path.join(PLUGIN_DIR, "native-host",
                                      "install_host.bat" if platform.system() == "Windows" else "install_host.sh")
        if not os.path.exists(install_script):
            wx.MessageBox("未找到安装脚本：\n" + install_script, "错误", wx.OK | wx.ICON_ERROR)
            return
        install_btn.Disable()
        install_btn.SetLabel("正在安装...")
        try:
            if platform.system() == "Windows":
                subprocess.Popen([install_script], cwd=os.path.dirname(install_script))
            else:
                subprocess.Popen(["bash", install_script], cwd=os.path.dirname(install_script))
        except Exception as e:
            wx.MessageBox("安装脚本启动失败：\n" + str(e), "错误", wx.OK | wx.ICON_ERROR)
        finally:
            install_btn.SetLabel("安装 / 重新安装 Native Host")
            install_btn.Enable()
            wx.CallLater(1500, refresh_host_status)
        wx.MessageBox(
            "安装脚本已启动，请在弹出的终端中按提示完成。\n\n"
            "完成后请前往浏览器：\n"
            "· Chrome/Edge: chrome://extensions 加载插件\n"
            "· 按脚本提示把真实扩展 ID 填入注册清单\n"
            "然后点击右下角\"保存设置\"确认配置。",
            "安装 Native Host", wx.OK | wx.ICON_INFORMATION)

    install_btn.Bind(wx.EVT_BUTTON, on_install_host)

    # ---------- 路径设置 ----------
    plugin_sizer.Add(wx.StaticText(plugin_panel, label="— 路径设置 —"), 0, wx.ALL, 8)

    def make_path_row(label, ctrl_name, default_val, is_file, tip):
        """生成一个带浏览按钮的路径选择行，返回文本控件。"""
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(plugin_panel, label=label, size=(120, -1))
        txt = wx.TextCtrl(plugin_panel, value=default_val)
        txt.SetToolTip(tip)
        bt = wx.Button(plugin_panel, label="浏览...", size=(60, -1))

        def on_browse(evt):
            if is_file:
                dlg = wx.FileDialog(plugin_panel, "选择可执行文件", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
            else:
                dlg = wx.DirDialog(plugin_panel, "选择目录", style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
            if dlg.ShowModal() == wx.ID_OK:
                txt.SetValue(dlg.GetPath())
            dlg.Destroy()

        bt.Bind(wx.EVT_BUTTON, on_browse)
        row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        row.Add(txt, 1, wx.EXPAND | wx.RIGHT, 5)
        row.Add(bt, 0, wx.ALIGN_CENTER_VERTICAL)
        plugin_sizer.Add(row, 0, wx.EXPAND | wx.ALL, 5)
        return txt

    _main_default = plugin_cfg.get("mainProgramPath", "")
    if not _main_default:
        # 尝试默认定位：与插件目录同级的主程序二进制/入口文件
        _cand_root = os.path.dirname(os.path.dirname(PLUGIN_DIR)) if os.path.basename(PLUGIN_DIR) == "Nodanium-BrowserPlugin" else PLUGIN_DIR
        for _cand in ("nodanium", "NodaniumLauncher.py", "NodaniumLauncher", "nodanium.bin"):
            _p = os.path.join(_cand_root, _cand)
            if os.path.exists(_p) and os.path.isfile(_p):
                _main_default = _p
                break
    # 已全局安装到系统时，默认指向 /usr/bin/nodanium
    if not _main_default and platform.system() != "Windows":
        import shutil
        _sh = shutil.which("nodanium")
        if _sh:
            _main_default = _sh
        elif os.path.exists("/usr/lib/nodanium/nodanium.bin"):
            _main_default = "/usr/lib/nodanium/nodanium.bin"

    main_ctrl = make_path_row(
        "主程序路径", "main_ctrl", _main_default, True,
        "Nodanium 主程序可执行文件（Nuitka 打包产物）\nNative Host 通过 --download 启动它完成下载")

    _host_default = plugin_cfg.get("hostBinaryPath", "")
    if not _host_default:
        for _cand in ("nodanium-host", "nodanium-host.exe", "host", "host.exe"):
            _p = os.path.join(PLUGIN_DIR, "native-host", _cand)
            if os.path.exists(_p):
                _host_default = _p
                break
    host_bin_ctrl = make_path_row(
        "Host 可执行文件", "host_bin_ctrl", _host_default, True,
        "Native Host 二进制（Nuitka 编译产物，读取浏览器消息）\n\n指向 .py 脚本也可，但推荐编译后的自包含二进制。")

    def write_host_path_to_manifests():
        """把当前 Host 路径写入已在浏览器注册目录中的清单。"""
        host_path = host_bin_ctrl.GetValue().strip()
        if not host_path or not os.path.exists(host_path):
            wx.MessageBox("请先选择有效的 Host 可执行文件路径", "错误", wx.OK | wx.ICON_ERROR)
            return
        host_path = os.path.abspath(host_path)
        reg_dirs = []
        if platform.system() == "Windows":
            reg_dirs = [
                os.path.join(os.getenv('LOCALAPPDATA', ''), "Google", "Chrome", "NativeMessagingHosts"),
                os.path.join(os.getenv('LOCALAPPDATA', ''), "Microsoft", "Edge", "User Data", "NativeMessagingHosts"),
                os.path.join(os.path.join(os.getenv('APPDATA', ''), "Mozilla", "NativeMessagingHosts")),
            ]
        else:
            home = os.path.expanduser("~")
            reg_dirs = [
                os.path.join(home, ".config", "google-chrome", "NativeMessagingHosts"),
                os.path.join(home, ".config", "chromium", "NativeMessagingHosts"),
                os.path.join(home, ".config", "microsoft-edge", "NativeMessagingHosts"),
                os.path.join(home, ".mozilla", "native-messaging-hosts"),
                os.path.join(home, ".config", "mozilla", "native-messaging-hosts"),
            ]
        written = []
        for d in reg_dirs:
            mp = os.path.join(d, "com.nodanium.yujy.json")
            if not os.path.exists(mp):
                continue
            try:
                with open(mp, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data["path"] = host_path
                with open(mp, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                written.append(d)
            except Exception as e:
                wx.MessageBox("写入失败：" + str(e), "错误", wx.OK | wx.ICON_ERROR)
        if written:
            wx.MessageBox("已将 Host 路径写入以下浏览器注册清单：\n\n" + "\n".join(written),
                          "路径已同步", wx.OK | wx.ICON_INFORMATION)
            refresh_host_status()
        else:
            wx.MessageBox("未找到已注册的清单。请先点击上方\"安装 / 重新安装 Native Host\"。",
                          "提示", wx.OK | wx.ICON_INFORMATION)
        # 同时写入配置
        save_plugin_config_file()

    path_sync_btn = wx.Button(plugin_panel, label="把上面的路径写入浏览器注册清单")
    path_sync_btn.SetToolTip("把 Host 可执行文件路径写入已安装的 Chrome/Edge/Firefox 注册清单，\n无需重新运行安装脚本。")
    path_sync_btn.Bind(wx.EVT_BUTTON, lambda e: write_host_path_to_manifests())
    plugin_sizer.Add(path_sync_btn, 0, wx.EXPAND | wx.ALL, 5)

    plugin_hint = wx.StaticText(
        plugin_panel,
        label="▸ 首次配置：\n"
              "1. 点击上方按钮安装 Native Host；\n"
              "2. 打开 Chrome/Edge，在 chrome://extensions\n"
              "   加载 Nodanium-BrowserPlugin 目录；\n"
              "3. 复制扩展 ID，把它填到注册清单的\n"
              "   allowed_origins 中，重新加载扩展。",
        style=wx.ALIGN_LEFT)
    plugin_hint.SetForegroundColour(wx.Colour(90, 90, 90))
    plugin_sizer.Add(plugin_hint, 0, wx.ALL, 8)

    plugin_sizer.Add(wx.StaticText(plugin_panel, label="— 小文件原生下载 —"), 0, wx.ALL, 8)

    limit_label = wx.StaticText(plugin_panel, label="原生下载大小阈值 (MB)")
    limit_default = int((plugin_cfg.get("nativeSizeLimitBytes", 0) or 0) / (1024 * 1024))
    limit_ctrl = wx.SpinCtrl(plugin_panel, value=str(max(limit_default, 0)),
                             min=0, max=1024, size=(CTRL_W, -1))
    limit_ctrl.SetToolTip("0 表示始终交由 Nodanium 多线程下载；\n大于 0 时，小于等于该大小的文件由浏览器原生下载。")
    plugin_sizer.Add(limit_label, 0, wx.ALL, 5)
    plugin_sizer.Add(limit_ctrl, 0, wx.ALL, 5)

    plugin_enabled = wx.CheckBox(plugin_panel, label="启用浏览器下载拦截")
    plugin_enabled.SetValue(bool(plugin_cfg.get("enabled", True)))
    plugin_sizer.Add(plugin_enabled, 0, wx.ALL, 8)

    plugin_note = wx.StaticText(
        plugin_panel,
        label="提示：修改以上配置后点\"保存设置\"，即写回插件配置。\n"
              "插件在下次下载时通过 Native Host 自动读取生效。")
    plugin_note.SetForegroundColour(wx.Colour(90, 90, 90))
    plugin_sizer.Add(plugin_note, 0, wx.ALL, 8)

    notebook.AddPage(window, "界面设置")
    notebook.AddPage(file_panel, "文件")
    notebook.AddPage(down_panel, "下载")
    notebook.AddPage(storage_panel, "存储")
    notebook.AddPage(header_panel, "请求头")
    notebook.AddPage(port_panel, "端口")
    notebook.AddPage(plugin_panel, "浏览器插件")

    def on_save_config(event):
        global Pos
        global fontname, FontSize

        Pos = (pos_x_ctrl.GetValue(), pos_y_ctrl.GetValue())

        fontname = font_choice.GetStringSelection()
        FontSize = font_size_ctrl.GetValue()

        config['default_port'] = port_ctrl.GetValue()
        config['auto_open_browser'] = auto_open_browser.GetValue()
        config['window_pos'] = Pos
        config['window_size'] = [win_w.GetValue(), win_h.GetValue()]
        config['font_name'] = fontname
        config['font_size'] = FontSize
        config['list_button_size'] = FontSize
        config['size'] = [300, 30]
        config['high_dpi'] = dpi_set.GetValue()

        config['dl_max_retry'] = retry_ctrl.GetValue()
        config['dl_timeout'] = timeout_ctrl.GetValue()
        config['dl_threads'] = threads_ctrl.GetValue()
        config['dl_chunk_mb'] = chunk_ctrl.GetValue()
        config['dl_cache_mb'] = cache_ctrl.GetValue()
        config['dl_speed_unit'] = unit_ctrl.GetStringSelection()
        config['dl_disable_ssl'] = ssl_ctrl.GetValue()

        if 'share_path' in config:
            config['share_path'] = config.get('share_path', '')

        try:
            import NewDownloadCore
            NewDownloadCore.DEFAULT_RETRY = retry_ctrl.GetValue()
            NewDownloadCore.DEFAULT_TIMEOUT = timeout_ctrl.GetValue()
        except Exception:
            pass

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

        # 保存浏览器插件配置（Native Host 会读取 browser-plugin-config.json）
        save_plugin_config_file()

        wx.MessageBox("设置已保存", "提示", wx.OK | wx.ICON_INFORMATION)

    save_button = wx.Button(options_window, label="保存设置")
    save_button.Bind(wx.EVT_BUTTON, on_save_config)

    main_sizer = wx.BoxSizer(wx.VERTICAL)
    main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
    main_sizer.Add(save_button, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

    options_window.SetSizer(main_sizer)
    options_window.Show()

    for sp in scroll_panels:
        sp.Layout()
        sp.SetVirtualSize(sp.GetBestVirtualSize())
        sp.FitInside()

    options_window.Raise()
    options_window.SetFocus()
