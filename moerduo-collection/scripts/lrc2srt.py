# -*- coding: utf-8 -*-
"""LRC -> SRT。每行一个块:起始=本行时间戳,结束=下一行时间戳(末块+4s),
   厘秒补毫秒。内容逐字不改。用法: python lrc2srt.py <in.lrc> [out.srt]"""
import re, sys

def conv(src, dst=None):
    dst = dst or re.sub(r'\.lrc$', '.srt', src, flags=re.I)
    items = []
    for line in open(src, encoding='utf-8', errors='ignore').read().splitlines():
        m = re.match(r'^\[(\d+):(\d+):(\d+)\.(\d+)\](.*)$', line)
        if not m:
            m2 = re.match(r'^\[(\d+):(\d+)\.(\d+)\](.*)$', line)   # [MM:SS.cc]
            if not m2: continue
            mi, s, fr, txt = m2.groups(); h = '0'
        else:
            h, mi, s, fr, txt = m.groups()
        ms = int(h)*3600000 + int(mi)*60000 + int(s)*1000 + int(fr.ljust(3, '0')[:3])
        if txt.strip(): items.append((ms, txt.strip()))
    def fmt(ms):
        h, ms = divmod(ms, 3600000); mi, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return '%02d:%02d:%02d,%03d' % (h, mi, s, ms)
    out = []
    for i, (ms, txt) in enumerate(items):
        end = items[i+1][0] if i+1 < len(items) else ms+4000
        if end <= ms: end = ms+1000
        out += [str(i+1), '%s --> %s' % (fmt(ms), fmt(end)), txt, '']
    open(dst, 'w', encoding='utf-8').write('\n'.join(out))
    print('blocks:', len(items), '->', dst)

if __name__ == '__main__':
    conv(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
