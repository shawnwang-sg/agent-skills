# -*- coding: utf-8 -*-
"""pages.json → 定稿 TXT + 电子书 HTML → MOBI（Calibre）。分集、分段与 PDF / MP3 一致。

用法：python make_book.py <工作目录>/pages.json --out <输出目录> [--author 作者] [--no-mobi]
输出：<标题>.txt（UTF-8 BOM，开头有目录，每集标序号/主题/时长）、<标题>.mobi（正常排版，
目录两级：类别 → 集；有打印页内容时放在书末附录）。电子书 HTML 留在 pages.json 同目录的 book/ 下。
"""
import argparse, html, json, os, subprocess, sys, tempfile, zipfile, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zh_lines import paras, find_calibre

ap = argparse.ArgumentParser()
ap.add_argument("pages")
ap.add_argument("--out", required=True)
ap.add_argument("--author", default="")
ap.add_argument("--no-mobi", action="store_true")
A = ap.parse_args()
D = json.load(open(A.pages, encoding="utf-8"))
TITLE, pages, ex = D["title"], D["pages"], D.get("extract") or {}
os.makedirs(A.out, exist_ok=True)
TXT = os.path.join(A.out, f"{TITLE}.txt")
BOOK = os.path.join(os.path.dirname(os.path.abspath(A.pages)), "book", f"{TITLE}.html")
EXT = ex.get("title")
ex_items = ex.get("items") or []

cats = list(dict.fromkeys(p["cat"] for p in pages))
n_items = sum(len(p["items"]) for p in pages)

# ---------- TXT ----------
L = [TITLE, f"（{len(cats)} 类 · {n_items} 篇 · {len(pages)} 集；每集对应 PDF 一页、一段 MP3）", "", "目录"]
for c in cats:
    eps = [i for i, p in enumerate(pages, 1) if p["cat"] == c]
    L.append(f"  {c}  第 {eps[0]}–{eps[-1]} 集" if len(eps) > 1 else f"  {c}  第 {eps[0]} 集")
if ex_items:
    L.append(f"  附录：{EXT}")
last = None
for no, p in enumerate(pages, 1):
    if p["cat"] != last:
        last = p["cat"]
        L += ["", "", "=" * 24, p["cat"], "=" * 24]
    L += ["", f"【第 {no} 集 · {' / '.join(p['topics'])} · 约 {p['min']} 分钟】", ""]
    for it in p["items"]:
        L += paras(it["t"]) + [""]
if ex_items:
    L += ["", "", "=" * 24, f"附录：{EXT}", "=" * 24, ""]
    for t in ex_items:
        L += paras(t) + [""]
open(TXT, "w", encoding="utf-8-sig").write("\n".join(L).rstrip() + "\n")
print("TXT：", TXT)

# ---------- 电子书 HTML ----------
os.makedirs(os.path.dirname(BOOK), exist_ok=True)
B = [f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{html.escape(TITLE)}</title><style>
body{{font-family:serif;line-height:1.75}} h1{{text-align:center;margin:1.5em 0 1em;page-break-before:always}}
h2{{font-size:1em;color:#8a6a2a;margin:2em 0 .8em;border-bottom:1px solid #ccc;padding-bottom:.3em}}
p{{margin:0 0 .5em;text-indent:0}} .item{{margin:0 0 1.2em}} .sep{{text-align:center;color:#999;margin:.2em 0 1em}}
</style></head><body>"""]
last = None
for no, p in enumerate(pages, 1):
    if p["cat"] != last:
        last = p["cat"]; B.append(f"<h1>{html.escape(p['cat'])}</h1>")
    B.append(f"<h2>第 {no} 集 · {html.escape(' / '.join(p['topics']))}</h2>")
    for it in p["items"]:
        B.append('<div class="item">' + "".join(f"<p>{html.escape(x)}</p>" for x in paras(it["t"])) + '</div><p class="sep">◆</p>')
if ex_items:
    B.append(f"<h1>附录：{html.escape(EXT)}</h1>" + "".join(
        '<div class="item">' + "".join(f"<p>{html.escape(x)}</p>" for x in paras(t)) + "</div>" for t in ex_items))
B.append("</body></html>")
open(BOOK, "w", encoding="utf-8").write("\n".join(B))

# ---------- MOBI ----------
if not A.no_mobi:
    conv = find_calibre()
    if not conv:
        sys.exit("没装 Calibre：winget install --id calibre.calibre -e --silent --accept-package-agreements --accept-source-agreements")
    mobi = os.path.join(A.out, f"{TITLE}.mobi")
    # 注意：XPath 必须写成 //*[name()='h1']，写 //h:h1 时 Calibre 认不出目录
    subprocess.run([conv, BOOK, mobi, "--title", TITLE, "--authors", A.author or TITLE, "--language", "zh",
                    "--chapter", "//*[name()='h1']", "--level1-toc", "//*[name()='h1']", "--level2-toc", "//*[name()='h2']",
                    "--output-profile", "kindle", "--mobi-file-type", "both"], capture_output=True)
    # 自检：转回 epub 读目录条数
    chk = os.path.join(tempfile.mkdtemp(), "x.epub")
    subprocess.run([conv, mobi, chk], capture_output=True)
    z = zipfile.ZipFile(chk); ncx = [f for f in z.namelist() if f.endswith(".ncx")]
    labs = re.findall(r"<text>(.*?)</text>", z.read(ncx[0]).decode("utf-8")) if ncx else []
    print("MOBI：", mobi, f"{os.path.getsize(mobi)//1024} KB；目录条目 {len(labs)}（应约为 类别数+集数+附录 = {len(cats)+len(pages)+bool(ex_items)}，Calibre 可能多 1 条书名）")
