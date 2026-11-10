"""等到这个库里「已转成文字、还没润色」的新条目攒够 N 条（默认 100），或者转写队列跑完，然后打印数量退出。
后台跑它，退出时就去做一轮 export → 润色 → build。

用法：python wait_new.py --root D:\\douyin [--n 100] [--max-hours 12]
"""
import argparse, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from export_batches import done_ids  # noqa: E402
from lib import Lib, add_root_arg  # noqa: E402

ACTIVE = ("queued", "fetching", "downloading", "transcribing")


def count(lib):
    rows = lib.items("id, status, transcript")
    seen = done_ids(lib)
    tabs = set(lib.all_tabs())
    new = sum(1 for r in rows if r["status"] in ("need_key", "done") and r["transcript"]
              and lib.folder_of(r["_lp"]) in tabs and r["id"] not in seen)
    active = sum(1 for r in rows if r["status"] in ACTIVE)
    return new, active


def main():
    ap = argparse.ArgumentParser()
    add_root_arg(ap)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--max-hours", type=float, default=12)
    a = ap.parse_args()
    lib = Lib(a.root)
    end = time.time() + a.max_hours * 3600
    while True:
        try:
            new, active = count(lib)
        except Exception:
            time.sleep(60)
            continue
        if new >= a.n or active == 0 or time.time() > end:
            print(f"待润色新条目 {new} 条；转写队列还剩 {active} 条" + ("（已全部转完）" if active == 0 else ""))
            return
        time.sleep(300)


if __name__ == "__main__":
    main()
