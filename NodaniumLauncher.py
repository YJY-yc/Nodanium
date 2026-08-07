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
  -r, --resume=<路径>     从 NDF/JSON 文件恢复下载
    --path=<保存路径>      覆盖保存目录（可选）
    --job=<线程数>         覆盖线程数（可选，0使用原设置）
    --cache=<缓存MB>      覆盖缓存大小（可选，0使用默认32MB）
    --header=<JSON头>     覆盖HTTP请求头（可选）
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


def _show_resume_dialog(ndf_path, parsed_args):
    """恢复下载对话框"""
    import tempfile
    import zipfile
    import json

    app = wx.GetApp()
    if app is None:
        app = wx.App(False)

    progress_data = {}
    extracted_dir = ""
    is_ndf = ndf_path.lower().endswith('.ndf')

    if is_ndf:
        if not os.path.exists(ndf_path):
            wx.MessageBox(f"NDF 文件不存在: {ndf_path}", "错误", wx.OK | wx.ICON_ERROR)
            return False
        extracted_dir = tempfile.mkdtemp(prefix="ndf_resume_")
        try:
            with zipfile.ZipFile(ndf_path, 'r') as zf:
                zf.extractall(extracted_dir)
            json_path = os.path.join(extracted_dir, "download_progress.json")
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
        except Exception as e:
            wx.MessageBox(f"NDF 文件解析失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            import shutil
            shutil.rmtree(extracted_dir, ignore_errors=True)
            return False
    elif ndf_path.lower().endswith('.json'):
        if not os.path.exists(ndf_path):
            wx.MessageBox(f"进度文件不存在: {ndf_path}", "错误", wx.OK | wx.ICON_ERROR)
            return False
        try:
            with open(ndf_path, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
        except Exception as e:
            wx.MessageBox(f"进度文件解析失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            return False
    else:
        wx.MessageBox("无效的文件类型，请使用 .ndf 或 .json 文件", "错误", wx.OK | wx.ICON_ERROR)
        return False

    if not progress_data or "url" not in progress_data:
        wx.MessageBox("进度文件损坏或缺少必要信息", "错误", wx.OK | wx.ICON_ERROR)
        if extracted_dir and os.path.exists(extracted_dir):
            import shutil
            shutil.rmtree(extracted_dir, ignore_errors=True)
        return False

    filename = progress_data.get("filename", "未知")
    url = progress_data.get("url", "")
    original_save_path = progress_data.get("save_path", "")
    file_total_size = progress_data.get("file_total_size", 0)
    total_downloaded = progress_data.get("total_downloaded", 0)
    jobs = progress_data.get("jobs", 8)
    chunk_size = progress_data.get("chunk_size", 10 * 1024 * 1024)

    completed_pct = (total_downloaded / file_total_size * 100) if file_total_size > 0 else 0

    dlg = wx.Dialog(None, title="恢复下载", size=(600, 560))

    main_sizer = wx.BoxSizer(wx.VERTICAL)

    info_box = wx.StaticBoxSizer(wx.VERTICAL, dlg, "下载信息")
    info_grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=8)
    info_grid.AddGrowableCol(1, proportion=1)

    info_grid.Add(wx.StaticText(dlg, label="文件名:"), flag=wx.ALIGN_RIGHT)
    info_grid.Add(wx.StaticText(dlg, label=filename), flag=wx.EXPAND, proportion=1)

    info_grid.Add(wx.StaticText(dlg, label="下载链接:"), flag=wx.ALIGN_RIGHT)
    url_ctrl = wx.TextCtrl(dlg, value=url, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.HSCROLL)
    url_ctrl.SetFont(wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
    url_ctrl.SetMinSize((-1, 48))
    info_grid.Add(url_ctrl, flag=wx.EXPAND, proportion=1)

    size_str = f"{file_total_size / 1024 / 1024:.2f} MiB" if file_total_size > 0 else "未知"
    info_grid.Add(wx.StaticText(dlg, label="文件大小:"), flag=wx.ALIGN_RIGHT)
    info_grid.Add(wx.StaticText(dlg, label=size_str), flag=wx.EXPAND, proportion=1)

    info_grid.Add(wx.StaticText(dlg, label="已下载:"), flag=wx.ALIGN_RIGHT)
    info_grid.Add(wx.StaticText(dlg, label=f"{completed_pct:.1f}%"), flag=wx.EXPAND, proportion=1)

    info_grid.Add(wx.StaticText(dlg, label="原始线程:"), flag=wx.ALIGN_RIGHT)
    info_grid.Add(wx.StaticText(dlg, label=str(jobs)), flag=wx.EXPAND, proportion=1)

    info_box.Add(info_grid, flag=wx.EXPAND | wx.ALL, border=10)
    main_sizer.Add(info_box, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

    param_box = wx.StaticBoxSizer(wx.VERTICAL, dlg, "参数")
    param_grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=8)
    param_grid.AddGrowableCol(1, proportion=1)

    param_grid.Add(wx.StaticText(dlg, label="保存路径:"), flag=wx.ALIGN_RIGHT)
    path_sizer = wx.BoxSizer(wx.HORIZONTAL)
    default_save = parsed_args.get("path", "") or original_save_path or os.path.dirname(os.path.abspath(ndf_path))
    txt_path = wx.TextCtrl(dlg, value=default_save, size=(-1, -1))
    btn_browse = wx.Button(dlg, label="浏览...", size=(-1, -1))
    path_sizer.Add(txt_path, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=5)
    path_sizer.Add(btn_browse, flag=wx.ALIGN_CENTER_VERTICAL)
    param_grid.Add(path_sizer, flag=wx.EXPAND, proportion=1)

    param_grid.Add(wx.StaticText(dlg, label="线程数:"), flag=wx.ALIGN_RIGHT)
    txt_job = wx.TextCtrl(dlg, value=parsed_args.get("job", "8"), size=(-1, -1))
    param_grid.Add(txt_job, flag=wx.EXPAND, proportion=1)

    param_grid.Add(wx.StaticText(dlg, label="缓存(MB):"), flag=wx.ALIGN_RIGHT)
    txt_cache = wx.TextCtrl(dlg, value=parsed_args.get("cache", "10"), size=(-1, -1))
    param_grid.Add(txt_cache, flag=wx.EXPAND, proportion=1)

    param_grid.Add(wx.StaticText(dlg, label="HTTP头(JSON):"), flag=wx.ALIGN_RIGHT)
    txt_header = wx.TextCtrl(dlg, value=parsed_args.get("header", ""), size=(-1, -1))
    param_grid.Add(txt_header, flag=wx.EXPAND, proportion=1)

    param_box.Add(param_grid, flag=wx.EXPAND | wx.ALL, border=10)
    main_sizer.Add(param_box, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    btn_start = wx.Button(dlg, label="开始恢复(&S)")
    btn_cancel = wx.Button(dlg, label="取消(&C)")
    btn_sizer.Add(btn_start, flag=wx.RIGHT, border=10)
    btn_sizer.Add(btn_cancel)
    main_sizer.Add(btn_sizer, flag=wx.ALIGN_CENTER | wx.ALL, border=15)

    dlg.SetSizer(main_sizer)
    dlg.Center()

    def on_browse(event):
        dlg_browse = wx.DirDialog(dlg, "选择保存目录", txt_path.GetValue(), style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dlg_browse.ShowModal() == wx.ID_OK:
            txt_path.SetValue(dlg_browse.GetPath())
        dlg_browse.Destroy()

    btn_browse.Bind(wx.EVT_BUTTON, on_browse)

    result = {"start": False, "params": {}}

    def on_start(event):
        save_path = txt_path.GetValue().strip()
        job_val = int(txt_job.GetValue().strip() or "0")
        cache_val = float(txt_cache.GetValue().strip() or "0")
        header_str = txt_header.GetValue().strip()

        if not save_path:
            wx.MessageBox("保存路径不能为空", "错误", wx.OK | wx.ICON_ERROR)
            return

        headers = {}
        if header_str:
            try:
                headers = json.loads(header_str)
            except Exception:
                headers = {header_str: "true"}

        result["start"] = True
        result["params"] = {
            "SavePath": save_path,
            "Jobs": job_val,
            "Cache": cache_val,
            "Head": headers if headers else None,
        }
        dlg.EndModal(wx.ID_OK)

    def on_cancel(event):
        result["start"] = False
        dlg.EndModal(wx.ID_CANCEL)

    btn_start.Bind(wx.EVT_BUTTON, on_start)
    btn_cancel.Bind(wx.EVT_BUTTON, on_cancel)

    dlg.ShowModal()
    dlg.Destroy()

    if not result["start"]:
        if extracted_dir and os.path.exists(extracted_dir):
            import shutil
            shutil.rmtree(extracted_dir, ignore_errors=True)
        return False

    import NewDownloadCore
    NewDownloadCore.ResumeDownload(
        ResumePath=ndf_path,
        SavePath=result["params"]["SavePath"],
        InputPath=result["params"]["SavePath"],
        Jobs=result["params"]["Jobs"],
        Cache=result["params"]["Cache"],
        Head=result["params"]["Head"],
        uuid=parsed_args.get("uuid", ""),
        SpeedUnit=parsed_args.get("speed_unit", "MB/s"),
    )
    return True

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
        elif arg.startswith('-') and len(arg) > 1:
            if i + 1 < len(args) and not args[i + 1].startswith('-'):
                parsed[arg[1:]] = args[i + 1]
                i += 1
            else:
                parsed[arg[1:]] = True
        i += 1
    return parsed

if len(sys.argv) > 1:
    args = sys.argv[1:]
    parsed_args = parse_args(args)
    
    
    positional_files = [a for a in args if not a.startswith('-')]
    ndf_file_arg = None
    for pf in positional_files:
        if pf.lower().endswith('.ndf') or pf.lower().endswith('.json'):
            ndf_file_arg = pf
            break
    
    if ndf_file_arg and "r" not in parsed_args and "resume" not in parsed_args:
        parsed_args["resume"] = ndf_file_arg
    
    if "v" in parsed_args or "version" in parsed_args:
        print("Nodanium version 3.6.0.0\nCopyright (c) 2023-2026 YUJY(YJY-yc)")
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
    elif "r" in parsed_args or "resume" in parsed_args:
        resume_path = parsed_args.get("r") or parsed_args.get("resume")
        if not resume_path or resume_path is True:
            print("错误: --resume 需要指定文件路径")
            print("使用 --help 查看帮助")
            sys.exit(1)
        success = _show_resume_dialog(resume_path, parsed_args)
        sys.exit(0 if success else 1)
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