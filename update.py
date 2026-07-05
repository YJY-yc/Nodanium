# Copyright (c) 2024-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import requests,time,wx
import webbrowser
from bs4 import BeautifulSoup
def check_update(current_version):
    retries = 1
    timeout = 3  
    print(current_version)
    print("正在检查更新...")
    for attempt in range(retries):
        try:
            # 获取更新页面内容
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get("https://yjymain.rth1.xyz/Update.html", 
                                  timeout=timeout, headers=headers)
            response.raise_for_status()
            
            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            latest_version = soup.find('h2').text.strip()
            
            # 比较版本
            if latest_version != current_version:
                return True, latest_version
            else:
                return False, latest_version
                
        except requests.exceptions.RequestException as e:
            print(f"检查更新失败，尝试 {attempt + 1}/{retries}: {e}")
            if attempt < retries - 1:  # 如果不是最后一次尝试，等待后重试
                time.sleep(2)  # 等待2秒后重试
            else:
                # 最后一次尝试失败后，显示更详细的错误信息
                error_msg = f"无法连接到更新服务器，请检查：\n" \
                          f"1. 网络连接是否正常\n" \
                          f"2. 防火墙是否阻止了连接\n" \
                          f"3. 服务器是否正常运行\n" \
                          f"错误详情：{str(e)}"
                wx.MessageBox(error_msg, "检查更新失败", wx.OK | wx.ICON_ERROR)
                return False, None

def show_update_dialog(current_version):
    import wx
    app = wx.App()
    
    # 检查更新
    has_update, latest_version = check_update(current_version)
    
    if has_update:
        dlg = wx.MessageDialog(None, 
                             f"发现新版本 {latest_version}，是否立即更新？\n当前版本：{current_version}",
                             "发现更新",
                             wx.YES_NO | wx.ICON_INFORMATION)
        if dlg.ShowModal() == wx.ID_YES:
            webbrowser.open("https://yjymain.rth1.xyz/Update.html")
        dlg.Destroy()
    else:
        wx.MessageBox("当前已是最新版本", "检查更新", wx.OK | wx.ICON_INFORMATION)
    
    app.MainLoop()

# 示例用法
if __name__ == "__main__":
    current_version = "V3.1.5.4"  # 这里替换为你的当前版本号
    show_update_dialog(current_version)
