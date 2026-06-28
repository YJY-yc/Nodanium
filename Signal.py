import wx
import threading
import time
import asyncio
from datetime import datetime
from bleak import BleakScanner
import pywifi
from pywifi import const
import subprocess
import re

_wifi_devices = []
_ble_devices = []
_is_scanning = False
_scan_thread = None
_update_callback = None

WIFI_CHANNELS_2G = {
    1: 2412, 2: 2417, 3: 2422, 4: 2427, 5: 2432, 6: 2437, 7: 2442, 8: 2447,
    9: 2452, 10: 2457, 11: 2462, 12: 2467, 13: 2472, 14: 2484
}

WIFI_CHANNELS_5G = {
    36: 5180, 40: 5200, 44: 5220, 48: 5240, 52: 5260, 56: 5280, 60: 5300, 64: 5320,
    100: 5500, 104: 5520, 108: 5540, 112: 5560, 116: 5580, 120: 5600, 124: 5620, 128: 5640,
    132: 5660, 136: 5680, 140: 5700, 149: 5745, 153: 5765, 157: 5785, 161: 5805, 165: 5825
}

def set_callback(callback_func):
    global _update_callback
    _update_callback = callback_func

def start_scanning():
    global _is_scanning, _scan_thread
    if not _is_scanning:
        _is_scanning = True
        _scan_thread = threading.Thread(target=_scan_loop)
        _scan_thread.daemon = True
        _scan_thread.start()

def stop_scanning():
    global _is_scanning
    _is_scanning = False

def _scan_loop():
    global _is_scanning, _wifi_devices, _ble_devices, _update_callback
    
    while _is_scanning:
        _wifi_devices = _scan_wifi()
        _ble_devices = _scan_ble_sync()
        
        if _update_callback:
            _update_callback(_wifi_devices, _ble_devices)
        
        time.sleep(2)





def _freq_to_channel(freq):
    if 2412 <= freq <= 2484:
        for ch, f in WIFI_CHANNELS_2G.items():
            if abs(f - freq) <= 10:
                return ch
    elif 5180 <= freq <= 5825:
        for ch, f in WIFI_CHANNELS_5G.items():
            if abs(f - freq) <= 10:
                return ch
    return None

def _channel_to_freq(channel):
    if channel <= 14:
        return WIFI_CHANNELS_2G.get(channel, 2412 + (channel-1)*5)
    else:
        return WIFI_CHANNELS_5G.get(channel, 5180 + (channel-36)*20)

def _scan_wifi():
    devices = []
    try:
        wifi = pywifi.PyWiFi()
        if not wifi.interfaces():
            return devices
            
        iface = wifi.interfaces()[0]
        iface.scan()
        time.sleep(1)
        
        results = iface.scan_results()
        
        for network in results:
            if not network.ssid:
                continue
                
            auth = "OPEN"
            if hasattr(network, 'akm') and network.akm:
                if const.AKM_TYPE_WPA2PSK in network.akm:
                    auth = "WPA2"
                elif const.AKM_TYPE_WPAPSK in network.akm:
                    auth = "WPA"
            
            channel = getattr(network, 'channel', 'N/A')
            if channel == 'N/A' or channel is None:
                freq = getattr(network, 'freq', 0)
                if freq:
                    ch = _freq_to_channel(freq)
                    channel = ch if ch else 'N/A'
            
            freq = getattr(network, 'freq', 'N/A')
            
            noise = -95
            signal = network.signal
            snr = signal - noise
            snr = round(snr, 1)
            
            device_info = {
                'type': 'WiFi',
                'ssid': network.ssid,
                'bssid': network.bssid,
                'signal': signal,
                'noise': noise,
                'snr': snr,
                'channel': channel,
                'freq': freq,
                'auth': auth,
                'raw_data': str(network)[:200]
            }
            devices.append(device_info)
    except Exception as e:
        print(f"WiFi扫描错误: {e}")
    
    devices.sort(key=lambda x: x['signal'], reverse=True)
    return devices

