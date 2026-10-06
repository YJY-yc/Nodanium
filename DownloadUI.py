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
import uuid
import subprocess
import threading
from urllib.parse import urlparse
from FileIcon import get_file_icon, get_fallback_icon, THUMBNAIL_EXTENSIONS


class RubberBandListCtrl(wx.ListCtrl):
    """支持鼠标框选（橡皮筋多选）的 ListCtrl。

    GTK 下的 wx.ListCtrl 原生不支持拖拽框选，这里用鼠标事件自行实现：在项目上/空白
    处按住左键拖拽时绘制选择矩形，并把矩形内的行加入选择。Windows/MSW 行为一致。

    注意：GTK 的 mouse motion 事件中按钮状态不可靠（LeftIsDown 常为 False），因此
    自行用 DOWN/UP 事件维护按键状态，不依赖 event.LeftIsDown()。框选只在左键按下
    并产生位移后启动，右键/中键绝不触发。
    """

    DRAG_THRESHOLD = 4

    def __init__(self, *args, **kwargs):
        style = kwargs.get("style", 0)
        style = style & ~wx.LC_SINGLE_SEL
        kwargs["style"] = style
        super().__init__(*args, **kwargs)
        self._left_pressed = False
        self._right_pressed = False
        self._middle_pressed = False
        self._rb_pending = False
        self._rb_active = False
        self._rb_start = wx.Point(0, 0)
        self._rb_end = wx.Point(0, 0)
        self._rb_base_sel = []
        self._rb_ctrl = False
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)
        self.Bind(wx.EVT_RIGHT_DOWN, self._on_right_down)
        self.Bind(wx.EVT_RIGHT_UP, self._on_right_up)
        self.Bind(wx.EVT_MIDDLE_DOWN, self._on_middle_down)
        self.Bind(wx.EVT_MIDDLE_UP, self._on_middle_up)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self._on_capture_lost)
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def _item_rect(self, idx):
        try:
            rect = self.GetItemRect(idx)
        except Exception:
            return None
        if rect is None:
            return None
        if isinstance(rect, (tuple, list)):
            if len(rect) < 4:
                return None
            return wx.Rect(int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))
        return rect if rect.GetWidth() > 0 and rect.GetHeight() > 0 else None

    def _reset_rubber_band(self):
        self._rb_pending = False
        self._rb_active = False
        if self.HasCapture():
            try:
                self.ReleaseMouse()
            except Exception:
                pass

    def _on_capture_lost(self, event):
        self._rb_pending = False
        self._rb_active = False
        self.Refresh(False)

    def _on_left_down(self, event):
        self._left_pressed = True
        if self._right_pressed or self._middle_pressed:
            self._reset_rubber_band()
            event.Skip()
            return
        self.SetFocus()
        self._rb_pending = True
        self._rb_active = False
        self._rb_ctrl = event.ControlDown()
        self._rb_start = event.GetPosition()
        self._rb_end = self._rb_start
        event.Skip()

    def _on_left_up(self, event):
        self._left_pressed = False
        was_active = self._rb_active
        self._reset_rubber_band()
        if was_active:
            self.Refresh(False)
        event.Skip()

    def _on_right_down(self, event):
        self._right_pressed = True
        self._reset_rubber_band()
        self.Refresh(False)
        event.Skip()

    def _on_right_up(self, event):
        self._right_pressed = False
        event.Skip()

    def _on_middle_down(self, event):
        self._middle_pressed = True
        self._reset_rubber_band()
        self.Refresh(False)
        event.Skip()

    def _on_middle_up(self, event):
        self._middle_pressed = False
        event.Skip()

    def _on_motion(self, event):
        if not self._left_pressed or self._right_pressed or self._middle_pressed:
            event.Skip()
            return
        if not self._rb_pending and not self._rb_active:
            event.Skip()
            return
        pos = event.GetPosition()
        if not self._rb_active:
            if abs(pos.x - self._rb_start.x) < self.DRAG_THRESHOLD and \
               abs(pos.y - self._rb_start.y) < self.DRAG_THRESHOLD:
                return
            self._rb_active = True
            if not self._rb_ctrl:
                self._clear_selection()
            self._rb_base_sel = self._get_selected_indices()
            if not self.HasCapture():
                self.CaptureMouse()
        self._rb_end = pos
        self._apply_rubber_band()
        self.Refresh(False)

    def _on_paint(self, event):
        event.Skip()
        if not self._rb_active:
            return
        dc = wx.ClientDC(self)
        rect = wx.Rect(self._rb_start, self._rb_end)
        dc.SetPen(wx.Pen(wx.Colour(0, 120, 215), 1, wx.PENSTYLE_SOLID))
        dc.SetBrush(wx.Brush(wx.Colour(0, 120, 215, 40), wx.BRUSHSTYLE_SOLID))
        dc.SetLogicalFunction(wx.INVERT)
        dc.DrawRectangle(rect)
        dc.SetLogicalFunction(wx.COPY)

    def _get_selected_indices(self):
        result = []
        idx = self.GetFirstSelected()
        while idx != -1:
            result.append(idx)
            idx = self.GetNextSelected(idx)
        return result

    def _clear_selection(self):
        idx = self.GetFirstSelected()
        while idx != -1:
            self.SetItemState(idx, 0, wx.LIST_STATE_SELECTED)
            idx = self.GetNextSelected(idx)

    def _select_index(self, idx, selected=True):
        mask = wx.LIST_STATE_SELECTED
        self.SetItemState(idx, mask if selected else 0, mask)

    def _apply_rubber_band(self):
        rect = wx.Rect(self._rb_start, self._rb_end)
        band = rect
        base = set(self._rb_base_sel)
        for idx in range(self.GetItemCount()):
            ir = self._item_rect(idx)
            if ir is None:
                continue
            in_band = band.Intersects(ir)
            if in_band:
                self._select_index(idx, True)
                base.add(idx)
            elif idx in base:
                self._select_index(idx, True)
            else:
                self._select_index(idx, False)


def get_filename_from_url(url):
    parsed = urlparse(url)
    path = parsed.path or url
    return os.path.basename(path) or "download_file"

