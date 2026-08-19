# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import wx
import requests
from bs4 import BeautifulSoup
import time
import os
import json
import threading
import platform
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

progress_dialog = None

DOWNLOAD_EXTENSIONS = [
    '.zip', '.jar', '.exe', '.msi', '.dmg', '.pkg',
    '.deb', '.rpm', '.tar.gz', '.tgz', '.7z', '.rar',
    '.apk', '.iso', '.img', '.bin', '.AppImage',
    '.mcpack', '.mcworld', '.mcaddon', '.mcjar',
    '.lua', '.js', '.ts', '.css', '.html', '.json', '.xml',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp',
    '.mp3', '.mp4', '.wav', '.flac', '.webm', '.mkv', '.avi',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.txt', '.md', '.py', '.java', '.cpp', '.c', '.h', '.go',
    '.rs', '.rb', '.php', '.sh', '.bat', '.ps1',
]

DOWNLOAD_WEB_ASSETS = ['.js', '.css', '.html', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.ico', '.woff', '.woff2', '.ttf', '.eot']

FAST_DOWNLOAD_EXTENSIONS = (
    '.zip', '.jar', '.exe', '.msi', '.dmg', '.pkg',
    '.deb', '.rpm', '.tar.gz', '.tgz', '.7z', '.rar',
    '.apk', '.iso', '.img', '.bin', '.AppImage',
    '.mcpack', '.mcworld', '.mcaddon', '.mcjar',
)

active_filter_extensions = list(FAST_DOWNLOAD_EXTENSIONS)

def parse_filter_extensions(text):
    exts = []
    for part in re.split(r'[,;\s\n]+', text or ''):
        part = part.strip().lstrip('*').strip()
        if not part:
            continue
        if not part.startswith('.'):
            part = '.' + part
        part = part.lower()
        if part not in exts:
            exts.append(part)
    return exts

def set_filter_extensions(text):
    global active_filter_extensions
    exts = parse_filter_extensions(text)
    if exts:
        active_filter_extensions = exts
    return active_filter_extensions

def get_filter_extensions_text():
    return ' '.join(sorted(active_filter_extensions, key=lambda e: e.lstrip('.')))

DOWNLOAD_URL_KEYWORDS = [
    'download', 'downloads', 'file', 'files', 'asset', 'assets',
    'release', 'releases', 'binary', 'binaries', 'artifact', 'artifacts',
    'raw', 'attachment', 'attachments', 'export', 'export/',
    'backup', 'archive', 'package', 'packages',
    'cdn', 'static', 'media', 'storage',
    'mod/', 'mods/', 'plugin/', 'plugins/',
    'version', 'versions', 'v1', 'v2', 'v3',
    'getfile', 'get-file', 'fetchfile', 'fetch-file',
    'downloadfile', 'download-file', 'dl/', 'dls/',
]

DOWNLOAD_CONTENT_TYPES = [
    'application/zip', 'application/java-archive', 'application/x-java-archive',
    'application/x-msdownload', 'application/x-msi', 'application/x-tar',
    'application/gzip', 'application/x-rar', 'application/x-7z',
    'application/octet-stream', 'application/binary',
    'application/vnd.android.package-archive',
    'application/deb', 'application/x-rpm',
    'application/pdf', 'application/msword',
    'application/vnd.openxmlformats', 'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/wasm', 'application/x-shockwave-flash',
    'application/vnd.minecraft',
    'audio/', 'video/', 'image/',
    'font/',
]

DOWNLOAD_CONTENT_DISPOSITION = ['attachment', 'inline']

def get_filename_from_url(url):
    from urllib.parse import unquote
    parsed = urlparse(url)
    path = parsed.path or url
    name = os.path.basename(path) or "download_file"
    return unquote(name)

def is_real_download_file(url):
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    query_lower = parsed.query.lower()
    for ext in DOWNLOAD_WEB_ASSETS:
        if path_lower.endswith(ext):
            return False
    filename = os.path.basename(parsed.path).lower()
    for ext in DOWNLOAD_EXTENSIONS:
        if filename.endswith(ext):
            return True
        if path_lower.endswith(ext):
            return True
    if query_lower:
        for ext in DOWNLOAD_EXTENSIONS:
            if query_lower.endswith(ext):
                return True
    return False

def is_fast_download_link(url):
    if not url:
        return False
    parsed = urlparse(url)
    path = parsed.path
    if not path or path == '/':
        return False
    path_lower = path.lower()
    for ext in FAST_DOWNLOAD_EXTENSIONS:
        if path_lower.endswith(ext):
            return True
    return False

def matches_filter(url):
    if not url:
        return False
    parsed = urlparse(url)
    path = parsed.path
    if not path or path == '/':
        return False
    path_lower = path.lower()
    for ext in active_filter_extensions:
        if path_lower.endswith(ext):
            return True
    return False

def is_download_link(url):
    parsed = urlparse(url)
    path_lower = parsed.path.lower()
    for ext in DOWNLOAD_EXTENSIONS:
        if path_lower.endswith(ext):
            return True
    combined = (parsed.path + '?' + parsed.query).lower() if parsed.query else parsed.path.lower()
    for ext in DOWNLOAD_EXTENSIONS:
        if combined.endswith(ext):
            return True
    if parsed.query:
        for qs_param in parse_qs(parsed.query).values():
            for val in qs_param:
                val_lower = val.lower()
                for ext in DOWNLOAD_EXTENSIONS:
                    if val_lower.endswith(ext):
                        return True
    filename = os.path.basename(parsed.path).lower()
    for ext in DOWNLOAD_EXTENSIONS:
        if filename.endswith(ext):
            return True
    url_lower = url.lower()
    keyword_score = 0
    for kw in DOWNLOAD_URL_KEYWORDS:
        if kw in url_lower:
            keyword_score += 1
    if keyword_score >= 1:
        has_file_ext = any(ext in path_lower for ext in DOWNLOAD_EXTENSIONS)
        if has_file_ext or keyword_score >= 2:
            return True
    if parsed.query:
        for qs_param in parse_qs(parsed.query).values():
            for val in qs_param:
                val_lower = val.lower()
                for ext in DOWNLOAD_EXTENSIONS:
                    if ext in val_lower and len(val_lower) < 300:
                        return True
    return False

def to_absolute_url(href, base_url):
    if not href:
        return ""
    parsed_base = urlparse(base_url)
    if href.startswith('//'):
        return parsed_base.scheme + ':' + href
    elif href.startswith('/'):
        return parsed_base.scheme + '://' + parsed_base.netloc + href
    elif href.startswith('http://') or href.startswith('https://'):
        return href
    else:
        return parsed_base.scheme + '://' + parsed_base.netloc + '/' + href

def analyze_webpage(url, headers=None, timeout=10):
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

        links = []
        seen_links = set()
        all_urls = _extract_all_urls_from_html(response.text, url)
        for link_info in all_urls:
            absolute = link_info["url"]
            if absolute and absolute not in seen_links:
                seen_links.add(absolute)
                links.append(absolute)

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
            'source': response.text,
            'elapsed_time': elapsed_time
        }
    except requests.Timeout:
        progress_dialog.Destroy()
        wx.MessageBox(f"连接超时：{timeout}秒\n请适当增加超时时间后重试",
                     "连接超时")

        return {'error': f'连接超时'}
    except Exception as e:
        return {'error': str(e)}

