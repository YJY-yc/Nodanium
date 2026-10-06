# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import sys
import time
import json
import base64
import socket
import random
import subprocess
import threading
import platform
import requests

SYS = platform.system()
_IS_FROZEN = bool(getattr(sys, "frozen", False))


def _prog_dir():
    if _IS_FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def data_bin_dir():
    if SYS == "Windows":
        base = os.path.join(os.getenv('APPDATA', ''), "Nodanium", "aria2")
    else:
        base = os.path.join(os.path.expanduser("~"), ".cache", "Nodanium", "aria2")
    os.makedirs(base, exist_ok=True)
    return base


def _bin_name():
    return "aria2c.exe" if SYS == "Windows" else "aria2c"


def prog_bin_dir():
    """程序内二进制目录：程序(可执行文件)所在目录下的 bin/。"""
    return os.path.join(_prog_dir(), "bin")


def _upload_stat_file():
    return os.path.join(data_bin_dir(), "upload_stat.json")


def _load_upload_stat():
    """读取累计上传统计：{"total": int, "gids": {gid: max_uploadLength}}。"""
    try:
        with open(_upload_stat_file(), "r", encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            d.setdefault("total", 0)
            d.setdefault("gids", {})
            return d
    except Exception:
        pass
    return {"total": 0, "gids": {}}


def _save_upload_stat(d):
    try:
        with open(_upload_stat_file(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


def accumulated_upload():
    """返回软件记录的累计已上传字节数（跨重启持久化，含当前跟踪任务的峰值）。"""
    d = _load_upload_stat()
    return int(d.get("total", 0) or 0) + sum(int(v or 0) for v in (d.get("gids") or {}).values())


def reset_accumulated_upload():
    """清零累计上传统计。"""
    _save_upload_stat({"total": 0, "gids": {}})


def system_bin_dir():
    """系统级程序目录：Linux 为 /bin，Windows 为程序所在盘符下的 bin。"""
    return "/bin" if SYS != "Windows" else "bin"


def _system_path_exe():
    """使用系统 PATH(where/which)定位 aria2c。"""
    try:
        p = subprocess.run(["where", "aria2c"] if SYS == "Windows" else ["which", "aria2c"],
                           capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def resolve_aria2c():
    """按优先级解析 aria2c，返回 (路径, 来源标识)。

    优先级：/bin(系统目录) -> 程序目录/bin(程序存储目录) -> 缓存目录 -> 系统 PATH。
    来源标识用于面板展示：system / program / cache / path。
    """
    cands = ((os.path.join(system_bin_dir(), _bin_name()), "system"),
             (os.path.join(prog_bin_dir(), _bin_name()), "program"),
             (os.path.join(data_bin_dir(), _bin_name()), "cache"))
    for cand, kind in cands:
        if os.path.isfile(cand):
            return cand, kind
    exe = _system_path_exe()
    if exe:
        return exe, "path"
    return None, None


def find_aria2c():
    """返回可用的 aria2c 路径；禁用或找不到返回 None。"""
    if not aria2_enabled():
        return None
    return resolve_aria2c()[0]


SOURCE_LABELS = {"system": "系统目录", "program": "程序存储目录",
                 "cache": "软件缓存目录", "path": "系统 PATH"}


def engine_report():
    """返回引擎解析报告：各候选位置是否命中、当前生效来源、版本。

    给管理面板用，展示优先级链与最终生效引擎。
    """
    checks = [
        ("system", os.path.join(system_bin_dir(), _bin_name())),
        ("program", os.path.join(prog_bin_dir(), _bin_name())),
        ("cache", os.path.join(data_bin_dir(), _bin_name())),
    ]
    report = {"enabled": aria2_enabled(), "candidates": [],
              "exe": None, "source": None, "version": ""}
    for kind, path in checks:
        report["candidates"].append(
            {"kind": kind, "label": SOURCE_LABELS[kind], "path": path,
             "exists": os.path.isfile(path)})
    pexe = _system_path_exe()
    report["candidates"].append(
        {"kind": "path", "label": SOURCE_LABELS["path"],
         "path": pexe or "(PATH 中未找到)", "exists": bool(pexe)})
    exe, kind = resolve_aria2c()
    report["exe"], report["source"] = exe, kind
    if exe:
        try:
            out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=5)
            report["version"] = (out.stdout or "").splitlines()[0] if out.stdout else ""
        except Exception:
            pass
    return report


def _free_port():
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.bind(("127.0.0.1", 0)); p = sk.getsockname()[1]; sk.close(); return p


def source_kind(source):
    """识别 BT 来源：magnet/HTTP(含种子url) -> add_uri; 本地 .torrent -> add_torrent。"""
    if not isinstance(source, str):
        return None
    s = source.strip().lower()
    if s.startswith("magnet:"):
        return "magnet"
    if os.path.isfile(source) and s.endswith(".torrent"):
        return "torrent"
    if s.startswith("http://") or s.startswith("https://"):
        return "http"
    return None


class Aria2Client(object):
    """aria2 JSON-RPC 通信封装。"""
    def __init__(self, port, secret):
        self.url = "http://127.0.0.1:%d/jsonrpc" % port
        self.secret = secret

    def _post(self, method, params, timeout=10):
        body = {"jsonrpc": "2.0", "id": 1, "method": method,
                "params": ["token:" + self.secret] + list(params or [])}
        try:
            r = requests.post(self.url, json=body, timeout=timeout)
            r.raise_for_status()
            res = r.json()
            return res.get("result"), res.get("error")
        except Exception as e:
            return None, {"message": str(e)}

    def add_uri(self, uri, opts=None):
        return self._post("aria2.addUri", [[uri], dict(opts or {})])

    def add_torrent(self, torrent_path, opts=None):
        with open(torrent_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return self._post("aria2.addTorrent", [data, [], dict(opts or {})])

    def tell_status(self, gid):
        return self._post("aria2.tellStatus", [gid])

    def pause(self, gid):
        return self._post("aria2.pause", [gid])

    def unpause(self, gid):
        return self._post("aria2.unpause", [gid])

    def remove(self, gid):
        return self._post("aria2.remove", [gid])

    def remove_download_result(self, gid):
        return self._post("aria2.removeDownloadResult", [gid])

    def tell_active(self, keys=None):
        return self._post("aria2.tellActive", [keys] if keys else [])

    def tell_waiting(self, offset=0, num=1000, keys=None):
        return self._post("aria2.tellWaiting", [offset, num, keys] if keys else [offset, num])

    def tell_stopped(self, offset=0, num=1000, keys=None):
        return self._post("aria2.tellStopped", [offset, num, keys] if keys else [offset, num])

    def get_global_option(self):
        return self._post("aria2.getGlobalOption", [])

    def change_global_option(self, opts):
        return self._post("aria2.changeGlobalOption", [dict(opts or {})])

    def get_version(self, timeout=10):
        return self._post("aria2.getVersion", [], timeout=timeout)

    def get_global_stat(self, timeout=10):
        return self._post("aria2.getGlobalStat", [], timeout=timeout)

    def purge_download_result(self):
        return self._post("aria2.purgeDownloadResult", [])


_HANDLES = {}
_HANDLE_LOCK = threading.Lock()


def _register(eng, gid):
    with _HANDLE_LOCK:
        _HANDLES[gid] = eng


def _unregister(gid):
    with _HANDLE_LOCK:
        _HANDLES.pop(gid, None)


def set_pause(gid, pause):
    eng = _HANDLES.get(gid)
    if eng:
        if pause:
            return eng.client.pause(gid)
        return eng.client.unpause(gid)
    svc = SERVICE
    if svc and svc.is_running():
        return svc.client.pause(gid) if pause else svc.client.unpause(gid)
    return None, {"message": "任务已不存在"}


def cancel_task(gid):
    eng = _HANDLES.get(gid)
    if eng:
        try:
            eng.client.remove(gid)
        except Exception:
            pass
        eng.stop_ev.set()
        eng.stop()
        return True
    svc = SERVICE
    if svc and svc.is_running():
        try:
            svc.client.remove(gid)
            svc.client.remove_download_result(gid)
            return True
        except Exception:
            return False
    return False


class BtEngine(object):
    """单个 BT 下载任务的 aria2 会话。"""

    def __init__(self):
        self.port = _free_port()
        self.secret = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789")
                              for _ in range(16))
        self.proc = None
        self.client = Aria2Client(self.port, self.secret)
        self.stop_ev = threading.Event()

    def start(self, aria2c, save_path):
        os.makedirs(save_path, exist_ok=True)
        cmd = [aria2c,
               "--enable-rpc", "--rpc-listen-all=false",
               "--rpc-listen-port=%d" % self.port,
               "--rpc-secret=" + self.secret,
               "--dir=" + save_path,
               "--seed-time=0", "--split=16",
               "--max-connection-per-server=16", "--enable-dht=true",
               "--summary-interval=0", "--console-log-level=error"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        for _ in range(100):
            if self.proc.poll() is not None or self.stop_ev.is_set():
                return False
            try:
                r, e2 = self.client.tell_status("x")
                if r is not None or e2 is not None:
                    return True
            except Exception:
                pass
            time.sleep(0.2)
        return False

    def add(self, source, kind):
        if kind == "torrent":
            return self.client.add_torrent(source)
        return self.client.add_uri(source)

    def stop(self):
        self.stop_ev.set()
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except Exception:
                    self.proc.kill()
        except Exception:
            pass


def _files_of(d):
    files = d.get("files") or []
    out = []
    for f in files:
        if not f.get("selected", True):
            continue
        out.append({"path": f.get("path", ""),
                    "length": int(f.get("length", 0) or 0),
                    "completed": int(f.get("completedLength", 0) or 0)})
    return out


SERVICE = None
_SERVICE_LOCK = threading.Lock()


def _default_service_port():
    try:
        return int(read_config().get("aria2_rpc_port", 6800) or 6800)
    except Exception:
        return 6800


def _config_dir():
    if SYS == "Windows":
        return os.path.join(os.getenv('APPDATA', ''), "Nodanium")
    return os.path.join(os.path.expanduser("~"), ".Nodanium")


def read_config():
    try:
        with open(os.path.join(_config_dir(), "config.json"), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def write_config(cfg):
    try:
        base = _config_dir()
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False


def aria2_enabled():
    """aria2 功能总开关(默认禁用)，保存在 config.json 的 aria2_enabled。"""
    v = read_config().get("aria2_enabled", False)
    return str(v).lower() in ("true", "1", "yes", "on")


def set_aria2_enabled(flag):
    cfg = read_config()
    cfg["aria2_enabled"] = bool(flag)
    return write_config(cfg)


def bt_use_service():
    """BT 任务是否走常驻服务(可在 aria2 管理面板统一查看/做种)。"""
    v = read_config().get("bt_use_service", True)
    return str(v).lower() not in ("false", "0", "no", "off")


def bt_seed_time():
    """BT 做种时间(分钟)，0 表示不做种。"""
    try:
        return max(0, int(read_config().get("bt_seed_time", 0) or 0))
    except Exception:
        return 0


def bt_seed_ratio():
    """BT 做种分享率，0 表示不限制。"""
    try:
        return max(0.0, float(read_config().get("bt_seed_ratio", 1.0) or 0))
    except Exception:
        return 1.0


def app_download_dir():
    """软件统一决定的默认下载目录：读数据目录下 dir.txt，回退 ~/Downloads。"""
    base = _config_dir()
    try:
        with open(os.path.join(base, "dir.txt"), "r") as f:
            d = (f.read() or "").strip()
        if d:
            return d
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Downloads")


class Aria2Service(object):
    """常驻 aria2c 服务：单实例承载 RPC，供管理面板查看/控制任务与设置。"""

    def __init__(self, exe, port=None, secret=None, options=None):
        self.exe = exe
        cfg = read_config()
        self.port = int(port or _default_service_port())
        self.secret = secret or cfg.get("aria2_rpc_secret") or "".join(
            random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(16))
        self.options = dict(options if options is not None else (cfg.get("aria2_options") or {}))
        self.proc = None
        self.auto_started = False
        self.client = Aria2Client(self.port, self.secret)

    def is_running(self):
        """本实例拉起的进程存活，或端口上已有可用的 aria2 RPC 服务。"""
        if self.proc is not None and self.proc.poll() is None:
            return True
        return self.probe(timeout=1)[0]

    def start(self):
        if self.is_running():
            return True, None
        if not self.exe:
            return False, "未找到 aria2 引擎(已禁用或未安装)"
        os.makedirs(data_bin_dir(), exist_ok=True)
        os.makedirs(os.path.join(data_bin_dir(), "session"), exist_ok=True)
        session_file = os.path.join(data_bin_dir(), "session", "aria2.session")
        if not os.path.exists(session_file):
            try:
                open(session_file, "a").close()
            except Exception:
                pass
        cmd = [self.exe, "--enable-rpc", "--rpc-listen-all=false",
               "--rpc-listen-port=%d" % self.port,
               "--rpc-secret=" + self.secret,
               "--dir=" + app_download_dir(),
               "--save-session=" + session_file,
               "--input-file=" + session_file,
               "--save-session-interval=10",
               "--summary-interval=0", "--console-log-level=error"]
        _fixed = {"dir", "save_session", "input_file", "rpc_listen_port", "rpc_secret",
                  "enable_rpc", "rpc_listen_all", "summary_interval", "console_log_level",
                  "force_save"}
        _invalid = {"bt_enable_dht"}
        for k, v in self.options.items():
            if k in _fixed or k in _invalid or v in (None, ""):
                continue
            cmd.append("--%s=%s" % (k.replace("_", "-"), v))
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            return False, "启动 aria2 服务失败：" + str(e)
        for _ in range(100):
            if self.proc.poll() is not None:
                return False, "aria2 服务进程已退出(端口 %d 可能被占用)" % self.port
            try:
                r, e2 = self.client.get_version()
                if r is not None:
                    self._start_stat_sampler()
                    return True, None
                if isinstance(e2, dict) and e2.get("code"):
                    return False, "RPC 无响应：" + str(e2.get("message", e2))
            except Exception:
                pass
            time.sleep(0.2)
        return False, "等待 aria2 RPC 就绪超时"

    def _start_stat_sampler(self):
        """后台定时采样上传字节，保证即使用户不在面板页也能累计。"""
        if getattr(self, "_stat_thread", None) and self._stat_thread.is_alive():
            return

        def loop():
            while self.proc is not None and self.proc.poll() is None:
                try:
                    self.global_stat()
                except Exception:
                    pass
                time.sleep(5)
        self._stat_thread = threading.Thread(target=loop, daemon=True)
        self._stat_thread.start()

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=4)
                except Exception:
                    self.proc.kill()
            except Exception:
                pass
        self.proc = None

    def probe(self, timeout=2):
        """探测 RPC 是否可达（可用于连接外部已在运行的 aria2）。
        返回 (ok, version_dict_or_msg)。timeout 默认较短，便于作为存活探测。"""
        r, e = self.client.get_version(timeout=timeout)
        if r is not None:
            return True, r
        return False, (e or {}).get("message", "无法连接")

    def ensure_running(self):
        """若未运行则启动；返回 (ok, err)。"""
        if self.is_running():
            return True, None
        return self.start()

    def add_task(self, source, kind, opts=None, save_path=None, seed_time=None,
                 seed_ratio=None, seeding=False):
    
        o = {}
        if save_path:
            o["dir"] = save_path
        st = int(seed_time or 0)
        if seeding:
            if st > 0:
                o["seed-time"] = str(st)
            r = float(seed_ratio or 0)
            o["seed-ratio"] = str(r if r > 0 else 0)
            o["check-integrity"] = "true"
            o["allow-overwrite"] = "true"
            o["bt-seed-unverified"] = "false"
        else:
            o["seed-time"] = str(st)
            if seed_ratio and float(seed_ratio) > 0:
                o["seed-ratio"] = str(float(seed_ratio))
            elif st <= 0:
                o["seed-ratio"] = "1.0"
        if opts:
            o.update(dict(opts))
        if kind == "torrent":
            return self.client.add_torrent(source, o)
        return self.client.add_uri(source, o)

    def tell(self, gid):
        return self.client.tell_status(gid)

    def global_stat(self):
        """返回传输统计：累计上传(持久化) / 本次会话上传 / 实时速度 / 任务数。

        aria2 的 getGlobalStat 不含累计字节，且不跨重启保留；因此：
        - 本次会话上传 = 各任务 uploadLength 之和（按 gid 取历史最大值，应对任务退出）；
        - 累计上传 = 持久化文件 upload_stat.json 中的 total（跨重启累加）。
        """
        out = {"uploadLength": 0, "downloadLength": 0, "uploadSpeed": 0,
               "downloadSpeed": 0, "numActive": 0, "numWaiting": 0,
               "accumulated": accumulated_upload()}
        keys = ["gid", "uploadLength", "downloadLength", "uploadSpeed", "downloadSpeed"]
        try:
            r, _e = self.client.get_global_stat()
            if isinstance(r, dict):
                out["uploadSpeed"] = int(r.get("uploadSpeed", 0) or 0)
                out["downloadSpeed"] = int(r.get("downloadSpeed", 0) or 0)
                out["numActive"] = int(r.get("numActive", 0) or 0)
                out["numWaiting"] = int(r.get("numWaiting", 0) or 0)
        except Exception:
            pass
        stat = _load_upload_stat()
        gids = stat.get("gids") or {}
        gids = {str(k): int(v or 0) for k, v in gids.items()}
        seen = set()
        session_up = 0
        dirty = False
        for meth, num in (("tell_active", None), ("tell_waiting", 0), ("tell_stopped", 0)):
            try:
                if num is None:
                    rr, _e = self.client.tell_active(keys=keys)
                else:
                    rr, _e = getattr(self.client, meth)(0, 1000, keys)
            except Exception:
                continue
            for d in (rr or []):
                gid = str(d.get("gid", ""))
                if gid:
                    seen.add(gid)
                up = int(d.get("uploadLength", 0) or 0)
                if gid and up > int(gids.get(gid, 0) or 0):
                    gids[gid] = up
                    dirty = True
                if up:
                    session_up += up
                out["downloadLength"] += int(d.get("downloadLength", 0) or 0)
        new_total = int(stat.get("total", 0) or 0)
        for gid in list(gids.keys()):
            if gid not in seen:
                new_total += int(gids.get(gid, 0) or 0)
                gids.pop(gid, None)
                dirty = True
        if dirty:
            _save_upload_stat({"total": new_total, "gids": gids})
        out["uploadLength"] = session_up
        out["accumulated"] = new_total + sum(int(v or 0) for v in gids.values())
        return out

    def seeding_tasks(self):

        keys = ["gid", "status", "totalLength", "completedLength", "downloadSpeed",
                "uploadSpeed", "uploadLength", "connections", "dir", "files", "bittorrent",
                "seeder", "infoHash", "errorMessage", "following"]
        rows = []
        for meth, num in (("tell_active", None), ("tell_waiting", 200), ("tell_stopped", 200)):
            try:
                if num is None:
                    r, _e = self.client.tell_active(keys=keys)
                else:
                    r, _e = getattr(self.client, meth)(0, num, keys)
                if isinstance(r, list):
                    rows.extend(r)
            except Exception:
                pass
        out = []
        for d in rows:
            bt = d.get("bittorrent")
            if not isinstance(bt, dict):
                continue
            total = int(d.get("totalLength", 0) or 0)
            done = int(d.get("completedLength", 0) or 0)
            st = d.get("status")
            if st == "error":
                continue
            if total > 0 and done < total:
                continue
            if total == 0 and st not in ("active", "waiting"):
                continue
            files = d.get("files") or []
            def _is_meta(f):
                return os.path.basename(str(f.get("path", ""))).startswith("[METADATA]")
            real = [f for f in files if f.get("selected", True) and not _is_meta(f)]
            if files and not real:
                continue
            out.append(d)
        return out


import atexit as _atexit


def get_service(exe=None, port=None, secret=None, options=None):
    """获取(或在需要时创建)全局 aria2 服务单例。aria2 被禁用时返回 None。

    未显式传入参数时自动从 config.json 读取端口/密钥/选项，保证与已运行服务一致。
    """
    global SERVICE
    if not aria2_enabled() and exe is None:
        return None
    cfg = read_config()
    if port is None:
        port = int(cfg.get("aria2_rpc_port", 6800) or 6800)
    if secret is None:
        secret = cfg.get("aria2_rpc_secret") or None
    if options is None:
        options = cfg.get("aria2_options") or {}
    with _SERVICE_LOCK:
        if SERVICE is None or not SERVICE.is_running():
            SERVICE = Aria2Service(exe or find_aria2c(), port, secret, options)
        if exe:
            SERVICE.exe = exe
        if port:
            SERVICE.port = int(port)
        if secret:
            SERVICE.secret = secret
            SERVICE.client = Aria2Client(SERVICE.port, secret)
        if options:
            SERVICE.options = dict(options)
        return SERVICE


def stop_service():
    global SERVICE
    with _SERVICE_LOCK:
        if SERVICE:
            SERVICE.stop()
            SERVICE = None


def stop_service_if_idle():

    svc = SERVICE
    if not (svc and svc.is_running()):
        return
    if not getattr(svc, "auto_started", False):
        return
    try:
        act, _e = svc.client.tell_active(keys=["gid"])
        wait, _e = svc.client.tell_waiting(0, 1000, keys=["gid"])
        if (act or wait):
            return
    except Exception:
        return
    stop_service()


def _cleanup_service():
    try:
        stop_service()
    except Exception:
        pass


_atexit.register(_cleanup_service)


def run_bt_task(source, save_path, aria2c, on_state):
    """阻塞执行 BT 任务。on_state(state_dict, gid) 在当前(后台)线程回调。"""
    kind = source_kind(source)
    if kind is None:
        on_state({"status": "失败", "err": "无法识别的 BT 来源(支持 magnet、本地 .torrent、HTTPS 种子链接)"}, None)
        return False
    tmp = None
    if kind == "http" and source.strip().lower().endswith(".torrent"):
        try:
            rr = requests.get(source, timeout=60)
            rr.raise_for_status()
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".torrent", delete=False)
            tmp.write(rr.content); tmp.close()
            source, kind = tmp.name, "torrent"
        except Exception as e:
            on_state({"status": "失败", "err": "下载种子文件失败：" + str(e)}, None)
            return False
    eng = BtEngine()
    gid = None
    ok = False
    try:
        if not eng.start(aria2c, save_path):
            on_state({"status": "失败", "err": "无法启动 aria2 下载引擎"}, None)
            return False
        time.sleep(0.3)
        r, es = eng.add(source, kind)
        if es or not r:
            on_state({"status": "失败", "err": "添加任务失败：" + str(es.get("message", es))}, None)
            eng.stop(); return False
        gid = str(r)
        _register(eng, gid)
        if tmp:
            try:
                os.remove(tmp)
            except Exception:
                pass
            tmp = None

        bt_name = ""
        done = total = 0
        while True:
            if eng.stop_ev.is_set():
                on_state({"status": "取消"}, gid)
                eng.stop(); return False
            st, es = eng.client.tell_status(gid)
            if es:
                msg = str(es.get("message", ""))
                if "No such download" in msg:
                    break
                time.sleep(1); continue
            d = st or {}
            sts = d.get("status")
            total = int(d.get("totalLength", 0) or 0)
            done = int(d.get("completedLength", 0) or 0)
            info = (d.get("bittorrent") or {}).get("info") or {}
            if isinstance(info, dict) and info.get("name"):
                bt_name = info["name"]
            ndone = _files_of(d)
            if sts == "error":
                on_state({"status": "失败", "err": "下载引擎报错"}, gid); break
            if sts == "complete":
                on_state({"status": "完成", "done": done, "total": total,
                          "name": bt_name, "files": ndone}, gid); ok = True; break
            if sts == "removed":
                on_state({"status": "取消"}, gid); break
            if sts in ("active", "waiting"):
                speed = int(d.get("downloadSpeed", 0) or 0)
                on_state({"status": "下载中", "done": done, "total": total,
                          "speed": speed, "name": bt_name, "files": ndone}, gid)
            time.sleep(1.0)
    except Exception as e:
        try: eng.stop()
        except Exception: pass
        on_state({"status": "失败", "err": str(e)}, gid)
        return False
    finally:
        if gid:
            _unregister(gid)
        eng.stop()
    return ok


def _source_infohash(source):
    """从本地 .torrent/磁力链提取 infohash（小写）；失败返回空串。"""
    try:
        if os.path.isfile(source) and source.lower().endswith(".torrent"):
            return (_torrent_infohash(source) or "").lower()
        if isinstance(source, str) and source.strip().lower().startswith("magnet:"):
            return _infohash_in_text(source)
    except Exception:
        pass
    return ""


def _purge_infohash_task(svc, source):
    """清除服务中与 source 相同 infohash 的**无权任务**（stopped/error）。

    aria2 的 remove 是异步的，移除后 infohash 仍可能短暂占用；
    因此移除后轮询等待，确保下一次 add 不再报错误。
    注意：active/waiting 的正常任务不在此处理（避免误删用户正在下载的任务）。
    """
    ih = _source_infohash(source)
    for _ in range(3):
        targets = []
        try:
            for getter in (lambda: svc.client.tell_stopped(0, 1000, keys=["gid", "infoHash"]),
                           lambda: svc.client.tell_waiting(0, 1000, keys=["gid", "infoHash"])):
                res, _ = getter()
                for d in (res or []):
                    targets.append(d)
        except Exception:
            pass
        removed = False
        for d in targets:
            d_ih = (d.get("infoHash") or "").lower()
            gid = d.get("gid")
            match = (ih and d_ih and d_ih == ih) or (not ih and d_ih and d_ih in str(source).lower())
            if match and gid:
                try:
                    svc.client.remove(gid)
                except Exception:
                    pass
                try:
                    svc.client.remove_download_result(gid)
                except Exception:
                    pass
                removed = True
        try:
            svc.client.purge_download_result()
        except Exception:
            pass
        if not removed:
            break
        try:
            import time as _t
            _t.sleep(0.8)
        except Exception:
            pass


def find_active_gid(svc, source):
    """在服务 active/waiting 中查找同 infohash 的 gid；未找到返回 None。"""
    ih = _source_infohash(source)
    if not ih:
        return None
    try:
        for getter in (lambda: svc.client.tell_active(keys=["gid", "infoHash"]),
                       lambda: svc.client.tell_waiting(0, 1000, keys=["gid", "infoHash"])):
            res, _ = getter()
            for d in (res or []):
                if (d.get("infoHash") or "").lower() == ih:
                    return d.get("gid")
    except Exception:
        pass
    return None


def run_bt_task_via_service(source, save_path, on_state,
                            seed_time=None, seed_ratio=None):
    """将 BT 任务交给常驻 aria2 服务执行(可在管理面板统一查看)。

    与 run_bt_task 的区别：
    - 复用全局常驻服务(固定端口/密钥)，任务对管理面板可见；
    - 下载完成后**立即上报「完成」并返回**，进度窗随之关闭；
    - 需做种时任务保留在服务中(按 seed-time/seed-ratio)，由「aria2 管理」
      面板统一查看/控制；不需做种则完成后从服务中移除(文件保留)。
    on_state(state_dict, gid) 在当前(后台)线程回调。
    """
    kind = source_kind(source)
    if kind is None:
        on_state({"status": "失败", "err": "无法识别的 BT 来源(支持 magnet、本地 .torrent、HTTPS 种子链接)"}, None)
        return False
    if not aria2_enabled():
        on_state({"status": "失败", "err": "aria2 已禁用(可在偏好设置或管理面板启用)"}, None)
        return False
    tmp = None
    if kind == "http" and source.strip().lower().endswith(".torrent"):
        try:
            rr = requests.get(source, timeout=60)
            rr.raise_for_status()
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".torrent", delete=False)
            tmp.write(rr.content); tmp.close()
            source, kind = tmp.name, "torrent"
        except Exception as e:
            on_state({"status": "失败", "err": "下载种子文件失败：" + str(e)}, None)
            return False

    if seed_time is None:
        seed_time = bt_seed_time()
    if seed_ratio is None:
        seed_ratio = bt_seed_ratio()

    gid = None
    ok = False
    try:
        svc = get_service()
        if svc is None:
            on_state({"status": "失败", "err": "aria2 服务不可用(已禁用或未安装)"}, None)
            return False
        was_running = svc.is_running()
        tok, terr = svc.ensure_running()
        if not tok:
            on_state({"status": "失败", "err": "无法启动常驻服务：" + str(terr)}, None)
            return False
        if not was_running:
            try:
                svc.auto_started = True
            except Exception:
                pass
        # 同 infohash 已在下载中：复用该 gid，在窗口中显示其进度（不重复添加）
        _active_gid = find_active_gid(svc, source)
        if _active_gid:
            r, es = _active_gid, None
        else:
            # 添加前先清除服务中同 infohash 的残留（stopped/error）任务，
            # 否则 aria2 会接受任务后立即置于 error(already registered)。
            _purge_infohash_task(svc, source)
            r, es = svc.add_task(source, kind, save_path=save_path,
                                 seed_time=seed_time, seed_ratio=seed_ratio)
            if es and "already registered" in str(es.get("message", "")).lower():
                _purge_infohash_task(svc, source)
                r, es = svc.add_task(source, kind, save_path=save_path,
                                     seed_time=seed_time, seed_ratio=seed_ratio)
        if es or not r:
            on_state({"status": "失败", "err": "添加任务失败：" + str((es or {}).get("message", es))}, None)
            return False
        gid = str(r)
        if tmp:
            try:
                os.remove(tmp)
            except Exception:
                pass
            tmp = None

        bt_name = ""
        done = total = 0
        seeded = False
        # 刚添加时可能读到一次 removed/error 余波（同 infohash 刚被移除），
        # 前几次给容错重试机会，避免误报“取消”。
        grace = 3
        saw_progress = False
        while True:
            st, es = svc.tell(gid)
            if es:
                msg = str(es.get("message", ""))
                if "No such download" in msg or "not found" in msg.lower():
                    break
                time.sleep(1); continue
            d = st or {}
            sts = d.get("status")
            total = int(d.get("totalLength", 0) or 0)
            done = int(d.get("completedLength", 0) or 0)
            info = (d.get("bittorrent") or {}).get("info") or {}
            if isinstance(info, dict) and info.get("name"):
                bt_name = info["name"]
            ndone = _files_of(d)
            if sts == "error":
                if grace > 0 and not saw_progress:
                    grace -= 1
                    time.sleep(0.5)
                    continue
                on_state({"status": "失败", "err": d.get("errorMessage") or "下载引擎报错"}, gid)
                break
            if sts == "removed":
                if grace > 0 and not saw_progress:
                    grace -= 1
                    time.sleep(0.5)
                    continue
                on_state({"status": "取消"}, gid); break
            if sts == "complete":
                seeding = bool(seed_time and seed_time > 0)
                on_state({"status": "完成", "done": done, "total": total,
                          "name": bt_name, "files": ndone, "seeding": seeding}, gid)
                ok = True
                if not seeding:
                    stop_service_if_idle()
                break
            if sts in ("active", "waiting"):
                saw_progress = True
                grace = 0
                speed = int(d.get("downloadSpeed", 0) or 0)
                on_state({"status": "下载中", "done": done, "total": total,
                          "speed": speed, "name": bt_name, "files": ndone}, gid)
            time.sleep(1.0)
    except Exception as e:
        on_state({"status": "失败", "err": str(e)}, gid)
        return False
    return ok


def cancel_service_task(gid):
    """取消/移除服务中的指定任务（不拉起服务）。"""
    svc = SERVICE
    if not (svc and svc.is_running()):
        return False
    try:
        svc.client.remove(gid)
        svc.client.remove_download_result(gid)
        return True
    except Exception:
        return False


def _infohash_in_text(s):
    s = (s or "").lower()
    i = s.find("urn:btih:")
    if i >= 0:
        return s[i + 9:].split("&")[0].strip()
    return ""


def _bdecode(data, pos=0):
    c = data[pos:pos + 1]
    if c == b"i":
        e = data.index(b"e", pos)
        return int(data[pos + 1:e]), e + 1
    if c == b"l":
        pos += 1
        out = []
        while data[pos:pos + 1] != b"e":
            v, pos = _bdecode(data, pos)
            out.append(v)
        return out, pos + 1
    if c == b"d":
        pos += 1
        out = {}
        while data[pos:pos + 1] != b"e":
            k, pos = _bdecode(data, pos)
            v, pos = _bdecode(data, pos)
            out[k] = v
        return out, pos + 1
    if c.isdigit():
        e = data.index(b":", pos)
        n = int(data[pos:e])
        return data[e + 1:e + 1 + n], e + 1 + n
    raise ValueError("bad bencode")


def _torrent_infohash(path):
    try:
        raw = open(path, "rb").read()
        d, _ = _bdecode(raw)
        info = d.get(b"info")
        if not isinstance(info, dict):
            return ""
        pos = raw.find(b"4:info") + len(b"4:info")
        _, end = _bdecode(raw, pos)
        import hashlib
        return hashlib.sha1(raw[pos:end]).hexdigest()
    except Exception:
        return ""


def _local_torrent_for(source, save_path):
    """在 save_path 下按 infohash 找本地 .torrent 文件。"""
    ih = _infohash_in_text(source)
    if not ih or not save_path or not os.path.isdir(save_path):
        return None
    try:
        names = [n for n in os.listdir(save_path) if n.lower().endswith(".torrent")]
    except Exception:
        return None
    for n in names:
        if ih in n.lower():
            return os.path.join(save_path, n)
    for n in names:
        if _torrent_infohash(os.path.join(save_path, n)) == ih:
            return os.path.join(save_path, n)
    return None


def start_seed(source, save_path, seed_time=None, seed_ratio=None, force=False):

    if not aria2_enabled():
        return False, "aria2 已禁用"
    if seed_time is None:
        seed_time = bt_seed_time() or 0
    if seed_ratio is None:
        seed_ratio = bt_seed_ratio()
    use_source = source
    lt = _local_torrent_for(source, save_path)
    if lt:
        use_source = lt
    kind = source_kind(use_source)
    if kind is None:
        return False, "无法识别的 BT 来源"
    if force and not (seed_time > 0) and not (seed_ratio > 0):
        seed_ratio = 0.0
    try:
        svc = SERVICE
        if not (svc and svc.is_running()):
            return False, "aria2 服务未运行（请先在“服务”页启动）"
        r, es = svc.add_task(use_source, kind, save_path=save_path,
                             seed_time=seed_time, seed_ratio=seed_ratio,
                             seeding=True)
        if es and "already registered" in str(es.get("message", "")).lower():
            gid = find_seed_gid(source)
            if gid:
                return True, gid
            return False, "任务已在做种列表中"
        if es or not r:
            return False, str((es or {}).get("message", es))
        return True, str(r)
    except Exception as e:
        return False, str(e)


def find_seed_gid(source):
  
    svc = SERVICE
    if not (svc and svc.is_running()):
        return None
    src = (source or "").lower()
    for meth in ("tell_active", "tell_waiting", "tell_stopped"):
        try:
            r, _e = getattr(svc.client, meth)(keys=["gid", "infoHash", "bittorrent"])
        except Exception:
            continue
        for d in (r or []):
            if not isinstance(d.get("bittorrent"), dict):
                continue
            ih = (d.get("infoHash") or "").lower()
            if ih and ih in src:
                return d.get("gid")
    return None


def _completed_bt_records():
  
    try:
        import DownloadUI as _DU
        hist = list(getattr(_DU, "download_history", []) or [])
    except Exception:
        return []
    out, seen = [], set()
    for r in hist:
        try:
            if r.get("proto") != "bt":
                continue
            st = str(r.get("status", ""))
            if not st.startswith("已完成"):
                continue
            nm = str(r.get("bt_name") or r.get("filename") or "")
            if nm.startswith("[METADATA]"):
                continue
            src = r.get("source") or r.get("url") or ""
            if not src:
                continue
            key = r.get("bt_gid") or src
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        except Exception:
            continue
    return out


def seed_all(force=True):

    ok_n, fails = 0, []
    for r in _completed_bt_records():
        src = r.get("source") or r.get("url") or ""
        if find_seed_gid(src):
            ok_n += 1
            continue
        ok, info = start_seed(src, r.get("save_path") or app_download_dir(), force=force)
        if ok:
            ok_n += 1
        else:
            fails.append((r.get("bt_name") or r.get("filename") or src, info))
    return ok_n, fails
