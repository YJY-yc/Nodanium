# Copyright (c) 2023-2026 YUJY(YJY-yc)
# This file is licensed under the MIT License.
# SPDX-License-Identifier: MIT

import os
import glob

PROGRESS_SUFFIX = "_download_progress.json"
LEGACY_PROGRESS_NAME = "download_progress.json"
NDF_TMP_SUFFIX = ".ndf.tmp"


def _safe_remove(path):
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            import shutil
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.exists(path):
            os.remove(path)
        return True
    except Exception:
        return False


def cleanup_download_artifacts(save_path, filename=""):

    if not save_path or not os.path.isdir(save_path):
        return

    legacy_temp = os.path.join(save_path, "temp")
    if os.path.isdir(legacy_temp):
        try:
      
            entries = os.listdir(legacy_temp)
            if not entries or all(
                (filename and os.path.basename(e).startswith(f"{filename}."))
                or e.startswith("chunk_")
                for e in entries
            ):
                _safe_remove(legacy_temp)
        except Exception:
            pass

    if not filename:
        return
    
    for name in (f"{filename}{PROGRESS_SUFFIX}",
                 f"{filename}_{LEGACY_PROGRESS_NAME}",
                 f"{filename}.ndf.tmp",
                 f"{filename}.tmp"):
        p = os.path.join(save_path, name)
        if os.path.exists(p) and os.path.isfile(p):
            _safe_remove(p)


def cleanup_save_dir(save_path):

    if not save_path or not os.path.isdir(save_path):
        return
    patterns = (
        os.path.join(save_path, f"*{PROGRESS_SUFFIX}"),
        os.path.join(save_path, LEGACY_PROGRESS_NAME),
        os.path.join(save_path, "*.ndf.tmp"),
    )
    for pat in patterns:
        for p in glob.glob(pat):
            if os.path.isfile(p):
                _safe_remove(p)
    legacy_temp = os.path.join(save_path, "temp")
    if os.path.isdir(legacy_temp):
        _safe_remove(legacy_temp)


def _referenced_progress_files():

    referenced = set()
    try:
        import DownloadUI
        DownloadUI.load_download_history()
        for rec in getattr(DownloadUI, "download_history", []) or []:
            if rec.get("proto") == "bt":
                uid = str(rec.get("uuid", ""))
                referenced.add("bt_" + uid[:8] + ".json")
            fn = rec.get("filename", "")
            if fn:
                referenced.add(f"{fn}{PROGRESS_SUFFIX}")
            rf = rec.get("resume_file", "")
            if rf:
                referenced.add(os.path.basename(rf))
    except Exception:
        pass
    return referenced


def cleanup_stale_progress_files(process_dir=None):
 
    if process_dir is None:
        try:
            from DownloadUI import PROCESS_DIR
            process_dir = PROCESS_DIR
        except Exception:
            base = os.path.expanduser("~")
            process_dir = os.path.join(base, ".Nodanium", "DownloadProcess")
    if not process_dir or not os.path.isdir(process_dir):
        return 0, 0

    referenced = _referenced_progress_files()
    removed = 0
    kept = 0
    for name in os.listdir(process_dir):
        p = os.path.join(process_dir, name)
        if not os.path.isfile(p):
            continue
        if not (name.endswith(PROGRESS_SUFFIX) or name.startswith("bt_")):
            continue

        if name in referenced:
            kept += 1
            continue
        if _safe_remove(p):
            removed += 1
        else:
            kept += 1
    return removed, kept


def cleanup_all(save_paths=None):

    paths = set(save_paths or [])
    if not paths:
        try:
            import DownloadUI
            DownloadUI.load_download_history()
            for rec in getattr(DownloadUI, "download_history", []) or []:
                sp = rec.get("save_path")
                if sp:
                    paths.add(sp)
        except Exception:
            pass
    for sp in paths:
        if sp and os.path.isdir(sp):
            cleanup_save_dir(sp)
    removed, kept = cleanup_stale_progress_files()
    return {"dirs": len(paths), "progress_removed": removed, "progress_kept": kept}


if __name__ == "__main__":
    print(cleanup_all())
