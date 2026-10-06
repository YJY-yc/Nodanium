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
import logging

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
    'bt_use_service': True,
    'bt_seed_time': 0,
    'bt_seed_ratio': 1.0,
}

LABEL_W = 150
CTRL_W = 180

# 请求头条目模板
KV_TEMPLATES = [
    ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    ("Referer", "https://example.com/"),
    ("Accept", "*/*"),
    ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"),
    ("Accept-Encoding", "gzip, deflate, br"),
    ("Connection", "keep-alive"),
    ("DNT", "1"),
    ("Origin", "https://example.com"),
    ("X-Requested-With", "XMLHttpRequest"),
    ("RemoteAddr", ""),
]


def get_data_folder():
    """获取跨平台数据目录"""
    sys_type = platform.system()
    if sys_type == "Windows":
        return os.path.join(os.getenv('APPDATA', ''), "Nodanium")
    elif sys_type == "Linux":
        return os.path.join(os.path.expanduser("~"), ".Nodanium")
    else:
        return os.path.join(os.path.expanduser("~"), ".Nodanium")


def on_go_to_file(event):
    if os.path.isdir(dirs):
       
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
        sp.SetMinSize((-1, 80))

        def _clamp_virtual(evt=None):
            # 保证虚拟尺寸不小于客户区，避免 GTK 滚动条被分配到负空间
            try:
                best = sp.GetBestVirtualSize()
                cw, ch = sp.GetClientSize()
                sp.SetVirtualSize((max(best.width, cw), max(best.height, ch)))
            except Exception:
                pass
            if evt is not None:
                evt.Skip()

        sp.Bind(wx.EVT_SIZE, _clamp_virtual)
        scroll_panels.append((sp, _clamp_virtual))
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
        s.Add(wx.StaticLine(window, style=wx.LI_HORIZONTAL), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)

    add_static_box(window, window_sizer, "界面设置", window_content)

    # ========================== 下载 ==========================
    down_panel, down_sizer = make_scroll_panel(notebook)

    def down_content(s):
        global retry_ctrl, timeout_ctrl, stall_ctrl, threads_ctrl, chunk_ctrl, cache_ctrl, unit_ctrl, ssl_ctrl
        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
        grid.AddGrowableCol(1, 1)

        retry_label = wx.StaticText(down_panel, label="重试次数")
        retry_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('dl_max_retry', 100)), min=1, max=1000, size=(CTRL_W, -1))

        timeout_label = wx.StaticText(down_panel, label="超时时间(秒)")
        timeout_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('dl_timeout', 240)), min=10, max=600, size=(CTRL_W, -1))

        stall_label = wx.StaticText(down_panel, label="读取停滞超时(秒)")
        stall_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('dl_read_stall', 30)), min=5, max=300, size=(CTRL_W, -1))

        threads_label = wx.StaticText(down_panel, label="并发线程数")
        threads_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('dl_threads', 8)), min=1, max=128, size=(CTRL_W, -1))

        chunk_label = wx.StaticText(down_panel, label="单分片大小(MB)")
        chunk_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('dl_chunk_mb', 10)), min=1, max=1024, size=(CTRL_W, -1))

        cache_label = wx.StaticText(down_panel, label="内存缓冲(MB)")
        cache_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('dl_cache_mb', 32)), min=1, max=2048, size=(CTRL_W, -1))

        unit_label = wx.StaticText(down_panel, label="速度单位")
        # 可选项与下载引擎 NewDownloadCore.format_speed 支持的单位保持一致：
        # MB/s=十进制字节速率，MiB/s=二进制字节速率，Mbps=比特率
        unit_ctrl = wx.Choice(down_panel, choices=['MB/s', 'MiB/s', 'Mbps'], size=(CTRL_W, -1))
        unit_default = config.get('dl_speed_unit', 'MB/s')
        if unit_default in unit_ctrl.GetStrings():
            unit_ctrl.SetStringSelection(unit_default)
        else:
            unit_ctrl.SetStringSelection('MB/s')

        for lbl, ctrl in [(retry_label, retry_ctrl), (timeout_label, timeout_ctrl),
                          (stall_label, stall_ctrl), (threads_label, threads_ctrl),
                          (chunk_label, chunk_ctrl),
                          (cache_label, cache_ctrl), (unit_label, unit_ctrl)]:
            grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        ssl_ctrl = wx.CheckBox(down_panel, label="忽略SSL证书校验（适用于自签名证书）")
        ssl_ctrl.SetValue(config.get('dl_disable_ssl', False))

        s.Add(grid, 0, wx.EXPAND | wx.ALL, 6)
        s.Add(ssl_ctrl, 0, wx.ALL, 8)

    add_static_box(down_panel, down_sizer, "多线程下载设置", down_content)

    # ---- BT 下载设置 ----
    def bt_content(s):
        global bt_service_ctrl, bt_seed_time_ctrl, bt_seed_ratio_ctrl
        bt_service_ctrl = wx.CheckBox(
            down_panel, label="BT 任务使用常驻服务（可在 aria2 管理面板统一查看/做种）")
        bt_service_ctrl.SetValue(config.get('bt_use_service', True))
        s.Add(bt_service_ctrl, 0, wx.ALL, 8)

        btip = wx.StaticText(down_panel, label="关闭则由每个 BT 任务独立启动 aria2 会话，\n"
                                              "不显示在 aria2 管理面板，也无法作种。")
        btip.SetForegroundColour(wx.Colour(130, 130, 130))
        s.Add(btip, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # aria2 服务为按需启动，不做后台常驻；已移除“启动软件时自动启动/自动作种”选项
        svc_tip = wx.StaticText(down_panel, label="aria2 服务按需启动：仅在发起 BT 下载时自动拉起，\n"
                                                 "服务未运行时不会作种；可在“BT 下载 → 服务”页手动启停。")
        svc_tip.SetForegroundColour(wx.Colour(130, 130, 130))
        s.Add(svc_tip, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        bgrid = wx.FlexGridSizer(cols=2, vgap=8, hgap=8)
        bgrid.AddGrowableCol(1, 1)
        st_lbl = wx.StaticText(down_panel, label="做种时间(分钟)")
        bt_seed_time_ctrl = wx.SpinCtrl(down_panel, value=str(config.get('bt_seed_time', 0)),
                                        min=0, max=100000, size=(CTRL_W, -1))
        sr_lbl = wx.StaticText(down_panel, label="做种分享率")
        bt_seed_ratio_ctrl = wx.SpinCtrlDouble(down_panel, value=str(config.get('bt_seed_ratio', 1.0)),
                                               min=0, max=1000, inc=0.1, size=(CTRL_W, -1))
        bt_seed_ratio_ctrl.SetDigits(1)
        for lbl, ctrl in [(st_lbl, bt_seed_time_ctrl), (sr_lbl, bt_seed_ratio_ctrl)]:
            bgrid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
            bgrid.Add(ctrl, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
        s.Add(bgrid, 0, wx.EXPAND | wx.ALL, 6)

        st_tip = wx.StaticText(down_panel, label="做种时间 0 且分享率 0 表示不做种；\n"
                                                "任一条件先达到即停止做种。")
        st_tip.SetForegroundColour(wx.Colour(130, 130, 130))
        s.Add(st_tip, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

    add_static_box(down_panel, down_sizer, "BT 下载设置", bt_content)

    # ========================== 存储 ==========================
    storage_panel, storage_sizer = make_scroll_panel(notebook)

    path_label = wx.StaticText(storage_panel, label="下载文件保存位置")
    path_text = wx.TextCtrl(storage_panel, value=dirs)

    def on_browse(event):
        dialog = wx.DirDialog(storage_panel, "选择下载文件夹",
                              style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        if dialog.ShowModal() == wx.ID_OK:
            new_path = dialog.GetPath()
            path_text.SetValue(new_path)
            global dirs
            dirs = new_path + "\\"
            with open(os.path.join(target_folder, "dir.txt"), "w") as f:
                f.write(dirs)
        dialog.Destroy()

    browse_button = wx.Button(storage_panel, label="浏览...")
    link_to_2 = wx.Button(storage_panel, label="打开文件路径",
                          style=wx.BORDER_NONE, size=(140, 30))
    link_to_2.SetForegroundColour(wx.Colour(0, 0, 255))
    link_to_2.SetBackgroundColour(wx.Colour(249, 249, 249))
    link_to_2.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    link_to_2.SetCursor(wx.Cursor(wx.CURSOR_HAND))
    link_to_2.Bind(wx.EVT_BUTTON, on_go_to_file)
    browse_button.Bind(wx.EVT_BUTTON, on_browse)

    storage_sizer.Add(path_label, 0, wx.ALL, 8)
    storage_sizer.Add(path_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    btn_sizer.Add(browse_button, 0, wx.RIGHT, 5)
    btn_sizer.Add(link_to_2, 0)
    storage_sizer.Add(btn_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

    storage_sizer.Add(wx.StaticLine(storage_panel, style=wx.LI_HORIZONTAL), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

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

    # ========================== 请求头（站点式） ==========================
    import SiteHeaders
    header_panel, header_sizer = make_scroll_panel(notebook)


    site_data = SiteHeaders._load_data()
    header_ui = {}

    def header_content(s):
        from wx.lib.scrolledpanel import ScrolledPanel

        # ---------- 帮助说明 ----------
        tip = wx.StaticText(
            header_panel,
            label="站点式请求头：按下载链接域名匹配，自动套用对应请求头。\n"
                  "支持宏变量 {url} {host} {domain} {filename} {filepath}；Cookie 单独粘贴。\n"
                  "域名支持 *.example.com 通配前缀，未命中时使用全局默认请求头。")
        tip.SetForegroundColour(wx.Colour(120, 120, 120))
        s.Add(tip, 0, wx.ALL, 6)

        # ============ 区域一：站点规则列表 ============
        rule_box = wx.StaticBox(header_panel, label="站点规则")
        rule_sz = wx.StaticBoxSizer(rule_box, wx.VERTICAL)
        rule_row = wx.BoxSizer(wx.HORIZONTAL)

        site_choice = wx.Choice(header_panel, choices=["__NONE__"], size=(200, -1))
        site_choice.SetSelection(0)
        header_ui['choice'] = site_choice

        new_btn = wx.Button(header_panel, label="新建站点")
        del_btn = wx.Button(header_panel, label="删除站点")
        enable_chk = wx.CheckBox(header_panel, label="启用此站点")
        enable_chk.SetValue(True)
        header_ui['enable'] = enable_chk

        rule_row.Add(site_choice, 1, wx.RIGHT, 5)
        rule_row.Add(new_btn, 0, wx.RIGHT, 5)
        rule_row.Add(del_btn, 0, wx.RIGHT, 5)
        rule_row.Add(enable_chk, 0, wx.ALIGN_CENTER_VERTICAL)
        rule_sz.Add(rule_row, 1, wx.EXPAND | wx.BOTTOM, 5)

      
        field_grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=6)
        field_grid.AddGrowableCol(1, 1)
        field_grid.Add(wx.StaticText(header_panel, label="站点名称"), 0, wx.ALIGN_CENTER_VERTICAL)
        name_ctrl = wx.TextCtrl(header_panel, size=(CTRL_W, -1))
        field_grid.Add(name_ctrl, 1, wx.EXPAND)
        field_grid.Add(wx.StaticText(header_panel, label="匹配域名"), 0, wx.ALIGN_CENTER_VERTICAL)
        domain_ctrl = wx.TextCtrl(header_panel, size=(CTRL_W, -1))
        domain_ctrl.SetHint("例如 *.example.com 或 example.com")
        field_grid.Add(domain_ctrl, 1, wx.EXPAND)
        rule_sz.Add(field_grid, 0, wx.EXPAND | wx.BOTTOM, 8)
        header_ui['name'] = name_ctrl
        header_ui['domain'] = domain_ctrl

        s.Add(rule_sz, 0, wx.EXPAND | wx.ALL, 8)

        # ============ 区域二：请求头条目（KV） ============
        kv_box = wx.StaticBox(header_panel, label="请求头条目（键-值）")
        kv_sz = wx.StaticBoxSizer(kv_box, wx.VERTICAL)
        kv_hint = wx.StaticText(header_panel, label="每行一个请求头，值中可使用宏变量。")
        kv_hint.SetForegroundColour(wx.Colour(120, 120, 120))
        kv_sz.Add(kv_hint, 0, wx.BOTTOM, 5)

        kv_scroll = ScrolledPanel(header_panel, -1, size=(620, 200))
        kv_scroll.SetupScrolling(scroll_x=False, scroll_y=True)
        kv_inner = wx.FlexGridSizer(cols=3, vgap=5, hgap=5)
        kv_inner.AddGrowableCol(1, 1)
        kv_inner.Add(wx.StaticText(kv_scroll, label="名称/键"), 0, wx.ALIGN_CENTER_VERTICAL)
        kv_inner.Add(wx.StaticText(kv_scroll, label="值"), 0, wx.ALIGN_CENTER_VERTICAL)
        kv_inner.Add(wx.StaticText(kv_scroll, label=""), 0)
        kv_scroll.SetSizer(kv_inner)
        kv_sz.Add(kv_scroll, 1, wx.EXPAND | wx.BOTTOM, 5)
        header_ui['kv_scroll'] = kv_scroll
        header_ui['kv_inner'] = kv_inner
        header_ui['kv_rows'] = []  # [(key_ctrl, value_ctrl, del_btn)]

        add_kv_btn = wx.Button(header_panel, label="+ 添加请求头条目")
        kv_sz.Add(add_kv_btn, 0, wx.ALL, 2)
        header_ui['add_kv'] = add_kv_btn

        s.Add(kv_sz, 0, wx.EXPAND | wx.ALL, 8)

        # ============ 区域三：Cookie ============
        cookie_box = wx.StaticBox(header_panel, label="Cookie（分号分隔 k=v; k2=v2）")
        cookie_sz = wx.StaticBoxSizer(cookie_box, wx.VERTICAL)
        cookie_ctrl = wx.TextCtrl(header_panel, style=wx.TE_MULTILINE, size=(620, 70))
        cookie_sz.Add(cookie_ctrl, 0, wx.EXPAND | wx.ALL, 4)

        cookie_btn_row = wx.BoxSizer(wx.HORIZONTAL)
        import_cookie_btn = wx.Button(header_panel, label="导入浏览器请求头")
        cookie_btn_row.Add(import_cookie_btn, 0, wx.RIGHT, 5)
        cookie_tip = wx.StaticText(
            header_panel,
            label="在浏览器开发者工具(Network)右键请求 → “复制为 cURL / 复制请求头”，\n再点此按钮粘贴导入，自动拆分 Cookie 与其余请求头。")
        cookie_tip.SetForegroundColour(wx.Colour(120, 120, 120))
        cookie_btn_row.Add(cookie_tip, 0, wx.ALIGN_CENTER_VERTICAL)
        cookie_sz.Add(cookie_btn_row, 0, wx.BOTTOM, 2)
        header_ui['import_cookie'] = import_cookie_btn

        s.Add(cookie_sz, 0, wx.EXPAND | wx.ALL, 8)
        header_ui['cookie'] = cookie_ctrl

        # ============ 区域四：全局默认请求头 ============
        gbox = wx.StaticBox(header_panel, label="全局默认请求头（未命中站点时使用）")
        gsz = wx.StaticBoxSizer(gbox, wx.VERTICAL)
        g_enable = wx.CheckBox(header_panel, label="启用全局默认请求头")
        g_enable.SetValue(bool(site_data.get('default_enabled', True)))
        gsz.Add(g_enable, 0, wx.ALL, 4)
        header_ui['g_enable'] = g_enable

        g_scroll = ScrolledPanel(header_panel, -1, size=(620, 130))
        g_scroll.SetupScrolling(scroll_x=False, scroll_y=True)
        g_inner = wx.FlexGridSizer(cols=3, vgap=5, hgap=5)
        g_inner.AddGrowableCol(1, 1)
        g_inner.Add(wx.StaticText(g_scroll, label="名称/键"), 0, wx.ALIGN_CENTER_VERTICAL)
        g_inner.Add(wx.StaticText(g_scroll, label="值"), 0, wx.ALIGN_CENTER_VERTICAL)
        g_inner.Add(wx.StaticText(g_scroll, label=""), 0)
        g_scroll.SetSizer(g_inner)
        gsz.Add(g_scroll, 1, wx.EXPAND | wx.BOTTOM, 5)
        g_add_btn = wx.Button(header_panel, label="+ 添加全局请求头条目")
        gsz.Add(g_add_btn, 0, wx.ALL, 2)
        header_ui['g_scroll'] = g_scroll
        header_ui['g_inner'] = g_inner
        header_ui['g_rows'] = []
        header_ui['g_add'] = g_add_btn

        gsz.Add(wx.StaticText(header_panel, label="全局默认 Cookie："), 0, wx.LEFT | wx.TOP, 6)
        g_cookie = wx.TextCtrl(header_panel, style=wx.TE_MULTILINE, size=(620, 60))
        gsz.Add(g_cookie, 0, wx.EXPAND | wx.ALL, 4)
        header_ui['g_cookie'] = g_cookie

        s.Add(gsz, 0, wx.EXPAND | wx.ALL, 8)

        # ============ 操作按钮 ============
        action_row = wx.BoxSizer(wx.HORIZONTAL)
        save_header_btn = wx.Button(header_panel, label="保存请求头配置")
        export_header_btn = wx.Button(header_panel, label="导出配置")
        action_row.Add(save_header_btn, 0, wx.RIGHT, 5)
        action_row.Add(export_header_btn, 0)
        s.Add(action_row, 0, wx.ALL, 8)
        header_ui['save_btn'] = save_header_btn
        header_ui['export_btn'] = export_header_btn

        # ---------- 公共函数 ----------
        def refresh_scroll(scroll):
            scroll.Layout()
            try:
                scroll.SetupScrolling(scroll_x=False, scroll_y=True)
                scroll.FitInside()
            except Exception:
                pass

        def owner_inner(owner_ui):
            return kv_inner if owner_ui is kv_scroll else g_inner

        def owner_rows(owner_ui):
            return header_ui['kv_rows'] if owner_ui is kv_scroll else header_ui['g_rows']

        def append_row(owner_ui, prefill_key="", prefill_val=""):
            inner = owner_inner(owner_ui)
            rows = owner_rows(owner_ui)
            key = wx.TextCtrl(owner_ui, size=(150, -1))
            val = wx.TextCtrl(owner_ui, size=(300, -1))
            val.SetHint("支持 {url} {domain} {filename} 等宏")
            del_btn = wx.Button(owner_ui, label="移除", size=(52, -1))
            row = (key, val, del_btn)
            rows.append(row)
            inner.Add(key, 0, wx.EXPAND)
            inner.Add(val, 1, wx.EXPAND)
            inner.Add(del_btn, 0, wx.ALIGN_CENTER_VERTICAL)
            def on_del(evt):
                try:
                    rows.remove(row)
                    for ctrl in row:
                        inner.Detach(ctrl)
                        ctrl.Destroy()
                    owner_ui.Layout()
                    owner_ui.Refresh()
                    refresh_scroll(owner_ui)
                except Exception:
                    pass
            del_btn.Bind(wx.EVT_BUTTON, on_del)
            key.SetValue(prefill_key)
            val.SetValue(prefill_val)
            refresh_scroll(owner_ui)

        add_kv_btn.Bind(wx.EVT_BUTTON, lambda e: add_templated_row(kv_scroll, 'kv_tpl_idx'))
        g_add_btn.Bind(wx.EVT_BUTTON, lambda e: add_templated_row(g_scroll, 'g_tpl_idx'))

        def add_templated_row(owner_ui, idx_key):
            i = header_ui.get(idx_key, 0)
            if KV_TEMPLATES:
                key, val = KV_TEMPLATES[i % len(KV_TEMPLATES)]
                i = (i + 1) % len(KV_TEMPLATES)
            else:
                key, val = "", ""
            header_ui[idx_key] = i
            append_row(owner_ui, key, val)
            refresh_scroll(owner_ui)

        active_idx = {'v': -1}

        def clear_editor():
            name_ctrl.SetValue("")
            domain_ctrl.SetValue("")
            enable_chk.SetValue(True)
            header_ui['kv_rows'].clear()
            kv_inner.Clear(delete_windows=True)
            add_header_labels(kv_inner, kv_scroll)
            cookie_ctrl.SetValue("")
            active_idx['v'] = -1
            refresh_scroll(kv_scroll)

        def add_header_labels(inner, owner):
            inner.Add(wx.StaticText(owner, label="名称/键"), 0, wx.ALIGN_CENTER_VERTICAL)
            inner.Add(wx.StaticText(owner, label="值"), 0, wx.ALIGN_CENTER_VERTICAL)
            inner.Add(wx.StaticText(owner, label=""), 0)

        def fill_rows(inner, rows_list, items, owner_ui):
            rows_list.clear()
            inner.Clear(delete_windows=True)
            add_header_labels(inner, owner_ui)
            for item in items or []:
                append_row(owner_ui, item.get('key', ''), item.get('value', ''))
            refresh_scroll(owner_ui)

        def load_rule(idx):
            rule = site_data['rules'][idx]
            active_idx['v'] = idx
            name_ctrl.SetValue(rule.get('name', ''))
            domain_ctrl.SetValue(rule.get('domain', ''))
            enable_chk.SetValue(bool(rule.get('enabled', True)))
            fill_rows(kv_inner, header_ui['kv_rows'], rule.get('headers', []), kv_scroll)
            cookie_ctrl.SetValue(rule.get('cookie', ''))

        def save_current_to_data():
            idx = active_idx['v']
            if idx < 0 or idx >= len(site_data['rules']):
                return
            rule = site_data['rules'][idx]
            rule['name'] = name_ctrl.GetValue().strip()
            rule['domain'] = domain_ctrl.GetValue().strip()
            rule['enabled'] = bool(enable_chk.GetValue())
            headers = []
            for (key, val, _) in header_ui['kv_rows']:
                headers.append({'key': key.GetValue().strip(), 'value': val.GetValue()})
            rule['headers'] = headers
            rule['cookie'] = cookie_ctrl.GetValue()

        def rebuild_choice():
            names = [r.get('name') or r.get('domain') or '未命名' for r in site_data['rules']]
            site_choice.SetItems(names if names else ["__NONE__"])
            site_choice.SetSelection(0)
            if names:
                load_rule(0)
            else:
                clear_editor()

        def on_new_site(evt):
    
            save_current_to_data()
            site_data['rules'].append(SiteHeaders.new_rule("", ""))
            rebuild_choice()
            site_choice.SetSelection(len(site_data['rules']) - 1)
            load_rule(len(site_data['rules']) - 1)

        def on_del_site(evt):
            idx = active_idx['v']
            if idx < 0 or idx >= len(site_data['rules']):
                return
            if wx.MessageBox("确定删除当前站点规则吗？", "确认删除",
                             wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
                return
            del site_data['rules'][idx]
            rebuild_choice()

        def on_choice_change(evt):
            idx = site_choice.GetSelection()
            if idx < 0 or idx >= len(site_data['rules']):
                return
           
            save_current_to_data()
            load_rule(idx)

        site_choice.Bind(wx.EVT_CHOICE, on_choice_change)
        new_btn.Bind(wx.EVT_BUTTON, on_new_site)
        del_btn.Bind(wx.EVT_BUTTON, on_del_site)


        def on_save_headers(evt):
            save_current_to_data()
            site_data['default_enabled'] = bool(g_enable.GetValue())
            g_headers = []
            for (key, val, _) in header_ui['g_rows']:
                g_headers.append({'key': key.GetValue().strip(), 'value': val.GetValue()})
            site_data['default_headers'] = g_headers
            site_data['default_cookie'] = g_cookie.GetValue()
            if SiteHeaders.save_data(site_data):
                wx.MessageBox("请求头配置已保存", "提示", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox("保存失败", "错误", wx.OK | wx.ICON_ERROR)

        def on_export_headers(evt):
            save_current_to_data()
            text = SiteHeaders.export_all_as_text(site_data)
            if not text.strip():
                text = "（暂无启用中的站点请求头配置）"
            dlg = wx.TextEntryDialog(
                header_panel,
                "导出结果（站点规则为纯文本格式）：",
                "导出请求头配置",
                value=text, style=wx.OK | wx.CANCEL)
            dlg.SetSize(600, 420)
            dlg.ShowModal()
            dlg.Destroy()

        save_header_btn.Bind(wx.EVT_BUTTON, on_save_headers)
        export_header_btn.Bind(wx.EVT_BUTTON, on_export_headers)

        
        def on_import_cookie(evt):

            prefill = ""
            try:
                tobj = wx.TextDataObject()
                if wx.TheClipboard.Open():
                    if wx.TheClipboard.GetData(tobj):
                        prefill = tobj.GetText()
                    wx.TheClipboard.Close()
            except Exception:
                pass

            dlg = wx.TextEntryDialog(
                header_panel,
                "粘贴浏览器导出的请求头（右键请求 → “复制为 cURL” 或 “复制请求头”）：\n"
                "将自动识别并拆分请求头与 Cookie。",
                "导入浏览器请求头",
                value=prefill, style=wx.OK | wx.CANCEL)
            dlg.SetSize(640, 420)
            if dlg.ShowModal() != wx.ID_OK:
                dlg.Destroy()
                return
            text = dlg.GetValue()
            dlg.Destroy()

            if not text.strip():
                wx.MessageBox("未输入内容。", "提示", wx.OK | wx.ICON_INFORMATION)
                return

            parsed = SiteHeaders.parse_browser_export(text)
            if not parsed["headers"] and not parsed["cookie"]:
                wx.MessageBox("未能从内容中解析出请求头条目。\n请确认是“Key: Value”格式或 cURL 命令。",
                              "提示", wx.OK | wx.ICON_INFORMATION)
                return


            auto_filled = False
            if parsed.get("url") and not domain_ctrl.GetValue().strip():
                try:
                    from urllib.parse import urlparse
                    host = (urlparse(parsed["url"]).hostname or "").lower()
                    if host:
      
                        domain_ctrl.SetValue(("*." + host) if not host.startswith("www.") else host)
                        auto_filled = True
                except Exception:
                    pass


            fill_rows(kv_inner, header_ui['kv_rows'],
                      [{'key': k, 'value': v} for k, v in parsed["headers"]], kv_scroll)

            if parsed["cookie"]:
                cookie_ctrl.SetValue(parsed["cookie"])

            warn = ""

            if not parsed.get("url"):
                warn = "\n\n注意：复制内容中未包含 URL，无法自动填充“匹配域名”。\n请在该规则“匹配域名”栏填写本站域名（如 example.com），否则此站点请求头不会被应用。"
            elif not auto_filled:
                warn = "\n\n注意：未自动填充“匹配域名”，请检查该规则的域名是否能匹配你要爬取/下载的网址。"

            wx.MessageBox(
                f"已导入 {len(parsed['headers'])} 条请求头" +
                (f"、Cookie({len(parsed['cookie'])} 字符)" if parsed["cookie"] else "") +
                "。\n请核验后点击下方“保存请求头配置”。" + (warn if parsed["cookie"] or parsed["headers"] else ""),
                "导入完成", wx.OK | wx.ICON_INFORMATION)

        import_cookie_btn.Bind(wx.EVT_BUTTON, on_import_cookie)

        # ---------- 初始化 ----------
        fill_rows(g_inner, header_ui['g_rows'], site_data.get('default_headers', []), g_scroll)
        g_cookie.SetValue(site_data.get('default_cookie', ''))
        rebuild_choice()

    add_static_box(header_panel, header_sizer, "请求头设置（站点式）", header_content)

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

    
    def host_installed():
        host_name = "com.nodanium.yujy"
        if platform.system() == "Windows":
            dirs = [os.path.join(os.getenv('LOCALAPPDATA', ''), "Google", "Chrome", "NativeMessagingHosts"),
                    os.path.join(os.getenv('APPDATA', ''), "Mozilla", "NativeMessagingHosts")]
          
            dirs.append(os.path.join(os.getenv('LOCALAPPDATA', ''), "Microsoft", "Edge", "User Data", "NativeMessagingHosts"))
            return any(os.path.exists(os.path.join(d, host_name + ".json")) for d in dirs)
       
        dirs = ["$HOME/.config/google-chrome/NativeMessagingHosts",
                "$HOME/.config/chromium/NativeMessagingHosts",
                "$HOME/.config/microsoft-edge/NativeMessagingHosts",
                "$HOME/.mozilla/native-messaging-hosts",
                "$HOME/.config/mozilla/native-messaging-hosts"]
        home = os.path.expanduser("~")
        return any(os.path.exists(os.path.join(d.replace("$HOME", home), host_name + ".json")) for d in dirs)

 
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
        host_status_txt.SetLabel("Native Host 状态： 已安装" if ok else "❌ 未安装（点击下方按钮一键安装）")
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
        try:
            with open(plugin_cfg_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.warning(f"写入插件配置失败: {e}")

    install_btn = wx.Button(plugin_panel, label="安装 / 重新安装 Native Host")
    install_btn.SetToolTip("注册 com.nodanium.yujy 到浏览器\n(Chrome / Edge / Firefox)")
    plugin_sizer.Add(install_btn, 0, wx.EXPAND | wx.ALL, 5)

    def on_install_host(event):
        if not os.path.isdir(PLUGIN_DIR):
            wx.MessageBox("未找到浏览器插件目录：\n" + PLUGIN_DIR, "错误", wx.OK | wx.ICON_ERROR)
            return

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
       
        _cand_root = os.path.dirname(os.path.dirname(PLUGIN_DIR)) if os.path.basename(PLUGIN_DIR) == "Nodanium-BrowserPlugin" else PLUGIN_DIR
        for _cand in ("nodanium", "NodaniumLauncher.py", "NodaniumLauncher", "nodanium.bin"):
            _p = os.path.join(_cand_root, _cand)
            if os.path.exists(_p) and os.path.isfile(_p):
                _main_default = _p
                break
   
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
    notebook.AddPage(down_panel, "下载")
    notebook.AddPage(storage_panel, "存储")
    notebook.AddPage(header_panel, "请求头")
    notebook.AddPage(port_panel, "端口")
    # 浏览器插件面板已隐藏，不再加入首选项（plugin_sizer 中的控件仍会被 save_plugin_config_file 引用）

    # ========================== 配置 ==========================
    config_panel, config_sizer = make_scroll_panel(notebook)

    sys_type = platform.system()

    app_dir = os.path.dirname(os.path.abspath(__file__))
    _exe = sys.executable.lower()
    is_frozen = not (_exe.endswith('python.exe') or _exe.endswith('pythonw.exe') or
                     _exe.endswith('python3') or _exe.endswith('python'))

    if is_frozen:
        main_script = sys.executable
    else:
        main_script = os.path.join(app_dir, "NodaniumLauncher.py")

    def _build_cmd(args):
        """Build a command line string for launching Nodanium."""
        if is_frozen:
            return f'"{sys.executable}" {args}'
        else:
            if sys_type == "Windows":
                python_dir = os.path.dirname(sys.executable)
                pythonw = os.path.join(python_dir, "pythonw.exe")
                launcher = os.path.abspath(main_script)
                if os.path.exists(pythonw):
                    return f'"{pythonw}" "{launcher}" {args}'
                return f'"{sys.executable}" "{launcher}" {args}'
            else:
                launcher = os.path.abspath(main_script)
                return f'{sys.executable} "{launcher}" {args}'

  
    autostart_box = wx.StaticBox(config_panel, label="开机自启动")
    autostart_sizer = wx.StaticBoxSizer(autostart_box, wx.VERTICAL)

    autostart_check = wx.CheckBox(config_panel, label="开机自动启动 Nodanium")

    def _autostart_desktop_path():
        return os.path.expanduser("~/.config/autostart/nodanium.desktop")

    def get_autostart_status():
        try:
            if sys_type == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                     r"Software\Microsoft\Windows\CurrentVersion\Run",
                                     0, winreg.KEY_READ)
                try:
                    winreg.QueryValueEx(key, "Nodanium")
                    return True
                except FileNotFoundError:
                    return False
                finally:
                    winreg.CloseKey(key)
            elif sys_type == "Linux":
                return os.path.exists(_autostart_desktop_path())
        except Exception:
            return False
        return False

    def set_autostart(enable):
        """返回 (是否成功, 错误信息)"""
        try:
            if sys_type == "Windows":
                import winreg
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                       r"Software\Microsoft\Windows\CurrentVersion\Run")
                try:
                    if enable:
                        winreg.SetValueEx(key, "Nodanium", 0, winreg.REG_SZ, _build_cmd("-s"))
                    else:
                        try:
                            winreg.DeleteValue(key, "Nodanium")
                        except FileNotFoundError:
                            pass
                finally:
                    winreg.CloseKey(key)
            elif sys_type == "Linux":
                desktop_path = _autostart_desktop_path()
                if enable:
                    os.makedirs(os.path.dirname(desktop_path), exist_ok=True)
                    if is_frozen:
                        exec_line = f"{sys.executable} -s"
                    else:
                        exec_line = f"{sys.executable} {os.path.abspath(main_script)} -s"
                    with open(desktop_path, 'w') as f:
                        f.write("[Desktop Entry]\nType=Application\nName=Nodanium\n"
                                f"Exec={exec_line}\nX-GNOME-Autostart-enabled=true\nTerminal=false\n")
                else:
                    if os.path.exists(desktop_path):
                        os.remove(desktop_path)
            else:
                return False, "当前系统不支持"
            return True, None
        except Exception as e:
            return False, str(e)

    autostart_check.SetValue(get_autostart_status())

    def on_autostart_toggle(event):
        ok, err = set_autostart(autostart_check.GetValue())
        if not ok:
            autostart_check.SetValue(not autostart_check.GetValue())
            logging.warning(f"设置开机自启失败: {err}")

    autostart_check.Bind(wx.EVT_CHECKBOX, on_autostart_toggle)
    autostart_sizer.Add(autostart_check, 0, wx.ALL, 8)
    config_sizer.Add(autostart_sizer, 0, wx.EXPAND | wx.ALL, 8)

    # --- 文件关联
    filetype_box = wx.StaticBox(config_panel, label="文件关联")
    filetype_sizer = wx.StaticBoxSizer(filetype_box, wx.VERTICAL)

    filetype_desc = wx.StaticText(config_panel,
        label="双击关联文件即可用 Nodanium 打开：\n"
              "· .ndf —— 恢复下载\n"
              "· .torrent —— 添加到 BT 下载")
    filetype_desc.SetForegroundColour(wx.Colour(90, 90, 90))
    filetype_sizer.Add(filetype_desc, 0, wx.ALL, 8)

    ndf_check = wx.CheckBox(config_panel, label="关联 .ndf 文件")
    torrent_check = wx.CheckBox(config_panel, label="关联 .torrent 文件")
    filetype_sizer.Add(ndf_check, 0, wx.LEFT | wx.RIGHT, 8)
    filetype_sizer.Add(torrent_check, 0, wx.ALL, 8)

    def _icon_path():
        p = os.path.join(app_dir, "icons", "ANT_icon.png")
        return p if os.path.exists(p) else sys.executable

    def _delete_reg_tree(root, path):
        import winreg
        try:
            with winreg.OpenKey(root, path, 0, winreg.KEY_ALL_ACCESS) as key:
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, 0)
                        _delete_reg_tree(root, path + "\\" + subkey_name)
                    except OSError:
                        break
            winreg.DeleteKey(root, path)
        except FileNotFoundError:
            pass

    def _win_register(ext, prog_id, desc, content_type, open_args):
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\." + ext.lstrip(".")) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, prog_id)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\" + prog_id) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, desc)
            winreg.SetValueEx(k, "Content Type", 0, winreg.REG_SZ, content_type)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\" + prog_id + r"\DefaultIcon") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _icon_path())
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              "Software\\Classes\\" + prog_id + r"\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, _build_cmd(open_args))

    def _win_unregister(ext, prog_id):
        import winreg
        _delete_reg_tree(winreg.HKEY_CURRENT_USER, "Software\\Classes\\" + prog_id)
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Classes\." + ext.lstrip(".")) as k:
                try:
                    val, _ = winreg.QueryValueEx(k, "")
                    if val == prog_id:
                        winreg.DeleteValue(k, "")
                except Exception:
                    pass
        except FileNotFoundError:
            pass

    def _linux_write_desktop():
        exec_line = f"{sys.executable} --open=%f" if is_frozen \
            else f"{sys.executable} {os.path.abspath(main_script)} --open=%f"
        desktop_path = os.path.expanduser("~/.local/share/applications/nodanium.desktop")
        os.makedirs(os.path.dirname(desktop_path), exist_ok=True)
        with open(desktop_path, 'w') as f:
            f.write("[Desktop Entry]\nType=Application\nName=Nodanium\n"
                    "MimeType=application/x-nodanium;application/x-bittorrent;\n"
                    f"Exec={exec_line}\nTerminal=false\n")

    def _linux_write_mime():
        mime_dir = os.path.expanduser("~/.local/share/mime/packages")
        os.makedirs(mime_dir, exist_ok=True)
        with open(os.path.join(mime_dir, "nodanium.xml"), 'w') as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">\n'
                    '  <mime-type type="application/x-nodanium">\n'
                    '    <comment>Nodanium 下载进度文件</comment>\n'
                    '    <glob pattern="*.ndf"/>\n'
                    '  </mime-type>\n'
                    '</mime-info>\n')

    def _linux_update_db():
        for cmd in (["update-mime-database", os.path.expanduser("~/.local/share/mime")],
                    ["update-desktop-database", os.path.expanduser("~/.local/share/applications")]):
            try:
                subprocess.run(cmd, capture_output=True, timeout=30)
            except Exception:
                pass

    def _linux_remove_desktop_if_unused():
        if not (ndf_check.GetValue() or torrent_check.GetValue()):
            p = os.path.expanduser("~/.local/share/applications/nodanium.desktop")
            if os.path.exists(p):
                os.remove(p)
        _linux_update_db()

    def get_ndf_status():
        try:
            if sys_type == "Windows":
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.ndf") as k:
                    val, _ = winreg.QueryValueEx(k, "")
                    return val == "Nodanium.ndf"
            elif sys_type == "Linux":
                return os.path.exists(os.path.expanduser("~/.local/share/mime/packages/nodanium.xml"))
        except Exception:
            return False
        return False

    def get_torrent_status():
        try:
            if sys_type == "Windows":
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.torrent") as k:
                    val, _ = winreg.QueryValueEx(k, "")
                    return val == "Nodanium.torrent"
            elif sys_type == "Linux":
                return os.path.exists(os.path.expanduser("~/.local/share/applications/nodanium.desktop"))
        except Exception:
            return False
        return False

    def on_ndf_toggle(event):
        enable = ndf_check.GetValue()
        try:
            if sys_type == "Windows":
                if enable:
                    _win_register(".ndf", "Nodanium.ndf", "Nodanium 下载进度文件",
                                  "application/x-nodanium", '--resume="%1"')
                else:
                    _win_unregister(".ndf", "Nodanium.ndf")
            elif sys_type == "Linux":
                if enable:
                    _linux_write_mime()
                else:
                    p = os.path.expanduser("~/.local/share/mime/packages/nodanium.xml")
                    if os.path.exists(p):
                        os.remove(p)
                _linux_update_db()
        except Exception as e:
            ndf_check.SetValue(not enable)
            logging.warning(f"设置 .ndf 关联失败: {e}")

    def on_torrent_toggle(event):
        enable = torrent_check.GetValue()
        try:
            if sys_type == "Windows":
                if enable:
                    _win_register(".torrent", "Nodanium.torrent", "Nodanium BT 种子文件",
                                  "application/x-bittorrent", '--torrent="%1"')
                else:
                    _win_unregister(".torrent", "Nodanium.torrent")
            elif sys_type == "Linux":
                if enable:
                    _linux_write_desktop()
                else:
                    _linux_remove_desktop_if_unused()
                _linux_update_db()
        except Exception as e:
            torrent_check.SetValue(not enable)
            logging.warning(f"设置 .torrent 关联失败: {e}")

    ndf_check.Bind(wx.EVT_CHECKBOX, on_ndf_toggle)
    torrent_check.Bind(wx.EVT_CHECKBOX, on_torrent_toggle)

    ndf_check.SetValue(get_ndf_status())
    torrent_check.SetValue(get_torrent_status())

    filetype_sizer.Add(wx.StaticText(config_panel,
        label="提示：Linux 下 .torrent 与 .ndf 共用同一桌面项。"), 0, wx.ALL, 8)
    config_sizer.Add(filetype_sizer, 0, wx.EXPAND | wx.ALL, 8)

    notebook.AddPage(config_panel, "配置")

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
        config['dl_read_stall'] = stall_ctrl.GetValue()
        config['dl_threads'] = threads_ctrl.GetValue()
        config['dl_chunk_mb'] = chunk_ctrl.GetValue()
        config['dl_cache_mb'] = cache_ctrl.GetValue()
        config['dl_speed_unit'] = unit_ctrl.GetStringSelection()
        config['dl_disable_ssl'] = ssl_ctrl.GetValue()
        config['bt_use_service'] = bt_service_ctrl.GetValue()
        config['bt_seed_time'] = bt_seed_time_ctrl.GetValue()
        try:
            config['bt_seed_ratio'] = round(float(bt_seed_ratio_ctrl.GetValue()), 1)
        except Exception:
            config['bt_seed_ratio'] = 1.0

        if 'share_path' in config:
            config['share_path'] = config.get('share_path', '')

        try:
            import NewDownloadCore
            NewDownloadCore.DEFAULT_RETRY = retry_ctrl.GetValue()
            NewDownloadCore.DEFAULT_TIMEOUT = timeout_ctrl.GetValue()
            NewDownloadCore.READ_STALL_TIMEOUT = stall_ctrl.GetValue()
        except Exception:
            pass


        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                disk_cfg = json.load(f)
            if not isinstance(disk_cfg, dict):
                disk_cfg = {}
        except Exception:
            disk_cfg = {}
        disk_cfg.update(config)
        config.update(disk_cfg)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(disk_cfg, f, ensure_ascii=False, indent=4)

        save_plugin_config_file()

        wx.MessageBox("设置已保存", "提示", wx.OK | wx.ICON_INFORMATION)

    save_button = wx.Button(options_window, label="保存设置")
    save_button.Bind(wx.EVT_BUTTON, on_save_config)

    main_sizer = wx.BoxSizer(wx.VERTICAL)
    main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
    main_sizer.Add(save_button, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

    options_window.SetSizer(main_sizer)
    options_window.Show()

    for sp, _clamp in scroll_panels:
        sp.Layout()
        try:
            sp.FitInside()
        except Exception:
            pass
  
        _clamp()