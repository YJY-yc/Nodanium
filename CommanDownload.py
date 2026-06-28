import wx
import os
import requests
from wx import MessageBox, ProgressDialog
from winotify import Notification, audio
def download_file(url, local_path, headers=None):
    global dirs
    print(headers)
    
    if headers is None or len(headers) <5:
        print("使用默认请求头")
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        headers = {"user-agent": ua}
    else:
        headers = {"user-agent": headers}
    try:
        response = requests.get(url, stream=True,headers=headers)
    except Exception as e:
        print(str(e))
        MessageBox(f"获取失败:\n{str(e)}\n请检查网络、链接是否正确 或请求头是否正确", "错误", wx.OK | wx.ICON_ERROR)
        return

    
    if response.status_code == 200:
        content_size = 0xffffff
        try:
            content_size = int(response.headers['content-length'])
        except:
            print("文件大小未知")
        
       
        progress = ProgressDialog("下载中", f"正在下载 {local_path}\n请求头：{headers}", maximum=content_size,
                                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT)
        
        wr = 0
        try:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*8):
                    if chunk:
                        wr += len(chunk)
                        (keepGoing, skip) = progress.Update(wr)
                        if not keepGoing:
                            break
                        f.write(chunk)
            
            print("文件下载成功，保存在：", local_path)
            progress.Destroy()
            toast = Notification(
                app_id="Advanced Network Toolset",
                title="下载完成",
                msg=f"文件已保存到：{local_path}",
                duration="long"
            )
            toast.set_audio(audio.Default, loop=False)
            
            toast.show()

           
            dlg = wx.MessageDialog(None, f"文件已保存到：\n{local_path}", "下载完成", 
                                 wx.OK | wx.CANCEL | wx.ICON_INFORMATION)
            dlg.SetOKLabel("打开文件")
            cancel_btn = dlg.FindWindowById(wx.ID_CANCEL)
            if dlg.ShowModal() == wx.ID_OK:
                
                os.startfile(local_path)
            dlg.Destroy()
            return 0
        except Exception as e:
            MessageBox(f"保存文件失败:\n{str(e)}\n请检查保存位置是否已满或有无权限", "错误", wx.OK | wx.ICON_ERROR)
    else:
        print("文件下载失败，状态码：", response.status_code)
        MessageBox( f"错误:{str(response.status_code)}请不要关闭下载界面", "错误", wx.OK | wx.ICON_ERROR)
