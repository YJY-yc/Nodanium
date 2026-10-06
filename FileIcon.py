# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT

import os
import platform
import logging
import ctypes
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
    

    if file_path:
        file_path = os.path.normpath(file_path)
    
   
    sys_type = platform.system()
    
    if sys_type == "Windows":
        result = get_windows_icon(file_path, size)
        if result is not None:
            return result
    elif sys_type == "Linux":
        result = get_linux_icon(file_path, size)
        if result is not None:
            return result
    

    if sys_type == "Windows":
        logging.warning(
            f"Windows系统图标获取失败，已回退到自绘图标: {file_path}"
        )
    return get_fallback_icon(file_path, size)


THUMBNAIL_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.ico', '.tif', '.tiff'}



class _SHFILEINFOW(ctypes.Structure):
    _fields_ = [
        ("hIcon", ctypes.c_void_p),
        ("iIcon", ctypes.c_int),
        ("dwAttributes", ctypes.c_ulong),
        ("szDisplayName", ctypes.c_wchar * 260),
        ("szTypeName", ctypes.c_wchar * 80),
    ]


_WIN_SHELL32_FUNCS = {}


def _get_shgetfileinfo():
    """获取配置好 argtypes/restype 的 SHGetFileInfoW（避免 64 位指针截断）。"""
    global _WIN_SHELL32_FUNCS
    if "SHGetFileInfoW" in _WIN_SHELL32_FUNCS:
        return _WIN_SHELL32_FUNCS["SHGetFileInfoW"]
    try:
        import ctypes
        shell32 = ctypes.windll.shell32
        shell32.SHGetFileInfoW.argtypes = [
            ctypes.c_wchar_p,       
            ctypes.c_ulong,          
            ctypes.POINTER(_SHFILEINFOW), 
            ctypes.c_uint,           
            ctypes.c_uint,           
        ]
        shell32.SHGetFileInfoW.restype = ctypes.c_size_t 
        _WIN_SHELL32_FUNCS["SHGetFileInfoW"] = shell32.SHGetFileInfoW
        if logging.getLogger().level > logging.INFO:
            logging.warning(f"FileIcon: SHGetFileInfoW argtypes 已配置: {shell32.SHGetFileInfoW}")
        return shell32.SHGetFileInfoW
    except Exception as e:
        logging.warning(f"SHGetFileInfoW 配置失败: {e}")
        return None


