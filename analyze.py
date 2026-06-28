import wx,requests
from bs4 import BeautifulSoup
import time

progress_dialog = None
def analyze_webpage(url,headers=None, timeout=10):
    global progress_dialog
    print(timeout)
    try:
        start_time = time.time()
        
        progress_dialog = wx.ProgressDialog("网页分析进度", "正在初始化...", maximum=100, 
                                          style=wx.PD_AUTO_HIDE )
        
        if headers is None:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
            }
        else:
            headers = {"user-agent": headers}
        
        
        progress_dialog.Update(10, "正在获取网页内容...")
        response = requests.get(url, headers=headers, data={}, verify=False, timeout=timeout)
        
     
        progress_dialog.Update(30, "网页内容获取完成，正在解析...")
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
      
        progress_dialog.Update(50, "正在提取网页信息...")
        
        
        title = soup.title.string if soup.title else "无标题"
        
       
        links = [a['href'] for a in soup.find_all('a', href=True)]
        
       
        images = [img['src'] for img in soup.find_all('img', src=True)]
        
      
        text = soup.get_text()
        
        progress_dialog.Update(80, "网页信息提取完成")
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        
        progress_dialog.Update(99, "分析完成,等待结果...")
        
        return {
            'title': title,
            'links': links,
            'images': images,
            'text': text,
            'source': response.text ,
            'elapsed_time': elapsed_time 
        }
    except requests.Timeout:
        progress_dialog.Destroy()
        wx.MessageBox(f"连接超时：{timeout}秒\n请适当增加超时时间后重试", 
                     "连接超时")
        
        return {'error': f'连接超时'}
    except Exception as e:
        return {'error': str(e)}

def on_analyze_button(url_l,headers=None,timeout=5,code=True):
    global progress_dialog
    print(url_l)
    print(code)

    result = analyze_webpage(url_l,headers=headers, timeout=timeout)
    
    if 'error' in result:
        wx.MessageBox(f"分析失败: {result['error']}", "错误", wx.OK | wx.ICON_ERROR)
        return
    result_window = wx.Frame(None, title="网页分析结果", size=(600, 400))
    notebook = wx.Notebook(result_window)

    info_panel = wx.Panel(notebook)
    links_panel = wx.Panel(notebook)
    images_panel = wx.Panel(notebook)
    text_panel = wx.Panel(notebook)
    if code:
        source_panel = wx.Panel(notebook)
    
    

    def create_scrollable_text(panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        text = wx.TextCtrl(panel, style=wx.TE_MULTILINE|wx.TE_READONLY)
        sizer.Add(text, 1, wx.EXPAND|wx.ALL, 5)
        panel.SetSizer(sizer)
        return text
   
    info_text = create_scrollable_text(info_panel)
    info_text.SetValue(f"网页标题: {result['title']}\n\n"
                      f"链接数量: {len(result['links'])}\n"
                      f"图片数量: {len(result['images'])}\n"
                      f"分析用时: {result['elapsed_time']:.2f}秒\n"  # 新增用时显示
                      f"请求头User-Agent：{headers}")
    
    links_text = create_scrollable_text(links_panel)
    links_text.SetValue("\n".join(result['links']))
    
   
    images_text = create_scrollable_text(images_panel)
    images_text.SetValue("\n".join(result['images']))
    
   
    text_text = create_scrollable_text(text_panel)
    text_text.SetValue(result['text'])
    
    if code:
        source_text = create_scrollable_text(source_panel)
        source_text.SetValue(result['source'])
        
    
    notebook.AddPage(info_panel, "基本信息")
    notebook.AddPage(links_panel, "链接")
    notebook.AddPage(images_panel, "图片")
    notebook.AddPage(text_panel, "文本")
    if code:
        notebook.AddPage(source_panel, "源码")
    

    main_sizer = wx.BoxSizer(wx.VERTICAL)
    main_sizer.Add(notebook, 1, wx.EXPAND)
    result_window.SetSizer(main_sizer)
    

    result_window.Show()
    progress_dialog.Destroy()
