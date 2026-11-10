"""生成每个 tab 的分类清单 <库>/_yuedu/topic_list_<tab>.txt，给润色子任务选 category / topic 用。

内容 = categories.json 里这个 tab 的大类（原样写）+ 每个大类已经用过的小主题（套用 topics.json 合并后，按篇数排）
+ 还没用过的建议小主题。每轮派子任务前跑一次，子任务就会优先沿用已有主题，不会冒出一堆碎主题。

categories.json 格式：{tab: {大类: [建议小主题, ...]}}；几个 tab 共用一套大类时可以写 {tab: "另一个tab名"}。
用法：python topic_list.py --root D:\\douyin
"""
import argparse, collections, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import Lib, add_root_arg  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    add_root_arg(ap)
    a = ap.parse_args()
    lib = Lib(a.root)
    cats = json.loads((lib.work / "categories.json").read_text(encoding="utf-8")) if (lib.work / "categories.json").exists() else {}
    tmap = json.loads((lib.work / "topics.json").read_text(encoding="utf-8")) if (lib.work / "topics.json").exists() else {}
    meta = {r["id"]: r["_lp"] for r in lib.items("id")}
    used = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for i, x in lib.done_results().items():
        if x.get("verdict") != "keep" or i not in meta:
            continue
        tab = x.get("tab") if x.get("tab") in lib.tabs else lib.folder_of(meta[i])
        c = x.get("category") or ""
        used[tab][c][tmap.get(c, {}).get(x.get("topic"), x.get("topic"))] += 1
    for tab in lib.tabs:
        spec = cats.get(tab, {})
        if isinstance(spec, str):
            spec = cats.get(spec, {})
        if isinstance(spec, list):
            spec = {c: [] for c in spec}
        pool = used[tab]
        lines = [f"「{tab}」的大类和小主题（category 原样写大类名，含空格和点；topic 优先从这里选，确实不合适才新起，并在汇报里列出）"]
        if lib.cfg["tab_desc"].get(tab):
            lines.append(f"这个分类收的是：{lib.cfg['tab_desc'][tab]}")
        for c in list(spec) + [c for c in pool if c not in spec and c]:
            have = [t for t, _ in pool[c].most_common() if t]
            extra = [t for t in spec.get(c, []) if t not in have]
            lines.append(f"{c}：" + "、".join([f"{t}({pool[c][t]})" for t in have] + extra))
        if not spec and not pool:
            lines.append("（还没定大类：先抽样标题定好 categories.json 再派子任务）")
        p = lib.work / f"topic_list_{tab}.txt"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(p)


if __name__ == "__main__":
    main()
