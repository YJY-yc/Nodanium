# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import wx
import wx.lib.mixins.listctrl as listmix
import os
import json
import datetime
import logging
import platform

# 跨平台数据目录配置
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

DATA_FOLDER = get_data_folder()
HISTORY_FILE = os.path.join(DATA_FOLDER, 'History.json')

from DownloadCore import download_window
logging.info('加载 DownloadUI 模块')
download_history = []

def load_download_history():
    logging.info("读取下载记录")

    global download_history
    try:
        history_dir = os.path.dirname(HISTORY_FILE)
        if not os.path.exists(history_dir):
            os.makedirs(history_dir, exist_ok=True)
            
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                loaded_history = json.load(f)
                
                if isinstance(loaded_history, list):
                    download_history = loaded_history
                    
                    download_history.sort(key=lambda x: x.get("timestamp", ""))
                    print(f"成功加载 {len(download_history)} 条下载记录")
                    logging.info(f"成功加载 {len(download_history)} 条下载记录")
                else:
                    print("历史文件格式错误，重置为空列表")
                    logging.warning("历史文件格式错误，重置为空列表")
                    download_history = []
                    save_download_history()
        else:
            download_history = []
            
            save_download_history()
            print("创建新的下载历史文件")
            logging.info("创建新的下载历史文件")
    except Exception as e:
        print(f"加载下载历史失败: {e}")
        logging.error(f"加载下载历史失败: {e}")
        download_history = []
        

if not download_history or len(download_history) == 0:
    load_download_history()

def save_download_history():
    """保存下载历史"""
    try:
        history_dir = os.path.dirname(HISTORY_FILE)
        if not os.path.exists(history_dir):
            os.makedirs(history_dir, exist_ok=True)
            
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(download_history, f, ensure_ascii=False, indent=2)
        print(f"成功保存 {len(download_history)} 条下载记录")
        logging.info(f"成功保存 {len(download_history)} 条下载记录")
    except Exception as e:
        print(f"保存下载历史失败: {e}")
        logging.error(f"保存下载历史失败: {e}")
def add_download_record(url, filename, save_path, status="已完成", file_size=0, download_items=None, batch_id=None, completed=None, total=None, file_count=None, success_count=None, failed_count=None):
    """添加下载记录"""
    record = {
        "url": url,
        "filename": filename,
        "save_path": save_path,
        "status": status,
        "file_size": file_size,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    if download_items is not None:
        record["download_items"] = download_items
    
   
    if batch_id is not None:
        record["batch_id"] = batch_id
    
    if completed is not None:
        record["completed"] = completed
    if total is not None:
        record["total"] = total
    
    if file_count is not None:
        record["file_count"] = file_count
    if success_count is not None:
        record["success_count"] = success_count
    if failed_count is not None:
        record["failed_count"] = failed_count
    
    download_history.append(record)
    save_download_history()
    return record
def get_file_icon(file_path, size=32):

    icon_size = (size, size)
    
    try:
       
        if not os.path.exists(file_path):
            print(f"文件不存在: {file_path}")
            logging.warning(f"文件不存在: {file_path}")
            return get_fallback_icon(file_path, size)
        
        file_path = os.path.abspath(file_path)
        

        if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.ico', '.gif')):
            if True:
                try:
                   
                    img = Image.open(file_path)
                   
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')
                    
                    img = img.resize(icon_size, Image.Resampling.LANCZOS)
                    
                   
                    import io
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    
                   
                    wx_img = wx.Image(icon_size[0], icon_size[1])
                    wx_img.LoadFile(img_bytes, wx.BITMAP_TYPE_PNG)
                    bitmap = wx.Bitmap(wx_img)
                    
                    return bitmap
                except Exception as img_error:
                    print(f"直接加载图片失败: {img_error}")
                    logging.error(f"直接加载图片失败: {img_error}")
        
       
        try:
            import ctypes
            from ctypes import wintypes
            
            class SHFILEINFOW(ctypes.Structure):
                _fields_ = [
                    ("hIcon", ctypes.c_void_p),
                    ("iIcon", ctypes.c_int),
                    ("dwAttributes", ctypes.c_ulong),
                    ("szDisplayName", ctypes.c_wchar * 260),
                    ("szTypeName", ctypes.c_wchar * 80)
                ]
            
            shell32 = ctypes.windll.shell32
            SHGFI_ICON = 0x100
            SHGFI_LARGEICON = 0x0
            
            shfi = SHFILEINFOW()
            file_attr = win32con.FILE_ATTRIBUTE_NORMAL
            if os.path.isdir(file_path):
                file_attr = win32con.FILE_ATTRIBUTE_DIRECTORY
            
            ret = shell32.SHGetFileInfoW(
                file_path,
                file_attr,
                ctypes.byref(shfi),
                ctypes.sizeof(shfi),
                SHGFI_ICON | SHGFI_LARGEICON
            )
            
            if not ret or not shfi.hIcon:
                print("无法获取图标句柄")
                logging.warning("无法获取图标句柄")
                return get_fallback_icon(file_path, size)
            
          
            hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
            hbmp = win32ui.CreateBitmap()
            hbmp.CreateCompatibleBitmap(hdc, icon_size[0], icon_size[1])
            hdc = hdc.CreateCompatibleDC()
            hdc.SelectObject(hbmp)
            
            
            win32gui.DrawIconEx(
                hdc.GetHandleOutput(),
                0, 0,
                shfi.hIcon,
                icon_size[0], icon_size[1],
                0, None, 0x0003
            )
            
            if True:
               
                bmpinfo = hbmp.GetInfo()
                bmpstr = hbmp.GetBitmapBits(True)
                img = Image.frombuffer(
                    'RGBA',
                    (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                    bmpstr, 'raw', 'BGRA', 0, 1
                )
                
              
                img = img.resize(icon_size, Image.Resampling.LANCZOS)
                
              
                import io
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)
                
                wx_img = wx.Image(icon_size[0], icon_size[1])
                wx_img.LoadFile(img_bytes, wx.BITMAP_TYPE_PNG)
                bitmap = wx.Bitmap(wx_img)
         
        
            win32gui.DestroyIcon(shfi.hIcon)
            return bitmap
            
        except Exception as sys_error:
            print(f"系统图标获取失败: {sys_error}")
            logging.error(f"系统图标获取失败: {sys_error}")
            return get_fallback_icon(file_path, size)
            
    except Exception as e:
        print(f"图标处理异常: {e}")
        logging.error(f"图标处理异常: {e}")
        import traceback
        traceback.print_exc()
        return get_fallback_icon(file_path, size)

def get_fallback_icon(file_path, size=16):
    """备用图标方案"""
    try:
       
        ext = os.path.splitext(file_path)[1].lower()
        
      
        if ext in ['.exe', '.com', '.bat', '.cmd']:
            return wx.ArtProvider.GetBitmap(wx.ART_EXECUTABLE_FILE, wx.ART_OTHER, (size, size))
        elif ext in ['.txt', '.log', '.ini', '.conf']:
            return wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, (size, size))
        elif ext in ['.pdf']:
            return wx.ArtProvider.GetBitmap(wx.ART_PDF, wx.ART_OTHER, (size, size))
        elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz']:
            return wx.ArtProvider.GetBitmap(wx.ART_ZIP, wx.ART_OTHER, (size, size))
        elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.ico']:
            return wx.ArtProvider.GetBitmap(wx.ART_IMAGE, wx.ART_OTHER, (size, size))
        elif ext in ['.mp3', '.wav', '.flac', '.aac']:
            return wx.ArtProvider.GetBitmap(wx.ART_MUSIC, wx.ART_OTHER, (size, size))
        elif ext in ['.mp4', '.avi', '.mkv', '.mov']:
            return wx.ArtProvider.GetBitmap(wx.ART_VIDEO, wx.ART_OTHER, (size, size))
        elif ext in ['.doc', '.docx']:
            return wx.ArtProvider.GetBitmap(wx.ART_DOCUMENT, wx.ART_OTHER, (size, size))
        elif ext in ['.xls', '.xlsx']:
            return wx.ArtProvider.GetBitmap(wx.ART_SPREADSHEET, wx.ART_OTHER, (size, size))
        elif ext in ['.ppt', '.pptx']:
            return wx.ArtProvider.GetBitmap(wx.ART_PRESENTATION, wx.ART_OTHER, (size, size))
        elif ext in ['.html', '.htm']:
            return wx.ArtProvider.GetBitmap(wx.ART_HTML, wx.ART_OTHER, (size, size))
        else:
           
            return wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, (size, size))
            
    except Exception as e:
        print(f"获取备用图标失败: {e}")
        logging.error(f"获取备用图标失败: {e}")
        return wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, (size, size))
