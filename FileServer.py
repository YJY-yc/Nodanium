# Copyright (c) 2024-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import wx
import wx.lib.newevent
import os
import socket
import threading
import json
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from io import BytesIO
import cgi
import re
import time,platform

(FileProgressEvent, EVT_FILE_PROGRESS) = wx.lib.newevent.NewEvent()
(ServerStatusEvent, EVT_SERVER_STATUS) = wx.lib.newevent.NewEvent()

server_thread = None

# 获取配置和目录信息
sys_type = platform.system()
if sys_type == "Windows":
    target_folder = os.path.join(os.getenv('APPDATA', ''), "Nodanium")
elif sys_type == "Linux":
    target_folder = os.path.join(os.path.expanduser("~"), ".Nodanium")
elif sys_type == "Darwin":
    target_folder = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Nodanium")
else:
    target_folder = os.path.join(os.path.expanduser("~"), ".Nodanium")

if not os.path.exists(target_folder):
    os.makedirs(target_folder)


config = {
    'font_size': 17,
    'list_button_size': 15,
    'font_name': "微软雅黑",
    'size': (300, 30),
    'size_button': (100, 30),
    'window_pos': (100, 20),  
    'window_size': [1020, 700],
    'high_dpi':True,
    'share_path': "D:/SharedFiles"
}
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

try:
    default_port = config['default_port']
    share_path = config['share_path']
    open_browser = config['auto_open_browser']
    print(default_port)
    print(share_path)
except:
    default_port=1524
    share_path="D:/SharedFiles"

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    
    daemon_threads = True

