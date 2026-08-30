# Copyright (c) 2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT

import os
import re
import json
import uuid
import platform
from datetime import datetime

CONFIG_NAME = "site_headers.json"
LOG_NAME = "site_headers.log"

DEFAULT_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36")


def get_data_folder():
    """获取跨平台数据目录"""
    sys_type = platform.system()
    if sys_type == "Windows":
        return os.path.join(os.getenv('APPDATA', ''), "Nodanium")
    return os.path.join(os.path.expanduser("~"), ".Nodanium")


def default_data():
    """返回初始化的默认数据结构"""
    return {
        "default_enabled": True,
        "default_headers": [{"key": "User-Agent", "value": DEFAULT_USER_AGENT}],
        "default_cookie": "",
        "rules": [],
    }


def _load_data():
    """读取 site_headers.json，缺失或损坏时返回默认结构"""
    path = os.path.join(get_data_folder(), CONFIG_NAME)
    data = default_data()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for k in data:
                    if k in loaded:
                        data[k] = loaded[k]
        except Exception:
            pass
    #校验
    if not isinstance(data.get("rules"), list):
        data["rules"] = []
    if not isinstance(data.get("default_headers"), list):
        data["default_headers"] = []
    if not isinstance(data.get("default_cookie"), str):
        data["default_cookie"] = ""
    return data


def _log(msg):
    """把请求头解析结果同时输出到控制台（后台）和日志文件。"""
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line)
    except Exception:
        pass
    try:
        folder = get_data_folder()
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, LOG_NAME), 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except Exception:
        pass


def save_data(data):
    """将数据写回 site_headers.json"""
    path = os.path.join(get_data_folder(), CONFIG_NAME)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False


def new_rule(name="", domain="", **kwargs):
    """创建一个新的站点规则字典"""
    rule = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.uuid4()))),
        "name": name,
        "domain": domain,
        "enabled": True,
        "headers": [],
        "cookie": "",
    }
    rule.update(kwargs)
    return rule


def _host_of(url):
    """解析链接的主机名（含端口），失败返回空串"""
    url = (url or "").strip()
    m = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://([^/?#]+)", url)
    if m:
        return m.group(1).lower()

    m = re.match(r"^([^/?#:]+)", url)
    return m.group(1).lower() if m else ""


def _domain_root(host):
    """提取主域名（去掉端口与子域名通配前的 www 等）"""
    return _strip_port(host).lower()


def _strip_port(host):
    """清洗域名：去掉协议、路径、端口、用户信息、尾点等，只保留纯净主机名。"""
    host = host or ""
    host = host.strip().lower()

    m = re.search(r"(?<=://)([^/?#]+)", host)
    if m:
        host = m.group(1)
    else:
        host = host.split("/")[0].split("?")[0].split("#")[0]

    # 去掉 userinfo 部分
    if "@" in host:
        host = host.rsplit("@", 1)[1]

    # 去掉端口
    host = re.sub(r":\d+$", "", host)

    # 去掉 IPv6 括号
    host = host.replace("[", "").replace("]", "")

    # 去掉尾部点
    host = host.rstrip(".")
    return host


def _has_magic(pat):
    return "*" in pat or "?" in pat


def _matches(pattern, host, host_root):
    """判断 host 是否匹配某一规则域名"""
    pattern = (pattern or "").strip().lower()
    if not pattern:
        return False

    p = _strip_port(pattern)
    if not p:
        return False

  
    host_base = _strip_port(host)
    p_base = _strip_port(p)

    # 对 www. 前缀宽松处理，避免从 www 复制的头与无 www 的页面域名不一致而漏匹配
    host_norm = host_base[4:] if host_base.startswith('www.') else host_base
    p_norm = p_base[4:] if p_base.startswith('www.') else p_base

    if _has_magic(p):
        return _fnmatch_like(p, host_base)

    if p == host or p == host_root or p == host_base:
        return True
    if p_norm and p_norm == host_norm:
        return True
    
    if host_base.endswith("." + p):
        return True
    return False


