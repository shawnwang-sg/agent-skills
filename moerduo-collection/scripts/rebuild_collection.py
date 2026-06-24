# -*- coding: utf-8 -*-
"""完整重建 磨耳朵.docx 的骨架:从 .bak 取仅-docx 集,从 srt 取干净集,
   按 001→061 重排,垃圾块丢弃,边界丢失/无 srt 的内容塞文末「待拆分附录」。
   这是模板——每次结构损坏情况不同,需按实际调整 body_nums / 来源判定 / 附录范围。
   逐字不改、绝不丢内容。写前已有 .bak 即可。"""
import zipfile, re, io, os
from xml.sax.saxutils import escape

FOLDER = 'C:/Users/Shugu/OneDrive/short videos/001-磨耳朵'
BAK = FOLDER + '/磨耳朵.docx.bak'      # 以备份为重建基准(也用它的 styles)
OUT = FOLDER + '/磨耳朵.docx'

RPR = '<w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/><w:lang w:val="x-none"/></w:rPr>'
def para(t=''):
    sp = '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
    if t == '': return '<w:p><w:pPr>%s%s</w:pPr></w:p>' % (sp, RPR)
    return '<w:p><w:pPr>%s%s</w:pPr><w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>' % (sp, RPR, RPR, escape(t))

# ---- 解析备份:每个集号首次出现下的内容 + 找出缠乱的大块(按实际改) ----
z = zipfile.ZipFile(BAK)
xml = z.read('word/document.xml').decode('utf-8')
paras = re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)
def ptxt(p): return ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)).strip()
dl = [ptxt(p) for p in paras]
marks = [(i, l) for i, l in enumerate(dl) if re.fullmatch(r'\d{3}', l)]
docx_content = {}
for k, (i, l) in enumerate(marks):
    end = marks[k+1][0] if k+1 < len(marks) else len(dl)
    if l not in docx_content:
        docx_content[l] = [dl[j] for j in range(i+1, end) if dl[j].strip()]
# 缠乱大块:示例为 035 标记后到下一个标记之间(按实际定位)
i035 = [i for i, l in marks if l == '035'][0]
nxt = [i for i, l in marks if i > i035][0]
blob = [dl[j] for j in range(i035+1, nxt) if dl[j].strip()]

# ---- 重排函数 ----
def parse_srt(path):
    L = open(path, encoding='utf-8', errors='ignore').read().splitlines()
    def ms(ts):
        m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', ts.strip()); h, mi, s, x = m.groups()
        return int(h)*3600000+int(mi)*60000+int(s)*1000+int(x.ljust(3, '0')[:3])
    out = []; i = 0
    while i < len(L):
        if '-->' in L[i]:
            a, b = L[i].split('-->'); j = i+1; buf = []
            while j < len(L) and L[j].strip(): buf.append(L[j].strip()); j += 1
            out.append((ms(a), ms(b), ' '.join(buf))); i = j
        else: i += 1
    return out
def reflow_srt(bl):
    out, cur, cw, pe = [], [], 0, None
    for s, e, t in bl:
        w = len(t.split()); g = (s-pe) if pe is not None else 0
        if cur:
            if g >= 1500: out += [' '.join(cur), '']; cur, cw = [], 0
            elif g >= 700 or cw+w >= 18: out.append(' '.join(cur)); cur, cw = [], 0
        cur.append(t); cw += w; pe = e
    if cur: out.append(' '.join(cur))
    r = []
    for l in out:
        if l == '' and (not r or r[-1] == ''): continue
        r.append(l)
    while r and r[-1] == '': r.pop()
    return r
def reflow_docx(lines):
    out, cur, cw = [], [], 0
    for t in lines:
        w = len(t.split())
        if cur and cw+w > 16: out.append(' '.join(cur)); cur, cw = [], 0
        cur.append(t); cw += w
    if cur: out.append(' '.join(cur))
    return out

# ---- 正文集号(按实际可用集调整;035-038/041/043/045 入附录) ----
body = ['%03d' % i for i in range(1, 35)] + ['039', '040', '042', '044'] + ['%03d' % i for i in range(46, 62)]
chunks = []
for n in body:
    p = '%s/%s.srt' % (FOLDER, n)
    lines = reflow_srt(parse_srt(p)) if os.path.exists(p) else reflow_docx(docx_content.get(n, []))
    chunks += [para(''), para(n)] + [para(l) for l in lines]
# 附录:原样保留缠乱大块
chunks += [para(''), para('==================== 待拆分附录 ===================='),
           para('原 docx 中边界丢失的混合文本块,原样保留、未改动,供后续拆分。'), para('')]
chunks += [para(l) for l in blob]

new = xml[:xml.index('<w:body>')+8] + ''.join(chunks) + xml[xml.rindex('<w:sectPr'):]
buf = io.BytesIO(); zo = zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED)
for it in z.infolist():
    zo.writestr(it, new.encode('utf-8') if it.filename == 'word/document.xml' else z.read(it.filename))
zo.close(); z.close(); open(OUT, 'wb').write(buf.getvalue())
print('rebuilt body:', len(body), 'appendix lines:', len(blob))
