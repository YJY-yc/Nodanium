# PluginManager.py
import os
import sys
import shutil
import zipfile
import wx



import tempfile

class PluginManager:
    """插件管理器类"""
    
    def __init__(self, plugins_dir="Plugins"):
        self.plugins_dir = plugins_dir
        self.loaded_plugins = {}
        self.preview_plugins = {}  # 存储预览插件
        self.preview_windows = {}  # 存储预览窗口
        
    def get_plugin_icon_path(self, plugin_name):
        """获取插件图标路径"""
        return os.path.join(self.plugins_dir, f"{plugin_name}.png")
    
    def get_plugin_version_path(self, plugin_name):
        """获取插件版本文件路径"""
        return os.path.join(self.plugins_dir, f"{plugin_name}.v")
    
    def get_plugin_version(self, plugin_name):
        """获取插件版本信息"""
        version_path = self.get_plugin_version_path(plugin_name)
        if os.path.exists(version_path):
            try:
                with open(version_path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except Exception as e:
                print(f"读取插件 {plugin_name} 版本文件失败: {e}")
        return "未知"
    
    def get_plugin_icon(self, plugin_name, size=(32, 32)):
        """获取插件图标"""
        icon_path = self.get_plugin_icon_path(plugin_name)
        if os.path.exists(icon_path):
            try:
                bitmap = wx.Bitmap(icon_path)
                if bitmap.IsOk():
                    # 调整图标大小
                    image = bitmap.ConvertToImage()
                    image = image.Scale(size[0], size[1], wx.IMAGE_QUALITY_HIGH)
                    return wx.Bitmap(image)
            except Exception as e:
                print(f"加载插件 {plugin_name} 图标失败: {e}")
        
        # 返回默认图标
        return wx.Bitmap(size[0], size[1])
    
    def load_plugin(self, plugin_name):
        """加载插件"""
        try:
            # 确保 Plugins 目录在 Python 路径中
            plugins_dir_abs = os.path.abspath(self.plugins_dir)
            if plugins_dir_abs not in sys.path:
                sys.path.insert(0, plugins_dir_abs)
            
            # 检查插件文件是否存在（只检查 .pyd 文件）
            plugin_file = os.path.join(self.plugins_dir, f"{plugin_name}.pyd")
            if not os.path.exists(plugin_file):
                print(f"找不到插件文件: {plugin_file}")
                return None
            
            print(f"尝试加载插件: {plugin_file}")
            
            # 直接导入插件模块，不使用包路径
            try:
                plugin_module =  __import__(plugin_name)
                self.loaded_plugins[plugin_name] = plugin_module
                print(f"成功加载插件: {plugin_name}")
                return plugin_module
            except ImportError as e:
                print(f"导入错误 {plugin_name}: {e}")
                
                # 对于 .pyd 文件，提供更详细的错误信息
                print(f"这可能是由于以下原因:")
                print(f"1. .pyd 文件是为不同版本的 Python 编译的")
                print(f"2. .pyd 文件是为不同的 CPU 架构编译的")
                print(f"3. .pyd 文件缺少必需的导出函数 (例如 PyInit_{plugin_name})")
                print(f"4. .pyd 文件依赖于其他不存在的动态链接库")
                
                return None
            except Exception as e:
                print(f"加载插件 {plugin_name} 时发生未知错误: {e}")
                return None
        except Exception as e:
            print(f"加载插件 {plugin_name} 失败: {e}")
            return None
    
    def preview_plugin(self, plugin_path):
        """预览插件"""
        try:
            # 获取插件名
            plugin_name = os.path.splitext(os.path.basename(plugin_path))[0]
            
            # 创建临时目录
            temp_dir = tempfile.mkdtemp()
            
            # 复制插件文件到临时目录
            temp_plugin_path = os.path.join(temp_dir, os.path.basename(plugin_path))
            shutil.copy2(plugin_path, temp_plugin_path)
            
            # 如果有图标文件，也复制过去
            icon_path = os.path.join(os.path.dirname(plugin_path), f"{plugin_name}.png")
            if os.path.exists(icon_path):
                shutil.copy2(icon_path, temp_dir)
            
            # 如果有版本文件，也复制过去
            version_path = os.path.join(os.path.dirname(plugin_path), f"{plugin_name}.v")
            if os.path.exists(version_path):
                shutil.copy2(version_path, temp_dir)
            
            # 动态导入插件
            sys.path.insert(0, temp_dir)
            try:
                # 直接导入插件模块，不使用包路径
                plugin_module =  __import__(plugin_name)
                self.preview_plugins[plugin_name] = {
                    'module': plugin_module,
                    'temp_dir': temp_dir
                }
                
                # 创建预览窗口
                preview_frame = wx.Frame(None, title=f"{plugin_name} 预览", size=(600, 400))
                preview_panel = wx.Panel(preview_frame)
                
                # 初始化插件界面
                if hasattr(plugin_module, 'MainPanel'):
                    plugin_module.MainPanel(preview_panel)
                
                # 显示窗口
                preview_frame.Show()
                
                # 存储预览窗口引用
                self.preview_windows[plugin_name] = preview_frame
                
                # 窗口关闭时清理
                def on_preview_close(event):
                    self.cleanup_preview_plugin(plugin_name)
                    event.Skip()
                
                preview_frame.Bind(wx.EVT_CLOSE, on_preview_close)
                
                return plugin_module
            except Exception as e:
                print(f"预览插件 {plugin_name} 失败: {e}")
                # 清理临时目录
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None
        except Exception as e:
            print(f"预览插件时出错: {e}")
            return None
    
    def cleanup_preview_plugin(self, plugin_name):
        """清理单个预览插件"""
        if plugin_name in self.preview_plugins:
            plugin_info = self.preview_plugins[plugin_name]
            try:
                # 从 sys.modules 中移除
                if plugin_name in sys.modules:
                    del sys.modules[plugin_name]
                
                # 删除临时目录
                if 'temp_dir' in plugin_info and os.path.exists(plugin_info['temp_dir']):
                    shutil.rmtree(plugin_info['temp_dir'], ignore_errors=True)
                
                # 从预览插件字典中移除
                del self.preview_plugins[plugin_name]
                
                # 关闭预览窗口
                if plugin_name in self.preview_windows:
                    self.preview_windows[plugin_name].Destroy()
                    del self.preview_windows[plugin_name]
                    
                print(f"清理预览插件 {plugin_name} 完成")
            except Exception as e:
                print(f"清理预览插件 {plugin_name} 时出错: {e}")
    
    def cleanup_preview_plugins(self):
        """清理所有预览插件"""
        # 复制一份键列表，避免在迭代过程中修改字典
        plugin_names = list(self.preview_plugins.keys())
        for plugin_name in plugin_names:
            self.cleanup_preview_plugin(plugin_name)
        
        # 清空预览插件字典
        self.preview_plugins = {}
        self.preview_windows = {}
    
    def install_plugin(self, file_path):
        """安装插件"""
        try:
            file_name = os.path.basename(file_path)
            
            # 处理 .zip 文件
            if file_name.endswith('.zip'):
                # 先检查zip中是否有.i文件
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    file_list = zip_ref.namelist()
                    
                    # 查找.i文件
                    info_file = None
                    for f in file_list:
                        if f.endswith('.i'):
                            info_file = f
                            break
                    
                    # 如果找到.i文件，读取内容并显示
                    info_text = ""
                    if info_file:
                        with zip_ref.open(info_file) as info:
                            info_text = info.read().decode('utf-8', errors='ignore')
                    
                    # 显示信息对话框（如果有信息）
                    if info_text:
                        wx.MessageBox(f"插件信息:\n\n{info_text}", "插件信息", wx.OK | wx.ICON_INFORMATION)
                    
                    # 解压所有文件
                    zip_ref.extractall(self.plugins_dir)
                    
                print(f"成功解压插件包: {file_name}")
                return True
            
            # 处理 .pyd 文件（不再处理 .py 文件）
            elif file_name.endswith('.pyd'):
                dest_path = os.path.join(self.plugins_dir, file_name)
                shutil.copy2(file_path, dest_path)
                print(f"成功复制插件文件: {file_name}")
                return True
            
            print(f"不支持的插件文件类型: {file_name}")
            return False
        except Exception as e:
            print(f"安装插件失败: {e}")
            return False

    def uninstall_plugin(self, plugin_name):
        """卸载插件（删除文件）"""
        try:
            # 从已加载插件列表中移除
            if plugin_name in self.loaded_plugins:
                del self.loaded_plugins[plugin_name]
            
            # 从 sys.modules 中移除
            if plugin_name in sys.modules:
                del sys.modules[plugin_name]
            
            # 删除插件文件（只删除 .pyd 文件）
            plugin_file = os.path.join(self.plugins_dir, f"{plugin_name}.pyd")
            if os.path.exists(plugin_file):
                try:
                    os.remove(plugin_file)
                    print(f"已删除插件文件: {plugin_file}")
                except Exception as e:
                    print(f"删除插件文件 {plugin_file} 失败: {e}")
                    return False
            
            # 删除插件图标文件
            icon_file = os.path.join(self.plugins_dir, f"{plugin_name}.png")
            if os.path.exists(icon_file):
                try:
                    os.remove(icon_file)
                    print(f"已删除插件图标: {icon_file}")
                except Exception as e:
                    print(f"删除插件图标 {icon_file} 失败: {e}")
            
            # 删除插件版本文件
            version_file = os.path.join(self.plugins_dir, f"{plugin_name}.v")
            if os.path.exists(version_file):
                try:
                    os.remove(version_file)
                    print(f"已删除插件版本文件: {version_file}")
                except Exception as e:
                    print(f"删除插件版本文件 {version_file} 失败: {e}")
            
            return True
        except Exception as e:
            print(f"卸载插件 {plugin_name} 失败: {e}")
            return False
    
    def get_loaded_plugins(self):
        """获取已加载的插件列表"""
        return list(self.loaded_plugins.keys())
    
    def get_preview_plugins(self):
        """获取预览插件列表"""
        return list(self.preview_plugins.keys())
    
    def scan_plugins(self):
        """扫描插件目录中的所有插件"""
        plugins = []
        
        if not os.path.exists(self.plugins_dir):
            print(f"插件目录 {self.plugins_dir} 不存在")
            return plugins
            
        for filename in os.listdir(self.plugins_dir):
            # 跳过 __init__.py 文件
            if filename == "__init__.py":
                continue
                
            # 获取插件名（去掉扩展名）
            plugin_name = os.path.splitext(filename)[0]
            
            # 跳过空名称
            if not plugin_name:
                continue
                
            # 只检查 .pyd 文件（不再认可 .py 文件）
            if filename.endswith('.pyd'):
                plugins.append(plugin_name)
                
        return plugins

class PluginDropTarget(wx.FileDropTarget):
    """文件拖放目标类"""
    
    def __init__(self, plugin_manager, list_ctrl, refresh_callback, preview_callback):
        super(PluginDropTarget, self).__init__()
        self.plugin_manager = plugin_manager
        self.list_ctrl = list_ctrl
        self.refresh_callback = refresh_callback
        self.preview_callback = preview_callback
    
    def OnDropFiles(self, x, y, filenames):
        """处理文件拖放"""
        for filename in filenames:
            # 检查是否是预览请求（按住Ctrl键拖拽）
            if wx.GetKeyState(wx.WXK_CONTROL):
                if self.preview_callback(filename):
                    wx.MessageBox(f"成功预览插件: {os.path.basename(filename)}", "成功", wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox(f"无法预览插件: {os.path.basename(filename)}", "错误", wx.OK | wx.ICON_ERROR)
            else:
                if self.plugin_manager.install_plugin(filename):
                    wx.MessageBox(f"成功安装插件: {os.path.basename(filename)}", "成功", wx.OK | wx.ICON_INFORMATION)
                    # 刷新插件列表
                    self.refresh_callback()
                else:
                    wx.MessageBox(f"无法安装插件: {os.path.basename(filename)}", "错误", wx.OK | wx.ICON_ERROR)
        return True

def MainPanel(parent):
    """插件管理器主面板"""
    # 创建插件管理器实例
    plugin_manager = PluginManager()
    
    # 创建一个垂直方向的盒子布局
    panel_sizer = wx.BoxSizer(wx.VERTICAL)
    
    # 创建标题
    title = wx.StaticText(parent, label="插件管理器")
    title_font = wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
    title.SetFont(title_font)
    panel_sizer.Add(title, 0, wx.ALL | wx.ALIGN_CENTER, 10)
    
    # 添加一条分隔线
    line = wx.StaticLine(parent)
    panel_sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
    
    # 创建说明文本
    info_text = wx.StaticText(parent, label="拖拽 .pyd 插件文件到此区域来安装新插件\n按住 Ctrl 键拖拽可以预览插件")
    panel_sizer.Add(info_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
    
    # 创建插件列表
    list_ctrl = wx.ListCtrl(parent, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_ALIGN_LEFT)
    
    # 添加列
    list_ctrl.InsertColumn(0, "图标", width=90)
    list_ctrl.InsertColumn(1, "插件名称", width=150)
    list_ctrl.InsertColumn(2, "版本", width=100)
    list_ctrl.InsertColumn(3, "状态", width=100)  # 添加状态列
    
    # 创建图像列表
    image_list = wx.ImageList(32, 32)
    list_ctrl.AssignImageList(image_list, wx.IMAGE_LIST_SMALL)
    
    # 定义预览函数
    def preview_plugin(file_path):
        """预览插件"""
        plugin_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # 预览插件
        plugin_module = plugin_manager.preview_plugin(file_path)
        if plugin_module:
            # 添加到列表
            icon = plugin_manager.get_plugin_icon(plugin_name)
            index = list_ctrl.InsertImageItem(list_ctrl.GetItemCount(), image_list.Add(icon))
            list_ctrl.SetItem(index, 1, plugin_name)
            list_ctrl.SetItem(index, 2, "预览版")
            list_ctrl.SetItem(index, 3, "预览中")
            
            return True
        return False
    
    # 定义刷新函数
    def refresh_plugin_list():
        """刷新插件列表"""
        list_ctrl.DeleteAllItems()
        
        # 扫描插件目录中的所有插件
        plugin_names = plugin_manager.scan_plugins()
        
        # 加载并添加插件到列表
        for plugin_name in plugin_names:
            # 尝试加载插件
            plugin_module = plugin_manager.load_plugin(plugin_name)
            if plugin_module:
                # 获取插件图标
                icon = plugin_manager.get_plugin_icon(plugin_name)
                index = list_ctrl.InsertImageItem(list_ctrl.GetItemCount(), image_list.Add(icon))
                list_ctrl.SetItem(index, 1, plugin_name)
                
                # 获取插件版本信息（从 .v 文件）
                version = plugin_manager.get_plugin_version(plugin_name)
                
                list_ctrl.SetItem(index, 2, version)
                list_ctrl.SetItem(index, 3, "已安装")
    
    # 初始加载插件列表
    refresh_plugin_list()
    
    # 设置拖放目标
    drop_target = PluginDropTarget(plugin_manager, list_ctrl, refresh_plugin_list, preview_plugin)
    list_ctrl.SetDropTarget(drop_target)
    
    panel_sizer.Add(list_ctrl, 1, wx.EXPAND | wx.ALL, 10)
    

    
    # 创建按钮面板
    button_panel = wx.Panel(parent)
    button_sizer = wx.BoxSizer(wx.HORIZONTAL)
    
    # 刷新按钮
    refresh_button = wx.Button(button_panel, label="刷新列表")
    refresh_button.Bind(wx.EVT_BUTTON, lambda event: refresh_plugin_list())
    button_sizer.Add(refresh_button, 0, wx.ALL, 5)
    
    open_folder_button = wx.Button(button_panel, label="打开插件文件夹")
    def on_open_folder(event):
        """打开插件文件夹"""
        import subprocess
        import platform
        
        # 获取插件文件夹路径
        plugins_dir = plugin_manager.plugins_dir
        
        # 根据不同操作系统使用不同命令打开文件夹
        try:
            if platform.system() == "Windows":
                subprocess.Popen(['explorer', plugins_dir])
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(['open', plugins_dir])
            else:  # Linux
                subprocess.Popen(['xdg-open', plugins_dir])
        except Exception as e:
            wx.MessageBox(f"无法打开插件文件夹: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)

    open_folder_button.Bind(wx.EVT_BUTTON, on_open_folder)
    button_sizer.Add(open_folder_button, 0, wx.ALL, 5)


    # 卸载按钮
    unload_button = wx.Button(button_panel, label="卸载选中")
    def on_unload(event):
        selected = list_ctrl.GetNextItem(-1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
        if selected != -1:
            plugin_name = list_ctrl.GetItemText(selected, 1)
            status = list_ctrl.GetItemText(selected, 3)
            
            if status == "预览中":
                # 清理预览插件
                plugin_manager.cleanup_preview_plugin(plugin_name)
                # 从列表中移除
                list_ctrl.DeleteItem(selected)
                wx.MessageBox(f"插件 {plugin_name} 预览已结束", "成功", wx.OK | wx.ICON_INFORMATION)
            elif wx.YES == wx.MessageBox(f"确定要卸载插件 {plugin_name} 吗？\n这将删除插件文件(.pyd)、图标文件(.png)和版本文件(.v)", "确认卸载", wx.YES_NO | wx.ICON_QUESTION):
                # 卸载插件（删除文件）
                if plugin_manager.uninstall_plugin(plugin_name):
                    # 从列表中移除
                    list_ctrl.DeleteItem(selected)
                    # 刷新插件列表
                    refresh_plugin_list()
                    wx.MessageBox(f"插件 {plugin_name} 已卸载", "成功", wx.OK | wx.ICON_INFORMATION)
                else:
                    wx.MessageBox(f"卸载插件 {plugin_name} 失败", "错误", wx.OK | wx.ICON_ERROR)
        else:
            wx.MessageBox("请先选择要卸载的插件", "提示", wx.OK | wx.ICON_INFORMATION)
    
    unload_button.Bind(wx.EVT_BUTTON, on_unload)
    button_sizer.Add(unload_button, 0, wx.ALL, 5)
    
    # 预览按钮
    preview_button = wx.Button(button_panel, label="预览插件")
    def on_preview(event):
        """打开文件选择对话框，选择要预览的插件"""
        wildcard = "Python extension modules (*.pyd)|*.pyd|All files (*.*)|*.*"
        dialog = wx.FileDialog(parent, "选择要预览的插件", wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        
        if dialog.ShowModal() == wx.ID_OK:
            file_path = dialog.GetPath()
            preview_plugin(file_path)
        
        dialog.Destroy()
    
    preview_button.Bind(wx.EVT_BUTTON, on_preview)
    button_sizer.Add(preview_button, 0, wx.ALL, 5)
    
    button_panel.SetSizer(button_sizer)
    panel_sizer.Add(button_panel, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
    
    # 设置面板的布局
    parent.SetSizer(panel_sizer)
    
    # 刷新布局
    parent.Layout()
    
    # 在窗口关闭时清理预览插件
    def on_close(event):
        plugin_manager.cleanup_preview_plugins()
        event.Skip()
    
    parent.Bind(wx.EVT_WINDOW_DESTROY, on_close)