class FileRequestHandler(SimpleHTTPRequestHandler):

    
    def __init__(self, *args, **kwargs):
        self.shared_folder = kwargs.pop('shared_folder')

        self.event_handler = kwargs.pop('event_handler')
        self.log_callback = kwargs.pop('log_callback')
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        message = format % args  
        if self.log_callback:
            self.log_callback(message)
        super().log_message(format, *args) 
    
    def translate_path(self, path):

        path = super().translate_path(path)
        relpath = os.path.relpath(path, os.getcwd())
        return os.path.join(self.shared_folder, relpath)
    
    def list_directory(self, path):
  
        try:
            list = os.listdir(path)
        except OSError:
            self.send_error(404, "No permission to list directory")
            return None
        
        list.sort(key=lambda a: a.lower())
        
        html = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<title>文件服务</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }",
            "h1 { color: #333; }",
            ".upload-box { background: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }",
            ".file-list { list-style: none; padding: 0; }",
            ".file-item { padding: 10px; border-bottom: 1px solid #ddd; }",
            ".file-item:hover { background: #f0f0f0; }",
            "a { color: #06c; text-decoration: none; }",
            "a:hover { text-decoration: underline; }",
            "button { background: #4CAF50; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; }",
            "button:hover { background: #45a049; }",
            "#progress { margin-top: 10px; display: none; }",
            "</style>",
            "</head><body>",
            "<h1>文件服务</h1>",
            "<div class='upload-box'>",
            "<h2>上传文件</h2>",
            "<form id='uploadForm' enctype='multipart/form-data'>",
            "<input type='file' id='fileInput' name='file'>",
            "<button type='button' onclick='uploadFile()'>上传</button>",
            "<div id='progress'>",
            "<div style='width: 100%; background: #ddd; border-radius: 4px;'>",
            "<div id='progressBar' style='height: 20px; width: 0%; background: #4CAF50; border-radius: 4px;'></div>",
            "</div>",
            "<div id='progressText'>0%</div>",
            "</div>",
            "</form>",
            "</div>",
            "<h2>文件列表</h2>",
            "<ul class='file-list'>",
            "</a>由软件ANTKit提供文件服务支持</a>"
        ]
        
 
        for name in list:
            fullname = os.path.join(path, name)
            if os.path.isdir(fullname):
                html.append(f"<li class='file-item'>📁 <a href='{name}'>{name}/</a></li>")
            else:
                html.append(f"<li class='file-item'>📄 <a href='{name}'>{name}</a></li>")

        html.extend([

    "</ul>",
    

    "<script>",
    "function uploadFile() {",
    "  const fileInput = document.getElementById('fileInput');",
    "  const progressDiv = document.getElementById('progress');",
    "  const progressBar = document.getElementById('progressBar');",
    "  const progressText = document.getElementById('progressText');",
    "  ",
    "  if (!fileInput.files.length) {",
    "    alert('请选择文件');", 
    "    return;",
    "  }",
    "  ",
    "  const file = fileInput.files[0];",
    "  const formData = new FormData();", 
    "  formData.append('file', file);",   
    "  ",
    "  progressDiv.style.display = 'block';",  # 进度条
    "  ",
    "  const xhr = new XMLHttpRequest();",
    "  xhr.open('POST', window.location.pathname, true);", 
    "  ",
 
    "  xhr.upload.onprogress = function(e) {",
    "    if (e.lengthComputable) {",
    "      const percent = Math.round((e.loaded / e.total) * 100);",
    "      progressBar.style.width = percent + '%';",
    "      progressText.textContent = percent + '%';",
    "    }",
    "  };",
    "  ",
    # 完成处理
    "  xhr.onload = function() {",
    "    if (xhr.status === 201) {",
    "      alert('上传成功');",
    "      location.reload();",  # 刷新文件列表
    "    } else {",
    "      alert('上传失败: ' + xhr.statusText);",
    "    }",
    "  };",
    "  ",
    # 错误处理
    "  xhr.onerror = function() {",
    "    alert('上传失败: 网络错误');",
    "  };",
    "  ",
    "  xhr.send(formData);", 
    "}",
    "</script>",
 
    "</body></html>"
])
        
   
        encoded = '\n'.join(html).encode('utf-8', 'surrogateescape')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        return BytesIO(encoded)
    
    def do_POST(self):
        try:
       
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_response(400, "Bad Request: Invalid content type")
                self.end_headers()
                return

            # 获取文件大小
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(411, "Length Required")
                self.end_headers()
                return

            form_data = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST'}
            )
            
            # 获取文件字段
            if 'file' not in form_data:
                self.send_response(400, "Bad Request: Missing file field")
                self.end_headers()
                return
                
            file_item = form_data['file']
            if not file_item.file:
                self.send_response(400, "Bad Request: Empty file")
                self.end_headers()
                return

  
            filename = file_item.filename
            if not filename:
                filename = f"upload_{int(time.time())}.dat"
            else:
             
                filename = os.path.basename(filename)
                filename = re.sub(r'[^\w.-]', '_', filename)

            filepath = os.path.join(self.shared_folder, filename)
            
            # 保存文件
            with open(filepath, 'wb') as f:
                while True:
                    chunk = file_item.file.read(64*1024)
                    if not chunk:
                        break
                    f.write(chunk)

            self.send_response(201, "Created")
            self.end_headers()
            self.wfile.write(b'File uploaded successfully')

        except Exception as e:
            self.send_response(500, f"Server Error: {str(e)}")
            self.end_headers()
