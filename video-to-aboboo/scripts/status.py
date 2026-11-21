# -*- coding: utf-8 -*-
"""端到端流水线进度表：每段走到哪一步了。

用法: python -I status.py <mp3文件夹>
读取 <mp3文件夹>/剪映原始字幕/课件编号对照.csv，逐段检查：
  jy   = 剪映原始字幕/<base>.jy.srt   （剪映已识别导出）
  job  = 剪映原始字幕/<id>.job.json   （已分句翻译）
  srt  = <base>.srt + <base>.en.srt   （双语/纯英文字幕已生成）
  q99  = <base>.q99                    （Aboboo 课件已保存；上传与否看 Aboboo，本表看不到）
"""
import csv
import sys
from pathlib import Path


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    folder = Path(sys.argv[1])
    raw = folder / "剪映原始字幕"
    rows = list(csv.DictReader((raw / "课件编号对照.csv").open(encoding="utf-8-sig")))
    stages = {"jy": [], "job": [], "srt": [], "q99": []}
    print(f"{'num':>4} {'id':<7} jy job srt q99")
    for r in rows:
        b = r["base"]
        have = {
            "jy": (raw / f"{b}.jy.srt").exists(),
            "job": (raw / f"{r['id']}.job.json").exists(),
            "srt": (folder / f"{b}.srt").exists() and (folder / f"{b}.en.srt").exists(),
            "q99": (folder / f"{b}.q99").exists(),
        }
        for k, v in have.items():
            if not v:
                stages[k].append(r["id"])
        print(f"{int(r['num']):>4} {r['id']:<7} " + " ".join(" Y " if have[k] else " . " for k in have))
    print()
    for k, ids in stages.items():
        print(f"缺 {k}: {len(ids)} 个 {', '.join(ids[:12])}{' ...' if len(ids) > 12 else ''}")


if __name__ == "__main__":
    main()