def _scan_ble_sync():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_scan_ble())
    except Exception as e:
        print(f"BLE扫描同步错误: {e}")
        return []

async def _scan_ble():
    devices = []
    try:
        scanned_devices = await BleakScanner.discover(timeout=1.5)
        
        for device in scanned_devices:
            if hasattr(device, 'name'):
                name = device.name or '未知设备'
                address = device.address
                rssi = getattr(device, 'rssi', -100)
                
                adv_data = getattr(device, 'advertisement_data', None)
                manufacturer_data = {}
                service_uuids = []
                
                if adv_data:
                    manufacturer_data = getattr(adv_data, 'manufacturer_data', {})
                    service_uuids = getattr(adv_data, 'service_uuids', [])
            else:
                continue
            
            noise = -95
            snr = rssi - noise
            
            device_info = {
                'type': 'BLE',
                'name': name,
                'address': address,
                'signal': rssi,
                'noise': noise,
                'snr': round(snr, 1),
                'manufacturer_data': manufacturer_data,
                'service_uuids': service_uuids,
                'details': f"广播数据: {len(manufacturer_data)}个制造商, {len(service_uuids)}个服务"
            }
            devices.append(device_info)
            
    except Exception as e:
        print(f"BLE扫描错误: {e}")
    
    devices.sort(key=lambda x: x['signal'], reverse=True)
    return devices



# ==================== 详情对话框 ====================

