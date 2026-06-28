import wx

class ContentPanel(wx.Panel):
    """右侧可复用的内容面板"""
    def __init__(self, parent, title, color, text):
        super().__init__(parent)
        self.SetBackgroundColour(color)
        sizer = wx.BoxSizer(wx.VERTICAL)
        title_text = wx.StaticText(self, label=title, style=wx.ALIGN_CENTER)
        title_text.SetFont(wx.Font(18, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        content_text = wx.StaticText(self, label=text)
        sizer.Add(title_text, 0, wx.ALL | wx.EXPAND, 20)
        sizer.Add(content_text, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)
        self.SetSizer(sizer)

class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="树形导航与内容联动示例", size=(800, 500))
        
        # 创建分割窗口
        splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE | wx.SP_BORDER)
        
        # ====== 左侧面板：树形导航 ======
        left_panel = wx.Panel(splitter)
        self.tree = wx.TreeCtrl(left_panel, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT)
        
        # 创建图像列表
        il = wx.ImageList(16, 16)
        self.folder_idx = il.Add(wx.ArtProvider.GetBitmap(wx.ART_FOLDER, wx.ART_OTHER, (16, 16)))
        self.file_idx = il.Add(wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, wx.ART_OTHER, (16, 16)))
        self.tree.AssignImageList(il)
        
        # 构建树形结构并存储节点ID到内容的映射
        self.node_content_map = {}
        root = self.tree.AddRoot("Root")
        
        # 添加示例数据
        os_node = self.tree.AppendItem(root, "操作系统", self.folder_idx)
        self.add_tree_node(os_node, "Windows", "windows_panel")
        self.add_tree_node(os_node, "Linux", "linux_panel")
        self.add_tree_node(os_node, "macOS", "macos_panel")
        
        lang_node = self.tree.AppendItem(root, "编程语言", self.folder_idx)
        self.add_tree_node(lang_node, "Python", "python_panel")
        self.add_tree_node(lang_node, "C++", "cpp_panel")
        self.add_tree_node(lang_node, "JavaScript", "js_panel")
        
        # 展开所有节点
        self.tree.ExpandAll()
        
        # ====== 右侧面板：内容展示区 ======
        right_panel = wx.Panel(splitter)
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 创建所有可能的内容面板（实际应用中可按需创建）
        self.content_panels = {
            "windows_panel": ContentPanel(right_panel, "Windows", 
                                         wx.Colour(240, 248, 255),
                                         "微软开发的操作系统，广泛应用于个人电脑。"),
            "linux_panel": ContentPanel(right_panel, "Linux",
                                       wx.Colour(255, 250, 240),
                                       "开源类Unix操作系统，常用于服务器和嵌入式设备。"),
            "macos_panel": ContentPanel(right_panel, "macOS",
                                       wx.Colour(240, 255, 240),
                                       "苹果公司开发的操作系统，以其用户界面和稳定性著称。"),
            "python_panel": ContentPanel(right_panel, "Python",
                                        wx.Colour(255, 240, 245),
                                        "高级编程语言，以简洁易读的语法和丰富的库著称。"),
            "cpp_panel": ContentPanel(right_panel, "C++",
                                     wx.Colour(240, 240, 255),
                                     "高性能编程语言，广泛应用于系统软件和游戏开发。"),
            "js_panel": ContentPanel(right_panel, "JavaScript",
                                    wx.Colour(255, 255, 240),
                                    "主要用于网页开发的脚本语言，也可用于服务器端。")
        }
        
        # 默认显示第一个面板
        default_key = "windows_panel"
        self.current_panel = self.content_panels[default_key]
        self.content_sizer.Add(self.current_panel, 1, wx.EXPAND)
        right_panel.SetSizer(self.content_sizer)
        
        # 设置分割窗口布局
        splitter.SplitVertically(left_panel, right_panel, sashPosition=250)
        splitter.SetMinimumPaneSize(100)
        
        # 绑定树节点选择事件
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_tree_selection_changed)
        
        # 左侧面板布局
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_sizer.Add(self.tree, 1, wx.EXPAND | wx.ALL, 5)
        left_panel.SetSizer(left_sizer)
        
        self.Show()
    
    def add_tree_node(self, parent, text, content_key):
        """添加树节点并建立映射"""
        item = self.tree.AppendItem(parent, text, self.file_idx)
        self.node_content_map[item] = content_key
        return item
    
    def on_tree_selection_changed(self, event):
        """树节点选择事件处理：切换右侧内容面板"""
        item = event.GetItem()
        
        # 只处理有对应内容的节点
        if item in self.node_content_map:
            content_key = self.node_content_map[item]
            
            # 隐藏当前面板
            self.current_panel.Hide()
            self.content_sizer.Remove(0)  # 从布局中移除
            
            # 显示新面板
            self.current_panel = self.content_panels[content_key]
            self.content_sizer.Add(self.current_panel, 1, wx.EXPAND)
            self.current_panel.Show()
            
            # 更新布局
            self.current_panel.GetParent().Layout()

def main():
    app = wx.App()
    frame = MainFrame()
    app.MainLoop()

if __name__ == "__main__":
    main()