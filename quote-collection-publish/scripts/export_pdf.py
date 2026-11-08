# -*- coding: utf-8 -*-
"""分页 HTML → PDF（无头 Chrome 打印，A4 无页眉页脚），并用 pymupdf 核对页数和尺寸。

用法：python export_pdf.py <分页.html> <输出.pdf> [更多 html pdf 成对参数...]
"""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zh_lines import find_chrome
import pymupdf

C = find_chrome() or sys.exit("找不到 Chrome/Edge")
args = sys.argv[1:]
if not args or len(args) % 2:
    sys.exit(__doc__)
for src, dst in zip(args[::2], args[1::2]):
    src, dst = os.path.abspath(src), os.path.abspath(dst)
    subprocess.run([C, "--headless=new", "--disable-gpu", "--user-data-dir=" + os.path.join(tempfile.gettempdir(), "qcp_pdf"),
                    "--virtual-time-budget=12000", "--no-pdf-header-footer", "--print-to-pdf=" + dst,
                    "file:///" + src.replace("\\", "/")], capture_output=True, timeout=600)
    d = pymupdf.open(dst); r = d[0].rect
    print(dst, d.page_count, "页", round(r.width / 72 * 25.4), "x", round(r.height / 72 * 25.4), "mm",
          round(os.path.getsize(dst) / 1e6, 1), "MB")
