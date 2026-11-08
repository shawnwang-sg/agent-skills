# -*- coding: utf-8 -*-
"""把成品汇总到桌面「<标题>」文件夹：PDF、MOBI、TXT、打印页 PDF、音频\\*.mp3。只复制，不删源文件。

用法：python collect.py --title 厉害文字集锦 --src <输出目录> [--audio <音频目录>] [--dest <目标目录>]
"""
import argparse, glob, os, shutil

ap = argparse.ArgumentParser()
ap.add_argument("--title", required=True)
ap.add_argument("--src", required=True)
ap.add_argument("--audio")
ap.add_argument("--dest")
A = ap.parse_args()

def desktop():
    try:  # OneDrive 可能把桌面重定向，按系统登记的位置取
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders")
        return os.path.expandvars(winreg.QueryValueEx(k, "Desktop")[0])
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Desktop")

dest = A.dest or os.path.join(desktop(), A.title)
os.makedirs(dest, exist_ok=True)
files = [f for pat in (f"{A.title}.pdf", f"{A.title}.mobi", f"{A.title}.txt", "*_打印页.pdf")
         for f in glob.glob(os.path.join(A.src, pat))]
for f in files:
    shutil.copy2(f, dest)
if A.audio:
    ad = os.path.join(dest, "音频"); os.makedirs(ad, exist_ok=True)
    for f in sorted(glob.glob(os.path.join(A.audio, "*.mp3"))):
        shutil.copy2(f, ad)
for n in sorted(os.listdir(dest)):
    p = os.path.join(dest, n)
    print(f"  {n}\\ （{len(os.listdir(p))} 个文件）" if os.path.isdir(p) else f"  {n}  {os.path.getsize(p)//1024} KB")
print("已汇总到", dest)
