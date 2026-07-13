# Copyright (c) 2023-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import logging
vision = "3.5.2.8"
logging.info('窗口模块启动')
import wx
import os
import time
from os import makedirs
import json
import sys
import threading
import platform
import wx.adv

ChatPort=None



url_text_1, filename_text_1 = "", ""

listbook=None
url_text_analyze=None
time_ctrl=None



sys_type = platform.system()
if sys_type == "Windows":
    roaming_path = os.getenv('APPDATA', '')
    target_folder = os.path.join(roaming_path, "Nodanium")
elif sys_type == "Linux":
    home_path = os.path.expanduser("~")
    target_folder = os.path.join(home_path, ".Nodanium")
elif sys_type == "Darwin":
    home_path = os.path.expanduser("~")
    target_folder = os.path.join(home_path, "Library", "Application Support", "Nodanium")
else:
    target_folder = os.path.join(os.path.expanduser("~"), ".Nodanium")

if not os.path.exists(target_folder):
    os.makedirs(target_folder)
print(target_folder)


dir_file = os.path.join(target_folder, "dir.txt")
if not os.path.exists(dir_file):
    if sys_type == "Windows":
        default_dir = "D:/Downloads/"
    else:
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads") + "/"
    with open(dir_file, "w") as f:
        f.write(default_dir)

with open(dir_file, "r") as f:
    dirs = f.read()

if dirs == "":
    if sys_type == "Windows":
        dirs = "D:/Downloads/"
    else:
        dirs = os.path.join(os.path.expanduser("~"), "Downloads") + "/"
    with open(dir_file, "w") as f:
        f.write(dirs)
print(dirs)
try:
    makedirs(dirs)
except:
    pass
    
try:
    makedirs(dirs+"temp/")
except:
        pass
config = {
    'font_size': 17,
    'list_button_size': 15,
    'font_name': "微软雅黑",
    'size': (300, 30),
    'size_button': (100, 30),
    'window_pos': (100, 20),  
    'window_size': [1020, 700],
    'high_dpi':True,
    'share_path': os.path.join(os.path.expanduser("~"), "SharedFiles") if sys.platform.startswith('linux') else "D:/SharedFiles",
    'default_port':1524,
    'auto_open_browser':True
}

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


FontSize = config['font_size']
ListButtonSize = config['list_button_size']
fontname = config['font_name']
Size = tuple(config['size'])
SizeButton = tuple(config['size_button'])
windowPos = tuple(config['window_size'])

try:
    import Adminchaker
except ImportError as e:
    print(f"导入 Adminchaker 失败: {e}")

try:
    import DNSShower
except ImportError as e:
    print(f"导入 DNSShower 失败: {e}")

try:
    import CommanDownload
except ImportError as e:
    print(f"导入 CommanDownload 失败: {e}")

try:
    import NetworkTraffic
except ImportError as e:
    print(f"导入 NetworkTraffic 失败: {e}")

try:
    import analyze
except ImportError as e:
    print(f"导入 analyze 失败: {e}")

try:
    import DownloadUI
except ImportError as e:
    print(f"导入 DownloadUI 失败: {e}")

try:
    from TPort import *
except ImportError as e:
    print(f"导入 TPort 失败: {e}")

try:
    import FileShareShell
except ImportError as e:
    print(f"导入 FileShareShell 失败: {e}")

try:
    import LinkButton
except ImportError as e:
    print(f"导入 LinkButton 失败: {e}")

try:
    import DatchDownload
except ImportError as e:
    print(f"导入 DatchDownload 失败: {e}")

try:
    from Ping import *
except ImportError as e:
    print(f"导入 Ping 失败: {e}")

try:
    from update import *
except ImportError as e:
    print(f"导入 update 失败: {e}")

try:
    import options
except ImportError as e:
    print(f"导入 options 失败: {e}")

try:
    import FileServer
except ImportError as e:
    print(f"导入 FileServer 失败: {e}")

try:
    import PortManager
except ImportError as e:
    print(f"导入 PortManager 失败: {e}")
#插件
program_dir = os.path.dirname(os.path.abspath(__file__))
plugins_dir = os.path.join(program_dir, "Plugins")

if os.path.exists(plugins_dir) and plugins_dir not in sys.path:
    sys.path.insert(0, plugins_dir)

plugins = {}