def refresh_download_list(list_ctrl, image_list):
    """刷新下载列表"""
 
    load_download_history()
    
    list_ctrl.DeleteAllItems()
    image_list.RemoveAll()
    
    icon_cache = {}  
    
    for record in download_history:
       
        file_path = os.path.join(record["save_path"], record["filename"])
        
        ext = os.path.splitext(record["filename"])[1].lower()
        if ext not in icon_cache:
            icon = get_file_icon(file_path)
            icon_index = image_list.Add(icon)
            icon_cache[ext] = icon_index
        else:
            icon_index = icon_cache[ext]
        
  
        index = list_ctrl.InsertItem(list_ctrl.GetItemCount(), icon_index)
        
        file_size = record.get("file_size", 0)
        if file_size == 0:
            size_str = "未知"
        elif file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        elif file_size < 1024 * 1024 * 1024:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{file_size / (1024 * 1024 * 1024):.1f} GB"
        
      
        list_ctrl.SetItem(index, 1, record["filename"])
        
     
        list_ctrl.SetItem(index, 2, size_str)
        
 
        status = record["status"]
        

        if record.get("url") == "批量下载文件夹":
            file_count = record.get("file_count", 0)
            success_count = record.get("success_count", 0)
            failed_count = record.get("failed_count", 0)
            completed = record.get("completed", 0)
            total = record.get("total", 0)
            
            if total > 0:
                progress = f" ({completed}/{total})"
            else:
                progress = ""
                
            if file_count > 0:
                status = f"{status}{progress} - {success_count}成功/{failed_count}失败"
            else:
                status = f"{status}{progress}"
        
        list_ctrl.SetItem(index, 3, status)
        list_ctrl.SetItem(index, 4, record["save_path"])
        list_ctrl.SetItem(index, 5, record["timestamp"])

