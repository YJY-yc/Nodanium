# Copyright (c) 2023-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import wx
import time
import Adminchaker
import sys
import logging
import tempfile
import psutil
import platform 
sys_type = platform.system()



#=启动参数=
def print_help():
    help_text = """Nodanium

选项:
  -v, --version           显示版本信息
  -h, --help              显示此帮助信息
  -c, --clear             清除数据目录
  -s, --silent            静默模式启动
  --download              命令行下载模式
    --url=<链接>          下载链接
    --filename=<文件名>    保存文件名
    --path=<保存路径>      文件保存路径
    --job=<线程数>         下载线程数（默认16）
    --size=<包大小(B)>        每个线程下载的包大小（默认1MB）
    --header=<自定义头>    自定义HTTP头（默认空）
    --cache=<缓存时间>     缓存时间（默认10MB）
    --run=<自动运行>       是否运行（默认None）
    注意: --download 模式下，--url 和 --filename 为必填参数
  --old_download              命令行下载模式(旧版)
    --url=<链接>          下载链接
    --filename=<文件名>    保存文件名
    --path=<保存路径>      文件保存路径
    --job=<线程数>         下载线程数（默认16）

    注意: --old_download 模式下，--url 和 --filename 为必填参数  
    
    """

    print(help_text)

def parse_args(args):
    parsed = {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith('--'):
            if '=' in arg:
                key, value = arg.split('=', 1)
                parsed[key[2:]] = value
            else:
                parsed[arg[2:]] = True
        elif arg.startswith('-'):
            parsed[arg[1:]] = True
        i += 1
    return parsed

if len(sys.argv) > 1:
    args = sys.argv[1:]
    parsed_args = parse_args(args)
    
    if "v" in parsed_args or "version" in parsed_args:
        print("Nodanium version 3.5.2.8\nCopyright (c) 2023-2026 YUJY(YJY-yc)")
        sys.exit(0)
    elif "h" in parsed_args or "help" in parsed_args:
        print_help()
        sys.exit(0)
    elif "c" in parsed_args or "clear" in parsed_args:
        print("确定要清除数据目录吗？(y/n)")
        choice = input()
        if choice.lower() == "y":
            if sys_type == "Windows":
                roaming_path = os.getenv('APPDATA') + ''
                target_folder = os.path.join(roaming_path, "Nodanium")
            elif sys_type == "Linux":
                home_path = os.path.expanduser("~")
                target_folder = os.path.join(home_path, ".Nodanium")
            try:
                if os.path.exists(target_folder):
                    import shutil
                    shutil.rmtree(target_folder)
                    print("数据目录已清除")
                else:
                    print("数据目录不存在")
            except Exception as e:
                print(f"清除数据目录失败: {str(e)}")
        sys.exit(0)
    elif "download" in parsed_args:
        import NewDownloadCore
        
        if "url" not in parsed_args:
            print("错误: --url 参数为必填项")
            print("使用 --help 查看帮助")
            sys.exit(1)
        if "filename" not in parsed_args:
            print("错误: --filename 参数为必填项")
            print("使用 --help 查看帮助")
            sys.exit(1)
        
        url = parsed_args["url"]
        filename = parsed_args["filename"]
        default_path = os.path.join(os.path.expanduser("~"), "Downloads")
        if sys_type == "Windows":
            default_path = "D:/Downloads/"
        save_path = parsed_args.get("path", default_path)
        job_count = int(parsed_args.get("job", 16))
        Size = int(parsed_args.get("size", 1024*1024))
        Header = parsed_args.get("header", "")
        Cache=int(parsed_args.get("cache", 10))
        Run=parsed_args.get("run", None)
        NewDownloadCore.Download(url,save_path,  filename, job_count,Size ,Header,Cache,Run,True)
        sys.exit(0)
    elif "old_download" in parsed_args:
        import DownloadCore
        
        if "url" not in parsed_args:
            print("错误: --url 参数为必填项")
            print("使用 --help 查看帮助")
            sys.exit(1)
        if "filename" not in parsed_args:
            print("错误: --filename 参数为必填项")
            print("使用 --help 查看帮助")
            sys.exit(1)
        
        url = parsed_args["url"]
        filename = parsed_args["filename"]
        default_path = os.path.join(os.path.expanduser("~"), "Downloads")
        if sys_type == "Windows":
            default_path = "D:/Downloads/"
        save_path = parsed_args.get("path", default_path)
        job_count = int(parsed_args.get("job", 16))
        
        DownloadCore.download_window(url, filename, save_path, job_count, True)
        sys.exit(0)
    elif "s" in parsed_args or "silent" in parsed_args:
        import Window
        Window.Window(silence=True)
        sys.exit(0)
else:
    print("未传入任何启动参数，使用 --help 查看帮助信息")



# 数据目录配置
target_folder = ""

if sys_type == "Windows":
    from winotify import Notification
    roaming_path = os.getenv('APPDATA') + ''
    target_folder = os.path.join(roaming_path, "Nodanium")
    print("当前是 Windows 系统")
elif sys_type == "Linux":
    print("当前是 Linux 系统")
  
    home_path = os.path.expanduser("~")
    target_folder = os.path.join(home_path, ".Nodanium")



try:
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
    logs_folder = os.path.join(target_folder, "logs")
    if not os.path.exists(logs_folder):
        os.makedirs(logs_folder)
except Exception as e:
    app = wx.App(False)
    wx.MessageBox(f"无法创建日志目录: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
    sys.exit(1)
def show_notification(title, message):
    if sys_type == "Windows":
        toast = Notification(app_id="Nodanium",
                            title=title,
                            msg=message)
        toast.show()
    elif sys_type == "Linux":
        try:
            import subprocess
            subprocess.run(["notify-send", title, message], check=True)
        except Exception as e:
            logging.warning(f"发送通知失败: {str(e)}")
    elif sys_type == "Darwin":
        try:
            import subprocess
            subprocess.run(["osascript", "-e", f'display notification "{message}" with title "{title}"'], check=True)
        except Exception as e:
            logging.warning(f"发送通知失败: {str(e)}")


timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
logging.basicConfig(
    filename=os.path.join(target_folder, "logs", f'{timestamp}.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)


if not os.path.exists(target_folder):
    os.makedirs(target_folder)
    logs_folder = os.path.join(target_folder, "logs")
    if not os.path.exists(logs_folder):
        os.makedirs(logs_folder)
        show_notification("初始化完成\n请在首选项中设置请求头", f"数据目录已创建：{target_folder}")

# 创建默认下载目录配置
dir_file = os.path.join(target_folder, "dir.txt")
if not os.path.exists(dir_file):
    default_download_dir = ""
    if sys_type == "Windows":
        default_download_dir = "D:/downloads/"
    else:
        default_download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    try:
        with open(dir_file, "w") as f:
            f.write(default_download_dir)
    except Exception as e:
        logging.warning(f"创建目录配置失败: {str(e)}")


head_file = os.path.join(target_folder, "Head.ANT")
default_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
if not os.path.exists(head_file):
    with open(head_file, 'w', encoding='utf-8') as f:
        f.write(default_user_agent)

logging.info('数据目录已创建')
print(target_folder)





if Adminchaker.is_admin():
    admin_title = "已获得管理员权限"
    admin_msg = "程序正在以管理员权限运行"
    if sys_type == "Windows":
        toast = Notification(
            app_id="Advanced Network Toolset",
            title=admin_title,
            msg=admin_msg
        )
        toast.show()
    elif sys_type == "Linux":
        show_notification(admin_title, admin_msg)
    elif sys_type == "Darwin":
        show_notification(admin_title, admin_msg)
    logging.info('已获得管理员权限')

def get_lockfile_path():
  
    return os.path.join(tempfile.gettempdir(), f".{os.path.basename(sys.argv[0])}.lock")

def acquire_lock(lockfile):
    try:
      
        fd = os.open(lockfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
   
        with os.fdopen(fd, 'w') as f:
            f.write(f"{os.getpid()}\n{sys.executable}\n{os.getcwd()}")
        return True, None
    except OSError as e:
        if e.errno == 17: 
            logging.info('锁文件已存在')
            return False, "锁文件已存在"
        logging.info(f"无法创建锁文件: {str(e)}")
        return False, f"无法创建锁文件: {str(e)}"

def check_existing_instance(lockfile):
    try:
        with open(lockfile, 'r') as f:
            lines = f.read().splitlines()
            if len(lines) >= 1:
                pid = int(lines[0])
                try:
                    process = psutil.Process(pid)
                    if process.is_running():
                        return True, pid, process
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        return False, None, None
    except Exception:
        return False, None, None

def show_instance_warning(lockfile, pid, process):
    app = wx.App(False)
    dialog = wx.Dialog(None, title="程序已运行", size=(750, 300))
    logging.info('检测到程序已在运行中')
    info = (
        f"检测到程序已在运行中！你可以通过检查托盘的方式找到该实例。\n\n进程ID: {pid}\n运行路径: {process.exe()}\n启动时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(process.create_time()))}"
    )
    
    panel = wx.Panel(dialog)
    vbox = wx.BoxSizer(wx.VERTICAL)
    
    st_message = wx.StaticText(panel, label=info)
    st_message.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    vbox.Add(st_message, flag=wx.ALL | wx.EXPAND, border=15)
    
    btn_kill = wx.Button(panel, label="终止前一个实例(&K)", id=wx.ID_YES)
    btn_ignore = wx.Button(panel, label="忽略并继续(&I)", id=wx.ID_IGNORE)
    btn_exit = wx.Button(panel, label="退出(&Q)", id=wx.ID_NO)

    message = wx.StaticText(panel, label="点击\"终止前一个实例\"终止前一个实例,点击\"忽略并继续\"将继续运行当前实例")
    
    hbox = wx.BoxSizer(wx.HORIZONTAL)
    hbox.Add(btn_kill, flag=wx.RIGHT, border=10)
    hbox.Add(btn_ignore, flag=wx.RIGHT, border=10)
    hbox.Add(btn_exit)
    vbox.Add(hbox, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=15)
    vbox.Add(message, flag=wx.ALL | wx.EXPAND, border=15)
    panel.SetSizer(vbox)
 
    def on_kill(event):
        try:
            process.terminate()
            process.wait(timeout=3)
            os.remove(lockfile)
            dialog.EndModal(wx.ID_YES)
        except Exception as e:
            wx.MessageBox(f"无法终止进程: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            logging.info('终止进程失败')
            dialog.EndModal(wx.ID_CANCEL)
    
    def on_ignore(event):
        dialog.EndModal(wx.ID_IGNORE)
    
    def on_exit(event):
        dialog.EndModal(wx.ID_NO)
    
    btn_kill.Bind(wx.EVT_BUTTON, on_kill)
    btn_ignore.Bind(wx.EVT_BUTTON, on_ignore)
    btn_exit.Bind(wx.EVT_BUTTON, on_exit)
    
    result = dialog.ShowModal()
    dialog.Destroy()
    return result

def cleanup_lock(lockfile):
    try:
        if os.path.exists(lockfile):
            with open(lockfile, 'r') as f:
                if f.readline().strip() == str(os.getpid()):
                    os.remove(lockfile)
    except Exception:
        pass


lockfile = get_lockfile_path()


acquired, error = acquire_lock(lockfile)
if not acquired:

    is_running, pid, process = check_existing_instance(lockfile)
    if is_running:
   
        choice = show_instance_warning(lockfile, pid, process)
        if choice == wx.ID_YES: 
            acquired, error = acquire_lock(lockfile)
            if not acquired:
                wx.MessageBox("无法获取锁，请重试", "错误", wx.OK | wx.ICON_ERROR)
                sys.exit(1)
        elif choice == wx.ID_IGNORE:  
            pass  
        else:  
            sys.exit(0)
    else:
   
        try:
            os.remove(lockfile)
            acquired, error = acquire_lock(lockfile)
            if not acquired:
                wx.MessageBox(f"无法获取锁: {error}", "错误", wx.OK | wx.ICON_ERROR)
                sys.exit(1)
        except Exception as e:
            pass


try:
    logging.info('启动窗口模块')
    import Window
    Window.Window()
except Exception as e:
    print(f"导入失败:{str(e)}")
    try:
        app = wx.GetApp()
        if app is None:
            app = wx.App(False)
    except:
        app = wx.App(False)
    wx.MessageBox(f"启动程序失败\n你的设备可以运行本程序，需要调试以解决此问题\n使用CLI参赛-c清除缓存\n导入窗口模块失败:\n{str(e)}", "错误", wx.OK | wx.ICON_ERROR)
    logging.error(f'导入窗口模块失败{str(e)}')
logging.info('主循环已结束')