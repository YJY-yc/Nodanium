import wx
import subprocess
import threading

class PacketCaptureApp(wx.Frame):
    def __init__(self):
        super().__init__(None, title="网络抓包工具", size=(800, 600))
        
        # 创建面板
        panel = wx.Panel(self)
        
        # 创建控件
        self.start_btn = wx.Button(panel, label="开始抓包", pos=(20, 20))
        self.stop_btn = wx.Button(panel, label="停止抓包", pos=(120, 20))
        self.stop_btn.Disable()
        
        self.output_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE|wx.TE_READONLY,
                                     pos=(20, 60), size=(760, 500))
        
        # 绑定事件
        self.start_btn.Bind(wx.EVT_BUTTON, self.on_start)
        self.stop_btn.Bind(wx.EVT_BUTTON, self.on_stop)
        
        # 抓包进程
        self.capture_process = None
        self.is_capturing = False
        
        self.Show()

    def on_start(self, event):
        """开始抓包"""
        self.start_btn.Disable()
        self.stop_btn.Enable()
        self.output_text.Clear()
        
        # 启动抓包线程
        self.is_capturing = True
        threading.Thread(target=self.capture_packets, daemon=True).start()

    def on_stop(self, event):
        """停止抓包"""
        self.is_capturing = False
        if self.capture_process:
            self.capture_process.terminate()
        self.start_btn.Enable()
        self.stop_btn.Disable()

    def capture_packets(self):
        """抓包线程"""
        try:
            # 使用tcpdump进行抓包
            self.capture_process = subprocess.Popen(
                ['tcpdump', '-i', 'any'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            while self.is_capturing:
                output = self.capture_process.stdout.readline()
                if output:
                    wx.CallAfter(self.output_text.AppendText, output)
                
        except Exception as e:
            wx.MessageBox(f"抓包失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)

if __name__ == "__main__":
    app = wx.App(False)
    frame = PacketCaptureApp()
    app.MainLoop()