try:
    if not os.path.exists(plugins_dir):
        print(f"插件目录 {plugins_dir} 不存在")
        logging.info(f"插件目录 {plugins_dir} 不存在")
    else:
        print(f"正在扫描插件目录: {plugins_dir}")
        logging.info(f"正在扫描插件目录: {plugins_dir}")
        if plugins_dir not in sys.path:
            sys.path.insert(0, plugins_dir)
        
        for filename in os.listdir(plugins_dir):
          
            if (filename == "__init__.py" or 
                filename == "__pycache__" or
                not (filename.endswith('.pyd') or filename.endswith('.py'))):
                continue
                
            plugin_name = os.path.splitext(filename)[0]
            
            if not plugin_name:
                continue
            
            try:
                print(f"正在尝试加载插件: {plugin_name}")
                logging.info(f"正在尝试加载插件: {plugin_name}")
              
                plugin_module = __import__(plugin_name)
                plugins[plugin_name] = plugin_module
                
                globals()[plugin_name] = plugin_module
                print(f"成功加载插件: {plugin_name}")
                logging.info(f"成功加载插件: {plugin_name}")
                
            except Exception as e:
                print(f"无法加载插件 {plugin_name}: {e}")
                logging.warning(f"无法加载插件 {plugin_name}: {e}")
                
except Exception as e:
    print(f"读取插件目录时出错: {e}")
    logging.info(f"读取插件目录时出错: {e}")
#=======================================




username_ctrl,password_ctrl=None,None

check=None

def on_analyze(event):
    global url_text_analyze,time_ctrl,check
    head="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    try:
        header_path = os.path.join(target_folder, "Head.ANT")
        if os.path.exists(header_path):
            with open(header_path, 'r', encoding='utf-8') as f:
                head=f.read()
    except:
        head="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"

    
    analyze.on_analyze_button(url_text_analyze.GetValue(), head,int(time_ctrl.GetValue()),check.GetValue())

def on_go_to_file(event):
        

    if os.path.isdir(dirs):
        os.startfile(dirs) 

def on_go_to_advanced(event):
    global listbook
   
    listbook.ChangeSelection(1)
def url3(frame, event):
    pass

