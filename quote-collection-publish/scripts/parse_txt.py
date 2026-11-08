# -*- coding: utf-8 -*-
"""把一个或多个名言 txt 拆成条目，并做去重，输出 raw_items.json 供人工/Claude 分类。

用法：python parse_txt.py 原集锦.txt [新增素材.txt ...] --out <工作目录>/raw_items.json

拆条规则（按优先级）：
  - 「———」(4 个以上破折号) 独占一行 → 条目分隔
  - 「=====」包住的一行 → 原文已有的分类标题，记在 src_cat 里（仅供参考，最终分类按内容重排）
  - 文件里没有破折号分隔线时，按空行分条
去重：去掉空白和标点后，被别的条目包含、或相似度 > 0.8 的视为重复，只留先出现的那条（先给的文件优先）。
输出：[{"id":0,"t":"...","src":"文件名","src_cat":"...","len":汉字数}, ...] 以及 dups 列表。
"""
import argparse, difflib, json, os, re

ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="+")
ap.add_argument("--out", required=True)
A = ap.parse_args()

def norm(s):
    return re.sub(r"[\W_a-zA-Z0-9]+", "", s)

items, dups = [], []
for fp in A.files:
    s = open(fp, encoding="utf-8-sig").read().replace("\r\n", "\n")
    blocks = [("", s)]
    parts = re.split(r"\n=+\n(.+?)\n=+\n", "\n" + s)
    if len(parts) > 1:
        blocks = [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]
    for cat, body in blocks:
        if re.search(r"^\s*—{4,}\s*$", body, re.M):
            raw = re.split(r"\n\s*—{4,}\s*\n", body)
        else:
            raw = re.split(r"\n\s*\n", body)
        for x in raw:
            x = re.sub(r"\n{3,}", "\n\n", x.strip())
            if not x:
                continue
            nx = norm(x)
            hit = None
            for it in items:
                o = it["_n"]
                if not nx or not o:
                    continue
                if nx in o or (len(o) > 8 and o in nx) or (
                        difflib.SequenceMatcher(None, nx, o, autojunk=False).quick_ratio() > 0.85 and
                        difflib.SequenceMatcher(None, nx, o, autojunk=False).ratio() > 0.8):
                    hit = it; break
            if hit:
                dups.append({"dup": x[:60], "kept_id": hit["id"]}); continue
            items.append({"id": len(items), "t": x, "src": os.path.basename(fp), "src_cat": cat,
                          "len": len(re.sub(r"[^一-鿿]", "", x)), "_n": nx})
for it in items:
    it.pop("_n")
os.makedirs(os.path.dirname(os.path.abspath(A.out)), exist_ok=True)
json.dump({"items": items, "dups": dups}, open(A.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"条目 {len(items)}，去重跳过 {len(dups)}，总汉字 {sum(i['len'] for i in items)}（按每分钟 275 字约 {sum(i['len'] for i in items)/275:.0f} 分钟）")
print("最长 5 条：", [(i["id"], i["len"]) for i in sorted(items, key=lambda i: -i["len"])[:5]])