def open_file_or_folder(file_path):
    """跨平台打开文件或文件夹"""
    sys_type = platform.system()
    
    try:
        if sys_type == "Windows":
            os.startfile(file_path)
  
        else:

            subprocess.run(['xdg-open', file_path], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"打开失败: {e}")
        return False
    except Exception as e:
        logging.error(f"打开失败: {e}")
        return False

def get_data_folder():
    """获取跨平台数据目录"""
    sys_type = platform.system()
    if sys_type == "Windows":
        return os.path.join(os.getenv('APPDATA', ''), "Nodanium")
    elif sys_type == "Linux":
        return os.path.join(os.path.expanduser("~"), ".Nodanium")
    else:
        return os.path.join(os.path.expanduser("~"), ".Nodanium")
DATA_FOLDER = get_data_folder()
HISTORY_FILE = os.path.join(DATA_FOLDER, 'History.json')
PROCESS_DIR = os.path.join(DATA_FOLDER, 'DownloadProcess')


def get_speed_unit():
    """读取首选项配置的下载速度单位(与下载引擎支持的单位一致)。"""
    try:
        with open(os.path.join(DATA_FOLDER, 'config.json'), 'r', encoding='utf-8') as f:
            unit = json.load(f).get('dl_speed_unit', 'MB/s')
    except Exception:
        unit = 'MB/s'
    return unit if unit in ('MB/s', 'MiB/s', 'Mbps') else 'MB/s'

def ensure_process_dir():
    """确保下载进度缓存目录存在"""
    try:
        os.makedirs(PROCESS_DIR, exist_ok=True)
    except Exception:
        pass
    return PROCESS_DIR

def is_fat_filesystem(path):

    if not path:
        return False

    probe = path
    if os.path.isfile(probe):
        probe = os.path.dirname(probe)
    sys_type = platform.system()
    try:
        if sys_type == "Windows":
            try:
                import ctypes
                drive = os.path.splitdrive(os.path.abspath(probe))[0]
                if not drive:
                    return False
                fs = ctypes.create_unicode_buffer(260)
                buf = ctypes.create_unicode_buffer(256)
                max_component = ctypes.c_uint32(0)
                flags = ctypes.c_uint32(0)
                ok = ctypes.windll.kernel32.GetVolumeInformationW(
                    drive + '\\',
                    buf, 256, None, ctypes.byref(max_component),
                    ctypes.byref(flags), fs, 260)
                if ok:
                    fsname = (fs.value or "").lower()
                    return any(k in fsname for k in ("fat", "exfat"))
                return False
            except Exception:
                return False
        elif sys_type == "Linux":
    
            try:
                import subprocess
                base = probe
                if not os.path.isdir(base):
                    base = os.path.dirname(os.path.abspath(probe))
                out = subprocess.run(
                    ['df', '-T', base], capture_output=True, text=True, timeout=5
                ).stdout
                import re
                lines = out.strip().split('\n')
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) >= 2:
                        fstype = parts[1].lower()
                        if any(k in fstype for k in ("vfat", "fat", "exfat", "fuseblk")):
                            return True
                return False
            except Exception:
                return False
        else:
            return False
    except Exception:
        return False

def resolve_resume_file(record):
    """解析下载记录对应的断点进度文件路径。
    优先使用缓存目录 DownloadProcess 下的进度文件，
    兼容旧版本存放在保存路径下的进度文件。
    """
    filename = record.get("filename", "")
    save_path = record.get("save_path", "")
    if not filename:
        return ""
    json_name = f"{filename}_download_progress.json"
    cache_file = os.path.join(PROCESS_DIR, json_name)
    if os.path.exists(cache_file):
        return cache_file

    if save_path:
        legacy = os.path.join(save_path, json_name)
        if os.path.exists(legacy):
            return legacy
    return ""



def _apply_record_visual(list_ctrl, index, record):
    """对文件名列应用可视化样式：
    - 已完成且文件存在 -> 文件名变绿
    - 已完成但文件被删除 -> 文件名删除线（灰色）
    """
    status = record.get("status", "")
    file_path = os.path.join(record.get("save_path", ""), record.get("filename", ""))
    try:
        if status == "已完成":
            if os.path.exists(file_path):
                list_ctrl.SetItemTextColour(index, wx.Colour(0, 140, 60))
            else:
                
                font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
                font.SetStrikethrough(True)
                list_ctrl.SetItemFont(index, font)
                list_ctrl.SetItemTextColour(index, wx.Colour(140, 140, 140))
    except Exception:
        pass



INCOMPLETE_STATUSES = ("下载中", "部分完成", "失败", "失败：分片重试耗尽", "失败：下载中断")


