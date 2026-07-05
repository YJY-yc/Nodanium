# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import wx
import psutil
import time

REFRESH_INTERVAL = 0.2  # 刷新间隔（秒）
ONE_ROUND_BYTES = 50 * 1024 * 1024  # 1转对应50MB流量
INDICATOR_WIDTH = 10  # 绿色指示块的宽度

# 全局变量
traffic_type = "上传和下载"  # 默认流量类型
mini_window = None  # 迷你窗口实例

class SmoothIndicatorPanel(wx.Panel):
    """自定义平滑指示块面板 - 支持60fps平滑动画"""
    def __init__(self, parent):
        super().__init__(parent)
        self.target_position = 0  # 目标位置百分比 0-100
        self.current_position = 0  # 当前显示位置
        self.indicator_width = INDICATOR_WIDTH
        self.animation_start_time = None
        self.start_position = 0
        self.is_animating = False
        

        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        

        self.SetBackgroundColour(wx.Colour(200, 200, 200))
        

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_animation_tick, self.timer)
        self.timer.Start(16)  # 60 FPS
    def stop_timer(self):
        """停止动画定时器"""
        if hasattr(self, 'timer') and self.timer.IsRunning():
            self.timer.Stop()
    def on_paint(self, event):
        """绘制指示块"""
        dc = wx.PaintDC(self)
        width, height = self.GetSize()
        
        dc.SetBrush(wx.Brush(wx.Colour(200, 200, 200)))
        dc.SetPen(wx.Pen(wx.Colour(200, 200, 200)))
        dc.DrawRectangle(0, 0, width, height)
        
      
        dc.SetPen(wx.Pen(wx.Colour(150, 150, 150), 1))
        dc.DrawRectangle(0, 0, width-1, height-1)
        
    
        max_pos = width - self.indicator_width
        x_pos = int((self.current_position / 100.0) * max_pos)
        

        dc.SetBrush(wx.Brush(wx.Colour(0, 200, 0)))
        dc.SetPen(wx.Pen(wx.Colour(0, 150, 0), 1))
        dc.DrawRectangle(x_pos, 0, self.indicator_width, height)
        
 
        dc.SetPen(wx.Pen(wx.Colour(0, 255, 0), 1))
        dc.DrawLine(x_pos, 0, x_pos + self.indicator_width, 0)  # 上边框
        dc.DrawLine(x_pos, 0, x_pos, height)  # 左边框
        
        dc.SetPen(wx.Pen(wx.Colour(0, 150, 0), 1))
        dc.DrawLine(x_pos + self.indicator_width, 0, x_pos + self.indicator_width, height)  # 右边框
        dc.DrawLine(x_pos, height-1, x_pos + self.indicator_width, height-1)  # 下边框
        
    def on_size(self, event):
        """面板大小改变时刷新"""
        self.Refresh()
        event.Skip()
        
    def set_position(self, position, animate=True):
        """设置指示块位置（0-100）"""
        position = max(0, min(100, position))
        
    
        if position < 5 and self.target_position > 95:

            self.target_position = position
            self.current_position = position
            self.is_animating = False
            self.Refresh()
            return
            
        self.target_position = position
        
  
        if animate and abs(self.target_position - self.current_position) > 0.5:
            self.start_animation()
        elif not animate:
            self.current_position = position
            self.Refresh()
    
    def start_animation(self):
        """开始动画"""
        self.start_position = self.current_position
        self.animation_start_time = time.time()
        self.is_animating = True
    
    def on_animation_tick(self, event):
        """动画定时器回调 - 60fps"""
        if not self.is_animating:
            return
            
        current_time = time.time()
        elapsed = current_time - self.animation_start_time
        
        # 动画持续时间：300ms
        animation_duration = 0.3
        
        if elapsed >= animation_duration:
            # 动画结束
            self.current_position = self.target_position
            self.is_animating = False
        else:
    
            progress = elapsed / animation_duration
         
            t = 1 - (1 - progress) ** 3
            
           
            self.current_position = self.start_position + (
                self.target_position - self.start_position) * t
        
        self.Refresh()

  
    
    def on_mouse_move(self, event):
        """鼠标移动事件 - 拖动窗口"""
        if event.Dragging() and event.LeftIsDown() and self.drag_pos is not None:
            new_pos = event.GetEventObject().ClientToScreen(event.GetPosition())
            delta = wx.Point(new_pos.x - self.drag_pos.x, new_pos.y - self.drag_pos.y)
            self.Move(self.window_pos + delta)
    
    def on_close(self, event):
        """关闭迷你窗口"""
        self.Close()
    
    def update_display(self):
        """更新迷你窗口显示"""
        # 获取流量数据
        net_io = psutil.net_io_counters()
        total_sent = net_io.bytes_sent
        total_recv = net_io.bytes_recv
        
        # 计算总流量
        total_bytes = total_sent + total_recv
        total_gb = total_bytes / (1024 ** 3)
        
        # 更新数显
        int_part, dec_part = self.format_gb_for_display(total_gb)
        
        # 整数部分最多显示5位
        if len(int_part) > 5:
            int_part = int_part[-5:]
        
        # 确保整数部分有5位
        int_part = int_part.zfill(5)
        
        # 更新数字显示
        for i in range(5):
            self.mini_digits[i].SetLabel(int_part[i])
        
        # 更新小数部分
        self.mini_digits[5].SetLabel(dec_part[0] if len(dec_part) > 0 else "0")
        self.mini_digits[6].SetLabel(dec_part[1] if len(dec_part) > 1 else "0")
        
        # 更新转盘位置
        remainder = total_bytes % ONE_ROUND_BYTES
        progress = (remainder / ONE_ROUND_BYTES) * 100
        self.mini_indicator.set_position(progress, animate=True)
        
        # 更新圈数显示
        total_rounds = total_bytes // ONE_ROUND_BYTES
        self.mini_rounds_label.SetLabel(f"圈:{total_rounds}")
        
        # 更新速率显示（简化计算）
        if not hasattr(self, 'last_update_time'):
            self.last_update_time = time.time()
            self.last_total_bytes = total_bytes
            speed_mb = 0
        else:
            current_time = time.time()
            time_diff = current_time - self.last_update_time
            if time_diff > 0.1:
                speed = (total_bytes - self.last_total_bytes) / time_diff
                speed_mb = speed / (1024 * 1024)
                self.last_update_time = current_time
                self.last_total_bytes = total_bytes
            else:
                speed_mb = 0
        
        self.mini_speed_label.SetLabel(f"{speed_mb:.1f} MB/s")
        
        # 更新速率颜色
        if speed_mb < 1:
            self.mini_speed_label.SetForegroundColour(wx.Colour(0, 130, 0))
        elif speed_mb < 10:
            self.mini_speed_label.SetForegroundColour(wx.Colour(0, 180, 0))
        else:
            self.mini_speed_label.SetForegroundColour(wx.Colour(220, 0, 0))
        
        # 递归调用
        wx.CallLater(500, self.update_display)
    
    def format_gb_for_display(self, value_gb):
        """格式化GB显示"""
        formatted = f"{value_gb:,.2f}"
        cleaned = formatted.replace(',', '')
        
        if '.' in cleaned:
            int_part, dec_part = cleaned.split('.')
        else:
            int_part = cleaned
            dec_part = "00"
        
        dec_part = dec_part.ljust(2, '0')[:2]
        
        return int_part, dec_part