def _fnmatch_like(pattern, host):
    """简化通配匹配，* 可匹配任意字符（包括点），支持 *.example.com"""
    regex = re.escape(pattern)
    regex = regex.replace(r"\*", ".*").replace(r"\?", ".")
    try:
        return re.fullmatch(regex, host) is not None
    except Exception:
        return pattern in host


def match_rule(data, url):
    """根据 URL 匹配第一条启用的站点规则；未命中返回 None"""
    host = _host_of(url)
    if not host:
        return None
    host_root = _domain_root(host)
    for rule in data.get("rules", []):
        if not isinstance(rule, dict):
            continue
        if not rule.get("enabled", True):
            continue
        if _matches(rule.get("domain", ""), host, host_root):
            return rule
    return None


def _parse_cookie(cookie_text):
    """将 'k=v; k2=v2; k3=v3' 文本解析为 dict"""
    result = {}
    if not cookie_text:
        return result
    for part in str(cookie_text).split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, _, value = part.partition("=")
            result[key.strip()] = value.strip()
    return result


def build_cookie_string(cookies_dict):
    """将 dict 拼回 'k=v; k2=v2' 字符串"""
    return "; ".join(f"{k}={v}" for k, v in cookies_dict.items())


def _headers_to_dict(header_list):
    """将 KV 条目列表转为 dict（跳过空键），后项覆盖前项"""
    result = {}
    for item in header_list or []:
        if not isinstance(item, dict):
            continue
        key = (item.get("key") or "").strip()
        value = item.get("value") or ""
        if not key:
            continue
        result[key] = value
    return result


def _apply_macros(text, ctx):
    """将文本中的 {url}/{host}/{domain}/{filename}/{filepath} 宏替换为实际值"""
    if not text:
        return text
    if isinstance(text, str):
        text = text.replace("{url}", ctx.get("url", ""))
        text = text.replace("{host}", ctx.get("host", ""))
        text = text.replace("{domain}", ctx.get("domain", ""))
        text = text.replace("{filename}", ctx.get("filename", ""))
        text = text.replace("{filepath}", ctx.get("filepath", ""))
    return text


def resolve_headers(url, filename="", save_path="", base_headers=None):
    """
    根据 URL 计算最终请求头 dict。

    :param url:         下载链接
    :param filename:    输出文件名（用于 {filename} 宏）
    :param save_path:   保存目录（用于 {filepath} 宏）
    :param base_headers: 调用方传入的原始请求头 dict（优先级最高）
    :return: 合并后的请求头 dict
    """
    data = _load_data()
    host = _host_of(url)
    host_root = _domain_root(host)

    ctx = {
        "url": url or "",
        "host": host,
        "domain": host_root,
        "filename": filename or "",
        "filepath": os.path.join(save_path or "", filename or ""),
    }

    merged = {}


    if data.get("default_enabled", True):
        for k, v in _headers_to_dict(data.get("default_headers", [])).items():
            merged[k] = _apply_macros(v, ctx)
        if data.get("default_cookie"):
            cookie = _parse_cookie(_apply_macros(data["default_cookie"], ctx))
            merged["Cookie"] = build_cookie_string(cookie)

    matched_name = ""
    matched_domain = ""
    rule = match_rule(data, url)
    if rule:
        for k, v in _headers_to_dict(rule.get("headers", [])).items():
            merged[k] = _apply_macros(v, ctx)
        if rule.get("cookie"):
            cookie = _parse_cookie(_apply_macros(rule["cookie"], ctx))
            merged["Cookie"] = build_cookie_string(cookie)
        matched_name = rule.get('name') or ""
        matched_domain = rule.get('domain') or ""

  
    for k, v in (base_headers or {}).items():
        merged[k] = _apply_macros(v, ctx)

    # 后台/日志输出匹配到的请求头项目
    try:
        rule_desc = f"「{matched_name}」/{matched_domain}" if matched_domain else "（未命中任何站点规则）"
        _log(f"请求头匹配: {url} -> {rule_desc}，共 {len(merged)} 项")
        for k, v in merged.items():
            _log(f"    {k}: {v}")
    except Exception:
        pass

    return merged


