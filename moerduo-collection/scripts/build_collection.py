# -*- coding: utf-8 -*-
"""磨耳朵.docx 完整重建(v2 格式):单栏 + 每章标题 + 每章独立分页 + 首页自动目录(TOC域)。
   来源:srt(有则优先,带时间戳)+ .bak(仅-docx 的集 002–032);边界丢失的大块入文末附录。
   逐字不改字面。每次结构损坏情况不同 → 按实际调整 TITLES / body_nums / 035 大块定位。
   用法: python build_collection.py [输出路径]   不给则写正式文件(需先关闭 Word)。"""
import zipfile, re, io, os, sys
from xml.sax.saxutils import escape

FOLDER = 'C:/Users/Shugu/OneDrive/short videos/001-磨耳朵'
BAK = FOLDER + '/磨耳朵.docx.bak'
OUT = sys.argv[1] if len(sys.argv) > 1 else FOLDER + '/磨耳朵.docx'

# 每章英文标题(简洁短语,读内容后拟;新增/变动集在此补)
TITLES = {
 '001':'Watch the Kids','002':'Reading People','003':'The Ugly Duckling','004':'By Chance',
 '005':'The Reservation','006':'Speak Your Mind','007':'The Rich Aunt','008':'The Yale Email',
 '009':'Caged Birds','010':'Resilience','011':'Happiness Trap','012':'A Crazy Dream',
 '013':"You're a Survivor",'014':'An Apology','015':'Thanksgiving Help','016':'Fishing with Dad',
 '017':'Meant to Be','018':'Kitchen News','019':'Eat Your Greens','020':'Culture Shock',
 '021':'Sales Psychology','022':'At the Pharmacy','023':'Gym Tour','024':'Birds of a Feather',
 '025':'True Confidence','026':'The Waitlist','027':'Hotel Checkout','028':'Asking Directions',
 '029':'Being Real Online','030':'Be Persistent','031':'Bouncing Back','032':'Picking a Pillow',
 '033':'Trying Blush','034':'Being Likable','039':'The Busy Trap','040':'Dating and Money',
 '042':"Steve's Way",'044':'A Framework','046':'Beat Self-Doubt','047':'Pessimism',
 '048':'Find Your Passion','049':'Table for One','050':'Meet Seattle','051':'Seattle Landmarks',
 '052':'Seattle Records','053':'Pickup Basketball','054':'English in India','055':'First Day in China',
 '056':'Secret Menu','057':'Direct Power','058':'Money & Dopamine','059':'Wave or Particle',
 '060':'Feeling Safe','061':'Money & Emotion',
}
BODY_NUMS = ['%03d' % i for i in range(1, 35)] + ['039', '040', '042', '044'] + ['%03d' % i for i in range(46, 62)]

# 锁检测
if os.path.exists(OUT):
    try: open(OUT, 'r+b').close()
    except PermissionError:
        sys.exit('LOCKED: %s 正被占用(关闭 Word / 等 OneDrive 同步),或给个临时输出路径作参数。' % OUT)

# ---- 解析 .bak ----
z = zipfile.ZipFile(BAK)
xml = z.read('word/document.xml').decode('utf-8')
def ptxt(p): return ''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>', p, re.S)).strip()
dl = [ptxt(p) for p in re.findall(r'<w:p[ >].*?</w:p>', xml, re.S)]
marks = [(i, l) for i, l in enumerate(dl) if re.fullmatch(r'\d{3}', l)]
docx_content = {}
for k, (i, l) in enumerate(marks):
    end = marks[k+1][0] if k+1 < len(marks) else len(dl)
    if l not in docx_content:
        docx_content[l] = [dl[j] for j in range(i+1, end) if dl[j].strip()]
i035 = [i for i, l in marks if l == '035'][0]
nxt = [i for i, l in marks if i > i035][0]
blob = [dl[j] for j in range(i035+1, nxt) if dl[j].strip()]

