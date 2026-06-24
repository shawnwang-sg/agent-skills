#!/usr/bin/env bash
# 模板:把一集从桌面文件夹搬进磨耳朵合集并改名为数字前缀。
# 用法:逐集替换 SRC / NUM,然后跑。绝对路径、不用 cd、写操作不用通配符。
# 保留: mp3 mp4 q99  merged字幕->NNN.srt  docx文稿->NNN.docx
# 丢弃: 原始.srt  *.stripped.txt  *.pdf  temp/   (不搬,留桌面)

T="C:/Users/Shugu/OneDrive/short videos/001-磨耳朵"
SRC="C:/Users/Shugu/Desktop/058 transform your finances"   # ← 改成本集文件夹
NUM="058"                                                   # ← 改成集号
BASE="058 transform your finances"                          # ← 改成文件主名(不含扩展名)

mv -f "$SRC/$BASE.mp3" "$T/$NUM.mp3" &&
mv -f "$SRC/$BASE.mp4" "$T/$NUM.mp4" &&
mv -f "$SRC/$BASE.q99" "$T/$NUM.q99" &&
mv -f "$SRC/${BASE}_merged.srt" "$T/$NUM.srt" &&
# 文稿 docx 文件名通常是另起的标题,逐集填:
# mv -f "$SRC/<文稿标题>.docx" "$T/$NUM.docx" &&
echo "$NUM done"

# 059 这类文件名不带数字(叫 tt合集01.*)时,直接把源名换成实际名、目标用文件夹数字前缀即可。
