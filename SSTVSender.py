# sstv_sender.py
import wx
import numpy as np
import wave
import os
from PIL import Image
import threading
import time
from enum import Enum
import pyaudio
import io
import subprocess
import tempfile

# SSTV编码模式枚举
class SSTVMode(Enum):
    MARTIN1 = "Martin 1"
    MARTIN2 = "Martin 2"
    SCOTTIE1 = "Scottie 1"
    SCOTTIE2 = "Scottie 2"
    ROBOT36 = "Robot 36"
    ROBOT72 = "Robot 72"
    PD50 = "PD 50"
    PD90 = "PD 90"
    PD120 = "PD 120"
    PD160 = "PD 160"
    PD180 = "PD 180"
    PD240 = "PD 240"
    PD290 = "PD 290"
    FAX480 = "FAX 480"
    COLOR = "Color"

# 模式到pysstv命令行参数的映射
MODE_TO_PYSSTV = {
    SSTVMode.MARTIN1: "MartinM1",
    SSTVMode.MARTIN2: "MartinM2",
    SSTVMode.SCOTTIE1: "ScottieS1",
    SSTVMode.SCOTTIE2: "ScottieS2",
    SSTVMode.ROBOT36: "Robot36",
    SSTVMode.ROBOT72: "Robot72",
    SSTVMode.PD50: "PD50",
    SSTVMode.PD90: "PD90",
    SSTVMode.PD120: "PD120",
    SSTVMode.PD160: "PD160",
    SSTVMode.PD180: "PD180",
    SSTVMode.PD240: "PD240",
    SSTVMode.PD290: "PD290",
    SSTVMode.FAX480: "FAX480",
    SSTVMode.COLOR: "Color",
}

# 模式分辨率信息
MODE_RESOLUTIONS = {
    SSTVMode.MARTIN1: (320, 256),
    SSTVMode.MARTIN2: (320, 256),
    SSTVMode.SCOTTIE1: (320, 256),
    SSTVMode.SCOTTIE2: (320, 256),
    SSTVMode.ROBOT36: (320, 240),
    SSTVMode.ROBOT72: (320, 240),
    SSTVMode.PD50: (320, 256),
    SSTVMode.PD90: (320, 256),
    SSTVMode.PD120: (320, 256),
    SSTVMode.PD160: (320, 256),
    SSTVMode.PD180: (320, 256),
    SSTVMode.PD240: (640, 496),
    SSTVMode.PD290: (800, 616),
    SSTVMode.FAX480: (480, 480),
    SSTVMode.COLOR: (320, 256),
}

# 全局变量用于控制播放
stop_playback = False

