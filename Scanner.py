# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import wx
import os
import re
import sys
import csv
import time
import socket
import shutil
import struct
import ipaddress
import platform
import threading
import subprocess
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, wait

import ProcUtil
import Adminchecker

sys_type = platform.system()

_MAX_HOSTS = 65536
_MAX_CONNECTS = 200000
_PING_WORKERS = 64
_PING_WORKERS_MAX = 256
_CONNECT_WORKERS = 200
_CONNECT_WORKERS_MAX = 1000
_PORT_SCAN_TIMEOUT = 0.8
_PING_TIMEOUT = 1.0
_BANNER_TIMEOUT = 1.0
_BANNER_LIMIT = 256

_FLUSH_INTERVAL = 0.3
_TCP_PORTS = [80, 443, 22, 21, 23, 25, 53, 110, 143, 3306, 3389, 8080]


def _run_cmd(cmd, timeout=10):
    try:
        proc = ProcUtil.popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace')
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode or 0, out or ''
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.communicate()
        except Exception:
            pass
        return -1, ''
    except Exception as e:
        logging.warning(f"命令执行失败: {cmd} - {e}")
        return -1, ''


def is_admin():
    try:
        return bool(Adminchecker.is_admin())
    except Exception:
        return False


_VIRTUAL_KEYS = (
    'virbr', 'lxc', 'lxd', 'docker', 'veth', 'br-', 'vmnet', 'vboxnet', 'vbox',
    'loopback', 'zt', 'tun', 'tap', 'tailscale', 'utun', 'wsl', 'hyper-v', 'vethernet',
)


def _is_virtual_iface(name, ip):
    lower = (name or '').lower()
    if any(key in lower for key in _VIRTUAL_KEYS):
        return True
    if lower.startswith(('lo', 'vir', 'docker', 'veth', 'br-')):
        return True
    return ip.startswith(('10.0.2.', '10.0.3.'))


def local_networks():
    candidates = []
    try:
        import psutil
        stats = psutil.net_if_stats()
        for name, addrs in psutil.net_if_addrs().items():
            st = stats.get(name)
            running = bool(st.isup) if st is not None else True
            for addr in addrs:
                if addr.family != socket.AF_INET:
                    continue
                ip = addr.address
                if not ip or ip.startswith('127.'):
                    continue
                mask = getattr(addr, 'netmask', None)
                try:
                    net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                except Exception:
                    continue
                if net.num_addresses < 4:
                    continue
                candidates.append({'iface': name, 'ip': ip, 'network': str(net),
                                   'virtual': _is_virtual_iface(name, ip),
                                   'up': running})
    except Exception as e:
        logging.warning(f"枚举本机网段失败: {e}")
    candidates.sort(key=lambda c: (c['virtual'], not c['up'], c['network']))
    return candidates


def _addr_to_hosts(token):
    host = token.strip()
    if not host:
        raise ValueError("空目标")
    try:
        if '/' in host:
            net = ipaddress.IPv4Network(host, strict=False)
            if net.num_addresses > _MAX_HOSTS:
                raise ValueError(f"网段过大，超过上限 {_MAX_HOSTS}")
            return [str(h) for h in net.hosts()]
        if '-' in host:
            first, last = [x.strip() for x in host.split('-', 1)]
            start = ipaddress.IPv4Address(first)
            end = ipaddress.IPv4Address(last) if '.' in last else \
                ipaddress.IPv4Address(f"{first.rsplit('.', 1)[0]}.{last}")
            if int(end) < int(start):
                raise ValueError(f"网段起止颠倒: {host}")
            if int(end) - int(start) + 1 > _MAX_HOSTS:
                raise ValueError(f"网段过大，超过上限 {_MAX_HOSTS}")
            return [str(ipaddress.IPv4Address(i)) for i in range(int(start), int(end) + 1)]
        ipaddress.IPv4Address(host)
        return [host]
    except ValueError as e:
        if isinstance(e, ValueError) and '目标' in str(e):
            raise
        raise ValueError(f"目标格式无效: {host}")


def parse_targets(text, resolve=False):
    hosts = []
    seen = set()
    for raw in re.split(r'[\s,;]+', text or ''):
        token = raw.strip()
        if not token:
            continue
        if resolve and _looks_like_host(token):
            ip = _resolve_host(token)
            if not ip:
                raise ValueError(f"无法解析目标: {token}")
            token = ip
        for ip in _addr_to_hosts(token):
            if ip not in seen:
                seen.add(ip)
                hosts.append(ip)
        if len(hosts) > _MAX_HOSTS:
            raise ValueError(f"目标数量超过上限 {_MAX_HOSTS}")
    if not hosts:
        raise ValueError("请输入目标")
    return hosts


def _port_token(token):
    token = token.strip()
    if not token:
        return []
    if '-' in token:
        first, last = token.split('-', 1)
        try:
            start, end = int(first), int(last)
        except ValueError:
            raise ValueError(f"端口范围无效: {token}")
        if start < 1 or end > 65535 or start > end:
            raise ValueError(f"端口范围无效: {token}")
        return list(range(start, end + 1))
    try:
        port = int(token)
    except ValueError:
        raise ValueError(f"端口格式无效: {token}")
    if port < 1 or port > 65535:
        raise ValueError(f"端口超出范围: {token}")
    return [port]


def parse_ports(text):
    ports = set()
    for raw in re.split(r'[\s,;]+', text or ''):
        if not raw.strip():
            continue
        try:
            ports.update(_port_token(raw))
        except ValueError:
            raise
        except Exception:
            raise ValueError(f"端口格式无效: {raw}")
    if not ports:
        raise ValueError("请输入端口或端口范围")
    return sorted(ports)


def _looks_like_host(token):
    if '/' in token or '-' in token:
        return False
    try:
        ipaddress.IPv4Address(token)
        return False
    except Exception:
        return bool(re.fullmatch(r'[A-Za-z0-9_.*\-]+', token))


def parse_targets_and_ports(target_text, port_text):
    hosts = parse_targets(target_text, resolve=True)
    ports = parse_ports(port_text)
    return hosts, ports


