# -*- coding: utf-8 -*-
"""集锦 JSON → A4 双栏分页 HTML（一页 = 一集音频）+ pages.json + 可选单独打印页。

用法：python build_pages.py <工作目录>/collection.json --out <输出目录>

collection.json 格式：
{
  "title": "厉害文字集锦",
  "cats": [ {"name": "一、行动·自律·成长",
             "items": [ {"t": "正文（段落之间用空行）", "topic": "行动胜过空想"}, ... ]}, ... ],
  "extract": {"title": "14 种实用方法", "file": "哈佛教授14种实用方法", "items": ["正文", ...]}   // 可选
}
做法：先用无头 Chrome 实测每篇在 9.5pt 双栏里的高度，再按页面容量把每个类别平均分成若干页；
一页只放一个类别；页面打开/打印时由页内脚本自动微调字号（9.5→最多 10.5pt）和篇间距，每页底部留约 7% 空白。
"""
import argparse, html, json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zh_lines import paras, find_chrome

ap = argparse.ArgumentParser()
ap.add_argument("collection")
ap.add_argument("--out", required=True, help="输出目录（放分页 HTML、打印页）；pages.json 写在 collection.json 旁边")
ap.add_argument("--cpm", type=float, default=275, help="语速：每分钟汉字数（edge-tts 云希 +8% 实测约 275）")
ap.add_argument("--font", type=float, default=9.5, help="正文字号 pt")
a = ap.parse_args()

C = json.load(open(a.collection, encoding="utf-8"))
TITLE = C["title"]
os.makedirs(a.out, exist_ok=True)
CHROME = find_chrome() or sys.exit("找不到 Chrome/Edge")
PROFILE = os.path.join(tempfile.gettempdir(), "qcp_prof")
OUT_HTML = os.path.join(a.out, f"{TITLE}_分页.html")
GAP_SEC = 2.0

# ---------- 版式（屏幕与打印共用，单位 mm）----------
PAGE_W, PAGE_H = 210, 297
PAD_T, PAD_B, PAD_X = 15, 13, 18
HEAD_H, FOOT_H = 15, 8
BODY_W = PAGE_W - 2 * PAD_X
BODY_H = PAGE_H - PAD_T - PAD_B - HEAD_H - FOOT_H
COL_GAP = 7
COL_W = (BODY_W - COL_GAP) / 2
F = a.font
CSS_TEXT = f"""
.txt{{font-family:"Noto Serif SC","Source Han Serif SC","Songti SC","SimSun",serif;font-size:{F}pt;line-height:1.75;
     color:var(--ink);text-align:justify;margin:0 0 3.4mm;padding-left:4mm;position:relative}}
.txt::before{{content:"";position:absolute;left:0;top:.62em;width:1.6mm;height:1.6mm;border-radius:50%;background:var(--gold);opacity:.7}}
.txt p{{margin:0}}.txt p+p{{margin-top:1.6mm}}
"""

def esc_item(t):
    return "".join(f"<p>{html.escape(p)}</p>" for p in paras(t))

def headless_dom(page_html):
    f = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    f.write(page_html); f.close()
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--user-data-dir=" + PROFILE, "--virtual-time-budget=8000",
                        "--dump-dom", "file:///" + f.name.replace("\\", "/")],
                       capture_output=True, text=True, encoding="utf-8", timeout=300)
    os.unlink(f.name)
    m = re.search(r'<pre id="out"[^>]*>(.*?)</pre>', r.stdout or "", re.S)
    if not m or not m.group(1).strip():
        sys.exit("无头浏览器没有返回结果：\n" + (r.stderr or "")[-2000:])
    return json.loads(html.unescape(m.group(1)))

def spoken(t):
    return len(re.sub(r"[^一-鿿]", "", t))

# ---------- 1. 实测每篇高度 ----------
flat = [(ci, it) for ci, c in enumerate(C["cats"]) for it in c["items"]]
measure = f"""<!doctype html><html><head><meta charset="utf-8"><style>
:root{{--ink:#000;--gold:#a8741f}} body{{margin:0}} #box{{width:{COL_W}mm}} {CSS_TEXT}
</style></head><body><div id="box">{''.join(f'<div class="txt">{esc_item(it["t"])}</div>' for _, it in flat)}</div>
<pre id="out"></pre><script>
document.fonts.ready.then(()=>{{const mm=96/25.4;const els=[...document.querySelectorAll('.txt')];
const r=els.map((e,i)=>{{const n=els[i+1];const h=(n?n.offsetTop:e.offsetTop+e.offsetHeight+parseFloat(getComputedStyle(e).marginBottom))-e.offsetTop;return h/mm}});
document.getElementById('out').textContent=JSON.stringify(r)}});
</script></body></html>"""
heights = headless_dom(measure)
assert len(heights) == len(flat)

# ---------- 2. 按页面容量切集（一页只放一个类别）----------
CAPF = 0.94