class FileShareServer:

    global share_path, default_port
    def __init__(self, panel, shared_folder, port=default_port, password=None):

        self.panel = panel
        self.shared_folder = shared_folder
        self.port = port
        self.password = password
        self.server = None
        self.server_thread = None
        
 
        os.makedirs(self.shared_folder, exist_ok=True)
    
    def _event_handler(self, current, total, action, filename):
  
        evt = FileProgressEvent(
            current=current,
            total=total,
            action=action,
            filename=filename,
            progress=int((current / total) * 100) if total > 0 else 0
        )
        wx.PostEvent(self.panel, evt)
    
    def _run_server(self):
        """运行服务器线程"""
        handler = lambda *args: FileRequestHandler(
            *args,
            shared_folder=self.shared_folder,
            password=self.password,
            event_handler=self._event_handler
        )
        
        self.server = ThreadedHTTPServer(
    ('', self.port), 
    lambda *args, **kwargs: FileRequestHandler(
        *args,
        shared_folder=self.shared_folder,
        event_handler=self._event_handler,
        log_callback=self.panel.log_message, 
        **kwargs
    )
)
       
        evt = ServerStatusEvent(status='running', port=self.port)
        wx.PostEvent(self.panel, evt)
        
        try:
            self.server.serve_forever()
        except Exception as e:
            # 发送错误事件
            evt = ServerStatusEvent(status='error', message=str(e))
            wx.PostEvent(self.panel, evt)
        finally:
            self.server = None
    
    def start(self):
        """启动服务器"""
        if self.server_thread and self.server_thread.is_alive():
            return False
            
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.start()

        wx.CallAfter(self.panel.log_text.AppendText, f"服务器启动在以下地址:\n") 
        
        ip_addresses = []
        addrinfo = socket.getaddrinfo(socket.gethostname()  , None)
        for addr in addrinfo:
            ip_address = addr[4][0]
            ip_addresses.append(ip_address)
        for ip in ip_addresses:
            wx.CallAfter(self.panel.log_text.AppendText, f"{ip}:{self.port}\n")
        wx.CallAfter(self.panel.log_text.AppendText, f"已列出所有共享的网络。在同一网络的设备可以通过输入上述链接访问(一般只有一个链接可以被其他设备访问，可以每一个都试一遍，IP部分末尾不是1的更可能)\n") 
        if open_browser:
            # 打开浏览器
            hostname = socket.gethostname()
            webbrowser.open(f"http://localhost:{self.port}")
        return True
    
    def stop(self):
        """停止服务器"""
        if self.server:
        
            server = self.server
            server.shutdown()
            server.server_close()
            self.server_thread.join()
            
          
            evt = ServerStatusEvent(status='stopped')
            wx.PostEvent(self.panel, evt)
            return True
        return False

