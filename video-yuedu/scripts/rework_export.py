"""找出改动超过上限（默认 15%）的视频篇目，连同原转写、现稿和逐处差异导出成返工批次。

用法：python rework_export.py --root D:\\douyin [--limit 15] [--size 20]
输出：<库>/_yuedu/todo/rework_<时间>_<序号>.json；子任务返工后写到 done/batch_rework_<时间>_<序号>.json
（文件名排序在原批次之后，同 id 的新结果会覆盖旧结果）。
"""
import argparse, difflib, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build_yuedu import PUNCT, change_pct, norm  # noqa: E402
from lib import Lib, add_root_arg  # noqa: E402


def ops(raw, body):
    a, b = PUNCT.sub("", raw), norm(body)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op != "equal":
            out.append(f"{op}: 「{a[i1:i2][:40]}」→「{b[j1:j2][:40]}」")
    return out


def main():
    ap = argparse.ArgumentParser()
    add_root_arg(ap)
    ap.add_argument("--limit", type=float, default=15)
    ap.add_argument("--size", type=int, default=20)
    a = ap.parse_args()
    lib = Lib(a.root)
    res = lib.done_results()
    meta = {r["id"]: r for r in lib.items("id, author, title, transcript")}
    items = []
    for i, x in res.items():
        if x.get("verdict") != "keep" or i not in meta:
            continue
        raw = meta[i]["transcript"] or ""
        p = change_pct(raw, x.get("body") or "")
        if p is not None and p > a.limit:
            items.append({"id": i, "pct": round(p, 1), "author": meta[i]["author"] or "", "title": meta[i]["title"] or "",
                          "raw": raw, "current": x, "diff": ops(raw, x.get("body") or "")})
    items.sort(key=lambda x: -x["pct"])
    stamp = time.strftime("%m%d%H%M")
    (lib.work / "todo").mkdir(parents=True, exist_ok=True)
    for n in range(0, len(items), a.size):
        p = lib.work / "todo" / f"rework_{stamp}_{n // a.size + 1:03d}.json"
        p.write_text(json.dumps(items[n:n + a.size], ensure_ascii=False, indent=1), encoding="utf-8")
        print(p)
    print(f"超过 {a.limit}% 的共 {len(items)} 篇")


if __name__ == "__main__":
    main()
