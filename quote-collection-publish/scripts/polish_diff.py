# -*- coding: utf-8 -*-
"""润色对照页：左边原文、右边改后，红色删除线 = 删掉的字，绿底 = 新加的字，旁边一句话说明为什么改。

用法：python polish_diff.py changes.json --title 厉害文字集锦 --out <输出目录>
changes.json：[{"cat": "类别", "old": "原文", "new": "改后", "why": "错别字：思维稠密→思维缜密"}, ...]
（只放改动过的条目。）
"""
import argparse, difflib, html, json, os

ap = argparse.ArgumentParser()
ap.add_argument("changes")
ap.add_argument("--title", required=True)
ap.add_argument("--out", required=True)
A = ap.parse_args()
ch = json.load(open(A.changes, encoding="utf-8"))

def marks(a, b):
    L, R = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        x, y = html.escape(a[i1:i2]), html.escape(b[j1:j2])
        if op == "equal":
            L.append(x); R.append(y)
        else:
            if x: L.append(f"<del>{x}</del>")
            if y: R.append(f"<ins>{y}</ins>")
    return "".join(L).replace("\n", "<br>"), "".join(R).replace("\n", "<br>")

rows, last = [], None
for k, c in enumerate(ch, 1):
    if c.get("cat") != last:
        last = c.get("cat"); rows.append(f'<h2>{html.escape(last or "")}</h2>')
    l, r = marks(c["old"], c["new"])
    rows.append(f'<div class="row"><div class="n">{k}</div><div class="c">{l}</div><div class="c">{r}</div>'
                f'<div class="why">{html.escape(c.get("why", ""))}</div></div>')
doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(A.title)} 润色对照</title><style>
:root{{--bg:#f6f3ee;--card:#fffdf9;--ink:#2a2622;--sub:#8a8178;--line:#e7e0d6;--del:#c0392b;--ins:#d7f0dc}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151311;--card:#1e1b18;--ink:#ece6dd;--sub:#9a9187;--line:#2e2a26;--del:#ff8a7a;--ins:#24452d}}}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.8 "Noto Serif SC",serif}} main{{max-width:1200px;margin:0 auto;padding:24px 16px 80px}}
h1{{font-size:24px}} h2{{color:#a8741f;margin-top:32px}} .row{{display:grid;grid-template-columns:32px 1fr 1fr 220px;gap:12px;background:var(--card);
border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:8px 0}} .n{{color:var(--sub)}} .why{{color:var(--sub);font-size:13px}}
del{{color:var(--del)}} ins{{background:var(--ins);text-decoration:none}}
@media (max-width:760px){{.row{{grid-template-columns:1fr}}}}
</style></head><body><main><h1>{html.escape(A.title)} · 润色对照</h1><p style="color:var(--sub)">共改 {len(ch)} 条。左：原文；右：改后。</p>
{''.join(rows)}</main></body></html>"""
out = os.path.join(A.out, f"{A.title}_润色对照.html")
open(out, "w", encoding="utf-8").write(doc)
print(out)
