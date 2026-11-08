"""把 done/ 里所有润色结果生成一个阅读页 yuedu.html。

结构：顶部 tab = 抖音收藏分类（厉害、爱好……），tab 里按「大类 → 小主题」分组，带目录和搜索；
另有「待处理清单」tab：没信息量的（含学习台里因无对白跳过的）、疑似归错分类的；「质检」tab：改动比例和存疑统计。
用法：python build_yuedu.py [--out D:\\douyin\\yuedu.html]
"""
import argparse, collections, difflib, html, json, re, sqlite3, time
from pathlib import Path

APP = Path(r"C:\Users\Shugu\douyin-fav-study")
WORK = Path(r"D:\douyin\_yuedu")
FOLDERS = ["厉害", "爱好", "厉害文字", "身体健康", "美食"]
PUNCT = re.compile(r"[\s，。、；：？！…—「」『』“”‘’（）《》()\[\]?,.;:!\"'﹐·\-*>#]")
CN_NUM = "一二三四五六七八九十"


def norm(s):
    s = s.replace("[?]", "").replace("（原视频到此结束）", "")
    s = re.sub(r"(?m)^## .*$", "", s)
    s = re.sub(r"(?m)^\d+\. ", "", s)
    s = re.sub(r"(?m)^> [^：:]{1,6}[：:]", "", s)
    return PUNCT.sub("", s)


def change_pct(raw, body):
    if "【正文】" in raw or "【图1】" in raw:
        # 图文：原稿里有作者/链接/话题和重复识别的图片文字，只拿正文部分比
        raw = raw.split("【图1】")[0] if len(raw.split("【图1】")[0]) > 30 else raw
        raw = re.sub(r"(?m)^(作者|链接)：.*$", "", raw)
    a = PUNCT.sub("", re.sub(r"#\S+|【(正文|图\d+)】", "", raw))
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


def folder_of(p):
    parts = Path(p or "").parts
    return parts[2] if len(parts) > 3 else ""


def load():
    res = {}
    for f in sorted((WORK / "done").glob("*.json")):
        for x in json.loads(f.read_text(encoding="utf-8")):
            res[int(x["id"])] = x
    c = sqlite3.connect(f"file:{APP / 'data' / 'library.db'}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    meta = {r["id"]: dict(r) for r in c.execute(
        "select id, author, title, url, local_path, transcript, duration, status, reason, media_type from items where source='local'")}
    return res, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"D:\douyin\yuedu.html")
    a = ap.parse_args()
    res, meta = load()

    keep = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(list)))
    low, move, qc = [], [], []
    for i, x in res.items():
        m = meta.get(i, {})
        folder = folder_of(m.get("local_path"))
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
        if m["status"] == "skipped" and i not in res and "说话内容" in (m.get("reason") or "") and folder_of(m["local_path"]) in FOLDERS:
            low.append({"id": i, "verdict": "low_info", "low_info_type": "画面为主", "reason": "转写时几乎没听到说话（画面、字幕或纯音乐为主）",
                        "theme": re.sub(r"#\S+", "", m.get("title") or "").strip()[:40], "_folder": folder_of(m["local_path"]),
                        "_author": m.get("author") or "", "_url": m.get("url") or "", "_path": m.get("local_path") or ""})

    css = CSS
    P = ["<!doctype html><html lang=zh><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
         f"<title>阅读 · 抖音收藏</title><style>{css}</style><body><main>",
         "<header><h1>阅读 · 抖音收藏</h1>",
         f"<p class=sub>视频转写稿 · 去口水词、改错字、不改原话 · 共 {len(qc)} 篇 · 更新于 {time.strftime('%Y-%m-%d %H:%M')}</p>",
         "<input id=q type=search placeholder='搜索标题、金句、作者……' autocomplete=off></header><nav class=tabs>"]
    tabs = [f for f in FOLDERS if keep.get(f)] + [f for f in FOLDERS if not keep.get(f)]
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
        P.append("<div class=toc>")
        for cat in sorted(cats, key=cat_key):
            topics = cats[cat]
            total = sum(len(v) for v in topics.values())
            P.append(f"<div class=tc><a href='#{f}-{html.escape(cat)}' class=tcat>{html.escape(cat)}<span>{total}</span></a><div class=ttop>")
            for t in sorted(topics, key=lambda t: -len(topics[t])):
                P.append(f"<a href='#{f}-{html.escape(cat)}-{html.escape(t)}'>{html.escape(t)}<span>{len(topics[t])}</span></a>")
            P.append("</div></div>")
        P.append("</div>")
        for cat in sorted(cats, key=cat_key):
            topics = cats[cat]
            P.append(f"<h2 id='{f}-{html.escape(cat)}'>{html.escape(cat)}</h2>")
            for t in sorted(topics, key=lambda t: -len(topics[t])):
                P.append(f"<h3 id='{f}-{html.escape(cat)}-{html.escape(t)}'>{html.escape(t)}</h3>")
                for x in sorted(topics[t], key=lambda x: x["id"]):
                    src = html.escape(x["_author"] or "佚名")
                    link = f" · <a href='{html.escape(x['_url'])}' target=_blank rel=noopener>原视频</a>" if x["_url"] else ""
                    P.append(f"<article data-s='{html.escape((x.get('theme', '') + x.get('gold', '') + x['_author']).lower())}'>"
                             f"<h5>{inline(x.get('theme', ''))}</h5><div class=src>—— {src}{link}</div>"
                             f"<div class=gold>{inline(x.get('gold', ''))}</div><details><summary>读全文</summary>{render(x.get('body', ''))}</details></article>")
        P.append("</section>")

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
    P.append("<h2>疑似放错收藏分类的</h2><p class=note>建议在抖音里改收藏夹；这里先不收进阅读版。</p>")
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
    over = sorted([x for x in qc if x["_pct"] > 10], key=lambda x: -x["_pct"])
    avg = sum(x["_pct"] for x in qc) / len(qc) if qc else 0
    uns = sum(int(x.get("unsure") or 0) for x in qc)
    P.append(f"<section id=tqc class=tab><h2>质检</h2><p class=note>改动比例 = 去掉标点和排版标记后，和原始转写逐字比对的差异。"
             f"超过 10% 的多半是转写错字多（改错字也算改动）。</p><ul class=stat><li>阅读版 {len(qc)} 篇</li>"
             f"<li>平均改动 {avg:.1f}%</li><li>超过 10% 的 {len(over)} 篇</li><li>存疑 [?] 共 {uns} 处</li></ul>"
             "<h3>改动超过 10% 的</h3><table>")
    for x in over:
        P.append(f"<tr><td>#{x['id']}</td><td>{html.escape(x.get('theme', ''))}</td><td>{html.escape(x['_author'])}</td><td>{x['_pct']:.0f}%</td>"
                 f"<td>{html.escape(x.get('note') or '')}</td></tr>")
    P.append("</table></section></main>" + JS)
    out = Path(a.out)
    out.write_text("".join(P), encoding="utf-8")
    print(f"{out}  阅读 {len(qc)} 篇 · 没信息量 {len(low)} · 疑似分错 {len(move)} · 平均改动 {avg:.1f}% · 超 10% {len(over)} 篇")


