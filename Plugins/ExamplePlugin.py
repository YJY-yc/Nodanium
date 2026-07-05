
import wx
from winotify import Notification
def MainPanel(parent):
    """
    在传入的父面板中创建一个简单的界面，显示一行字
    
    参数:
        parent: 父面板，通常是 wx.Panel 或类似的容器
    """
  
    panel_sizer = wx.BoxSizer(wx.VERTICAL)
    
    text = wx.StaticText(parent, label="这是 ExamplePlugin 插件的界面。")
    
    
    font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
    text.SetFont(font)
    text.SetForegroundColour(wx.Colour(0, 0, 128)) 
    
    panel_sizer.Add(text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
    
   
    parent.SetSizer(panel_sizer)
    
    parent.Layout()
def Run():
    Notification(app_id="ExamplePlugin", title="插件启动", msg="ExamplePlugin 插件已启动").show()