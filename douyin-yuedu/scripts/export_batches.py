"""从 douyin-fav-study 学习台导出「已转成文字、还没润色」的条目，分批写成 JSON 给子任务处理。

用法：
  python export_batches.py [--folders 厉害,爱好] [--size 30] [--limit N]
默认：所有收藏分类，每批 30 条。已经在 done/ 里有结果的条目不会重复导出。
输出：<工作目录>/todo/batch_<时间>_<序号>.json，并打印批次文件列表。
"""
import argparse, json, re, sqlite3, time
from pathlib import Path

APP = Path(r"C:\Users\Shugu\douyin-fav-study")
WORK = Path(r"D:\douyin\_yuedu")
ORDER = ["厉害", "爱好", "厉害文字", "身体健康", "美食"]


def done_ids():
    """已经润色完的 id，加上已导出、还在处理中的 id（todo 里有、done 里还没有同名结果的批次）。"""
    ids = set()
    for f in (WORK / "done").glob("*.json"):
        try:
            ids |= {int(x["id"]) for x in json.loads(f.read_text(encoding="utf-8"))}
        except Exception as e:
            print("⚠ 读不了", f.name, e)
    for f in (WORK / "todo").glob("*.json"):
        if not (WORK / "done" / f.name).exists():
            ids |= {int(x["id"]) for x in json.loads(f.read_text(encoding="utf-8"))}
    return ids


def folder_of(p):
    parts = Path(p or "").parts
    return parts[2] if len(parts) > 3 and parts[1] == "douyin" else (parts[-2] if len(parts) > 1 else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folders", default=",".join(ORDER))
    ap.add_argument("--size", type=int, default=30)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    folders = [f for f in a.folders.split(",") if f]
    (WORK / "todo").mkdir(parents=True, exist_ok=True)
    (WORK / "done").mkdir(parents=True, exist_ok=True)
    seen = done_ids()
    c = sqlite3.connect(f"file:{APP / 'data' / 'library.db'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    rows = c.execute("""select id, author, title, duration, media_type, transcript, local_path, url
                        from items where source='local' and transcript is not null and transcript<>''
                        and status in ('need_key','done') order by id""").fetchall()
    todo = []
    for r in rows:
        f = folder_of(r["local_path"])
        if f in folders and r["id"] not in seen:
            title = re.sub(r"#\S+", "", r["title"] or "").strip()[:80]
            todo.append({"id": r["id"], "folder": f, "author": r["author"] or "", "title": title,
                         "duration": round(r["duration"] or 0), "kind": "图文" if r["media_type"] == "note" else "视频",
                         "transcript": r["transcript"]})
    todo.sort(key=lambda x: (folders.index(x["folder"]), x["id"]))
    if a.limit:
        todo = todo[: a.limit]
    stamp = time.strftime("%m%d%H%M")
    files = []
    for n in range(0, len(todo), a.size):
        p = WORK / "todo" / f"batch_{stamp}_{n // a.size + 1:03d}.json"
        p.write_text(json.dumps(todo[n:n + a.size], ensure_ascii=False, indent=1), encoding="utf-8")
        files.append(p)
    print(f"待润色 {len(todo)} 条，{len(files)} 批")
    for p in files:
        print(p)


if __name__ == "__main__":
    main()
