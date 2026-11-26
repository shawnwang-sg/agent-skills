"""paper-vault 本地服务：打开潜研堂，保存首页分类树、章节概括和评分，并把划词收藏转给雅言堂。

用法（在 vault 目录里）：python serve.py [--port 8791] [--no-browser] [--coach http://127.0.0.1:5310]
默认只监听 127.0.0.1；vault 里有 lan.local.json（{"enabled": true, "pin": "...."}）时开局域网，别的设备要输密码。零依赖。

接口：
  GET  /api/folders        读首页分类树、收藏、在读
  POST /api/folders        首页分类树、收藏、在读 → folders.json（和 notes.json 一起放在个人 meta 文件夹）
  GET  /api/notes          读全部章节概括
  POST /api/notes          保存一条章节概括（不评分）→ notes.json（默认在 ~/OneDrive/self-meta/paper-vault/，可用环境变量 PAPER_VAULT_META 改）
  POST /api/judge          保存概括并调用本机已登录的 claude CLI 打分（1–10）和点评 → notes.json
  GET  /api/learn?slug=    这篇论文的学习记录（没删的）
  POST /api/learn          选中即学：{slug, mode, section, text, context, again}；有存档且 again 不为真直接返回存档，
                           否则调引擎讲一次、追加一项 → learn.json（和 notes.json 同一个个人 meta 文件夹）
  POST /api/learn/delete   {id}：标记为已删（不真删）
  GET/POST /api/engine     读 / 改「学习」用的引擎（claude、codex）→ vault 里的 engine.local.json（不进 Git）
  GET/POST /api/coach/...  转发给雅言堂（lang-coach）的 /api/collect 系列接口
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# 章节概括是个人数据：默认存进 self-meta 仓库的 paper-vault 文件夹（有的话），否则存在 vault 里
_META = Path(os.environ.get("PAPER_VAULT_META") or Path.home() / "OneDrive" / "self-meta" / "paper-vault")
META_DIR = _META if _META.parent.is_dir() else ROOT     # 个人数据：self-meta/paper-vault（没有 self-meta 时退回 vault 根目录）
NOTES = META_DIR / "notes.json"
FOLDERS = META_DIR / "folders.json"
META_SCHEMA = 1                                          # 个人数据格式版本：notes / folders 结构改了就 +1
_meta_lock = threading.Lock()


def migrate_folders():
    """旧版把 folders.json 放在 vault 根目录（进了程序仓库）：第一次启动时挪到个人 meta 文件夹，旧文件留着不删。"""
    old = ROOT / "folders.json"
    if META_DIR != ROOT and not FOLDERS.exists() and old.exists():
        META_DIR.mkdir(parents=True, exist_ok=True)
        FOLDERS.write_text(old.read_text(encoding="utf-8"), encoding="utf-8")
        print("已把收藏、在读和分类树挪到 %s" % FOLDERS)


def owner_id():
    try:
        return json.loads((META_DIR.parent / "owner.json").read_text(encoding="utf-8")).get("id")
    except Exception:
        return None


def bump_meta():
    """每次写个人数据后更新 meta.json：owner、revision +1、各文件哈希（约定见 self-meta/SPEC.md）。"""
    if META_DIR == ROOT:
        return
    import hashlib as _h
    import socket as _s
    with _meta_lock:
        f = META_DIR / "meta.json"
        try:
            old = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            old = {}
        tables = {}
        for name in ("notes", "folders", "learn"):
            fp = META_DIR / ("%s.json" % name)
            if fp.exists():
                b = fp.read_bytes()
                d = json.loads(b.decode("utf-8"))
                if name == "notes":
                    rows = sum(len(v) for v in d.get("summaries", {}).values())
                elif name == "learn":
                    rows = sum(1 for v in d.get("items", {}).values() if not v.get("deleted"))
                else:
                    rows = len(d.get("favorites", [])) + len(d.get("reading", []))
                tables[name] = {"rows": rows, "hash": "sha256:" + _h.sha256(b).hexdigest()}
        meta = {"format": "paper-vault-meta", "version": 1, "schema": META_SCHEMA, "owner": owner_id() or old.get("owner"),
                "revision": int(old.get("revision") or 0) + 1, "base": int(old.get("revision") or 0),
                "device": _s.gethostname(), "exportedAt": time.strftime("%Y-%m-%dT%H:%M:%S"), "tables": tables}
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, f)


def owner_mismatch():
    """个人 meta 文件夹属于另一个人时拒绝写入（只读还能看）。"""
    try:
        m = json.loads((META_DIR / "meta.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    me = owner_id()
    return bool(m.get("owner") and me and m["owner"] != me)
MAX_BODY = 4 * 1024 * 1024
COACH = "http://127.0.0.1:5310"
COACH_PATHS = ("collect", "collect/ping", "collect/recent")
JUDGE_MODEL = "sonnet"
_notes_lock = threading.Lock()

# ── 局域网访问 ──────────────────────────────────────────────────────────────
# vault 根目录的 lan.local.json：{"enabled": true, "pin": "...."}（不进 Git）。
# 开了以后监听 0.0.0.0；本机直接用，别的设备第一次要输密码，之后记住一年；连错 8 次锁 10 分钟。
LAN_FILE = ROOT / "lan.local.json"
LAN_COOKIE = "pv_pin"
# 离开就锁（设计见 praxis-academy/docs/lock-on-leave.md）：页面调 POST /api/lock 把这台设备标成已锁（cookie pv_locked），
# 已锁的设备连本机也要输密码；别的程序从本机调接口不带这个 cookie，照旧放行。没设密码时不生效。
LOCKED_COOKIE = "pv_locked"   # 不带 Secure：本机纯 http 下也要生效


def locked_cookie(on):
    return "%s=%s; Max-Age=%d; Path=/; HttpOnly; SameSite=Strict" % (LOCKED_COOKIE, "1" if on else "", 31536000 if on else 0)


def load_lan():
    try:
        d = json.loads(LAN_FILE.read_text(encoding="utf-8"))
        return d if d.get("enabled") and str(d.get("pin") or "") else None
    except Exception:
        return None


LAN = load_lan()
LAN_TOKEN = hashlib.sha256(("paper-vault:%s" % LAN["pin"]).encode()).hexdigest() if LAN else None
_fails = {}
LOGIN_PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>潜研堂</title><style>
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f4ece0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;color:#2b2620}
form{background:#fffaf2;border:1px solid #e0d5c4;border-radius:14px;padding:28px 24px;width:min(300px,86vw);text-align:center}
h1{font-size:18px;margin:0 0 6px}.tip{color:#6f6456;font-size:13px;margin:0 0 14px}input::placeholder{font-size:13px;letter-spacing:0}input{width:100%;box-sizing:border-box;font-size:22px;letter-spacing:6px;text-align:center;padding:10px;border:1px solid #e0d5c4;border-radius:10px}
button{margin-top:14px;width:100%;padding:10px;font-size:16px;border:none;border-radius:10px;background:#A62B26;color:#fff}p{color:#A62B26;font-size:14px;min-height:20px;margin:10px 0 0}
</style></head><body><form id="f"><h1>潜研堂 · 输入密码</h1><div class="tip">请输入 8 位密码（含大小写字母和特殊符号）</div><input id="pin" type="password" autocomplete="off" placeholder="8 位：大小写字母 + 特殊符号" autofocus><button>进入</button><p id="msg"></p></form>
<script>try{if(localStorage.getItem('pv_ui')==='en'){document.documentElement.lang='en';document.title='Lyceum Hall';document.querySelector('h1').textContent='Lyceum Hall · Password';document.querySelector('.tip').textContent='Enter your 8-character password (upper and lower case letters and symbols)';document.getElementById('pin').placeholder='8 characters: letters + symbols';document.querySelector('button').textContent='Enter';}}catch(e){}
document.getElementById('f').onsubmit=async(e)=>{e.preventDefault();const r=await fetch('/api/lan-login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin:document.getElementById('pin').value})});
if(r.ok)location.reload();else document.getElementById('msg').textContent=(await r.json().catch(()=>({}))).error||'不对';};</script></body></html>"""


