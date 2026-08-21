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
    if sys_type == "Windows":
        logging.warning(
            f"Windows系统图标获取失败，已回退到自绘图标: {file_path}"
        )
    return get_fallback_icon(file_path, size)

# 适合生成缩略图的图片扩展名
THUMBNAIL_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.ico', '.tif', '.tiff'}


# Windows SHFILEINFOW 结构（模块级定义，避免重复定义）
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
            ctypes.c_wchar_p,        # pszPath
            ctypes.c_ulong,          # dwFileAttributes
            ctypes.POINTER(_SHFILEINFOW),  # psfi
            ctypes.c_uint,           # cbFileInfo
            ctypes.c_uint,           # uFlags
        ]
        shell32.SHGetFileInfoW.restype = ctypes.c_size_t  # DWORD_PTR
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
            # 仅含掩码（老式单色图标），无法直接读色，返回 None 走 fallback
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
        bmi.bmiHeader.biHeight = -h  # 负值 = 自顶向下，与 wx.Image 行序一致
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  # BI_RGB

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
                ctypes.byref(bmi), 0,  # DIB_RGB_COLORS
            )
        finally:
            user32.ReleaseDC(0, hdc)
        if nlines <= 0:
            return None

        # BGRA -> wx.Image(RGB + Alpha)
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
        # 仅当图标真实含 alpha 通道时才设置，否则保持不透明，避免整幅透明导致的“消失”
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
        # 释放 GetIconInfo 返回的位图与 SHGetFileInfoW 的图标句柄
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
                # 将像素数据交给 wx，避免重复编码解码
                wx_img = wx.Image(size, size)
                wx_img.SetData(rgbt)
                if 'A' in img.getbands():
                    rgba = img.convert('RGBA').tobytes()
                    alpha = bytes(rgba[3::4])  # 仅提取 alpha 通道
                    try:
                        wx_img.SetAlpha(alpha)
                    except Exception:
                        pass
                return wx.Bitmap(wx_img)
        else:
            # 无 PIL，用 wx 直接加载
            wx_img = wx.Image(file_path)
            if not wx_img.IsOk():
                return None
            wx_img = wx_img.Scale(size, size, wx.IMAGE_QUALITY_HIGH)
            return wx.Bitmap(wx_img)
    except Exception as e:
        logging.debug(f"图片缩略图生成失败: {e}")
        return None


def _get_shell_thumbnail(file_path, size):
    """通过 IShellItemImageFactory 获取资源管理器中显示的真缩略图（图片/视频/PDF 等）"""
    # 使用标准 COM API：SHCreateItemFromParsingName -> IShellItemImageFactory::GetImage
    # 与“文件资源管理器”使用同一套缩略图/图标解析机制
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
                # 释放 GDI HBITMAP
                gdi32 = ctypes.windll.gdi32
                gdi32.DeleteObject(hbitmap.value)
        finally:
            # 释放 IShellItemImageFactory 对象
            release_cast(p_item)
    except Exception as e:
        logging.warning(f"IShellItemImageFactory 获取缩略图异常: {type(e).__name__}: {e}")
        return None


def _get_dpi_scale():
    """获取当前显示器 DPI 缩放比例（1.0 = 100%）"""
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
            dpi = user32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            return dpi / 96.0
        finally:
            user32.ReleaseDC(0, hdc)
    except Exception:
        return 1.0


def get_windows_icon(file_path, size=32):
    """获取与 Windows 文件资源管理器一致的图标。
    通过 SHGetFileInfoW（系统关联图标，带 DPI 适配）为主路径；
    文件存在时额外尝试 IShellItemImageFactory 提取真缩略图。"""
    try:
        # 确保路径是绝对路径
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

        # 文件不存在时，用扩展名解析关联图标（下载中的文件也能显示对应图标）
        file_exists = os.path.exists(file_path)
        file_attr = 0x80  # FILE_ATTRIBUTE_NORMAL
        flags = SHGFI_ICON | SHGFI_LARGEICON
        if file_exists:
            if os.path.isdir(file_path):
                file_attr = 0x10  # FILE_ATTRIBUTE_DIRECTORY
        else:
            flags |= SHGFI_USEFILEATTRIBUTES

        # 主路径：请求系统关联图标。
        # 注意：返回给调用方的位图必须恒为逻辑 size×size（如 32），不能按 DPI 放大，
        # 否则塞进固定尺寸的 ImageList 会被裁剪（图标看起来不完整）。
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
                # 用 size（非 pixel_size）转换，保证返回位图尺寸与显示层一致，避免裁剪
                bmp = _hicon_to_bitmap(shfi.hIcon, size)
                if bmp is not None:
                    return bmp

        # 缩略图增强：文件存在时，用 shell 机制提取真缩略图（图片/视频/PDF）
        if file_exists:
            thumb = _get_shell_thumbnail(file_path, size)
            if thumb is not None and thumb.IsOk():
                if thumb.GetWidth() == size and thumb.GetHeight() == size:
                    return thumb
                img = thumb.ConvertToImage()
                return wx.Bitmap(img.Scale(size, size, wx.IMAGE_QUALITY_HIGH))
            logging.warning(f"FileIcon: shell缩略图失败或不可用: {file_path}")
            # shell 缩略图失败时，图片用内建缩略图兜底
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