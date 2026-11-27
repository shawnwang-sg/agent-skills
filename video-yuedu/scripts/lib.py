"""一个「本地视频收藏库」的配置和公共函数。

库 = 一个根目录，下面是分类子文件夹（抖音收藏夹分类、自己建的主题文件夹……）。
根目录布局：分类文件夹（= tab）、_unsorted/（还没归类的视频和图文，算 inbox「未分类」）、
_output/（集锦 PDF、收藏清单等整理副产物，和阅读页无关，脚本忽略）、_yuedu/、_pending/ 等下划线开头的工作文件夹、yuedu.html。
兼容旧布局：直接散放在根目录的视频 / 图文文件夹也算 inbox。
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

博约阁（转写工具）的数据库里可能同时有好几个库的条目，所以一律按 local_path 是否在根目录下来区分。
"""
import json, os
from pathlib import Path

DEFAULT_APP = r"D:\praxis\praxis-framework\hive-pavilion"
DEFAULT = {
    "title": "",            # 页面标题，空 = 「阅读 · <根目录名>」
    "subtitle": "视频转写稿 · 去口水词、改错字、不改原话",
    "app": DEFAULT_APP,     # 转写用的博约阁（需要有「导入本地文件夹 · 只转文字」功能）
    "app_url": "http://127.0.0.1:8765",
    "tabs": [],             # 顶部 tab = 分类文件夹名，按这个顺序
    "tab_desc": {},         # 每个 tab 的主题一句话，给子任务判断放没放错
    "inbox": "未分类",       # 没进分类文件夹的条目（在 inbox_dir 里，或旧布局直接放根目录）算这个 tab
    "inbox_dir": "_unsorted",  # 未归类条目所在的子文件夹名（在根目录下）
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
        self.inbox_dir = self.root / cfg["inbox_dir"]   # 未归类条目的实际目录（可能还不存在）
        self.out = self.root / cfg["page"]
        self._prefix = os.path.normcase(str(self.root)).rstrip("\\/") + os.sep

    def save(self):
        self.work.mkdir(parents=True, exist_ok=True)
        (self.work / "config.json").write_text(json.dumps(self.cfg, ensure_ascii=False, indent=1), encoding="utf-8")

    def owns(self, p):
        return bool(p) and os.path.normcase(str(p)).startswith(self._prefix)

    def folder_of(self, p):
        """条目所在的 tab：根目录下第一层文件夹名；在 inbox_dir（_unsorted）里的、
        或直接放在根目录的（旧布局）算 inbox；其他下划线开头的文件夹 / exclude 返回 None；不在这个库里返回 None。"""
        if not self.owns(p):
            return None
        parts = Path(str(p)[len(self._prefix):]).parts
        if len(parts) <= 1:
            return self.inbox
        if parts[0] == self.cfg["inbox_dir"]:
            return self.inbox
        return None if parts[0] in self.cfg["exclude"] or parts[0].startswith("_") else parts[0]

    def has_loose(self):
        """旧布局：根目录下是否还有散放的视频 / 图文文件夹（不含 tab、exclude、下划线开头的文件夹）。"""
        VID = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".flv", ".mp3", ".m4a", ".wav"}
        IMGS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        skip = set(self.tabs) | set(self.cfg["exclude"])
        for p in self.root.iterdir():
            if p.name.startswith(("_", ".")) or p.name in skip:
                continue
            if p.is_file() and p.suffix.lower() in VID:
                return True
            if p.is_dir():
                fs = list(p.iterdir())
                if (any(f.suffix.lower() in IMGS for f in fs) or (p / "正文.txt").exists())                         and not any(f.is_dir() or f.suffix.lower() in VID for f in fs):
                    return True
        return False

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
        """博约阁里属于这个库的条目（source='local' 且文件在根目录下）。"""
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
    ap.add_argument("--root", required=True, help=r"库的根目录，如 F:\praxis\praxis-media\hive-pavilion\douyin 或 F:\praxis\praxis-media\hive-pavilion\xiaohongshu")