def lan_addresses():
    import socket
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith(("127.", "169.254.")):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


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
    bump_meta()


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


# ── 学习（选中即学）────────────────────────────────────────────────────────
# 提示词和讲解格式在 skill paper-explain（prompts/ 是唯一来源）；规格见 LEARN-SPEC.md。
# 记录存在个人 meta 文件夹的 learn.json：items[id]，id = slug + 规整后文字的哈希；entries 按时间先后追加。
LEARN = META_DIR / "learn.json"
LEARN_MAX = 500          # 选中超过 500 个字符不讲
LEARN_CTX = 900          # 上下文以选中为中心截到约 900 个字符
LEARN_TIMEOUT = 60
PROMPT_DIRS = [ROOT / "plugins" / "paper-vault" / "skills" / "paper-explain" / "prompts",
               Path(__file__).resolve().parent.parent / "paper-explain" / "prompts"]   # vault 里 / skill 仓库里
_learn_lock = threading.Lock()
_busy_lock = threading.Lock()
_busy = {}               # id → Lock：同一段文字同时只跑一个请求


def norm_text(s):
    return re.sub(r"\s+", " ", s or "").strip()


def learn_id(slug, text):
    return "%s:%s" % (slug, hashlib.sha1(norm_text(text).encode("utf-8")).hexdigest()[:16])


