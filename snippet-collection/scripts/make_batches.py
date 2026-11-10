"""Split a folder of note sub-folders (images + 正文.txt) into OCR batches.

Usage: python -X utf8 make_batches.py <source_dir> <work_dir> [--per 42]
Writes <work_dir>/manifest.json and batchN.txt files. Each batch block:
    ### NNN | <sub-folder name>
    <absolute image path>
    ...
"""
import argparse
import json
import os

IMG = (".jpg", ".jpeg", ".png", ".webp")
ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("work")
ap.add_argument("--per", type=int, default=42, help="target images per batch")
a = ap.parse_args()
os.makedirs(a.work, exist_ok=True)

dirs = sorted(d for d in os.listdir(a.src) if os.path.isdir(os.path.join(a.src, d)))
items = []
for i, d in enumerate(dirs, 1):
    imgs = sorted(f for f in os.listdir(os.path.join(a.src, d)) if f.lower().endswith(IMG))
    items.append({"n": i, "dir": d, "images": [os.path.join(a.src, d, f) for f in imgs]})
with open(os.path.join(a.work, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=1)

batches, cur, cnt = [], [], 0
for it in items:
    cur.append(it)
    cnt += len(it["images"])
    if cnt >= a.per:
        batches.append(cur)
        cur, cnt = [], 0
if cur:
    batches.append(cur)
for k, b in enumerate(batches, 1):
    with open(os.path.join(a.work, f"batch{k}.txt"), "w", encoding="utf-8") as f:
        for it in b:
            f.write(f"### {it['n']:03d} | {it['dir']}\n")
            f.writelines(p + "\n" for p in it["images"])
    print(f"batch{k}: {len(b)} folders, {sum(len(x['images']) for x in b)} images")

loose = [f for f in os.listdir(a.src) if f.lower().endswith(IMG)]
videos = [f for f in os.listdir(a.src) if f.lower().endswith(".mp4")]
print(f"folders {len(items)}, images {sum(len(x['images']) for x in items)}, "
      f"loose images in root {len(loose)} {loose[:3]}, videos {len(videos)}")
