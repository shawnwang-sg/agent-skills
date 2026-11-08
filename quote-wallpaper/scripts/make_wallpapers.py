# -*- coding: utf-8 -*-
"""名言 → 桌面文字壁纸（每条一张）。HTML 模板 + 无头 Chrome 截图，4 进程并行，输出 JPG。

用法：
  python make_wallpapers.py <输入> --out <输出目录> [--bg 背景图] [--limit N] [--force]
输入可以是：
  - quote-collection-publish 生成的 pages.json（自动带上类别）
  - JSON 列表：["文字", ...] 或 [{"t": "文字", "cat": "类别", "name": "文件名(可选)"}, ...]
  - txt：条目之间空一行

规则（用户定稿）：
  - 背景默认是 assets/ 或 ~/Pictures/Wallpapers/ 下的 雷尼尔雪山_16x10_3072x1920.jpg，画布 3072×1920
  - ≤100 字：右上角磨砂玻璃横条框 BAR；101～300 字：右上角磨砂玻璃大框 BIG；>300 字不做
  - 框的位置和大小永远固定；字号自动取能放下的最大值（短文最大 64px，长文最大 60px）
  - 换行用 zh_lines.lines_of（≤100 字最多 4 段、长文最多 6 段，引号不拆）
  - 文件名：NNN_<类别前4字>_<正文开头10字>.jpg，JPG 质量 90
"""
import argparse, html, json, os, re, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zh_lines import lines_of, find_chrome

HERE = os.path.dirname(os.path.abspath(__file__))
# 背景图不进 git：优先用 skill 里 assets/ 的副本，没有就用本机图片库里的原图
_BG_NAME = "雷尼尔雪山_16x10_3072x1920.jpg"
DEFAULT_BG = next((p for p in [os.path.join(HERE, "..", "assets", _BG_NAME),
                               os.path.join(os.path.expanduser("~"), "Pictures", "Wallpapers", _BG_NAME)]
                   if os.path.exists(p)), os.path.join(HERE, "..", "assets", _BG_NAME))
W, H = 3072, 1920
BAR = (1800, 64, 3008, 430)     # 短文框（固定，x0,y0,x1,y1）
BIG = (2060, 64, 3008, 880)     # 长文框（固定）
CHROME = find_chrome()
PROFILE = os.path.join(tempfile.gettempdir(), "qwp_prof")

def page(text, bg):
    box = BAR if len(text) <= 100 else BIG
    x0, y0, x1, y1 = [round(v * W / 3072) if i % 2 == 0 else round(v * H / 1920) for i, v in enumerate(box)]
    paras = "".join(f"<p>{html.escape(p)}</p>" for p in lines_of(text))
    bgu = "file:///" + os.path.abspath(bg).replace("\\", "/")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:url('{bgu}') center/cover}}
.g{{position:absolute;left:{x0}px;top:{y0}px;width:{x1-x0}px;height:{y1-y0}px;box-sizing:border-box;padding:56px 64px;
   border-radius:34px;background:rgba(238,242,246,.50);backdrop-filter:blur(30px) saturate(1.1);
   border:2px solid rgba(255,255,255,.55);box-shadow:0 10px 40px rgba(20,30,40,.12);
   display:flex;flex-direction:column;justify-content:center}}
.g p{{margin:0;font-family:"Noto Serif SC","Source Han Serif SC","SimSun",serif;font-weight:500;color:#1e2630;line-height:1.6;text-align:justify}}
.g p+p{{margin-top:.45em}}
</style></head><body><div class="g" id="g">{paras}</div>
<script>
const g=document.getElementById('g');let s={64 if len(text) <= 100 else 60};
const fit=()=>g.scrollHeight<=g.clientHeight+1;
const set=v=>g.querySelectorAll('p').forEach(p=>p.style.fontSize=v+'px');
document.fonts.ready.then(()=>{{set(s);while(!fit()&&s>26){{s-=1;set(s)}}document.title='fs='+s}});
</script></body></html>"""

def job(args):
    jpg, text, bg, wid = args
    from PIL import Image
    if os.path.exists(jpg):
        return jpg
    png = os.path.join(tempfile.gettempdir(), f"qwp_{wid}_{os.getpid()}.png")
    f = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    f.write(page(text, bg)); f.close()
    for _ in range(4):                       # 偶发截图失败时重试
        try:
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={PROFILE}_{wid}",
                            "--hide-scrollbars", "--force-device-scale-factor=1", f"--window-size={W},{H}",
                            "--virtual-time-budget=6000", "--screenshot=" + png, "file:///" + f.name.replace("\\", "/")],
                           capture_output=True, timeout=180)
        except subprocess.TimeoutExpired:
            pass
        if os.path.exists(png) and os.path.getsize(png) > 100000:
            break
    os.unlink(f.name)
    if not os.path.exists(png):
        return "失败 " + jpg
    Image.open(png).convert("RGB").save(jpg, quality=90, optimize=True)
    os.unlink(png)
    return jpg

def load(path):
    if path.lower().endswith(".txt"):
        s = open(path, encoding="utf-8-sig").read()
        return [{"t": x.strip(), "cat": ""} for x in re.split(r"\n\s*\n", s) if x.strip()]
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d, dict) and "pages" in d:
        return [{"t": it["t"], "cat": p["cat"]} for p in d["pages"] for it in p["items"]]
    return [x if isinstance(x, dict) else {"t": x, "cat": ""} for x in d]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", required=True)
    ap.add_argument("--bg", default=DEFAULT_BG)
    ap.add_argument("--limit", type=int, default=0, help="只做前 N 张（试样）")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的图片")
    A = ap.parse_args()
    if not CHROME:
        sys.exit("找不到 Chrome/Edge")
    from PIL import Image
    iw, ih = Image.open(A.bg).size
    if abs(iw / ih - W / H) > 0.02:
        print(f"注意：背景图比例 {iw}x{ih} 与画布 {W}x{H} 不同，会居中裁切")
    os.makedirs(A.out, exist_ok=True)
    items = [x for x in load(A.input) if len(x["t"]) <= 300]
    skipped = len(load(A.input)) - len(items)
    if A.limit:
        items = items[:A.limit]
    tasks = []
    for no, x in enumerate(items, 1):
        short = re.sub(r"^[一二三四五六七八九十]+、|\s|·", "", x.get("cat", ""))[:4]
        head = re.sub(r'[\\/:*?"<>|\s“”‘’。，、；：！？…—（）()]', "", x["t"])[:10]
        name = x.get("name") or "_".join(s for s in (f"{no:03d}", short, head) if s)
        jpg = os.path.join(A.out, name + ".jpg")
        if A.force and os.path.exists(jpg):
            os.remove(jpg)
        tasks.append((jpg, x["t"], A.bg, no % 4))
    print("共", len(tasks), "张；超过 300 字跳过", skipped, "条", flush=True)
    bad = []
    with ProcessPoolExecutor(4) as ex:
        for k, r in enumerate(ex.map(job, tasks), 1):
            if r.startswith("失败"):
                bad.append(r)
            if k % 50 == 0 or k == len(tasks):
                print(k, "/", len(tasks), flush=True)
    print("失败：", bad or "无")