def learn_kind(text):
    return "word" if len(norm_text(text).split(" ")) <= 3 else "sentence"


def load_prompt(kind):
    """返回 (系统提示词, 版本号)。"""
    for d in PROMPT_DIRS:
        f = d / ("word.txt" if kind == "word" else "sentence.txt")
        if f.exists():
            try:
                ver = int((d / "version.txt").read_text(encoding="utf-8").strip())
            except Exception:
                ver = 0
            return f.read_text(encoding="utf-8").strip(), ver
    raise RuntimeError("找不到 paper-explain 的提示词（prompts/）")


def clip_context(ctx, text, limit=LEARN_CTX):
    """上下文规整成一行，以选中为中心截到 limit 个字符。"""
    ctx, text = norm_text(ctx), norm_text(text)
    if len(ctx) <= limit:
        return ctx
    i = ctx.find(text)
    if i < 0:
        return ctx[:limit]
    start = max(0, min(i + len(text) // 2 - limit // 2, len(ctx) - limit))
    return ctx[start:start + limit]


def paper_title(slug):
    try:
        return json.loads((ROOT / "papers" / slug / "paper.json").read_text(encoding="utf-8"))["meta"].get("title") or slug
    except Exception:
        return slug


def learn_input(slug, section, context, text):
    """给模型的四行输入，别的不带。"""
    return "论文：%s\n小节：%s\n上下文：%s\n选中：%s" % (
        norm_text(paper_title(slug)), norm_text(section) or "（无）", clip_context(context or text, text), norm_text(text))


# 引擎：engine(system, user, timeout) → {"text", "model", "usage": {"input", "output"}}。加引擎只加一个函数，再登记到 ENGINES。
def engine_claude(system, user, timeout):
    cmd = ["claude", "-p", "--model", "sonnet", "--effort", "low", "--system-prompt", system,
           "--tools", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--setting-sources", "",
           "--disable-slash-commands", "--no-session-persistence", "--output-format", "json"]
    r = subprocess.run(cmd, input=user, capture_output=True, text=True, encoding="utf-8",
                       timeout=timeout, cwd=tempfile.gettempdir())
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout or "claude 调用失败")[-300:])
    d = json.loads(r.stdout)
    if d.get("is_error"):
        raise RuntimeError(str(d.get("result") or "claude 返回错误")[-300:])
    u = d.get("usage") or {}
    models = list((d.get("modelUsage") or {}).keys())
    return {"text": (d.get("result") or "").strip(), "model": models[0] if models else "sonnet",
            "usage": {"input": int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0)
                      + int(u.get("cache_read_input_tokens") or 0),
                      "output": int(u.get("output_tokens") or 0)}}


def engine_codex(system, user, timeout):
    """Codex 命令行（codex exec 非交互）。没有单独的系统提示词参数：提示词和四行输入一起走标准输入。"""
    exe = shutil.which("codex")
    cmd = [exe, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-c", 'model_reasoning_effort="low"', "--json", "-"]
    r = subprocess.run(cmd, input=system + "\n\n" + user, capture_output=True, text=True, encoding="utf-8",
                       timeout=timeout, cwd=tempfile.gettempdir())
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout or "codex 调用失败")[-300:])
    text, usage, model = "", {}, "codex"
    for line in r.stdout.splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        item = ev.get("item") or {}
        if item.get("type") == "agent_message" and item.get("text"):
            text = item["text"]
        if ev.get("usage"):
            usage = ev["usage"]
        model = ev.get("model") or model
    return {"text": text.strip(), "model": model,
            "usage": {"input": int(usage.get("input_tokens") or 0), "output": int(usage.get("output_tokens") or 0)}}


FAKE_CALLS = []          # 假引擎被调用的记录（测试看它判断有没有调模型）


