"""把一个库 done/ 里所有润色结果生成阅读页（默认 <库根目录>/yuedu.html）。

结构：顶部 tab = 分类文件夹（config.json 的 tabs），tab 里按「大类 → 小主题」分组，左侧导航、搜索、
连播 / 洗牌连播；另有「待处理清单」tab：没信息量的（含学习台里因无对白跳过的）、疑似归错分类的；
「质检」tab：改动比例和存疑统计。
用法：python build_yuedu.py --root D:\\douyin [--out 另存路径]
子任务自检改动比例时只 import change_pct，不需要 --root。
"""
import argparse, collections, difflib, html, json, re, sys, time, urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib import Lib, add_root_arg  # noqa: E402


class _Punct:
    """去掉所有空白、标点和符号（Unicode 类别 P*/S*/Z*），只留文字和数字来比对。"""
    import unicodedata as _u

    def sub(self, _repl, s):
        return "".join(ch for ch in s if not ch.isspace() and self._u.category(ch)[0] not in "PSZ")


PUNCT = _Punct()
LIMIT = 15  # 改动上限（%），用户定的
CN_NUM = "一二三四五六七八九十"


def norm(s):
    s = s.replace("[?]", "").replace("（原视频到此结束）", "")
    # 菜谱的「## 食材」整节是从后文摘出的清单（排版），不算改动；其他结构小标题也不算
    s = re.sub(r"(?ms)^## (食材|用料|配料|调料)\s*$.*?(?=^## |\Z)", "", s)
    s = re.sub(r"(?m)^## (做法|步骤|准备)\s*$", "", s)
    s = re.sub(r"(?m)^## ", "", s)  # 其他小标题只去符号，文字参与比对（多半是原话里的词）
    s = re.sub(r"(?m)^\d+\. ", "", s)
    s = re.sub(r"(?m)^> [^：:]{1,6}[：:]", "", s)
    return PUNCT.sub("", s)


def change_pct(raw, body):
    """视频转写稿和阅读稿的逐字差异比例。图文（识别图片文字后合并重排）不适合这样比，返回 None。"""
    if "【正文】" in raw or "【图1】" in raw:
        return None
    try:  # 有的转写是繁体，转成简体再比，繁转简不算改动
        import zhconv
        raw = zhconv.convert(raw, "zh-cn")
    except ImportError:
        pass
    a = PUNCT.sub("", raw)
    b = norm(body)
    if not a:
        return 0.0
    chg = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op != "equal":
            chg += max(i2 - i1, j2 - j1)
    return chg / len(a) * 100


def inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s.replace("[?]", "<mark title='听不清，按上下文推测'>[?]</mark>")


def render(body):
    out, lst, quote = [], None, []

    def flush():
        nonlocal lst, quote
        if lst:
            out.append(f"<{lst[0]}>" + "".join(f"<li>{inline(x)}</li>" for x in lst[1]) + f"</{lst[0]}>")
            lst = None
        if quote:
            out.append("<blockquote>" + "".join(f"<p>{x}</p>" for x in quote) + "</blockquote>")
            quote = []

    for line in body.split("\n"):
        if not line.strip():
            flush(); continue
        m = re.match(r"^(\d+)\. (.*)", line)
        if m or line.startswith("- "):
            tag = "ol" if m else "ul"
            if lst and lst[0] != tag:
                flush()
            if quote:
                flush()
            lst = lst or (tag, [])
            lst[1].append(m.group(2) if m else line[2:]); continue
        if line.startswith("> "):
            if lst:
                flush()
            t = line[2:]
            sp = re.match(r"^([^：:]{1,6})[：:](.*)", t)
            if sp and len(sp.group(1)) <= 4 and not re.search(r"[，。]", sp.group(1)):
                quote.append(f"<span class=who>{html.escape(sp.group(1))}</span>{inline(sp.group(2))}")
            else:
                quote.append(inline(t))
            continue
        flush()
        out.append(f"<h4>{inline(line[3:])}</h4>" if line.startswith("## ") else f"<p>{inline(line)}</p>")
    flush()
    return "".join(out)


