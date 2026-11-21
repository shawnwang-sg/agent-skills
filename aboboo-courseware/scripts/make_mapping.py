# -*- coding: utf-8 -*-
"""给一个文件夹里的切分 mp3 生成 Aboboo 课件编号对照表。

用法: python -I make_mapping.py <mp3文件夹> --start 63 [--out CSV]
mp3 命名约定（lesson-splitter 的输出）: "<课号>-<段号> <标题> (<起>-<止>).mp3"，如
  "22-03 Jim Rohn - The Major KEY ... (12m00s-18m00s).mp3"
按文件名排序后依次编号：num = start, start+1, ...
课件名 = "{num:03d} {标题}-part{段号}"，如 "105 Jim Rohn - The Major KEY ...-part03"
默认写到 <mp3文件夹>/剪映原始字幕/课件编号对照.csv（UTF-8 BOM，列 id,num,name,base），
已存在则拒绝覆盖（加 --force 才覆盖）。
"""
import argparse
import csv
import re
import sys
from pathlib import Path

PAT = re.compile(r"^(?P<id>(?P<lesson>\d+)-(?P<part>\d+))\s+(?P<title>.+?)(\s+\([^()]*\))?$")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--start", type=int, required=True, help="第一个课件的编号，如 63")
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    folder = Path(a.folder)
    out = Path(a.out) if a.out else folder / "剪映原始字幕" / "课件编号对照.csv"
    if out.exists() and not a.force:
        sys.exit(f"{out} 已存在；确认要重编号再加 --force")
    rows = []
    for i, mp3 in enumerate(sorted(folder.glob("*.mp3"))):
        m = PAT.match(mp3.stem)
        if not m:
            sys.exit(f"文件名不符合 '<课号>-<段号> <标题> (...)': {mp3.name}")
        num = a.start + i
        rows.append({
            "id": m["id"],
            "num": num,
            "name": f"{num:03d} {m['title']}-part{m['part']}",
            "base": mp3.stem,
        })
    if not rows:
        sys.exit("文件夹里没有 mp3")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "num", "name", "base"], quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} 个课件：{rows[0]['num']:03d} ~ {rows[-1]['num']:03d} -> {out}")
    for r in rows[:3]:
        print("  ", r["id"], r["name"])


if __name__ == "__main__":
    main()