def export_rule_as_text(rule):
    """将单条站点规则导出为可读文本"""
    lines = []
    lines.append(f"# 站点名称: {rule.get('name', '')}")
    lines.append(f"# 匹配域名: {rule.get('domain', '')}")
    lines.append(f"# 启用: {'是' if rule.get('enabled', True) else '否'}")
    lines.append("")
    for item in rule.get("headers", []) or []:
        if isinstance(item, dict) and item.get("key"):
            lines.append(f"{item['key']}: {item.get('value', '')}")
    if rule.get("cookie"):
        lines.append(f"Cookie: {rule['cookie']}")
    return "\n".join(lines)


def export_all_as_text(data):
    """将所有启用的站点规则导出为纯文本（请求头拼接风格）"""
    sections = []
    for rule in data.get("rules", []):
        if not isinstance(rule, dict) or not rule.get("enabled", True):
            continue
        sections.append(export_rule_as_text(rule))
    return "\n\n" + "\n\n".join(sections)


# ------------------------------ 浏览器导出请求头解析 ------------------------------
# 支持从浏览器开发者工具复制的两类文本：
#   1) cURL 命令行（右键 Copy as cURL）
#   2) 逐行 "Key: Value" 请求头
# 解析结果中 Cookie 会被单独拆分出来：
#   返回 dict: {url, headers(列表[(key,value)]), cookie(str)}

def _parse_curl_text(text):
    """从 cURL 命令行文本提取 url 与 -H 请求头。
    返回 (url, headers_list)；headers_list 为 (key, value) 列表。
    """
    url = ""
    headers = []
    tokens = _tokenize_curl(text)
    it = iter(tokens)
    for tok in it:
        tl = tok.lower()
        if tl in ('--url', '--request-url', '-u') and not url:
            try:
                nxt = next(it)
            except StopIteration:
                break
            if '://' in nxt:
                url = nxt
        elif tl in ('-h', '--header'):
            try:
                hdr = next(it)
            except StopIteration:
                continue
            pair = _split_header_line(hdr)
            if pair:
                headers.append(pair)
 
    if not url:
        for tok in tokens:
            if ('://' in tok or tok.startswith('http:')) and '/' in tok:
                url = tok
                break
    return url, headers


def _tokenize_curl(text):
    """将 cURL 命令按 shell 词法切分为 token，保留每段字符串内容。"""
    import shlex
    tokens = []
    try:
        tokens = shlex.split(text, posix=True)
    except Exception:
  
        tokens = text.split()

    if tokens and tokens[0].lower() == 'curl':
        tokens = tokens[1:]
    return tokens


def _split_header_line(header):
    """解析 'Key: value' 单行，返回 (key, value) 或 None。"""
    if not header:
        return None
    if ':' in header:
        key, _, val = header.partition(':')
        key = key.strip()
        if key:
            return key, val.strip()
    return None


def parse_browser_export(text):
    """解析浏览器导出的请求头文本，自动识别 cURL 或逐行 Key: Value 格式。
    返回 dict: {url, headers: [(key, value), ...], cookie: str}
    """
    text = (text or "").strip()
    result = {"url": "", "headers": [], "cookie": ""}
    if not text:
        return result


    first_line = text.lstrip()[:20].lower()
    if first_line.startswith('curl ') or ' -h ' in text.lower() or ' --header ' in text.lower() or first_line.startswith('curl"') or first_line.startswith("curl'"):
        url, headers = _parse_curl_text(text)
        result["url"] = url
        result["headers"] = headers
    else:

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            pair = _split_header_line(line)
            if pair:
                result["headers"].append(pair)


    keep = []
    for key, val in result["headers"]:
        kl = key.lower()
        if kl in ('cookie', 'set-cookie'):
            result["cookie"] = val
        else:
            keep.append((key, val))
    result["headers"] = keep
    return result



_COOKIE_KEYS = {"cookie", "set-cookie"}