def split_category(hs):
    """先定页数，再把内容平均分到各页（类别内可小幅调序）。超一点点放不下就靠缩字号省一页。"""
    cap = BODY_H * 2 * CAPF
    T = sum(hs)
    kf = max(1, int(T // cap))
    k = kf if T / (kf * cap) <= 1.05 else kf + 1
    target = T / k
    rem, out = list(range(len(hs))), []
    for p in range(k):
        if p == k - 1:
            out.append(sorted(rem)); break
        cur, h, i = [], 0.0, 0
        while i < len(rem) and i <= 15:
            j = rem[i]
            if not cur or h + hs[j] <= target * 1.02:
                cur.append(j); h += hs[j]; rem.pop(i)
            else:
                i += 1
        out.append(sorted(cur))
    return [g for g in out if g]

pages, k0 = [], 0
for ci, c in enumerate(C["cats"]):
    its = [dict(it, h=heights[k0 + j]) for j, it in enumerate(c["items"])]
    k0 += len(its)
    if not its:
        continue
    for ep, idx in enumerate(split_category([x["h"] for x in its]), 1):
        grp = [its[j] for j in idx]
        sec = sum(spoken(x["t"]) for x in grp) / a.cpm * 60 + GAP_SEC * (len(grp) - 1)
        pages.append({"ci": ci, "cat": c["name"], "ep": ep, "items": [{"t": x["t"], "topic": x.get("topic", "")} for x in grp],
                      "fill": round(sum(x["h"] for x in grp) / (BODY_H * 2), 3), "min": round(sec / 60, 1),
                      "topics": [t for t in dict.fromkeys(x.get("topic", "") for x in grp) if t]})
json.dump({"title": TITLE, "pages": pages, "extract": C.get("extract")},
          open(os.path.join(os.path.dirname(os.path.abspath(a.collection)), "pages.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)   # pages.json 放在 collection.json 旁边（工作目录）

# ---------- 3. 输出分页 HTML ----------
def short(c):
    return re.sub(r"^[一二三四五六七八九十]+、", "", c)

def page_html(no, p):
    body = "".join(f'<div class="txt">{esc_item(it["t"])}</div>' for it in p["items"])
    return f"""<section class="page" id="p{no}"><header><span class="cat">{html.escape(short(p['cat']))}</span>
<span class="ep">第 {no} 集 · {html.escape(' / '.join(p['topics']))}</span></header>
<div class="body">{body}</div>
<footer><span>约 {p['min']} 分钟 · {len(p['items'])} 篇</span><span>{no}</span></footer></section>"""

toc, seen, secs = [], set(), []
for no, p in enumerate(pages, 1):
    if p["ci"] not in seen:
        seen.add(p["ci"]); toc.append(f'<a href="#p{no}">{html.escape(p["cat"])}<b>P{no}</b></a>')
    secs.append(f'<div class="scaler">{page_html(no, p)}</div>')
mins = [p["min"] for p in pages]
doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(TITLE)}</title><style>
:root{{--bg:#e9e5de;--paper:#fffdf8;--ink:#2a2622;--sub:#8c8378;--gold:#a8741f;--line:#e6dfd3}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#121110;--paper:#1d1b18;--ink:#ebe5dc;--sub:#9a9187;--gold:#e2ba70;--line:#302b26}}}}
:root[data-theme="dark"]{{--bg:#121110;--paper:#1d1b18;--ink:#ebe5dc;--sub:#9a9187;--gold:#e2ba70;--line:#302b26}}
*{{box-sizing:border-box}} html,body{{margin:0;background:var(--bg);color:var(--ink)}}
.top{{max-width:{PAGE_W}mm;margin:0 auto;padding:28px 16px 8px;font-family:"Noto Serif SC",serif}}
.top h1{{margin:0;font-size:28px;letter-spacing:4px}} .top p{{color:var(--sub);font-size:14px;margin:6px 0 14px}}
.toc{{display:flex;flex-wrap:wrap;gap:6px}} .toc a{{font-size:13px;color:var(--ink);text-decoration:none;border:1px solid var(--line);background:var(--paper);border-radius:16px;padding:3px 11px}}
.toc b{{color:var(--gold);font-weight:600;margin-left:6px}}
.wrap{{padding:12px 0 60px}} .scaler{{margin:0 auto 18px;width:{PAGE_W}mm}}
.page{{width:{PAGE_W}mm;height:{PAGE_H}mm;padding:{PAD_T}mm {PAD_X}mm {PAD_B}mm;background:var(--paper);
  box-shadow:0 2px 14px rgba(0,0,0,.12);display:flex;flex-direction:column;overflow:hidden;transform-origin:top left}}
.page header{{height:{HEAD_H}mm;display:flex;justify-content:space-between;align-items:flex-start;border-bottom:.3mm solid var(--gold);
  font-family:"Noto Serif SC",serif;padding-bottom:2mm}}
.page header .cat{{font-size:14pt;font-weight:700;letter-spacing:1px;color:var(--gold)}}
.page header .ep{{font-size:9pt;color:var(--sub);padding-top:1.6mm;text-align:right;max-width:60%}}
.page .body{{height:{BODY_H}mm;padding-top:4mm;overflow:hidden;column-count:2;column-gap:{COL_GAP}mm;column-fill:auto;column-rule:.2mm solid var(--line)}}
.page footer{{height:{FOOT_H}mm;display:flex;justify-content:space-between;align-items:flex-end;font:8.5pt "Noto Serif SC",serif;color:var(--sub);border-top:.2mm solid var(--line)}}
{CSS_TEXT}
@media print{{@page{{size:A4;margin:0}} body{{background:#fff}} .top{{display:none}} .wrap{{padding:0}}
  .scaler{{margin:0;width:auto!important;height:auto!important}} .page{{box-shadow:none;transform:none!important;break-after:page}}
  :root{{--paper:#fff;--ink:#222;--sub:#888;--gold:#a8741f;--line:#ddd}}}}
</style></head><body>
<div class="top"><h1>{html.escape(TITLE)}</h1>
<p>{len(pages)} 页 · 每页一集音频 · 每集约 {min(mins)}～{max(mins)} 分钟（平均 {sum(mins)/len(mins):.1f} 分钟）· 共 {sum(len(p['items']) for p in pages)} 篇</p>
<nav class="toc">{''.join(toc)}</nav></div>
<div class="wrap">{''.join(secs)}</div>
<pre id="out" hidden></pre>
<script>
function fit(){{const mm=96/25.4,w={PAGE_W}*mm,h={PAGE_H}*mm,avail=Math.min(document.documentElement.clientWidth-16,w),k=avail/w;
document.querySelectorAll('.scaler').forEach(s=>{{s.style.width=avail+'px';s.style.height=h*k+'px';s.firstElementChild.style.transform=k<1?`scale(${{k}})`:'none'}})}}
addEventListener('resize',fit);fit();
function ovf(b){{return b.scrollWidth>b.clientWidth+1||b.scrollHeight>b.clientHeight+1}}
// 单篇超长的页：逐步缩小字号直到放得下
function shrink(){{document.querySelectorAll('.page .body').forEach(b=>{{let f={F};while(ovf(b)&&f>7.5){{f-=.25;b.querySelectorAll('.txt').forEach(t=>t.style.fontSize=f+'pt')}}}})}}
// 未排满的页：底部留约 7% 空白；先适度放大字号（最多 10.5pt），再拉开篇间距
function stretch(){{document.querySelectorAll('.page .body').forEach(b=>{{const ts=[...b.querySelectorAll('.txt')];if(ovf(b))return;
b.style.height=(b.clientHeight*0.93)+'px';
let f=Math.round(parseFloat(getComputedStyle(ts[0]).fontSize)*.75*4)/4;const fs=v=>ts.forEach(t=>t.style.fontSize=v+'pt');
while(f<10.5){{fs(f+.25);if(ovf(b)){{fs(f);break}}f+=.25}}
let g=3.4;const set=v=>ts.forEach(t=>t.style.marginBottom=v+'mm');
while(g<9){{set(g+.25);if(ovf(b)){{set(g);break}}g+=.25}}
while(ovf(b)&&g>2){{g-=.25;set(g)}} while(ovf(b)&&f>7.5){{f-=.25;fs(f)}}}})}}
document.fonts.ready.then(()=>{{shrink();stretch();
const bad=[...document.querySelectorAll('.page .body')].map((b,i)=>ovf(b)?i+1:0).filter(Boolean);
document.getElementById('out').textContent=JSON.stringify(bad)}});
</script></body></html>"""
open(OUT_HTML, "w", encoding="utf-8").write(doc)
print("分页 HTML：", OUT_HTML)

# ---------- 单独的打印页 ----------
ex = C.get("extract")
if ex and ex.get("items"):
    ex_html = os.path.join(a.out, f"{ex.get('file') or ex['title']}_打印页.html")
    ex_body = "".join(f'<div class="txt">{esc_item(t)}</div>' for t in ex["items"])
    ex_doc = doc[:doc.index("<body>")] + f"""<body><div class="wrap"><div class="scaler"><section class="page" id="p1">
<header><span class="cat">{html.escape(ex['title'])}</span><span class="ep">单页打印</span></header>
<div class="body">{ex_body}</div><footer><span>{html.escape(TITLE)} · 附页</span><span></span></footer></section></div></div>
<pre id="out" hidden></pre>""" + doc[doc.index("<script>"):]
    open(ex_html, "w", encoding="utf-8").write(ex_doc)
    print("打印页：", ex_html, "溢出：", headless_dom(ex_doc))

over = headless_dom(doc)
print(f"页数 {len(pages)}，每页 {min(mins)}～{max(mins)} 分钟，平均 {sum(mins)/len(mins):.1f}；"
      f"实测填充 {min(p['fill'] for p in pages):.0%}～{max(p['fill'] for p in pages):.0%}；溢出页：{over or '无'}")
for no, p in enumerate(pages, 1):
    print(f"  {no:>2} {short(p['cat'])[:6]} 第{p['ep']}集 {p['min']}分 {p['fill']:.0%} {len(p['items'])}篇 {'/'.join(p['topics'])}")
