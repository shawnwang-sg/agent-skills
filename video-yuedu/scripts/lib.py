"""一个「本地视频收藏库」的配置和公共函数。

库 = 一个根目录，下面是分类子文件夹（抖音收藏夹分类、自己建的主题文件夹……）或直接平铺的视频文件。
每个视频是「作者 - 标题.mp4」，每条图文是「作者 - 标题」文件夹（图片 + 正文.txt）。
工作目录 <根目录>/_yuedu/ 放配置和润色过程文件：

  config.json        库的配置（见 DEFAULT 和 init_lib.py）
  rules.md           这个库特有的判定规则（给子任务看，可选）
  categories.json    每个 tab 的「大类 → 建议小主题」：{tab: {大类: [小主题, ...]}}
  topic_list_<tab>.txt  由 topic_list.py 生成，给子任务选分类用
  topics.json        小主题合并表 {大类: {原小主题: 合并后}}
  corrections.json   用户亲自指出的错字 {id: [[原文, 改成], ...]}
  todo/ done/        待处理批次、润色结果
  moves.json         本地挪动记录（relocate.py）

学习台（转写工具）的数据库里可能同时有好几个库的条目，所以一律按 local_path 是否在根目录下来区分。
"""
import json, os
from pathlib import Path

DEFAULT_APP = r"C:\Users\Shugu\douyin-fav-study"
DEFAULT = {
    "title": "",            # 页面标题，空 = 「阅读 · <根目录名>」
    "subtitle": "视频转写稿 · 去口水词、改错字、不改原话",
    "app": DEFAULT_APP,     # 转写用的学习台（需要有「导入本地文件夹 · 只转文字」功能）
    "app_url": "http://127.0.0.1:8765",
    "tabs": [],             # 顶部 tab = 分类文件夹名，按这个顺序
    "tab_desc": {},         # 每个 tab 的主题一句话，给子任务判断放没放错
    "inbox": "未分类",       # 直接放在根目录下（没进分类文件夹）的条目算这个 tab
    "link_label": "原链接",  # 本地文件不在时退回线上链接的文字
    "page": "yuedu.html",   # 生成的阅读页文件名（放在根目录，才能用相对路径播本地视频）
    "exclude": [],          # 不当 tab、也不处理的子文件夹（如「超15分钟长视频」）
}


class Lib:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.work = self.root / "_yuedu"
        f = self.work / "config.json"
        cfg = dict(DEFAULT)
        if f.exists():
            cfg.update(json.loads(f.read_text(encoding="utf-8")))
        self.cfg = cfg
        self.title = cfg["title"] or f"阅读 · {self.root.name}"
        self.app = Path(cfg["app"])
        self.db = self.app / "data" / "library.db"
        self.tabs = list(cfg["tabs"])
        self.inbox = cfg["inbox"]
        self.out = self.root / cfg["page"]
        self._prefix = os.path.normcase(str(self.root)).rstrip("\\/") + os.sep

    def save(self):
        self.work.mkdir(parents=True, exist_ok=True)
        (self.work / "config.json").write_text(json.dumps(self.cfg, ensure_ascii=False, indent=1), encoding="utf-8")

    def owns(self, p):
        return bool(p) and os.path.normcase(str(p)).startswith(self._prefix)

    def folder_of(self, p):
        """条目所在的 tab：根目录下第一层文件夹名；直接放在根目录的算 inbox；不在这个库里返回 None。"""
        if not self.owns(p):
            return None
        parts = Path(str(p)[len(self._prefix):]).parts
        if len(parts) <= 1:
            return self.inbox
        return None if parts[0] in self.cfg["exclude"] or parts[0].startswith("_") else parts[0]

    def all_tabs(self):
        return self.tabs + ([self.inbox] if self.inbox not in self.tabs else [])

    def connect(self, ro=True):
        import sqlite3
        if ro:
            c = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True, timeout=30)
        else:
            c = sqlite3.connect(self.db, timeout=30)
        c.row_factory = sqlite3.Row
        return c

    def items(self, cols="*", where="1=1"):
        """学习台里属于这个库的条目（source='local' 且文件在根目录下）。"""
        c = self.connect()
        rows = [dict(r) for r in c.execute(f"select {cols}, local_path as _lp from items where source='local' and {where}")
                if self.owns(r["_lp"])]
        c.close()
        return rows

    def done_results(self):
        """done/ 里所有结果，文件名排后的覆盖前面同 id 的。"""
        res = {}
        for f in sorted((self.work / "done").glob("*.json")):
            for x in json.loads(f.read_text(encoding="utf-8")):
                res[int(x["id"])] = x
        return res


def add_root_arg(ap):
    ap.add_argument("--root", required=True, help=r"库的根目录，如 D:\douyin 或 D:\xiaohongshu")