# ---- 重排 ----
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
def get_lines(n):
    p = '%s/%s.srt' % (FOLDER, n)
    return reflow_srt(parse_srt(p)) if os.path.exists(p) else reflow_docx(docx_content.get(n, []))

# ---- XML 段落 ----
def body_para(text):
    sp = '<w:spacing w:after="40" w:line="264" w:lineRule="auto"/>'
    rpr = '<w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>'
    if text == '': return '<w:p><w:pPr>%s%s</w:pPr></w:p>' % (sp, rpr)
    return '<w:p><w:pPr>%s%s</w:pPr><w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>' % (sp, rpr, rpr, escape(text))
def title_para(text):
    rpr = '<w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>'
    return ('<w:p><w:pPr><w:pStyle w:val="Heading1"/><w:pageBreakBefore/><w:outlineLvl w:val="0"/>'
            '<w:jc w:val="center"/><w:spacing w:before="120" w:after="160"/>%s</w:pPr>'
            '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>' % (rpr, rpr, escape(text)))
def center(text, sz, bold=False):
    b = '<w:b/>' if bold else ''
    rpr = '<w:rPr>%s<w:sz w:val="%d"/><w:szCs w:val="%d"/></w:rPr>' % (b, sz, sz)
    return ('<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="120"/>%s</w:pPr>'
            '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>' % (rpr, rpr, escape(text)))

chunks = [center('磨耳朵 · 英语跟读合集', 44, True), center('目录', 32, True),
          center('（若目录页码未显示，请在 Word 中全选后按 F9 更新域）', 18),
          '<w:p><w:pPr><w:spacing w:after="0" w:line="276" w:lineRule="auto"/></w:pPr>'
          '<w:fldSimple w:instr=\' TOC \\o "1-1" \\h \\z \\u \'>'
          '<w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:t>正在生成目录…请更新域</w:t></w:r></w:fldSimple></w:p>']
for n in BODY_NUMS:
    chunks.append(title_para('%s  %s' % (n, TITLES.get(n, ''))))
    chunks += [body_para(l) for l in get_lines(n)]
chunks.append(title_para('Appendix (To Split)'))
chunks.append(body_para('原 docx 中 035 标记后的混合文本块,集号边界已丢失,原样保留、未改动,供后续拆分。'))
chunks.append(body_para(''))
chunks += [body_para(l) for l in blob]

sectpr = ('<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
          '<w:pgMar w:top="1440" w:right="1080" w:bottom="1440" w:left="1080" w:header="720" w:footer="720" w:gutter="0"/>'
          '<w:cols w:space="720"/><w:docGrid w:linePitch="360"/></w:sectPr>')
new_doc = xml[:xml.index('<w:body>')+8] + ''.join(chunks) + sectpr + '</w:body></w:document>'

styles = z.read('word/styles.xml').decode('utf-8')
if 'w:styleId="Heading1"' not in styles:
    styles = styles.replace('</w:styles>',
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>'
        '<w:pPr><w:keepNext/><w:outlineLvl w:val="0"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style></w:styles>')
try:
    settings = z.read('word/settings.xml').decode('utf-8')
    if '<w:updateFields' not in settings:
        settings = re.sub(r'(<w:settings[^>]*>)', r'\1<w:updateFields w:val="true"/>', settings, count=1)
except KeyError:
    settings = None

buf = io.BytesIO(); zo = zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED)
for it in z.infolist():
    fn = it.filename
    data = (new_doc.encode('utf-8') if fn == 'word/document.xml'
            else styles.encode('utf-8') if fn == 'word/styles.xml'
            else settings.encode('utf-8') if fn == 'word/settings.xml' and settings
            else z.read(fn))
    zo.writestr(it, data)
zo.close(); z.close(); open(OUT, 'wb').write(buf.getvalue())
print('WROTE', OUT, '| chapters', len(BODY_NUMS), '+ appendix')