def on_download_button(event):
    global url_text_1, filename_text_1, dirs
    url = url_text_1.GetValue()
    filename = filename_text_1.GetValue()
    
  
    history_path = os.path.join(target_folder, "history.json")
    history = []
    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            history = json.load(f)
    
    history.append({
        "url": url,
        "filename": filename,
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)
    
    header_path = os.path.join(target_folder, "Head.ANT")
    if os.path.exists(header_path):
        with open(header_path, 'r', encoding='utf-8') as f:
            he=f.read()

    CommanDownload.download_file(url, dirs+filename,he)
    print(f"URL: {url}, 文件名: {filename}")
    logging.debug(f"URL: {url}, 文件名: {filename}")
    frame.SetStatusText("")

def thread_download_button(event):
    global url_text, filename_text, thread_choice, packet_size_choice,dirs
    url = url_text.GetValue()
    filename = filename_text.GetValue()
    
 
    history_path = os.path.join(target_folder, "history.json")
    history = []
    if os.path.exists(history_path):
        with open(history_path, 'r', encoding='utf-8') as f:
            history = json.load(f)
    
    history.append({
        "url": url,
        "filename": filename,
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=4)
    
    import DownloadCore
    DownloadCore.download_window(
    url=url,
    filename=filename,
    save_path=dirs,
    disable_ssl = True ,
    thread_count=int(thread_choice.GetValue())
)


def on_download_enter(frame, event):
    pass

def on_help_enter(frame, event):
    pass

def on_url_enter(frame, event):
    pass

def on_url_enter_2(frame, event):
    pass

def on_filename_enter(frame, event):
    pass

def on_leave(frame, event):
    global vision
    

def on_thread_enter(frame, event):
    pass

def on_packet_size_enter(frame, event):
    pass



#======================




#=====================



def create_tray_icon(frame):
    if Adminchaker.is_admin():
        icon = wx.Icon('icons/Admin_icon.png', wx.BITMAP_TYPE_PNG)
        tray = wx.adv.TaskBarIcon()
        tray.SetIcon(icon, "Nodanium(管理员)")
    else:
        icon = wx.Icon('icons/ANT_icon.png', wx.BITMAP_TYPE_PNG)
        tray = wx.adv.TaskBarIcon()
        tray.SetIcon(icon, "Nodanium(钒合金)")


    gif_path = "icons/load.gif"

    status_bar = frame.CreateStatusBar(3)
    status_bar.SetStatusWidths([-1, -2, -1])
    status_bar.SetStatusText("Nodanium", 1)
    status_bar.SetStatusText(f"版本: {vision}", 2)


    animation = wx.adv.Animation(gif_path)
    if animation.IsOk():

        animation_ctrl = wx.adv.AnimationCtrl(status_bar, -1, animation)
        animation_ctrl.Play()

        def update_animation_position():
            
            rect = status_bar.GetFieldRect(0)
            animation_ctrl.SetPosition((rect.x, rect.y))
            animation_ctrl.SetSize((rect.width, rect.height))

        update_animation_position()

        def on_size(event):
            update_animation_position()
            event.Skip()

        status_bar.Bind(wx.EVT_SIZE, on_size)


    def create_menu():
        menu = wx.Menu()
        
        
 
        show_item = menu.Append(wx.ID_ANY, "显示窗口")
        hid_item = menu.Append(wx.ID_ANY, "隐藏窗口")
        menu.AppendSeparator()  
        update_item = menu.Append(wx.ID_ANY, "检测更新")
        opt_item = menu.Append(wx.ID_ANY, "首选项")
        menu.AppendSeparator()  
        exit_item = menu.Append(wx.ID_EXIT, "退出")
        
        
        def on_show(event):
            frame.Show()
            frame.Raise()
            frame.Iconize(False)
            
        def on_exit(event):
            tray.Destroy()
            frame.Destroy()
            
        def on_hid(event):
            frame.Hide()
            
        def on_check(event):
            wx.CallAfter(show_update_dialog, "V"+vision)
            
        def opt_check(event):
            options.options(event)
            
        tray.Bind(wx.EVT_MENU, on_show, show_item)
        tray.Bind(wx.EVT_MENU, on_exit, exit_item)
        tray.Bind(wx.EVT_MENU, on_hid, hid_item)
        tray.Bind(wx.EVT_MENU, on_check, update_item)
        tray.Bind(wx.EVT_MENU, opt_check, opt_item)
        
        return menu

    def on_tray_double_click(event):
        frame.Show()
        frame.Raise()
        frame.Iconize(False)
        
    tray.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, on_tray_double_click)
    
 
    def on_right_click(event):
      
        try:
            menu = create_menu()
     
            tray.PopupMenu(menu)
            menu.Destroy()
        except Exception as e:
            print(f"托盘菜单错误: {e}")
            logging.error(f"托盘菜单错误: {e}")
    
    tray.Bind(wx.adv.EVT_TASKBAR_RIGHT_DOWN, on_right_click)

def Window(silence=False):
    global url_text_1, filename_text_1,check
    global url_text, filename_text, thread_choice, packet_size_choice, download_button_2
    global listbook
    global url_text_analyze
    global listbook, panel5 
    global username_ctrl,password_ctrl
    global time_ctrl
    app = wx.App()
    

    if config.get("high_dpi") == True and sys_type == "Windows":
        logging.info('高DPI模式已启用')
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 高DPI！！！！！！太不容易了!!!!
        except Exception as e:
            logging.warning(f"高DPI设置失败: {str(e)}")
    il = wx.ImageList(32, 32)

    bmp1 = wx.Bitmap('icons/path_to_icon1.png')
    bmp2 = wx.Bitmap('icons/path_to_icon2.png')
    bmp3 = wx.Bitmap('icons/path_to_icon3.png')
    bmp4 = wx.Bitmap('icons/path_to_icon4.png')
    bmp5 = wx.Bitmap('icons/path_to_icon5.png')
    bmp6 = wx.Bitmap('icons/path_to_icon6.png')
    bmp7 = wx.Bitmap('icons/path_to_icon7.png')
    bmp8 = wx.Bitmap('icons/home.png') 
    bmp9 = wx.Bitmap('icons/arrow.png')  
    bmp11 = wx.Bitmap('icons/DNS.png')  
    bmp10 = wx.Bitmap('icons/path_to_icon8.png')
    bmp12 = wx.Bitmap('icons/path_to_icon9.png')
    bmp13 = wx.Bitmap('icons/path_to_icon10.png')
    bmp14 = wx.Bitmap('icons/path_to_icon11.png')
    bmp15 = wx.Bitmap('icons/Plugin.png')
  
    il.Add(bmp1)
    il.Add(bmp2)
    il.Add(bmp3)
    il.Add(bmp4)
    il.Add(bmp5)
    il.Add(bmp6)
    il.Add(bmp7)
    il.Add(bmp8)
    il.Add(bmp9)
    il.Add(bmp10)
    il.Add(bmp11)
    il.Add(bmp12)
    il.Add(bmp13)
    il.Add(bmp14)
    il.Add(bmp15)
    icon = wx.Icon('icons/path_to_icon1.png', wx.BITMAP_TYPE_PNG)
    tray = wx.adv.TaskBarIcon()
    tray.SetIcon(icon, "Nodanium")

    global frame 
    if Adminchaker.is_admin(): 
        frame = wx.Frame(None, title="Nodanium(管理员)", size=windowPos) 
    else:
        frame = wx.Frame(None, title="Nodanium", size=windowPos)
    
   

    def on_close(event):
        frame.Hide()
        
    frame.Bind(wx.EVT_CLOSE, on_close)
    
    frame.SetBackgroundColour(wx.Colour(200, 200, 200))
    listbook = wx.Treebook(frame, style=wx.TB_LEFT)
    listbook.SetBackgroundColour(wx.Colour(200, 200, 200))
    listbook.AssignImageList(il)
    listbook.SetFont(wx.Font(ListButtonSize, wx.FONTFAMILY_DEFAULT, 
                  wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, 
                  faceName=fontname))
    

    panel0 = wx.Panel(listbook)

    panel13 = wx.Panel(listbook)
 
    panel3 = wx.Panel(listbook)
    panel4 = wx.Panel(listbook)
    panel5 = wx.Panel(listbook)
    panel6 = wx.Panel(listbook)
    panel7 = wx.Panel(listbook)
   
    panel9 = wx.Panel(listbook)
    panel10 = wx.Panel(listbook)
    panel11 = wx.Panel(listbook)
    panel12 = wx.Panel(listbook)
    panel14 = wx.Panel(listbook)
    panel0.SetBackgroundColour(wx.Colour(255, 255, 255))


    panel3.SetBackgroundColour(wx.Colour(255, 255, 255))
    panel4.SetBackgroundColour(wx.Colour(255, 255, 255))
    panel5.SetBackgroundColour(wx.Colour(255, 255, 255))
    panel6.SetBackgroundColour(wx.Colour(255, 255, 255))
    panel7.SetBackgroundColour(wx.Colour(255, 255, 255))
   
    panel9.SetBackgroundColour(wx.Colour(255, 255, 255))
    panel10.SetBackgroundColour(wx.Colour(255, 255, 255))
    panel11.SetBackgroundColour(wx.Colour(255, 255, 255))
    panel12.SetBackgroundColour(wx.Colour(255, 255, 255))
    panel13.SetBackgroundColour(wx.Colour(255, 255, 255))
    panel14.SetBackgroundColour(wx.Colour(255, 255, 255))


    listbook.AddPage(panel0, "主页", imageId=7)

    listbook.AddPage(panel13, "下载功能", imageId=0)
    

    # 网络工具（父节点）
    listbook.AddPage(wx.Panel(listbook), "网络工具", imageId=2)
    listbook.AddSubPage(panel3, "网页筛选", imageId=2)  # 移除parent参数
    listbook.AddSubPage(panel9, "DNS编辑", imageId=10)  # 移除parent参数
    listbook.AddSubPage(panel10, "Ping", imageId=11)  # 移除parent参数

    # 系统工具（父节点）
    listbook.AddPage(wx.Panel(listbook), "系统工具", imageId=12)
    listbook.AddSubPage(panel12, "端口管理器", imageId=13)  # 移除parent参数
    listbook.AddSubPage(panel11, "文件服务", imageId=12)  # 移除parent参数
    listbook.AddSubPage(panel6, "转发文件", imageId=5)  # 移除parent参数

    # 管理功能（父节点）
    listbook.AddPage(wx.Panel(listbook), "管理功能", imageId=4)
    listbook.AddSubPage(panel13, "下载管理", imageId=5)  # 移除parent参数
    listbook.AddSubPage(panel5, "历史记录", imageId=4)
    listbook.AddSubPage(panel14, "流量转盘", imageId=4)  # 移除parent参数
    try:
        FileShareShell.MainPanel(panel6)
    except Exception as e:
        print(f"文件转发面板加载失败: {e}")
        logging.error(f"文件转发面板加载失败: {e}")
    fileshare_panel = FileServer.FileSharePanel(panel11)  

    PortManager.port_manager_panel(panel12)
    DownloadUI.create_download_panel(panel13)
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(fileshare_panel, 1, wx.EXPAND|wx.ALL, 5)
    panel11.SetSizer(sizer)
    panel11.Layout()


    #插件加载
    listbook.AddPage(wx.Panel(listbook), "插件", imageId=1)
    try:
        if "ChatPort" in plugins:
            listbook.AddSubPage(panel7, "内网通讯", imageId=6)
            ChatPort.init_chat_ui(panel7,frame)

    except Exception as e:
        print(f"没有找到插件: {e}")
        logging.info(f'没有找到插件: {e}')
    try:
   
        for plugin_name, plugin_module in plugins.items():
            if plugin_name == "ChatPort":
                continue 
                
            try:
               
                plugin_panel = wx.Panel(listbook)
                plugin_panel.SetBackgroundColour(wx.Colour(255, 255, 255))
               
                icon_path = os.path.join("Plugins", f"{plugin_name}.png")
                image_id = 14 
                
                
                if os.path.exists(icon_path):
                    try:
                        bitmap = wx.Bitmap(icon_path, wx.BITMAP_TYPE_PNG)
                        if bitmap.IsOk():
                            image_id = listbook.GetImageList().Add(bitmap)
                            
                            logging.info(f'为 {plugin_name} 插件加载了自定义图标')
                    except Exception as e:
                        logging.warning(f'加载 {plugin_name} 插件图标失败: {e}')
                        print(f"加载 {plugin_name} 插件图标失败: {e}")
                
                # 创建页面，使用对应图标
                listbook.AddSubPage(plugin_panel, plugin_name, imageId=image_id)
                
                
                if hasattr(plugin_module, 'MainPanel'):
                    plugin_module.MainPanel(plugin_panel)
                    
                    logging.info(f'成功初始化 {plugin_name} 插件界面')
                else:
                    print(f" {plugin_name} 插件没有 MainPanel 方法")
                    logging.info(f' {plugin_name} 插件没有 MainPanel 方法')
                if hasattr(plugin_module, 'Run'):
                    plugin_module.Run()
                  
                    logging.info(f'{plugin_name} 插件成功执行Run方法')
                else:
                   
                    logging.info(f' {plugin_name} 插件没有 Run 方法')
            except Exception as e:
                print(f"初始化 {plugin_name} 插件界面时出错: {e}")
                logging.error(f'初始化 {plugin_name} 插件界面时出错: {e}')
    except Exception as e:
        print(f"遍历插件时出错: {e}")
        logging.error(f"遍历插件时出错: {e}")
    DNSShower.init_dns_tab(panel9)

    PingPanel(panel10)
    NetworkTraffic.create_panel(panel14)
    

    logging.info('插件已完成加载')


    listbook.AddPage(panel4, "关于...", imageId=3)

    panel3_sizer = wx.BoxSizer(wx.VERTICAL)

 
    title_label = wx.StaticText(panel3, label="从链接中筛选")
    title_label.SetFont(wx.Font(FontSize + 7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=fontname))
    panel3_sizer.Add(title_label, 0, wx.ALL | wx.EXPAND, 10)

    hbox_url = wx.BoxSizer(wx.HORIZONTAL)
    url_label_analyze = wx.StaticText(panel3, label="URL:")
    url_label_analyze.SetFont(wx.Font(FontSize, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=fontname))
    url_text_analyze = wx.TextCtrl(panel3, size=Size)
    url_text_analyze.Bind(wx.EVT_ENTER_WINDOW, lambda event: url3(frame, event))
    url_text_analyze.Bind(wx.EVT_LEAVE_WINDOW, lambda event: on_leave(frame, event))
    hbox_url.Add(url_label_analyze, 0, wx.ALL | wx.CENTER, 5)
    hbox_url.Add(url_text_analyze, 1, wx.ALL | wx.EXPAND, 5)
    panel3_sizer.Add(hbox_url, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

    hbox_timeout = wx.BoxSizer(wx.HORIZONTAL)
    time_ctrl = wx.SpinCtrl(panel3, value="5", min=1, max=120, size=(100, -1))
    hbox_timeout.Add(wx.StaticText(panel3, label="超时时间 (秒):"), 0, wx.ALL | wx.CENTER, 5)
    hbox_timeout.Add(time_ctrl, 0, wx.ALL | wx.CENTER, 5)
    panel3_sizer.Add(hbox_timeout, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

    check = wx.CheckBox(panel3, label="渲染源码（更慢）")
    panel3_sizer.Add(check, 0, wx.ALL | wx.EXPAND, 10)

    analyze_button = wx.Button(panel3, label="分析", size=SizeButton)
    analyze_button.SetFont(wx.Font(FontSize - 4, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=fontname))
    analyze_button.Bind(wx.EVT_ENTER_WINDOW, lambda event: frame.SetStatusText)
    analyze_button.Bind(wx.EVT_BUTTON, on_analyze)

    panel3_sizer.Add(analyze_button, 0, wx.ALL | wx.ALIGN_LEFT, 10)

    
    panel3.SetSizer(panel3_sizer)
    panel4_sizer = wx.BoxSizer(wx.VERTICAL)
    
  
    about_title = wx.StaticText(panel4, label="关于软件")
    about_title.SetFont(wx.Font(FontSize + 5, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, faceName=fontname))
    panel4_sizer.Add(about_title, 0, wx.ALL | wx.ALIGN_LEFT, 10)
    

    about_info = wx.StaticText(panel4, label=f"作者: YJY-yc\n版本: {vision}\n文件保存路径: {dirs}\n默认端口: {str(config.get('default_port', 1524))}")
    about_info.SetFont(wx.Font(FontSize - 2, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=fontname))
    panel4_sizer.Add(about_info, 0, wx.ALL | wx.ALIGN_LEFT, 10)
    

    link_sizer = wx.BoxSizer(wx.HORIZONTAL)
    
    update_link = LinkButton.create_link_button(panel4, "https://yjymain.rth1.xyz/", "icons/link_small.png", "网站链接", (100, 30))
    github_link = LinkButton.create_link_button(panel4, "https://github.com/YJY-yc/Nodanium", "icons/link_small.png", "GitHub链接", (130, 30))
    
    if update_link:
        link_sizer.Add(update_link, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    if github_link:
        link_sizer.Add(github_link, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    
    panel4_sizer.Add(link_sizer, 0, wx.ALL | wx.ALIGN_LEFT, 10)
    

    button_sizer = wx.BoxSizer(wx.HORIZONTAL)
    
    network_info_button = wx.Button(panel4, label="显示网络信息", size=(160, 40))
    network_info_button.SetFont(wx.Font(FontSize - 4, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=fontname))
    button_sizer.Add(network_info_button, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    
    download_button_op = wx.Button(panel4, label="首选项", size=SizeButton)
    download_button_op.SetFont(wx.Font(FontSize - 4, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=fontname))
    button_sizer.Add(download_button_op, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    
    panel4_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_LEFT, 10)
    

    network_info_text = wx.TextCtrl(panel4, size=(-1, 150), style=wx.TE_MULTILINE | wx.TE_READONLY)
    panel4_sizer.Add(network_info_text, 1, wx.ALL | wx.EXPAND, 10)
    
    def on_network_info(event):
        import socket
        import subprocess
        info = ""
        
        hostname = socket.gethostname()
        info += f"主机名: {hostname}\n\n"
        
        addrinfo = socket.getaddrinfo(hostname, None)
        info += "IP地址:\n"
        for addr in addrinfo:
            info += f"  {addr[4][0]}\n"
      
        try:
            sys_type = platform.system()
            if sys_type == "Windows":
                result = subprocess.run(['ipconfig'], capture_output=True, text=True)
            else:
                result = subprocess.run(['ip', 'addr'], capture_output=True, text=True)
            info += "\n网关信息:\n"
            info += result.stdout
        except:
            info += "\n无法获取网关信息"
        
        network_info_text.SetValue(info)

    network_info_button.Bind(wx.EVT_BUTTON, on_network_info)
    
    def on_update_link(event):
        import webbrowser
        webbrowser.open("https://yjymain.rth1.xyz/")
    
    if update_link:
        update_link.Bind(wx.EVT_BUTTON, on_update_link)
    
    download_button_op.Bind(wx.EVT_BUTTON, options.options)
    
 
    panel4.SetSizer(panel4_sizer)

    panel0.SetBackgroundColour(wx.Colour(243, 243, 243))  # VS Code浅色主题背景
    
    main_sizer = wx.BoxSizer(wx.HORIZONTAL)
    
 
    left_panel = wx.Panel(panel0)
    left_panel.SetBackgroundColour(wx.Colour(255, 255, 255))  # 白色卡片
    left_sizer = wx.BoxSizer(wx.VERTICAL)
    
 
    title_text = wx.StaticText(left_panel, label="Nodanium")
    title_text.SetFont(wx.Font(30, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
    title_text.SetForegroundColour(wx.Colour(30, 30, 30))
    left_sizer.Add(title_text, 0, wx.TOP | wx.LEFT | wx.BOTTOM, 20)
    
    
    subtitle_text = wx.StaticText(left_panel, label=f"版本 {vision}")
    subtitle_text.SetForegroundColour(wx.Colour(100, 100, 100))
    subtitle_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    left_sizer.Add(subtitle_text, 0, wx.LEFT | wx.BOTTOM, 30)
    

    update_title = wx.StaticText(left_panel, label="更新信息")
    update_title.SetForegroundColour(wx.Colour(50, 50, 50))
    update_title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_SEMIBOLD))
    left_sizer.Add(update_title, 0, wx.LEFT | wx.BOTTOM, 10)
    

    update_text = wx.TextCtrl(left_panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_NONE)
    update_text.SetBackgroundColour(wx.Colour(255, 255, 255))
    update_text.SetForegroundColour(wx.Colour(50, 50, 50))
    update_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    left_sizer.Add(update_text, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
    
    left_panel.SetSizer(left_sizer)
    main_sizer.Add(left_panel, 1, wx.EXPAND | wx.ALL, 20)
    

    right_panel = wx.Panel(panel0)
    right_panel.SetBackgroundColour(wx.Colour(255, 255, 255))  # 白色卡片
    right_sizer = wx.BoxSizer(wx.VERTICAL)
    

    action_title = wx.StaticText(right_panel, label="开始")
    action_title.SetForegroundColour(wx.Colour(50, 50, 50))
    action_title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_SEMIBOLD))
    right_sizer.Add(action_title, 0, wx.BOTTOM, 15)
    
    def on_new_download(event):
        listbook.ChangeSelection(1)  # 切换到下载功能页
    
    new_download_btn = wx.Button(right_panel, label="   新建下载")
    new_download_btn.SetBitmap(wx.Bitmap("./icons/add.png"), wx.LEFT)
    new_download_btn.SetBackgroundColour(wx.Colour(0, 122, 204))
    new_download_btn.SetForegroundColour(wx.Colour(255, 255, 255))
    new_download_btn.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    new_download_btn.SetMinSize((280, 40))
    new_download_btn.Bind(wx.EVT_BUTTON, on_new_download)
    right_sizer.Add(new_download_btn, 0, wx.BOTTOM, 8)
    
    # 打开保存路径按钮
    def on_open_save_path(event):
        if os.path.isdir(dirs):
            if platform.system() == "Windows":
                os.startfile(dirs)
            else:
                import subprocess
                subprocess.run(["xdg-open", dirs])
    
    open_path_btn = wx.Button(right_panel, label="   打开保存路径")
    open_path_btn.SetBitmap(wx.Bitmap("./icons/view.png"), wx.LEFT)
    open_path_btn.SetBackgroundColour(wx.Colour(230, 230, 230))
    open_path_btn.SetForegroundColour(wx.Colour(50, 50, 50))
    open_path_btn.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    open_path_btn.SetMinSize((280, 40))
    open_path_btn.Bind(wx.EVT_BUTTON, on_open_save_path)
    right_sizer.Add(open_path_btn, 0, wx.BOTTOM, 8)
    

    pref_btn = wx.Button(right_panel, label="   首选项")
    pref_btn.SetBitmap(wx.Bitmap("./icons/init.png"), wx.LEFT)
    pref_btn.SetBackgroundColour(wx.Colour(230, 230, 230))
    pref_btn.SetForegroundColour(wx.Colour(50, 50, 50))
    pref_btn.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    pref_btn.SetMinSize((280, 40))
    pref_btn.Bind(wx.EVT_BUTTON, options.options)
    right_sizer.Add(pref_btn, 0, wx.BOTTOM, 8)
    

    def on_exit(event):
        logging.info('程序退出')
        sys.exit(0)
    
    exit_btn = wx.Button(right_panel, label="   退出程序")
    exit_btn.SetBitmap(wx.Bitmap("./icons/exit.png"), wx.LEFT)
    exit_btn.SetBackgroundColour(wx.Colour(230, 230, 230))
    exit_btn.SetForegroundColour(wx.Colour(50, 50, 50))
    exit_btn.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    exit_btn.SetMinSize((280, 40))
    exit_btn.Bind(wx.EVT_BUTTON, on_exit)
    right_sizer.Add(exit_btn, 0, wx.BOTTOM, 8)
    

    link = LinkButton.create_link_button(right_panel, "https://yjymain.rth1.xyz", "icons/link_small.png", "https://yjymain.rth1.xyz", (280, 40))
    if link:
        link.SetBackgroundColour(wx.Colour(230, 230, 230))
        right_sizer.Add(link, 0, wx.BOTTOM, 8)
    

    separator = wx.StaticLine(right_panel, style=wx.LI_HORIZONTAL)
    separator.SetForegroundColour(wx.Colour(200, 200, 200))
    right_sizer.Add(separator, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 15)
    
    # 最近下载标题
    recent_title = wx.StaticText(right_panel, label="最近下载")
    recent_title.SetForegroundColour(wx.Colour(50, 50, 50))
    recent_title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_SEMIBOLD))
    right_sizer.Add(recent_title, 0, wx.BOTTOM, 10)
    
    # 最近下载列表
    recent_list = wx.ListCtrl(right_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_NONE)
    recent_list.SetBackgroundColour(wx.Colour(255, 255, 255))
    recent_list.SetForegroundColour(wx.Colour(50, 50, 50))
    
    header_attr = wx.ItemAttr()
    header_attr.SetBackgroundColour(wx.Colour(240, 240, 240))
    header_attr.SetTextColour(wx.Colour(100, 100, 100))
    recent_list.SetHeaderAttr(header_attr)
    recent_list.InsertColumn(0, '文件名', width=180)
    recent_list.InsertColumn(1, '日期', width=90)
    

    download_history_file = os.path.join(target_folder, 'History.json')
    if os.path.exists(download_history_file):
        try:
            with open(download_history_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
                if isinstance(history_data, list):
                   
                    recent_items = history_data[-10:][::-1]
                    for item in recent_items:
                        filename = item.get('filename', '未知文件')
                        timestamp = item.get('timestamp', '')
                        recent_list.InsertItem(recent_list.GetItemCount(), filename)
                        recent_list.SetItem(recent_list.GetItemCount() - 1, 1, timestamp)
        except Exception as e:
            logging.error(f"加载下载历史失败: {e}")
    
    right_sizer.Add(recent_list, 1, wx.EXPAND, 0)
    right_panel.SetSizer(right_sizer)
    main_sizer.Add(right_panel, 0, wx.ALL | wx.EXPAND, 20)
    
    panel0.SetSizer(main_sizer)
    

    def fetch_update_info():
        try:
            with open("info.md", "r", encoding='utf-8') as f:
                info = f.read()
            wx.CallAfter(update_text.SetValue, info if info.strip() else "暂无更新信息")
        except FileNotFoundError:
            wx.CallAfter(update_text.SetValue, "错误：info.md文件未找到")
            logging.error("错误：info.md文件未找到")    
        except PermissionError:
            wx.CallAfter(update_text.SetValue, "错误：没有权限读取文件")
            logging.error("错误：没有权限读取文件")
        except Exception as e:
            wx.CallAfter(update_text.SetValue, f"获取信息失败: {str(e)}")
            logging.warning(f"获取信息失败: {str(e)}")
    
    threading.Thread(target=fetch_update_info, daemon=True).start()
    def fetch_update_info():
        try: 
            with open("info.md", "r", encoding='utf-8') as f:
                info = f.read()
            wx.CallAfter(update_text.SetValue, info if info.strip() else "暂无更新信息")
        except FileNotFoundError:
            wx.CallAfter(update_text.SetValue, "错误：info.md文件未找到")
            logging.error("错误：info.md文件未找到")    
        except PermissionError:
            wx.CallAfter(update_text.SetValue, "错误：没有权限读取文件")
            logging.error("错误：没有权限读取文件")
        except Exception as e:
            wx.CallAfter(update_text.SetValue, f"获取信息失败: {str(e)}")
            logging.warning(f"获取信息失败: {str(e)}")


    threading.Thread(target=fetch_update_info, daemon=True).start()

    listbook.ChangeSelection(0)



    def load_history():
        history_path = os.path.join(target_folder, "history.json")
        if os.path.exists(history_path):
            with open(history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    history_list = wx.ListCtrl(panel5, style=wx.LC_REPORT|wx.LC_SINGLE_SEL, pos=(10, 10), size=(windowPos[0]-170,windowPos[1]-130))
    history_list.InsertColumn(0, 'URL', width=300)
    history_list.InsertColumn(1, '文件', width=200)
    history_list.InsertColumn(2, '时间', width=150)
    
   
    def on_right_click(event):
        try:
            menu = wx.Menu()
             
            copy_url_item = menu.Append(wx.ID_ANY, "复制URL")
       
            copy_filename_item = menu.Append(wx.ID_ANY, "复制文件名")
      
            delete_item = menu.Append(wx.ID_ANY, "删除")
            
            def on_copy_url(event):
                selected = history_list.GetFirstSelected()
                if selected != -1:
                    url = history_list.GetItem(selected, 0).GetText()
                    try:
                        if wx.TheClipboard.Open():
                            wx.TheClipboard.SetData(wx.TextDataObject(url))
                            wx.TheClipboard.Close()
                    except Exception as clipboard_error:
                        print(f"剪贴板操作失败: {clipboard_error}")
        
            def on_copy_filename(event):
                selected = history_list.GetFirstSelected()
                if selected != -1:
                    filename = history_list.GetItem(selected, 1).GetText()
                    try:
                        if wx.TheClipboard.Open():
                            wx.TheClipboard.SetData(wx.TextDataObject(filename))
                            wx.TheClipboard.Close()
                    except Exception as clipboard_error:
                        print(f"剪贴板操作失败: {clipboard_error}")
        
            def on_delete(event):
                selected = history_list.GetFirstSelected()
                if selected != -1:
                    history_list.DeleteItem(selected)
                    history = load_history()
                    del history[selected]
                    with open(os.path.join(target_folder, "history.json"), 'w', encoding='utf-8') as f:
                        json.dump(history, f, ensure_ascii=False, indent=4)
        
            history_list.Bind(wx.EVT_MENU, on_copy_url, copy_url_item)
            history_list.Bind(wx.EVT_MENU, on_copy_filename, copy_filename_item)
            history_list.Bind(wx.EVT_MENU, on_delete, delete_item)
            
 
            if hasattr(event, 'GetPosition'):
                pos = event.GetPosition()
            else:
                pos = wx.GetMousePosition()
            

            if sys_type == "Linux":
   
                history_list.PopupMenu(menu, pos)
            else:
                history_list.PopupMenu(menu, pos)
            
            menu.Destroy()
        except Exception as e:
            print(f"右键菜单错误: {e}")
            logging.error(f"右键菜单错误: {e}")
    def on_resize(event):
        new_size = frame.GetSize()
        history_list.SetSize((new_size[0]-170, new_size[1]-130))
        event.Skip()
    
    frame.Bind(wx.EVT_SIZE, on_resize)
    try:
            
        for record in load_history():
            history_list.Append([record['url'], record['filename'], record['time']])
    except Exception as e:
        print(f"加载历史记录时出错: {e}")
        logging.error(f"加载历史记录时出错: {e}")

    if not silence:
        frame.Show()

    tray = create_tray_icon(frame)
    
    if silence:
        # 静默模式：只创建托盘，不显示窗口
        frame.Hide()
    else:
        frame.Show()

    app.MainLoop()