def _hicon_to_bitmap(hicon, size):
    """将 HICON 句柄转换为指定尺寸的 wx.Bitmap（转换后释放全部 GDI 句柄）。
    不依赖 wx 的 HICON 转换方法（部分 wxPython 构建没有 FromHIcon/ConvertToBitmap），
    改用 GDI GetIconInfo + GetDIBits 读像素，再用核心 API wx.Image 组装。"""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    class BITMAP(ctypes.Structure):
        _fields_ = [
            ("bmType", ctypes.c_long),
            ("bmWidth", ctypes.c_long),
            ("bmHeight", ctypes.c_long),
            ("bmWidthBytes", ctypes.c_long),
            ("bmPlanes", ctypes.c_ushort),
            ("bmBitsPixel", ctypes.c_ushort),
            ("bmBits", ctypes.c_void_p),
        ]

    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ("fIcon", ctypes.c_bool),
            ("xHotspot", ctypes.c_ulong),
            ("yHotspot", ctypes.c_ulong),
            ("hbmMask", ctypes.c_void_p),
            ("hbmColor", ctypes.c_void_p),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", ctypes.c_uint),
            ("biWidth", ctypes.c_long),
            ("biHeight", ctypes.c_long),
            ("biPlanes", ctypes.c_ushort),
            ("biBitCount", ctypes.c_ushort),
            ("biCompression", ctypes.c_uint),
            ("biSizeImage", ctypes.c_uint),
            ("biXPelsPerMeter", ctypes.c_long),
            ("biYPelsPerMeter", ctypes.c_long),
            ("biClrUsed", ctypes.c_uint),
            ("biClrImportant", ctypes.c_uint),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER)]

    ic = ICONINFO()
    try:
        user32.GetIconInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(ICONINFO)]
        user32.GetIconInfo.restype = ctypes.c_bool
        if not user32.GetIconInfo(hicon, ctypes.byref(ic)):
            return None
        hbm = ic.hbmColor
        if not hbm:
        
            return None

        gdi32.GetObjectA.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        gdi32.GetObjectA.restype = ctypes.c_int
        bm = BITMAP()
        if not gdi32.GetObjectA(ctypes.c_void_p(hbm), ctypes.sizeof(BITMAP), ctypes.byref(bm)):
            return None
        w, h = bm.bmWidth, bm.bmHeight
        if w <= 0 or h <= 0:
            return None

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h 
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  

        raw = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
            ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), ctypes.c_uint,
        ]
        gdi32.GetDIBits.restype = ctypes.c_int
        hdc = user32.GetDC(0)
        try:
            nlines = gdi32.GetDIBits(
                hdc, ctypes.c_void_p(hbm), 0, h, ctypes.byref(raw),
                ctypes.byref(bmi), 0,  
            )
        finally:
            user32.ReleaseDC(0, hdc)
        if nlines <= 0:
            return None

  
        px = raw.raw
        rgb = bytearray(w * h * 3)
        alpha = bytearray(w * h)
        any_alpha = False
        for i in range(w * h):
            j = i * 4
            rgb[i * 3] = px[j + 2]
            rgb[i * 3 + 1] = px[j + 1]
            rgb[i * 3 + 2] = px[j]
            a = px[j + 3]
            alpha[i] = a
            if a != 0:
                any_alpha = True
        img = wx.Image(w, h)
        img.SetData(bytes(rgb))
 
        if any_alpha:
            try:
                img.SetAlpha(bytes(alpha))
            except Exception:
                pass
        bmp = img.ConvertToBitmap()
        if not bmp.IsOk():
            return None
        if bmp.GetWidth() == size and bmp.GetHeight() == size:
            return bmp
        img2 = bmp.ConvertToImage().Scale(size, size, wx.IMAGE_QUALITY_HIGH)
        return img2.ConvertToBitmap()
    except Exception as e:
        logging.debug(f"HICON 读像素失败: {e}")
        return None
    finally:
       
        try:
            if ic.hbmColor:
                gdi32.DeleteObject(ic.hbmColor)
            if ic.hbmMask:
                gdi32.DeleteObject(ic.hbmMask)
        except Exception:
            pass
        try:
            user32.DestroyIcon(hicon)
        except Exception:
            pass


def get_windows_thumbnail(file_path, size=32):
    """对存在的图片文件生成真实缩略图，作为图标显示"""
    try:
        if not os.path.isfile(file_path):
            return None
        if PIL_AVAILABLE:
            with Image.open(file_path) as img:
                try:
                    img.load()
                except Exception:
                    return None
                if img.width <= 0 or img.height <= 0:
                    return None
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                rgbt = img.convert('RGB').tobytes()
             
                wx_img = wx.Image(size, size)
                wx_img.SetData(rgbt)
                if 'A' in img.getbands():
                    rgba = img.convert('RGBA').tobytes()
                    alpha = bytes(rgba[3::4]) 
                    try:
                        wx_img.SetAlpha(alpha)
                    except Exception:
                        pass
                return wx.Bitmap(wx_img)
        else:
         
            wx_img = wx.Image(file_path)
            if not wx_img.IsOk():
                return None
            wx_img = wx_img.Scale(size, size, wx.IMAGE_QUALITY_HIGH)
            return wx.Bitmap(wx_img)
    except Exception as e:
        logging.debug(f"图片缩略图生成失败: {e}")
        return None