def get_system_total_traffic():
    """直接从系统获取总流量数据（从系统启动开始）"""
    net_io = psutil.net_io_counters()
    return {
        'total_sent': net_io.bytes_sent,      # 系统启动以来总发送量
        'total_recv': net_io.bytes_recv,      # 系统启动以来总接收量
        'sent_speed': 0,                      # 实时速率需要单独计算
        'recv_speed': 0
    }

def calculate_speed():
    """计算实时速率（需要上次的数据）"""

    if not hasattr(calculate_speed, 'last_time'):
        calculate_speed.last_time = time.time()
        calculate_speed.last_sent = 0
        calculate_speed.last_recv = 0
        
        # 获取初始数据
        net_io = psutil.net_io_counters()
        calculate_speed.last_sent = net_io.bytes_sent
        calculate_speed.last_recv = net_io.bytes_recv
        
        return 0, 0
    
    current_time = time.time()
    time_diff = current_time - calculate_speed.last_time
    
    if time_diff < 0.1:  
        return 0, 0
    
    net_io = psutil.net_io_counters()
    current_sent = net_io.bytes_sent
    current_recv = net_io.bytes_recv
    
    # 计算速率
    sent_speed = (current_sent - calculate_speed.last_sent) / time_diff
    recv_speed = (current_recv - calculate_speed.last_recv) / time_diff
    

    calculate_speed.last_time = current_time
    calculate_speed.last_sent = current_sent
    calculate_speed.last_recv = current_recv
    
    return sent_speed, recv_speed