def engine_fake(system, user, timeout):
    """只给测试用：环境变量 PAPER_VAULT_FAKE_ENGINE=1 时才有，界面上不出现。PAPER_VAULT_FAKE_DELAY 可设秒数。"""
    FAKE_CALLS.append(user)
    time.sleep(float(os.environ.get("PAPER_VAULT_FAKE_DELAY") or 0))
    sel = user.rsplit("选中：", 1)[-1][:40]
    n = len(FAKE_CALLS)
    if "五行" in system:
        text = ("是什么：假引擎第 %d 次讲「%s」。\n为什么：测试用。\n在这里：测试用。\n翻译：测试\n搭配：fake engine" % (n, sel))
    else:
        text = ("大意：假引擎第 %d 次讲这句。\n前因：测试用。\n理解：「%s」。\n后果：测试用。\n关键：fake：假的；test：测试\n"
                "翻译：测试。\n句型：无\n这一行没有标签，原样显示。" % (n, sel))
    return {"text": text, "model": "fake", "usage": {"input": len(system + user) // 2, "output": len(text) // 2}}


ENGINES = {"claude": (engine_claude, lambda: bool(shutil.which("claude"))),
           "codex": (engine_codex, lambda: bool(shutil.which("codex"))),
           "fake": (engine_fake, lambda: os.environ.get("PAPER_VAULT_FAKE_ENGINE") == "1")}
HIDDEN_ENGINES = ("fake",)


def engine_file():
    return ROOT / "engine.local.json"


def engine_options():
    """界面上可选的引擎（本机装了的）。"""
    return [k for k, (_, ok) in ENGINES.items() if k not in HIDDEN_ENGINES and ok()]


def current_engine():
    try:
        name = json.loads(engine_file().read_text(encoding="utf-8")).get("engine")
    except Exception:
        name = None
    if name in ENGINES and ENGINES[name][1]():
        return name
    if ENGINES["fake"][1]():         # 打开了假引擎（测试）：没选过就用它，免得误调真模型
        return "fake"
    opts = engine_options()
    return opts[0] if opts else "claude"


def set_engine(name):
    if name not in ENGINES or not ENGINES[name][1]():
        raise ValueError("没有这个引擎：%s" % name)
    f = engine_file()
    tmp = f.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"engine": name}, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, f)


def call_engine(name, system, user):
    """输出为空或命令失败才重试一次；超时不重试。格式不齐照原样返回。"""
    fn = ENGINES[name][0]
    err = None
    for _ in range(2):
        try:
            res = fn(system, user, LEARN_TIMEOUT)
            if res.get("text"):
                return res
            err = RuntimeError("模型没有输出")
        except subprocess.TimeoutExpired:
            raise
        except Exception as e:
            err = e
    raise err


def load_learn():
    try:
        d = json.loads(LEARN.read_text(encoding="utf-8"))
        if isinstance(d.get("items"), dict):
            return d
    except Exception:
        pass
    return {"version": 1, "items": {}}


def public_item(it):
    """给页面看的记录：去掉已删的项。"""
    out = dict(it)
    out["entries"] = [e for e in it.get("entries", []) if not e.get("deleted")]
    return out


def learn_list(slug):
    return [public_item(v) for v in load_learn()["items"].values() if v.get("slug") == slug and not v.get("deleted")]


def learn(slug, mode, section, text, context, again=False, nth=None):
    """返回 (记录, 是否新调了模型, 用量)。nth：选中的是这一小节里这段文字的第几处（从 0 起），下划线画在那一处。"""
    text = norm_text(text)
    lid = learn_id(slug, text)
    with _busy_lock:
        lk = _busy.setdefault(lid, threading.Lock())
    waited = not lk.acquire(blocking=False)
    if waited:                       # 同一段文字已经在讲：等它讲完，直接用它的结果
        lk.acquire()
    try:
        it = load_learn()["items"].get(lid)
        if it and not it.get("deleted") and it.get("entries") and (waited or not again):
            return public_item(it), False, None
        if owner_mismatch():
            raise PermissionError("个人 meta 文件夹属于另一个人，没有写入")
        kind = learn_kind(text)
        system, ver = load_prompt(kind)
        name = current_engine()
        res = call_engine(name, system, learn_input(slug, section, context, text))
        now = time.strftime("%Y-%m-%d %H:%M")
        entry = {"at": now, "engine": name, "model": res.get("model") or name, "prompt": ver,
                 "body": res["text"], "usage": res.get("usage") or {}}
        LEARN.parent.mkdir(parents=True, exist_ok=True)
        with _learn_lock:
            d = load_learn()
            it = d["items"].get(lid)
            if not it:
                it = d["items"][lid] = {"id": lid, "slug": slug, "mode": mode, "section": section, "kind": kind,
                                        "text": text, "entries": [], "created_at": now, "updated_at": now, "deleted": False}
            elif it.get("deleted"):          # 删过又学：旧的几项仍算已删，不再显示
                for e in it.get("entries", []):
                    e["deleted"] = True
                it.update(deleted=False, mode=mode, section=section)
                it.pop("nth", None)          # 位置跟着这次选中重记
            if nth is not None:              # 没带 nth（旧页面、从卡片再讲一次）就不动已有的
                it["nth"] = nth
            it["entries"].append(entry)
            it["updated_at"] = now
            write_json(LEARN, d)
        bump_meta()
        return public_item(it), True, entry["usage"]
    finally:
        lk.release()