class SSTVEncoder:
    """使用pysstv命令行的SSTV编码器"""
    def __init__(self, sample_rate=48000):
        self.sample_rate = sample_rate
        self.stop_flag = False
        
    def stop(self):
        """停止编码"""
        self.stop_flag = True
        
    def get_mode_resolution(self, mode):
        """获取指定模式的分辨率"""
        return MODE_RESOLUTIONS.get(mode, (320, 256))
    
    def get_mode_name(self, mode):
        """获取pysstv使用的模式名称"""
        return MODE_TO_PYSSTV.get(mode, "MartinM1")
    
    def prepare_image(self, image_path, target_width, target_height):
        """准备图片：调整大小并居中填充"""
        try:
            # 打开图片
            img = Image.open(image_path).convert('RGB')
            
            # 保持宽高比缩放
            img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            
            # 创建新图片，黑色背景
            new_img = Image.new('RGB', (target_width, target_height), (0, 0, 0))
            
            # 计算居中位置
            paste_x = (target_width - img.width) // 2
            paste_y = (target_height - img.height) // 2
            
            # 粘贴图片
            new_img.paste(img, (paste_x, paste_y))
            
            # 保存到临时文件
            temp_img = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            new_img.save(temp_img.name)
            return temp_img.name
            
        except Exception as e:
            raise Exception(f"图片处理失败: {str(e)}")
    
    def encode_image(self, image_path, mode, progress_callback=None):
        """使用pysstv命令行将图片编码为SSTV音频信号"""
        try:
            self.stop_flag = False
            
            if progress_callback:
                wx.CallAfter(progress_callback, 10)
            
            # 获取目标分辨率
            target_width, target_height = self.get_mode_resolution(mode)
            
            # 准备图片
            temp_img_path = self.prepare_image(image_path, target_width, target_height)
            
            if self.stop_flag:
                os.unlink(temp_img_path)
                return np.array([])
            
            if progress_callback:
                wx.CallAfter(progress_callback, 30)
            
            # 创建临时WAV文件
            temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_wav_path = temp_wav.name
            temp_wav.close()
            
            # 获取pysstv模式名称
            pysstv_mode = self.get_mode_name(mode)
            
            # 构建pysstv命令
            cmd = [
                'python', '-m', 'pysstv',
                '--mode', pysstv_mode,
                '--rate', str(self.sample_rate),
                '--bits', '16',
                temp_img_path, temp_wav_path
            ]
            
            if progress_callback:
                wx.CallAfter(progress_callback, 50, f"执行: pysstv --mode {pysstv_mode}")
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 删除临时图片
            os.unlink(temp_img_path)
            
            if result.returncode != 0:
                raise Exception(f"pysstv编码失败: {result.stderr}")
            
            if self.stop_flag:
                os.unlink(temp_wav_path)
                return np.array([])
            
            if progress_callback:
                wx.CallAfter(progress_callback, 80, "读取音频数据...")
            
            # 读取生成的WAV文件
            with wave.open(temp_wav_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                audio_bytes = wav_file.readframes(frames)
                audio_data = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32767.0
            
            # 删除临时WAV文件
            os.unlink(temp_wav_path)
            
            if progress_callback:
                wx.CallAfter(progress_callback, 100, "编码完成")
            
            return audio_data
            
        except Exception as e:
            # 清理临时文件
            try:
                if 'temp_img_path' in locals():
                    os.unlink(temp_img_path)
                if 'temp_wav_path' in locals():
                    os.unlink(temp_wav_path)
            except:
                pass
            raise Exception(f"编码失败: {str(e)}")
    
    def save_to_wav(self, filename, audio_data):
        """保存音频数据为WAV文件"""
        if len(audio_data) == 0:
            raise ValueError("音频数据为空")
        
        # 转换为16位整数
        audio_int16 = np.int16(audio_data * 32767)
        
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

class SSTVPanel:
    """SSTV发送面板类"""
    def __init__(self, parent):
        self.parent = parent
        self.panel = wx.Panel(parent)
        
        # 初始化属性
        self.encoder = SSTVEncoder()
        self.current_image_path = None
        self.playing = False
        
        # 创建控件
        self.create_widgets()
        
    def create_widgets(self):
        """创建所有界面控件"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 文件选择部分
        file_sizer = wx.BoxSizer(wx.HORIZONTAL)
        file_label = wx.StaticText(self.panel, label="图片文件:")
        file_sizer.Add(file_label, 0, wx.ALL | wx.CENTER, 5)
        
        self.file_path_text = wx.TextCtrl(self.panel, style=wx.TE_READONLY)
        file_sizer.Add(self.file_path_text, 1, wx.ALL | wx.EXPAND, 5)
        
        browse_btn = wx.Button(self.panel, label="浏览...")
        browse_btn.Bind(wx.EVT_BUTTON, self.on_browse)
        file_sizer.Add(browse_btn, 0, wx.ALL, 5)
        
        main_sizer.Add(file_sizer, 0, wx.EXPAND)
        
        # 编码模式选择
        mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mode_label = wx.StaticText(self.panel, label="SSTV模式:")
        mode_sizer.Add(mode_label, 0, wx.ALL | wx.CENTER, 5)
        
        self.all_modes = list(SSTVMode)
        self.mode_choice = wx.Choice(self.panel, choices=[mode.value for mode in self.all_modes])
        self.mode_choice.SetSelection(0)
        self.mode_choice.Bind(wx.EVT_CHOICE, self.on_mode_change)
        mode_sizer.Add(self.mode_choice, 1, wx.ALL | wx.EXPAND, 5)
        
        info_btn = wx.Button(self.panel, label="模式信息", size=(80, -1))
        info_btn.Bind(wx.EVT_BUTTON, self.on_mode_info)
        mode_sizer.Add(info_btn, 0, wx.ALL, 5)
        
        main_sizer.Add(mode_sizer, 0, wx.EXPAND)
        
        # 分辨率显示
        res_sizer = wx.BoxSizer(wx.HORIZONTAL)
        res_label = wx.StaticText(self.panel, label="目标分辨率:")
        res_sizer.Add(res_label, 0, wx.ALL | wx.CENTER, 5)
        
        self.resolution_text = wx.StaticText(self.panel, label="")
        res_sizer.Add(self.resolution_text, 1, wx.ALL | wx.CENTER, 5)
        
        main_sizer.Add(res_sizer, 0, wx.EXPAND)
        
        # 图片预览
        preview_label = wx.StaticText(self.panel, label="图片预览:")
        main_sizer.Add(preview_label, 0, wx.ALL, 5)
        
        self.preview_image = wx.StaticBitmap(self.panel, size=(320, 240))
        main_sizer.Add(self.preview_image, 0, wx.ALL | wx.CENTER, 5)
        
        # 进度条
        progress_label = wx.StaticText(self.panel, label="编码进度:")
        main_sizer.Add(progress_label, 0, wx.ALL, 5)
        
        self.progress_bar = wx.Gauge(self.panel, range=100, size=(-1, 20))
        main_sizer.Add(self.progress_bar, 0, wx.ALL | wx.EXPAND, 5)
        
        # 状态显示
        self.status_text = wx.StaticText(self.panel, label="就绪")
        main_sizer.Add(self.status_text, 0, wx.ALL, 5)
        
        # 按钮区域
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.encode_btn = wx.Button(self.panel, label="编码并播放")
        self.encode_btn.Bind(wx.EVT_BUTTON, lambda evt: self.on_encode(play=True))
        button_sizer.Add(self.encode_btn, 1, wx.ALL, 5)
        
        self.stop_btn = wx.Button(self.panel, label="停止播放")
        self.stop_btn.Bind(wx.EVT_BUTTON, self.on_stop)
        self.stop_btn.Disable()
        button_sizer.Add(self.stop_btn, 1, wx.ALL, 5)
        
        save_btn = wx.Button(self.panel, label="保存为WAV")
        save_btn.Bind(wx.EVT_BUTTON, lambda evt: self.on_encode(save=True))
        button_sizer.Add(save_btn, 1, wx.ALL, 5)
        
        main_sizer.Add(button_sizer, 0, wx.EXPAND)
        
        # 帮助信息
        help_text = wx.StaticText(self.panel, 
                                 label="提示：使用pysstv命令行编码，确保已安装pysstv: pip install pysstv")
        help_text.SetForegroundColour(wx.Colour(100, 100, 100))
        main_sizer.Add(help_text, 0, wx.ALL, 5)
        
        self.panel.SetSizer(main_sizer)
        
        # 初始化显示
        self.update_resolution_display()
    
    def update_resolution_display(self):
        """更新分辨率显示"""
        mode_index = self.mode_choice.GetSelection()
        mode = self.all_modes[mode_index]
        width, height = self.encoder.get_mode_resolution(mode)
        self.resolution_text.SetLabel(f"{width} x {height}")
    
    def on_mode_change(self, event):
        """模式改变事件"""
        self.update_resolution_display()
    
    def on_mode_info(self, event):
        """显示当前模式的详细信息"""
        mode_index = self.mode_choice.GetSelection()
        mode = self.all_modes[mode_index]
        width, height = self.encoder.get_mode_resolution(mode)
        pysstv_mode = self.encoder.get_mode_name(mode)
        
        info_text = f"模式: {mode.value}\n"
        info_text += f"分辨率: {width} x {height}\n"
        info_text += f"pysstv模式: {pysstv_mode}\n"
        
        wx.MessageBox(info_text, "模式信息", wx.OK | wx.ICON_INFORMATION)
    
    def on_browse(self, event):
        """浏览文件"""
        wildcard = "图片文件 (*.jpg;*.png;*.bmp;*.gif)|*.jpg;*.png;*.bmp;*.gif|所有文件 (*.*)|*.*"
        dialog = wx.FileDialog(self.panel, "选择图片", wildcard=wildcard, style=wx.FD_OPEN)
        
        if dialog.ShowModal() == wx.ID_OK:
            file_path = dialog.GetPath()
            self.file_path_text.SetValue(file_path)
            self.current_image_path = file_path
            
            # 显示图片预览
            try:
                img = wx.Image(file_path, wx.BITMAP_TYPE_ANY)
                width, height = img.GetSize()
                
                # 缩放预览
                if width > height:
                    new_width = 320
                    new_height = int(320 * height / width)
                else:
                    new_height = 240
                    new_width = int(240 * width / height)
                
                img = img.Scale(new_width, new_height, wx.IMAGE_QUALITY_HIGH)
                
                # 居中显示
                bitmap = wx.Bitmap(img)
                result_bitmap = wx.Bitmap(320, 240)
                dc = wx.MemoryDC(result_bitmap)
                dc.SetBackground(wx.Brush(wx.Colour(240, 240, 240)))
                dc.Clear()
                dc.DrawBitmap(bitmap, (320 - new_width) // 2, (240 - new_height) // 2, True)
                dc.SelectObject(wx.NullBitmap)
                
                self.preview_image.SetBitmap(result_bitmap)
                self.panel.Layout()
                
            except Exception as e:
                wx.MessageBox(f"无法加载图片: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
        
        dialog.Destroy()
    
    def update_progress(self, value, message=None):
        """更新进度条和状态信息"""
        self.progress_bar.SetValue(int(value))
        if message:
            self.status_text.SetLabel(message)
        else:
            self.status_text.SetLabel(f"编码中: {value}%")
    
    def play_audio(self, audio_data):
        """使用pyaudio播放音频"""
        global stop_playback
        try:
            p = pyaudio.PyAudio()
            audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
            
            stream = p.open(format=pyaudio.paInt16,
                          channels=1,
                          rate=self.encoder.sample_rate,
                          output=True,
                          frames_per_buffer=1024)
            
            # 分块播放
            chunk_size = 4096
            total_chunks = len(audio_bytes) // chunk_size + 1
            
            for i in range(total_chunks):
                if stop_playback:
                    break
                
                start = i * chunk_size
                end = min(start + chunk_size, len(audio_bytes))
                chunk = audio_bytes[start:end]
                
                if chunk:
                    stream.write(chunk)
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"播放失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
        finally:
            wx.CallAfter(self.on_play_finished)
    
    def on_play_finished(self):
        """播放完成后的处理"""
        global stop_playback
        stop_playback = False
        self.playing = False
        self.encode_btn.Enable()
        self.stop_btn.Disable()
        self.status_text.SetLabel("播放完成")
        self.progress_bar.SetValue(0)
    
    def on_stop(self, event):
        """停止播放"""
        global stop_playback
        stop_playback = True
        self.encoder.stop()
        self.status_text.SetLabel("正在停止...")
    
    def on_encode(self, play=False, save=False):
        """编码SSTV信号"""
        global stop_playback
        if not self.current_image_path:
            wx.MessageBox("请先选择图片", "提示", wx.OK | wx.ICON_INFORMATION)
            return
        
        mode_index = self.mode_choice.GetSelection()
        mode = self.all_modes[mode_index]
        
        def encode_thread():
            try:
                stop_playback = False
                self.encoder.stop_flag = False
                
                wx.CallAfter(self.status_text.SetLabel, "开始编码...")
                wx.CallAfter(self.progress_bar.SetValue, 0)
                
                if play:
                    wx.CallAfter(self.encode_btn.Disable)
                    wx.CallAfter(self.stop_btn.Enable)
                    self.playing = True
                
                audio_data = self.encoder.encode_image(
                    self.current_image_path, 
                    mode,
                    self.update_progress
                )
                
                if len(audio_data) == 0:
                    if self.encoder.stop_flag:
                        wx.CallAfter(self.status_text.SetLabel, "编码已停止")
                    else:
                        wx.CallAfter(wx.MessageBox, "编码失败：生成的音频数据为空", "错误", wx.OK | wx.ICON_ERROR)
                    
                    wx.CallAfter(self.encode_btn.Enable)
                    wx.CallAfter(self.stop_btn.Disable)
                    return
                
                wx.CallAfter(self.status_text.SetLabel, "编码完成")
                
                if play and not self.encoder.stop_flag:
                    wx.CallAfter(self.status_text.SetLabel, "正在播放...")
                    self.play_audio(audio_data)
                
                if save and not self.encoder.stop_flag:
                    wx.CallAfter(self.save_audio_dialog, audio_data)
                
            except Exception as e:
                error_msg = str(e)
                wx.CallAfter(wx.MessageBox, f"编码失败: {error_msg}", "错误", wx.OK | wx.ICON_ERROR)
                wx.CallAfter(self.progress_bar.SetValue, 0)
                wx.CallAfter(self.status_text.SetLabel, "编码失败")
                wx.CallAfter(self.encode_btn.Enable)
                wx.CallAfter(self.stop_btn.Disable)
        
        thread = threading.Thread(target=encode_thread)
        thread.daemon = True
        thread.start()
    
    def save_audio_dialog(self, audio_data):
        """保存音频文件对话框"""
        save_dialog = wx.FileDialog(
            self.panel, "保存WAV文件", wildcard="WAV文件 (*.wav)|*.wav",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )
        if save_dialog.ShowModal() == wx.ID_OK:
            filename = save_dialog.GetPath()
            if not filename.endswith('.wav'):
                filename += '.wav'
            try:
                self.encoder.save_to_wav(filename, audio_data)
                wx.MessageBox(f"文件已保存: {filename}", "保存成功", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                wx.MessageBox(f"保存失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
        save_dialog.Destroy()
    
    def get_panel(self):
        """返回实际的wx.Panel对象"""
        return self.panel

def create_sstv_panel(parent):
    """创建SSTV发送面板"""
    sstv_panel = SSTVPanel(parent)
    return sstv_panel.get_panel()

if __name__ == "__main__":
    app = wx.App(False)
    frame = wx.Frame(None, title="SSTV发送器", size=(550, 650))
    frame.CreateStatusBar()
    frame.SetStatusText("就绪")
    
    sstv_panel = create_sstv_panel(frame)
    
    frame.Show()
    app.MainLoop()