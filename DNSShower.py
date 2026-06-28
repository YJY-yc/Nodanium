import wx
import subprocess
import os
import dns.resolver
dns_list = None
panel = None
import time
import dns.resolver


def resolve_dns(domain):
    """
    使用系统设置的 DNS 地址解析 DNS 记录
    参数:
        domain: 要解析的域名
    返回:
        包含 DNS 记录的字典
    """
    result = {
        'A': [],
        'AAAA': [],
        'CNAME': []
    }
    start_time = time.time()

    resolver = dns.resolver.Resolver()

    try:
        
        answers = resolver.resolve(domain, 'A')
        for rdata in answers:
            result['A'].append(rdata.address)

      
        answers = resolver.resolve(domain, 'AAAA')
        for rdata in answers:
            result['AAAA'].append(rdata.address)

     
        try:
            answers = resolver.resolve(domain, 'CNAME')
            for rdata in answers:
                result['CNAME'].append(rdata.target.to_text().rstrip('.'))
        except dns.resolver.NoAnswer:
            pass

    except dns.resolver.NXDOMAIN:
        raise Exception("域名不存在")
    except dns.resolver.NoAnswer:
        pass
    except Exception as e:
        raise Exception(f"DNS 解析失败: {str(e)}")

    result['lookup_time'] = f"{(time.time() - start_time) * 1000:.2f}ms"
    return result

def on_add_dns(event):

    dlg = wx.Dialog(panel, title="添加DNS记录", size=(400, 300))
    vbox = wx.BoxSizer(wx.VERTICAL)
    

    hostname_label = wx.StaticText(dlg, label="主机名(如xxx.com):")
    hostname_ctrl = wx.TextCtrl(dlg)

    ip_label = wx.StaticText(dlg, label="IP地址(形如xxx.xxx.xxx.xxx):")
    ip_ctrl = wx.TextCtrl(dlg)

    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    ok_btn = wx.Button(dlg, label="确定")
    cancel_btn = wx.Button(dlg, label="取消")
    
    def on_ok(event):
  
        hostname = hostname_ctrl.GetValue().strip()
        ip = ip_ctrl.GetValue().strip()
        
        if not hostname or not ip:
            wx.MessageBox("主机名和IP地址不能为空", "错误", wx.OK|wx.ICON_ERROR)
            return
        confirm_dlg = wx.MessageDialog(dlg, 
                                 "确定要添加此DNS记录吗？添加此DNS到host文件可能导致无法访问某些网站或应用程序。除非你知道你在做什么，否则请不要添加此DNS记录。\n\n", 
                                 "",
                                 wx.YES_NO|wx.ICON_WARNING)
        confirm_dlg.SetYesNoLabels("我知道我在做什么", "取消")
        if confirm_dlg.ShowModal() != wx.ID_YES:
            return
        try:
  
            with open(r'C:\Windows\System32\drivers\etc\hosts', 'a') as f:
                f.write(f"\n{ip}\t{hostname}") 
            idx = dns_list.InsertItem(dns_list.GetItemCount(), hostname)
            dns_list.SetItem(idx, 1, ip)
            dns_list.SetItem(idx, 2, "N/A") 
            subprocess.run(['ipconfig', '/flushdns'], capture_output=True)
            
            wx.MessageBox("DNS记录已添加并生效", "成功", wx.OK|wx.ICON_INFORMATION)
            dlg.EndModal(wx.ID_OK)
            
        except PermissionError:
            wx.MessageBox("需要管理员权限才能修改hosts文件", "错误", wx.OK|wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"添加DNS记录失败: {str(e)}", "错误", wx.OK|wx.ICON_ERROR)
    
    ok_btn.Bind(wx.EVT_BUTTON, on_ok)
    cancel_btn.Bind(wx.EVT_BUTTON, lambda e: dlg.EndModal(wx.ID_CANCEL))
    
    btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
    btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
    
    # 布局
    vbox.Add(hostname_label, 0, wx.ALL, 5)
    vbox.Add(hostname_ctrl, 0, wx.EXPAND|wx.ALL, 5)
    vbox.Add(ip_label, 0, wx.ALL, 5)
    vbox.Add(ip_ctrl, 0, wx.EXPAND|wx.ALL, 5)
    vbox.Add(btn_sizer, 0, wx.ALIGN_CENTER|wx.ALL, 10)
    
    dlg.SetSizer(vbox)
    dlg.ShowModal()