def create_download_panel(parent):
    global HISTORY_FILE
    panel =parent
    

    main_sizer = wx.BoxSizer(wx.VERTICAL)

    control_sizer = wx.BoxSizer(wx.HORIZONTAL)
    

    new_download_btn = wx.Button(panel, label="新建下载")
    control_sizer.Add(new_download_btn, 0, wx.ALL, 5)
    
    delete_btn = wx.Button(panel, label="删除")
    control_sizer.Add(delete_btn, 0, wx.ALL, 5)
    
    clear_btn = wx.Button(panel, label="清空历史")
    control_sizer.Add(clear_btn, 0, wx.ALL, 5)

    open_folder_btn = wx.Button(panel, label="打开文件夹")
    control_sizer.Add(open_folder_btn, 0, wx.ALL, 5)

    refresh_btn = wx.Button(panel, label="刷新")
    control_sizer.Add(refresh_btn, 0, wx.ALL, 5)

    main_sizer.Add(control_sizer, 0, wx.EXPAND)
    

    line = wx.StaticLine(panel, style=wx.LI_HORIZONTAL)
    main_sizer.Add(line, 0, wx.EXPAND | wx.ALL, 5)
    

    download_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_HRULES | wx.LC_VRULES)
  
    image_list = wx.ImageList(32, 32)
    download_list.AssignImageList(image_list, wx.IMAGE_LIST_SMALL)
    
    download_list.InsertColumn(0, "", width=45)
    download_list.InsertColumn(1, "文件名", width=200)
    download_list.InsertColumn(2, "大小", width=100)
    download_list.InsertColumn(3, "状态", width=80)
    download_list.InsertColumn(4, "保存路径", width=300)
    download_list.InsertColumn(5, "时间", width=150)
    
    main_sizer.Add(download_list, 1, wx.EXPAND | wx.ALL, 5)

    panel.SetSizer(main_sizer)

    load_download_history()
    refresh_download_list(download_list, image_list)
  
    create_context_menu(download_list)
    # 跨平台配置目录
    sys_type = platform.system()
    if sys_type == "Windows":
        config_dir = os.path.join(os.getenv('APPDATA', ''), 'Nodanium')
        default_save_path = os.path.join(os.environ['USERPROFILE'], 'Downloads')
    else:
        config_dir = os.path.join(os.path.expanduser("~"), '.Nodanium')
        default_save_path = os.path.join(os.path.expanduser("~"), 'Downloads')
    dir_file = os.path.join(config_dir, 'dir.txt')
    if os.path.exists(dir_file):
        try:
            with open(dir_file, 'r', encoding='utf-8') as f:
                saved_path = f.read().strip()
                if saved_path and os.path.exists(saved_path):
                    default_save_path = saved_path
        except Exception as e:
            print(f"读取保存路径配置失败: {e}")
            logging.error(f"读取保存路径配置失败: {e}")

    new_download_btn.Bind(wx.EVT_BUTTON, lambda e: on_new_download(panel, download_list,  image_list))
    delete_btn.Bind(wx.EVT_BUTTON, lambda e: on_delete_download(download_list))
    clear_btn.Bind(wx.EVT_BUTTON, lambda e: on_clear_history(download_list))
    def open_folder(e):
        import subprocess
        import platform
        sys_type = platform.system()
        if sys_type == "Windows":
            os.startfile(default_save_path)
        else:
            # Linux/macOS 使用 xdg-open 或 open 命令
            try:
                if sys_type == "Darwin":
                    subprocess.run(['open', default_save_path])
                else:
                    subprocess.run(['xdg-open', default_save_path])
            except Exception as ex:
                wx.MessageBox(f"无法打开文件夹: {str(ex)}", "错误", wx.OK | wx.ICON_ERROR)
    
    open_folder_btn.Bind(wx.EVT_BUTTON, open_folder)
    download_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: on_item_activated(download_list, e))
    refresh_btn.Bind(wx.EVT_BUTTON, lambda e: (
        
        refresh_download_list(download_list, image_list)
    ))
    return panel
def create_context_menu(list_ctrl):
    """创建右键菜单"""
   
    menu = wx.Menu()
    
    open_item = menu.Append(wx.ID_OPEN, "打开")
    open_folder_item = menu.Append(wx.ID_ANY, "在文件夹中显示")
    show_items_item = menu.Append(wx.ID_ANY, "显示包含的项目") 
    redownload_item = menu.Append(wx.ID_ANY, "重新下载")
    menu.AppendSeparator()
    
   
    export_item = menu.Append(wx.ID_ANY, "导出选中项")
    menu.AppendSeparator()
    

    copy_menu = wx.Menu()
    copy_url_item = copy_menu.Append(wx.ID_ANY, "复制URL")
    copy_filename_item = copy_menu.Append(wx.ID_ANY, "复制文件名")
    copy_path_item = copy_menu.Append(wx.ID_ANY, "复制路径")
    menu.AppendSubMenu(copy_menu, "复制")
    
    menu.AppendSeparator()
    delete_item = menu.Append(wx.ID_DELETE, "删除")
    
   
    list_ctrl.Bind(wx.EVT_CONTEXT_MENU, lambda e: on_context_menu(e, list_ctrl, menu))
    list_ctrl.Bind(wx.EVT_MENU, lambda e: on_menu_open(e, list_ctrl), open_item)
    list_ctrl.Bind(wx.EVT_MENU, lambda e: on_menu_open_folder(e, list_ctrl), open_folder_item)
    list_ctrl.Bind(wx.EVT_MENU, lambda e: on_menu_show_items(e, list_ctrl), show_items_item)  # 绑定新菜单项
    list_ctrl.Bind(wx.EVT_MENU, lambda e: on_menu_redownload(e, list_ctrl), redownload_item)
    list_ctrl.Bind(wx.EVT_MENU, lambda e: on_menu_export(e, list_ctrl), export_item)  # 绑定导出菜单项
    list_ctrl.Bind(wx.EVT_MENU, lambda e: on_menu_copy_url(e, list_ctrl), copy_url_item)
    list_ctrl.Bind(wx.EVT_MENU, lambda e: on_menu_copy_filename(e, list_ctrl), copy_filename_item)
    list_ctrl.Bind(wx.EVT_MENU, lambda e: on_menu_copy_path(e, list_ctrl), copy_path_item)
    list_ctrl.Bind(wx.EVT_MENU, lambda e: on_menu_delete(e, list_ctrl), delete_item)
def on_context_menu(event, list_ctrl, menu):
    """显示右键菜单"""
    pos = event.GetPosition()
    pos = list_ctrl.ScreenToClient(pos)
    item = list_ctrl.HitTest(pos)[0]
    
    if item != -1:
        list_ctrl.Select(item)
     
        if 0 <= item < len(download_history):
            record = download_history[item]
         
            if record.get("url") == "批量下载文件夹":
                menu.FindItemByPosition(2).Enable(True)  
            else:
                menu.FindItemByPosition(2).Enable(False) 
        
        list_ctrl.PopupMenu(menu, pos)