def learn_delete(lid):
    with _learn_lock:
        d = load_learn()
        it = d["items"].get(lid)
        if not it:
            return False
        it["deleted"] = True
        it["updated_at"] = time.strftime("%Y-%m-%d %H:%M")
        write_json(LEARN, d)
    bump_meta()
    return True


class Handler(SimpleHTTPRequestHandler):
    coach = COACH

    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def reply(self, code, obj, cookies=()):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        for c in cookies:               # 一个响应发几个 cookie 就调几次，不能合并成一行
            self.send_header("Set-Cookie", c)
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
            return self.reply(e.code, {"error": msg or "雅言堂返回 %d" % e.code})
        except Exception:
            return self.reply(503, {"error": "雅言堂没开（%s）" % self.coach})

    def lan_gate(self):
        """True = 放行；False = 已经回了登录页 / 401 / 429。"""
        ip = self.client_address[0]
        local = ip in ("127.0.0.1", "::1", "::ffff:127.0.0.1")
        cookies = dict(c.strip().split("=", 1) for c in (self.headers.get("Cookie") or "").split(";") if "=" in c)
        locked = bool(LAN) and bool(cookies.get(LOCKED_COOKIE))
        path = self.path.split("?")[0]
        # 离开就锁：GET 问「有没有这个功能、这台设备锁没锁」；POST 锁上（只动发请求的这台设备自己的 cookie，谁都可以调）
        if path == "/api/lock":
            if self.command == "POST" and LAN:
                self.reply(200, {"on": True, "locked": True}, [locked_cookie(True), "%s=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict" % LAN_COOKIE])
            else:
                self.reply(200, {"on": bool(LAN), "locked": locked})
            return False
        if not LAN or (local and not locked):
            return True
        if not locked and cookies.get(LAN_COOKIE) == LAN_TOKEN:
            return True
        if self.command == "POST" and path == "/api/lan-login":
            f = _fails.get(ip, [0, 0])
            if f[1] > time.time():
                self.reply(429, {"error": "错太多次了，10 分钟后再试"}); return False
            try:
                n = int(self.headers.get("Content-Length") or 0)
                got = str(json.loads(self.rfile.read(min(n, 1000)).decode("utf-8")).get("pin", ""))
            except Exception:
                got = ""
            if got == str(LAN["pin"]):
                _fails.pop(ip, None)
                # 局域网设备照旧发密码 cookie；已锁的清掉标记
                out = []
                if not local:
                    out.append("%s=%s; Max-Age=31536000; Path=/; HttpOnly; SameSite=Strict" % (LAN_COOKIE, LAN_TOKEN))
                if locked:
                    out.append(locked_cookie(False))
                self.reply(200, {"ok": True}, out)
                return False
            f[0] += 1
            if f[0] >= 8:
                f = [0, time.time() + 600]
            _fails[ip] = f
            self.reply(401, {"error": "密码不对"}); return False
        if path.startswith("/api/"):
            self.reply(401, {"error": "需要先输入密码"}); return False
        body = LOGIN_PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
        return False

    def do_HEAD(self):
        if self.lan_gate():
            super().do_HEAD()

    def do_GET(self):
        if not self.lan_gate():
            return
        if self.path.startswith("/api/coach/"):
            return self.proxy_coach(self.path[len("/api/coach/"):])
        if self.path.split("?")[0] == "/api/notes":
            return self.reply(200, load_notes())
        if self.path.split("?")[0] == "/api/learn":
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            slug = (q.get("slug") or [""])[0]
            if not re.fullmatch(r"[\w.-]+", slug):
                return self.reply(400, {"error": "bad slug"})
            return self.reply(200, {"items": learn_list(slug)})
        if self.path.split("?")[0] == "/api/engine":
            return self.reply(200, {"engine": current_engine(), "options": engine_options()})
        if self.path.split("?")[0] in ("/api/folders", "/folders.json"):
            try:
                return self.reply(200, json.loads(FOLDERS.read_text(encoding="utf-8")))
            except Exception:
                return self.reply(404, {"error": "还没有 folders.json"})
        return super().do_GET()

    def do_POST(self):
        if not self.lan_gate():
            return
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
            if owner_mismatch():
                return self.reply(409, {"error": "个人 meta 文件夹属于另一个人，没有写入"})
            FOLDERS.parent.mkdir(parents=True, exist_ok=True)
            write_json(FOLDERS, {"version": 1, "favorites": lists["favorites"], "reading": lists["reading"], "tree": data["tree"]})
            bump_meta()
            return self.reply(200, {"ok": True})

        if path == "/api/engine":
            try:
                set_engine(data.get("engine"))
            except ValueError as e:
                return self.reply(400, {"error": str(e)})
            return self.reply(200, {"engine": current_engine(), "options": engine_options()})

        if path == "/api/learn/delete":
            lid = data.get("id")
            if not isinstance(lid, str) or len(lid) > 300:
                return self.reply(400, {"error": "bad id"})
            if owner_mismatch():
                return self.reply(409, {"error": "个人 meta 文件夹属于另一个人，没有写入"})
            return self.reply(200, {"ok": True}) if learn_delete(lid) else self.reply(404, {"error": "没有这条记录"})

        if path == "/api/learn":
            slug, mode, section = data.get("slug"), data.get("mode"), data.get("section") or ""
            text, context = norm_text(data.get("text") if isinstance(data.get("text"), str) else ""), data.get("context") or ""
            if not (isinstance(slug, str) and re.fullmatch(r"[\w.-]+", slug) and (ROOT / "papers" / slug).is_dir()):
                return self.reply(400, {"error": "bad slug"})
            nth = data.get("nth")
            if mode not in ("skim", "grasp", "master") or not isinstance(section, str) or not isinstance(context, str):
                return self.reply(400, {"error": "bad fields"})
            if nth is not None and (not isinstance(nth, int) or isinstance(nth, bool) or not 0 <= nth <= 100000):
                return self.reply(400, {"error": "bad nth"})
            if not text:
                return self.reply(400, {"error": "没有选中文字"})
            if len(text) > LEARN_MAX:
                return self.reply(400, {"error": "选得太长了（超过 %d 个字符），一次讲一个点" % LEARN_MAX})
            try:
                item, fresh, usage = learn(slug, mode, section[:300], text, context[:20000], bool(data.get("again")), nth)
            except PermissionError as e:
                return self.reply(409, {"error": str(e)})
            except subprocess.TimeoutExpired:
                return self.reply(504, {"error": "讲解超时，再试一次"})
            except Exception as e:
                return self.reply(500, {"error": "讲解失败：%s" % e})
            return self.reply(200, {"ok": True, "item": item, "cached": not fresh, "usage": usage})

        if path in ("/api/notes", "/api/judge") and owner_mismatch():
            return self.reply(409, {"error": "个人 meta 文件夹属于另一个人，没有写入"})
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
        # pythonw 启动又没重定向输出时 sys.stderr 是 None：写日志会出错，数据存了页面却收不到回应。没有标准错误就不写。
        if self.command == "POST" and sys.stderr is not None:
            try:
                super().log_message(fmt, *args)
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser(description="paper-vault 本地服务")
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--coach", default=COACH, help="雅言堂的地址（默认 %s）" % COACH)
    a = ap.parse_args()
    Handler.coach = a.coach.rstrip("/")
    srv = ThreadingHTTPServer(("0.0.0.0" if LAN else "127.0.0.1", a.port), Handler)
    url = "http://127.0.0.1:%d/index.html" % a.port
    print("paper-vault: %s  (Ctrl+C 退出)" % url)
    if LAN:
        for ip in lan_addresses():
            print("局域网：http://%s:%d/  （别的设备第一次打开要输密码）" % (ip, a.port))
    migrate_folders()
    print("个人数据（章节概括、学习记录、收藏、在读、分类树）存在：%s" % META_DIR)
    if not a.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
