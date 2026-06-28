import wx
import wx.adv
import psutil
import threading
import time
import sys
import os
import ctypes
from collections import defaultdict
import ctypes
ctypes.windll.shcore.SetProcessDpiAwareness(1) 
# 配置文件
BAN_LIST_FILE = "BanList.txt"

def is_admin():
    """检查是否具有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """以管理员权限重新启动当前脚本"""
    if not is_admin():
        script = os.path.abspath(sys.argv[0])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, script, None, 1)
        sys.exit()

class BanThread(threading.Thread):
    """屏蔽单个进程的线程，持续检测并强制杀死"""
    def __init__(self, process_name, stop_event, kill_counter):
        super().__init__(daemon=True)
        self.process_name = process_name.lower()
        self.stop_event = stop_event
        self.kill_counter = kill_counter  # 共享计数器字典

    def run(self):
        while not self.stop_event.is_set():
            try:
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if proc.info['name'] is not None and proc.info['name'].lower() == self.process_name:
                            proc.kill()  # 强制杀死进程
                            # 增加杀死次数计数
                            self.kill_counter[self.process_name] += 1
                            print(f"Killed {self.process_name} (PID: {proc.info['pid']}, Total: {self.kill_counter[self.process_name]})")
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
            except Exception as e:
                print(f"Error in ban thread for {self.process_name}: {e}")
            time.sleep(0.5)  # 扫描间隔

class BanManager:
    """管理所有屏蔽线程"""
    def __init__(self):
        self.threads = []
        self.stop_events = []
        self.is_banning = False
        self.start_time = None
        self.kill_counter = defaultdict(int)  # 记录每个进程被杀死的次数

    def load_ban_list(self):
        """从BanList.txt读取要屏蔽的进程名（换行分割）"""
        if not os.path.exists(BAN_LIST_FILE):
            return []
        with open(BAN_LIST_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # 去除空行和首尾空白，保留非空行
        processes = [line.strip() for line in lines if line.strip()]
        return processes

    def start_banning(self):
        """启动所有屏蔽线程"""
        if self.is_banning:
            return
        processes = self.load_ban_list()
        if not processes:
            return
        self.is_banning = True
        self.start_time = time.time()
        self.stop_events = [threading.Event() for _ in processes]
        self.threads = []
        # 重置计数器
        self.kill_counter.clear()
        for proc_name, stop_event in zip(processes, self.stop_events):
            t = BanThread(proc_name, stop_event, self.kill_counter)
            t.start()
            self.threads.append(t)

    def stop_banning(self):
        """停止所有屏蔽线程"""
        if not self.is_banning:
            return
        self.is_banning = False
        for event in self.stop_events:
            event.set()
        for t in self.threads:
            t.join(timeout=1.0)
        self.threads.clear()
        self.stop_events.clear()
        self.start_time = None

    def get_kill_counts(self):
        """获取杀死次数统计（只返回次数>0的）"""
        return {proc: count for proc, count in self.kill_counter.items() if count > 0}

class BanPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        # 管理器
        self.ban_manager = BanManager()

        # 创建分割器
        splitter = wx.SplitterWindow(self, style=wx.SP_3D | wx.SP_BORDER)
        
        # 左侧面板 - 目标列表
        left_panel = wx.Panel(splitter)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_label = wx.StaticText(left_panel, label="屏蔽目标列表")
        left_label.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        self.left_list = wx.ListCtrl(left_panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.left_list.AppendColumn("进程名称", width=180)
        left_sizer.Add(left_label, flag=wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, border=5)
        left_sizer.Add(self.left_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        left_panel.SetSizer(left_sizer)
        
        # 右侧面板 - 杀死次数统计
        right_panel = wx.Panel(splitter)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        right_label = wx.StaticText(right_panel, label="杀死次数统计（仅显示已杀死进程）")
        right_label.SetFont(wx.Font(10, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        self.right_list = wx.ListCtrl(right_panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.right_list.AppendColumn("进程名称", width=150)
        self.right_list.AppendColumn("杀死次数", width=100, format=wx.LIST_FORMAT_RIGHT)
        right_sizer.Add(right_label, flag=wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, border=5)
        right_sizer.Add(self.right_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        right_panel.SetSizer(right_sizer)
        
        # 设置分割器（左右比例 1:1）
        splitter.SplitVertically(left_panel, right_panel, 200)
        
        # 按钮和状态区域
        self.toggle_btn = wx.Button(self, label="启动屏蔽")
        self.status_text = wx.StaticText(self, label="状态：待机")
        self.time_text = wx.StaticText(self, label="已屏蔽时间：00:00:00")
        
        # 主布局
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(splitter, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(self.toggle_btn, flag=wx.ALL, border=5)
        btn_sizer.Add(self.status_text, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        btn_sizer.Add(self.time_text, flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        main_sizer.Add(btn_sizer, flag=wx.ALIGN_CENTER)
        
        self.SetSizer(main_sizer)
        
        # 设置默认背景色
        self.normal_color = wx.Colour(255, 255, 255)  # 白色
        self.banning_color = wx.Colour(144, 238, 144)  # 淡绿色
        
        # 绑定事件
        self.toggle_btn.Bind(wx.EVT_BUTTON, self.on_toggle)
        
        # 加载屏蔽列表显示
        self.load_and_display_list()
        
        # 启动时自动开始屏蔽
        wx.CallAfter(self.auto_start)
        
        # 计时器更新UI
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_display, self.timer)
        self.timer.Start(500)  # 每0.5秒更新一次

    def set_ui_color(self, is_banning):
        """设置界面颜色"""
        if is_banning:
            color = self.banning_color
        else:
            color = self.normal_color
        
        # 设置面板背景色
        self.SetBackgroundColour(color)
        
        # 设置分割器中两个面板的背景色
        if hasattr(self, 'left_list'):
            # 设置列表控件的背景色
            self.left_list.SetBackgroundColour(color)
            self.right_list.SetBackgroundColour(color)
        
        self.Refresh()

    def load_and_display_list(self):
        """加载进程列表到左侧列表控件"""
        processes = self.ban_manager.load_ban_list()
        self.left_list.DeleteAllItems()
        for idx, proc in enumerate(processes):
            self.left_list.InsertItem(idx, proc)

    def update_kill_count_display(self):
        """更新右侧杀死次数显示"""
        kill_counts = self.ban_manager.get_kill_counts()
        
        # 清空并重新显示
        self.right_list.DeleteAllItems()
        
        if kill_counts:
            for idx, (proc_name, count) in enumerate(kill_counts.items()):
                self.right_list.InsertItem(idx, proc_name)
                self.right_list.SetItem(idx, 1, str(count))

    def auto_start(self):
        """打开窗口时自动启动屏蔽"""
        self.start_banning()

    def start_banning(self):
        """启动屏蔽，变更状态"""
        if self.ban_manager.is_banning:
            return
        self.ban_manager.start_banning()
        self.toggle_btn.SetLabel("停止屏蔽")
        self.status_text.SetLabel("状态：屏蔽中")
        self.set_ui_color(True)

    def stop_banning(self):
        """停止屏蔽，变更状态"""
        if not self.ban_manager.is_banning:
            return
        self.ban_manager.stop_banning()
        self.toggle_btn.SetLabel("启动屏蔽")
        self.status_text.SetLabel("状态：待机")
        self.set_ui_color(False)
        
        # 停止后清空杀死次数显示
        self.right_list.DeleteAllItems()

    def on_toggle(self, event):
        """按钮点击：启动/停止切换"""
        if self.ban_manager.is_banning:
            self.stop_banning()
        else:
            self.start_banning()

    def update_display(self, event):
        """更新显示：时间和杀死次数"""
        # 更新时间显示
        if self.ban_manager.is_banning and self.ban_manager.start_time is not None:
            elapsed = int(time.time() - self.ban_manager.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            time_str = f"已屏蔽时间：{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.time_text.SetLabel(time_str)
        else:
            self.time_text.SetLabel("已屏蔽时间：00:00:00")
        
        # 更新杀死次数显示
        self.update_kill_count_display()

class BanFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="智子屏蔽器", size=(600, 400))
        panel = BanPanel(self)
        self.Centre()

class BanApp(wx.App):
    def OnInit(self):
        frame = BanFrame()
        frame.Show()
        return True

if __name__ == "__main__":
    # 获取管理员权限
    if not is_admin():
        run_as_admin()
    else:
        app = BanApp(False)
        app.MainLoop()