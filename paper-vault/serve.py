"""paper-vault 本地服务：打开论文库，保存首页分类树、章节概括和评分，并把划词收藏转给英语教练。

用法（在 vault 目录里）：python serve.py [--port 8791] [--no-browser] [--coach http://127.0.0.1:5310]
只监听 127.0.0.1，零依赖。

接口：
  POST /api/folders        首页分类树、收藏、在读 → folders.json
  GET  /api/notes          读全部章节概括
  POST /api/notes          保存一条章节概括（不评分）→ notes.json（默认在 ~/OneDrive/self-meta/paper-vault/，可用环境变量 PAPER_VAULT_META 改）
  POST /api/judge          保存概括并调用本机已登录的 claude CLI 打分（1–10）和点评 → notes.json
  GET/POST /api/coach/...  转发给英语教练（lang-coach）的 /api/collect 系列接口
"""
import argparse
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FOLDERS = ROOT / "folders.json"
# 章节概括是个人数据：默认存进 self-meta 仓库的 paper-vault 文件夹（有的话），否则存在 vault 里
_META = Path(os.environ.get("PAPER_VAULT_META") or Path.home() / "OneDrive" / "self-meta" / "paper-vault")
NOTES = (_META if _META.parent.is_dir() else ROOT) / "notes.json"
MAX_BODY = 4 * 1024 * 1024
COACH = "http://127.0.0.1:5310"
COACH_PATHS = ("collect", "collect/ping", "collect/recent")
JUDGE_MODEL = "sonnet"
_notes_lock = threading.Lock()


def valid_tree(nodes, depth=0):
    if not isinstance(nodes, list) or depth > 20:
        return False
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not isinstance(n.get("name"), str):
            return False
        if not all(isinstance(s, str) for s in n.get("papers", [])):
            return False
        if not valid_tree(n.get("children", []), depth + 1):
            return False
    return True


def write_json(path, obj):
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if path.exists():
        os.replace(path, path.with_suffix(".json.bak"))
    os.replace(tmp, path)


# ── 章节概括 ────────────────────────────────────────────────────────────────
def load_notes():
    try:
        d = json.loads(NOTES.read_text(encoding="utf-8"))
        if isinstance(d.get("summaries"), dict):
            return d
    except Exception:
        pass
    return {"version": 1, "summaries": {}}


def add_note(slug, key, entry):
    """notes.json：summaries[slug][key] 是这一节每次提交的历史（新的在后）。"""
    NOTES.parent.mkdir(parents=True, exist_ok=True)
    with _notes_lock:
        d = load_notes()
        d["summaries"].setdefault(slug, {}).setdefault(key, []).append(entry)
        write_json(NOTES, d)


def section_text(slug, mode, sec, title):
    """取 paper.json 里这一节的原文和译文，给评分用。按序号取，标题对不上就按标题找。"""
    pj = ROOT / "papers" / slug / "paper.json"
    secs = json.loads(pj.read_text(encoding="utf-8"))["modes"][mode]["sections"]
    norm = lambda s: re.sub(r"\s+", " ", s or "").strip().lower()
    s = secs[sec] if 0 <= sec < len(secs) else None
    if s is None or (title and norm(s.get("title")) != norm(title)):
        s = next((x for x in secs if norm(x.get("title")) == norm(title)), s)
    if s is None:
        raise ValueError("section not found")
    out = []
    for b in s.get("blocks", []):
        t = b.get("type")
        if t in ("p", "quote", "h3"):
            out.append("EN: %s\nZH: %s" % (b.get("en", ""), b.get("zh", "")))
        elif t == "list":
            out += ["- %s / %s" % (i.get("en", ""), i.get("zh", "")) for i in b.get("items", [])]
        elif t == "terms":
            out += ["* %s：%s %s" % (i.get("w", ""), i.get("zh", ""), i.get("m", "")) for i in b.get("items", [])]
        elif t == "figure":
            out.append("[图] %s / %s" % (b.get("caption_en", ""), b.get("caption_zh", "")))
        elif t == "qa":
            out.append("Q: %s\nA: %s" % (b.get("q_zh", ""), b.get("a_zh", "")))
    meta = json.loads(pj.read_text(encoding="utf-8"))["meta"]
    return meta.get("title", slug), s.get("title_zh") or s.get("title", ""), "\n".join(out)[:16000]


JUDGE_PROMPT = """你是严格但友善的论文阅读教练。读者读完论文《{paper}》的一节「{sec}」，写了自己的概括。
请对照这一节的原文和译文，判断概括对不对、全不全，用中文回复，只输出一个 JSON 对象，不要任何别的文字。

评分 1–10：
9–10 抓住了这节的主张、机制和证据，没有错误；7–8 主线对，漏了次要点；5–6 只说到一半，或有小错；
3–4 偏题或有关键错误；1–2 基本没读懂。只复述标题、空泛套话，最多 3 分。

JSON 格式：
{{"score": 整数1到10,
 "verdict": "一句话总评",
 "right": ["说对了的要点"],
 "missed": [{{"point": "漏掉的关键点", "quote": "能支撑它的原文英文句子，逐字摘自下文"}}],
 "wrong": [{{"claim": "读者写的哪句话", "why": "为什么不对或过度推断"}}],
 "reference": "参考概括，中文 2–4 句",
 "english": [{{"original": "读者的英文原句", "better": "更地道的写法", "why": "简短说明"}}]}}
字符串里不要出现英文双引号（引用请用「」），保证是合法 JSON。
english 只在读者用英文写时给出，最多 3 条；否则给空数组。missed 和 wrong 没有就给空数组。

【这一节的内容】
{text}

【读者的概括】
{summary}
"""


