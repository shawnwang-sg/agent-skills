# -*- coding: utf-8 -*-
"""把若干集的 srt 按磨耳朵格式追加进 磨耳朵.docx(数字行 + 阅读友好意群行)。
   用法: 改 FOLDER / EPS。会先备份再写。追加在文末(不重排)。
   重排时间戳断行规则见 reflow_srt。"""
import zipfile, re, io, os, shutil
from xml.sax.saxutils import escape

FOLDER = 'C:/Users/Shugu/OneDrive/short videos/001-磨耳朵'
DOCX = FOLDER + '/磨耳朵.docx'
EPS = ['058', '059', '060', '061']            # ← 要追加的集号(对应 FOLDER/NNN.srt)

RPR = '<w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/><w:lang w:val="x-none"/></w:rPr>'
def para(text=''):
    sp = '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
    if text == '':
        return '<w:p><w:pPr>%s%s</w:pPr></w:p>' % (sp, RPR)
    return ('<w:p><w:pPr>%s%s</w:pPr><w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % (sp, RPR, RPR, escape(text)))

def parse_srt(path):
    lines = open(path, encoding='utf-8', errors='ignore').read().splitlines()
    def ms(ts):
        m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', ts.strip())
        h, mi, s, x = m.groups()
        return int(h)*3600000 + int(mi)*60000 + int(s)*1000 + int(x.ljust(3, '0')[:3])
    out = []; i = 0
    while i < len(lines):
        if '-->' in lines[i]:
            a, b = lines[i].split('-->'); j = i+1; buf = []
            while j < len(lines) and lines[j].strip() != '':
                buf.append(lines[j].strip()); j += 1
            out.append((ms(a), ms(b), ' '.join(buf))); i = j
        else:
            i += 1
    return out

def reflow_srt(blocks):
    out, cur, curw, prev = [], [], 0, None
    for s, e, t in blocks:
        w = len(t.split()); gap = (s - prev) if prev is not None else 0
        if cur:
            if gap >= 1500: out.append(' '.join(cur)); out.append(''); cur, curw = [], 0
            elif gap >= 700 or curw + w >= 18: out.append(' '.join(cur)); cur, curw = [], 0
        cur.append(t); curw += w; prev = e
    if cur: out.append(' '.join(cur))
    res = []
    for l in out:
        if l == '' and (not res or res[-1] == ''): continue
        res.append(l)
    while res and res[-1] == '': res.pop()
    return res

shutil.copyfile(DOCX, DOCX + '.bak')
z = zipfile.ZipFile(DOCX)
xml = z.read('word/document.xml').decode('utf-8')
chunks = []
for n in EPS:
    chunks.append(para('')); chunks.append(para(n))
    for l in reflow_srt(parse_srt('%s/%s.srt' % (FOLDER, n))):
        chunks.append(para(l))
new = xml.replace('<w:sectPr', ''.join(chunks) + '<w:sectPr', 1)
buf = io.BytesIO(); zo = zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED)
for it in z.infolist():
    zo.writestr(it, new.encode('utf-8') if it.filename == 'word/document.xml' else z.read(it.filename))
zo.close(); z.close(); open(DOCX, 'wb').write(buf.getvalue())
print('appended:', EPS)
