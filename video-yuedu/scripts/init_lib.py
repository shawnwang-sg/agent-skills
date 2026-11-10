"""建一个新库（或查看已有库）的配置：<根目录>/_yuedu/config.json，并按分类文件夹抽样标题，方便定 tab 和大类。

用法：
  python init_lib.py --root D:\\xiaohongshu --title "阅读 · 小红书收藏" [--tabs 职场,AI,美食] [--link-label 小红书原链接]
                     [--app C:\\Users\\Shugu\\douyin-fav-study] [--app-url http://127.0.0.1:8765] [--sample 40]
不给 --tabs 时：用根目录下「直接含视频文件」的子文件夹当 tab（图文笔记文件夹、_ 开头的、exclude 里的不算）。
平铺的库（视频都直接放在根目录）没有分类文件夹：先看抽样标题，再用 --tabs 定几个 tab，润色时给每条定 tab，
relocate.py 会把文件挪进对应的子文件夹。已有 config 时只更新给出的参数。
"""
import argparse, collections, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import Lib, add_root_arg  # noqa: E402

VIDEO = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".flv", ".mp3", ".m4a", ".wav"}
IMG = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def is_note_dir(d):
    """图文笔记文件夹：有图片或 正文.txt，自己没有视频、没有子文件夹。"""
    fs = list(d.iterdir())
    return (any(f.suffix.lower() in IMG for f in fs) or (d / "正文.txt").exists()) \
        and not any(f.is_dir() or f.suffix.lower() in VIDEO for f in fs)


def scan(root):
    """{文件夹名: [条目名...]}，根目录下直接放的算 ""。"""
    out = collections.defaultdict(list)
    for p in root.iterdir():
        if p.name.startswith(("_", ".")):
            continue
        if p.is_file() and p.suffix.lower() in VIDEO:
            out[""].append(p.stem)
        elif p.is_dir() and is_note_dir(p):
            out[""].append(p.name)
        elif p.is_dir():
            for q in p.iterdir():
                if (q.is_file() and q.suffix.lower() in VIDEO) or (q.is_dir() and is_note_dir(q)):
                    out[p.name].append(q.stem if q.is_file() else q.name)
    return out


def main():
    ap = argparse.ArgumentParser()
    add_root_arg(ap)
    ap.add_argument("--title")
    ap.add_argument("--tabs")
    ap.add_argument("--link-label")
    ap.add_argument("--app")
    ap.add_argument("--app-url")
    ap.add_argument("--inbox")
    ap.add_argument("--exclude")
    ap.add_argument("--sample", type=int, default=40)
    a = ap.parse_args()
    lib = Lib(a.root)
    found = scan(lib.root)
    for k, v in (("title", a.title), ("link_label", a.link_label), ("app", a.app), ("app_url", a.app_url), ("inbox", a.inbox)):
        if v:
            lib.cfg[k] = v
    if a.exclude:
        lib.cfg["exclude"] = [x for x in a.exclude.split(",") if x]
    if a.tabs:
        lib.cfg["tabs"] = [x for x in a.tabs.split(",") if x]
    elif not lib.cfg["tabs"]:
        lib.cfg["tabs"] = [k for k in sorted(found, key=lambda k: -len(found[k])) if k and k not in lib.cfg["exclude"]]
    lib.save()
    lib = Lib(a.root)
    print(f"配置：{lib.work / 'config.json'}")
    print(f"标题：{lib.title}；学习台：{lib.app}；tabs：{lib.tabs or '（还没定）'}；根目录下未分类的算「{lib.inbox}」")
    random.seed(1)
    for k in sorted(found, key=lambda k: -len(found[k])):
        name = k or f"（根目录，算「{lib.inbox}」）"
        print(f"\n== {name}  {len(found[k])} 条" + ("  [exclude]" if k in lib.cfg["exclude"] else ""))
        for t in random.sample(found[k], min(a.sample, len(found[k]))):
            print("  ", t[:50])


if __name__ == "__main__":
    main()
