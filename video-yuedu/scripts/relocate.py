"""按润色结果在本地重新归类：把文件挪到它该在的分类文件夹。

用户的想法：线上收藏夹只是基础云盘，下载到本地后按学习需要灵活整理，不必和线上分类一致。
挪哪些：
- verdict=move 且 move_to 是这个库的 tab（config 的 tabs）；move_to 不是 tab（如「其他」）的不挪，留在待处理清单。
- verdict=keep 且带 tab 字段、但文件还不在那个 tab 文件夹里（平铺的库：润色时顺便定 tab，再挪进去）。
同步修改：学习台数据库 items.local_path；学习台 data/downloaded.json 里的旧路径；data/relocated.json 记新位置
（douyin-fav-study 的 downloaded_path 认这个记录，同步收藏夹时不会把文件再复制回原分类）。
每笔挪动记到 <库>/_yuedu/moves.json，--undo 全部撤回。目标里已有同名文件时加「 (2)」，不覆盖。

用法：python relocate.py --root D:\\douyin [--dry-run] [--export] [--undo]
  --export：把挪过的 move 条目按新分类导出成 todo/batch_reclass_*.json，交给子任务按新分类重新整理（默认 keep）。
"""
import argparse, json, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import Lib, add_root_arg  # noqa: E402


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def save(p, data):
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def unique(dest):
    if not dest.exists():
        return dest
    stem, suf = (dest.name, "") if not dest.suffix else (dest.stem, dest.suffix)
    i = 2
    while (dest.parent / f"{stem} ({i}){suf}").exists():
        i += 1
    return dest.parent / f"{stem} ({i}){suf}"


def apply(moves, lib, dl, rel):
    db = lib.connect(ro=False)
    for m in moves:
        src, dst = Path(m["from"]), Path(m["to"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        db.execute("update items set local_path=? where id=?", (str(dst), m["id"]))
        db.commit()
        a = m.get("aweme_id")
        if a:
            v = dl.get(a)
            paths = [v] if isinstance(v, str) else list(v or [])
            dl[a] = [p for p in paths if p != str(src)] + [str(dst)]
            rel[a] = str(dst)
    db.close()


def main():
    ap = argparse.ArgumentParser()
    add_root_arg(ap)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--export", action="store_true")
    a = ap.parse_args()
    lib = Lib(a.root)
    DL, REL, LOG = lib.app / "data" / "downloaded.json", lib.app / "data" / "relocated.json", lib.work / "moves.json"
    dl, rel, log = load(DL, {}), load(REL, {}), load(LOG, [])

    if a.undo:
        back = [{"id": m["id"], "aweme_id": m.get("aweme_id"), "from": m["to"], "to": m["from"]} for m in reversed(log)]
        if not a.dry_run and back:
            apply(back, lib, dl, rel)
            for m in back:
                rel.pop(m.get("aweme_id") or "", None)
            save(DL, dl); save(REL, rel); save(LOG, [])
        print(f"撤回 {len(back)} 条")
        return

    meta = {r["id"]: r for r in lib.items("id, local_path, aweme_id")}
    moves = []
    for i, r in lib.done_results().items():
        if r.get("verdict") == "move":
            target = r.get("move_to")
        elif r.get("verdict") == "keep":
            target = r.get("tab")
        else:
            continue
        if target not in lib.tabs or i not in meta:
            continue
        src = Path(meta[i]["local_path"])
        if lib.folder_of(src) == target or not src.exists():
            continue
        dst = unique(lib.root / target / src.name)
        moves.append({"id": i, "aweme_id": meta[i].get("aweme_id"), "from": str(src), "to": str(dst),
                      "verdict": r.get("verdict"), "theme": r.get("theme")})
    for m in moves:
        print(f'#{m["id"]}  {lib.folder_of(m["from"])} → {Path(m["to"]).parent.name}  {Path(m["from"]).name[:50]}')
    if not a.dry_run and moves:
        apply(moves, lib, dl, rel)
        if DL.exists() or dl:
            save(DL, dl)
        save(REL, rel)
        save(LOG, log + moves)
    print(f"{'将' if a.dry_run else '已'}挪动 {len(moves)} 条")
    redo = [m["id"] for m in moves if m["verdict"] == "move"]
    if a.export and redo and not a.dry_run:
        from export_batches import item_json, write_batches
        rows = {r["id"]: r for r in lib.items("id, author, title, duration, media_type, transcript, local_path")}
        files = write_batches(lib, [item_json(lib, rows[i]) for i in redo if i in rows], 30, "batch_reclass")
        print("按新分类重新整理：", *files, sep="\n")


if __name__ == "__main__":
    main()