def _get_shell_thumbnail(file_path, size):
 
    import ctypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class SIZE(ctypes.Structure):
        _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

    try:
        shell32 = ctypes.windll.shell32

        # IShellItemImageFactory IID: bcc18b79-ba16-442f-80c4-8a59c30c463b
        iid = GUID()
        iid.Data1 = ctypes.c_ulong(0xBCC18B79)
        iid.Data2 = ctypes.c_ushort(0xBA16)
        iid.Data3 = ctypes.c_ushort(0x442F)
        iid.Data4 = (ctypes.c_ubyte * 8)(*bytes.fromhex("80c48a59c30c463b"))

        shell32.SHCreateItemFromParsingName.argtypes = [
            ctypes.c_wchar_p, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p),
        ]
        shell32.SHCreateItemFromParsingName.restype = ctypes.c_long

        p_item = ctypes.c_void_p()
        hr = shell32.SHCreateItemFromParsingName(
            file_path, None, ctypes.byref(iid), ctypes.byref(p_item)
        )
        if hr < 0 or not p_item.value:
            return None

        # p_item 指向对象，对象首字段是 vtable 指针数组的首地址
        vtbl_ptr = ctypes.cast(
            p_item, ctypes.POINTER(ctypes.c_void_p)
        ).contents.value
        if not vtbl_ptr:
            return None
        vtbl = ctypes.cast(vtbl_ptr, ctypes.POINTER(ctypes.c_void_p))

        # IUnknown: [0]QueryInterface [1]AddRef [2]Release；[3] 之后是 GetImage
        get_image_cast = ctypes.cast(
            vtbl[3],
            ctypes.CFUNCTYPE(
                ctypes.c_long,
                ctypes.c_void_p,
                ctypes.POINTER(SIZE),
                ctypes.c_uint,
                ctypes.POINTER(ctypes.c_void_p),
            ),
        )
        release_cast = ctypes.cast(
            vtbl[2], ctypes.CFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
        )

        sz = SIZE(size, size)
        hbitmap = ctypes.c_void_p()
        # SIIGBF_RESIZETOFIT = 0：优先返回真缩略图，无法生成时回退图标（与资源管理器一致）
        # 如需强制大尺寸可叠加 SIIGBF_BIGGERSIZEOK=0x01
        hr = get_image_cast(p_item, ctypes.byref(sz), 0x00, ctypes.byref(hbitmap))
        if hr < 0 or not hbitmap.value:
            logging.warning(f"IShellItemImageFactory::GetImage 失败 hr=0x{hr & 0xffffffff:08x}")
            return None
        try:
            try:
                return wx.Bitmap.FromHBitmap(hbitmap.value)
            finally:
            
                gdi32 = ctypes.windll.gdi32
                gdi32.DeleteObject(hbitmap.value)
        finally:
        
            release_cast(p_item)
    except Exception as e:
        logging.warning(f"IShellItemImageFactory 获取缩略图异常: {type(e).__name__}: {e}")
        return None


def _get_dpi_scale():
 
    try:
        import ctypes
        shcore = ctypes.windll.shcore
        if hasattr(shcore, "GetScaleFactorForDevice"):
            val = shcore.GetScaleFactorForDevice(0)
            return val / 100.0
    except Exception:
        pass
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hdc = user32.GetDC(0)
        try:
            dpi = user32.GetDeviceCaps(hdc, 88) 
            return dpi / 96.0
        finally:
            user32.ReleaseDC(0, hdc)
    except Exception:
        return 1.0