def get_total_pages(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        page_numbers = set()

        for a in soup.find_all('a', href=True):
            href = a['href']
            parsed_href = urlparse(href)
            qs = parse_qs(parsed_href.query)
            for key in ['page', 'p', 'Page', 'pg', 'offset', 'start']:
                if key in qs:
                    try:
                        num = int(qs[key][0])
                        if num > 0:
                            if key in ('offset', 'start'):
                                page_numbers.add(num // 20 + 1)
                            else:
                                page_numbers.add(num)
                    except (ValueError, IndexError):
                        pass

        for btn in soup.find_all(['button', 'a']):
            for attr in ['data-page', 'data-page-number', 'data-pagenum', 'data-num']:
                val = btn.get(attr)
                if val:
                    try:
                        num = int(val)
                        if num > 0:
                            page_numbers.add(num)
                    except ValueError:
                        pass

        if page_numbers:
            return max(page_numbers)

        return 1
    except Exception:
        return 1

def generate_page_urls(base_url, start_page, end_page):
    parsed = urlparse(base_url)
    qs = parse_qs(parsed.query, keep_blank_values=True)

    page_param = None
    for key in ['page', 'p', 'Page', 'pg']:
        if key in qs:
            page_param = key
            break

    if page_param is None:
        page_param = 'page'

    urls = []
    for page_num in range(start_page, end_page + 1):
        new_qs = dict(qs)
        new_qs[page_param] = [str(page_num)]
        new_query = urlencode(new_qs, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        urls.append(urlunparse(new_parsed))

    return urls

def _check_content_type_downloadable(url, timeout=8):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        parsed = urlparse(url)
        head_url = parsed._replace(query=parsed.query).geturl()
        response = requests.head(head_url, headers=headers, verify=False, timeout=timeout, allow_redirects=True)
        content_type = response.headers.get('Content-Type', '').lower()
        content_disposition = response.headers.get('Content-Disposition', '').lower()
        for ct in DOWNLOAD_CONTENT_TYPES:
            if content_type.startswith(ct):
                return True
        if 'attachment' in content_disposition:
            return True
        if 'octet-stream' in content_type:
            return True
        return False
    except Exception:
        return False

def _extract_urls_from_javascript(script_text, base_url, add_fn):
    if len(script_text) < 10:
        return
    for m in re.finditer(r'''(?:fetch|axios\.(?:get|post|put|delete)|http(?:Client)?)\s*\(\s*['"`]([^'"`]+)['"]''', script_text):
        url_val = m.group(1)
        if url_val.startswith(('http://', 'https://', '//')):
            abs_url = url_val if url_val.startswith('http') else 'https:' + url_val
            add_fn(abs_url)
        elif url_val.startswith('/'):
            add_fn(to_absolute_url(url_val, base_url))
        elif url_val.startswith(('api/', 'v1/', 'v2/', 'v3/', 'download', 'file', 'files', 'raw', 'assets')):
            add_fn(to_absolute_url('/' + url_val, base_url))
    for m in re.finditer(r'''['"`]([^'"`]+?(?:\.jar|\.zip|\.exe|\.msi|\.dmg|\.apk|\.iso|\.bin|\.AppImage|\.deb|\.rpm|\.tar\.gz|\.tgz|\.7z|\.rar|\.mcpack|\.mcworld|\.mcaddon|\.mcjar))[^'"`]*['"]''', script_text):
        url_val = m.group(1)
        if url_val.startswith(('http://', 'https://', '//')):
            abs_url = url_val if url_val.startswith('http') else 'https:' + url_val
            add_fn(abs_url)
        elif url_val.startswith('/'):
            add_fn(to_absolute_url(url_val, base_url))
        else:
            add_fn(to_absolute_url('/' + url_val, base_url))
    for m in re.finditer(r'''(?:const|let|var)\s+(\w+)\s*=\s*['"`]([^'"`]+)['"]\s*;?''', script_text):
        var_name = m.group(1).lower()
        var_val = m.group(2)
        if any(kw in var_name for kw in ['url', 'link', 'href', 'src', 'download', 'file', 'asset', 'mod', 'version', 'release']):
            if var_val.startswith(('http://', 'https://', '//')):
                abs_url = var_val if var_val.startswith('http') else 'https:' + var_val
                add_fn(abs_url)
            elif var_val.startswith('/'):
                add_fn(to_absolute_url(var_val, base_url))
            elif len(var_val) < 300:
                add_fn(to_absolute_url('/' + var_val, base_url))
    for m in re.finditer(r'''import\s+.*?from\s+['"`]([^'"`]+)['"]''', script_text):
        url_val = m.group(1)
        if url_val.startswith(('http://', 'https://')):
            add_fn(url_val)
    for m in re.finditer(r'''require\s*\(\s*['"`]([^'"`]+)['"]\s*\)''', script_text):
        url_val = m.group(1)
        if url_val.startswith(('http://', 'https://')):
            add_fn(url_val)
    for m in re.finditer(r'''(?:api|endpoint|url|link|href|src|download_url|file_url|asset_url)\s*[:=]\s*['"`]([^'"`]+)['"]''', script_text, re.IGNORECASE):
        url_val = m.group(1)
        if url_val.startswith(('http://', 'https://', '//')):
            abs_url = url_val if url_val.startswith('http') else 'https:' + url_val
            add_fn(abs_url)
        elif url_val.startswith('/'):
            add_fn(to_absolute_url(url_val, base_url))
        elif len(url_val) < 300 and '/' in url_val:
            add_fn(to_absolute_url('/' + url_val, base_url))
    for m in re.finditer(r'''(?:https?://[^'"`\s]+)''', script_text):
        url_val = m.group(0)
        decoded = _decode_html_entities(url_val)
        add_fn(decoded)
    for m in re.finditer(r'''`([^`]+?)`''', script_text):
        template = m.group(1)
        urls_in_template = re.findall(r'(https?://[^\s]+|/[^\s"\'<>]+)', template)
        for url_val in urls_in_template:
            if url_val.startswith('http'):
                add_fn(url_val)
            elif url_val.startswith('/'):
                add_fn(to_absolute_url(url_val, base_url))

def _extract_all_urls_from_html(html_text, base_url):
    links = []
    seen = set()

    def add(url_val, text=""):
        if not url_val:
            return
        resolved = url_val
        if url_val.startswith(('//', '/')) or (not url_val.startswith(('http:', 'https:')) and not url_val.startswith('data:')):
            resolved = to_absolute_url(url_val, base_url)
        if resolved and resolved not in seen:
            seen.add(resolved)
            links.append({"url": resolved, "text": text})

    soup = BeautifulSoup(html_text, 'html.parser')

    tag_attr_map = {
        'a': ['href'],
        'area': ['href'],
        'iframe': ['src'],
        'frame': ['src'],
        'embed': ['src'],
        'object': ['data'],
        'audio': ['src'],
        'video': ['src', 'poster'],
        'source': ['src'],
        'track': ['src'],
        'img': ['src', 'data-src'],
        'script': ['src'],
        'link': ['href'],
        'form': ['action'],
        'input': ['src', 'formaction'],
        'button': ['formaction'],
        'meta': ['content'],
    }

    for tag_name, attrs in tag_attr_map.items():
        for tag in soup.find_all(tag_name):
            for attr in attrs:
                val = tag.get(attr)
                if val and isinstance(val, str):
                    if val.startswith(('http', '//', '/')):
                        absolute = to_absolute_url(val, base_url)
                        add(absolute, tag.get_text(strip=True)[:80])

    for tag in soup.find_all(True):
        for attr_name, attr_val in tag.attrs.items():
            if isinstance(attr_val, str) and attr_val.startswith(('http://', 'https://', '//', '/')):
                absolute = to_absolute_url(attr_val, base_url)
                add(absolute)

    for script in soup.find_all('script'):
        script_text = script.string or script.get_text() or ""
        if not script_text:
            continue

        script_id = (script.get('id') or '').lower()
        script_type = (script.get('type') or '').lower()

        is_next_data = 'next_data' in script_id
        is_next_f = 'next_f' in script_id
        is_json = script_type == 'application/json'

        if is_next_data or is_next_f or is_json:
            try:
                data = json.loads(script_text.strip())
                _extract_urls_from_json(data, add)
            except json.JSONDecodeError:
                pass
            for found_url in re.findall(r'https?://[^\s"\'<>\\]+', script_text):
                add(_decode_html_entities(found_url))
            for found_url in re.findall(r'//[^"\'<>\\]+', script_text):
                add('https:' + _decode_html_entities(found_url))
            _extract_urls_from_script_json(script_text, add)
            _extract_urls_from_javascript(script_text, base_url, add)
            continue

        _extract_urls_from_script_json(script_text, add)

        _extract_urls_from_javascript(script_text, base_url, add)

        for found_url in re.findall(r'https?://[^\s"\'<>\\]+', script_text):
            add(_decode_html_entities(found_url))

        for found_url in re.findall(r'//[^"\'<>\\]+', script_text):
            add('https:' + _decode_html_entities(found_url))

    for meta in soup.find_all('meta'):
        refresh = meta.get('content', '')
        if refresh and 'url=' in refresh.lower():
            url_part = re.search(r'url=(.+)', refresh, re.IGNORECASE)
            if url_part:
                absolute = to_absolute_url(url_part.group(1).strip(), base_url)
                add(absolute)

    raw_urls = re.findall(r'https?://[^\s"\'<>\\<]+', html_text)
    for raw_url in raw_urls:
        add(_decode_html_entities(raw_url))

    raw_proto_urls = re.findall(r'//[^\s"\'<>\\<]+', html_text)
    for raw_url in raw_proto_urls:
        add('https:' + _decode_html_entities(raw_url))

    return links

def _decode_html_entities(text):
    entities = {
        '&amp;': '&', '&quot;': '"', '&#39;': "'",
        '&#x27;': "'", '&#x2F;': '/', '&#47;': '/',
        '&lt;': '<', '&gt;': '>', '&#x3C;': '<', '&#x3E;': '>',
    }
    for enc, dec in entities.items():
        text = text.replace(enc, dec)
    return text

def _extract_urls_from_script_json(text, add_fn):
    if len(text) < 30:
        return

    for m in re.finditer(r'(?:window\.|self\.|globalThis\.)?(\w[\w$.]*)\s*=\s*(\{)', text):
        key_name = m.group(1).lower()
        if any(kw in key_name for kw in ('data', 'state', 'props', 'page', 'next', 'initial', 'payload', 'response', 'result', 'list', 'items', 'versions', 'files', 'mod')):
            start = m.start(2)
            depth = 0
            in_string = False
            escape_next = False
            for i in range(start, min(start + 80000, len(text))):
                ch = text[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\':
                    escape_next = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:i+1]
                        try:
                            data = json.loads(candidate)
                            if isinstance(data, (dict, list)):
                                _extract_urls_from_json(data, add_fn)
                        except json.JSONDecodeError:
                            pass
                        break

    for m in re.finditer(r'(?:window\.|self\.|globalThis\.)?(\w[\w$.]*)\s*=\s*(\[)', text):
        key_name = m.group(1).lower()
        if any(kw in key_name for kw in ('data', 'list', 'items', 'versions', 'files', 'results', 'mod')):
            start = m.start(2)
            depth = 0
            in_string = False
            escape_next = False
            for i in range(start, min(start + 80000, len(text))):
                ch = text[i]
                if escape_next:
                    escape_next = False
                    continue
                if ch == '\\':
                    escape_next = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == '[':
                    depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        candidate = text[start:i+1]
                        try:
                            data = json.loads(candidate)
                            if isinstance(data, list):
                                _extract_urls_from_json(data, add_fn)
                        except json.JSONDecodeError:
                            pass
                        break

    for m in re.finditer(r'self\.__next_f\.push\(\s*(\[)', text):
        start = m.start(1)
        depth = 0
        in_string = False
        escape_next = False
        for i in range(start, min(start + 100000, len(text))):
            ch = text[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i+1]
                    try:
                        data = json.loads(candidate)
                        if isinstance(data, list):
                            _extract_urls_from_json(data, add_fn)
                    except json.JSONDecodeError:
                        pass
                    break

def _extract_urls_from_json(data, add_fn, depth=0):
    if depth > 15:
        return
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, str):
                if val.startswith(('http://', 'https://', '//')):
                    add_fn(val, key)
                elif val.startswith('/') and len(val) < 200:
                    add_fn(val, key)
                elif len(val) < 500 and '/' in val and any(ext in val.lower() for ext in DOWNLOAD_EXTENSIONS):
                    add_fn(val, key)
                elif len(val) < 500 and any(ext in val.lower() for ext in DOWNLOAD_EXTENSIONS):
                    add_fn(val, key)
                else:
                    val_lower = val.lower()
                    if len(val) < 500 and any(kw in val_lower for kw in DOWNLOAD_URL_KEYWORDS):
                        has_ext = any(ext in val_lower for ext in DOWNLOAD_EXTENSIONS)
                        if has_ext or len(val) < 200:
                            add_fn(val, key)
            elif isinstance(val, (dict, list)):
                _extract_urls_from_json(val, add_fn, depth + 1)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                _extract_urls_from_json(item, add_fn, depth + 1)
            elif isinstance(item, str):
                if item.startswith(('http://', 'https://', '//')):
                    add_fn(item)
                elif len(item) < 500 and '/' in item and any(ext in item.lower() for ext in DOWNLOAD_EXTENSIONS):
                    add_fn(item)
                elif len(item) < 500 and any(ext in item.lower() for ext in DOWNLOAD_EXTENSIONS):
                    add_fn(item)
                else:
                    item_lower = item.lower()
                    if len(item) < 500 and any(kw in item_lower for kw in DOWNLOAD_URL_KEYWORDS):
                        has_ext = any(ext in item_lower for ext in DOWNLOAD_EXTENSIONS)
                        if has_ext or len(item) < 200:
                            add_fn(item)

def crawl_page_for_download_links(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        response = requests.get(url, headers=headers, verify=False, timeout=15)
        response.encoding = 'utf-8'

        download_links = []
        seen = set()

        def add_download(absolute, text=""):
            if absolute and absolute not in seen:
                seen.add(absolute)
                download_links.append({
                    "url": absolute,
                    "filename": get_filename_from_url(absolute),
                    "text": text
                })

        all_links = _extract_all_urls_from_html(response.text, url)
        for link in all_links:
            absolute = link["url"]
            if is_download_link(absolute):
                add_download(absolute, link.get("text", ""))

        meaningful_downloads = [dl for dl in download_links if is_real_download_file(dl["url"])]
        fast_downloads = [dl for dl in download_links if is_fast_download_link(dl["url"])]

        html_text = response.text

        has_spa = any([
            'id="__next"' in html_text,
            'self.__next_f.push' in html_text,
            '__NEXT_DATA__' in html_text,
            '__NUXT__' in html_text,
            '__NUXT_DATA__' in html_text,
            'window.__NUXT__' in html_text,
            len(html_text) < 10000 and 'id="app"' in html_text,
            'data-reactroot' in html_text,
            'id="root"' in html_text and len(html_text) < 15000,
            'ng-version' in html_text,
        ])

        if has_spa:
            _crawl_nuxt_api(url, headers, download_links, seen, html_text)

            if not any(is_fast_download_link(dl["url"]) for dl in download_links):
                _crawl_spa_api_direct(url, headers, download_links, seen)

        meaningful_downloads = [dl for dl in download_links if is_real_download_file(dl["url"])]
        fast_downloads = [dl for dl in download_links if is_fast_download_link(dl["url"])]

        if fast_downloads and has_spa:
            return download_links

        if not meaningful_downloads and has_spa:
            _crawl_spa_with_selenium(url, headers, download_links, seen)

        if not meaningful_downloads and has_spa:
            _crawl_spa_with_playwright(url, headers, download_links, seen)

        if fast_downloads:
            return download_links

        if meaningful_downloads and not has_spa:
            return download_links

        if not meaningful_downloads:
            soup = BeautifulSoup(html_text, 'html.parser')
            for form in soup.find_all('form', action=True):
                action = form['action']
                method = (form.get('method') or 'get').upper()
                inputs = {}
                for inp in form.find_all(['input', 'select', 'textarea']):
                    name = inp.get('name')
                    if name:
                        inputs[name] = inp.get('value', '')
                absolute = to_absolute_url(action, url)
                try:
                    if method == 'GET':
                        resp2 = requests.get(absolute, params=inputs, headers=headers, verify=False, timeout=10)
                    else:
                        resp2 = requests.post(absolute, data=inputs, headers=headers, verify=False, timeout=10)
                    extracted2 = _extract_all_urls_from_html(resp2.text, url)
                    for link in extracted2:
                        absolute2 = link["url"]
                        if is_download_link(absolute2):
                            add_download(absolute2, link.get("text", ""))
                except Exception:
                    pass

        if not meaningful_downloads:
            all_candidates = list(seen)
            for link in all_candidates:
                if not is_download_link(link):
                    if _check_content_type_downloadable(link):
                        add_download(link, "")

        if not meaningful_downloads:
            _discover_and_crawl_api_endpoints(url, headers, download_links, seen)

        meaningful_downloads = [dl for dl in download_links if is_real_download_file(dl["url"])]
        return download_links
    except Exception as e:
        print(f"爬取页面失败 {url}: {e}")
        return []

def _crawl_nuxt_api(url, headers, download_links, seen, html=None):
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        if html is None:
            resp = requests.get(url, headers=headers, verify=False, timeout=15)
            if resp.status_code != 200:
                return
            html = resp.text

        if '__NUXT_DATA__' not in html and '__NUXT__' not in html:
            return

        api_base = None
        for m in re.finditer(r'apiBaseUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']', html):
            api_base = m.group(1)
            break

        if not api_base:
            m = re.search(r'apiBaseUrl[^}]+', html)
            if m:
                for m2 in re.finditer(r'["\']([^"\']+)["\']', m.group(0)):
                    val = m2.group(1)
                    if 'api' in val.lower():
                        api_base = val
                        break

        if not api_base:
            api_base = base.rstrip('/') + '/api/'

        path_parts = [p for p in parsed.path.split('/') if p]
        category_patterns = ['mod', 'project', 'plugin', 'modpack', 'resource', 'addon', 'extension', 'theme', 'map', 'mod/versions', 'modpack/versions']
        slug = None
        for i, part in enumerate(path_parts):
            if part.lower() in category_patterns and i + 1 < len(path_parts):
                slug = path_parts[i + 1]
                break

        if not slug and len(path_parts) >= 1:
            for i, part in enumerate(path_parts):
                if part.lower() not in ('versions', 'version', 'download', 'downloads', 'files', 'file') and i + 1 < len(path_parts):
                    slug = part
                    break
            if not slug:
                slug = path_parts[0]

        if not slug:
            return

        api_base_clean = api_base.rstrip('/') + '/'
        api_patterns = [
            f"{api_base_clean}project/{slug}/version",
            f"{api_base_clean}mod/{slug}/version",
            f"{api_base_clean}projects/{slug}/versions",
            f"{api_base_clean}mods/{slug}/versions",
            f"{api_base_clean}{slug}/version",
            f"{api_base_clean}{slug}/versions",
            f"{api_base_clean}versions?slug={slug}",
            f"{api_base_clean}search?query={slug}",
        ]

        for api_url in api_patterns:
            try:
                api_headers = {**headers, 'Accept': 'application/json'}
                resp2 = requests.get(api_url, headers=api_headers, verify=False, timeout=10)
                if resp2.status_code != 200:
                    continue

                data = resp2.json()

                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            files = item.get('files', [])
                            if isinstance(files, list):
                                for f in files:
                                    if isinstance(f, dict) and 'url' in f:
                                        dl_url = f['url']
                                        if dl_url and dl_url not in seen:
                                            seen.add(dl_url)
                                            fn = f.get('filename', get_filename_from_url(dl_url))
                                            download_links.append({
                                                "url": dl_url,
                                                "filename": fn,
                                                "text": item.get('name', '')
                                            })

                _extract_downloads_from_api_response(data, api_url, base, download_links, seen)

                if any(is_fast_download_link(dl["url"]) for dl in download_links):
                    return

            except Exception:
                pass

        try:
            search_url = f"{api_base_clean}search?query={slug}&limit=3"
            sr = requests.get(search_url, headers={**headers, 'Accept': 'application/json'}, verify=False, timeout=10)
            if sr.status_code == 200:
                sdata = sr.json()
                if isinstance(sdata, dict) and 'hits' in sdata:
                    for hit in sdata['hits']:
                        if isinstance(hit, dict):
                            proj_id = hit.get('project_id', hit.get('id', ''))
                            if proj_id:
                                try:
                                    ver_url = f"{api_base_clean}project/{proj_id}/version"
                                    vr = requests.get(ver_url, headers={**headers, 'Accept': 'application/json'}, verify=False, timeout=10)
                                    if vr.status_code == 200:
                                        vdata = vr.json()
                                        if isinstance(vdata, list):
                                            for item in vdata:
                                                if isinstance(item, dict):
                                                    files = item.get('files', [])
                                                    if isinstance(files, list):
                                                        for f in files:
                                                            if isinstance(f, dict) and 'url' in f:
                                                                dl_url = f['url']
                                                                if dl_url and dl_url not in seen:
                                                                    seen.add(dl_url)
                                                                    fn = f.get('filename', get_filename_from_url(dl_url))
                                                                    download_links.append({
                                                                        "url": dl_url,
                                                                        "filename": fn,
                                                                        "text": item.get('name', '')
                                                                    })
                                except Exception:
                                    pass
        except Exception:
            pass

    except Exception:
        pass

def _crawl_spa_with_selenium(url, headers, download_links, seen):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.__nodanium_urls = [];
                const origFetch = window.fetch;
                window.fetch = function() {
                    try { window.__nodanium_urls.push(arguments[0]); } catch(e) {}
                    return origFetch.apply(this, arguments);
                };
                const origXHROpen = XMLHttpRequest.prototype.open;
                XMLHttpRequest.prototype.open = function() {
                    try { window.__nodanium_urls.push(arguments[1]); } catch(e) {}
                    return origXHROpen.apply(this, arguments);
                };
                const origXHRSend = XMLHttpRequest.prototype.send;
                XMLHttpRequest.prototype.send = function() {
                    try { if(this.responseURL) window.__nodanium_urls.push(this.responseURL); } catch(e) {}
                    return origXHRSend.apply(this, arguments);
                };
            '''
        })

        driver.get(url)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        time.sleep(5)

        driver.execute_script('''
            var links = document.querySelectorAll('a[href]');
            var results = [];
            for (var i = 0; i < links.length; i++) {
                results.push(links[i].href);
            }
            window.__nodanium_urls = window.__nodanium_urls.concat(results);
            return results;
        ''')

        try:
            dynamic_urls = driver.execute_script('return window.__nodanium_urls || [];')
            if dynamic_urls:
                for du in dynamic_urls:
                    if du and isinstance(du, str):
                        if du.startswith(('http://', 'https://')):
                            if is_download_link(du) and du not in seen:
                                seen.add(du)
                                download_links.append({
                                    "url": du,
                                    "filename": get_filename_from_url(du),
                                    "text": "SPA动态链接"
                                })
        except Exception:
            pass

        page_source = driver.page_source
        extracted_spa = _extract_all_urls_from_html(page_source, url)
        for link in extracted_spa:
            absolute2 = link["url"]
            if is_download_link(absolute2) and absolute2 not in seen:
                seen.add(absolute2)
                download_links.append({
                    "url": absolute2,
                    "filename": get_filename_from_url(absolute2),
                    "text": link.get("text", "")
                })

        try:
            logs = driver.get_log('performance')
            for log in logs:
                try:
                    msg = json.loads(log['message'])['message']
                    if msg['method'] == 'Network.requestWillBeSent':
                        req = msg['params']['request']
                        req_url = req.get('url', '')
                        if req_url and is_download_link(req_url) and req_url not in seen:
                            seen.add(req_url)
                            download_links.append({
                                "url": req_url,
                                "filename": get_filename_from_url(req_url),
                                "text": "SPA网络请求"
                            })
                except Exception:
                    pass
        except Exception:
            pass

        try:
            driver.quit()
        except Exception:
            pass
    except ImportError:
        print("Selenium未安装，跳过SPA渲染")
    except Exception as e:
        print(f"Selenium渲染失败: {e}")
        try:
            driver.quit()
        except Exception:
            pass

def _crawl_spa_with_playwright(url, headers, download_links, seen):
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            captured_urls = []

            def on_request(request):
                req_url = request.url
                if req_url and is_download_link(req_url) and req_url not in seen:
                    captured_urls.append(req_url)

            page.on("request", on_request)
            page.on("response", lambda response: on_request(response.request))

            page.goto(url, wait_until='networkidle', timeout=45000)
            time.sleep(2)

            page_source = page.content()
            extracted = _extract_all_urls_from_html(page_source, url)
            for link in extracted:
                absolute2 = link["url"]
                if is_download_link(absolute2) and absolute2 not in seen:
                    seen.add(absolute2)
                    download_links.append({
                        "url": absolute2,
                        "filename": get_filename_from_url(absolute2),
                        "text": link.get("text", "")
                    })

            for cu in captured_urls:
                if cu not in seen:
                    seen.add(cu)
                    download_links.append({
                        "url": cu,
                        "filename": get_filename_from_url(cu),
                        "text": "Playwright捕获"
                    })

            browser.close()
    except ImportError:
        print("Playwright未安装，跳过")
    except Exception as e:
        print(f"Playwright渲染失败: {e}")

def _discover_and_crawl_api_endpoints(url, headers, download_links, seen):
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        api_paths = [
            '/api', '/api/v1', '/api/v2', '/api/v3',
            '/graphql', '/api/downloads', '/api/files',
            '/api/releases', '/api/versions', '/api/assets',
        ]

        for api_path in api_paths:
            try:
                api_url = base + api_path
                resp = requests.get(api_url, headers=headers, verify=False, timeout=10)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                        api_links = []
                        _extract_urls_from_json(data, lambda u, k="": api_links.append({"url": u, "key": k}))
                        for link_info in api_links:
                            absolute = link_info["url"]
                            if is_download_link(absolute) and absolute not in seen:
                                seen.add(absolute)
                                download_links.append({
                                    "url": absolute,
                                    "filename": get_filename_from_url(absolute),
                                    "text": f"API发现({api_path})"
                                })
                            elif absolute.startswith('/'):
                                full_url = to_absolute_url(absolute, base)
                                if is_download_link(full_url) and full_url not in seen:
                                    seen.add(full_url)
                                    download_links.append({
                                        "url": full_url,
                                        "filename": get_filename_from_url(full_url),
                                        "text": f"API发现({api_path})"
                                    })
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass
    except Exception:
        pass

def _crawl_spa_api_direct(url, headers, download_links, seen):
    try:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        api_urls = _discover_api_endpoints_from_page(url, headers, base)

        for api_url in api_urls:
            try:
                resp = requests.get(api_url, headers=headers, verify=False, timeout=15)
                if resp.status_code != 200:
                    continue
                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    continue

                _extract_downloads_from_api_response(data, api_url, base, download_links, seen)

                if any(is_fast_download_link(dl["url"]) for dl in download_links):
                    return

            except Exception:
                pass
    except Exception:
        pass

def _discover_api_endpoints_from_page(url, headers, base):
    discovered = []
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=15)
        if resp.status_code != 200:
            return discovered
        html = resp.text

        for m in re.finditer(r'''(?:fetch|axios\.(?:get|post)|http(?:Client)?)\s*\(\s*['"`]([^'"`]+)['"]''', html):
            api_path = m.group(1)
            if api_path.startswith('/'):
                candidate = base + api_path
            elif api_path.startswith('http'):
                candidate = api_path
            else:
                continue
            if any(kw in candidate.lower() for kw in ('api', 'version', 'download', 'file', 'asset', 'mod', 'release')):
                discovered.append(candidate)

        for m in re.finditer(r'''["'](\/api\/[^"']+)["']''', html):
            discovered.append(base + m.group(1))

        for m in re.finditer(r'''["'](\/v[0-9]+\/[^"']+)["']''', html):
            path = m.group(1)
            if any(kw in path.lower() for kw in ('version', 'download', 'file', 'asset', 'mod', 'release', 'list', 'item')):
                discovered.append(base + path)

        for m in re.finditer(r'''["']([^"']*(?:version|download|file|asset|mod|release)[^"']*)["']''', html, re.IGNORECASE):
            path = m.group(1)
            if path.startswith('/') and len(path) < 200:
                discovered.append(base + path)

        soup = BeautifulSoup(html, 'html.parser')
        for script in soup.find_all('script'):
            script_text = script.string or script.get_text() or ""
            for m in re.finditer(r'''["'](\/[^"']*(?:api|version|download|file|asset|mod|release)[^"']*)["']''', script_text, re.IGNORECASE):
                path = m.group(1)
                if len(path) < 200:
                    discovered.append(base + path)

    except Exception:
        pass

    valid_urls = []
    seen_urls = set()
    for u in discovered:
        if u not in seen_urls:
            seen_urls.add(u)
            valid_urls.append(u)

    return valid_urls[:30]

def _extract_downloads_from_api_response(data, api_url, base, download_links, seen):
    try:
        if isinstance(data, dict):
            for key in ('hits', 'versions', 'results', 'items', 'data', 'list', 'docs', 'assets', 'files', 'downloads'):
                if key in data and isinstance(data[key], list):
                    _extract_downloads_from_list(data[key], base, download_links, seen)
                    return

            for key, val in data.items():
                if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                    if any(k in val[0] for k in ('url', 'download_url', 'files', 'name', 'filename')):
                        _extract_downloads_from_list(val, base, download_links, seen)
                        return

            _extract_downloads_from_json_deep(data, base, download_links, seen)

        elif isinstance(data, list):
            _extract_downloads_from_list(data, base, download_links, seen)
    except Exception:
        pass

def _extract_downloads_from_list(items, base, download_links, seen):
    for item in items:
        if not isinstance(item, dict):
            continue

        for key in ('download_url', 'downloadUrl', 'file_url', 'fileUrl', 'href', 'link', 'url'):
            if key in item and isinstance(item[key], str):
                dl_url = item[key]
                if dl_url.startswith('//'):
                    dl_url = 'https:' + dl_url
                elif dl_url.startswith('/'):
                    dl_url = base + dl_url
                if dl_url.startswith(('http://', 'https://')) and dl_url not in seen:
                    seen.add(dl_url)
                    fn = item.get('filename', item.get('name', item.get('fileName', get_filename_from_url(dl_url))))
                    download_links.append({
                        "url": dl_url,
                        "filename": fn,
                        "text": "API爬取"
                    })

        files = item.get('files', item.get('downloads', item.get('assets', item.get('attachments', item.get('versions', [])))))
        if isinstance(files, list):
            for f in files:
                if isinstance(f, dict):
                    for key in ('url', 'download_url', 'href', 'file_url', 'link'):
                        if key in f and isinstance(f[key], str):
                            dl_url = f[key]
                            if dl_url.startswith('//'):
                                dl_url = 'https:' + dl_url
                            elif dl_url.startswith('/'):
                                dl_url = base + dl_url
                            if dl_url.startswith(('http://', 'https://')) and dl_url not in seen:
                                seen.add(dl_url)
                                fn = f.get('filename', f.get('name', f.get('fileName', get_filename_from_url(dl_url))))
                                download_links.append({
                                    "url": dl_url,
                                    "filename": fn,
                                    "text": "API爬取"
                                })
                            break
                elif isinstance(f, str) and is_download_link(f):
                    if f not in seen:
                        seen.add(f)
                        download_links.append({
                            "url": f,
                            "filename": get_filename_from_url(f),
                            "text": "API爬取"
                        })

        dl_map = item.get('downloads', {})
        if isinstance(dl_map, dict):
            for dl_key, dl_val in dl_map.items():
                if isinstance(dl_val, str):
                    if dl_val.startswith('//'):
                        dl_val = 'https:' + dl_val
                    elif dl_val.startswith('/'):
                        dl_val = base + dl_val
                    if dl_val.startswith(('http://', 'https://')) and is_download_link(dl_val) and dl_val not in seen:
                        seen.add(dl_val)
                        download_links.append({
                            "url": dl_val,
                            "filename": get_filename_from_url(dl_val),
                            "text": "API爬取"
                        })

def _extract_downloads_from_json_deep(data, base, download_links, seen, depth=0):
    if depth > 10:
        return
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, str):
                if val.startswith(('http://', 'https://')) and is_download_link(val) and val not in seen:
                    seen.add(val)
                    download_links.append({
                        "url": val,
                        "filename": get_filename_from_url(val),
                        "text": "API爬取"
                    })
                elif val.startswith('/') and is_download_link(base + val) and (base + val) not in seen:
                    seen.add(base + val)
                    download_links.append({
                        "url": base + val,
                        "filename": get_filename_from_url(val),
                        "text": "API爬取"
                    })
            elif isinstance(val, (dict, list)):
                _extract_downloads_from_json_deep(val, base, download_links, seen, depth + 1)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                _extract_downloads_from_json_deep(item, base, download_links, seen, depth + 1)
            elif isinstance(item, str):
                if item.startswith(('http://', 'https://')) and is_download_link(item) and item not in seen:
                    seen.add(item)
                    download_links.append({
                        "url": item,
                        "filename": get_filename_from_url(item),
                        "text": "API爬取"
                    })

def on_analyze_button(url_l, headers=None, timeout=5, code=True):
    global progress_dialog
    print(url_l)
    print(code)

    result = analyze_webpage(url_l, headers=headers, timeout=timeout)

    if 'error' in result:
        wx.MessageBox(f"分析失败: {result['error']}", "错误", wx.OK | wx.ICON_ERROR)
        return

    result_window = wx.Frame(None, title="网页分析结果", size=(800, 600))
    notebook = wx.Notebook(result_window)

    info_panel = wx.Panel(notebook)
    links_panel = wx.Panel(notebook)
    images_panel = wx.Panel(notebook)
    text_panel = wx.Panel(notebook)
    if code:
        source_panel = wx.Panel(notebook)

    def create_scrollable_text(panel):
        sizer = wx.BoxSizer(wx.VERTICAL)
        text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(text, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(sizer)
        return text

    info_text = create_scrollable_text(info_panel)
    info_text.SetValue(f"网页标题: {result['title']}\n\n"
                      f"链接数量: {len(result['links'])}\n"
                      f"图片数量: {len(result['images'])}\n"
                      f"分析用时: {result['elapsed_time']:.2f}秒\n"
                      f"请求头User-Agent：{headers}")

    # ==================== 链接面板（列表样式 + 批量下载） ====================
    links_panel_sizer = wx.BoxSizer(wx.VERTICAL)

    page_ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)
    page_label = wx.StaticText(links_panel, label="页数模式:")
    page_ctrl_sizer.Add(page_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    page_mode_combo = wx.ComboBox(links_panel, choices=["自动检测", "手动指定"], style=wx.CB_READONLY)
    page_mode_combo.SetSelection(0)
    page_ctrl_sizer.Add(page_mode_combo, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    from_label = wx.StaticText(links_panel, label="从:")
    page_ctrl_sizer.Add(from_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    from_spin = wx.SpinCtrl(links_panel, min=1, max=9999, initial=1, size=(80, -1))
    page_ctrl_sizer.Add(from_spin, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    to_label = wx.StaticText(links_panel, label="到:")
    page_ctrl_sizer.Add(to_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    to_spin = wx.SpinCtrl(links_panel, min=1, max=9999, initial=1, size=(80, -1))
    page_ctrl_sizer.Add(to_spin, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    detect_btn = wx.Button(links_panel, label="检测页数")
    page_ctrl_sizer.Add(detect_btn, 0, wx.ALL, 5)
    crawl_btn = wx.Button(links_panel, label="爬取下载链接")
    page_ctrl_sizer.Add(crawl_btn, 0, wx.ALL, 5)
    links_panel_sizer.Add(page_ctrl_sizer, 0, wx.EXPAND | wx.ALL, 5)

    filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
    filter_label = wx.StaticText(links_panel, label="筛选扩展名:")
    filter_sizer.Add(filter_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
    filter_text = wx.TextCtrl(links_panel, value=get_filter_extensions_text(), style=wx.TE_PROCESS_ENTER)
    filter_sizer.Add(filter_text, 1, wx.ALL | wx.EXPAND, 5)
    apply_filter_btn = wx.Button(links_panel, label="应用筛选")
    filter_sizer.Add(apply_filter_btn, 0, wx.ALL, 5)
    reset_filter_btn = wx.Button(links_panel, label="重置默认")
    filter_sizer.Add(reset_filter_btn, 0, wx.ALL, 5)
    links_panel_sizer.Add(filter_sizer, 0, wx.EXPAND | wx.ALL, 5)

    link_list_ctrl = wx.ListCtrl(links_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
    link_list_ctrl.InsertColumn(0, "选择", width=50)
    link_list_ctrl.InsertColumn(1, "文件名", width=200)
    link_list_ctrl.InsertColumn(2, "URL", width=450)
    link_list_ctrl.InsertColumn(3, "页面", width=60)
    links_panel_sizer.Add(link_list_ctrl, 1, wx.ALL | wx.EXPAND, 5)

    list_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    batch_download_btn = wx.Button(links_panel, label="一键批量下载")
    list_btn_sizer.Add(batch_download_btn, 0, wx.ALL, 5)
    select_all_btn = wx.Button(links_panel, label="全选")
    list_btn_sizer.Add(select_all_btn, 0, wx.ALL, 5)
    deselect_all_btn = wx.Button(links_panel, label="取消全选")
    list_btn_sizer.Add(deselect_all_btn, 0, wx.ALL, 5)
    clear_list_btn = wx.Button(links_panel, label="清空列表")
    list_btn_sizer.Add(clear_list_btn, 0, wx.ALL, 5)
    links_panel_sizer.Add(list_btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

    links_panel.SetSizer(links_panel_sizer)

    link_items = []
    page_counter = [1]

    def add_link_item(url, page_num=1):
        idx = link_list_ctrl.GetItemCount()
        filename = get_filename_from_url(url)
        item = link_list_ctrl.InsertItem(idx, "✓")
        link_list_ctrl.SetItem(item, 1, filename)
        link_list_ctrl.SetItem(item, 2, url)
        link_list_ctrl.SetItem(item, 3, str(page_num))
        link_items.append({
            "url": url,
            "filename": filename,
            "selected": True,
            "page": page_num
        })

    def populate_from_result_links():
        existing = {item["url"] for item in link_items}
        count = 0
        for link_url in result.get('links', []):
            if link_url not in existing and matches_filter(link_url):
                add_link_item(link_url, 1)
                count += 1
                existing.add(link_url)
        wx.CallAfter(lambda: result_window.SetStatusText(f"已从初始页面添加 {count} 个下载链接，正在自动爬取..."))

        def do_auto_crawl():
            found = crawl_page_for_download_links(url_l)
            new_count = 0
            for link in found:
                if link["url"] not in existing and matches_filter(link["url"]):
                    wx.CallAfter(lambda u=link["url"]: add_link_item(u, 1))
                    existing.add(link["url"])
                    new_count += 1
            wx.CallAfter(lambda: result_window.SetStatusText(f"自动爬取完成，共找到 {new_count} 个下载链接"))

        threading.Thread(target=do_auto_crawl, daemon=True).start()

    def on_list_activated(event):
        item = event.GetItem()
        if item >= 0 and item < len(link_items):
            current_val = link_list_ctrl.GetItemText(item, 0)
            new_val = " " if current_val == "✓" else "✓"
            link_list_ctrl.SetItem(item, 0, new_val)
            link_items[item]["selected"] = (new_val == "✓")

    def on_select_all(event):
        for i in range(link_list_ctrl.GetItemCount()):
            link_list_ctrl.SetItem(i, 0, "✓")
            if i < len(link_items):
                link_items[i]["selected"] = True

    def on_deselect_all(event):
        for i in range(link_list_ctrl.GetItemCount()):
            link_list_ctrl.SetItem(i, 0, " ")
            if i < len(link_items):
                link_items[i]["selected"] = False

    def on_clear_list(event):
        link_list_ctrl.DeleteAllItems()
        link_items.clear()
        page_counter[0] = 1

    def on_apply_filter(event):
        new_exts = set_filter_extensions(filter_text.GetValue())
        filter_text.SetValue(get_filter_extensions_text())
        removed = 0
        kept = []
        for i in range(link_list_ctrl.GetItemCount()):
            url = link_list_ctrl.GetItemText(i, 2)
            page = link_list_ctrl.GetItemText(i, 3)
            if matches_filter(url):
                kept.append((url, page))
            else:
                removed += 1
        link_list_ctrl.DeleteAllItems()
        link_items.clear()
        for url, page in kept:
            add_link_item(url, int(page) if page.isdigit() else 1)
        total = len(active_filter_extensions)
        wx.MessageBox(f"筛选规则已更新（共 {total} 个扩展名），已移除 {removed} 个不匹配链接",
                      "筛选已应用", wx.OK | wx.ICON_INFORMATION)
        result_window.SetStatusText(f"当前筛选: {get_filter_extensions_text()}")

    def on_reset_filter(event):
        global active_filter_extensions
        active_filter_extensions = list(FAST_DOWNLOAD_EXTENSIONS)
        filter_text.SetValue(get_filter_extensions_text())
        kept = []
        for i in range(link_list_ctrl.GetItemCount()):
            url = link_list_ctrl.GetItemText(i, 2)
            page = link_list_ctrl.GetItemText(i, 3)
            if matches_filter(url):
                kept.append((url, page))
        link_list_ctrl.DeleteAllItems()
        link_items.clear()
        for url, page in kept:
            add_link_item(url, int(page) if page.isdigit() else 1)
        result_window.SetStatusText(f"已重置为默认筛选: {get_filter_extensions_text()}")

    def on_detect_page(event):
        detect_btn.Enable(False)
        wx.CallAfter(result_window.SetStatusText, "正在检测页数...")

        def do_detect():
            total = get_total_pages(url_l)
            wx.CallAfter(lambda: to_spin.SetValue(total))
            wx.CallAfter(lambda: from_spin.SetValue(1))
            wx.CallAfter(lambda: result_window.SetStatusText(f"检测到共 {total} 页"))
            wx.CallAfter(lambda: wx.MessageBox(f"检测到共 {total} 页", "检测完成", wx.OK | wx.ICON_INFORMATION))
            wx.CallAfter(lambda: detect_btn.Enable(True))

        threading.Thread(target=do_detect, daemon=True).start()

    def on_crawl(event):
        page_mode = page_mode_combo.GetSelection()
        start_page = from_spin.GetValue()
        end_page = to_spin.GetValue()

        if page_mode == 0:
            total = get_total_pages(url_l)
            end_page = total
            wx.CallAfter(lambda: to_spin.SetValue(total))

        if start_page > end_page:
            start_page, end_page = end_page, start_page

        crawl_btn.Enable(False)
        wx.CallAfter(result_window.SetStatusText, f"正在爬取第 {start_page}-{end_page} 页...")

        page_urls = generate_page_urls(url_l, start_page, end_page)
        progress = wx.ProgressDialog("爬取下载链接",
                                     f"正在分析第 {start_page}-{end_page} 页...",
                                     maximum=len(page_urls),
                                     style=wx.PD_AUTO_HIDE | wx.PD_APP_MODAL)

        total_found = [0]
        new_count = [0]

        def do_crawl():
            existing_urls = {item["url"] for item in link_items}
            for i, page_url in enumerate(page_urls):
                found = crawl_page_for_download_links(page_url)
                page_num = start_page + i
                for link in found:
                    if link["url"] not in existing_urls and matches_filter(link["url"]):
                        wx.CallAfter(lambda u=link["url"], p=page_num: add_link_item(u, p))
                        existing_urls.add(link["url"])
                        total_found[0] += 1
                        new_count[0] += 1
                wx.CallAfter(lambda idx=i: progress.Update(idx + 1, f"正在爬取第 {start_page + idx}/{end_page} 页..."))

            wx.CallAfter(lambda: progress.Update(len(page_urls), f"完成，共发现 {total_found[0]} 个下载链接"))
            wx.CallAfter(lambda: result_window.SetStatusText(f"爬取完成，新增 {new_count[0]} 个下载链接"))
            wx.CallAfter(lambda: crawl_btn.Enable(True))
            wx.CallAfter(lambda: wx.MessageBox(f"爬取完成，共发现 {total_found[0]} 个下载链接", "爬取完成", wx.OK | wx.ICON_INFORMATION))
            wx.CallAfter(lambda: progress.Destroy)

        threading.Thread(target=do_crawl, daemon=True).start()

    def on_batch_download(event):
        selected = [item for item in link_items if item.get("selected", True)]
        if not selected:
            wx.MessageBox("没有选中的链接，请先在列表中勾选要下载的链接", "错误", wx.OK | wx.ICON_ERROR)
            return

        urls = [item["url"] for item in selected]
        download_items_data = [{"url": item["url"], "filename": item["filename"]} for item in selected]

        folder_name = f"批量下载_{time.strftime('%Y%m%d_%H%M%S')}"

        sys_type = platform.system()
        if sys_type == "Windows":
            download_dir = os.path.join(os.environ.get('USERPROFILE', os.path.expanduser("~")), 'Downloads')
        else:
            download_dir = os.path.join(os.path.expanduser("~"), 'Downloads')

        dlg = wx.Dialog(result_window, title="批量下载设置", size=(400, 250))
        dlg_panel = wx.Panel(dlg)
        dlg_sizer = wx.BoxSizer(wx.VERTICAL)

        folder_sizer = wx.BoxSizer(wx.HORIZONTAL)
        folder_label = wx.StaticText(dlg_panel, label="文件夹名称:")
        folder_text = wx.TextCtrl(dlg_panel, value=folder_name)
        folder_sizer.Add(folder_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        folder_sizer.Add(folder_text, 1, wx.ALL, 5)
        dlg_sizer.Add(folder_sizer, 0, wx.EXPAND | wx.ALL, 5)

        thread_sizer = wx.BoxSizer(wx.HORIZONTAL)
        thread_label = wx.StaticText(dlg_panel, label="线程数:")
        thread_spin = wx.SpinCtrl(dlg_panel, min=1, max=10, initial=4)
        thread_sizer.Add(thread_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        thread_sizer.Add(thread_spin, 0, wx.ALL, 5)
        dlg_sizer.Add(thread_sizer, 0, wx.EXPAND | wx.ALL, 5)

        chunk_sizer = wx.BoxSizer(wx.HORIZONTAL)
        chunk_label = wx.StaticText(dlg_panel, label="分块大小:")
        chunk_text = wx.TextCtrl(dlg_panel, value="1", size=(80, -1))
        chunk_combo = wx.ComboBox(dlg_panel, choices=["B", "KB", "MB", "GB"], style=wx.CB_READONLY, value="MB")
        chunk_sizer.Add(chunk_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        chunk_sizer.Add(chunk_text, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        chunk_sizer.Add(chunk_combo, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        dlg_sizer.Add(chunk_sizer, 0, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        ok_btn = wx.Button(dlg_panel, wx.ID_OK, label="开始下载")
        cancel_btn = wx.Button(dlg_panel, wx.ID_CANCEL, label="取消")
        btn_sizer.AddStretchSpacer(1)
        btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
        btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
        dlg_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)

        dlg_panel.SetSizer(dlg_sizer)

        if dlg.ShowModal() == wx.ID_OK:
            fn = folder_text.GetValue().strip()
            tc = thread_spin.GetValue()
            try:
                cv = float(chunk_text.GetValue().strip())
            except ValueError:
                cv = 1.0
            cu = chunk_combo.GetValue()
            multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
            chunk_bytes = max(int(cv * multipliers.get(cu, 1024**2)), 1)

            if not fn:
                fn = folder_name

            dlg.Destroy()

            try:
                import DatchDownload
                parent_window = result_window
                parent_window.download_items = download_items_data
                DatchDownload.create_download_window(
                    parent_window,
                    urls,
                    tc,
                    "",
                    download_dir,
                    fn,
                    chunk_size=chunk_bytes
                )
            except Exception as e:
                wx.MessageBox(f"启动批量下载失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
        else:
            dlg.Destroy()

    link_list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, on_list_activated)
    select_all_btn.Bind(wx.EVT_BUTTON, on_select_all)
    deselect_all_btn.Bind(wx.EVT_BUTTON, on_deselect_all)
    clear_list_btn.Bind(wx.EVT_BUTTON, on_clear_list)
    detect_btn.Bind(wx.EVT_BUTTON, on_detect_page)
    crawl_btn.Bind(wx.EVT_BUTTON, on_crawl)
    batch_download_btn.Bind(wx.EVT_BUTTON, on_batch_download)
    apply_filter_btn.Bind(wx.EVT_BUTTON, on_apply_filter)
    reset_filter_btn.Bind(wx.EVT_BUTTON, on_reset_filter)
    filter_text.Bind(wx.EVT_TEXT_ENTER, on_apply_filter)

    populate_from_result_links()

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

    result_window.CreateStatusBar()
    result_window.SetStatusText("就绪")

    result_window.Show()
    progress_dialog.Destroy()