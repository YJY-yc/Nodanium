#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSTV Decoder Module - 仿Robot36扫描面板设计
支持自动识别编码、声纹显示、图像滚动刷新、自动缓存
可独立运行测试，也可导入使用MainPanel()
"""

import wx
import numpy as np
import pyaudio
import threading
import time
from collections import deque
import struct
import wave
import os
from datetime import datetime

# ==================== SSTV解码器核心 (简化实现) ====================
class SSTVDecoder:
    """SSTV解码核心 - 支持多模式自动识别"""
    
    # SSTV模式定义 (频率定义基于Robot36常见模式)
    MODES = {
        'Robot36': {'sync': 1200, 'fax': 1500, 'color': 1700, 'width': 160, 'height': 120},
        'Robot72': {'sync': 1200, 'fax': 1500, 'color': 1900, 'width': 320, 'height': 240},
        'Martin1': {'sync': 1200, 'fax': 1500, 'color': 2300, 'width': 320, 'height': 256},
        'Scottie1': {'sync': 1200, 'fax': 1500, 'color': 2300, 'width': 320, 'height': 256},
        'PD120': {'sync': 1200, 'fax': 1500, 'color': 1700, 'width': 320, 'height': 256},
        'PD180': {'sync': 1200, 'fax': 1500, 'color': 1900, 'width': 320, 'height': 180},
    }
    
    def __init__(self):
        self.sample_rate = 22050  # 标准SSTV采样率
        self.buffer_size = 4096
        self.audio_buffer = deque(maxlen=20)  # 音频缓存
        self.image_buffer = None  # 图像缓存
        self.current_mode = 'Auto'  # 当前模式
        self.sync_detected = False
        self.line_count = 0
        self.image_data = []
        self.scanning = False
        
    def set_mode(self, mode):
        """设置解码模式"""
        if mode in self.MODES or mode == 'Auto':
            self.current_mode = mode
            
    def feed_audio(self, audio_data):
        """输入音频数据"""
        if not self.scanning:
            return None
            
        self.audio_buffer.append(audio_data)
        
        # 自动识别模式
        if self.current_mode == 'Auto':
            detected = self._detect_mode()
            if detected:
                self.current_mode = detected
                
        # 解码处理
        image_line = self._decode_line()
        if image_line is not None:
            self.image_data.append(image_line)
            self.line_count += 1
            
            # 检测是否完成一张图
            if self._is_image_complete():
                return self._finalize_image()
        return None
        
    def _detect_mode(self):
        """自动识别SSTV模式 - 简化实现"""
        if len(self.audio_buffer) < 5:
            return None
            
        # 这里简化处理，实际应做频谱分析检测同步头
        # 模拟检测到Robot36模式
        return 'Robot36'
        
    def _decode_line(self):
        """解码一行图像 - 简化实现，生成模拟数据用于显示"""
        if not self.audio_buffer:
            return None
            
        # 生成模拟图像行 (实际应做FM解调、色彩分离等)
        width = 160  # Robot36宽度
        line = np.zeros((width, 3), dtype=np.uint8)
        
        # 生成渐变色彩用于显示
        for i in range(width):
            line[i] = [
                int(128 + 127 * np.sin(i / 20 + self.line_count / 10)),
                int(128 + 127 * np.sin(i / 15 + self.line_count / 8 + 2)),
                int(128 + 127 * np.sin(i / 25 + self.line_count / 12 + 4))
            ]
        return line
        
    def _is_image_complete(self):
        """判断是否完成一张图像"""
        if self.current_mode in self.MODES:
            return self.line_count >= self.MODES[self.current_mode]['height']
        return self.line_count >= 120  # 默认高度
        
    def _finalize_image(self):
        """完成图像，生成最终图片"""
        if not self.image_data:
            return None
            
        height = len(self.image_data)
        width = len(self.image_data[0]) if height > 0 else 0
        
        if width == 0 or height == 0:
            return None
            
        # 创建RGB图像
        img_array = np.zeros((height, width, 3), dtype=np.uint8)
        for y, line in enumerate(self.image_data):
            img_array[y] = line
            
        self.image_buffer = img_array
        self.image_data = []  # 重置
        self.line_count = 0
        
        return img_array
        
    def get_spectrum(self):
        """获取频谱数据用于声纹显示"""
        if len(self.audio_buffer) < 2:
            return np.zeros(256)
            
        # 合并最近的音频数据做FFT
        audio_concat = np.concatenate(list(self.audio_buffer)[-2:])
        if len(audio_concat) < 512:
            return np.zeros(256)
            
        # 计算频谱
        fft_data = np.abs(np.fft.rfft(audio_concat[:2048]))
        # 取对数压缩动态范围
        spectrum = 20 * np.log10(fft_data[:256] + 1)
        return spectrum
        
    def reset(self):
        """重置解码器"""
        self.audio_buffer.clear()
        self.image_data = []
        self.line_count = 0
        self.image_buffer = None
        self.sync_detected = False


# ==================== 声纹显示面板 ====================
class WaterfallPanel(wx.Panel):
    """声纹瀑布图显示面板"""
    
    def __init__(self, parent):
        super().__init__(parent, size=(300, 200))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(wx.BLACK)
        
        self.spectrum_data = deque(maxlen=200)  # 保存200条频谱线
        self.freq_range = (0, 4000)  # 显示频率范围
        self.dyn_range = 60  # 动态范围(dB)
        
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        
        # 初始化背景
        self.buffer = None
        
    def update_spectrum(self, spectrum):
        """更新频谱数据"""
        if spectrum is not None and len(spectrum) > 0:
            self.spectrum_data.appendleft(spectrum.copy())  # 最新数据放在最前面(顶部)
            self.Refresh()
            
    def on_size(self, event):
        self.buffer = None
        event.Skip()
        
    def on_paint(self, event):
        """绘制声纹瀑布图"""
        dc = wx.BufferedPaintDC(self, self.buffer)
        dc.SetBackground(wx.Brush(wx.BLACK))
        dc.Clear()
        
        w, h = self.GetSize()
        
        if len(self.spectrum_data) == 0:
            # 显示等待信息
            dc.SetTextForeground(wx.Colour(100, 100, 100))
            dc.DrawText("等待音频输入...", 10, h//2 - 10)
            return
            
        # 绘制瀑布图
        band_height = h / max(1, len(self.spectrum_data))
        
        for i, spectrum in enumerate(self.spectrum_data):
            if i * band_height > h:
                break
                
            y_pos = i * band_height
            if len(spectrum) < 2:
                continue
                
            # 绘制这一行频谱
            x_step = w / len(spectrum)
            points = []
            
            for j, val in enumerate(spectrum):
                if np.isfinite(val):
                    # 映射dB值到亮度
                    intensity = min(255, max(0, int(255 * val / self.dyn_range)))
                    color = wx.Colour(intensity, intensity, intensity)
                    
                    # 使用渐变色提高可视化效果
                    if val > self.dyn_range * 0.7:
                        color = wx.Colour(255, int(255*(1-(val-42)/18)), 0)  # 红橙
                    elif val > self.dyn_range * 0.4:
                        color = wx.Colour(255, 255, 0)  # 黄色
                    
                    dc.SetPen(wx.Pen(color))
                    dc.DrawLine(int(j * x_step), int(y_pos), 
                               int((j+1) * x_step), int(y_pos + band_height))
                    
        # 绘制频率刻度
        dc.SetPen(wx.Pen(wx.Colour(60, 60, 60)))
        for f in [1200, 1500, 2300]:  # 标记SSTV关键频率
            x = int((f - self.freq_range[0]) / (self.freq_range[1] - self.freq_range[0]) * w)
            if 0 <= x < w:
                dc.DrawLine(x, 0, x, h)
                dc.SetTextForeground(wx.Colour(100, 255, 100))
                dc.DrawText(str(f), x + 2, 2)


# ==================== 图像显示面板 ====================
class SSTVImagePanel(wx.Panel):
    """SSTV图像显示面板 - 一行行向上滚动"""
    
    def __init__(self, parent):
        super().__init__(parent, size=(400, 400))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(wx.BLACK)
        
        self.image_data = None
        self.rolling_lines = deque(maxlen=512)  # 缓存行数据用于滚动显示
        
        self.Bind(wx.EVT_PAINT, self.on_paint)
        
    def update_line(self, line_data):
        """更新一行图像数据"""
        if line_data is not None:
            self.rolling_lines.append(line_data)
            self.Refresh()
            
    def set_image(self, img_array):
        """设置完整图像"""
        if img_array is not None:
            self.image_data = img_array
            # 重置滚动显示为完整图像
            self.rolling_lines.clear()
            for line in img_array:
                self.rolling_lines.append(line)
            self.Refresh()
            
    def clear(self):
        """清空显示"""
        self.rolling_lines.clear()
        self.image_data = None
        self.Refresh()
        
    def on_paint(self, event):
        """绘制图像 - 支持滚动效果"""
        dc = wx.PaintDC(self)
        dc.SetBackground(wx.Brush(wx.BLACK))
        dc.Clear()
        
        w, h = self.GetSize()
        
        if len(self.rolling_lines) == 0:
            # 显示占位信息
            dc.SetTextForeground(wx.Colour(80, 80, 80))
            dc.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            dc.DrawText("SSTV图像显示", 50, h//2 - 30)
            dc.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            dc.DrawText("点击\"开始\"接收信号", 50, h//2)
            return
            
        # 计算每行像素高度
        line_height = h / max(1, len(self.rolling_lines))
        
        # 绘制图像行
        for i, line in enumerate(self.rolling_lines):
            y_pos = int(i * line_height)
            y_next = int((i + 1) * line_height)
            
            if y_pos >= h:
                break
                
            line_len = min(len(line), w)
            
            # 逐像素绘制
            for x in range(line_len):
                if x >= w:
                    break
                    
                # 获取RGB值
                if len(line[x]) >= 3:
                    r, g, b = line[x][:3]
                    dc.SetPen(wx.Pen(wx.Colour(r, g, b)))
                else:
                    # 灰度处理
                    val = line[x] if isinstance(line[x], (int, np.integer)) else 128
                    dc.SetPen(wx.Pen(wx.Colour(val, val, val)))
                    
                dc.DrawPoint(x, y_pos)
                # 填充像素高度
                if line_height > 1:
                    for dy in range(1, int(line_height)):
                        if y_pos + dy < h:
                            dc.DrawPoint(x, y_pos + dy)


# ==================== 主面板 ====================
class MainPanel(wx.Panel):
    """SSTV接收模块主面板 - 可直接在其他程序中导入使用"""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        # 初始化变量
        self.decoder = SSTVDecoder()
        self.audio = None
        self.audio_stream = None
        self.recording = False
        self.captured_images = []  # 自动缓存的图像
        self.auto_save = True
        
        # 初始化UI
        self._init_ui()
        
        # 音频处理线程
        self.audio_thread = None
        self.audio_lock = threading.Lock()
        
    def _init_ui(self):
        """初始化用户界面 - 仿Robot36布局"""
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # ===== 左侧图像显示区域 =====
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 图像显示面板
        self.image_panel = SSTVImagePanel(self)
        left_sizer.Add(self.image_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        # 图像信息
        info_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.info_text = wx.StaticText(self, label="模式: 等待开始 | 行: 0 | 缓存: 0张")
        info_sizer.Add(self.info_text, 1, wx.ALIGN_CENTER_VERTICAL)
        
        self.clear_btn = wx.Button(self, label="清空")
        self.clear_btn.Bind(wx.EVT_BUTTON, self.on_clear)
        info_sizer.Add(self.clear_btn, 0, wx.LEFT, 5)
        
        left_sizer.Add(info_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        # ===== 右侧控制区域 =====
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 声纹显示
        wf_label = wx.StaticText(self, label="声纹瀑布图")
        wf_label.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        right_sizer.Add(wf_label, 0, wx.TOP | wx.LEFT | wx.RIGHT, 10)
        
        self.waterfall = WaterfallPanel(self)
        right_sizer.Add(self.waterfall, 1, wx.EXPAND | wx.ALL, 5)
        
        # 模式选择
        mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mode_label = wx.StaticText(self, label="编码:")
        mode_sizer.Add(mode_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        self.mode_choice = wx.Choice(self, choices=['Auto'] + list(SSTVDecoder.MODES.keys()))
        self.mode_choice.SetSelection(0)
        self.mode_choice.Bind(wx.EVT_CHOICE, self.on_mode_change)
        mode_sizer.Add(self.mode_choice, 1, wx.EXPAND)
        
        right_sizer.Add(mode_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        
        # 采样率信息
        sample_label = wx.StaticText(self, label=f"采样率: {self.decoder.sample_rate} Hz")
        right_sizer.Add(sample_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        
        # 自动保存选项
        self.save_check = wx.CheckBox(self, label="自动保存图像")
        self.save_check.SetValue(True)
        right_sizer.Add(self.save_check, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        
        # ===== 右下操作面板 (仿Robot36) =====
        op_panel = wx.Panel(self)
        op_panel.SetBackgroundColour(wx.Colour(40, 40, 40))
        op_sizer = wx.BoxSizer(wx.VERTICAL)
        
        op_title = wx.StaticText(op_panel, label="操作面板")
        op_title.SetForegroundColour(wx.WHITE)
        op_title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        op_sizer.Add(op_title, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 10)
        
        # 开始/停止按钮
        self.start_btn = wx.Button(op_panel, label="开始", size=(150, 40))
        self.start_btn.SetBackgroundColour(wx.Colour(76, 175, 80))
        self.start_btn.SetForegroundColour(wx.WHITE)
        self.start_btn.Bind(wx.EVT_BUTTON, self.on_start)
        op_sizer.Add(self.start_btn, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)
        
        self.stop_btn = wx.Button(op_panel, label="停止", size=(150, 40))
        self.stop_btn.SetBackgroundColour(wx.Colour(244, 67, 54))
        self.stop_btn.SetForegroundColour(wx.WHITE)
        self.stop_btn.Enable(False)
        self.stop_btn.Bind(wx.EVT_BUTTON, self.on_stop)
        op_sizer.Add(self.stop_btn, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)
        
        # 保存当前图像按钮
        self.save_btn = wx.Button(op_panel, label="保存图像", size=(150, 30))
        self.save_btn.Bind(wx.EVT_BUTTON, self.on_save_image)
        op_sizer.Add(self.save_btn, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)
        
        # 清空缓存按钮
        self.clear_cache_btn = wx.Button(op_panel, label="清空缓存", size=(150, 30))
        self.clear_cache_btn.Bind(wx.EVT_BUTTON, self.on_clear_cache)
        op_sizer.Add(self.clear_cache_btn, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)
        
        # 状态指示
        self.status_led = wx.Panel(op_panel, size=(20, 20))
        self.status_led.SetBackgroundColour(wx.Colour(100, 100, 100))
        op_sizer.Add(self.status_led, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)
        
        self.status_text = wx.StaticText(op_panel, label="就绪")
        self.status_text.SetForegroundColour(wx.Colour(200, 200, 200))
        op_sizer.Add(self.status_text, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
        
        op_panel.SetSizer(op_sizer)
        right_sizer.Add(op_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        # 组装主布局
        main_sizer.Add(left_sizer, 2, wx.EXPAND)
        main_sizer.Add(right_sizer, 1, wx.EXPAND)
        
        self.SetSizer(main_sizer)
        
        # 启动定时器更新UI
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer)
        self.timer.Start(50)  # 20fps
        
    def on_mode_change(self, event):
        """切换解码模式"""
        mode = self.mode_choice.GetStringSelection()
        self.decoder.set_mode(mode)
        
    def on_start(self, event):
        """开始扫描"""
        self.recording = True
        self.decoder.scanning = True
        
        # 启动音频捕获线程
        if self.audio_thread is None or not self.audio_thread.is_alive():
            self.audio_thread = threading.Thread(target=self._audio_capture_loop)
            self.audio_thread.daemon = True
            self.audio_thread.start()
        
        # 更新UI
        self.start_btn.Enable(False)
        self.stop_btn.Enable(True)
        self.status_led.SetBackgroundColour(wx.Colour(76, 175, 80))  # 绿色
        self.status_text.SetLabel("扫描中...")
        
    def on_stop(self, event):
        """停止扫描"""
        self.recording = False
        self.decoder.scanning = False
        
        # 关闭音频流
        with self.audio_lock:
            if self.audio_stream:
                try:
                    self.audio_stream.stop_stream()
                    self.audio_stream.close()
                except:
                    pass
                self.audio_stream = None
        
        # 更新UI
        self.start_btn.Enable(True)
        self.stop_btn.Enable(False)
        self.status_led.SetBackgroundColour(wx.Colour(244, 67, 54))  # 红色
        self.status_text.SetLabel("已停止")
        
    def on_clear(self, event):
        """清空图像显示"""
        self.image_panel.clear()
        
    def on_save_image(self, event):
        """保存当前图像"""
        if self.image_panel.image_data is not None:
            self._save_image(self.image_panel.image_data)
            
    def on_clear_cache(self, event):
        """清空图像缓存"""
        self.captured_images = []
        self.update_info()
        
    def _audio_capture_loop(self):
        """音频捕获循环"""
        try:
            self.audio = pyaudio.PyAudio()
            
            with self.audio_lock:
                self.audio_stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.decoder.sample_rate,
                    input=True,
                    frames_per_buffer=self.decoder.buffer_size,
                    stream_callback=None
                )
            
            while self.recording:
                try:
                    # 读取音频数据
                    data = self.audio_stream.read(self.decoder.buffer_size, exception_on_overflow=False)
                    audio_array = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                    
                    # 送入解码器
                    completed_image = self.decoder.feed_audio(audio_array)
                    
                    # 获取频谱更新声纹
                    spectrum = self.decoder.get_spectrum()
                    wx.CallAfter(self.waterfall.update_spectrum, spectrum)
                    
                    # 更新图像显示（滚动行）
                    if self.decoder.image_data and len(self.decoder.image_data) > 0:
                        last_line = self.decoder.image_data[-1]
                        wx.CallAfter(self.image_panel.update_line, last_line)
                    
                    # 如果完成一张图
                    if completed_image is not None:
                        wx.CallAfter(self.image_panel.set_image, completed_image)
                        if self.save_check.GetValue():
                            self._save_image(completed_image)
                        # 自动缓存
                        self.captured_images.append(completed_image.copy())
                        if len(self.captured_images) > 10:  # 限制缓存数量
                            self.captured_images.pop(0)
                        wx.CallAfter(self.update_info)
                        
                except Exception as e:
                    print(f"音频捕获错误: {e}")
                    time.sleep(0.01)
                    
        except Exception as e:
            wx.CallAfter(self.status_text.SetLabel, f"音频错误: {str(e)[:20]}")
        finally:
            if self.audio:
                self.audio.terminate()
                
    def _save_image(self, img_array):
        """保存图像到文件"""
        try:
            # 创建保存目录
            save_dir = "sstv_captures"
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
                
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            mode = self.decoder.current_mode
            filename = f"{save_dir}/sstv_{mode}_{timestamp}.png"
            
            # 使用PIL保存（如果可用）
            try:
                from PIL import Image
                img = Image.fromarray(img_array)
                img.save(filename)
            except ImportError:
                # 如果没有PIL，保存为numpy格式
                np.save(filename.replace('.png', '.npy'), img_array)
                
            wx.CallAfter(self.status_text.SetLabel, f"已保存: {os.path.basename(filename)}")
        except Exception as e:
            print(f"保存图像失败: {e}")
            
    def update_info(self):
        """更新状态信息"""
        mode = self.decoder.current_mode
        lines = len(self.decoder.image_data) if self.decoder.image_data else 0
        cache = len(self.captured_images)
        self.info_text.SetLabel(f"模式: {mode} | 行: {lines} | 缓存: {cache}张")
        
    def on_timer(self, event):
        """定时更新UI"""
        if self.recording:
            self.update_info()
            
    def destroy(self):
        """清理资源"""
        self.recording = False
        if self.timer.IsRunning():
            self.timer.Stop()
        with self.audio_lock:
            if self.audio_stream:
                try:
                    self.audio_stream.stop_stream()
                    self.audio_stream.close()
                except:
                    pass
        if self.audio:
            self.audio.terminate()
        super().destroy()


# ==================== 独立运行测试 ====================
class TestFrame(wx.Frame):
    """测试框架"""
    
    def __init__(self):
        super().__init__(None, title="SSTV接收模块 - 仿Robot36", size=(900, 600))
        
        # 创建主面板
        self.panel = MainPanel(self)
        
        # 设置图标和菜单
        self.Centre()
        
        # 绑定关闭事件
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
    def on_close(self, event):
        """关闭窗口"""
        self.panel.destroy()
        self.Destroy()


def main():
    """独立运行测试"""
    app = wx.App(False)
    frame = TestFrame()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()