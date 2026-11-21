# -*- coding: utf-8 -*-
"""把剪映导出的「英文+中文」SRT 整理成整句双语字幕。

用法: python -I jy_merge.py <剪映srt> <job.json> <输出目录> <base名>
job.json: {"groups": [[1,3],[4,7],...], "zh": ["...", "..."]}
  groups 为英文块的 1-based 闭区间（连续、不漏不重）；zh 与 groups 一一对应（整句中文译文）。
  「英文块」= 不含任何 CJK 汉字的块（剪映偶尔把一句英文识别成中文，那一块会被跳过）。
输出:
  <base>.srt    英上中下双语，GBK + CRLF（给 Aboboo：它忽略 BOM、按内容猜编码，UTF-8 易乱码）
  <base>.en.srt 纯英文整句，UTF-8 带 BOM
英文只做拼接（块之间加一个空格），不改任何字。时间 = 首块起点 ~ 末块终点。
"""
import json
import re
import sys
import unicodedata
from pathlib import Path


def parse_srt(text):
    blocks = []
    for chunk in re.split(r"\r?\n\s*\r?\n", text.strip()):
        lines = [l for l in chunk.splitlines() if l.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        start, end = [t.strip() for t in lines[1].split("-->")]
        blocks.append((start, end, " ".join(l.strip() for l in lines[2:])))
    return blocks


def to_gbk(text):
    out = []
    for ch in text:
        try:
            ch.encode("gbk")
            out.append(ch)
        except UnicodeEncodeError:
            plain = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode()
            out.append(plain or "?")
    return "".join(out).replace("\n", "\r\n").encode("gbk")


def is_cjk(s):
    return any("一" <= c <= "鿿" for c in s)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    src, job_path, out_dir, base = sys.argv[1:5]
    blocks = parse_srt(Path(src).read_text(encoding="utf-8-sig"))
    en = [b for b in blocks if not is_cjk(b[2])]
    job = json.loads(Path(job_path).read_text(encoding="utf-8"))
    groups, zh = job["groups"], job["zh"]
    assert len(groups) == len(zh), f"groups {len(groups)} != zh {len(zh)}"

    expect = 1
    for a, b in groups:
        assert a == expect and b >= a, f"group [{a},{b}] 不连续，期望从 {expect} 开始"
        expect = b + 1
    assert expect - 1 == len(en), f"分组覆盖到 {expect-1}，英文共 {len(en)} 块"
    bad = [i for i, z in enumerate(zh, 1) if not ("一" <= z.strip()[:1] <= "鿿")]
    assert not bad, f"这些中文句不是以汉字开头（Aboboo 会切错中英）: {bad}"

    bi, mono = [], []
    for i, ((a, b), z) in enumerate(zip(groups, zh), 1):
        seg = en[a - 1:b]
        text = re.sub(r"\s+", " ", " ".join(s[2] for s in seg)).strip()
        t = f"{seg[0][0]} --> {seg[-1][1]}"
        bi.append(f"{i}\n{t}\n{text}\n{z.strip()}\n")
        mono.append(f"{i}\n{t}\n{text}\n")

    out = Path(out_dir)
    (out / f"{base}.srt").write_bytes(to_gbk("\n".join(bi)))
    (out / f"{base}.en.srt").write_text("\n".join(mono), encoding="utf-8-sig")
    print(f"{base}: 英文 {len(en)} 块 -> {len(groups)} 句")


if __name__ == "__main__":
    main()