class DeviceDetailDialog(wx.Dialog):
    """设备详情对话框"""
    
    def __init__(self, parent, device_info):
        title = f"设备详情 - {device_info.get('ssid', device_info.get('name', '未知'))}"
        super().__init__(parent, title=title, size=(600, 500))
        
        self.device_info = device_info
        self._create_ui()
        self.CenterOnParent()
        
    def _create_ui(self):
        """创建UI"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 创建只读文本框
        text_ctrl = wx.TextCtrl(
            panel, 
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL,
            size=(580, 400)
        )
        
        # 格式化设备信息
        info_text = self._format_device_info()
        text_ctrl.SetValue(info_text)
        
        # 设置等宽字体
        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        text_ctrl.SetFont(font)
        
        main_sizer.Add(text_ctrl, 1, wx.EXPAND | wx.ALL, 10)
        
        # 按钮区
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        copy_btn = wx.Button(panel, label="复制到剪贴板")
        copy_btn.Bind(wx.EVT_BUTTON, self._on_copy)
        btn_sizer.Add(copy_btn, 0, wx.RIGHT, 10)
        
        close_btn = wx.Button(panel, label="关闭")
        close_btn.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
        btn_sizer.Add(close_btn, 0)
        
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)
        
        panel.SetSizer(main_sizer)
        
    def _format_device_info(self):
        """格式化设备信息"""
        lines = []
        lines.append("=" * 80)
        lines.append(f"设备类型: {self.device_info.get('type', '未知')}")
        lines.append("=" * 80)
        
        if self.device_info['type'] == 'WiFi':
            lines.append(f"SSID: {self.device_info.get('ssid', 'N/A')}")
            lines.append(f"BSSID (MAC): {self.device_info.get('bssid', 'N/A')}")
            lines.append(f"信号强度: {self.device_info.get('signal', 'N/A')} dBm")
            lines.append(f"噪声底噪: {self.device_info.get('noise', 'N/A')} dBm")
            lines.append(f"信噪比(SNR): {self.device_info.get('snr', 'N/A')} dB")
            lines.append(f"信道: {self.device_info.get('channel', 'N/A')}")
            lines.append(f"频率: {self.device_info.get('freq', 'N/A')} MHz")
            lines.append(f"加密方式: {self.device_info.get('auth', 'N/A')}")
            
            if 'raw_data' in self.device_info:
                lines.append("\n原始数据:")
                lines.append("-" * 60)
                lines.append(self.device_info['raw_data'])
                
        else:  # BLE设备
            lines.append(f"设备名称: {self.device_info.get('name', '未知设备')}")
            lines.append(f"MAC地址: {self.device_info.get('address', 'N/A')}")
            lines.append(f"信号强度: {self.device_info.get('signal', 'N/A')} dBm")
            lines.append(f"噪声底噪: {self.device_info.get('noise', 'N/A')} dBm")
            lines.append(f"信噪比(SNR): {self.device_info.get('snr', 'N/A')} dB")
            
            if self.device_info.get('service_uuids'):
                lines.append("\n服务UUIDs:")
                for uuid in self.device_info['service_uuids'][:10]:  # 限制显示数量
                    lines.append(f"  • {uuid}")
                if len(self.device_info['service_uuids']) > 10:
                    lines.append(f"  ... 还有{len(self.device_info['service_uuids'])-10}个")
            
            if self.device_info.get('manufacturer_data'):
                lines.append("\n制造商数据:")
                for manufacturer_id, data in list(self.device_info['manufacturer_data'].items())[:5]:
                    if isinstance(data, bytes):
                        hex_data = ' '.join(f'{b:02x}' for b in data[:16])
                        if len(data) > 16:
                            hex_data += '...'
                        lines.append(f"  • ID: {manufacturer_id} (0x{manufacturer_id:04x})")
                        lines.append(f"    数据: {hex_data}")
                    else:
                        lines.append(f"  • ID: {manufacturer_id}: {data}")
                if len(self.device_info['manufacturer_data']) > 5:
                    lines.append(f"  ... 还有{len(self.device_info['manufacturer_data'])-5}个")
            
            if self.device_info.get('details'):
                lines.append("\n详细信息:")
                lines.append(self.device_info['details'])
        
        lines.append("\n" + "=" * 80)
        lines.append(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return '\n'.join(lines)
    
    def _on_copy(self, event):
        """复制到剪贴板"""
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self._format_device_info()))
            wx.TheClipboard.Close()
            wx.MessageBox("已复制到剪贴板", "提示", wx.OK | wx.ICON_INFORMATION)

# ==================== wxPython界面函数 ====================

def create_panel(parent):
    panel = wx.Panel(parent)
    
    _create_ui(panel)
    
    panel.Bind(wx.EVT_WINDOW_DESTROY, lambda evt: stop_scanning())
    
    set_callback(lambda wifi, ble: wx.CallAfter(_update_ui, panel, wifi, ble))
    
    return panel

def _create_ui(panel):
    panel.scan_btn = None
    panel.wifi_list = None
    panel.ble_list = None
    panel.wifi_stats = None
    panel.ble_stats = None
    panel.status_text = None
    
    main_sizer = wx.BoxSizer(wx.VERTICAL)
    
    control_sizer = wx.BoxSizer(wx.HORIZONTAL)
    
    title = wx.StaticText(panel, label="无线电信号探测仪")
    title.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD))
    control_sizer.Add(title, 0, wx.ALL, 10)
    
    control_sizer.AddStretchSpacer()
    
    panel.scan_btn = wx.Button(panel, label="开始扫描")
    panel.scan_btn.Bind(wx.EVT_BUTTON, lambda evt: _on_toggle_scan(panel))
    control_sizer.Add(panel.scan_btn, 0, wx.ALL, 5)
    
    clear_btn = wx.Button(panel, label="清空列表")
    clear_btn.Bind(wx.EVT_BUTTON, lambda evt: _on_clear(panel))
    control_sizer.Add(clear_btn, 0, wx.ALL, 5)
    
    main_sizer.Add(control_sizer, 0, wx.EXPAND)
    
    notebook = wx.Notebook(panel)
    panel.notebook = notebook
    
    wifi_panel = wx.Panel(notebook)
    panel.wifi_list, panel.wifi_stats = _create_wifi_tab(wifi_panel, panel)
    notebook.AddPage(wifi_panel, f"WiFi信号")
    
    ble_panel = wx.Panel(notebook)
    panel.ble_list, panel.ble_stats = _create_ble_tab(ble_panel, panel)
    notebook.AddPage(ble_panel, f"蓝牙设备")
    
    main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
    
    panel.status_text = wx.StaticText(panel, label="就绪 | 使用内置天线探测 | 双击列表项查看详情")
    main_sizer.Add(panel.status_text, 0, wx.ALL | wx.EXPAND, 5)
    
    panel.SetSizer(main_sizer)

def _create_wifi_tab(parent, main_panel):
    sizer = wx.BoxSizer(wx.VERTICAL)
    
    wifi_list = wx.ListCtrl(
        parent, 
        style=wx.LC_REPORT | wx.BORDER_SUNKEN
    )
    
    wifi_list.AppendColumn("SSID", width=200)
    wifi_list.AppendColumn("BSSID", width=150)
    wifi_list.AppendColumn("信号", width=60)
    wifi_list.AppendColumn("噪声", width=60)
    wifi_list.AppendColumn("SNR", width=60)
    wifi_list.AppendColumn("信道", width=50)
    wifi_list.AppendColumn("加密", width=60)
    
    wifi_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, 
                   lambda evt: _on_item_double_click(main_panel, 'wifi', evt.GetIndex()))
    
    sizer.Add(wifi_list, 1, wx.EXPAND | wx.ALL, 5)
    
    wifi_stats = wx.StaticText(parent, label="发现 0 个WiFi网络")
    sizer.Add(wifi_stats, 0, wx.ALL, 5)
    
    parent.SetSizer(sizer)
    return wifi_list, wifi_stats

def _create_ble_tab(parent, main_panel):
    sizer = wx.BoxSizer(wx.VERTICAL)
    
    ble_list = wx.ListCtrl(
        parent,
        style=wx.LC_REPORT | wx.BORDER_SUNKEN
    )
    
    ble_list.AppendColumn("设备名称", width=200)
    ble_list.AppendColumn("MAC地址", width=150)
    ble_list.AppendColumn("信号", width=60)
    ble_list.AppendColumn("噪声", width=60)
    ble_list.AppendColumn("SNR", width=60)
    ble_list.AppendColumn("服务", width=50)
    
    ble_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, 
                  lambda evt: _on_item_double_click(main_panel, 'ble', evt.GetIndex()))
    
    sizer.Add(ble_list, 1, wx.EXPAND | wx.ALL, 5)
    
    ble_stats = wx.StaticText(parent, label="发现 0 个蓝牙设备")
    sizer.Add(ble_stats, 0, wx.ALL, 5)
    
    parent.SetSizer(sizer)
    return ble_list, ble_stats

def _on_item_double_click(panel, device_type, index):
    global _wifi_devices, _ble_devices
    
    if device_type == 'wifi' and index < len(_wifi_devices):
        device_info = _wifi_devices[index]
        dialog = DeviceDetailDialog(panel, device_info)
        dialog.ShowModal()
        dialog.Destroy()
    elif device_type == 'ble' and index < len(_ble_devices):
        device_info = _ble_devices[index]
        dialog = DeviceDetailDialog(panel, device_info)
        dialog.ShowModal()
        dialog.Destroy()

def _on_toggle_scan(panel):
    if _is_scanning:
        stop_scanning()
        panel.scan_btn.SetLabel("开始扫描")
        panel.status_text.SetLabel("扫描已停止")
    else:
        start_scanning()
        panel.scan_btn.SetLabel("停止扫描")
        panel.status_text.SetLabel("正在扫描...")

def _on_clear(panel):
    panel.wifi_list.DeleteAllItems()
    panel.ble_list.DeleteAllItems()
    panel.wifi_stats.SetLabel("发现 0 个WiFi网络")
    panel.ble_stats.SetLabel("发现 0 个蓝牙设备")

def _update_ui(panel, wifi_devices, ble_devices):
    if not panel or not hasattr(panel, 'wifi_list'):
        return
    
    panel.wifi_list.DeleteAllItems()
    for i, wifi in enumerate(wifi_devices):
        index = panel.wifi_list.InsertItem(i, wifi['ssid'])
        panel.wifi_list.SetItem(index, 1, wifi['bssid'])
        panel.wifi_list.SetItem(index, 2, str(wifi['signal']))
        panel.wifi_list.SetItem(index, 3, str(wifi['noise']))
        panel.wifi_list.SetItem(index, 4, str(wifi['snr']))
        panel.wifi_list.SetItem(index, 5, str(wifi['channel']))
        panel.wifi_list.SetItem(index, 6, wifi['auth'])
    
    wifi_count = len(wifi_devices)
    panel.wifi_stats.SetLabel(f"发现 {wifi_count} 个WiFi网络")
    panel.notebook.SetPageText(0, f"WiFi信号 ({wifi_count})")
    
    panel.ble_list.DeleteAllItems()
    for i, ble in enumerate(ble_devices):
        index = panel.ble_list.InsertItem(i, ble['name'])
        panel.ble_list.SetItem(index, 1, ble['address'])
        panel.ble_list.SetItem(index, 2, str(ble['signal']))
        panel.ble_list.SetItem(index, 3, str(ble['noise']))
        panel.ble_list.SetItem(index, 4, str(ble['snr']))
        service_count = len(ble.get('service_uuids', []))
        panel.ble_list.SetItem(index, 5, str(service_count))
    
    ble_count = len(ble_devices)
    panel.ble_stats.SetLabel(f"发现 {ble_count} 个蓝牙设备")
    panel.notebook.SetPageText(1, f"蓝牙设备 ({ble_count})")
    
    panel.status_text.SetLabel(
        f"最后更新: {datetime.now().strftime('%H:%M:%S')} | "
        f"双击列表项查看详情"
    )

# ==================== 测试代码 ====================

def main():
    app = wx.App()
    
    frame = wx.Frame(None, title="无线电信号探测仪", size=(1100, 750))
    
    def on_exit(evt):
        stop_scanning()
        frame.Close()
    
    def on_about(evt):
        wx.MessageBox(
            "无线电信号探测模块 v3.0\n\n"
            "功能：\n"
            "• WiFi信号扫描 - SSID、BSSID、信号强度、信道、加密\n"
            "• 蓝牙设备扫描 - 名称、地址、信号强度、服务列表\n"
            "• 信噪比(SNR)计算 - 显示信号质量\n"
            "• 双击列表项查看完整详情\n\n"
            "全部使用内置天线探测，无需额外硬件！\n\n"
            "依赖库：\n"
            "• pywifi - WiFi探测\n"
            "• bleak - 蓝牙探测\n"
            "• wxPython - GUI框架",
            "关于",
            wx.OK | wx.ICON_INFORMATION
        )
    
    panel = create_panel(frame)
    
    frame.Bind(wx.EVT_CLOSE, lambda evt: (stop_scanning(), evt.Skip()))
    
    frame.Center()
    frame.Show()
    
    app.MainLoop()

if __name__ == "__main__":
    print("=" * 70)
    print("无线电信号探测模块 v3.0")
    print("=" * 70)
    print("使用电脑内置天线探测WiFi、蓝牙信号")
    print("\n依赖库检查:")
    
    libs = [
        ("pywifi", "WiFi探测"),
        ("bleak", "蓝牙探测"),
        ("wx", "GUI框架")
    ]
    
    all_ok = True
    for lib, name in libs:
        try:
            __import__(lib)
            print(f"  ✓ {lib:10} - {name}")
        except ImportError:
            print(f"  ✗ {lib:10} - {name} (pip install {lib})")
            all_ok = False
    
    print("\n" + "=" * 70)
    if all_ok:
        print("所有依赖已安装，启动测试界面...\n")
        print("功能说明:")
        print("   WiFi探测 - 列出附近WiFi网络及信号质量")
        print("   蓝牙探测 - 扫描BLE设备及服务信息")
        print("   双击设备 - 查看完整详情信息")
        print("\n" + "=" * 70)
        main()
    else:
        print("请先安装缺失的依赖库")
        input("按回车键退出...")