"""把阅读版里判为「放错收藏分类」(verdict=move) 的条目，在本地挪到建议的分类文件夹。

用户的想法：抖音线上收藏只是基础云盘，下载到本地后按学习需要灵活整理，不必强行跟线上分类一致。
- 只挪 move_to 是 D:\\douyin 下真实分类文件夹的（厉害/爱好/厉害文字/身体健康/美食）；「其他」不挪。
- 同步更新学习台数据库 items.local_path、data/downloaded.json，并记到 data/relocated.json
  （douyin-fav 的 downloaded_path 会认这个记录，「只下载」同步原收藏夹时不会再复制回去）。
- 每次挪动记一笔到 D:\\douyin\\_yuedu\\moves.json，可用 --undo 全部撤回。

用法：python -X utf8 relocate.py [--dry-run] [--undo]
"""
import argparse, glob, json, shutil, sqlite3, sys
from pathlib import Path

ROOT = Path(r"D:\douyin")
WORK = ROOT / "_yuedu"
APP = Path(r"C:\Users\Shugu\douyin-fav-study")
DB = APP / "data" / "library.db"
DL = APP / "data" / "downloaded.json"
REL = APP / "data" / "relocated.json"
LOG = WORK / "moves.json"
FOLDERS = {"厉害", "爱好", "厉害文字", "身体健康", "美食"}


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
    stem, suf = (dest.name, "") if dest.is_dir() or not dest.suffix else (dest.stem, dest.suffix)
    i = 2
    while (dest.parent / f"{stem} ({i}){suf}").exists():
        i += 1
    return dest.parent / f"{stem} ({i}){suf}"


def apply(moves, db, dl, rel):
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
            paths = [p for p in paths if p != str(src)] + [str(dst)]
            dl[a] = paths
            rel[a] = str(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--undo", action="store_true")
    a = ap.parse_args()
    db = sqlite3.connect(DB, timeout=30)
    dl, rel, log = load(DL, {}), load(REL, {}), load(LOG, [])

    if a.undo:
        back = [{"id": m["id"], "aweme_id": m.get("aweme_id"), "from": m["to"], "to": m["from"]} for m in reversed(log)]
        if not a.dry_run:
            apply(back, db, dl, rel)
            for m in back:
                rel.pop(m.get("aweme_id") or "", None)
            save(DL, dl); save(REL, rel); save(LOG, [])
        print(f"撤回 {len(back)} 条")
        return

    last = {}
    for f in sorted(glob.glob(str(WORK / "done" / "*.json"))):
        for r in json.load(open(f, encoding="utf-8")):
            last[r["id"]] = r
    moves = []
    for i, r in last.items():
        if r.get("verdict") != "move" or r.get("move_to") not in FOLDERS:
            continue
        row = db.execute("select local_path, aweme_id from items where id=?", (i,)).fetchone()
        if not row or not row[0]:
            continue
        src = Path(row[0])
        if src.parent.name == r["move_to"] or not src.exists():
            continue
        dst = unique(ROOT / r["move_to"] / src.name)
        moves.append({"id": i, "aweme_id": row[1], "from": str(src), "to": str(dst), "theme": r.get("theme")})
    for m in moves:
        print(f'#{m["id"]}  {Path(m["from"]).parent.name} → {Path(m["to"]).parent.name}  {Path(m["from"]).name[:50]}')
    if not a.dry_run and moves:
        apply(moves, db, dl, rel)
        save(DL, dl); save(REL, rel); save(LOG, log + moves)
    print(f"{'将' if a.dry_run else '已'}挪动 {len(moves)} 条")


if __name__ == "__main__":
    sys.exit(main())