_PING_FALLBACK = {'busybox': None}
_BUILTIN_SERVICES = {
    7: 'echo', 20: 'ftp-data', 21: 'ftp', 22: 'ssh', 23: 'telnet', 25: 'smtp', 53: 'domain',
    67: 'dhcp', 69: 'tftp', 80: 'http', 110: 'pop3', 111: 'rpcbind', 123: 'ntp', 135: 'msrpc',
    137: 'netbios-ns', 139: 'netbios-ssn', 143: 'imap', 161: 'snmp', 389: 'ldap', 443: 'https',
    445: 'microsoft-ds', 465: 'smtps', 500: 'isakmp', 512: 'exec', 513: 'login', 514: 'shell',
    587: 'submission', 631: 'ipp', 636: 'ldaps', 873: 'rsync', 993: 'imaps', 995: 'pop3s',
    1080: 'socks', 1433: 'ms-sql-s', 1521: 'oracle', 1723: 'pptp', 2049: 'nfs', 2375: 'docker',
    3000: 'http-alt', 3306: 'mysql', 3389: 'ms-wbt-server', 5000: 'http-alt', 5432: 'postgresql',
    5601: 'kibana', 5900: 'rfb', 5985: 'wsman', 6379: 'redis', 7001: 'weblogic', 8000: 'http-alt',
    8080: 'http-proxy', 8081: 'http-alt', 8443: 'https-alt', 8888: 'http-alt', 9000: 'http-alt',
    9090: 'http-alt', 9200: 'elasticsearch', 11211: 'memcache', 27017: 'mongodb',
}


def _ping_commands(ip, timeout):
    wait_s = max(1, int(round(timeout)))
    wait_ms = max(1, int(timeout * 1000))
    if sys_type == 'Windows':
        return [['ping', '-n', '1', '-w', str(wait_ms), ip]], re.compile(r'[<=](\d+)\s*ms')
    pattern = re.compile(r'time[=<]([\d.]+)\s*ms')
    commands = [['ping', '-c', '1', '-W', str(wait_s), ip]]
    fallback = _PING_FALLBACK['busybox']
    if fallback is None:
        fallback = _PING_FALLBACK['busybox'] = bool(shutil.which('busybox'))
    if fallback:
        commands.append(['busybox', 'ping', '-c', '1', '-W', str(wait_s), ip])
    return commands, pattern


def ping_host(ip, timeout=_PING_TIMEOUT):
    commands, pattern = _ping_commands(ip, timeout)
    for cmd in commands:
        proc = None
        try:
            proc = ProcUtil.popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace')
            out, _ = proc.communicate(timeout=timeout + 3)
        except Exception:
            if proc is not None:
                try:
                    proc.kill()
                    proc.communicate()
                except Exception:
                    pass
            continue
        if proc.returncode != 0:
            continue
        match = pattern.search(out or '')
        return True, (float(match.group(1)) if match else None)
    return False, None


def _normalize_mac(mac):
    parts = re.split(r'[:-]', (mac or '').strip())
    if len(parts) != 6:
        return ''
    try:
        if not all(re.fullmatch(r'[0-9A-Fa-f]{1,2}', p) for p in parts):
            return ''
        return ':'.join(p.upper().rjust(2, '0') for p in parts)
    except Exception:
        return ''


def read_arp_table():
    entries = {}
    if sys_type == 'Windows':
        code, out = _run_cmd(['arp', '-a'])
        for line in out.splitlines():
            tokens = line.split()
            if len(tokens) >= 2 and re.fullmatch(r'\d{1,3}(\.\d{1,3}){3}', tokens[0]):
                mac = _normalize_mac(tokens[1])
                if mac:
                    entries[tokens[0]] = mac
    else:
        code, out = _run_cmd(['ip', 'neigh', 'show'])
        if code != 0 or not out.strip():
            code, out = _run_cmd(['arp', '-n'])
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 4 and re.fullmatch(r'\d{1,3}(\.\d{1,3}){3}', parts[0]):
                    if 'incomplete' in line:
                        continue
                    mac = _normalize_mac(parts[2])
                    if mac:
                        entries[parts[0]] = mac
        else:
            for line in out.splitlines():
                parts = line.split()
                if not parts or not re.fullmatch(r'\d{1,3}(\.\d{1,3}){3}', parts[0]):
                    continue
                if 'lladdr' not in parts or 'FAILED' in parts or 'INCOMPLETE' in parts:
                    continue
                mac = _normalize_mac(parts[parts.index('lladdr') + 1])
                if mac:
                    entries[parts[0]] = mac
    return entries


def scapy_available():
    try:
        import scapy  # noqa: F401
        return True
    except Exception:
        return False


def scapy_install_hint():
    if sys.platform.startswith('win'):
        return 'pip install scapy'
    return 'pip install --user scapy'


def _iface_for_ip(ip):
    try:
        import psutil
        for name, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family != socket.AF_INET or not addr.address:
                    continue
                try:
                    net = ipaddress.IPv4Network(f"{addr.address}/{addr.netmask}", strict=False)
                except Exception:
                    continue
                if ipaddress.IPv4Address(ip) in net:
                    return name
    except Exception:
        pass
    return None


def _group_by_iface(targets):
    groups = {}
    for ip in targets:
        groups.setdefault(_iface_for_ip(ip), []).append(ip)
    return groups


def arp_sweep(hosts, timeout=2.0, stop_event=None, progress=None):
    from scapy.all import ARP, Ether, srp
    targets = list(hosts)
    result = {}
    done = 0
    batch = 64
    for iface, group in _group_by_iface(targets).items():
        for i in range(0, len(group), batch):
            if stop_event is not None and stop_event.is_set():
                return result
            chunk = group[i:i + batch]
            kwargs = {'timeout': timeout, 'verbose': False, 'retry': 0}
            if iface:
                kwargs['iface'] = iface
            try:
                answered, _ = srp(Ether(dst='ff:ff:ff:ff:ff:ff') / ARP(pdst=chunk), **kwargs)
            except Exception as e:
                logging.warning(f"ARP 扫描失败: {e}")
                answered = []
            for _, rcv in answered:
                result[rcv.psrc] = _normalize_mac(rcv.hwsrc)
            done += len(chunk)
            if progress:
                progress(done, result)
    return result


def tcp_trigger(hosts, ports=(80, 443, 22, 445, 139, 53), timeout=0.3,
                workers=64, stop_event=None):
    tasks = [(ip, port) for ip in hosts for port in ports]

    def probe(task):
        if stop_event is not None and stop_event.is_set():
            return
        ip, port = task
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect_ex((ip, port))
        except Exception:
            pass
        finally:
            try:
                sock.close()
            except Exception:
                pass

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(probe, tasks))


_NAME_CACHE = {}
_NAME_LOCK = threading.Lock()


def _dns_encode_name(name):
    out = b''
    for part in name.strip('.').split('.'):
        if part:
            out += bytes([len(part)]) + part.encode('ascii', 'ignore')
    return out + b'\x00'


def _dns_read_name(data, offset):
    labels = []
    end = offset
    jumped = False
    hops = 0
    while offset < len(data):
        length = data[offset]
        if length & 0xC0 == 0xC0:
            if not jumped:
                end = offset + 2
            offset = ((length & 0x3F) << 8) | data[offset + 1]
            jumped = True
            hops += 1
            if hops > 12:
                break
            continue
        if length == 0:
            if not jumped:
                end = offset + 1
            break
        offset += 1
        labels.append(data[offset:offset + length].decode('utf-8', 'replace'))
        offset += length
    return '.'.join(labels), end


