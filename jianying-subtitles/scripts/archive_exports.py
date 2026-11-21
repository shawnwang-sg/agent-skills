# -*- coding: utf-8 -*-
"""把剪映导出到桌面的 jy_<id>.srt 归档成 <base>.jy.srt，并列出每段的进度。

用法: python -I archive_exports.py <mp3文件夹> [--desktop DIR]
需要 <mp3文件夹>/剪映原始字幕/课件编号对照.csv（aboboo-courseware 的 make_mapping.py 生成）。
- 桌面上的 jy_<id>.srt → <mp3文件夹>/剪映原始字幕/<base>.jy.srt（已存在则覆盖，等于重导）
- 打印：已归档但还没有 <id>.job.json 的 id（= 待翻译），方便直接派给翻译子代理
"""
import argparse
import csv
import shutil
import sys
from pathlib import Path


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--desktop", default=str(Path.home() / "Desktop"))
    a = ap.parse_args()
    folder = Path(a.folder)
    raw = folder / "剪映原始字幕"
    rows = list(csv.DictReader((raw / "课件编号对照.csv").open(encoding="utf-8-sig")))
    moved = []
    for r in rows:
        src = Path(a.desktop) / f"jy_{r['id']}.srt"
        if src.exists():
            shutil.move(str(src), str(raw / f"{r['base']}.jy.srt"))
            moved.append(r["id"])
    print("本次归档:", ", ".join(moved) or "无")
    todo = [r["id"] for r in rows
            if (raw / f"{r['base']}.jy.srt").exists() and not (raw / f"{r['id']}.job.json").exists()]
    print("待翻译（有 .jy.srt 无 job.json）:", ", ".join(todo) or "无")
    missing = [r["id"] for r in rows if not (raw / f"{r['base']}.jy.srt").exists()]
    print("还没从剪映导出:", ", ".join(missing) or "无")


if __name__ == "__main__":
    main()