def cat_key(c):
    m = re.match(r"^([一二三四五六七八九十]+)、", c or "")
    if m:
        s = m.group(1)
        n = 10 + (CN_NUM.index(s[1]) + 1 if len(s) > 1 else 0) if s.startswith("十") else CN_NUM.index(s[0]) + 1
        return (0, n, c)
    return (1, 0, c or "未分类")


LIB = None  # 当前库（main 里设置）


def main():
    global LIB
    ap = argparse.ArgumentParser()
    add_root_arg(ap)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    LIB = lib = Lib(a.root)
    WORK = lib.work
    folder_of = lib.folder_of
    res = lib.done_results()
    meta = {r["id"]: r for r in lib.items("id, author, title, url, local_path, transcript, duration, status, reason, media_type")}
    res = {i: x for i, x in res.items() if i in meta}  # 只要这个库的条目

    tmap = {}
    if (WORK / "topics.json").exists():  # 小主题合并表：{大类: {原小主题: 合并后}}
        tmap = json.loads((WORK / "topics.json").read_text(encoding="utf-8"))
    fixes = {}
    if (WORK / "corrections.json").exists():  # 用户确认过的字词校正：{id: [[原文, 改成], ...]}
        fixes = {k: v for k, v in json.loads((WORK / "corrections.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
    for x in res.values():
        for a_, b_ in fixes.get(str(x["id"]), []):
            for k in ("theme", "gold", "body"):
                if x.get(k):
                    x[k] = x[k].replace(a_, b_)
        if fixes.get(str(x["id"])) and x.get("body") is not None:
            x["unsure"] = x["body"].count("[?]")
        if x.get("verdict") == "keep":
            x["topic"] = tmap.get(x.get("category"), {}).get(x.get("topic"), x.get("topic"))
    keep = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    low, move, qc = [], [], []
    for i, x in res.items():
        m = meta.get(i, {})
        folder = folder_of(m.get("local_path"))
        if x.get("verdict") == "keep" and x.get("tab") in lib.tabs:  # 平铺库：润色时定的 tab（还没挪进文件夹也先归过去）
            folder = x["tab"]
        x["_folder"], x["_author"], x["_url"] = folder, m.get("author") or "", m.get("url") or ""
        x["_path"] = m.get("local_path") or ""
        if x.get("verdict") == "keep":
            keep[folder][x.get("category") or "未分类"][x.get("topic") or "其他"].append(x)
            pct = change_pct(m.get("transcript") or "", x.get("body") or "")
            x["_pct"] = pct
            qc.append(x)
        elif x.get("verdict") == "move":
            move.append(x)
        else:
            low.append(x)
    # 学习台里因为「几乎没有说话内容」而跳过的，也算没信息量（画面为主或纯音乐）
    for i, m in meta.items():
        if m["status"] == "skipped" and i not in res and "说话内容" in (m.get("reason") or "") and folder_of(m["local_path"]) in lib.all_tabs():
            low.append({"id": i, "verdict": "low_info", "low_info_type": "画面为主", "reason": "转写时几乎没听到说话（画面、字幕或纯音乐为主）",
                        "theme": re.sub(r"#\S+", "", m.get("title") or "").strip()[:40], "_folder": folder_of(m["local_path"]),
                        "_author": m.get("author") or "", "_url": m.get("url") or "", "_path": m.get("local_path") or ""})

    css = CSS
    P = ["<!doctype html><html lang=zh><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
         f"<title>{html.escape(lib.title)}</title><style>{css}</style><body><main>",
         f"<header><h1>{html.escape(lib.title)}</h1>",
         f"<p class=sub>{html.escape(lib.cfg['subtitle'])} · 共 {len(qc)} 篇 · 更新于 {time.strftime('%Y-%m-%d %H:%M')}</p>",
         "<input id=q type=search placeholder='搜索标题、金句、作者……' autocomplete=off></header><nav class=tabs>"]
    order = lib.all_tabs() if keep.get(lib.inbox) else lib.tabs
    tabs = [f for f in order if keep.get(f)] + [f for f in order if not keep.get(f)]
    for n, f in enumerate(tabs):
        cnt = sum(len(v) for t in keep.get(f, {}).values() for v in t.values())
        P.append(f"<button data-tab='t{n}' class='{'on' if n == 0 else ''}'>{f}<span>{cnt or '待整理'}</span></button>")
    P.append(f"<button data-tab=tlow>待处理清单<span>{len(low) + len(move)}</span></button><button data-tab=tqc>质检</button></nav>")

    for n, f in enumerate(tabs):
        cats = keep.get(f, {})
        P.append(f"<section id=t{n} class='tab{' on' if n == 0 else ''}'>")
        if not cats:
            P.append("<p class=empty>这个分类还没转写完，转好后每满 100 条会整理进来。</p></section>")
            continue
        # 左侧固定导航：大类 → 小主题
        P.append("<div class=layout><aside class=side><div class=side-in>")
        for cat in sorted(cats, key=cat_key):
            topics = cats[cat]
            total = sum(len(v) for v in topics.values())
            P.append(f"<div class=tc><a href='#{f}-{html.escape(cat)}' class=tcat>{html.escape(cat)}<span>{total}</span></a><div class=ttop>")
            for t in sorted(topics, key=lambda t: -len(topics[t])):
                P.append(f"<a href='#{f}-{html.escape(cat)}-{html.escape(t)}'>{html.escape(t)}<span>{len(topics[t])}</span></a>")
            P.append("</div></div>")
        P.append(f"</div></aside><div class=content><div class=tabplay>「{html.escape(f)}」全部{PLAYBTN}<label class=wi><input type=checkbox class=withimg checked> 连播带图文</label></div>")
        for cat in sorted(cats, key=cat_key):
            topics = cats[cat]
            P.append(f"<h2 id='{f}-{html.escape(cat)}'>{html.escape(cat)}{PLAYBTN}</h2>")
            for t in sorted(topics, key=lambda t: -len(topics[t])):
                P.append(f"<h3 id='{f}-{html.escape(cat)}-{html.escape(t)}'>{html.escape(t)}{PLAYBTN}</h3>")
                for x in sorted(topics[t], key=lambda x: x["id"]):
                    src = html.escape(x["_author"] or "佚名")
                    link = media_link(x, " · ")
                    P.append(f"<article data-s='{html.escape((x.get('theme', '') + x.get('gold', '') + x['_author']).lower())}'>"
                             f"<h5>{inline(x.get('theme', ''))}</h5><div class=src>—— {src}{link}</div>"
                             f"<div class=gold>{inline(x.get('gold', ''))}</div><div class=body>{render(x.get('body', ''))}</div></article>")
        P.append("</div></div></section>")

    # 待处理清单
    P.append("<section id=tlow class=tab><h2>文字没有信息量的</h2><p class=note>这些不进阅读版。原文件都还在，需要的话可以回原视频看画面。</p>")
    by = collections.defaultdict(list)
    for x in low:
        by[x.get("low_info_type") or "其他"].append(x)
    for t in ["画面为主", "断续口播", "纯音乐歌词", "残缺", "其他"]:
        if by.get(t):
            P.append(f"<h3>{t}<span class=cnt>{len(by[t])}</span></h3><table>")
            for x in sorted(by[t], key=lambda x: (x["_folder"], x["id"])):
                P.append(row(x))
            P.append("</table>")
    P.append("<h2>疑似放错分类的</h2><p class=note>建议移到的是本库的分类时，会在本地挪过去再整理进阅读版；"
             "建议移到「其他」等本库没有的分类，就只列在这里，不收进阅读版。</p>")
    bym = collections.defaultdict(list)
    for x in move:
        bym[x.get("move_to") or "其他"].append(x)
    for t in sorted(bym):
        P.append(f"<h3>建议移到「{html.escape(t)}」<span class=cnt>{len(bym[t])}</span></h3><table>")
        for x in sorted(bym[t], key=lambda x: x["id"]):
            P.append(row(x))
        P.append("</table>")
    P.append("</section>")

    # 质检
    vids = [x for x in qc if x["_pct"] is not None]
    over = sorted([x for x in vids if x["_pct"] > LIMIT], key=lambda x: -x["_pct"])
    pcts = sorted(x["_pct"] for x in vids)
    avg = pcts[len(pcts) // 2] if pcts else 0  # 中位数，不受个别乱码长稿影响
    uns = sum(int(x.get("unsure") or 0) for x in qc)
    P.append(f"<section id=tqc class=tab><h2>质检</h2><p class=note>改动比例 = 去掉标点和排版标记后，和原始转写逐字比对的差异。"
             f"超过 15% 的多半是转写错字多（改错字也算改动）。图文是识别图片文字后合并重排，不参与统计。</p><ul class=stat><li>阅读版 {len(qc)} 篇（视频 {len(vids)}）</li>"
             f"<li>改动中位数 {avg:.1f}%</li><li>超过 15% 的 {len(over)} 篇</li><li>存疑 [?] 共 {uns} 处</li></ul>"
             "<h3>改动超过 15% 的</h3><table>")
    for x in over:
        P.append(f"<tr><td>#{x['id']}</td><td>{html.escape(x.get('theme', ''))}</td><td>{html.escape(x['_author'])}</td><td>{x['_pct']:.0f}%</td>"
                 f"<td>{html.escape(x.get('note') or '')}</td></tr>")
    P.append("</table></section></main>" + JS)
    out = Path(a.out) if a.out else lib.out
    out.write_text("".join(P), encoding="utf-8")
    print(f"{out}  阅读 {len(qc)} 篇 · 没信息量 {len(low)} · 疑似分错 {len(move)} · 视频改动中位数 {avg:.1f}% · 超 15% {len(over)}/{len(vids)} 篇")


IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
def media_link(x, prefix=""):
    """「原视频」：点开在页面里弹窗播放本地视频；图文弹出本地图片。本地文件找不到时退回线上链接。
    阅读页放在库根目录，本地文件用相对路径引用（所以页面不能单独挪走）。"""
    p = Path(x.get("_path") or "")
    if p.exists():
        try:
            rel = p.relative_to(LIB.out.parent).as_posix()
        except ValueError:
            rel = p.as_uri()
        q = urllib.parse.quote
        if p.is_dir():
            imgs = sorted(f.name for f in p.iterdir() if f.suffix.lower() in IMG_EXT)
            if imgs:
                srcs = json.dumps([q(f"{rel}/{n}") for n in imgs])
                return f"{prefix}<a href='#' class=play data-imgs='{html.escape(srcs)}'>原图文</a>"
        else:
            return f"{prefix}<a href='#' class=play data-video='{html.escape(q(rel))}'>原视频</a>"
    if x.get("_url"):
        return f"{prefix}<a href='{html.escape(x['_url'])}' target=_blank rel=noopener>{html.escape(LIB.cfg['link_label'])}</a>"
    return ""


def row(x):
    link = media_link(x)
    return (f"<tr><td>#{x['id']}</td><td>{html.escape(x.get('_folder', ''))}</td><td>{html.escape(x.get('theme') or '')}</td>"
            f"<td>{html.escape(x.get('_author', ''))}</td><td>{html.escape(x.get('reason') or '')}</td><td>{link}</td></tr>")


CSS = """
:root{--bg:#f7f4ee;--fg:#24211c;--mut:#7a7368;--card:#fffdf9;--line:#e6dfd3;--acc:#9a5b2a;--q:#f1ebe0;--on:#24211c;--onfg:#fffdf9}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#181614;--fg:#ebe6dd;--mut:#a69f94;--card:#211e1b;--line:#38332d;--acc:#e0a46b;--q:#2a2622;--on:#ebe6dd;--onfg:#181614}}
:root[data-theme=dark]{--bg:#181614;--fg:#ebe6dd;--mut:#a69f94;--card:#211e1b;--line:#38332d;--acc:#e0a46b;--q:#2a2622;--on:#ebe6dd;--onfg:#181614}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:18px/1.95 "Noto Serif SC","Source Han Serif SC","Songti SC","SimSun",serif}
main{max-width:1680px;margin:0 auto;padding:28px 32px 100px}a{color:var(--acc)}
header{max-width:none}#q{max-width:560px}
.layout{display:grid;grid-template-columns:270px minmax(0,1fr);gap:40px;align-items:start}
.side{position:sticky;top:64px;max-height:calc(100vh - 76px);overflow-y:auto;padding:14px 4px 30px 0;font-size:15px;line-height:1.7;border-right:1px solid var(--line)}
.side .tc{padding:8px 10px 8px 0;border-bottom:1px dashed var(--line)}.side .tc:last-child{border:0}
.side .tcat{display:block;font-weight:600;color:var(--fg);text-decoration:none}.side .tcat:hover,.side .ttop a:hover{color:var(--acc)}
.side .ttop{display:block;margin:2px 0 0 12px}.side .ttop a{display:block;color:var(--mut);text-decoration:none;padding:1px 0}
.side span{color:var(--mut);font-size:12px;margin-left:6px;font-weight:400}
.content h2:first-child{margin-top:8px}h2,h3{scroll-margin-top:70px}
header h1{font-size:30px;letter-spacing:.06em;margin:0}.sub{color:var(--mut);font-size:14px;margin:4px 0 14px}
#q{width:100%;padding:9px 14px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--fg);font:inherit;font-size:15px}
.tabs{position:sticky;top:0;z-index:5;background:var(--bg);display:flex;gap:6px;overflow-x:auto;padding:12px 0;margin:8px 0 6px;border-bottom:1px solid var(--line)}
.tabs button{flex:none;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:999px;padding:5px 14px;font:inherit;font-size:15px;cursor:pointer}
.tabs button span{margin-left:6px;font-size:12px;color:var(--mut)}.tabs button.on{background:var(--on);color:var(--onfg);border-color:var(--on)}.tabs button.on span{color:inherit;opacity:.7}
.tab{display:none}.tab.on{display:block}.empty,.note{color:var(--mut);font-size:15px}
.toc{border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin:18px 0;font-size:15px;background:var(--card)}
.tc{padding:6px 0;border-bottom:1px dashed var(--line)}.tc:last-child{border:0}.tcat{font-weight:600;color:var(--fg);text-decoration:none}
.toc span,.cnt{color:var(--mut);font-size:12px;margin-left:4px;font-weight:400}.ttop{display:flex;flex-wrap:wrap;gap:2px 14px;margin-top:2px}.ttop a{text-decoration:none;color:var(--mut)}
h2{font-size:24px;margin:44px 0 6px;color:var(--acc);letter-spacing:.04em}h3{font-size:18px;margin:26px 0 10px;color:var(--mut);font-weight:600}
article{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:22px 26px;margin:14px 0}
article h5{font-size:20px;margin:0;line-height:1.5}.src{color:var(--mut);font-size:13px;margin:2px 0 12px}
.gold{border-left:3px solid var(--acc);padding:2px 0 2px 14px;color:var(--acc);font-size:17px;line-height:1.8}
details{margin-top:12px}summary{cursor:pointer;color:var(--mut);font-size:14px;list-style:none}summary::before{content:"▸ "}details[open] summary::before{content:"▾ "}
details[open] summary{margin-bottom:12px}
article p{margin:0 0 1.05em;text-align:justify}article h4{font-size:17px;margin:1.5em 0 .5em;color:var(--acc)}
blockquote{margin:0 0 1.1em;padding:12px 18px;background:var(--q);border-radius:8px}blockquote p{margin:0 0 .5em}blockquote p:last-child{margin:0}
.who{display:inline-block;min-width:2.6em;color:var(--acc);font-weight:600}ol,ul{padding-left:1.4em;margin:0 0 1.1em}li{margin:.35em 0}
mark{background:none;color:var(--mut);font-size:.8em}
table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.6;margin-bottom:10px}td{border-bottom:1px solid var(--line);padding:6px 6px;vertical-align:top}td:first-child{color:var(--mut);white-space:nowrap}
.stat{display:flex;flex-wrap:wrap;gap:8px 22px;padding:0;list-style:none;font-size:15px}
.hide{display:none!important}
.gold{margin-bottom:16px}
@media (max-width:900px){main{padding:20px 16px 80px}.layout{grid-template-columns:1fr;gap:12px}
 .side{position:static;max-height:none;border-right:0;border:1px solid var(--line);border-radius:12px;padding:10px 14px;background:var(--card)}
 .side .ttop{display:flex;flex-wrap:wrap;gap:0 12px;margin-left:0}}
@media (max-width:600px){article{padding:18px 16px}body{font-size:17px}table{font-size:13px}}
#pl{border:0;padding:0;background:#000;border-radius:12px;max-width:min(96vw,1100px);max-height:94vh;overflow:hidden}
#pl::backdrop{background:rgba(0,0,0,.72)}
#pl .x{position:absolute;top:8px;right:10px;z-index:2;border:0;background:rgba(0,0,0,.55);color:#fff;font-size:22px;width:36px;height:36px;border-radius:50%;cursor:pointer}
#pl video{display:block;max-width:min(96vw,1100px);max-height:94vh}
#pl .imgs{max-height:94vh;overflow-y:auto;background:var(--bg);padding:10px}#pl .imgs img{display:block;max-width:100%;margin:0 auto 10px}
.play{cursor:pointer}
.pp{display:inline-flex;gap:6px;margin-left:14px;vertical-align:middle}
.pp button{border:1px solid var(--line);background:var(--card);color:var(--mut);border-radius:999px;padding:1px 11px;font:inherit;font-size:13px;line-height:1.7;cursor:pointer;letter-spacing:0;font-weight:400}
.pp button:hover{color:var(--acc);border-color:var(--acc)}
.tabplay{font-size:14px;color:var(--mut);margin:8px 0 -18px}.wi{margin-left:16px;cursor:pointer;white-space:nowrap}.wi input{vertical-align:middle;accent-color:var(--acc)}
#pl .bar{display:none;align-items:center;gap:10px;padding:8px 12px;background:#111;color:#ddd;font-size:14px}
#pl.list .bar{display:flex}#pl.list video{max-height:calc(94vh - 46px)}#pl.list .imgs{max-height:calc(94vh - 46px)}
#pl .bar .info{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#pl .bar button{border:1px solid #444;background:#222;color:#eee;border-radius:999px;padding:2px 12px;font:inherit;font-size:13px;cursor:pointer}
article.now{outline:2px solid var(--acc);outline-offset:3px}
"""
PLAYBTN = "<span class=pp><button class=pa data-mode=seq title=按顺序连续播放>▶ 连播</button><button class=pa data-mode=shuf title=随机顺序连续播放>🔀 洗牌</button></span>"
JS = """<dialog id=pl><button class=x aria-label=关闭>×</button><div class=stage></div><div class=bar><button class=prev>↑ 上一条</button><span class=info></span><button class=next>下一条 ↓</button></div></dialog><script>
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
$$('.tabs button').forEach(b=>b.onclick=()=>{$$('.tabs button').forEach(x=>x.classList.toggle('on',x===b));
 $$('.tab').forEach(t=>t.classList.toggle('on',t.id===b.dataset.tab));try{localStorage.setItem('yuedu-tab',b.dataset.tab)}catch(e){}});
try{const t=localStorage.getItem('yuedu-tab');const b=t&&$(`.tabs button[data-tab="${t}"]`);if(b)b.click()}catch(e){}
$('#q').oninput=e=>{const q=e.target.value.trim().toLowerCase();$$('article').forEach(a=>a.classList.toggle('hide',!!q&&!a.dataset.s.includes(q)&&!a.textContent.toLowerCase().includes(q)))};
// 「原视频」：弹窗播放本地视频 / 查看本地图文图片
const pl=$('#pl'),stage=pl.querySelector('.stage'),info=pl.querySelector('.info');
let list=[],cur=-1,timer=0;
function load(a,onEnd){clearTimeout(timer);stage.innerHTML='';
 if(a.dataset.video){const v=document.createElement('video');v.controls=true;v.autoplay=true;v.src=a.dataset.video;
  v.onerror=()=>{stage.innerHTML='<p style="color:#fff;padding:30px">打不开这个本地视频，可能已被移动或删除。</p>';if(onEnd)timer=setTimeout(onEnd,1200)};
  if(onEnd)v.onended=onEnd;stage.append(v)}
 else{const box=document.createElement('div');box.className='imgs';const srcs=JSON.parse(a.dataset.imgs);srcs.forEach(s=>{const i=new Image();i.src=s;box.append(i)});stage.append(box);
  if(onEnd){// 连播里的图文：按内容长短停 5～15 秒（每张约 5 秒、或按约 100px/秒滚完），期间自动往下滚，最多 15 秒就跳下一条
   const t0=performance.now();
   const step=now=>{if(!box.isConnected)return;const max=box.scrollHeight-box.clientHeight;
    const ms=Math.min(15000,Math.max(5000,srcs.length*5000,max*10+2000)),p=Math.min(1,(now-t0)/ms);box.scrollTop=max*p;
    if(p<1)requestAnimationFrame(step);else onEnd()};requestAnimationFrame(step)}}}
document.addEventListener('click',e=>{const a=e.target.closest('a.play');if(!a)return;e.preventDefault();
 list=[];pl.classList.remove('list');load(a);if(!pl.open)pl.showModal()});
// 连播 / 洗牌连播：按钮所在的整个 tab、大类（到下一个大类为止）或小主题（到下一个标题为止），跳过被搜索隐藏的
function scope(b){const h=b.closest('h2,h3,.tabplay');let r=[];
 if(h.classList.contains('tabplay'))r=[...h.parentElement.querySelectorAll('article')];
 else{const stop=h.tagName==='H2'?['H2']:['H2','H3'];for(let n=h.nextElementSibling;n&&!stop.includes(n.tagName);n=n.nextElementSibling)if(n.tagName==='ARTICLE')r.push(n)}
 const img=withImg();return r.filter(a=>!a.classList.contains('hide')&&a.querySelector(img?'a.play':'a.play[data-video]'))}
// 「连播带图文」勾选：所有 tab 共用一个设置，记在本机
function withImg(){const c=$('.withimg');return !c||c.checked}
try{const s=localStorage.getItem('yuedu-withimg');if(s!==null)$$('.withimg').forEach(c=>c.checked=s==='1')}catch(e){}
document.addEventListener('change',e=>{if(!e.target.classList.contains('withimg'))return;const v=e.target.checked;
 $$('.withimg').forEach(c=>c.checked=v);try{localStorage.setItem('yuedu-withimg',v?'1':'0')}catch(e){}});
function go(i){if(!list.length)return;if(i>=list.length){pl.close();return}cur=Math.max(0,i);const art=list[cur];
 $$('article.now').forEach(x=>x.classList.remove('now'));art.classList.add('now');
 info.textContent=`${cur+1} / ${list.length} · ${art.querySelector('h5').textContent}`;load(art.querySelector('a.play'),()=>go(cur+1))}
document.addEventListener('click',e=>{const b=e.target.closest('button.pa');if(!b)return;e.preventDefault();e.stopPropagation();
 list=scope(b);if(!list.length){alert('这里没有可播放的原视频');return}
 if(b.dataset.mode==='shuf')for(let i=list.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[list[i],list[j]]=[list[j],list[i]]}
 pl.classList.add('list');if(!pl.open)pl.showModal();go(0)});
pl.querySelector('.next').onclick=()=>go(cur+1);pl.querySelector('.prev').onclick=()=>go(cur-1);
pl.addEventListener('keydown',e=>{if(!list.length)return;
 if(e.key==='ArrowDown'||e.key==='PageDown'){e.preventDefault();go(cur+1)}else if(e.key==='ArrowUp'||e.key==='PageUp'){e.preventDefault();go(cur-1)}});
let wt=0;pl.addEventListener('wheel',e=>{if(!list.length||e.target.closest('.imgs'))return;e.preventDefault();const t=Date.now();
 if(t-wt<700||Math.abs(e.deltaY)<30)return;wt=t;go(cur+(e.deltaY>0?1:-1))},{passive:false});
pl.querySelector('.x').onclick=()=>pl.close();
pl.addEventListener('click',e=>{if(e.target===pl)pl.close()});
pl.addEventListener('close',()=>{clearTimeout(timer);stage.innerHTML='';const n=$('article.now');
 if(list.length&&n){n.scrollIntoView({block:'center'});setTimeout(()=>n.classList.remove('now'),2500)}list=[];pl.classList.remove('list')});
</script>"""

if __name__ == "__main__":
    main()