def get_windows_icon(file_path, size=32):

    try:
     
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        shgetfileinfo = _get_shgetfileinfo()
        if shgetfileinfo is None:
            logging.warning(f"FileIcon: SHGetFileInfoW 不可用，无法获取系统图标: {file_path}")

        SHGFI_ICON = 0x100
        SHGFI_LARGEICON = 0x0
        SHGFI_SMALLICON = 0x1
        SHGFI_USEFILEATTRIBUTES = 0x10

        shfi = _SHFILEINFOW()

        file_exists = os.path.exists(file_path)
        file_attr = 0x80 
        flags = SHGFI_ICON | SHGFI_LARGEICON
        if file_exists:
            if os.path.isdir(file_path):
                file_attr = 0x10  
        else:
            flags |= SHGFI_USEFILEATTRIBUTES

    
        scale = _get_dpi_scale()
        logging.warning(f"FileIcon: 路径={file_path} 存在={file_exists} 缩放={scale:.2f} 目标size={size}")
        if shgetfileinfo is not None:
            ret = shgetfileinfo(
                file_path,
                file_attr,
                ctypes.byref(shfi),
                ctypes.sizeof(shfi),
                flags,
            )
            logging.warning(f"FileIcon: SHGetFileInfoW ret={ret} hIcon={shfi.hIcon if hasattr(shfi, 'hIcon') else '??'} iIcon={shfi.iIcon}")
            if ret and shfi.hIcon:
            
                bmp = _hicon_to_bitmap(shfi.hIcon, size)
                if bmp is not None:
                    return bmp

 
        if file_exists:
            thumb = _get_shell_thumbnail(file_path, size)
            if thumb is not None and thumb.IsOk():
                if thumb.GetWidth() == size and thumb.GetHeight() == size:
                    return thumb
                img = thumb.ConvertToImage()
                return wx.Bitmap(img.Scale(size, size, wx.IMAGE_QUALITY_HIGH))
            logging.warning(f"FileIcon: shell缩略图失败或不可用: {file_path}")

            ext = os.path.splitext(file_path)[1].lower()
            if ext in THUMBNAIL_EXTENSIONS:
                thumb = get_windows_thumbnail(file_path, size)
                if thumb is not None:
                    return thumb

        return None

    except Exception as e:
        logging.warning(f"Windows图标获取抛异常: {type(e).__name__}: {e}")
        return None

def get_linux_icon(file_path, size=32):
    """获取Linux系统图标"""
    try:
        import gi
        gi.require_version('Gio', '2.0')
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gio, Gtk
        
   
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)
        
        gfile = Gio.File.new_for_path(file_path)
        
 
        if gfile.query_exists(None):
         
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

def load_icon_from_path(icon_path, size):
  
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
      
        if file_path and (os.path.isdir(file_path) or file_path.endswith(('/','\\'))):
            return draw_folder_icon(size)
        
        
        ext = ''
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
        
        color_map = {
            '.txt': (100, 149, 237), 
            '.pdf': (220, 53, 69),    
            '.doc': (0, 112, 192),    
            '.docx': (0, 112, 192),
            '.xls': (34, 197, 94),    
            '.xlsx': (34, 197, 94),
            '.ppt': (251, 146, 60),  
            '.pptx': (251, 146, 60),
            '.html': (251, 191, 36),   
            '.zip': (168, 85, 247),   
            '.rar': (168, 85, 247),
            '.7z': (168, 85, 247),
            '.jpg': (6, 182, 212),    
            '.jpeg': (6, 182, 212),
            '.png': (6, 182, 212),
            '.gif': (6, 182, 212),
            '.mp3': (236, 72, 153),   
            '.wav': (236, 72, 153),
            '.mp4': (139, 92, 246),  
            '.avi': (139, 92, 246),
            '.exe': (220, 53, 69),    
        }
        
        color = color_map.get(ext, (160, 160, 160))
        return draw_file_icon(size, color)
        
    except Exception:
        return get_default_bitmap(size)

def draw_folder_icon(size=32):
    
    bmp = wx.Bitmap(size, size)
    dc = wx.MemoryDC()
    dc.SelectObject(bmp)
    dc.SetBackground(wx.Brush(wx.WHITE))
    dc.Clear()
    

    dc.SetPen(wx.Pen(wx.BLACK, 1))
    dc.SetBrush(wx.Brush(wx.Colour(251, 191, 36)))
    dc.DrawRectangle(4, 10, size-8, size-14)
    dc.DrawPolygon([(4, 10), (size-8+10, 3), (size-4, 10), (4, 10)])
    
    dc.SelectObject(wx.NullBitmap)
    return bmp

def draw_file_icon(size, color):

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