def bytes_to_gb(bytes_value):
    """字节转换为GB"""
    return bytes_value / (1024 ** 3)

def format_gb_for_display(value_gb):
    """格式化GB显示，专门用于7位数码管显示"""

    formatted = f"{value_gb:,.2f}"
    

    cleaned = formatted.replace(',', '')
    

    if '.' in cleaned:
        int_part, dec_part = cleaned.split('.')
    else:
        int_part = cleaned
        dec_part = "00"
    
    dec_part = dec_part.ljust(2, '0')[:2]
    
    return int_part, dec_part

def get_traffic_data():
    """获取完整的流量数据"""

    traffic_data = get_system_total_traffic()
        # 计算实时速率
    sent_speed, recv_speed = calculate_speed()
    traffic_data['sent_speed'] = sent_speed
    traffic_data['recv_speed'] = recv_speed
    
    return traffic_data

def create_panel(parent):
    """创建流量监控面板的主函数"""
    panel = parent
    
    # 设置面板背景色
    panel.SetBackgroundColour(wx.Colour(240, 240, 240))
    
   
    main_sizer = wx.BoxSizer(wx.VERTICAL)
    
    # 转盘
    indicator_label = wx.StaticText(panel, label="流量转盘 (每圈50MB):")
    indicator_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
    main_sizer.Add(indicator_label, 0, wx.LEFT | wx.TOP, 10)
    
    # 平滑指示器
    indicator_panel = SmoothIndicatorPanel(panel)
    indicator_panel.SetMinSize((-1, 25))
    main_sizer.Add(indicator_panel, 0, wx.EXPAND | wx.ALL, 10)
    
    # 数显
    display_panel = wx.Panel(panel)
    display_panel.SetBackgroundColour(wx.Colour(50, 50, 50))
    display_sizer = wx.BoxSizer(wx.HORIZONTAL)
    
   
    total_label = wx.StaticText(display_panel, label="总流量:")
    total_label.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
    total_label.SetForegroundColour(wx.Colour(200, 200, 255))
    display_sizer.Add(total_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
    
    #数字显示框
    digits = []
    

    for i in range(5):
        digit = wx.StaticText(display_panel, label="0", style=wx.ALIGN_CENTER)
        digit.SetFont(wx.Font(24, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        digit.SetForegroundColour(wx.Colour(255, 255, 255))
        display_sizer.Add(digit, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        digits.append(digit)
    

    decimal_point = wx.StaticText(display_panel, label=".")
    decimal_point.SetFont(wx.Font(24, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
    decimal_point.SetForegroundColour(wx.Colour(255, 255, 255))
    display_sizer.Add(decimal_point, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.BOTTOM, 5)
    

    for i in range(2):
        digit = wx.StaticText(display_panel, label="0", style=wx.ALIGN_CENTER)
        digit.SetFont(wx.Font(24, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        digit.SetForegroundColour(wx.Colour(255, 100, 100))  # 红色
        display_sizer.Add(digit, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        digits.append(digit)  # 第6和第7位是小数部分
    
   
    unit_label = wx.StaticText(display_panel, label="GB")
    unit_label.SetFont(wx.Font(18, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
    unit_label.SetForegroundColour(wx.Colour(200, 200, 255))
    display_sizer.Add(unit_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
    
    display_panel.SetSizer(display_sizer)
    main_sizer.Add(display_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
    
    # 控制面板
    control_panel = wx.Panel(panel)
    control_sizer = wx.BoxSizer(wx.HORIZONTAL)
    
    
    type_label = wx.StaticText(control_panel, label="流量类型:")
    type_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
    control_sizer.Add(type_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
    
    type_choices = ["上传和下载", "仅上传", "仅下载"]
    type_combo = wx.ComboBox(control_panel, choices=type_choices, style=wx.CB_READONLY)
    type_combo.SetSelection(0)
    control_sizer.Add(type_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
    
  
    speed_label = wx.StaticText(control_panel, label="速率: 0.00 MB/s")
    speed_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
    speed_label.SetForegroundColour(wx.Colour(0, 100, 0))
    control_sizer.Add(speed_label, 0, wx.ALIGN_CENTER_VERTICAL)
    
    control_sizer.AddStretchSpacer(1)
    

    mini_button = wx.Button(control_panel, label="生成小窗")
    mini_button.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
    
    mini_button.SetMinSize((80, -1))
    mini_button.Bind(wx.EVT_BUTTON, lambda e: create_mini_window(parent))
    control_sizer.Add(mini_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
    
    
    total_label = wx.StaticText(control_panel, label="系统累计流量")
    total_label.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
    total_label.SetForegroundColour(wx.Colour(100, 100, 100))
    control_sizer.Add(total_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
    
    control_panel.SetSizer(control_sizer)
    main_sizer.Add(control_panel, 0, wx.EXPAND | wx.ALL, 10)
    
   
    status_panel = wx.Panel(panel)
    status_sizer = wx.BoxSizer(wx.HORIZONTAL)
    
   
    upload_info = wx.StaticText(status_panel, label="上传: 0.00 GB")
    upload_info.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    upload_info.SetForegroundColour(wx.Colour(0, 100, 200))
    status_sizer.Add(upload_info, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
    
    
    download_info = wx.StaticText(status_panel, label="下载: 0.00 GB")
    download_info.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    download_info.SetForegroundColour(wx.Colour(200, 100, 0))
    status_sizer.Add(download_info, 0, wx.ALIGN_CENTER_VERTICAL)
    
    status_sizer.AddStretchSpacer(1)
    
    # 当前转数显示
    rounds_label = wx.StaticText(status_panel, label="当前圈数: 0")
    rounds_label.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    rounds_label.SetForegroundColour(wx.Colour(0, 150, 0))
    status_sizer.Add(rounds_label, 0, wx.ALIGN_CENTER_VERTICAL)
    
    status_panel.SetSizer(status_sizer)
    main_sizer.Add(status_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
    
    panel.SetSizer(main_sizer)
    

    def update_display():
        """更新所有显示元素"""
        # 获取流量数据
        traffic_data = get_traffic_data()
        total_sent = traffic_data['total_sent']
        total_recv = traffic_data['total_recv']
        sent_speed = traffic_data['sent_speed']
        recv_speed = traffic_data['recv_speed']
        
  
        if traffic_type == "仅上传":
            total_bytes = total_sent
            total_speed = sent_speed
            display_text = f"上传: {bytes_to_gb(total_sent):.2f} GB"
            upload_info.SetLabel(display_text)
            download_info.SetLabel("下载: --")
        elif traffic_type == "仅下载":
            total_bytes = total_recv
            total_speed = recv_speed
            display_text = f"下载: {bytes_to_gb(total_recv):.2f} GB"
            download_info.SetLabel(display_text)
            upload_info.SetLabel("上传: --")
        else:  
            total_bytes = total_sent + total_recv
            total_speed = sent_speed + recv_speed
            upload_info.SetLabel(f"上传: {bytes_to_gb(total_sent):.2f} GB")
            download_info.SetLabel(f"下载: {bytes_to_gb(total_recv):.2f} GB")
        
    
        total_gb = bytes_to_gb(total_bytes)
        
    
        int_part, dec_part = format_gb_for_display(total_gb)
        

        int_len = len(int_part)
        if int_len > 5:
            # 超过5位，只显示最后5位
            int_part = int_part[-5:]
        

        int_part = int_part.zfill(5)
        
   
        for i in range(5):
            digits[i].SetLabel(int_part[i])
        

        digits[5].SetLabel(dec_part[0] if len(dec_part) > 0 else "0")  # 第6位是小数第一位
        digits[6].SetLabel(dec_part[1] if len(dec_part) > 1 else "0")  # 第7位是小数第二位
        


        total_rounds = total_bytes // ONE_ROUND_BYTES
        remainder = total_bytes % ONE_ROUND_BYTES
        progress = (remainder / ONE_ROUND_BYTES) * 100
        

        indicator_panel.set_position(progress, animate=True)
        

        rounds_label.SetLabel(f"当前圈数: {total_rounds:,}")

        speed_mb = total_speed / (1024 * 1024)
        speed_label.SetLabel(f"速率: {speed_mb:.2f} MB/s")
        
        if speed_mb < 1:
            speed_label.SetForegroundColour(wx.Colour(0, 100, 0))
        elif speed_mb < 10:
            speed_label.SetForegroundColour(wx.Colour(0, 150, 0))
        else:
            speed_label.SetForegroundColour(wx.Colour(200, 0, 0))
        
        wx.CallLater(int(REFRESH_INTERVAL * 1000), update_display)
    

    def on_type_change(event):
        global traffic_type
        traffic_type = type_combo.GetValue()
    
    type_combo.Bind(wx.EVT_COMBOBOX, on_type_change)
    
    wx.CallLater(100, update_display)
    
    return panel

def create_mini_window(parent):
    """创建迷你窗口"""

    frame = wx.Frame(None, title="网络流量监控 - 独立窗口", size=(650, 250))
    

    panel = wx.Panel(frame)
    main_sizer = wx.BoxSizer(wx.VERTICAL)
    

    digit_panel = wx.Panel(panel)
    digit_panel.SetBackgroundColour(wx.Colour(240, 240, 240))
    digit_sizer = wx.BoxSizer(wx.HORIZONTAL)
    

    digits = []
    for i in range(7):
        digit_label = wx.StaticText(digit_panel, label="0", style=wx.ALIGN_CENTER)
        digit_label.SetMinSize((30, 50))
        digit_label.SetFont(wx.Font(24, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        if i < 5:  
            digit_label.SetForegroundColour(wx.Colour(0, 0, 0))
            digit_label.SetBackgroundColour(wx.Colour(255, 255, 200))
        else:  
            digit_label.SetForegroundColour(wx.Colour(255, 0, 0))
            digit_label.SetBackgroundColour(wx.Colour(255, 255, 200))
        
      
        digit_label.SetWindowStyle(digit_label.GetWindowStyle() | wx.BORDER_SIMPLE)
        digit_sizer.Add(digit_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 2)
        digits.append(digit_label)
    
    digit_panel.SetSizer(digit_sizer)
    main_sizer.Add(digit_panel, 0, wx.ALIGN_CENTER | wx.ALL, 10)
    

    indicator_panel = SmoothIndicatorPanel(panel)
    indicator_panel.SetMinSize((-1, 20))
    main_sizer.Add(indicator_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
    

    control_panel = wx.Panel(panel)
    control_sizer = wx.BoxSizer(wx.HORIZONTAL)
    

    type_label = wx.StaticText(control_panel, label="流量类型:")
    type_label.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    control_sizer.Add(type_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
    
    type_choices = ["上传和下载", "仅上传", "仅下载"]
    type_combo = wx.ComboBox(control_panel, choices=type_choices, style=wx.CB_READONLY)
    type_combo.SetSelection(0)
    control_sizer.Add(type_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

    speed_label = wx.StaticText(control_panel, label="速率: 0.00 MB/s")
    speed_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
    speed_label.SetForegroundColour(wx.Colour(0, 100, 0))
    control_sizer.Add(speed_label, 0, wx.ALIGN_CENTER_VERTICAL)
    
    control_sizer.AddStretchSpacer(1)
    

    close_button = wx.Button(control_panel, label="关闭小窗")
    close_button.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
    close_button.SetBackgroundColour(wx.Colour(220, 100, 100))
 
    close_button.SetMinSize((80, -1))
    close_button.Bind(wx.EVT_BUTTON, lambda e: frame.Close())
    control_sizer.Add(close_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
    
    control_panel.SetSizer(control_sizer)
    main_sizer.Add(control_panel, 0, wx.EXPAND | wx.ALL, 10)
    

    status_panel = wx.Panel(panel)
    status_sizer = wx.BoxSizer(wx.HORIZONTAL)
    

    upload_info = wx.StaticText(status_panel, label="上传: 0.00 GB")
    upload_info.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    upload_info.SetForegroundColour(wx.Colour(0, 100, 200))
    status_sizer.Add(upload_info, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
    

    download_info = wx.StaticText(status_panel, label="下载: 0.00 GB")
    download_info.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    download_info.SetForegroundColour(wx.Colour(200, 100, 0))
    status_sizer.Add(download_info, 0, wx.ALIGN_CENTER_VERTICAL)
    
    status_sizer.AddStretchSpacer(1)

    rounds_label = wx.StaticText(status_panel, label="当前圈数: 0")
    rounds_label.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    rounds_label.SetForegroundColour(wx.Colour(0, 150, 0))
    status_sizer.Add(rounds_label, 0, wx.ALIGN_CENTER_VERTICAL)
    
    status_panel.SetSizer(status_sizer)
    main_sizer.Add(status_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
    
    panel.SetSizer(main_sizer)
  
    frame.SetWindowStyle(frame.GetWindowStyle() | wx.STAY_ON_TOP)
    
  
    def update_mini_display():
        """更新迷你窗口显示"""
        try:
          
            if not frame.IsShown(): 
                return
        except RuntimeError:
            
            return
            

        traffic_data = get_traffic_data()
        total_sent = traffic_data['total_sent']
        total_recv = traffic_data['total_recv']
        sent_speed = traffic_data['sent_speed']
        recv_speed = traffic_data['recv_speed']
        

        current_type = type_combo.GetValue()
        if current_type == "仅上传":
            total_bytes = total_sent
            total_speed = sent_speed
            upload_info.SetLabel(f"上传: {bytes_to_gb(total_sent):.2f} GB")
            download_info.SetLabel("下载: --")
        elif current_type == "仅下载":
            total_bytes = total_recv
            total_speed = recv_speed
            download_info.SetLabel(f"下载: {bytes_to_gb(total_recv):.2f} GB")
            upload_info.SetLabel("上传: --")
        else:  # 上传和下载
            total_bytes = total_sent + total_recv
            total_speed = sent_speed + recv_speed
            upload_info.SetLabel(f"上传: {bytes_to_gb(total_sent):.2f} GB")
            download_info.SetLabel(f"下载: {bytes_to_gb(total_recv):.2f} GB")
        
 
        total_gb = bytes_to_gb(total_bytes)
        
 
        int_part, dec_part = format_gb_for_display(total_gb)

        int_len = len(int_part)
        if int_len > 5:
            int_part = int_part[-5:]

        int_part = int_part.zfill(5)
        
     
        for i in range(5):
            digits[i].SetLabel(int_part[i])
        
        digits[5].SetLabel(dec_part[0] if len(dec_part) > 0 else "0")
        digits[6].SetLabel(dec_part[1] if len(dec_part) > 1 else "0")
     
        total_rounds = total_bytes // ONE_ROUND_BYTES
        remainder = total_bytes % ONE_ROUND_BYTES
        progress = (remainder / ONE_ROUND_BYTES) * 100
        
        indicator_panel.set_position(progress, animate=True)
        
        rounds_label.SetLabel(f"当前圈数: {total_rounds:,}")
        
        speed_mb = total_speed / (1024 * 1024)
        speed_label.SetLabel(f"速率: {speed_mb:.2f} MB/s")
        
        if speed_mb < 1:
            speed_label.SetForegroundColour(wx.Colour(0, 100, 0))
        elif speed_mb < 10:
            speed_label.SetForegroundColour(wx.Colour(0, 150, 0))
        else:
            speed_label.SetForegroundColour(wx.Colour(200, 0, 0))
        
        try:
            if frame.IsShown():
                wx.CallLater(int(REFRESH_INTERVAL * 1000), update_mini_display)
        except RuntimeError:
       
            return
    

    def on_type_change(event):

        pass
    
    type_combo.Bind(wx.EVT_COMBOBOX, on_type_change)
    

    def on_close(event):

        if 'indicator_panel' in locals():
            indicator_panel.stop_timer()
        

        frame.Destroy()
    
    frame.Bind(wx.EVT_CLOSE, on_close)
    
 
    wx.CallLater(100, update_mini_display)
    
    frame.Show()

def get_system_total_traffic_summary():
    """获取系统流量统计摘要"""
    net_io = psutil.net_io_counters()
    
    total_gb = (net_io.bytes_sent + net_io.bytes_recv) / (1024 ** 3)
    int_part, dec_part = format_gb_for_display(total_gb)
    
    return {
        'total_upload_gb': net_io.bytes_sent / (1024 ** 3),
        'total_download_gb': net_io.bytes_recv / (1024 ** 3),
        'total_traffic_gb': total_gb,
        'display_int_part': int_part[-5:].zfill(5) if len(int_part) > 5 else int_part.zfill(5),
        'display_dec_part': dec_part
    }

if __name__ == "__main__":

    summary = get_system_total_traffic_summary()
    print("系统累计流量统计（从系统启动开始）:")
    print(f"总上传流量: {summary['total_upload_gb']:.2f} GB")
    print(f"总下载流量: {summary['total_download_gb']:.2f} GB")
    print(f"总流量: {summary['total_traffic_gb']:.2f} GB")
    print(f"数显格式: {summary['display_int_part']}.{summary['display_dec_part']} GB")
    print()
    
    app = wx.App(False)
    frame = wx.Frame(None, title="网络流量监控", size=(650, 250))
    import ctypes
    panel = create_panel(wx.Panel(frame))
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    frame.Show()
    app.MainLoop()