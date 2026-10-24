# Copyright (c) 2025-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT
import os
import json
import uuid
import platform
import datetime
import threading

_lock = threading.RLock()


def data_folder() -> str:
    if platform.system() == "Windows":
        return os.path.join(os.getenv("APPDATA", ""), "Nodanium")
    return os.path.join(os.path.expanduser("~"), ".Nodanium")


def history_file() -> str:
    return os.path.join(data_folder(), "History.json")


def generate_uuid() -> str:
    return str(uuid.uuid4())


def _read(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def load() -> list:
    with _lock:
        path = history_file()
        records = _read(path)
        for rec in records:
            if "uuid" not in rec:
                rec["uuid"] = generate_uuid()
        records.sort(key=lambda x: x.get("timestamp", ""))
        return records


def save(records: list) -> bool:
    with _lock:
        path = history_file()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(tmp, path)
            return True
        except Exception:
            return False


def add_record(url: str, filename: str, save_path: str, status: str = "已完成",
               file_size: int = 0, source: str = "cli", **extra) -> dict:
    with _lock:
        records = load()
        record = {
            "uuid": generate_uuid(),
            "url": url,
            "filename": filename,
            "save_path": save_path,
            "status": status,
            "file_size": int(file_size or 0),
            "source": source,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        record.update(extra)
        records.append(record)
        save(records)
        return record


def update_record(record_uuid: str, **kwargs) -> bool:
    if not record_uuid:
        return False
    with _lock:
        records = load()
        for rec in records:
            if rec.get("uuid") == record_uuid:
                rec.update(kwargs)
                save(records)
                return True
        return False


def find_record(record_uuid: str):
    for rec in load():
        if rec.get("uuid") == record_uuid:
            return rec
    return None


def delete_record(record_uuid: str) -> bool:
    with _lock:
        records = load()
        kept = [r for r in records if r.get("uuid") != record_uuid]
        if len(kept) == len(records):
            return False
        save(kept)
        return True
