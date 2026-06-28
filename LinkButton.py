import wx
import webbrowser

def create_link_button(panel, link_url, image_path, label,size):
    """
    创建一个带有图片的链接按钮。

    :param panel: 按钮绘制的面板
    :param link_url: 按钮点击后要打开的链接
    :param image_path: 按钮上显示的图片的路径
    :param label: 按钮上显示的文本
    :param size: 按钮的大小
    :return: 创建好的链接按钮
    """
    try:
       
        link_icon = wx.Bitmap(image_path, wx.BITMAP_TYPE_PNG)
    except Exception as e:
        print(f"加载图片失败: {e}")
        return None
    

    update_link = wx.Button(panel, label=label, 
                          style=wx.BORDER_NONE, size=size)

    update_link.SetBitmap(link_icon, wx.LEFT)  # 将图片放在文本左侧
    update_link.SetForegroundColour(wx.Colour(0, 0, 255))
    update_link.SetBackgroundColour(wx.Colour(255, 255, 255))
    update_link.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
    update_link.SetCursor(wx.Cursor(wx.CURSOR_HAND))

    def on_update_link(event):
        webbrowser.open(link_url)

    update_link.Bind(wx.EVT_BUTTON, on_update_link)
    return update_link