def _get_record_progress(record):

    if record.get("proto") == "bt":
 
        uid = str(record.get("uuid", ""))
        resume_file = os.path.join(PROCESS_DIR, "bt_" + uid[:8] + ".json")
    else:
        resume_file = resolve_resume_file(record)
    if not resume_file or not os.path.exists(resume_file):
        return None
    try:
        with open(resume_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        total = int(data.get("file_total_size", 0) or 0)
        done = int(data.get("total_downloaded", 0) or 0)
        if total <= 0:
            return None
        return min(100, int(done / total * 100))
    except Exception:
        return None


from DownloadCore import download_window
logging.info('加载 DownloadUI 模块')
download_history = []
_download_list_ctrl = None
_image_list_ctrl = None

_history_lock = threading.RLock()


def _history_guard(func):

    def wrapper(*args, **kwargs):
        with _history_lock:
            return func(*args, **kwargs)
    return wrapper

def generate_uuid():
  
    return str(uuid.uuid4())

def save_download_history():

    with _history_lock:
        try:
            history_dir = os.path.dirname(HISTORY_FILE)
            if not os.path.exists(history_dir):
                os.makedirs(history_dir, exist_ok=True)
            tmp = HISTORY_FILE + ".tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(download_history, f, ensure_ascii=False, indent=2)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp, HISTORY_FILE)
            print(f"成功保存 {len(download_history)} 条下载记录")
            logging.info(f"成功保存 {len(download_history)} 条下载记录")
        except Exception as e:
            print(f"保存下载历史失败: {e}")
            logging.error(f"保存下载历史失败: {e}")

@_history_guard
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
                    
          
                    for record in download_history:
                        if "uuid" not in record:
                            record["uuid"] = generate_uuid()
                    
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

@_history_guard
def update_download_record_by_uuid(uuid, **kwargs):
  
    global download_history
    for record in download_history:
        if record.get("uuid") == uuid:
            for key, value in kwargs.items():
                record[key] = value
            save_download_history()
            logging.info(f"成功修改UUID为 {uuid} 的下载记录")
            return True
   
    load_download_history()
    for record in download_history:
        if record.get("uuid") == uuid:
            for key, value in kwargs.items():
                record[key] = value
            save_download_history()
            logging.info(f"重新加载后成功修改UUID为 {uuid} 的下载记录")
            return True
    logging.warning(f"未找到UUID为 {uuid} 的下载记录")
    return False

def get_download_record_by_uuid(uuid):
   
    for record in download_history:
        if record.get("uuid") == uuid:
            return record
    return None


if not download_history or len(download_history) == 0:
    load_download_history()

def add_download_record(url, filename, save_path, status="已完成", file_size=0, download_items=None, batch_id=None, completed=None, total=None, file_count=None, success_count=None, failed_count=None):
    
    record = {
        "uuid": generate_uuid(),
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

def refresh_download_list(list_ctrl, image_list):

    
    
    list_ctrl.DeleteAllItems()
    image_list.RemoveAll()
    
    icon_cache = {}
    
    for record in download_history:
       
        file_path = os.path.join(record["save_path"], record["filename"])
        
        ext = os.path.splitext(record["filename"])[1].lower()
   
        if os.path.isfile(file_path) and ext in THUMBNAIL_EXTENSIONS:
            cache_key = file_path
        else:
            cache_key = ext
        if cache_key not in icon_cache:
            icon = get_file_icon(file_path)
            icon_index = image_list.Add(icon)
            icon_cache[cache_key] = icon_index
        else:
            icon_index = icon_cache[cache_key]
        
  
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
        _apply_record_visual(list_ctrl, index, record)
        
     
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
        else:
        
            if status in INCOMPLETE_STATUSES and record.get("filename"):
                pct = _get_record_progress(record)
                if pct is not None:
                    status = f"{pct}%"
                else:
                    status = f"{status}（未完成）"
        
        list_ctrl.SetItem(index, 3, status)
        list_ctrl.SetItem(index, 4, record["save_path"])
        list_ctrl.SetItem(index, 5, record["timestamp"])

def create_download_panel(parent):
    global HISTORY_FILE
    global _download_list_ctrl, _image_list_ctrl
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
    

    download_list = RubberBandListCtrl(panel, style=wx.LC_REPORT | wx.LC_HRULES | wx.LC_VRULES)
  
    image_list = wx.ImageList(32, 32)
    download_list.AssignImageList(image_list, wx.IMAGE_LIST_SMALL)
    _download_list_ctrl = download_list
    _image_list_ctrl = image_list
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
     
        if wx.GetKeyState(wx.WXK_ALT):
            open_path = ensure_process_dir()
        else:
            open_path = default_save_path
        if sys_type == "Windows":
            os.startfile(open_path)
        else:
      
            try:
                subprocess.run(['xdg-open', open_path])
            except Exception as ex:
                wx.MessageBox(f"无法打开文件夹: {str(ex)}", "错误", wx.OK | wx.ICON_ERROR)
    
    open_folder_btn.Bind(wx.EVT_BUTTON, open_folder)
    download_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: on_item_activated(download_list, e))
    download_list.Bind(wx.EVT_KEY_DOWN, lambda e: on_delete_key(e, download_list))
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
    resume_item = menu.Append(wx.ID_ANY, "恢复下载")
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
    list_ctrl.Bind(wx.EVT_MENU, lambda e: on_menu_resume(e, list_ctrl), resume_item)
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
        already = (list_ctrl.GetItemState(item, wx.LIST_STATE_SELECTED) & wx.LIST_STATE_SELECTED) != 0
        if not already:
            list_ctrl.Select(item)
     
        if 0 <= item < len(download_history):
            record = download_history[item]
          
            is_bt = record.get("proto") == "bt"
            if record.get("url") == "批量下载文件夹":
                menu.FindItemByPosition(2).Enable(True)  
            else:
                menu.FindItemByPosition(2).Enable(False)
            if is_bt:
          
                st = str(record.get("status", ""))
                unfinished = ("下载中" in st) or ("取消" in st) or st.startswith("失败") \
                    or ("未完成" in st)
                try:
                    menu.FindItemByPosition(3).Enable(unfinished)  
                    menu.FindItemByPosition(4).Enable(True)        
                except Exception:
                    pass
                list_ctrl.PopupMenu(menu, pos)
                return
      
            is_resumable = (
                record.get("status", "") in ("下载中", "部分完成", "失败", "失败：分片重试耗尽", "失败：下载中断")
                and bool(resolve_resume_file(record))
            )
            menu.FindItemByPosition(3).Enable(is_resumable)
        
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
                                    filename = get_filename_from_url(url)
                                
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

    if list_ctrl is None or image_list is None:
        return
    try:
        if list_ctrl.IsBeingDeleted() or image_list.IsBeingDeleted():
            return
    except Exception:
        pass
    load_download_history()
    with _history_lock:
        records = list(download_history)

    list_ctrl.DeleteAllItems()
    image_list.RemoveAll()

    icon_cache = {}

    for record in records:
        try:
            save_path = record.get("save_path", "") or ""
            filename = record.get("filename", "") or ""
            status = record.get("status", "") or ""
            timestamp = record.get("timestamp", "") or ""
            file_path = os.path.join(save_path, filename)

            ext = os.path.splitext(filename)[1].lower()

            if os.path.isfile(file_path) and ext in THUMBNAIL_EXTENSIONS:
                cache_key = file_path
            else:
                cache_key = ext
            if cache_key not in icon_cache:
                icon = get_file_icon(file_path)
                icon_index = image_list.Add(icon)
                icon_cache[cache_key] = icon_index
            else:
                icon_index = icon_cache[cache_key]

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

            list_ctrl.SetItem(index, 1, filename)
            _apply_record_visual(list_ctrl, index, record)
            list_ctrl.SetItem(index, 2, size_str)

            if record.get("url") == "批量下载文件夹":
                pass
            else:

                if status in INCOMPLETE_STATUSES and filename:
                    pct = _get_record_progress(record)
                    if pct is not None:
                        status = f"{pct}%"
                    else:
                        status = f"{status}（未完成）"
            list_ctrl.SetItem(index, 3, status)
            list_ctrl.SetItem(index, 4, save_path)
            list_ctrl.SetItem(index, 5, timestamp)
        except Exception as e:
            logging.error(f"刷新下载记录失败: {e}")
            continue
def on_new_download(parent, list_ctrl, image_list, prefill_url=None):
    
    import os
    import threading
    import platform
    

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

    if prefill_url:
        url_text.SetValue(prefill_url)
        try:
            filename_text.SetValue(get_filename_from_url(prefill_url))
        except Exception:
            pass
    

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
    thread_count_spin = wx.SpinCtrl(single_panel, min=1, max=1024, initial=4, size=(150, -1))
    thread_sizer.Add(thread_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    thread_sizer.Add(thread_count_spin, 0, wx.ALL, 5)
    single_sizer.Add(thread_sizer, 0, wx.EXPAND | wx.ALL, 5)

    chunk_sizer = wx.BoxSizer(wx.HORIZONTAL)
    chunk_label = wx.StaticText(single_panel, label="分块大小:")
    chunk_size_text = wx.TextCtrl(single_panel, value="1", size=(80, -1))
    chunk_unit_combo = wx.ComboBox(single_panel, choices=["B", "KB", "MB", "GB"], style=wx.CB_READONLY, value="MB")
    chunk_sizer.Add(chunk_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    chunk_sizer.Add(chunk_size_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    chunk_sizer.Add(chunk_unit_combo, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    single_sizer.Add(chunk_sizer, 0, wx.EXPAND | wx.ALL, 5)
    
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

    batch_chunk_sizer = wx.BoxSizer(wx.HORIZONTAL)
    batch_chunk_label = wx.StaticText(batch_panel, label="分块大小:")
    batch_chunk_size_text = wx.TextCtrl(batch_panel, value="1", size=(80, -1))
    batch_chunk_unit_combo = wx.ComboBox(batch_panel, choices=["B", "KB", "MB", "GB"], style=wx.CB_READONLY, value="MB")
    batch_chunk_sizer.Add(batch_chunk_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    batch_chunk_sizer.Add(batch_chunk_size_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    batch_chunk_sizer.Add(batch_chunk_unit_combo, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    batch_sizer.Add(batch_chunk_sizer, 0, wx.EXPAND | wx.ALL, 5)
    
    undownloaded_list = wx.ListBox(batch_panel, style=wx.LB_SINGLE)
    batch_sizer.Add(undownloaded_list, 1, wx.ALL | wx.EXPAND, 5)
    
    batch_panel.SetSizer(batch_sizer)
    notebook.AddPage(batch_panel, "批量下载")
    
    # ==================== BT 下载选项卡 ====================
    bt_panel = wx.Panel(notebook)
    bt_sizer = wx.BoxSizer(wx.VERTICAL)
    
    bt_tip = wx.StaticText(bt_panel, label="支持磁力链 / HTTPS 种子链接 / 本地 .torrent 文件")
    bt_tip.SetForegroundColour(wx.Colour(120, 120, 120))
    bt_sizer.Add(bt_tip, 0, wx.ALL | wx.EXPAND, 5)
    
    bt_src_sizer = wx.BoxSizer(wx.HORIZONTAL)
    bt_src_label = wx.StaticText(bt_panel, label="磁力/种子链接:")
    bt_source_text = wx.TextCtrl(bt_panel)
    choose_torrent_btn = wx.Button(bt_panel, label="选择 .torrent 文件")
    bt_src_sizer.Add(bt_src_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    bt_src_sizer.Add(bt_source_text, 1, wx.ALL, 5)
    bt_src_sizer.Add(choose_torrent_btn, 0, wx.ALL, 5)
    bt_sizer.Add(bt_src_sizer, 0, wx.EXPAND | wx.ALL, 5)
    
    bt_path_sizer = wx.BoxSizer(wx.HORIZONTAL)
    bt_path_label = wx.StaticText(bt_panel, label="保存目录:")
    bt_path_text = wx.TextCtrl(bt_panel, value=default_save_path)
    bt_path_browse_btn = wx.Button(bt_panel, label="浏览...")
    bt_path_sizer.Add(bt_path_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    bt_path_sizer.Add(bt_path_text, 1, wx.ALL, 5)
    bt_path_sizer.Add(bt_path_browse_btn, 0, wx.ALL, 5)
    bt_sizer.Add(bt_path_sizer, 0, wx.EXPAND | wx.ALL, 5)
    
    bt_hint = wx.StaticText(bt_panel, label="BT 依赖 aria2 下载引擎；请先确保本机已安装 aria2。")
    bt_hint.SetForegroundColour(wx.Colour(150, 150, 150))
    bt_sizer.Add(bt_hint, 0, wx.ALL | wx.EXPAND, 5)
    
    bt_panel.SetSizer(bt_sizer)
    notebook.AddPage(bt_panel, "BT下载")
    
    def on_choose_torrent(event):
        with wx.FileDialog(dlg, "选择 torrent 种子文件", wildcard="种子文件 (*.torrent)|*.torrent|所有文件 (*.*)|*.*",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fd:
            if fd.ShowModal() == wx.ID_OK:
                bt_source_text.SetValue(fd.GetPath())
    
    def on_bt_path_browse(event):
        dd = wx.DirDialog(dlg, "选择保存目录", defaultPath=bt_path_text.GetValue())
        if dd.ShowModal() == wx.ID_OK:
            bt_path_text.SetValue(dd.GetPath())
        dd.Destroy()
    
    choose_torrent_btn.Bind(wx.EVT_BUTTON, on_choose_torrent)
    bt_path_browse_btn.Bind(wx.EVT_BUTTON, on_bt_path_browse)

    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    ok_btn = wx.Button(panel, wx.ID_OK, label="确定")
    cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="取消")
    btn_sizer.AddStretchSpacer(1)
    btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
    btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
    main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
    
    panel.SetSizer(main_sizer)
    

    batch_urls = []
    
    def get_chunk_size_bytes(size_ctrl, unit_ctrl):
        try:
            val = float(size_ctrl.GetValue().strip())
            unit = unit_ctrl.GetValue()
            multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
            return max(int(val * multipliers.get(unit, 1024**2)), 1)
        except:
            return 1024 * 1024

    def on_url_enter(event):
        url = url_text.GetValue().strip()
        if url:
    
            filename = get_filename_from_url(url)
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
     
            filename = get_filename_from_url(url)
            filename_text.SetValue(filename)
    
    url_text.Bind(wx.EVT_TEXT, on_url_change)
    

    if dlg.ShowModal() == wx.ID_OK:
        current_page = notebook.GetSelection()
        
        if current_page == 0:  
            url = url_text.GetValue().strip()
            filename = filename_text.GetValue().strip()
            save_path = path_text.GetValue().strip()
            thread_count = thread_count_spin.GetValue()
            chunk_size = get_chunk_size_bytes(chunk_size_text, chunk_unit_combo)
            
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
                

                
              
                def on_download_completed(success, file_size, uuid=None):
    
                    def set_status(u):
                        if u:
                            if success:
                                update_download_record_by_uuid(u, status="已完成", file_size=file_size)
                            else:
                                if file_size > 0:
                                    update_download_record_by_uuid(u, status="部分完成", file_size=file_size)
                                else:
                                    update_download_record_by_uuid(u, status="失败")

                    if uuid:
                        set_status(uuid)
                    else:
     
                        for u in download_history:
                            if (u.get("url") == url and
                                u.get("filename") == filename and
                                u.get("save_path") == save_path):
                                set_status(u.get("uuid"))
                                break
                 
                    if success:
                        try:
                            import DownloadCleanup
                            DownloadCleanup.cleanup_download_artifacts(save_path, filename)
                            DownloadCleanup.cleanup_stale_progress_files(PROCESS_DIR)
                        except Exception:
                            pass
                   
                    wx.CallAfter(refresh_download_list, list_ctrl, image_list)
                
                def start_download():
                    try:
                        record = add_download_record(url, filename, save_path, "下载中", 0)
                        record_uuid = record["uuid"]
                      
                        record["resume_file"] = os.path.join(PROCESS_DIR, f"{filename}_download_progress.json")
                        save_download_history()
                       
                        wx.CallAfter(refresh_download_list, list_ctrl, image_list)

                     
                        if is_fat_filesystem(save_path):
                            wx.CallAfter(
                                wx.MessageBox,
                                "目标保存路径位于 FAT(含 exFAT) 文件系统，不支持稀疏文件，\n已切换到旧版下载引擎。",
                                "提示", wx.OK | wx.ICON_INFORMATION
                            )
                            wx.CallAfter(
                                download_window, url, filename, save_path,
                                thread_count, True, on_download_completed
                            )
                            return

                        import NewDownloadCore

                        wx.CallAfter(NewDownloadCore.Download, record_uuid, url, save_path, filename, 
                                    Jobs=thread_count, Cache=5, Size=chunk_size, 
                                    disable_ssl=True, completion_callback=on_download_completed,
                                    SpeedUnit=get_speed_unit())
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
        
        elif current_page == 1:  
            if not batch_urls:
                wx.MessageBox("请先导入网址文件", "错误", wx.OK | wx.ICON_ERROR)
                dlg.Destroy()
                return
            
            main_site = main_site_text.GetValue().strip()
            thread_count = batch_thread_spin.GetValue()
            folder_name = folder_text.GetValue().strip()
            batch_chunk_size = get_chunk_size_bytes(batch_chunk_size_text, batch_chunk_unit_combo)
            
            if not folder_name:
                wx.MessageBox("请输入文件夹名称", "错误", wx.OK | wx.ICON_ERROR)
                dlg.Destroy()
                return
            

            parent_window = parent
            if hasattr(dlg, 'download_items') and dlg.download_items:
                parent_window.download_items = dlg.download_items
            dlg.Destroy()        
           
            try:
                import BatchDownload
                BatchDownload.create_download_window(
                    parent_window, 
                    batch_urls, 
                    thread_count, 
                    main_site, 
                    default_save_path,
                    folder_name,
                    list_ctrl,  
                    image_list,
                    chunk_size=batch_chunk_size
                )
            except Exception as e:
                wx.MessageBox(f"启动批量下载失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            return  
        elif current_page == 2:  
            source = bt_source_text.GetValue().strip()
            save_path = bt_path_text.GetValue().strip()
            
            if not source:
                wx.MessageBox("请输入磁力链/种子链接，或选择 .torrent 文件", "提示", wx.OK | wx.ICON_ERROR)
                dlg.Destroy(); return
            if not save_path:
                wx.MessageBox("请输入保存目录", "提示", wx.OK | wx.ICON_ERROR)
                dlg.Destroy(); return
            
            import TorrentDownload as _TD
            ok, msg = _start_bt_download(parent, list_ctrl, image_list, source, save_path, _TD)
            if msg:
                wx.MessageBox(msg, "BT下载", wx.OK | wx.ICON_ERROR if not ok else wx.ICON_INFORMATION)
                if not ok:
                    dlg.Destroy()
                    return
    dlg.Destroy()


def _ensure_aria2c(parent, TD):
    """确保 aria2 可用：仅查找本机已安装的 aria2c。

    返回 (exe, error)；未找到时给出安装提示。
    """
    exe = TD.find_aria2c()
    if exe:
        return exe, None
    return None, ("未找到 aria2 引擎。请先安装 aria2 后重试。\n"
                  "Linux: sudo apt install aria2 / sudo pacman -S aria2\n"
                  "Windows: 从 aria2 官网下载 aria2c.exe 放入程序目录或 PATH")


def _start_bt_download(parent, list_ctrl, image_list, source, save_path, TD):
    """创建 BT 下载记录, 弹出进度窗口并启动后台下载。返回 (成功?, 提示消息)。"""
    import threading
    use_service = bool(getattr(TD, "bt_use_service", lambda: False)())
    exe, err = _ensure_aria2c(parent, TD)
    if not exe:
        return False, err


    storage = {"status": "连接中", "gid": None, "engine_status": "active",
               "name": "", "done": 0, "total": 0, "speed": 0,
               "via_service": use_service}
    try:
        import BtorrentWindow
        BtorrentWindow.show_bt_window(parent, storage, save_path)
    except Exception as e:
        print("BT 进度窗口打开失败:", e)

    os.makedirs(save_path, exist_ok=True)
    record = add_download_record(source, "BT下载", save_path, "下载中", 0)
    record["proto"] = "bt"
    record["source"] = source
    record["bt_is_dir"] = True
    record["bt_gid"] = ""
    save_download_history()
    uuid = record["uuid"]
    wx.CallAfter(refresh_download_list, list_ctrl, image_list)

    def tick():
        try:
            _exec_bt(uuid, source, save_path, exe, list_ctrl, image_list, TD, storage)
        except Exception as e:
            storage.update({"status": "失败", "err": str(e)})
            update_download_record_by_uuid(uuid, status="失败")
            wx.CallAfter(refresh_download_list, list_ctrl, image_list)
    threading.Thread(target=tick, daemon=True).start()
    return True, ""


def _exec_bt(record_uuid, source, save_path, exe, list_ctrl, image_list, TD, storage=None):
    """在后台线程执行 BT 下载并同步记录/列表/进度窗。

    storage["via_service"] 为真时走常驻服务（可在 aria2 管理面板查看/做种），
    否则走每任务独立会话(旧行为)。
    """
    prog_json = os.path.join(PROCESS_DIR, "bt_" + str(record_uuid)[:8] + ".json")
    import time as _t
    _last = {"sig": None, "t": 0.0}

    def _needs_refresh(status, done, total, fname):
        pct = (int(done * 100 // total) if total and total > 0 else -1)
        sig = "%s|%d|%s" % (status, pct, fname)
        now = _t.time()
        if sig != _last["sig"] or (now - _last["t"]) >= 5.0:
            _last["sig"] = sig
            _last["t"] = now
            return True
        return False

    def on_state(state, gid):
        status = state.get("status", "下载中")
        done = state.get("done", 0)
        total = state.get("total", 0)
        fname = (state.get("name") or "").strip()
        files = state.get("files") or []

        if storage is not None:
            try:
                storage["status"] = "完成" if status == "完成" else ("失败" if status == "失败" else status)
                if gid:
                    storage["gid"] = gid
                if fname:
                    storage["name"] = fname
                storage["done"] = done
                storage["total"] = total
                storage["speed"] = state.get("speed", 0)
            except Exception:
                pass
        try:
            with open(prog_json, "w", encoding="utf-8") as f:
                json.dump({"file_total_size": total or 0, "total_downloaded": done or 0}, f)
        except Exception:
            pass

        rec = get_download_record_by_uuid(record_uuid) or {}

        if fname and not rec.get("bt_name"):
            update_download_record_by_uuid(record_uuid, filename=fname, bt_single=(len(files) == 1),
                                           bt_name=fname, bt_gid=gid or "")
            rec["filename"] = fname
            rec["bt_single"] = len(files) == 1
        if total and int(rec.get("file_size") or 0) != int(total):
            update_download_record_by_uuid(record_uuid, file_size=int(total))
            rec["file_size"] = int(total)


        if files:
            sig = tuple((f.get("path"), f.get("length"), f.get("completed")) for f in files)
            if sig != _last.get("bt_files"):
                _last["bt_files"] = sig
                update_download_record_by_uuid(record_uuid, bt_files=list(files))
                rec["bt_files"] = list(files)

        path = ""
        mf = [f for f in files if f.get("path")]
        if status in ("完成", "做种中") and mf:

            onep = mf[0]["path"]
            full = onep if os.path.isabs(onep) else os.path.join(save_path, onep)
            if len(mf) == 1:
                update_download_record_by_uuid(record_uuid,
                                               filename=os.path.basename(full),
                                               save_path=os.path.dirname(full))
                rec["filename"] = os.path.basename(full)
                rec["save_path"] = os.path.dirname(full)
            else:

                bdir = os.path.dirname(full)
                if os.path.basename(bdir) != os.path.basename(save_path) and bdir != save_path:
                    update_download_record_by_uuid(record_uuid,
                                                   filename=os.path.basename(bdir),
                                                   save_path=os.path.dirname(bdir))
                    rec["filename"] = os.path.basename(bdir)
                    rec["save_path"] = os.path.dirname(bdir)
                else:
                    rec["filename"] = rec.get("filename")
                    rec["save_path"] = save_path

            update_download_record_by_uuid(record_uuid, status="已完成", bt_gid=gid or "",
                                           bt_seeding=bool(state.get("seeding")))
        elif status == "完成":
            update_download_record_by_uuid(record_uuid, status="已完成", bt_gid=gid or "",
                                           bt_seeding=bool(state.get("seeding")))
        elif status == "失败":
            update_download_record_by_uuid(record_uuid, status="失败: " + (state.get("err") or "BT下载异常"))
        elif status == "取消":
            update_download_record_by_uuid(record_uuid, status="已取消")
        if _needs_refresh(status, done, total, fname):
            wx.CallAfter(refresh_download_list, list_ctrl, image_list)

    if storage is not None and storage.get("via_service"):
        TD.run_bt_task_via_service(source, save_path, on_state)
    else:
        TD.run_bt_task(source, save_path, exe, on_state)


def _delete_selected_records(list_ctrl, delete_files=False):
    """删除列表中选中记录的删除逻辑（不含确认对话框）。"""
    global download_history
    selected_indices = []
    item = list_ctrl.GetFirstSelected()
    while item != -1:
        selected_indices.append(item)
        item = list_ctrl.GetNextSelected(item)
    selected_indices.sort(reverse=True)
    for index in selected_indices:
        if not (0 <= index < len(download_history)):
            continue
        record = download_history[index]
        if delete_files:
            file_path = os.path.join(record["save_path"], record["filename"])
            try:
                if os.path.exists(file_path):
                    if record.get("url") == "批量下载文件夹":
                        import shutil
                        shutil.rmtree(file_path)
                    elif os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        import shutil
                        shutil.rmtree(file_path)
            except Exception as e:
                wx.MessageBox(f"删除文件失败: {str(e)}", "警告", wx.OK | wx.ICON_WARNING)
        download_history.pop(index)
    save_download_history()
    wx.CallAfter(refresh_download_list, list_ctrl, list_ctrl.GetImageList(wx.IMAGE_LIST_SMALL))


def on_delete_key(event, list_ctrl):
    """Delete 键直接删除选中记录（不弹确认框，不删除磁盘文件）。"""
    code = event.GetKeyCode()
    if code == wx.WXK_DELETE or code == getattr(wx, "WXK_NUMPAD_DELETE", -1):
        if list_ctrl.GetSelectedItemCount() > 0:
            _delete_selected_records(list_ctrl, delete_files=False)
        return
    event.Skip()


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
    dlg_sizer = wx.BoxSizer(wx.VERTICAL)
    dlg_sizer.Add(panel, 1, wx.EXPAND)
    dlg.SetSizer(dlg_sizer)
    dlg.Layout()
    
    def on_yes(event):
        dlg.EndModal(wx.ID_YES)
    
    def on_no(event):
        dlg.EndModal(wx.ID_NO)
    
    yes_btn.Bind(wx.EVT_BUTTON, on_yes)
    no_btn.Bind(wx.EVT_BUTTON, on_no)
    
    if dlg.ShowModal() == wx.ID_YES:
        _delete_selected_records(list_ctrl, delete_files=delete_files_checkbox.GetValue())
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

    dlg_sizer = wx.BoxSizer(wx.VERTICAL)
    dlg_sizer.Add(panel, 1, wx.EXPAND)
    dlg.SetSizer(dlg_sizer)
    dlg.Layout()
    
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
                if not open_file_or_folder(folder_path):
                    wx.MessageBox("无法打开文件夹", "错误", wx.OK | wx.ICON_ERROR)
            else:
                wx.MessageBox("文件夹不存在", "错误", wx.OK | wx.ICON_ERROR)
        elif os.path.exists(file_path) and record["status"] == "已完成":
            if not open_file_or_folder(file_path):
                wx.MessageBox("无法打开文件", "错误", wx.OK | wx.ICON_ERROR)
        elif record.get("status", "") in ("下载中", "部分完成", "失败", "失败：分片重试耗尽", "失败：下载中断") and resolve_resume_file(record):
           
            resume_download_record(list_ctrl, record)
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
            if not open_file_or_folder(file_path):
                wx.MessageBox("无法打开文件", "错误", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("文件不存在", "错误", wx.OK | wx.ICON_ERROR)

def on_menu_open_folder(event, list_ctrl):
    """在文件夹中显示"""
    selected = list_ctrl.GetFirstSelected()
    if selected != -1 and 0 <= selected < len(download_history):
        record = download_history[selected]
        file_path = os.path.join(record["save_path"], record["filename"])
        
        if os.path.exists(file_path):
            if not open_file_or_folder(record["save_path"]):
                wx.MessageBox("无法打开文件夹", "错误", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("文件不存在", "错误", wx.OK | wx.ICON_ERROR)
def _bt_relaunch(list_ctrl, record):
    """BT 记录的“继续/重新下载”：用原磁力/种子重新发起 BT 任务。

    已下载分片由 aria2 校核后直接续作/作种，因此可同时用于下载恢复与重新下载。
    保存目录沿用原记录；新任务在「BT 下载 → 作种管理」中可见。
    """
    src = record.get("source") or record.get("url") or ""
    if not src or src == "BT下载":
        wx.MessageBox("该记录缺少 BT 来源(磁力/种子)，无法恢复。", "提示",
                      wx.OK | wx.ICON_INFORMATION)
        return
    save_path = record.get("save_path") or os.path.join(os.path.expanduser("~"), "Downloads")
    try:
        import TorrentDownload as _TD
    except Exception as e:
        wx.MessageBox(f"BT 引擎不可用：{e}", "错误", wx.OK | wx.ICON_ERROR)
        return
    try:
        img = list_ctrl.GetImageList(wx.IMAGE_LIST_SMALL)
    except Exception:
        img = None
    parent = wx.GetTopLevelParent(list_ctrl)
    ok, msg = _start_bt_download(parent, list_ctrl, img, src, save_path, _TD)
    if not ok:
        wx.MessageBox(f"恢复 BT 任务失败：{msg}", "错误", wx.OK | wx.ICON_ERROR)


def resume_download_record(list_ctrl, record):
 

    if record.get("proto") == "bt":
        _bt_relaunch(list_ctrl, record)
        return
    resume_file = resolve_resume_file(record)
    if not resume_file:
        wx.MessageBox("未找到断点进度文件，无法恢复下载。", "提示", wx.OK | wx.ICON_INFORMATION)
        return

    save_path = record.get("save_path", "")
    save_path = os.path.dirname(resume_file) if not save_path else save_path
    if not os.path.exists(save_path):
        os.makedirs(save_path, exist_ok=True)

    target_file = os.path.join(save_path, record.get("filename", ""))
    if not os.path.exists(target_file):
        wx.MessageBox(
            f"未找到已下载的临时文件：{target_file}\n请确认文件未被移动或删除，否则无法继续分段下载。",
            "恢复失败", wx.OK | wx.ICON_ERROR)
        return

    status = record.get("status", "")
    record_uuid = record.get("uuid", "")

    def on_resume_completed(success, file_size, uuid=None):
        set_uuid = uuid if uuid else record_uuid
        if success:
            if set_uuid:
                update_download_record_by_uuid(set_uuid, status="已完成", file_size=file_size)
 
            if resume_file and os.path.exists(resume_file):
                try:
                    os.remove(resume_file)
                except Exception:
                    pass
  
            try:
                import DownloadCleanup
                DownloadCleanup.cleanup_download_artifacts(save_path, record.get("filename", ""))
                DownloadCleanup.cleanup_stale_progress_files(PROCESS_DIR)
            except Exception:
                pass
        else:
           
            disk_size = 0
            try:
                disk_size = os.path.getsize(os.path.join(save_path, record.get("filename", "")))
            except Exception:
                disk_size = 0
            if set_uuid:
                if disk_size > 0 or _get_record_progress(record):
                    update_download_record_by_uuid(set_uuid, status="部分完成", file_size=disk_size)
                else:
                    update_download_record_by_uuid(set_uuid, status="失败", file_size=file_size)
        wx.CallAfter(refresh_download_list, list_ctrl, list_ctrl.GetImageList(wx.IMAGE_LIST_SMALL))

    def _do_resume():
      
        try:
            import NewDownloadCore
            NewDownloadCore.ResumeDownload(
                ResumePath=resume_file,
                SavePath=save_path,
                InputPath=save_path,
                uuid=record_uuid,
                SpeedUnit=get_speed_unit(),
                completion_callback=on_resume_completed,
                Jobs=0,
                Size=0,
                Cache=0.0,
            )
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"启动恢复下载失败：{str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            wx.CallAfter(refresh_download_list, list_ctrl, list_ctrl.GetImageList(wx.IMAGE_LIST_SMALL))

    if status == "下载中":
        update_download_record_by_uuid(record_uuid, status="失败")
        save_download_history()

    wx.CallAfter(_do_resume)


def on_menu_resume(event, list_ctrl):
    
    selected = list_ctrl.GetFirstSelected()
    if selected == -1 or selected >= len(download_history):
        return
    resume_download_record(list_ctrl, download_history[selected])


def on_menu_redownload(event, list_ctrl):

    selected = list_ctrl.GetFirstSelected()
    if selected != -1 and 0 <= selected < len(download_history):
        record = download_history[selected]

        if record.get("proto") == "bt":
            _bt_relaunch(list_ctrl, record)
            return
        url = record["url"]
        filename = record["filename"]
        save_path = record["save_path"]
        
        if record.get("url") == "批量下载文件夹":

            if record.get("download_items"):

                try:
                    import BatchDownload
 
                    download_items = record.get("download_items", [])
                    urls = [item["url"] for item in download_items]
                    

                    BatchDownload.create_download_window(
                        None,  
                        urls, 
                        4,  
                        "",  
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
           
            _restart_download_record(list_ctrl, record)

def _restart_download_record(list_ctrl, record):
    """用记录中的 URL/文件名/保存路径重新发起下载（新版引擎，FAT 盘回退旧引擎）。"""
    url = record.get("url", "")
    filename = record.get("filename", "")
    save_path = record.get("save_path", "")
    if not url or not filename:
        wx.MessageBox("该记录缺少下载链接或文件名，无法重新下载。", "错误", wx.OK | wx.ICON_ERROR)
        return
    try:
        os.makedirs(save_path, exist_ok=True)
    except Exception as e:
        wx.MessageBox(f"保存路径不可用：{e}", "错误", wx.OK | wx.ICON_ERROR)
        return

    record_uuid = record.get("uuid") or str(uuid.uuid4())
    record["uuid"] = record_uuid
    record["status"] = "下载中"
    record["progress"] = 0
    save_download_history()
    wx.CallAfter(refresh_download_list, list_ctrl, list_ctrl.GetImageList(wx.IMAGE_LIST_SMALL))

    def on_done(success, file_size, uuid=None):
        _uuid = uuid or record_uuid
        if success:
            update_download_record_by_uuid(_uuid, status="已完成", file_size=file_size)
            try:
                import DownloadCleanup
                DownloadCleanup.cleanup_download_artifacts(save_path, filename)
            except Exception:
                pass
        else:
            disk_size = 0
            try:
                disk_size = os.path.getsize(os.path.join(save_path, filename))
            except Exception:
                pass
            update_download_record_by_uuid(_uuid, status="部分完成" if disk_size > 0 else "失败",
                                           file_size=disk_size)
        wx.CallAfter(refresh_download_list, list_ctrl, list_ctrl.GetImageList(wx.IMAGE_LIST_SMALL))

    
    if is_fat_filesystem(save_path):
        wx.CallAfter(wx.MessageBox,
                     "目标保存路径位于 FAT(含 exFAT) 文件系统，不支持稀疏文件，\n已切换到旧版下载引擎。",
                     "提示", wx.OK | wx.ICON_INFORMATION)
        wx.CallAfter(download_window, url, filename, save_path, 16, True, on_done)
        return
    try:
        import NewDownloadCore
        wx.CallAfter(NewDownloadCore.Download, record_uuid, url, save_path, filename,
                     Jobs=16, Cache=5, disable_ssl=True, completion_callback=on_done,
                     SpeedUnit=get_speed_unit())
    except Exception as e:
        update_download_record_by_uuid(record_uuid, status=f"失败: {e}")
        save_download_history()
        wx.CallAfter(refresh_download_list, list_ctrl, list_ctrl.GetImageList(wx.IMAGE_LIST_SMALL))
        wx.MessageBox(f"重新下载失败：{e}", "错误", wx.OK | wx.ICON_ERROR)

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

def trigger_new_download(parent=None, prefill_url=None):
    if parent is None:
        app = wx.GetApp()
        if app is not None:
            parent = wx.GetActiveWindow()
            if parent is None:
                parent = app.GetTopWindow()
    try:
        lst = _download_list_ctrl
        img = _image_list_ctrl
    except NameError:
        lst = None
        img = None
    if lst is None or img is None:
        return
    on_new_download(parent, lst, img, prefill_url=prefill_url)


def trigger_bt_download(source, save_path=None, parent=None):
    """外部入口：从文件关联/命令行直接发起 BT 下载。

    source 可为本地 .torrent 路径、磁力链或种子 URL。
    返回 (成功?, 提示消息)。
    """
    if not source:
        return False, "缺少 BT 来源"
    if save_path is None or not str(save_path).strip():
        try:
            import TorrentDownload as _TD
            save_path = _TD.app_download_dir()
        except Exception:
            save_path = os.path.join(os.path.expanduser("~"), "Downloads")
    try:
        import TorrentDownload as _TD
    except Exception as e:
        return False, f"BT 引擎不可用：{e}"
    if parent is None:
        try:
            parent = _download_list_ctrl.GetParent()
        except Exception:
            parent = wx.GetActiveWindow()
    try:
        lst = _download_list_ctrl
        img = _image_list_ctrl
    except NameError:
        lst = None
        img = None
    if lst is None or img is None:
        return False, "下载面板尚未就绪"
    try:
        return _start_bt_download(parent, lst, img, source, save_path, _TD)
    except Exception as e:
        return False, str(e)

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