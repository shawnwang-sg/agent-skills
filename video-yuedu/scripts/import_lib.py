"""把库里的分类文件夹（和根目录下没分类的文件）交给学习台「只转文字」：调用学习台的 /api/import_folder。

学习台要先开着（douyin-fav-study：.venv\\Scripts\\python -X utf8 -m app，默认 http://127.0.0.1:8765）。
学习台按文件写入时间顺序加入队列；已经在学习台里的不会重复加；超过设置里时长上限的长视频会跳过、文件留着。
不复制、不移动、不改原文件。

用法：python import_lib.py --root D:\\xiaohongshu [--folders 职场,美食] [--limit 200] [--no-notes]
  --folders 默认 = 所有 tab + 根目录（inbox）；--limit 每个文件夹最多几条（按写入时间最早的几条）。
"""
import argparse, json, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import Lib, add_root_arg  # noqa: E402


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    add_root_arg(ap)
    ap.add_argument("--folders", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-notes", action="store_true")
    a = ap.parse_args()
    lib = Lib(a.root)
    base = lib.cfg["app_url"].rstrip("/")
    names = [f for f in a.folders.split(",") if f] or lib.all_tabs()
    total = 0
    for name in names:
        d = lib.root if name == lib.inbox else lib.root / name
        if not d.is_dir():
            print(f"跳过 {name}：没有这个文件夹")
            continue
        try:
            r = post(f"{base}/api/import_folder", {"path": str(d), "limit": a.limit, "include_notes": not a.no_notes,
                                                   "transcribe_only": True})
        except Exception as e:
            sys.exit(f"连不上学习台 {base}（先把它打开）：{e}")
        if r.get("error"):
            print(f"{name}：{r['error']}")
            continue
        print(f"{name}：共 {r.get('total')} 条，新增 {r.get('added')}，已在学习台 {r.get('existing')}")
        total += r.get("added") or 0
    print(f"新加入转写队列 {total} 条。之后跑 wait_new.py 等攒够 100 条再整理。")


if __name__ == "__main__":
    main()
