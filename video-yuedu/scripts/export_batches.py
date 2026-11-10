"""从学习台导出这个库里「已转成文字、还没润色」的条目，分批写成 JSON 给子任务处理。

用法：
  python export_batches.py --root D:\\douyin [--folders 厉害,爱好] [--size 30] [--limit N]
  python export_batches.py --root D:\\douyin --ids 1649,1747 --prefix batch_reclass   # 指定条目（如挪过分类的）
默认：所有 tab（含根目录下没分类的 inbox），每批 30 条。已经在 done/ 里有结果、或已导出还在处理中的条目不会重复导出
（--ids 指定时不跳过 done，用来重做）。
输出：<库>/_yuedu/todo/<prefix>_<时间>_<序号>.json，并打印批次文件列表。
"""
import argparse, json, re, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import Lib, add_root_arg  # noqa: E402


def done_ids(lib):
    """已经润色完的 id，加上已导出、还在处理中的 id（todo 里有、done 里还没有同名结果的批次）。"""
    ids = set()
    for f in (lib.work / "done").glob("*.json"):
        try:
            ids |= {int(x["id"]) for x in json.loads(f.read_text(encoding="utf-8"))}
        except Exception as e:
            print("⚠ 读不了", f.name, e)
    for f in (lib.work / "todo").glob("*.json"):
        if not (lib.work / "done" / f.name).exists():
            ids |= {int(x["id"]) for x in json.loads(f.read_text(encoding="utf-8"))}
    return ids


def item_json(lib, r):
    title = re.sub(r"#\S+", "", r["title"] or "").strip()[:80]
    return {"id": r["id"], "folder": lib.folder_of(r["local_path"]), "author": r["author"] or "", "title": title,
            "duration": round(r["duration"] or 0), "kind": "图文" if r["media_type"] == "note" else "视频",
            "transcript": r["transcript"]}


def write_batches(lib, todo, size, prefix="batch"):
    (lib.work / "todo").mkdir(parents=True, exist_ok=True)
    (lib.work / "done").mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%m%d%H%M")
    files = []
    for n in range(0, len(todo), size):
        p = lib.work / "todo" / f"{prefix}_{stamp}_{n // size + 1:03d}.json"
        p.write_text(json.dumps(todo[n:n + size], ensure_ascii=False, indent=1), encoding="utf-8")
        files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser()
    add_root_arg(ap)
    ap.add_argument("--folders", default="", help="只导出这些 tab，逗号分隔；默认全部")
    ap.add_argument("--ids", default="", help="只导出这些条目 id，逗号分隔")
    ap.add_argument("--prefix", default="batch")
    ap.add_argument("--size", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    lib = Lib(a.root)
    folders = [f for f in a.folders.split(",") if f] or lib.all_tabs()
    want = {int(i) for i in a.ids.split(",") if i.strip()}
    seen = set() if want else done_ids(lib)
    rows = lib.items("id, author, title, duration, media_type, transcript, local_path",
                     "transcript is not null and transcript<>'' and status in ('need_key','done')")
    todo = [item_json(lib, r) for r in sorted(rows, key=lambda r: r["id"])
            if (r["id"] in want if want else lib.folder_of(r["local_path"]) in folders) and r["id"] not in seen]
    todo.sort(key=lambda x: (folders.index(x["folder"]) if x["folder"] in folders else 99, x["id"]))
    if a.limit:
        todo = todo[: a.limit]
    files = write_batches(lib, todo, a.size, a.prefix)
    print(f"待润色 {len(todo)} 条，{len(files)} 批")
    for p in files:
        print(p)


if __name__ == "__main__":
    main()
