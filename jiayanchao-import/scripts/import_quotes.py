# -*- coding: utf-8 -*-
"""把名言导入 growth-planner 的嘉言钞（data/data.json 里的 quotes 数组），自动去重、拆长段、拆出处。

用法：
  python import_quotes.py <输入> --source 厉害文字集锦 [--data C:\\Users\\Shugu\\growth-planner\\data\\data.json] [--dry-run]
输入可以是：quote-collection-publish 的 pages.json（含附录 extract）、JSON 字符串列表、或空行分隔的 txt。

规则：
  - 改写前先备份 data.json → data.backup-<时间>.json；只追加，不改原有句子；保留原文件换行风格
  - 去重 key：NFKC 归一化后去掉空白和标点、转小写；与库里任意一句互相包含（≥10 字）、
    或匹配字数占 ≥70%、或相似度 ≥0.6 都算重复（整条先比，拆分后的片段再比一次）
  - 超过 MAX+40 字（默认 160）的长段按句子拆成 ≤MAX（120）字左右的几句；单句超长在逗号处再拆
  - 末尾「——出处」（20 字以内）拆到 source 字段，否则 source 填 --source
  - 新句子字段：{"id": uuid4, "text", "source", "enabled": true}
"""
import argparse, datetime, difflib, json, os, re, shutil, unicodedata, uuid

ap = argparse.ArgumentParser()
ap.add_argument("input")
ap.add_argument("--source", required=True, help="没有出处时填的来源名，一般是集锦标题")
ap.add_argument("--data", default=r"C:\Users\Shugu\growth-planner\data\data.json")
ap.add_argument("--max", type=int, default=120)
ap.add_argument("--dry-run", action="store_true", help="只统计，不写文件")
A = ap.parse_args()
MAX = A.max

def key(t):
    return re.sub(r"[\s\W_]", "", unicodedata.normalize("NFKC", t)).lower()

def load(path):
    if path.lower().endswith(".txt"):
        s = open(path, encoding="utf-8-sig").read()
        return [x.strip() for x in re.split(r"\n\s*\n", s) if x.strip()]
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, dict) and "pages" in d:
        items = [it["t"] for p in d["pages"] for it in p["items"]]
        ex = (d.get("extract") or {}).get("items") or []
        return items + ["\n\n".join(ex)] if ex else items
    return [x["t"] if isinstance(x, dict) else x for x in d]

def sentences(t):
    out = []
    for para in [p for p in t.split("\n\n") if p.strip()]:
        ss = [s for s in re.findall(r".*?[。！？；!?][”’」』）)]*|.+$", re.sub(r"\s*\n\s*", "", para)) if s.strip()]
        m = []
        for s in ss:
            if m and (m[-1].count("“") > m[-1].count("”") or m[-1].count('"') % 2): m[-1] += s
            else: m.append(s)
        fine = []
        for s in m:
            if len(s) > MAX + 40:
                cur = ""
                for part in re.findall(r".*?[，,：:]|.+$", s):
                    if cur and len(cur) + len(part) > MAX: fine.append(cur); cur = part
                    else: cur += part
                if cur: fine.append(cur)
            else:
                fine.append(s)
        out.append(fine)
    return out

def chunks(t):
    t = t.strip()
    if len(t) <= MAX + 40:
        return [re.sub(r"\s*\n\s*", "", t)]
    res = []
    for sents in sentences(t):
        cur = ""
        for s in sents:
            if cur and len(cur) + len(s) > MAX: res.append(cur); cur = s
            else: cur += s
        if cur:
            if res and len(cur) < 30 and len(res[-1]) + len(cur) <= MAX + 40: res[-1] += cur
            else: res.append(cur)
    return res

def split_src(t):
    m = re.search(r"——\s*([^—]{1,20})$", t.strip())
    return (t[:m.start()].strip(), m.group(1).strip()) if m else (t, "")

raw = open(A.data, encoding="utf-8", newline="").read()
data = json.loads(raw)
quotes = data.setdefault("quotes", [])
old = [key(q.get("text", "")) for q in quotes]

def dup(n):
    for o in old:
        if not o: continue
        if n in o or (len(o) >= 10 and o in n): return True
        sm = difflib.SequenceMatcher(None, n, o, autojunk=False)
        if sm.real_quick_ratio() < 0.35 or sm.quick_ratio() < 0.35: continue
        if sum(b.size for b in sm.get_matching_blocks()) / len(n) >= 0.7 or sm.ratio() >= 0.6: return True
    return False

add, si, sc = [], 0, 0
for t in load(A.input):
    if not key(t): continue
    if dup(key(t)): si += 1; continue
    for c in chunks(t):
        k = key(c)
        if not k or dup(k): sc += 1; continue
        body, src = split_src(c)
        add.append({"id": str(uuid.uuid4()), "text": body, "source": src or A.source, "enabled": True})
        old.append(k)

L = sorted(len(x["text"]) for x in add) or [0]
print(f"原有 {len(quotes)} 句；整条重复跳过 {si}；拆分后片段重复跳过 {sc}；新增 {len(add)} 句（长度中位 {L[len(L)//2]}，最长 {L[-1]}）")
for x in add[:5]:
    print("  +", x["text"][:40], "｜", x["source"])
if A.dry_run or not add:
    print("（未写入）" if A.dry_run else "没有新句子，未写入"); raise SystemExit
bak = os.path.join(os.path.dirname(A.data), f"data.backup-{datetime.datetime.now():%Y%m%d-%H%M%S}.json")
shutil.copy2(A.data, bak)
quotes += add
nl = "\r\n" if "\r\n" in raw else "\n"
out = json.dumps(data, ensure_ascii=False, indent=2).replace("\n", nl) + (nl if raw.endswith(("\n", "\r\n")) else "")
open(A.data, "w", encoding="utf-8", newline="").write(out)
print(f"已写入，共 {len(quotes)} 句；备份：{bak}")
