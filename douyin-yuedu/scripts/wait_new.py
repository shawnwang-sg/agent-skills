"""等到「已转成文字、还没润色」的新条目攒够 N 条（默认 100），或者转写队列全部跑完，然后打印数量退出。
后台跑它，退出时就去做一轮 export → 润色 → build。

用法：python wait_new.py [--n 100] [--folders 厉害,爱好,...] [--max-hours 12]
"""
import argparse, sqlite3, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_batches import APP, ORDER, done_ids, folder_of  # noqa: E402

ACTIVE = ("queued", "fetching", "downloading", "transcribing")


def count(folders):
    c = sqlite3.connect(f"file:{APP / 'data' / 'library.db'}?mode=ro", uri=True, timeout=30)
    rows = c.execute("select id, status, local_path, transcript from items where source='local'").fetchall()
    c.close()
    seen = done_ids()
    new = sum(1 for i, s, p, t in rows if s in ("need_key", "done") and t and folder_of(p) in folders and i not in seen)
    active = sum(1 for i, s, p, t in rows if s in ACTIVE)
    return new, active


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--folders", default=",".join(ORDER))
    ap.add_argument("--max-hours", type=float, default=12)
    a = ap.parse_args()
    folders = a.folders.split(",")
    end = time.time() + a.max_hours * 3600
    while True:
        try:
            new, active = count(folders)
        except Exception:
            time.sleep(60)
            continue
        if new >= a.n or (active == 0) or time.time() > end:
            print(f"待润色新条目 {new} 条；转写队列还剩 {active} 条" + ("（已全部转完）" if active == 0 else ""))
            return
        time.sleep(300)


if __name__ == "__main__":
    main()