def on_menu_show_items(event, list_ctrl):

    selected = list_ctrl.GetFirstSelected()
    if selected != -1 and 0 <= selected < len(download_history):
        record = download_history[selected]
        
        if record.get("url") == "批量下载文件夹" and record.get("download_items"):
    
            dlg = wx.Dialog(None, title=f"批量下载项目 - {record['filename']}", size=(600, 500))  # 增加高度以容纳按钮
            panel = wx.Panel(dlg)
            vbox = wx.BoxSizer(wx.VERTICAL)
            
         
            title = wx.StaticText(panel, label=f"文件夹 '{record['filename']}' 包含以下项目:")
            title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            vbox.Add(title, 0, wx.ALL | wx.EXPAND, 10)
            
            list_ctrl_items = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
            list_ctrl_items.InsertColumn(0, "URL", width=300)
            list_ctrl_items.InsertColumn(1, "文件名", width=200)
            list_ctrl_items.InsertColumn(2, "状态", width=100)
            vbox.Add(list_ctrl_items, 1, wx.ALL | wx.EXPAND, 10)
            #Enchantments:[{id:"minecraft:quick_charge",lvl:5s},{id:"minecraft:mending",lvl:1s}]
            download_items = record.get("download_items", [])
            for i, item in enumerate(download_items):
                index = list_ctrl_items.InsertItem(i, item.get("url", ""))
                list_ctrl_items.SetItem(index, 1, item.get("filename", ""))
                
                file_path = os.path.join(record["save_path"], record["filename"], item.get("filename", ""))
                if os.path.exists(file_path):
                    list_ctrl_items.SetItem(index, 2, "已下载")
                else:
                    list_ctrl_items.SetItem(index, 2, "未下载")
            
            button_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            export_btn = wx.Button(panel, label="导出项目列表")
            button_sizer.Add(export_btn, 0, wx.ALL | wx.CENTER, 5)
            
            close_btn = wx.Button(panel, label="关闭")
            button_sizer.Add(close_btn, 0, wx.ALL | wx.CENTER, 5)
            
            vbox.Add(button_sizer, 0, wx.ALL | wx.CENTER, 10)
            
            def on_export_click(event):
                """导出项目列表"""
               
                file_dlg = wx.FileDialog(
                    dlg,
                    "导出项目列表",
                    wildcard="文本文件 (*.txt)|*.txt|JSON文件 (*.json)|*.json",
                    style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
                )
                
                if file_dlg.ShowModal() == wx.ID_OK:
                    export_path = file_dlg.GetPath()
                    file_ext = os.path.splitext(export_path)[1].lower()
                    
                    try:
                        if file_ext == '.txt':
                        
                            with open(export_path, 'w', encoding='utf-8') as f:
                                for item in download_items:
                                    url = item.get("url", "")
                                    filename = item.get("filename", "")
                                    if filename:
                                        f.write(f"{url} (文件名: {filename})\n")
                                    else:
                                        f.write(f"{url}\n")
                            wx.MessageBox(f"成功导出 {len(download_items)} 个项目到 {export_path}", "导出成功", wx.OK | wx.ICON_INFORMATION)
                        
                        elif file_ext == '.json':
                         
                            export_data = []
                            for item in download_items:
                                url = item.get("url", "")
                                filename = item.get("filename", "")
                                
                           
                                if not filename and url:
                                    filename = os.path.basename(url) or "download_file"
                                
                                export_data.append({
                                    "url": url,
                                    "filename": filename
                                })
                            
                            with open(export_path, 'w', encoding='utf-8') as f:
                                json.dump(export_data, f, ensure_ascii=False, indent=2)
                            wx.MessageBox(f"成功导出 {len(download_items)} 个项目到 {export_path}", "导出成功", wx.OK | wx.ICON_INFORMATION)
                        
                        else:
                            wx.MessageBox("不支持的文件格式，请选择.txt或.json格式", "错误", wx.OK | wx.ICON_ERROR)
                    
                    except Exception as e:
                        wx.MessageBox(f"导出失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
                
                file_dlg.Destroy()
            
            export_btn.Bind(wx.EVT_BUTTON, on_export_click)
            close_btn.Bind(wx.EVT_BUTTON, lambda e: dlg.EndModal(wx.ID_OK))
            
            panel.SetSizer(vbox)
            dlg.ShowModal()
            dlg.Destroy()
        else:
            wx.MessageBox("这不是批量下载文件夹记录或没有包含的项目信息", "提示", wx.OK | wx.ICON_INFORMATION)
def refresh_download_list(list_ctrl, image_list):
    """刷新下载列表"""
  
    load_download_history()
    
    list_ctrl.DeleteAllItems()
    image_list.RemoveAll()
    
    icon_cache = {} 
    
    for record in download_history:
  
        file_path = os.path.join(record["save_path"], record["filename"])
        
 
        ext = os.path.splitext(record["filename"])[1].lower()
        if ext not in icon_cache:
            icon = get_file_icon(file_path)
            icon_index = image_list.Add(icon)
            icon_cache[ext] = icon_index
        else:
            icon_index = icon_cache[ext]
        
        index = list_ctrl.InsertItem(list_ctrl.GetItemCount(), icon_index)
        
    
        file_size = record.get("file_size", 0)
        if file_size == 0:
            size_str = "未知"
        elif file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        elif file_size < 1024 * 1024 * 1024:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        else:
            size_str = f"{file_size / (1024 * 1024 * 1024):.1f} GB"
        
        list_ctrl.SetItem(index, 1, record["filename"])
        list_ctrl.SetItem(index, 2, size_str)
        list_ctrl.SetItem(index, 3, record["status"])
        list_ctrl.SetItem(index, 4, record["save_path"])
        list_ctrl.SetItem(index, 5, record["timestamp"])
def on_new_download(parent, list_ctrl, image_list):
    
    import os
    import threading
    import platform
    
    # 跨平台配置目录
    sys_type = platform.system()
    if sys_type == "Windows":
        config_dir = os.path.join(os.getenv('APPDATA', ''), 'Nodanium')
        default_save_path = os.path.join(os.environ['USERPROFILE'], 'Downloads')
    else:
        config_dir = os.path.join(os.path.expanduser("~"), '.Nodanium')
        default_save_path = os.path.join(os.path.expanduser("~"), 'Downloads')
    dir_file = os.path.join(config_dir, 'dir.txt')
    if os.path.exists(dir_file):
        try:
            with open(dir_file, 'r', encoding='utf-8') as f:
                saved_path = f.read().strip()
                if saved_path and os.path.exists(saved_path):
                    default_save_path = saved_path
        except Exception as e:
            print(f"读取保存路径配置失败: {e}")

    dlg = wx.Dialog(parent, title="新建下载", size=(600, 500))  # 增加对话框大小以容纳选项卡
    panel = wx.Panel(dlg)
    

    notebook = wx.Notebook(panel)
    

    main_sizer = wx.BoxSizer(wx.VERTICAL)
    main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
    
    # ==================== 单文件下载选项卡 ====================
    single_panel = wx.Panel(notebook)
    single_sizer = wx.BoxSizer(wx.VERTICAL)
    

    url_sizer = wx.BoxSizer(wx.HORIZONTAL)
    url_label = wx.StaticText(single_panel, label="下载链接:")
    url_text = wx.TextCtrl(single_panel, style=wx.TE_PROCESS_ENTER)
    url_sizer.Add(url_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    url_sizer.Add(url_text, 1, wx.ALL, 5)
    single_sizer.Add(url_sizer, 0, wx.EXPAND | wx.ALL, 5)
    

    filename_sizer = wx.BoxSizer(wx.HORIZONTAL)
    filename_label = wx.StaticText(single_panel, label="文件名:")
    filename_text = wx.TextCtrl(single_panel)
    filename_sizer.Add(filename_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    filename_sizer.Add(filename_text, 1, wx.ALL, 5)
    single_sizer.Add(filename_sizer, 0, wx.EXPAND | wx.ALL, 5)
    

    path_sizer = wx.BoxSizer(wx.HORIZONTAL)
    path_label = wx.StaticText(single_panel, label="保存路径:")
    path_text = wx.TextCtrl(single_panel, value=default_save_path)
    browse_btn = wx.Button(single_panel, label="浏览...")
    path_sizer.Add(path_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    path_sizer.Add(path_text, 1, wx.ALL, 5)
    path_sizer.Add(browse_btn, 0, wx.ALL, 5)
    single_sizer.Add(path_sizer, 0, wx.EXPAND | wx.ALL, 5)
    

    thread_sizer = wx.BoxSizer(wx.HORIZONTAL)
    thread_label = wx.StaticText(single_panel, label="线程数 (1-1024):")
    thread_count_spin = wx.SpinCtrl(single_panel, min=1, max=1024, initial=4, size=(100, -1))
    thread_sizer.Add(thread_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    thread_sizer.Add(thread_count_spin, 0, wx.ALL, 5)
    single_sizer.Add(thread_sizer, 0, wx.EXPAND | wx.ALL, 5)
    
    single_panel.SetSizer(single_sizer)
    notebook.AddPage(single_panel, "单文件下载")
    
    # ==================== 批量下载选项卡 ====================
    batch_panel = wx.Panel(notebook)
    batch_sizer = wx.BoxSizer(wx.VERTICAL)
    

    import_sizer = wx.BoxSizer(wx.HORIZONTAL)
    import_btn = wx.Button(batch_panel, label="导入网址文件")
    import_sizer.Add(import_btn, 0, wx.ALL, 5)
    batch_sizer.Add(import_sizer, 0, wx.EXPAND | wx.ALL, 5)
    

    main_site_sizer = wx.BoxSizer(wx.HORIZONTAL)
    main_site_label = wx.StaticText(batch_panel, label="主网站:")
    main_site_text = wx.TextCtrl(batch_panel)
    main_site_sizer.Add(main_site_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    main_site_sizer.Add(main_site_text, 1, wx.ALL, 5)
    batch_sizer.Add(main_site_sizer, 0, wx.EXPAND | wx.ALL, 5)
    

    folder_sizer = wx.BoxSizer(wx.HORIZONTAL)
    folder_label = wx.StaticText(batch_panel, label="文件夹名称:")
    folder_text = wx.TextCtrl(batch_panel, value=f"批量下载_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
    folder_sizer.Add(folder_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    folder_sizer.Add(folder_text, 1, wx.ALL, 5)
    batch_sizer.Add(folder_sizer, 0, wx.EXPAND | wx.ALL, 5)
    

    batch_thread_sizer = wx.BoxSizer(wx.HORIZONTAL)
    batch_thread_label = wx.StaticText(batch_panel, label="线程数:")
    batch_thread_spin = wx.SpinCtrl(batch_panel, min=1, max=10, initial=4)
    batch_thread_sizer.Add(batch_thread_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    batch_thread_sizer.Add(batch_thread_spin, 0, wx.ALL, 5)
    batch_sizer.Add(batch_thread_sizer, 0, wx.EXPAND | wx.ALL, 5)
    

    undownloaded_list = wx.ListBox(batch_panel, style=wx.LB_SINGLE)
    batch_sizer.Add(undownloaded_list, 1, wx.ALL | wx.EXPAND, 5)
    
    batch_panel.SetSizer(batch_sizer)
    notebook.AddPage(batch_panel, "批量下载")

    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    ok_btn = wx.Button(panel, wx.ID_OK, label="确定")
    cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="取消")
    btn_sizer.AddStretchSpacer(1)
    btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
    btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
    main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
    
    panel.SetSizer(main_sizer)
    

    batch_urls = []
    
    def on_url_enter(event):
        url = url_text.GetValue().strip()
        if url:
    
            filename = os.path.basename(url) or "download_file"
            filename_text.SetValue(filename)
    
    def on_browse_click(event):
        dir_dlg = wx.DirDialog(dlg, "选择保存目录", defaultPath=path_text.GetValue(), style=wx.DD_DEFAULT_STYLE)
        if dir_dlg.ShowModal() == wx.ID_OK:
            path_text.SetValue(dir_dlg.GetPath())
        dir_dlg.Destroy()
    
    def on_import_click(event):
        with wx.FileDialog(dlg, "选择网址文件", wildcard="文本和JSON文件 (*.txt;*.json)|*.txt;*.json|所有文件 (*.*)|*.*",
                        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            
            path = fileDialog.GetPath()
            try:

                if path.lower().endswith('.json'):
                    # JSON格式导入
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            urls = []
                            download_items = [] 
                            for item in data:
                                if isinstance(item, dict) and 'url' in item:
                                    url = item['url'].strip()
                                    if url:
                                        filename = item.get('filename', '')
                              
                                        urls.append(url)
                                     
                                        download_items.append({"url": url, "filename": filename})
                            wx.MessageBox(f"成功导入 {len(urls)} 个网址", "提示", wx.OK | wx.ICON_INFORMATION)
                            undownloaded_list.Set(urls)
                            batch_urls.extend(urls)
                  
                            dlg.download_items = download_items
                        else:
                            wx.MessageBox("JSON格式错误：应为数组格式", "错误", wx.OK | wx.ICON_ERROR)
                else:
              
                    with open(path, 'r', encoding='utf-8') as f:
                        urls = [line.strip() for line in f if line.strip()]
                        wx.MessageBox(f"成功导入 {len(urls)} 个网址", "提示", wx.OK | wx.ICON_INFORMATION)
                        undownloaded_list.Set(urls)
                        batch_urls.extend(urls)
            except json.JSONDecodeError as e:
                wx.MessageBox(f"JSON解析失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            except Exception as e:
                wx.MessageBox(f"导入文件失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
    url_text.Bind(wx.EVT_TEXT_ENTER, on_url_enter)
    browse_btn.Bind(wx.EVT_BUTTON, on_browse_click)
    import_btn.Bind(wx.EVT_BUTTON, on_import_click)
    

    def on_url_change(event):
        url = url_text.GetValue().strip()
        if url and not filename_text.GetValue():
     
            filename = os.path.basename(url) or "download_file"
            filename_text.SetValue(filename)
    
    url_text.Bind(wx.EVT_TEXT, on_url_change)
    

    if dlg.ShowModal() == wx.ID_OK:
        current_page = notebook.GetSelection()
        
        if current_page == 0:  # 单文件下载选项卡
            url = url_text.GetValue().strip()
            filename = filename_text.GetValue().strip()
            save_path = path_text.GetValue().strip()
            thread_count = thread_count_spin.GetValue()
            
            if url and filename and save_path:
       
                file_path = os.path.join(save_path, filename)
                if os.path.exists(file_path):
                    msg_dlg = wx.MessageDialog(
                        parent, 
                        f"文件 '{filename}' 已存在，是否继续下载并覆盖？", 
                        "文件已存在", 
                        wx.YES_NO | wx.ICON_QUESTION
                    )
                    if msg_dlg.ShowModal() != wx.ID_YES:
                        msg_dlg.Destroy()
                        dlg.Destroy()
                        return
                    msg_dlg.Destroy()
                
     
                record = add_download_record(url, filename, save_path, "下载中", 0)
                refresh_download_list(list_ctrl, image_list)
                
                # 下载完成回调函数
                def on_download_completed(success, file_size):

                    for idx, item in enumerate(download_history):
                        if (item["url"] == url and 
                            item["filename"] == filename and 
                            item["save_path"] == save_path and 
                            item["status"] == "下载中"):
                            if success:
                                item["status"] = "已完成"
                                item["file_size"] = file_size
                            else:
                                if file_size > 0:
                        
                                    item["status"] = "部分完成"
                                    item["file_size"] = file_size
                                else:
                                    item["status"] = "失败"
                            break
    
                    save_download_history()
                    wx.CallAfter(refresh_download_list, list_ctrl, image_list)
                
                def start_download():
                    try:
                        wx.CallAfter(download_window, url, filename, save_path, thread_count=thread_count, disable_ssl=True, 
                                    completion_callback=on_download_completed)
                    except Exception as e:
    
                        for idx, item in enumerate(download_history):
                            if (item["url"] == url and 
                                item["filename"] == filename and 
                                item["save_path"] == save_path and 
                                item["status"] == "下载中"):
                                item["status"] = f"失败: {str(e)}"
                                break
                        save_download_history()
                        wx.CallAfter(refresh_download_list, list_ctrl, image_list)
                
                thread = threading.Thread(target=start_download)
                thread.daemon = True
                thread.start()
        
        elif current_page == 1:  # 批量下载选项卡
            if not batch_urls:
                wx.MessageBox("请先导入网址文件", "错误", wx.OK | wx.ICON_ERROR)
                dlg.Destroy()
                return
            
            main_site = main_site_text.GetValue().strip()
            thread_count = batch_thread_spin.GetValue()
            folder_name = folder_text.GetValue().strip()
            
            if not folder_name:
                wx.MessageBox("请输入文件夹名称", "错误", wx.OK | wx.ICON_ERROR)
                dlg.Destroy()
                return
            

            parent_window = parent
            if hasattr(dlg, 'download_items') and dlg.download_items:
                parent_window.download_items = dlg.download_items
            dlg.Destroy()        
           
            try:
                import DatchDownload
                DatchDownload.create_download_window(
                    parent_window, 
                    batch_urls, 
                    thread_count, 
                    main_site, 
                    default_save_path,
                    folder_name,
                    list_ctrl,  
                    image_list 
                )
            except Exception as e:
                wx.MessageBox(f"启动批量下载失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            return  
    dlg.Destroy()
def on_delete_download(list_ctrl):
    selected_count = list_ctrl.GetSelectedItemCount()
    if selected_count == 0:
        return
    
   
    dlg = wx.Dialog(None, title="确认删除", size=(400, 200))
    panel = wx.Panel(dlg)
    vbox = wx.BoxSizer(wx.VERTICAL)
   
    if selected_count == 1:
        selected = list_ctrl.GetFirstSelected()
        filename = list_ctrl.GetItemText(selected, 1)
        message = f"确定要删除下载记录 '{filename}' 吗?"
    else:
        message = f"确定要删除选中的 {selected_count} 条下载记录吗?"
    
  
    msg_label = wx.StaticText(panel, label=message)
    vbox.Add(msg_label, 0, wx.ALL | wx.EXPAND, 10)
   
    delete_files_checkbox = wx.CheckBox(panel, label="一并删除文件")
    vbox.Add(delete_files_checkbox, 0, wx.ALL | wx.EXPAND, 10)
   
    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    btn_sizer.AddStretchSpacer(1)
    yes_btn = wx.Button(panel, wx.ID_YES, label="确定")
    no_btn = wx.Button(panel, wx.ID_NO, label="取消")
    btn_sizer.Add(yes_btn, 0, wx.ALL, 5)
    btn_sizer.Add(no_btn, 0, wx.ALL, 5)
    vbox.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
    
    panel.SetSizer(vbox)
    
    def on_yes(event):
        dlg.EndModal(wx.ID_YES)
    
    def on_no(event):
        dlg.EndModal(wx.ID_NO)
    
    yes_btn.Bind(wx.EVT_BUTTON, on_yes)
    no_btn.Bind(wx.EVT_BUTTON, on_no)
    
    if dlg.ShowModal() == wx.ID_YES:
        global download_history
        delete_files = delete_files_checkbox.GetValue()
        

        selected_indices = []
        item = list_ctrl.GetFirstSelected()
        while item != -1:
            selected_indices.append(item)
            item = list_ctrl.GetNextSelected(item)
        
   
        selected_indices.sort(reverse=True)
        
        for index in selected_indices:
            if 0 <= index < len(download_history):
                record = download_history[index]
                
             
                if delete_files:
                    file_path = os.path.join(record["save_path"], record["filename"])
                    try:
                        if os.path.exists(file_path):
                     
                            if record.get("url") == "批量下载文件夹":
                             
                                import shutil
                                shutil.rmtree(file_path)
                            
                                if os.path.exists(file_path) and os.path.isdir(file_path):
                                    for root, dirs, files in os.walk(file_path, topdown=False):
                                        for name in files:
                                            os.remove(os.path.join(root, name))
                                        for name in dirs:
                                            os.rmdir(os.path.join(root, name))
                                    os.rmdir(file_path)
                            else:
                           
                                if os.path.isfile(file_path):
                                    os.remove(file_path)
                                elif os.path.isdir(file_path):
                                    import shutil
                                    shutil.rmtree(file_path)
                    except Exception as e:
                        wx.MessageBox(f"删除文件失败: {str(e)}", "警告", wx.OK | wx.ICON_WARNING)
                
                download_history.pop(index)
        
        save_download_history()
   
        wx.CallAfter(refresh_download_list, list_ctrl, list_ctrl.GetImageList(wx.IMAGE_LIST_SMALL))
    dlg.Destroy()

def on_clear_history(list_ctrl):
    """清空历史记录"""
    dlg = wx.Dialog(list_ctrl.GetParent(), title="确认清空历史记录", size=(400, 180))
    panel = wx.Panel(dlg)
    

    sizer = wx.BoxSizer(wx.VERTICAL)
    

    text = wx.StaticText(panel, label="确定要清空所有下载历史记录吗？")
    sizer.Add(text, 0, wx.ALL | wx.CENTER, 10)
    
   
    delete_files_checkbox = wx.CheckBox(panel, label="一并删除文件")
    sizer.Add(delete_files_checkbox, 0, wx.ALL | wx.LEFT, 20)
    

    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    yes_btn = wx.Button(panel, label="确定")
    no_btn = wx.Button(panel, label="取消")
    btn_sizer.Add(yes_btn, 0, wx.ALL, 5)
    btn_sizer.Add(no_btn, 0, wx.ALL, 5)
    
    sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
    
    panel.SetSizer(sizer)
    
    def on_yes(event):
        dlg.EndModal(wx.ID_YES)
    
    def on_no(event):
        dlg.EndModal(wx.ID_NO)
    
    yes_btn.Bind(wx.EVT_BUTTON, on_yes)
    no_btn.Bind(wx.EVT_BUTTON, on_no)
    
    if dlg.ShowModal() == wx.ID_YES:
        global download_history
        delete_files = delete_files_checkbox.GetValue()
        

        if delete_files:
            for record in download_history:
                file_path = os.path.join(record["save_path"], record["filename"])
                try:
                    if os.path.exists(file_path):
                 
                        if record.get("url") == "批量下载文件夹":
                          
                            import shutil
                            try:
                              
                                shutil.rmtree(file_path)
                            except Exception as e:
                     
                                if os.path.exists(file_path) and os.path.isdir(file_path):
                                    try:
                                        for root, dirs, files in os.walk(file_path, topdown=False):
                                            for name in files:
                                                try:
                                                    os.remove(os.path.join(root, name))
                                                except:
                                                    pass
                                            for name in dirs:
                                                try:
                                                    os.rmdir(os.path.join(root, name))
                                                except:
                                                    pass
                                        if os.path.exists(file_path):
                                            os.rmdir(file_path)
                                    except:
                                        pass
                        else:
                        
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                            elif os.path.isdir(file_path):
                                import shutil
                                shutil.rmtree(file_path)
                except Exception as e:
                    wx.MessageBox(f"删除文件失败: {str(e)}", "警告", wx.OK | wx.ICON_WARNING)
        
        download_history.clear()
        save_download_history()

        wx.CallAfter(refresh_download_list, list_ctrl, list_ctrl.GetImageList(wx.IMAGE_LIST_SMALL))
    
    dlg.Destroy()

def on_item_activated(list_ctrl, event):
    """双击列表项事件"""
    selected = event.GetIndex()
    if 0 <= selected < len(download_history):
        record = download_history[selected]
        file_path = os.path.join(record["save_path"], record["filename"])
        

        if record.get("url") == "批量下载文件夹":

            folder_path = os.path.join(record["save_path"], record["filename"])
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                try:
                    os.startfile(folder_path)
                except Exception as e:
                    wx.MessageBox(f"无法打开文件夹: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            else:
                wx.MessageBox("文件夹不存在", "错误", wx.OK | wx.ICON_ERROR)
        elif os.path.exists(file_path) and record["status"] == "已完成":
            try:
                os.startfile(file_path)
            except Exception as e:
                wx.MessageBox(f"无法打开文件: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("文件不存在或下载未完成", "提示", wx.OK | wx.ICON_INFORMATION)
def on_menu_export(event, list_ctrl):
    """导出选中的下载记录"""
    selected_count = list_ctrl.GetSelectedItemCount()
    if selected_count == 0:
        return
    

    dlg = wx.FileDialog(
        None,
        "导出选中项",
        wildcard="JSON文件 (*.json)|*.json",
        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
    )
    
    if dlg.ShowModal() == wx.ID_OK:
        export_path = dlg.GetPath()
        
        try:

            selected_data = []
            item = list_ctrl.GetFirstSelected()
            while item != -1:
                if 0 <= item < len(download_history):
                    record = download_history[item]
 
                    simplified_record = {
                        "url": record["url"],
                        "filename": record["filename"]
                    }
                    selected_data.append(simplified_record)
                item = list_ctrl.GetNextSelected(item)
            
      
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(selected_data, f, ensure_ascii=False, indent=2)
            
            wx.MessageBox(f"成功导出 {len(selected_data)} 条记录到 {export_path}", "导出成功", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"导出失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
    
    dlg.Destroy()
def on_menu_open(event, list_ctrl):
    """打开文件"""
    selected = list_ctrl.GetFirstSelected()
    if selected != -1 and 0 <= selected < len(download_history):
        record = download_history[selected]
        file_path = os.path.join(record["save_path"], record["filename"])
        
        if os.path.exists(file_path):
            try:
                os.startfile(file_path)
                
            except Exception as e:
                wx.MessageBox(f"无法打开文件: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("文件不存在", "错误", wx.OK | wx.ICON_ERROR)

def on_menu_open_folder(event, list_ctrl):
    """在文件夹中显示"""
    selected = list_ctrl.GetFirstSelected()
    if selected != -1 and 0 <= selected < len(download_history):
        record = download_history[selected]
        file_path = os.path.join(record["save_path"], record["filename"])
        
        if os.path.exists(file_path):
            try:
                os.startfile(record["save_path"])
                
            except Exception as e:
                wx.MessageBox(f"无法打开文件夹: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("文件不存在", "错误", wx.OK | wx.ICON_ERROR)

def on_menu_redownload(event, list_ctrl):
    """重新下载"""
    selected = list_ctrl.GetFirstSelected()
    if selected != -1 and 0 <= selected < len(download_history):
        record = download_history[selected]
        url = record["url"]
        filename = record["filename"]
        save_path = record["save_path"]
        

        if record.get("url") == "批量下载文件夹":

            if record.get("download_items"):

                try:
                    import DatchDownload
 
                    download_items = record.get("download_items", [])
                    urls = [item["url"] for item in download_items]
                    

                    DatchDownload.create_download_window(
                        None,  # parent_window
                        urls, 
                        4,  # thread_count
                        "",  # main_site
                        save_path,
                        filename,
                        list_ctrl,
                        list_ctrl.GetImageList(wx.IMAGE_LIST_SMALL)
                    )
                except Exception as e:
                    wx.MessageBox(f"重新下载批量文件夹失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            else:
                wx.MessageBox("批量下载文件夹记录缺少下载项目信息", "错误", wx.OK | wx.ICON_ERROR)
        else:

            wx.CallAfter(download_window, url, filename, save_path, True, thread_count=16, disable_ssl=True)

def on_menu_copy_url(event, list_ctrl):
    """复制URL"""
    selected = list_ctrl.GetFirstSelected()
    if selected != -1 and 0 <= selected < len(download_history):
        record = download_history[selected]
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(record["url"]))
            wx.TheClipboard.Close()
            

def on_menu_copy_filename(event, list_ctrl):
    """复制文件名"""
    selected = list_ctrl.GetFirstSelected()
    if selected != -1 and 0 <= selected < len(download_history):
        record = download_history[selected]
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(record["filename"]))
            wx.TheClipboard.Close()
            

def on_menu_copy_path(event, list_ctrl):
    """复制路径"""
    selected = list_ctrl.GetFirstSelected()
    if selected != -1 and 0 <= selected < len(download_history):
        record = download_history[selected]
        file_path = os.path.join(record["save_path"], record["filename"])
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(file_path))
            wx.TheClipboard.Close()
            

def on_menu_delete(event, list_ctrl):
  
    on_delete_download(list_ctrl)


def show_download_manager():

    app = wx.App(False)
 
    frame = wx.Frame(None, title="下载管理器", size=(800, 600))

    download_panel = create_download_panel(frame)

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(download_panel, 1, wx.EXPAND)
    frame.SetSizer(sizer)
    
    frame.Center()
    frame.Show()
    
    app.MainLoop()

def DownloadUI(parent=None):
  

    app = wx.App(False)
    frame = wx.Frame(None, title="下载管理器", size=(800, 600))
    download_panel = create_download_panel(wx.Panel(frame))
    

    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(download_panel, 1, wx.EXPAND)
    frame.SetSizer(sizer)
    
    frame.Center()
    frame.Show()
    app.MainLoop()  

if __name__ == "__main__":
 
    DownloadUI()