class FileSharePanel(wx.Panel):
    """文件共享面板"""
    
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition, 
                 size=wx.DefaultSize, style=wx.TAB_TRAVERSAL, name="FileSharePanel"):
        super().__init__(parent, id, pos, size, style, name)
        
     
        self.init_ui()
        
       
        self.Bind(EVT_FILE_PROGRESS, self.on_file_progress)
        self.Bind(EVT_SERVER_STATUS, self.on_server_status)
        
        
        self.server = None
    
    def log_message(self, message):
        wx.CallAfter(self.log_text.AppendText, f"{message}\n") 

    def init_ui(self):
      
        main_sizer = wx.BoxSizer(wx.VERTICAL)
      
        setting_box = wx.StaticBox(self, label="将文件夹共享到局域网中")
        setting_sizer = wx.StaticBoxSizer(setting_box, wx.VERTICAL)
        
 
        folder_sizer = wx.BoxSizer(wx.HORIZONTAL)
        folder_label = wx.StaticText(self, label="共享文件夹:")
        self.folder_path = wx.TextCtrl(self, value=os.path.expanduser(share_path))

        browse_btn = wx.Button(self, label="浏览...")
        browse_btn.SetBitmap(wx.Bitmap("./icons/view.png"), wx.LEFT)
        browse_btn.Bind(wx.EVT_BUTTON, self.on_browse_folder)
        folder_sizer.Add(folder_label, 0, wx.ALIGN_CENTER|wx.ALL, 5)
        folder_sizer.Add(self.folder_path, 1, wx.EXPAND|wx.ALL, 5)
        folder_sizer.Add(browse_btn, 0, wx.ALL, 5)
        
  
        port_sizer = wx.BoxSizer(wx.HORIZONTAL)
        port_label = wx.StaticText(self, label="端口号:")
        self.port_ctrl = wx.SpinCtrl(self, min=1024, max=65535, initial=default_port)
        port_sizer.Add(port_label, 0, wx.ALIGN_CENTER|wx.ALL, 5)
        port_sizer.Add(self.port_ctrl, 0, wx.ALL, 5)
        

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_btn = wx.Button(self, label="启动服务器")
        self.start_btn.SetBitmap(wx.Bitmap("./icons/run.png"), wx.LEFT)
        self.stop_btn = wx.Button(self, label="停止服务器")
        self.stop_btn.SetBitmap(wx.Bitmap("./icons/stop.png"), wx.LEFT)
        self.stop_btn.Disable()
        self.start_btn.Bind(wx.EVT_BUTTON, self.on_start_server)
        self.stop_btn.Bind(wx.EVT_BUTTON, self.on_stop_server)
        btn_sizer.Add(self.start_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.stop_btn, 0, wx.ALL, 5)
        

        setting_sizer.Add(folder_sizer, 0, wx.EXPAND|wx.ALL, 5)
        setting_sizer.Add(port_sizer, 0, wx.EXPAND|wx.ALL, 5)
        setting_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER|wx.ALL, 5)
        

        self.status_text = wx.StaticText(self, label="服务器未运行")
        self.url_text = wx.StaticText(self, label="访问URL: ")
        
        self.log_text = wx.TextCtrl(self, style=wx.TE_MULTILINE|wx.TE_READONLY)
        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.log_text.SetFont(font)
        

        main_sizer.Add(setting_sizer, 0, wx.EXPAND|wx.ALL, 5)
        main_sizer.Add(self.status_text, 0, wx.EXPAND|wx.ALL, 5)
        main_sizer.Add(self.url_text, 0, wx.EXPAND|wx.ALL, 5)
        main_sizer.Add(self.log_text, 1, wx.EXPAND|wx.ALL, 5)
        
        self.SetSizer(main_sizer)
        self.Layout()
    
    def on_browse_folder(self, event):
      
        default_path = self.folder_path.GetValue()
        dlg = wx.DirDialog(self, "选择共享文件夹", defaultPath=default_path, 
                          style=wx.DD_DEFAULT_STYLE|wx.DD_DIR_MUST_EXIST)
        
        if dlg.ShowModal() == wx.ID_OK:
            self.folder_path.SetValue(dlg.GetPath())
        dlg.Destroy()
    
    def on_start_server(self, event):
      
        folder = self.folder_path.GetValue()
        if not folder:
            self.log_message("错误: 请选择共享文件夹")
            return
            
        port = self.port_ctrl.GetValue()
        config['share_path'] = self.folder_path.GetValue()
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        # 创建文件夹======
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            self.log_message(f"错误: 无法创建共享文件夹: {str(e)}")
            return
        
        self.server = FileShareServer(
            panel=self,
            shared_folder=folder,
            port=port
        )
        
        if self.server.start():
            self.start_btn.Disable()
            self.stop_btn.Enable()
    
    def on_stop_server(self, event):
      
        if self.server:
            
            self.server.stop()
            self.status_text.SetLabel("服务器已停止")
            self.start_btn.Enable()
            self.stop_btn.Disable()
    
    def on_file_progress(self, event):
        """处理文件传输进度事件"""
        filename = event.filename
        action = "下载" if event.action == "download" else "上传"
        progress = event.progress
        status = "进行中" if progress < 100 else "完成"
        
        found = -1
        for i in range(self.progress_list.GetItemCount()):
            if (self.progress_list.GetItem(i, 1).GetText() == filename and 
                self.progress_list.GetItem(i, 0).GetText() == action):
                found = i
                break
        
        if found == -1:
            
            index = self.progress_list.InsertItem(self.progress_list.GetItemCount(), action)
            self.progress_list.SetItem(index, 1, filename)
            self.progress_list.SetItem(index, 2, f"{progress}%")
            self.progress_list.SetItem(index, 3, status)
        else:
            
            self.progress_list.SetItem(found, 2, f"{progress}%")
            self.progress_list.SetItem(found, 3, status)
        
        
        self.progress_list.EnsureVisible(self.progress_list.GetItemCount() - 1)
    
    def on_server_status(self, event):
        
        if event.status == 'running':
            self.status_text.SetLabel(f"服务器运行中 (端口: {event.port})")
            hostname = socket.gethostname()
            self.url_text.SetLabel(f"本地访问URL: http://127.0.0.1:{event.port}")
        elif event.status == 'stopped':
            self.status_text.SetLabel("服务器已停止")
            self.url_text.SetLabel("访问URL: ")
        elif event.status == 'error':
            self.status_text.SetLabel(f"服务器错误: {event.message}")
            self.log_message(f"服务器错误: {event.message}")
            self.start_btn.Enable()
            self.stop_btn.Disable()

class FileShareApp(wx.App):
  
    def OnInit(self):
        frame = wx.Frame(None, title="文件共享服务器", size=(600, 500))
        panel = FileSharePanel(frame)
        frame.Show()
        return True

if __name__ == "__main__":
    app = FileShareApp(False)
    app.MainLoop()