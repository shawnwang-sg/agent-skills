# -*- coding: utf-8 -*-
"""中文基础换行规则（PDF / MP3 / 电子书 / 壁纸共用，保证四者分段一致）。"""
import re, os, shutil, glob

def lines_of(text):
    """按句号/问号/叹号/分号断句，太短的句子并到前一段，避免一句一行。
    句末后引号跟着本句；引号没闭合时不断开。短文(≤100字)最多 4 段，长文最多 6 段。"""
    text = re.sub(r"\s*\n\s*", "", text.strip())
    sents = [s for s in re.findall(r".*?[。！？；!?][”’」』）)]*|.+$", text) if s.strip()]
    merged = []
    for s in sents:
        if merged and (merged[-1].count("“") > merged[-1].count("”") or merged[-1].count('"') % 2):
            merged[-1] += s
        else:
            merged.append(s)
    limit = 4 if len(text) <= 100 else 6
    min_len = max(14, len(text) // limit)
    out = []
    for s in merged:
        if out and (len(out[-1]) < min_len or len(s) < 8):
            out[-1] += s
        else:
            out.append(s)
    while len(out) > limit:
        i = min(range(len(out) - 1), key=lambda k: len(out[k]) + len(out[k + 1]))
        out[i:i + 2] = [out[i] + out[i + 1]]
    return out

def paras(t):
    """原文已分段（空行隔开）的保持原样；单段且超过 60 字的按 lines_of 换行；60 字以内不换行。"""
    ps = [p.strip() for p in t.split("\n\n") if p.strip()]
    return lines_of(t) if len(ps) == 1 and len(t) > 60 else ps

def find_chrome():
    for p in [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]:
        if os.path.exists(p):
            return p
    return shutil.which("chrome") or shutil.which("msedge")

def find_calibre():
    for p in [r"C:\Program Files\Calibre2\ebook-convert.exe", r"C:\Program Files (x86)\Calibre2\ebook-convert.exe"]:
        if os.path.exists(p):
            return p
    return shutil.which("ebook-convert")
