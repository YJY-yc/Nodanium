import wx
import wx.adv
import requests
import threading, os, time, shutil
from urllib.parse import urlparse
from pathlib import Path
from winotify import Notification, audio
from concurrent.futures import ThreadPoolExecutor

# 导入DownloadUI中的函数
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from DownloadUI import add_download_record, refresh_download_list, download_history, load_download_history, save_download_history

def get_download_dir():
    appdata_dir = os.getenv('APPDATA')
    config_path = os.path.join(appdata_dir, 'Nodanium', 'dir.txt')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except:
        return os.path.join(os.getcwd(), "downloads")

stop_download = False

def create_download_window(parent, urls, thread_count, main_site, download_dir, folder_name, list_ctrl=None, image_list=None):
   
    folder_path = os.path.join(download_dir, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    
    download_window = wx.Frame(parent, title=f"批量下载 - {folder_name}", size=(400, 300))
    panel = wx.Panel(download_window)
    vbox = wx.BoxSizer(wx.VERTICAL)
    
    new_gauge = wx.Gauge(panel, range=100)
    new_remaining_label = wx.StaticText(panel, label="剩余项: 0")
    new_undownloaded_list = wx.ListBox(panel, style=wx.LB_SINGLE)
    new_export_btn = wx.Button(panel, label="导出未下载列表")
    
    vbox.Add(new_gauge, 0, wx.ALL|wx.EXPAND, 10)
    vbox.Add(new_remaining_label, 0, wx.ALL|wx.CENTER, 5)
    vbox.Add(new_undownloaded_list, 1, wx.ALL|wx.EXPAND, 10)
    
    stop_btn = wx.Button(panel, label="停止下载")
    end_and_export_btn = wx.Button(panel, label="结束并导出")
    
    hbox = wx.BoxSizer(wx.HORIZONTAL)
    hbox.Add(new_export_btn, 0, wx.ALL|wx.CENTER, 5)
    hbox.Add(stop_btn, 0, wx.ALL|wx.CENTER, 5)
    hbox.Add(end_and_export_btn, 0, wx.ALL|wx.CENTER, 5)
    vbox.Add(hbox, 0, wx.ALL|wx.CENTER, 10)

    # 关键修复：将父窗口的download_items属性复制到新的下载窗口
    if hasattr(parent, 'download_items') and parent.download_items:
        download_window.download_items = parent.download_items

    def on_close(event):
        global stop_download
        stop_download = True
        download_window.Destroy()
    
    download_window.Bind(wx.EVT_CLOSE, on_close)
    new_export_btn.Bind(wx.EVT_BUTTON, lambda event: on_export(download_window, new_undownloaded_list))
    
    panel.SetSizer(vbox)
    download_window.Show()
    
    stop_btn.Bind(wx.EVT_BUTTON, lambda event: on_stop(download_window))
    end_and_export_btn.Bind(wx.EVT_BUTTON, lambda event: on_end_and_export(download_window, new_undownloaded_list))
    
    threading.Thread(
        target=start_download, 
        args=(urls, thread_count, new_gauge, new_remaining_label, new_undownloaded_list, main_site, folder_path, download_window, list_ctrl, image_list, folder_name)
    ).start()

def on_end_and_export(window, undownloaded_list):
    global stop_download
    stop_download = True
    wx.CallAfter(on_export, window, undownloaded_list)
    wx.CallAfter(window.Close)

def on_stop(window):
    global stop_download
    stop_download = True
    wx.MessageBox("下载已停止", "提示", wx.OK|wx.ICON_INFORMATION)
    window.Close()
def create_download_app():
    app = wx.App(False)
    frame = wx.Frame(None, title="批量下载", size=(600, 500))
    
    panel = wx.Panel(frame)
    vbox = wx.BoxSizer(wx.VERTICAL)
    frame.urls = []
    
    hbox0 = wx.BoxSizer(wx.HORIZONTAL)
    import_btn = wx.Button(panel, label="导入网址文件")
    hbox0.Add(import_btn, 0, wx.ALL|wx.CENTER, 5)
    vbox.Add(hbox0, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 10)
    
    appdata_dir = os.getenv('APPDATA')
    config_path = os.path.join(appdata_dir, 'Nodanium', 'dir.txt')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            download_dir = f.read().strip()
    except:
        download_dir = os.path.join(os.getcwd(), "downloads")
    
    # 添加文件夹名称输入框 - 修复：确保每个批量下载都有唯一名称
    hbox_folder = wx.BoxSizer(wx.HORIZONTAL)
    folder_label = wx.StaticText(panel, label="文件夹名称:")
    import uuid
    unique_id = str(uuid.uuid4())[:6]  # 生成唯一标识符
    folder_text = wx.TextCtrl(panel, value=f"批量下载_{time.strftime('%Y%m%d_%H%M%S')}_{unique_id}")
    hbox_folder.Add(folder_label, 0, wx.ALL|wx.CENTER, 5)
    hbox_folder.Add(folder_text, 1, wx.ALL|wx.EXPAND, 5)
    vbox.Add(hbox_folder, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 10)
    
    hbox3 = wx.BoxSizer(wx.HORIZONTAL)
    main_site_label = wx.StaticText(panel, label="主网站:")
    main_site_text = wx.TextCtrl(panel)
    hbox3.Add(main_site_label, 0, wx.ALL|wx.CENTER, 5)
    hbox3.Add(main_site_text, 1, wx.ALL|wx.EXPAND, 5)
    vbox.Add(hbox3, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 10)
    
    hbox2 = wx.BoxSizer(wx.HORIZONTAL)
    thread_label = wx.StaticText(panel, label="线程数:")
    thread_spin = wx.SpinCtrl(panel, min=1, max=10, initial=4)
    hbox2.Add(thread_label, 0, wx.ALL|wx.CENTER, 5)
    hbox2.Add(thread_spin, 1, wx.ALL|wx.EXPAND, 5)
    vbox.Add(hbox2, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 10)
    
    undownloaded_list = wx.ListBox(panel, style=wx.LB_SINGLE)
    vbox.Add(undownloaded_list, 1, wx.ALL|wx.EXPAND, 10)

    download_btn = wx.Button(panel, label="开始下载")
    vbox.Add(download_btn, 0, wx.ALL|wx.CENTER, 10)

    import_btn.Bind(wx.EVT_BUTTON, lambda event: frame.urls.extend(on_import(frame, undownloaded_list)))
    
    download_btn.Bind(wx.EVT_BUTTON, lambda event: create_download_window(
        frame, 
        frame.urls,  
        thread_spin.GetValue(), 
        main_site_text.GetValue(), 
        download_dir,
        folder_text.GetValue()
    ))
     
    panel.SetSizer(vbox)
    frame.Show()
    app.MainLoop()

def on_import(frame, undownloaded_list):
    with wx.FileDialog(frame, "选择网址文件", wildcard="Text files (*.txt)|*.txt|JSON files (*.json)|*.json",
                     style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
        if fileDialog.ShowModal() == wx.ID_CANCEL:
            return []
        
        path = fileDialog.GetPath()
        try:
            # 根据文件扩展名判断格式
            if path.lower().endswith('.json'):
                # JSON格式导入
                import json
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        urls = []
                        download_items = []  # 存储原始URL和文件名信息
                        for item in data:
                            if isinstance(item, dict) and 'url' in item:
                                url = item['url']
                                filename = item.get('filename', '')
                                # 存储原始URL，不添加备注信息
                                urls.append(url)
                                # 同时存储下载项目信息
                                download_items.append({"url": url, "filename": filename})
                        wx.MessageBox(f"成功导入 {len(urls)} 个网址", "提示", wx.OK|wx.ICON_INFORMATION)
                        undownloaded_list.Set(urls) 
                        # 将下载项目信息存储到frame中，供后续使用
                        frame.download_items = download_items
                        return urls
                    else:
                        wx.MessageBox("JSON格式错误：应为数组格式", "错误", wx.OK|wx.ICON_ERROR)
                        return []
            else:
                # 原有TXT格式导入
                with open(path, 'r', encoding='utf-8') as f:
                    urls = [line.strip() for line in f if line.strip()]
                    wx.MessageBox(f"成功导入 {len(urls)} 个网址", "提示", wx.OK|wx.ICON_INFORMATION)
                    undownloaded_list.Set(urls) 
                    return urls
        except json.JSONDecodeError as e:
            wx.MessageBox(f"JSON解析失败: {str(e)}", "错误", wx.OK|wx.ICON_ERROR)
            return []
        except Exception as e:
            wx.MessageBox(f"导入文件失败: {str(e)}", "错误", wx.OK|wx.ICON_ERROR)
            return []
        



def on_export(frame, undownloaded_list):
    undownloaded_urls = undownloaded_list.GetItems()
    if not undownloaded_urls:
        wx.MessageBox("没有未下载的网址", "提示", wx.OK|wx.ICON_INFORMATION)
        return
    
    with wx.FileDialog(frame, "保存未下载列表", wildcard="Text files (*.txt)|*.txt",
                     style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
        if fileDialog.ShowModal() == wx.ID_CANCEL:
            return
        
        path = fileDialog.GetPath()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(undownloaded_urls))
            wx.MessageBox("未下载列表导出成功", "提示", wx.OK|wx.ICON_INFORMATION)
        except Exception as e:
            wx.MessageBox(f"导出失败: {str(e)}", "错误", wx.OK|wx.ICON_ERROR)
def start_download(urls, thread_count, gauge, remaining_label, undownloaded_list, main_site, download_dir, window, list_ctrl=None, image_list=None, folder_name=""):
    global stop_download
    stop_download = False
    
    if not urls:
        wx.MessageBox("请先导入网址文件", "错误", wx.OK|wx.ICON_ERROR)
        return
    
    # 在下载开始时添加批量下载记录（仅在list_ctrl和image_list不为None时）
    if list_ctrl and image_list:
        # 解析URL列表，提取URL和文件名信息
        download_items = []
        
        # 检查是否有预先存储的下载项目信息（来自JSON导入）
        if hasattr(window, 'download_items') and window.download_items:
            download_items = window.download_items
        else:
            # 如果没有预先存储的信息，使用原有解析逻辑
            for url_item in urls:
                url = url_item
                filename = ""
                
                # 解析JSON格式的备注信息（兼容旧格式）
                if " (文件名: " in url_item and url_item.endswith(")"):
                    parts = url_item.split(" (文件名: ")
                    if len(parts) == 2:
                        url = parts[0]
                        filename = parts[1][:-1]  # 去掉末尾的括号
                
                download_items.append({"url": url, "filename": filename})
        
        # 修复：保存路径应该是父目录，而不是具体的子文件夹路径
        parent_dir = os.path.dirname(download_dir)
        
        # 为每个批量下载记录生成唯一标识符
        import uuid
        batch_id = str(uuid.uuid4())  # 使用完整UUID作为唯一标识
        
        # 确保download_history已经被正确加载
        if not download_history:
            load_download_history()
            print("在添加记录前强制加载download_history")
        
        # 添加批量下载文件夹记录，包含项目列表信息和唯一标识
        folder_record = add_download_record(
            url="批量下载文件夹", 
            filename=folder_name, 
            save_path=parent_dir,  # 修改为父目录
            status="N/A", 
            file_size=0,
            download_items=download_items,  # 添加下载项目列表
            batch_id=batch_id  # 添加唯一标识符
        )
        refresh_download_list(list_ctrl, image_list)
    else:
        # 如果没有list_ctrl和image_list，只进行下载不添加记录
        print("独立下载模式：不添加下载记录到主界面")
    
    if main_site and not main_site.endswith('/'):
        main_site += '/'

    wx.CallAfter(undownloaded_list.Set, urls)
    
    total = len(urls)
    completed = 0
    
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = []
        for item in download_items:
            if stop_download:  
                break
            
            current_url = item['url']
            item_filename = item.get('filename', '')  # 获取对应的文件名
            
            if main_site and not current_url.startswith('http'):
                current_url = main_site + current_url
            
            # 确保这里传递的是item_filename作为第四个参数
            future = executor.submit(download_file, current_url, download_dir, False, item_filename)
            futures.append((current_url, future))
        
        while completed < total and not stop_download:
            for url_future in futures:
                current_url, future = url_future
                if future.done():
                    completed += 1
                    result = future.result()
                    if result:
                        # 修复：直接使用URL字符串进行匹配删除
                        try:
                            index = undownloaded_list.FindString(current_url)
                            if index != wx.NOT_FOUND:
                                wx.CallAfter(undownloaded_list.Delete, index)
                        except Exception as e:
                            print(f"删除URL失败: {current_url}, 错误: {e}")
                    progress = int(completed/total*100)
                    wx.CallAfter(gauge.SetValue, progress)
                    wx.CallAfter(remaining_label.SetLabel, f"剩余项: {total - completed}")
                   
                    futures.remove(url_future)
            wx.MilliSleep(50)
    
    # 下载完成后更新文件夹状态（仅在list_ctrl和image_list不为None时）
    if list_ctrl and image_list:
        # 增强文件夹统计：计算文件数量、文件夹大小等详细信息
        folder_stats = {
            "file_count": 0,
            "folder_size": 0,
            "success_count": 0,
            "failed_count": 0
        }
        
        if os.path.exists(download_dir):
            for root, dirs, files in os.walk(download_dir):
                folder_stats["file_count"] += len(files)
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        folder_stats["folder_size"] += os.path.getsize(file_path)
                        folder_stats["success_count"] += 1
                    except:
                        folder_stats["failed_count"] += 1
        
        # 修复：避免重新导入模块导致历史数据重置
        try:
            # 使用之前导入的模块函数，避免重新导入
            print(f"开始更新记录，batch_id: {batch_id}, folder_name: {folder_name}")
            
            # 确保download_history已经被正确加载
            if not download_history:
                load_download_history()
                
            print(f"当前记录数量: {len(download_history)}")
            
            # 备份当前历史记录数量，用于检测是否被重置
            initial_count = len(download_history)
            
            # 确定下载状态：如果被中途停止，状态为"已停止"，否则为"已完成"
            final_status = "已停止" if stop_download else "已完成"
            print(f"下载状态: {final_status}, 完成数量: {completed}/{total}")
            
            # 方法1：优先使用batch_id匹配
            updated = False
            for i, record in enumerate(download_history):
                record_batch_id = record.get("batch_id")
                if record_batch_id and record_batch_id == batch_id:
                    print(f"找到batch_id匹配的记录，索引: {i}")
                    record["status"] = final_status
                    record["file_size"] = folder_stats["folder_size"]
                    # 添加文件夹统计信息
                    record["file_count"] = folder_stats["file_count"]
                    record["success_count"] = folder_stats["success_count"]
                    record["failed_count"] = folder_stats["failed_count"]
                    # 添加完成进度信息
                    record["completed"] = completed
                    record["total"] = total
                    updated = True
                    print(f"记录更新成功: {record}")
                    break
            
            # 方法2：如果batch_id匹配失败，使用文件夹名称和URL匹配
            if not updated:
                print("batch_id匹配失败，尝试文件夹名称匹配")
                for i, record in enumerate(download_history):
                    if (record.get("filename") == folder_name and 
                        record.get("url") == "批量下载文件夹"):
                        print(f"找到文件夹名称匹配的记录，索引: {i}")
                        record["status"] = final_status
                        record["file_size"] = folder_stats["folder_size"]
                        # 添加文件夹统计信息
                        record["file_count"] = folder_stats["file_count"]
                        record["success_count"] = folder_stats["success_count"]
                        record["failed_count"] = folder_stats["failed_count"]
                        record["completed"] = completed
                        record["total"] = total
                        # 确保batch_id被正确设置
                        if "batch_id" not in record:
                            record["batch_id"] = batch_id
                        updated = True
                        print(f"记录更新成功: {record}")
                        break
            
            # 方法3：如果仍然失败，检查历史记录是否被重置
            if not updated:
                print("前两种方法都失败，检查历史记录状态")
                current_count = len(download_history)
                if current_count < initial_count:
                    print(f"警告：历史记录数量从{initial_count}减少到{current_count}，可能被重置")
                    # 重新加载历史记录
                    load_download_history()
                    print(f"重新加载后记录数量: {len(download_history)}")
                    
                    # 重新尝试匹配
                    for i, record in enumerate(download_history):
                        record_batch_id = record.get("batch_id")
                        if record_batch_id and record_batch_id == batch_id:
                            print(f"重新加载后找到batch_id匹配的记录，索引: {i}")
                            record["status"] = final_status
                            record["file_size"] = folder_stats["folder_size"]
                            # 添加文件夹统计信息
                            record["file_count"] = folder_stats["file_count"]
                            record["success_count"] = folder_stats["success_count"]
                            record["failed_count"] = folder_stats["failed_count"]
                            record["completed"] = completed
                            record["total"] = total
                            updated = True
                            break
            
            # 方法4：如果仍然失败，直接通过索引更新最后一条匹配的记录
            if not updated:
                print("重新加载后仍然匹配失败，尝试索引匹配")
                # 查找最近添加的批量下载记录
                for i in range(len(download_history)-1, -1, -1):
                    record = download_history[i]
                    if record.get("url") == "批量下载文件夹":
                        print(f"找到索引匹配的记录，索引: {i}")
                        record["status"] = final_status
                        record["file_size"] = folder_stats["folder_size"]
                        # 添加文件夹统计信息
                        record["file_count"] = folder_stats["file_count"]
                        record["success_count"] = folder_stats["success_count"]
                        record["failed_count"] = folder_stats["failed_count"]
                        record["completed"] = completed
                        record["total"] = total
                        record["batch_id"] = batch_id  # 确保设置batch_id
                        updated = True
                        print(f"记录更新成功: {record}")
                        break
            
            if not updated:
                print("警告：未能找到匹配的记录进行更新")
                # 作为最后手段，添加新记录
                add_download_record(
                    url="批量下载文件夹", 
                    filename=folder_name, 
                    save_path=parent_dir,
                    status=final_status, 
                    file_size=folder_stats["folder_size"],
                    download_items=download_items,
                    batch_id=batch_id,
                    completed=completed,
                    total=total,
                    file_count=folder_stats["file_count"],
                    success_count=folder_stats["success_count"],
                    failed_count=folder_stats["failed_count"]
                )
                print("已创建新记录")
            else:
                save_download_history()
            
        except Exception as e:
            print(f"更新记录时发生错误: {e}")
            # 错误处理：无论如何都要保存记录
            import traceback
            traceback.print_exc()
        
        refresh_download_list(list_ctrl, image_list)
    wx.CallAfter(gauge.Hide)
    wx.CallAfter(remaining_label.Hide)
    wx.CallAfter(undownloaded_list.Show)
    wx.CallAfter(undownloaded_list.SetFocus)
    wx.CallAfter(window.Layout)


def download_file(url, download_dir, add_single_record=True, filename=""):
    try:
        if stop_download:  
            return False
            
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        headers = {"user-agent": ua}
        
        response = requests.get(url, stream=True, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"下载失败: {url} 状态码: {response.status_code}")
            return False
            
        os.makedirs(download_dir, exist_ok=True)
        
        # 优先使用传入的filename参数
        if not filename:  
            filename = os.path.basename(url)
            if not filename:
                filename = "download_" + str(int(time.time())) + ".bin"
        local_path = os.path.join(download_dir, filename)
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*8):
                if chunk:
                    if stop_download:
                        f.close()
                        os.remove(local_path)
                        return False
                    f.write(chunk)
        
        print(f"文件保存成功: {local_path}")
        wx.CallAfter(show_download_complete_notification, local_path)
        
        # 修改：只有在不是批量下载时才添加单个文件记录
        if add_single_record:
            import sys
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from DownloadUI import add_download_record, refresh_download_list
            add_download_record(url, filename, download_dir, "已完成", os.path.getsize(local_path))
        
        # 修改：只有在不是批量下载时才添加单个文件记录
        if add_single_record:
            import sys
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from DownloadUI import add_download_record, refresh_download_list
            add_download_record(url, filename, download_dir, "已完成", os.path.getsize(local_path))
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"下载请求失败: {url} 错误: {str(e)}")
        return False
    except IOError as e:
        print(f"文件保存失败: {url} 错误: {str(e)}")
        return False
    except Exception as e:
        print(f"未知错误: {url} 错误: {str(e)}")
        return False
def show_download_complete_notification(local_path):
    toast = Notification(
        app_id="Advanced Network Toolset",
        title="下载完成",
        msg=f"文件已保存到：{local_path}",
        duration="long"
    )
    toast.set_audio(audio.Default, loop=False)
    toast.show()

if __name__ == "__main__":
    create_download_app()