def _dns_ptr_name(data):
    try:
        qdcount = struct.unpack('>H', data[4:6])[0]
        ancount = struct.unpack('>H', data[6:8])[0]
        offset = 12
        for _ in range(qdcount):
            _, offset = _dns_read_name(data, offset)
            offset += 4
        for _ in range(ancount):
            _, offset = _dns_read_name(data, offset)
            rtype, _, _, rdlen = struct.unpack('>HHIH', data[offset:offset + 10])
            offset += 10
            if rtype == 12:
                name, _ = _dns_read_name(data, offset)
                if name:
                    return name
            offset += rdlen
    except Exception:
        pass
    return ''


def _mdns_lookup(ip, timeout=0.6):
    sock = None
    try:
        rev = '.'.join(reversed(ip.split('.'))) + '.in-addr.arpa'
        query = struct.pack('>HHHHHH', 0, 0, 1, 0, 0, 0)
        query += _dns_encode_name(rev) + struct.pack('>HH', 12, 1)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(timeout)
        sock.sendto(query, ('224.0.0.251', 5353))
        deadline = time.time() + timeout
        while time.time() < deadline:
            data, addr = sock.recvfrom(2048)
            if addr[0] != ip:
                continue
            name = _dns_ptr_name(data)
            if name:
                return name[:-6] if name.lower().endswith('.local') else name
    except Exception:
        return ''
    finally:
        if sock is not None:
            sock.close()
    return ''


def _netbios_lookup(ip, timeout=0.5):
    sock = None
    try:
        raw = b'*' + b'\x00' * 15
        enc = bytearray()
        for byte in raw:
            enc.append(ord('A') + (byte >> 4))
            enc.append(ord('A') + (byte & 0x0F))
        packet = struct.pack('>HHHHHH', 0x1234, 0, 1, 0, 0, 0)
        packet += bytes([32]) + bytes(enc) + b'\x00' + struct.pack('>HH', 0x0021, 0x0001)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(packet, (ip, 137))
        data, _ = sock.recvfrom(2048)
        _, offset = _dns_read_name(data, 12)
        offset += 4
        _, offset = _dns_read_name(data, offset)
        offset += 10
        count = data[offset]
        offset += 1
        fallback = ''
        for _ in range(count):
            raw_name = data[offset:offset + 16].rstrip(b'\x00 ').decode('ascii', 'replace')
            kind = data[offset + 16]
            offset += 18
            if not raw_name:
                continue
            if kind == 0x00 and not raw_name.startswith('__'):
                return raw_name
            if not fallback and kind == 0x20:
                fallback = raw_name
        return fallback
    except Exception:
        return ''
    finally:
        if sock is not None:
            sock.close()


def _avahi_lookup(ip):
    exe = shutil.which('avahi-resolve')
    if not exe:
        return ''
    code, out = _run_cmd([exe, '-a', ip], timeout=1.2)
    if code != 0:
        return ''
    parts = out.strip().split()
    return parts[-1] if len(parts) >= 2 else ''


def _netbios_tool(ip):
    if sys_type == 'Windows':
        code, out = _run_cmd(['nbtstat', '-A', ip], timeout=1.5)
        if code != 0:
            return ''
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and '<00>' in parts[1] and parts[2].upper() == 'UNIQUE':
                return parts[0].strip()
        return ''
    exe = shutil.which('nmblookup')
    if not exe:
        return ''
    code, out = _run_cmd([exe, '-A', ip], timeout=1.5)
    for line in out.splitlines():
        if '<00>' not in line or '__MSBROWSE__' in line:
            continue
        parts = line.split()
        if parts:
            return parts[0].strip()
    return ''


def reverse_lookup(ip):
    with _NAME_LOCK:
        if ip in _NAME_CACHE:
            return _NAME_CACHE[ip]
    name = ''
    try:
        name = socket.gethostbyaddr(ip)[0]
    except Exception:
        name = ''
    if not name or name == ip:
        try:
            name = (_mdns_lookup(ip) or _netbios_lookup(ip)
                    or _avahi_lookup(ip) or _netbios_tool(ip))
        except Exception as e:
            logging.warning(f"主机名解析失败: {ip} - {e}")
            name = ''
    if name == ip:
        name = ''
    with _NAME_LOCK:
        _NAME_CACHE[ip] = name
    return name


def service_name(port):
    if port not in _SERVICE_CACHE:
        name = ''
        try:
            name = socket.getservbyport(port, 'tcp')
        except Exception:
            name = ''
        _SERVICE_CACHE[port] = name or _BUILTIN_SERVICES.get(port, '')
    return _SERVICE_CACHE[port]


def _read_banner(sock):
    old = sock.gettimeout()
    try:
        sock.settimeout(_BANNER_TIMEOUT)
        data = sock.recv(_BANNER_LIMIT)
        return data.decode('utf-8', errors='replace').strip().replace('\r', ' ').replace('\n', ' ')
    except Exception:
        return ''
    finally:
        try:
            sock.settimeout(old)
        except Exception:
            pass


def tcp_probe(ip, port, timeout=_PORT_SCAN_TIMEOUT, banner=False):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    start = time.perf_counter()
    try:
        if sock.connect_ex((ip, port)) != 0:
            return None
        elapsed = (time.perf_counter() - start) * 1000
        text = _read_banner(sock) if banner else ''
        return elapsed, text
    except Exception:
        return None
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _resolve_host(host):
    try:
        ipaddress.IPv4Address(host)
        return host
    except Exception:
        pass
    try:
        return socket.gethostbyname(host)
    except Exception:
        return None


def _blank(value):
    if value is None or value == '':
        return '-'
    return value


def _sort_ip(text):
    try:
        return (0, int(ipaddress.IPv4Address(text)))
    except Exception:
        return (1, 0)


_SERVICE_CACHE = {}


