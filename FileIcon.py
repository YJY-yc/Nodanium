# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT

import os
import platform
import logging
import wx

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL/Pillow 未安装，可能影响图标显示")

def get_file_icon(file_path, size=32):
    """获取系统文件管理器显示的图标（跨平台）"""
    icon_size = (size, size)
    
    # 标准化路径
    if file_path:
        file_path = os.path.normpath(file_path)
    
    # 根据平台获取系统图标
    sys_type = platform.system()
    
    if sys_type == "Windows":
        result = get_windows_icon(file_path, size)
        if result is not None:
            return result
    elif sys_type == "Linux":
        result = get_linux_icon(file_path, size)
        if result is not None:
            return result
    elif sys_type == "Darwin":
        result = get_macos_icon(file_path, size)
        if result is not None:
            return result
    
    # 如果系统图标获取失败，使用备用方案
    return get_fallback_icon(file_path, size)

def get_windows_icon(file_path, size=32):
    """获取Windows系统图标"""
    try:
        import ctypes
        from ctypes import wintypes
        
        # 确保路径是绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        # 定义 SHFILEINFO 结构
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
        SHGFI_SMALLICON = 0x1
        SHGFI_USEFILEATTRIBUTES = 0x10
        
        shfi = SHFILEINFOW()
        
        # 检查文件是否存在
        if os.path.exists(file_path):
            # 文件存在，获取真实图标
            file_attr = 0x80  # FILE_ATTRIBUTE_NORMAL
            if os.path.isdir(file_path):
                file_attr = 0x10  # FILE_ATTRIBUTE_DIRECTORY
            
            ret = shell32.SHGetFileInfoW(
                file_path,
                file_attr,
                ctypes.byref(shfi),
                ctypes.sizeof(shfi),
                SHGFI_ICON | SHGFI_SMALLICON
            )
        else:
            # 文件不存在，使用扩展名获取图标
            ret = shell32.SHGetFileInfoW(
                file_path,
                0,
                ctypes.byref(shfi),
                ctypes.sizeof(shfi),
                SHGFI_ICON | SHGFI_SMALLICON | SHGFI_USEFILEATTRIBUTES
            )
        
        if not ret or not shfi.hIcon:
            return None
        
        # 使用 wx.Icon 转换
        icon = wx.Icon()
        icon.SetHandle(shfi.hIcon)
        bmp = wx.Bitmap(icon)
        
        # 调整大小
        if bmp.GetWidth() != size or bmp.GetHeight() != size:
            img = wx.ImageFromBitmap(bmp)
            img = img.Scale(size, size, wx.IMAGE_QUALITY_HIGH)
            bmp = wx.Bitmap(img)
        
        # 释放图标句柄
        ctypes.windll.user32.DestroyIcon(shfi.hIcon)
        return bmp
        
    except Exception as e:
        logging.debug(f"Windows图标获取失败: {e}")
        return None

def get_linux_icon(file_path, size=32):
    """获取Linux系统图标（使用Gio/Gtk）"""
    try:
        import gi
        gi.require_version('Gio', '2.0')
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gio, Gtk
        
        # 确保路径是绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        gfile = Gio.File.new_for_path(file_path)
        
        # 检查文件是否存在
        if gfile.query_exists(None):
            # 文件存在，获取真实图标
            if gfile.query_file_type(Gio.FileQueryInfoFlags.NONE, None) == Gio.FileType.DIRECTORY:
                file_info = gfile.query_info(
                    'standard::icon', 
                    Gio.FileQueryInfoFlags.NONE, 
                    None
                )
            else:
                file_info = gfile.query_info(
                    'standard::content-type,standard::icon', 
                    Gio.FileQueryInfoFlags.NONE, 
                    None
                )
        else:
            # 文件不存在，尝试从扩展名获取图标
            content_type = Gio.content_type_guess(file_path, None)[0]
            gicon = Gio.content_type_get_icon(content_type)
            if gicon:
                icon_theme = Gtk.IconTheme.get_default()
                icon_info = icon_theme.lookup_by_gicon(gicon, size, 0)
                if icon_info:
                    icon_path = icon_info.get_filename()
                    if icon_path and os.path.exists(icon_path):
                        return load_icon_from_path(icon_path, size)
                return None
            return None
        
        gicon = file_info.get_icon()
        if not gicon:
            return None
        
        # 获取主题图标
        icon_theme = Gtk.IconTheme.get_default()
        icon_info = icon_theme.lookup_by_gicon(gicon, size, 0)
        
        if icon_info:
            icon_path = icon_info.get_filename()
            if icon_path and os.path.exists(icon_path):
                return load_icon_from_path(icon_path, size)
        
        return None
        
    except ImportError as e:
        logging.debug(f"Linux图标获取失败（Gio/Gtk未安装）: {e}")
        return None
    except Exception as e:
        logging.debug(f"Linux图标获取失败: {e}")
        return None