def row(x):
    link = f"<a href='{html.escape(x['_url'])}' target=_blank rel=noopener>原视频</a>" if x.get("_url") else ""
    return (f"<tr><td>#{x['id']}</td><td>{html.escape(x.get('_folder', ''))}</td><td>{html.escape(x.get('theme') or '')}</td>"
            f"<td>{html.escape(x.get('_author', ''))}</td><td>{html.escape(x.get('reason') or '')}</td><td>{link}</td></tr>")


CSS = """
:root{--bg:#f7f4ee;--fg:#24211c;--mut:#7a7368;--card:#fffdf9;--line:#e6dfd3;--acc:#9a5b2a;--q:#f1ebe0;--on:#24211c;--onfg:#fffdf9}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#181614;--fg:#ebe6dd;--mut:#a69f94;--card:#211e1b;--line:#38332d;--acc:#e0a46b;--q:#2a2622;--on:#ebe6dd;--onfg:#181614}}
:root[data-theme=dark]{--bg:#181614;--fg:#ebe6dd;--mut:#a69f94;--card:#211e1b;--line:#38332d;--acc:#e0a46b;--q:#2a2622;--on:#ebe6dd;--onfg:#181614}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:18px/1.95 "Noto Serif SC","Source Han Serif SC","Songti SC","SimSun",serif}
main{max-width:760px;margin:0 auto;padding:36px 16px 100px}a{color:var(--acc)}
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
@media (max-width:600px){article{padding:18px 16px}body{font-size:17px}table{font-size:13px}}
"""
JS = """<script>
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
$$('.tabs button').forEach(b=>b.onclick=()=>{$$('.tabs button').forEach(x=>x.classList.toggle('on',x===b));
 $$('.tab').forEach(t=>t.classList.toggle('on',t.id===b.dataset.tab));try{localStorage.setItem('yuedu-tab',b.dataset.tab)}catch(e){}});
try{const t=localStorage.getItem('yuedu-tab');const b=t&&$(`.tabs button[data-tab="${t}"]`);if(b)b.click()}catch(e){}
$('#q').oninput=e=>{const q=e.target.value.trim().toLowerCase();$$('article').forEach(a=>a.classList.toggle('hide',!!q&&!a.dataset.s.includes(q)&&!a.textContent.toLowerCase().includes(q)))};
</script>"""

if __name__ == "__main__":
    main()