def _write_csv(path, header, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def confirm_scope(parent):
    answer = wx.MessageBox(
        "本次扫描范围较大。\n请确认目标属于自有网络或已获授权范围，仅对已授权目标继续。",
        "确认扫描范围", wx.YES_NO | wx.ICON_QUESTION, parent)
    return answer == wx.YES


# ==================== 公共控件 ====================

class _ThinBar(wx.Panel):
    def __init__(self, parent, width=170, height=8):
        super().__init__(parent, size=(width, height))
        self._ratio = 0.0
        self.SetMinSize((width, height))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def SetRatio(self, ratio):
        ratio = max(0.0, min(1.0, float(ratio)))
        if abs(ratio - self._ratio) < 0.001:
            return
        self._ratio = ratio
        self.Refresh()

    def _on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        w, h = self.GetClientSize()
        if w <= 2 or h <= 2:
            return
        track = wx.Colour(214, 218, 224)
        fill = wx.Colour(78, 126, 184)
        radius = h // 2
        dc.SetPen(wx.Pen(track, 0))
        dc.SetBrush(wx.Brush(track))
        dc.DrawRoundedRectangle(0, 0, w, h, radius)
        filled = int(w * self._ratio)
        if filled > 1:
            dc.SetBrush(wx.Brush(fill))
            dc.DrawRoundedRectangle(0, 0, filled, h, radius)


class _ScanPanel(wx.Panel):
    ROW_LIMIT = 20000
    KEY_FIELDS = 1
    EXPORT_NAME = "scan_result.csv"

    def __init__(self, parent):
        super().__init__(parent)
        self.stopping = threading.Event()
        self.total = 0
        self.done = 0
        self.found = 0
        self.start_ts = 0.0
        self._pending = []
        self._row_index = {}
        self.running = False
        self._flush_scheduled = False
        self._list_ctrl = None
        self._flush_timer = None
        self._stop_watch = None
        self.log_text = None

    def _font(self):
        return self.GetFont()

    def _icon_btn(self, icon_name, fallback, tip):
        path = os.path.join('icons', icon_name)
        if os.path.exists(path):
            try:
                btn = wx.BitmapButton(self, bitmap=wx.Bitmap(path))
                btn.SetToolTip(tip)
                return btn
            except Exception:
                pass
        btn = wx.Button(self, label=fallback, size=(56, -1))
        btn.SetToolTip(tip)
        return btn

    def _more_btn(self):
        path = os.path.join('icons', 'more.png')
        if os.path.exists(path):
            try:
                btn = wx.BitmapButton(self, bitmap=wx.Bitmap(path))
                btn.SetToolTip("更多")
                return btn
            except Exception:
                pass
        btn = wx.Button(self, label="...", size=(44, -1))
        btn.SetToolTip("更多")
        return btn

    def _menu_item(self, menu, label, handler):
        item = menu.Append(wx.ID_ANY, label)
        self.Bind(wx.EVT_MENU, handler, item)
        return item

    def _toolbar(self, vbox):
        row = wx.BoxSizer(wx.HORIZONTAL)
        vbox.Add(row, 0, wx.EXPAND | wx.ALL, 8)
        return row

    def _section(self, vbox, title):
        header = wx.Button(self, label=f"▸ {title}", style=wx.BORDER_NONE)
        header.SetFont(self._font())
        body = wx.Panel(self)
        row = wx.BoxSizer(wx.HORIZONTAL)
        body.SetSizer(row)
        vbox.Add(header, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        vbox.Add(body, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        body.Hide()

        def toggle(event):
            shown = not body.IsShown()
            body.Show(shown)
            header.SetLabel(("▾ " if shown else "▸ ") + title)
            self.Layout()

        header.Bind(wx.EVT_BUTTON, toggle)
        self._sections = getattr(self, '_sections', {})
        self._sections[title] = (header, body, toggle)
        return body, row

    def _label(self, parent, text):
        lbl = wx.StaticText(parent, label=text)
        lbl.SetFont(self._font())
        return lbl

    def _log_pane(self, vbox):
        body, row = self._section(vbox, "日志")
        row.SetOrientation(wx.VERTICAL)
        self.log_text = wx.TextCtrl(body, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.log_text.SetFont(self._font())
        self.log_text.SetMinSize((-1, 110))
        row.Add(self.log_text, 1, wx.EXPAND | wx.BOTTOM, 4)
        return body

    def _status_row(self, vbox):
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.status = self._label(self, "就绪")
        row.Add(self.status, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        self.progress = _ThinBar(self)
        row.Add(self.progress, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        vbox.Add(row, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 4)

    def log(self, text):
        wx.CallAfter(self._append_log, text)

    def _append_log(self, text):
        if not self.log_text:
            return
        self.log_text.Freeze()
        try:
            lines = self.log_text.GetNumberOfLines()
            if lines > 500:
                self.log_text.Remove(0, self.log_text.GetLineLength(0) + 1)
            self.log_text.AppendText(f"[{time.strftime('%H:%M:%S')}] {text}\n")
        finally:
            self.log_text.Thaw()

    def _start_flusher(self, interval):
        def tick():
            if getattr(self, '_flush_timer', None) is None:
                return
            self._progress_update(self.done, self.total, self.found)
            self._flush_rows()
            self._flush_timer.Start(int(interval * 1000), oneShot=True)
        if getattr(self, '_flush_timer', None) is None:
            self._flush_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, lambda event: tick(), self._flush_timer)
        tick()

    def _stop_flusher(self):
        timer = getattr(self, '_flush_timer', None)
        if timer is not None:
            timer.Stop()

    def _progress_update(self, done, total, found, final=False):
        self.progress.SetRatio(done / total if total else 0)
        if final:
            self.status.SetLabel(f"完成 {done}/{total} · {found} 项")
            return
        elapsed = time.time() - self.start_ts
        self.status.SetLabel(f"{done}/{total} · {found} 项 · {elapsed:.1f} 秒")

    def _reset_progress(self, total):
        self.total = total
        self.done = 0
        self.found = 0
        self.start_ts = time.time()
        self.progress.SetRatio(0)
        self.status.SetLabel(f"准备 {total} 项")

    def _set_running(self, running):
        self.running = running
        self.start_btn.Enable(not running)
        self.stop_btn.Enable(running)
        self.GetParent().Freeze()
        try:
            self.Layout()
        finally:
            self.GetParent().Thaw()

    def _on_start(self, event):
        if self._stop_watch is not None:
            self._stop_watch.Stop()
        self.stopping.clear()
        self._reset_progress(0)
        self._progress_update(0, 0, 0)
        self._set_running(True)
        try:
            self._run()
        except Exception as e:
            logging.error(f"扫描启动失败: {e}")
            self.log(f"扫描启动失败: {e}")
            self._set_running(False)

    def _on_stop(self, event):
        if not self.stopping.is_set():
            self.log("已请求停止")
        self.stopping.set()
        self._stop_flusher()
        if not self.start_btn.IsEnabled():
            self.status.SetLabel("正在停止...")
            self._stop_watch = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._check_stopped, self._stop_watch)
            self._stop_watch.Start(200)

    def _check_stopped(self, event):
        if self.running:
            return
        self._stop_watch.Stop()
        self._set_running(False)
        self._stop_flusher()
        self._flush_rows()
        self.progress.SetRatio(self.done / self.total if self.total else 0)
        self.status.SetLabel(f"已停止 · {self.done}/{self.total}")

    def _build_list(self, sizer):
        self._list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT)
        self._list_ctrl.SetFont(self._font())
        sizer.Add(self._list_ctrl, 1, wx.ALL | wx.EXPAND, 10)

    def _list_clear(self):
        self._pending.clear()
        self._row_index.clear()
        self._list_ctrl.DeleteAllItems()

    def _flush_rows(self):
        self._flush_scheduled = False
        if not self._pending or not self._list_ctrl:
            return
        rows, self._pending = self._pending, []
        self._list_ctrl.Freeze()
        try:
            for row in rows:
                if self.KEY_FIELDS > 1:
                    key = ':'.join(str(row[i]) for i in range(self.KEY_FIELDS))
                else:
                    key = str(row[0])
                index = self._row_index.get(key)
                if index is None:
                    index = self._list_ctrl.GetItemCount()
                    if index >= self.ROW_LIMIT:
                        continue
                    self._list_ctrl.InsertItem(index, str(row[0]))
                    self._row_index[key] = index
                for col, value in enumerate(row[1:], start=1):
                    self._list_ctrl.SetItem(index, col, str(value))
        finally:
            self._list_ctrl.Thaw()

    def _queue_rows(self, rows):
        if not rows:
            return
        if len(self._pending) > 2000:
            self._flush_rows()
        self._pending.extend(rows)
        if not self._flush_scheduled:
            self._flush_scheduled = True
            wx.CallAfter(self._flush_rows)

    def _queue_now(self, rows):
        if rows:
            wx.CallAfter(self._queue_rows, rows)

    def _sync(self, done=None, found=None, rows=None):
        if done is not None:
            self.done = done
        if found is not None:
            self.found = found
        if rows:
            wx.CallAfter(self._queue_rows, rows)

    def _finish(self, message, detail=None):
        elapsed = time.time() - self.start_ts
        wx.CallAfter(self._finish_ui, message, detail, elapsed)

    def _finish_ui(self, message, detail, elapsed):
        self._stop_flusher()
        final_done = self.done if self.stopping.is_set() else self.total
        self.progress.SetRatio(final_done / self.total if self.total else 0)
        self.status.SetLabel(f"{message} · {elapsed:.1f} 秒")
        self._flush_rows()
        self._set_running(False)
        if detail:
            self.log(detail)

    def _on_copy(self, event):
        row = self._list_ctrl.GetFirstSelected()
        if row < 0:
            return
        values = [self._list_ctrl.GetItemText(row, c) for c in range(self._list_ctrl.GetColumnCount())]
        text = '\t'.join(values)
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()
            self.status.SetLabel("已复制")

    def _on_clear(self, event):
        self._list_clear()
        self.progress.SetRatio(0)
        self.status.SetLabel("已清空")

    def _all_ips(self):
        return [self._list_ctrl.GetItemText(i, 0) for i in range(self._list_ctrl.GetItemCount())]

    def _selection_ips(self):
        ips = []
        row = self._list_ctrl.GetFirstSelected()
        while row >= 0:
            ips.append(self._list_ctrl.GetItemText(row, 0))
            row = self._list_ctrl.GetNextSelected(row)
        return ips

    def _unique_ips(self, ips):
        return sorted(set(ips), key=_sort_ip)

    def _on_export(self, event):
        if self._list_ctrl.GetItemCount() == 0:
            self.log("没有可导出的结果")
            return
        dlg = wx.FileDialog(self, "导出结果", wildcard="CSV 文件 (*.csv)|*.csv",
                            defaultFile=self.EXPORT_NAME, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        path = dlg.GetPath()
        dlg.Destroy()
        header = [self._list_ctrl.GetColumn(c).GetText() for c in range(self._list_ctrl.GetColumnCount())]
        rows = []
        for i in range(self._list_ctrl.GetItemCount()):
            rows.append([self._list_ctrl.GetItemText(i, c) for c in range(self._list_ctrl.GetColumnCount())])
        try:
            _write_csv(path, header, rows)
            self.log(f"已导出 {len(rows)} 条结果到 {path}")
        except Exception as e:
            logging.error(f"导出失败: {e}")
            wx.MessageBox(f"导出失败: {e}", "错误", wx.OK | wx.ICON_ERROR, self)


# ==================== 主机发现 ====================

class HostDiscoveryPanel(_ScanPanel):
    EXPORT_NAME = "hosts.csv"

    def __init__(self, parent, send_to_ports_cb=None):
        super().__init__(parent)
        self.send_to_ports_cb = send_to_ports_cb
        vbox = wx.BoxSizer(wx.VERTICAL)

        bar = self._toolbar(vbox)
        self.target_text = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.target_text.SetFont(self._font())
        self.target_text.SetHint("网段或 IP，如 192.168.1.0/24、192.168.1.1-20")
        self.target_text.Bind(wx.EVT_TEXT_ENTER, self._on_start)
        bar.Add(self.target_text, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        detect_btn = wx.Button(self, label="探测", size=(64, -1))
        detect_btn.SetToolTip("探测本机网段")
        bar.Add(detect_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.start_btn = self._icon_btn('run.png', "开始", "开始扫描")
        self.stop_btn = self._icon_btn('stop.png', "停止", "停止扫描")
        self.stop_btn.Enable(False)
        bar.Add(self.start_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        bar.Add(self.stop_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        more_btn = self._more_btn()
        bar.Add(more_btn, 0, wx.ALIGN_CENTER_VERTICAL)

        win, adv = self._section(vbox, "高级")
        adv.Add(self._label(win, "超时(秒)"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.timeout_spin = wx.SpinCtrlDouble(win, min=0.2, max=10.0, inc=0.2, initial=_PING_TIMEOUT)
        self.timeout_spin.SetDigits(1)
        adv.Add(self.timeout_spin, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        adv.Add(self._label(win, "并发"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.workers_spin = wx.SpinCtrl(win, min=1, max=_PING_WORKERS_MAX, initial=_PING_WORKERS)
        adv.Add(self.workers_spin, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.resolve_check = wx.CheckBox(win, label="解析主机名")
        self.resolve_check.SetValue(True)
        self.resolve_check.SetToolTip("反查 DNS、mDNS 与 NetBIOS 名称")
        adv.Add(self.resolve_check, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.arp_check = wx.CheckBox(win, label="ARP 增强")
        self.arp_check.SetValue(True)
        adv.Add(self.arp_check, 0, wx.ALIGN_CENTER_VERTICAL)

        self._status_row(vbox)
        self._build_list(vbox)
        for col, (name, width) in enumerate((
                ("IP", 165), ("状态", 105), ("延迟(ms)", 95),
                ("MAC", 185), ("主机名", 195))):
            self._list_ctrl.InsertColumn(col, name, width=width)

        self._log_pane(vbox)
        self.SetSizer(vbox)

        menu = wx.Menu()
        self._menu_item(menu, "发送到端口扫描", self._on_send)
        menu.AppendSeparator()
        self._menu_item(menu, "导出 CSV", self._on_export)
        self._menu_item(menu, "清空结果", self._on_clear)
        menu.AppendSeparator()
        self._menu_item(menu, "以管理员身份重启", self._on_elevate)
        more_btn.Bind(wx.EVT_BUTTON, lambda event: self.PopupMenu(menu))

        detect_btn.Bind(wx.EVT_BUTTON, self._on_detect)
        self.start_btn.Bind(wx.EVT_BUTTON, self._on_start)
        self.stop_btn.Bind(wx.EVT_BUTTON, self._on_stop)
        self._list_ctrl.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self._on_copy)
        self._update_arp_hint()

    def _update_arp_hint(self):
        if not scapy_available():
            self.arp_check.SetToolTip(f"未安装 scapy，仅用 ping 与 ARP 表（{scapy_install_hint()}）")
        elif not is_admin():
            self.arp_check.SetToolTip("未提权，ARP 增强需以管理员身份重启")
        else:
            self.arp_check.SetToolTip("使用 ARP 广播发现局域网设备")

    def _on_detect(self, event):
        nets = local_networks()
        if not nets:
            self.status.SetLabel("未探测到可用网段")
            return
        real = [n for n in nets if not n['virtual']] or nets
        if len(real) == 1:
            self._fill_target(real[0])
            return
        menu = wx.Menu()
        for net in real[:8]:
            label = f"{net['network']}  ({net['iface']})"
            if net['virtual']:
                label += "  [虚拟]"
            item = menu.Append(wx.ID_ANY, label)
            self.Bind(wx.EVT_MENU, lambda e, n=net: self._fill_target(n), item)
        self.PopupMenu(menu)

    def _fill_target(self, net):
        self.target_text.SetValue(net['network'])
        self.status.SetLabel(f"已填入 {net['network']}")

    def fill_targets(self, ips):
        current = self.target_text.GetValue().strip()
        existing = [t for t in re.split(r'[\s,;]+', current) if t]
        expanded = set()
        for token in existing:
            try:
                expanded.update(_addr_to_hosts(token))
            except ValueError:
                pass
        merged = [ip for ip in ips if ip not in expanded]
        if not merged:
            self.status.SetLabel("目标已包含全部主机")
            return
        self.target_text.SetValue('\n'.join(existing + merged))
        self.status.SetLabel(f"已回填 {len(merged)} 个主机")

    def _on_elevate(self, event):
        try:
            import Window as _Window
            _Window.restart_as_elevated()
        except Exception as e:
            logging.error(f"提权重启失败: {e}")
            self.log(f"提权重启失败: {e}")

    def _on_send(self, event):
        ips = self._selection_ips() or self._all_ips()
        if not ips:
            self.log("列表中没有可发送的主机")
            return
        if self.send_to_ports_cb:
            self.send_to_ports_cb(self._unique_ips(ips))

    def _run(self):
        target_text = self.target_text.GetValue().strip()
        if not target_text:
            self.status.SetLabel("请先填写网段")
            self._set_running(False)
            return
        try:
            hosts = parse_targets(target_text)
        except ValueError as e:
            wx.MessageBox(str(e), "提示", wx.OK | wx.ICON_INFORMATION, self)
            self._set_running(False)
            return
        if len(hosts) > 256 and not confirm_scope(self):
            self.status.SetLabel("已取消")
            self._set_running(False)
            return
        opts = {
            'hosts': hosts,
            'timeout': self.timeout_spin.GetValue(),
            'workers': self.workers_spin.GetValue(),
            'resolve': self.resolve_check.GetValue(),
            'use_arp': self.arp_check.GetValue(),
        }
        self.log(f"开始扫描 {len(hosts)} 个目标，并发 {min(opts['workers'], _PING_WORKERS_MAX)}，"
                 f"超时 {opts['timeout']:.1f} 秒")
        self._reset_progress(len(hosts))
        self._progress_update(0, len(hosts), 0)
        self._start_flusher(_FLUSH_INTERVAL)
        threading.Thread(target=self._run_task, args=(opts,), daemon=True).start()

    def _run_task(self, opts):
        hosts = opts['hosts']
        timeout = opts['timeout']
        workers = max(1, min(opts['workers'], _PING_WORKERS_MAX))
        resolve = opts['resolve']
        use_arp = opts['use_arp']

        host_set = set(hosts)
        rows = {}

        name_pool = ThreadPoolExecutor(max_workers=16) if resolve else None
        name_futures = {}
        name_found = {'n': 0}

        def schedule_name(ip):
            if name_pool is None or ip in name_futures:
                return
            if rows.get(ip, {}).get('host'):
                return
            name_futures[ip] = name_pool.submit(reverse_lookup, ip)

        def harvest_names():
            batch = []
            for ip, fut in list(name_futures.items()):
                if not fut.done():
                    continue
                del name_futures[ip]
                try:
                    name = fut.result()
                except Exception:
                    name = ''
                row = rows.get(ip)
                if row is None:
                    continue
                if name:
                    row['host'] = name
                    name_found['n'] += 1
                batch.append(self._host_row(row))
            if batch:
                self._queue_now(batch)

        def merge(ip, mac='', delay=None, method='ARP'):
            hit = rows.get(ip)
            if hit is None:
                hit = rows[ip] = {'ip': ip, 'delay': None, 'mac': '',
                                  'methods': set(), 'method': method}
            if mac and not hit['mac']:
                hit['mac'] = mac
            if delay is not None:
                hit['delay'] = delay
            hit['methods'].add(method)
            if 'Ping' in hit['methods']:
                hit['method'] = 'Ping'
            elif 'ARP' in hit['methods']:
                hit['method'] = 'ARP'
            else:
                hit['method'] = 'ARP表'
            schedule_name(ip)
            return hit

        use_scapy = use_arp and scapy_available() and is_admin()
        arp_timeout = max(0.8, min(timeout, 3.0))
        if use_arp and not use_scapy:
            if not scapy_available():
                self.log(f"未安装 scapy，跳过 ARP 增强扫描（{scapy_install_hint()}）")
            else:
                self.log("未提权，跳过 ARP 增强扫描")

        arp_count = {'n': 0}
        if use_scapy:
            self.log(f"正在执行 ARP 广播扫描，网段 {len(hosts)} 个地址")

            def arp_progress(done_count, result):
                batch = [self._host_row(merge(ip, mac=mac, method='ARP'))
                         for ip, mac in result.items() if ip not in arp_shown]
                arp_shown.update(result)
                if batch:
                    self._queue_now(batch)
                self._sync(found=len(rows))

            arp_shown = set()

            try:
                found = arp_sweep(hosts, timeout=arp_timeout, stop_event=self.stopping,
                                  progress=arp_progress)
                for ip, mac in found.items():
                    merge(ip, mac=mac, method='ARP')
                arp_count['n'] = len(found)
                self.log(f"ARP 扫描发现 {arp_count['n']} 台设备")
                if not found:
                    self.log("ARP 广播无响应，改用 TCP 触发并读取 ARP 表")
                    tcp_trigger(hosts, stop_event=self.stopping)
                    fallback = {ip: mac for ip, mac in read_arp_table().items() if ip in host_set}
                    if fallback:
                        self._queue_now([self._host_row(merge(ip, mac=mac, method='ARP表'))
                                         for ip, mac in fallback.items()])
                        self.log(f"ARP 表补充 {len(fallback)} 台设备")
            except Exception as e:
                self.log(f"ARP 扫描失败: {e}")

        pre_table = read_arp_table()
        pre_new = []
        for ip in hosts:
            if ip in pre_table and ip not in rows:
                pre_new.append(merge(ip, mac=pre_table[ip], method='ARP表'))
        if pre_new:
            self._queue_now(self._host_rows(pre_new))
            self.log(f"ARP 表补充 {len(pre_new)} 台设备")
        self._sync(found=len(rows))

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(ping_host, ip, timeout): ip for ip in hosts}
            try:
                for index, fut in enumerate(as_completed(futures), start=1):
                    if self.stopping.is_set():
                        for f in futures:
                            f.cancel()
                        break
                    ip = futures[fut]
                    try:
                        ok, delay = fut.result()
                    except Exception:
                        ok, delay = False, None
                    batch = []
                    if ok:
                        batch.append(self._host_row(merge(ip, delay=delay, method='Ping')))
                    self._sync(done=index, found=len(rows))
                    self._queue_now(batch)
                    harvest_names()
            finally:
                pool.shutdown(wait=False, cancel_futures=True)

        try:
            post_table = read_arp_table()
        except Exception as e:
            logging.warning(f"读取 ARP 表失败: {e}")
            post_table = {}
        post_new = 0
        for ip in hosts:
            if ip in post_table:
                before = ip in rows
                merge(ip, mac=post_table[ip], method='ARP表')
                if not before:
                    post_new += 1
        if post_new:
            self.log(f"ARP 表补充 {post_new} 台设备")

        if name_futures:
            wait(list(name_futures.values()), timeout=4)
            harvest_names()
        if name_pool is not None:
            name_pool.shutdown(wait=False, cancel_futures=True)

        ordered = [rows[ip] for ip in sorted(rows, key=_sort_ip)]
        if resolve and ordered:
            named = sum(1 for row in ordered if row.get('host'))
            self.log(f"解析到 {named}/{len(ordered)} 个主机名")
        self.found = len(ordered)
        if not self.stopping.is_set():
            self.done = self.total
        self._queue_now(self._host_rows(ordered))
        head = "已中止" if self.stopping.is_set() else "完成"
        detail = (f"在线 {len(ordered)} 台（Ping {self._count_method(ordered, 'Ping')}、"
                  f"ARP {self._count_method(ordered, 'ARP')}、"
                  f"ARP表 {self._count_method(ordered, 'ARP表')}）")
        self._finish(f"{head} · {len(ordered)} 台", detail)

    def _count_method(self, rows, method):
        return sum(1 for r in rows if r['method'] == method)

    def _host_row(self, row):
        delay = f"{row['delay']:.1f}" if row.get('delay') is not None else '-'
        state = "在线" if row.get('delay') is not None else "疑似在线"
        return (row['ip'], state, delay, _blank(row.get('mac')),
                _blank(row.get('host')))

    def _host_rows(self, rows):
        return [self._host_row(row) for row in rows]


# ==================== 端口扫描 ====================

class PortScanPanel(_ScanPanel):
    KEY_FIELDS = 2
    EXPORT_NAME = "ports.csv"
    PRESETS = (
        ("预设", ""),
        ("常用 100", "100"),
        ("常用 1000", "1000"),
        ("1-1024", "1-1024"),
        ("1-65535", "1-65535"),
        ("Web", "80,443,8080,8443,8000,8888,3000,5000,9000"),
    )

    def __init__(self, parent, send_to_hosts_cb=None):
        super().__init__(parent)
        self.send_to_hosts_cb = send_to_hosts_cb
        vbox = wx.BoxSizer(wx.VERTICAL)

        bar = self._toolbar(vbox)
        self.target_text = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.target_text.SetFont(self._font())
        self.target_text.SetHint("目标，如 192.168.1.1 或 192.168.1.1-20")
        self.target_text.Bind(wx.EVT_TEXT_ENTER, self._on_start)
        bar.Add(self.target_text, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        self.port_text = wx.TextCtrl(self, size=(110, -1), style=wx.TE_PROCESS_ENTER)
        self.port_text.SetFont(self._font())
        self.port_text.SetHint("端口")
        self.port_text.Bind(wx.EVT_TEXT_ENTER, self._on_start)
        bar.Add(self.port_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        self.preset_choice = wx.Choice(self, choices=[p[0] for p in self.PRESETS], size=(96, -1))
        self.preset_choice.SetSelection(0)
        bar.Add(self.preset_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        self.start_btn = self._icon_btn('run.png', "开始", "开始扫描")
        self.stop_btn = self._icon_btn('stop.png', "停止", "停止扫描")
        self.stop_btn.Enable(False)
        bar.Add(self.start_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        bar.Add(self.stop_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        more_btn = self._more_btn()
        bar.Add(more_btn, 0, wx.ALIGN_CENTER_VERTICAL)

        win, adv = self._section(vbox, "高级")
        adv.Add(self._label(win, "超时(秒)"), 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self.timeout_spin = wx.SpinCtrlDouble(win, min=0.1, max=10.0, inc=0.1, initial=_PORT_SCAN_TIMEOUT)
        self.timeout_spin.SetDigits(1)
        adv.Add(self.timeout_spin, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        adv.Add(self._label(win, "并发"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.workers_spin = wx.SpinCtrl(win, min=1, max=_CONNECT_WORKERS_MAX, initial=_CONNECT_WORKERS)
        adv.Add(self.workers_spin, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.banner_check = wx.CheckBox(win, label="抓取 Banner")
        adv.Add(self.banner_check, 0, wx.ALIGN_CENTER_VERTICAL)

        self._status_row(vbox)
        self._build_list(vbox)
        for col, (name, width) in enumerate((
                ("IP", 175), ("端口", 85), ("服务", 115),
                ("耗时(ms)", 100), ("Banner", 240))):
            self._list_ctrl.InsertColumn(col, name, width=width)

        self._log_pane(vbox)
        self.SetSizer(vbox)

        menu = wx.Menu()
        self._menu_item(menu, "回填到主机发现", self._on_back)
        menu.AppendSeparator()
        self._menu_item(menu, "导出 CSV", self._on_export)
        self._menu_item(menu, "清空结果", self._on_clear)
        more_btn.Bind(wx.EVT_BUTTON, lambda event: self.PopupMenu(menu))

        self.start_btn.Bind(wx.EVT_BUTTON, self._on_start)
        self.stop_btn.Bind(wx.EVT_BUTTON, self._on_stop)
        self.preset_choice.Bind(wx.EVT_CHOICE, self._on_preset)
        self._list_ctrl.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self._on_copy)

    def _on_preset(self, event):
        index = self.preset_choice.GetSelection()
        if index <= 0:
            return
        token = self.PRESETS[index][1]
        if token == "100":
            value = ','.join(str(p) for p in _top_ports(100))
        elif token == "1000":
            value = ','.join(str(p) for p in _top_ports(1000))
        else:
            value = token
        self.port_text.SetValue(value)
        self.preset_choice.SetSelection(0)

    def set_targets(self, ips):
        current = self.target_text.GetValue().strip()
        existing = [t for t in re.split(r'[\s,;]+', current) if t]
        merged = [ip for ip in ips if ip not in existing]
        if not merged:
            self.status.SetLabel("目标已包含全部主机")
            return
        self.target_text.SetValue(', '.join(existing + merged))
        self.status.SetLabel(f"已接收 {len(merged)} 个主机")

    def _on_back(self, event):
        ips = self._unique_ips(self._selection_ips() or self._all_ips())
        if not ips:
            self.status.SetLabel("没有可回填的主机")
            return
        if self.send_to_hosts_cb:
            self.send_to_hosts_cb(ips)

    def _run(self):
        opts = {
            'target_text': self.target_text.GetValue(),
            'port_text': self.port_text.GetValue(),
            'timeout': self.timeout_spin.GetValue(),
            'workers': self.workers_spin.GetValue(),
            'banner': self.banner_check.GetValue(),
        }
        try:
            hosts, ports = parse_targets_and_ports(opts['target_text'], opts['port_text'])
        except ValueError as e:
            wx.MessageBox(str(e), "提示", wx.OK | wx.ICON_INFORMATION, self)
            self._set_running(False)
            return
        timeout = opts['timeout']
        workers = max(1, min(opts['workers'], _CONNECT_WORKERS_MAX))
        banner = opts['banner']
        total_conns = len(hosts) * len(ports)
        if total_conns > _MAX_CONNECTS and not confirm_scope(self):
            self.status.SetLabel("已取消")
            self._set_running(False)
            return
        self.log(f"开始扫描 {len(hosts)} 个主机、{len(ports)} 个端口，并发 {workers}，超时 {timeout:.1f} 秒")
        self._reset_progress(total_conns)
        self._progress_update(0, total_conns, 0)
        self._start_flusher(_FLUSH_INTERVAL)
        stop = self.stopping
        total = total_conns
        open_ports = {}
        lock = threading.Lock()
        state = {'done': 0, 'found': 0}
        tasks = [(ip, port) for ip in hosts for port in ports]

        def scan_one(task):
            ip, port = task
            if stop.is_set():
                return
            result = tcp_probe(ip, port, timeout, banner)
            batch = []
            with lock:
                state['done'] += 1
                if result is not None:
                    elapsed, text = result
                    open_ports.setdefault(ip, []).append(port)
                    state['found'] += 1
                    batch.append((ip, port, service_name(port),
                                  f"{elapsed:.1f}", _blank(text)))
                done_now = state['done']
                found_now = state['found']
            self._sync(done=done_now, found=found_now, rows=batch)

        def run_pool():
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(scan_one, tasks))
            with lock:
                done = state['done']
                summary = {ip: sorted(ports) for ip, ports in open_ports.items()}
                found = state.get('found', 0)
            wx.CallAfter(self._port_done, done, total, summary, found, stop.is_set())

        threading.Thread(target=run_pool, daemon=True).start()

    def _port_done(self, done, total, open_ports, found, stopped):
        self._stop_flusher()
        self.done = done
        self.found = found
        self.progress.SetRatio(done / total if total else 0)
        self._flush_rows()
        self._set_running(False)
        elapsed = time.time() - self.start_ts
        suffix = "已中止" if stopped else "完成"
        self.status.SetLabel(f"{suffix} · {found} 个端口 · {len(open_ports)} 台主机 · {elapsed:.1f} 秒")
        for ip in sorted(open_ports, key=_sort_ip):
            ports = open_ports[ip]
            self.log(f"{ip} 开放 {len(ports)} 个端口: {','.join(str(p) for p in ports)}")


_TOP_CACHE = {}


def _top_ports(count):
    if count in _TOP_CACHE:
        return _TOP_CACHE[count]
    well_known = list(range(1, 1025))
    seen = set()
    result = []
    for port in well_known:
        if service_name(port):
            seen.add(port)
            result.append(port)
            if len(result) >= count:
                break
    for port in range(1025, 65536):
        if len(result) >= count:
            break
        if port in seen:
            continue
        if service_name(port):
            result.append(port)
    if len(result) < count:
        for port in _TCP_PORTS:
            if len(result) >= count:
                break
            if port not in result:
                result.append(port)
    result = sorted(result[:count])
    _TOP_CACHE[count] = result
    return result


# ==================== 页面注册 ====================

HOST_TITLE = "主机发现"
PORT_TITLE = "端口扫描"


class ScanPage(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)


def create_containers(book):
    return ScanPage(book), ScanPage(book)


def build_panels(host_container, port_container):
    host_panel = HostDiscoveryPanel(host_container)
    port_panel = PortScanPanel(port_container)
    for container, panel in ((host_container, host_panel), (port_container, port_panel)):
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 1, wx.EXPAND)
        container.SetSizer(sizer)
        container.Layout()

    state = {'book': None, 'anchor': None}

    def switch(title):
        book = state['book']
        anchor = state['anchor']
        if book is None:
            return
        try:
            target = -1
            for i in range(book.GetPageCount()):
                if book.GetPageText(i) == title:
                    target = i
                    break
            if target < 0:
                logging.warning(f"未找到扫描子页: {title}")
                return
            if anchor:
                for i in range(book.GetPageCount()):
                    if book.GetPageText(i) == anchor and book.GetSelection() != i:
                        book.SetSelection(i)
                        break
            book.SetSelection(target)
        except Exception as e:
            logging.warning(f"页面切换失败: {e}")

    def bind(book_ctrl, anchor_title):
        state['book'] = book_ctrl
        state['anchor'] = anchor_title

    def send_to_ports(ips):
        port_panel.set_targets(ips)
        switch(PORT_TITLE)

    def send_to_hosts(ips):
        host_panel.fill_targets(ips)
        switch(HOST_TITLE)

    host_panel.send_to_ports_cb = send_to_ports
    port_panel.send_to_hosts_cb = send_to_hosts
    host_panel.bind_book = bind
    return host_panel, port_panel