def get_macos_icon(file_path, size=32):
    """获取macOS系统图标"""
    try:
        from Cocoa import NSWorkspace, NSImage
        
        # 确保路径是绝对路径
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        workspace = NSWorkspace.sharedWorkspace()
        
        # 检查文件是否存在
        if os.path.exists(file_path):
            # 文件存在，获取真实图标
            icon = workspace.iconForFile_(file_path)
        else:
            # 文件不存在，使用UTI获取图标
            uti = workspace.typeOfFile_error_(file_path, None)
            if uti:
                icon = workspace.iconForFileType_(uti)
            else:
                return None
        
        if not icon:
            return None
        
        # 设置图标大小
        icon.setSize_((size, size))
        rep = icon.representations()[0]
        
        # 转换为wx.Bitmap
        import io
        tiff_data = rep.TIFFRepresentation()
        img = wx.Image(size, size)
        img.LoadFile(io.BytesIO(tiff_data), wx.BITMAP_TYPE_TIFF)
        return wx.Bitmap(img)
        
    except ImportError as e:
        logging.debug(f"macOS图标获取失败（pyobjc未安装）: {e}")
        return None
    except Exception as e:
        logging.debug(f"macOS图标获取失败: {e}")
        return None

def load_icon_from_path(icon_path, size):
    """从图标文件加载并转换为wx.Bitmap"""
    try:
        if PIL_AVAILABLE:
            img = Image.open(icon_path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            
            import io
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            wx_img = wx.Image(size, size)
            wx_img.LoadFile(img_bytes, wx.BITMAP_TYPE_PNG)
            return wx.Bitmap(wx_img)
        else:
            # 没有PIL，尝试用wx直接加载
            wx_img = wx.Image(icon_path)
            if wx_img.IsOk():
                wx_img = wx_img.Scale(size, size, wx.IMAGE_QUALITY_HIGH)
                return wx.Bitmap(wx_img)
        return None
    except Exception as e:
        logging.debug(f"加载图标文件失败: {e}")
        return None

def get_fallback_icon(file_path, size=32):
    """备用图标方案"""
    try:
        # 检查是否是目录
        if file_path and (os.path.isdir(file_path) or file_path.endswith(('/','\\'))):
            return draw_folder_icon(size)
        
        # 根据扩展名返回不同颜色的图标
        ext = ''
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
        
        color_map = {
            '.txt': (100, 149, 237),  # 蓝色
            '.pdf': (220, 53, 69),     # 红色
            '.doc': (0, 112, 192),     # 深蓝
            '.docx': (0, 112, 192),
            '.xls': (34, 197, 94),     # 绿色
            '.xlsx': (34, 197, 94),
            '.ppt': (251, 146, 60),    # 橙色
            '.pptx': (251, 146, 60),
            '.html': (251, 191, 36),   # 黄色
            '.zip': (168, 85, 247),    # 紫色
            '.rar': (168, 85, 247),
            '.7z': (168, 85, 247),
            '.jpg': (6, 182, 212),     # 青色
            '.jpeg': (6, 182, 212),
            '.png': (6, 182, 212),
            '.gif': (6, 182, 212),
            '.mp3': (236, 72, 153),    # 粉色
            '.wav': (236, 72, 153),
            '.mp4': (139, 92, 246),    # 紫色
            '.avi': (139, 92, 246),
            '.exe': (220, 53, 69),     # 红色
        }
        
        color = color_map.get(ext, (160, 160, 160))
        return draw_file_icon(size, color)
        
    except Exception:
        return get_default_bitmap(size)

def draw_folder_icon(size=32):
    """绘制文件夹图标"""
    bmp = wx.Bitmap(size, size)
    dc = wx.MemoryDC()
    dc.SelectObject(bmp)
    dc.SetBackground(wx.Brush(wx.WHITE))
    dc.Clear()
    
    # 绘制文件夹
    dc.SetPen(wx.Pen(wx.BLACK, 1))
    dc.SetBrush(wx.Brush(wx.Colour(251, 191, 36)))
    dc.DrawRectangle(4, 10, size-8, size-14)
    dc.DrawPolygon([(4, 10), (size-8+10, 3), (size-4, 10), (4, 10)])
    
    dc.SelectObject(wx.NullBitmap)
    return bmp

def draw_file_icon(size, color):
    """绘制文件图标"""
    bmp = wx.Bitmap(size, size)
    dc = wx.MemoryDC()
    dc.SelectObject(bmp)
    dc.SetBackground(wx.Brush(wx.WHITE))
    dc.Clear()
    
    dc.SetPen(wx.Pen(wx.BLACK, 1))
    dc.SetBrush(wx.Brush(wx.Colour(240, 240, 240)))
    dc.DrawRectangle(2, 2, size-4, size-4)
    
    dc.SetBrush(wx.Brush(wx.Colour(color)))
    dc.DrawRectangle(2, 2, size//3, 6)
    
    dc.SetPen(wx.Pen(wx.Colour(180, 180, 180), 1))
    line_y = 12
    for i in range(3):
        dc.DrawLine(4, line_y, size-4, line_y)
        line_y += 4
    
    dc.SelectObject(wx.NullBitmap)
    return bmp

def get_default_bitmap(size):
    """默认图标"""
    bmp = wx.Bitmap(size, size)
    dc = wx.MemoryDC()
    dc.SelectObject(bmp)
    dc.SetBackground(wx.Brush(wx.WHITE))
    dc.Clear()
    dc.SetPen(wx.Pen(wx.BLACK, 1))
    dc.SetBrush(wx.Brush(wx.Colour(220, 220, 220)))
    dc.DrawRectangle(2, 2, size-4, size-4)
    dc.SelectObject(wx.NullBitmap)
    return bmp