def init_dns_tab(p):
    global dns_list, panel
    panel = p  
    vbox = wx.BoxSizer(wx.VERTICAL)
    title_label = wx.StaticText(panel, label="编辑与管理DNS")
    parent_font = p.GetFont()
    title_font = parent_font.Scaled(1.2)
    title_label.SetFont(title_font)
    vbox.Add(title_label, 0, wx.ALL | wx.EXPAND, 10)
    dns_list = wx.ListCtrl(panel, style=wx.LC_REPORT|wx.LC_SINGLE_SEL)
    dns_list.InsertColumn(0, '主机名', width=300)
    dns_list.InsertColumn(1, 'IP地址', width=150)
    dns_list.InsertColumn(2, 'TTL', width=100)
    dns_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, on_dns_item_double_click)
    # 按钮区域

    if os.path.exists("./icons/add.png"):
        try:
            modify_btn = wx.BitmapButton(panel, bitmap=wx.Bitmap("./icons/add.png"))
            modify_btn.SetToolTip("添加DNS")
        except:
            modify_btn = wx.Button(panel, label="添加DNS")
    else:
        modify_btn = wx.Button(panel, label="添加DNS")
        
    if os.path.exists("./icons/reload.png"):
        try:
            refresh_btn = wx.BitmapButton(panel, bitmap=wx.Bitmap("./icons/reload.png"))
            refresh_btn.SetToolTip("刷新")
        except:
            refresh_btn = wx.Button(panel, label="刷新")
    else:
        refresh_btn = wx.Button(panel, label="刷新")
    if os.path.exists("./icons/flush.png"):
        try:
            flush_btn = wx.BitmapButton(panel, bitmap=wx.Bitmap("./icons/flush.png"))
            flush_btn.SetToolTip("清空缓存")
        except:
            flush_btn = wx.Button(panel, label="清空缓存")
    else:
        flush_btn = wx.Button(panel, label="清空缓存")


    hbox = wx.BoxSizer(wx.HORIZONTAL)
    if os.path.exists("./icons/delete.png"):
        try:
            remove_btn = wx.BitmapButton(panel, bitmap=wx.Bitmap("./icons/delete.png"))
            remove_btn.SetToolTip("删除记录")
        except:
            remove_btn = wx.Button(panel, label="删除记录")
    else:
        remove_btn = wx.Button(panel, label="删除记录")
    #remove_btn = wx.Button(panel, label="删除记录")
    if os.path.exists("./icons/resolve_dns.png"):
        try:
            resolve_btn = wx.BitmapButton(panel, bitmap=wx.Bitmap("./icons/resolve_dns.png"))
            resolve_btn.SetToolTip("解析DNS")
        except:
            resolve_btn = wx.Button(panel, label="解析DNS")
    else:
        resolve_btn = wx.Button(panel, label="解析DNS")


    #resolve_btn = wx.Button(panel, label="解析DNS") 
    if os.path.exists("./icons/init.png"):
        try:
            init_btn = wx.BitmapButton(panel, bitmap=wx.Bitmap("./icons/init.png"))
            init_btn.SetToolTip("初始化DNS")
        except:
            init_btn = wx.Button(panel, label="初始化DNS")
    else:
        init_btn = wx.Button(panel, label="初始化DNS")

    #init_btn = wx.Button(panel, label="初始化DNS") 
    
    hbox.Add(refresh_btn, 0, wx.ALL, 5)
    hbox.Add(flush_btn, 0, wx.ALL, 5)
    hbox.Add(init_btn, 0, wx.ALL, 5)
    hbox.Add(remove_btn, 0, wx.ALL, 5)
    hbox.Add(resolve_btn, 0, wx.ALL, 5)
    hbox.Add(modify_btn, 0, wx.ALL, 5) 
    vbox.Add(dns_list, 1, wx.EXPAND|wx.ALL, 10)
    vbox.Add(hbox, 0, wx.ALL|wx.CENTER, 10)
    def on_resolve_dns(event):
        dlg = wx.TextEntryDialog(panel, '请输入要解析的域名:', 'DNS解析')
        if dlg.ShowModal() == wx.ID_OK:
            domain = dlg.GetValue()
            try:
                result = resolve_dns(domain)
                msg = f"{domain}的DNS解析结果:\n\n"
                for record_type, records in result.items():
                    if records:
                        msg += f"{record_type}记录: {records}\n"
                
                # 创建可滚动的对话框
                result_dlg = wx.Dialog(panel, title="DNS解析结果", size=(500, 400))
                vbox = wx.BoxSizer(wx.VERTICAL)
                
                # 添加文本控件显示结果
                text_ctrl = wx.TextCtrl(result_dlg, style=wx.TE_MULTILINE|wx.TE_READONLY, value=msg)
                vbox.Add(text_ctrl, 1, wx.EXPAND|wx.ALL, 10)
                
                # 添加复制按钮
                hbox = wx.BoxSizer(wx.HORIZONTAL)
                copy_btn = wx.Button(result_dlg, label="复制结果")
                close_btn = wx.Button(result_dlg, label="关闭")
                
                def on_copy(event):
                    if wx.TheClipboard.Open():
                        wx.TheClipboard.SetData(wx.TextDataObject(msg))
                        wx.TheClipboard.Close()
                        wx.MessageBox("已复制到剪贴板", "提示", wx.OK|wx.ICON_INFORMATION)
                
                copy_btn.Bind(wx.EVT_BUTTON, on_copy)
                close_btn.Bind(wx.EVT_BUTTON, lambda e: result_dlg.EndModal(wx.ID_OK))
                
                hbox.Add(copy_btn, 0, wx.ALL, 5)
                hbox.Add(close_btn, 0, wx.ALL, 5)
                vbox.Add(hbox, 0, wx.ALIGN_CENTER|wx.BOTTOM, 10)
                
                result_dlg.SetSizer(vbox)
                result_dlg.ShowModal()
                
            except Exception as e:
                wx.MessageBox(str(e), "错误", wx.OK|wx.ICON_ERROR)
        dlg.Destroy()
    resolve_btn.Bind(wx.EVT_BUTTON, on_resolve_dns)
    modify_btn.Bind(wx.EVT_BUTTON, on_add_dns)
    # 功能实现
    def on_init_dns(event):
        """初始化DNS按钮处理函数"""
        confirm_dlg = wx.MessageDialog(panel, 
                                 "确定要初始化DNS记录吗？初始DNS将会覆盖当前的hosts文件内容，导致部分软件添加的DNS记录失效，或部分网页无法访问。除非你知道你在做什么，否则请不要初始化DNS记录。\n\n", 
                                 "",
                                 wx.YES_NO|wx.ICON_WARNING)
        confirm_dlg.SetYesNoLabels("我知道我在做什么", "取消")
        if confirm_dlg.ShowModal() != wx.ID_YES:
            return
        try:
            # 导入host.py文件中的host变量
            from host import host
            
            # 以管理员权限写入hosts文件
            with open(r'C:\Windows\System32\drivers\etc\hosts', 'w') as f:
                f.write(host)
            
            # 刷新DNS缓存
            subprocess.run(['ipconfig', '/flushdns'], capture_output=True)
            
            wx.MessageBox("DNS已成功初始化", "成功", wx.OK|wx.ICON_INFORMATION)
            refresh_dns_list()  # 刷新列表显示
            
        except PermissionError:
            wx.MessageBox("需要管理员权限才能修改hosts文件", "错误", wx.OK|wx.ICON_ERROR)
        except ImportError:
            wx.MessageBox("未找到host.py文件或host变量", "错误", wx.OK|wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"初始化DNS失败: {str(e)}", "错误", wx.OK|wx.ICON_ERROR)


    init_btn.Bind(wx.EVT_BUTTON, on_init_dns)
    def get_dns_cache():
        try:
    
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            result = subprocess.run(
                ['ipconfig', '/displaydns'],
                capture_output=True, 
                text=True,
                startupinfo=startupinfo
            )
            
            if result.returncode != 0:
                wx.MessageBox(
                    "获取DNS缓存失败，请尝试以管理员权限运行程序\n错误信息: " + result.stderr,
                    "错误", 
                    wx.OK|wx.ICON_ERROR
                )
                return ""
                
            return result.stdout
            
        except Exception as e:
            wx.MessageBox(
                f"执行命令失败: {str(e)}\n请确保ipconfig命令可用", 
                "错误", 
                wx.OK|wx.ICON_ERROR
            )
            return ""
        


    def parse_dns_cache(output):
        records = []
        lines = output.split('\n')
        current_record = {}
        
        for line in lines:
            line_lower = line.lower()
            
            if 'record name' in line_lower or '记录名称' in line_lower:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current_record['name'] = parts[1].strip()
            elif 'record type' in line_lower or '记录类型' in line_lower and current_record:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current_record['type'] = parts[1].strip()
            elif 'time to live' in line_lower or '生存时间' in line_lower and current_record:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current_record['ttl'] = parts[1].strip()
            elif 'data' in line_lower or '数据' in line_lower and current_record:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current_record['data'] = parts[1].strip()
                    records.append(current_record)
                    current_record = {}
        
        return records
    def parse_hosts_file():
        """解析hosts文件中的DNS记录"""
        records = []
        try:
            with open(r'C:\Windows\System32\drivers\etc\hosts', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'): 
                        parts = line.split()
                        if len(parts) >= 2: 
                            ip = parts[0]
                            for hostname in parts[1:]:
                                if not hostname.startswith('#'):  
                                    records.append({
                                        'name': hostname,
                                        'data': ip,
                                        'ttl': 'HOST'  
                                    })
        except Exception as e:
            wx.MessageBox(f"读取hosts文件失败: {str(e)}", "错误", wx.OK|wx.ICON_ERROR)
        return records
        
    def refresh_dns_list(event=None):
        dns_list.DeleteAllItems()
        
        # 获取并显示DNS缓存
        cache = get_dns_cache()
        records = parse_dns_cache(cache)
        for record in records:
            idx = dns_list.InsertItem(dns_list.GetItemCount(), record.get('name', ''))
            dns_list.SetItem(idx, 1, record.get('data', ''))
            dns_list.SetItem(idx, 2, record.get('ttl', ''))
        

        hosts_records = parse_hosts_file()
        for record in hosts_records:
            idx = dns_list.InsertItem(dns_list.GetItemCount(), record.get('name', ''))
            dns_list.SetItem(idx, 1, record.get('data', ''))
            dns_list.SetItem(idx, 2, record.get('ttl', ''))
    def flush_dns_cache(event):
        try:
            
            subprocess.run(['ipconfig', '/flushdns'], capture_output=True)
            wx.MessageBox("DNS缓存已清空", "成功", wx.OK|wx.ICON_INFORMATION)
            refresh_dns_list()
        except Exception as e:
            wx.MessageBox(f"清空DNS缓存失败: {str(e)}", "错误", wx.OK|wx.ICON_ERROR)
    

    def remove_dns_record(event):
        selected = dns_list.GetFirstSelected()
        if selected != -1:
            # 获取要删除的记录信息
            hostname = dns_list.GetItem(selected, 0).GetText()
            ip = dns_list.GetItem(selected, 1).GetText()

            try:
                
                hosts_path = r'C:\Windows\System32\drivers\etc\hosts'
                with open(hosts_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

            
                new_lines = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] == hostname and parts[0] == ip:
                            continue  # 跳过要删除的记录
                    new_lines.append(line + '\n')

                # 将更新后的内容写回 hosts 文件
                with open(hosts_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)

                # 刷新 DNS 缓存
                subprocess.run(['ipconfig', '/flushdns'], capture_output=True)

                # 删除列表中的记录
                dns_list.DeleteItem(selected)

                wx.MessageBox("DNS 记录已删除", "成功", wx.OK | wx.ICON_INFORMATION)
            except PermissionError:
                wx.MessageBox("需要管理员权限才能修改 hosts 文件", "错误", wx.OK | wx.ICON_ERROR)
            except Exception as e:
                wx.MessageBox(f"删除 DNS 记录失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("请先选择一条记录", "提示", wx.OK | wx.ICON_INFORMATION)

    
    refresh_btn.Bind(wx.EVT_BUTTON, refresh_dns_list)
    flush_btn.Bind(wx.EVT_BUTTON, flush_dns_cache)

    remove_btn.Bind(wx.EVT_BUTTON, remove_dns_record)
    
    panel.SetSizer(vbox)
    refresh_dns_list()  


def on_dns_item_double_click(event):
    item = event.GetItem()
    hostname = item.GetText()
    ip = dns_list.GetItem(item.GetId(), 1).GetText()
    ttl = dns_list.GetItem(item.GetId(), 2).GetText()
    
    # 分割IP字符串（如果有多个IP）
    ip_list = ip.split(', ')
    
    dlg = wx.Dialog(panel, title="DNS记录详情", size=(400, 300))
    vbox = wx.BoxSizer(wx.VERTICAL)
    
    # 主机名部分
    hostname_box = wx.StaticBox(dlg, label="主机名")
    hostname_sizer = wx.StaticBoxSizer(hostname_box, wx.VERTICAL)
    hostname_text = wx.StaticText(dlg, label=hostname)
    hostname_sizer.Add(hostname_text, 0, wx.ALL|wx.EXPAND, 5)
    
    # IP地址部分 - 改为显示所有IP
    ip_box = wx.StaticBox(dlg, label=f"IP地址 ({len(ip_list)}个)")
    ip_sizer = wx.StaticBoxSizer(ip_box, wx.VERTICAL)
    
    # 为每个IP创建单独的StaticText
    for i, single_ip in enumerate(ip_list, 1):
        ip_text = wx.StaticText(dlg, label=f"{i}. {single_ip.strip()}")
        ip_sizer.Add(ip_text, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
    
    # TTL部分
    ttl_box = wx.StaticBox(dlg, label="TTL (生存时间)")
    ttl_sizer = wx.StaticBoxSizer(ttl_box, wx.VERTICAL)
    ttl_text = wx.StaticText(dlg, label=f"{ttl} 秒")
    ttl_sizer.Add(ttl_text, 0, wx.ALL|wx.EXPAND, 5)
    
    vbox.Add(hostname_sizer, 0, wx.EXPAND|wx.ALL, 10)
    vbox.Add(ip_sizer, 0, wx.EXPAND|wx.ALL, 10)
    vbox.Add(ttl_sizer, 0, wx.EXPAND|wx.ALL, 10)
    
    # 添加关闭按钮
    close_btn = wx.Button(dlg, label="关闭")
    close_btn.Bind(wx.EVT_BUTTON, lambda e: dlg.EndModal(wx.ID_OK))
    vbox.Add(close_btn, 0, wx.ALIGN_CENTER|wx.ALL, 10)
    
    dlg.SetSizer(vbox)
    dlg.ShowModal()