def judge(slug, mode, sec, title, summary):
    paper, sec_name, text = section_text(slug, mode, sec, title)
    prompt = JUDGE_PROMPT.format(paper=paper, sec=sec_name, text=text, summary=summary)
    res, err = None, ""
    for _ in range(2):          # 偶尔输出的 JSON 不合法：重来一次
        r = subprocess.run(["claude", "-p", "--model", JUDGE_MODEL, "--tools", "", "--output-format", "text"],
                           input=prompt, capture_output=True, text=True, encoding="utf-8",
                           timeout=240, cwd=tempfile.gettempdir())
        if r.returncode:
            raise RuntimeError((r.stderr or r.stdout or "claude 调用失败")[-400:])
        m = re.search(r"\{.*\}", r.stdout, re.S)
        try:
            res = json.loads(m.group(0))
            break
        except Exception as e:
            err = "%s：%s" % (e, r.stdout[-200:])
    if res is None:
        raise RuntimeError("评分结果不是合法 JSON（" + err + "）")
    res["score"] = max(1, min(10, int(res.get("score") or 1)))
    return res


class Handler(SimpleHTTPRequestHandler):
    coach = COACH

    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def reply(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def same_origin(self):
        # 只接受本页发来的请求（同源），挡住别的网页跨站写入
        origin = self.headers.get("Origin")
        return not origin or origin.split("//", 1)[-1] == self.headers.get("Host")

    def read_json(self):
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            raise ValueError("json only")
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            raise ValueError("bad size")
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def proxy_coach(self, sub, body=None):
        if sub.split("?")[0] not in COACH_PATHS:
            return self.reply(404, {"error": "not found"})
        req = urllib.request.Request(self.coach + "/api/" + sub, data=body, method="POST" if body is not None else "GET",
                                     headers={"Content-Type": "application/json"} if body is not None else {})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return self.reply(r.status, json.loads(r.read().decode("utf-8") or "{}"))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("error")
            except Exception:
                msg = None
            return self.reply(e.code, {"error": msg or "英语教练返回 %d" % e.code})
        except Exception:
            return self.reply(503, {"error": "英语教练没开（%s）" % self.coach})

    def do_GET(self):
        if self.path.startswith("/api/coach/"):
            return self.proxy_coach(self.path[len("/api/coach/"):])
        if self.path.split("?")[0] == "/api/notes":
            return self.reply(200, load_notes())
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        if not self.same_origin():
            return self.reply(403, {"error": "cross-origin"})
        try:
            data = self.read_json()
        except ValueError as e:
            return self.reply(400, {"error": str(e)})
        except Exception:
            return self.reply(400, {"error": "bad json"})
        if not isinstance(data, dict):
            return self.reply(400, {"error": "bad body"})

        if path.startswith("/api/coach/"):
            return self.proxy_coach(path[len("/api/coach/"):], json.dumps(data, ensure_ascii=False).encode("utf-8"))

        if path == "/api/folders":
            if not valid_tree(data.get("tree")):
                return self.reply(400, {"error": "bad tree"})
            lists = {}
            for key in ("favorites", "reading"):
                v = data.get(key, [])
                if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                    return self.reply(400, {"error": "bad " + key})
                lists[key] = v
            write_json(FOLDERS, {"version": 1, "favorites": lists["favorites"], "reading": lists["reading"], "tree": data["tree"]})
            return self.reply(200, {"ok": True})

        if path in ("/api/notes", "/api/judge"):
            slug, mode, text = data.get("slug"), data.get("mode"), (data.get("text") or "").strip()
            sec, title = data.get("sec"), data.get("title") or ""
            if not (isinstance(slug, str) and re.fullmatch(r"[\w.-]+", slug) and (ROOT / "papers" / slug).is_dir()):
                return self.reply(400, {"error": "bad slug"})
            if mode not in ("skim", "grasp", "master") or not isinstance(sec, int) or not text or len(text) > 6000:
                return self.reply(400, {"error": "bad fields"})
            entry = {"text": text, "title": title, "at": time.strftime("%Y-%m-%d %H:%M")}
            if path == "/api/judge":
                try:
                    entry["result"] = judge(slug, mode, sec, title, text)
                except subprocess.TimeoutExpired:
                    return self.reply(504, {"error": "评分超时，再试一次"})
                except Exception as e:
                    return self.reply(500, {"error": "评分失败：%s" % e})
            add_note(slug, "%s:%d" % (mode, sec), entry)
            return self.reply(200, {"ok": True, "entry": entry})

        return self.reply(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        if self.command == "POST":
            super().log_message(fmt, *args)


def main():
    ap = argparse.ArgumentParser(description="paper-vault 本地服务")
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--coach", default=COACH, help="英语教练的地址（默认 %s）" % COACH)
    a = ap.parse_args()
    Handler.coach = a.coach.rstrip("/")
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = "http://127.0.0.1:%d/index.html" % a.port
    print("paper-vault: %s  (Ctrl+C 退出)" % url)
    print("章节概括存在：%s" % NOTES)
    if not a.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
