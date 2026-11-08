---
name: quote-collection-publish
description: 把名言/金句/摘抄 txt（如 D:\douyin\厉害文字集锦.txt）整理成一套「集锦出版物」：分类+小主题排序、拆条、去重、润色（附对照页）、A4 双栏分页 HTML/PDF（一页 = 一集）、每集一个 MP3 朗读音频（edge-tts 云希）、TXT 定稿、MOBI 电子书、单独打印页，最后汇总到桌面。触发词：「整理成集锦」「集锦出版」「做成 PDF/MP3/电子书」「名言做成音频」「一页一集」「双栏 PDF」「做 mobi」「厉害文字集锦」，或用户丢来一个名言/摘抄 txt 让你分类、润色、出 PDF、出音频、出电子书——即使只要其中一样（比如只要 MP3 或只要 PDF），也用这个 skill，因为几样产物的分集和分段必须一致。文字壁纸用 quote-wallpaper，导入 growth-planner 嘉言钞用 jiayanchao-import。
---

# 名言集锦出版

把一堆零散的名言摘抄，做成能读、能听、能打印的一套东西。核心约束是**四样产物严格对齐**：PDF 一页 = 一集 MP3 = TXT/MOBI 里的一集，分段规则也完全相同（`scripts/zh_lines.py` 的 `paras()`）。所以任何改动文字的操作，都要回到 `collection.json` 改，再从头重新生成下游产物。

依赖：Python（edge-tts、pymupdf）、ffmpeg/ffprobe、Chrome 或 Edge、Calibre（做 MOBI 时；没装就 `winget install --id calibre.calibre -e --silent --accept-package-agreements --accept-source-agreements`）。
运行 Python 时都加 `PYTHONIOENCODING=utf-8`，否则中文输出乱码。

## 工作目录约定

- 工作目录：放在源 txt 旁边的 `<源目录>\<标题>_制作\`（例：`D:\douyin\厉害文字集锦_制作\`），中间文件（raw_items.json、collection.json、pages.json、ep_tmp、book）都放这里。
- 成品输出目录：源 txt 所在目录；音频放 `<源目录>\音频\`。
- 最后用 `collect.py` 复制到桌面「<标题>」文件夹（用户要求「产物都放在桌面」）。

## 用户偏好速查（来自用户在原会话里的明确要求和纠正）

| 方面 | 要求 |
|---|---|
| 分类 | 约 10 个大类，名字形如「一、行动·自律·成长」；每类再分 3～7 个小主题，**意思相近的话放在一起**；类内可随意洗牌，不跨类 |
| 拆条 | 一条里混着几段不同来源/不同意思的，按文义拆开（用户特别强调「注意鉴别文字」） |
| 删 | 评论区口水话（「天啊好喜欢这句」「ps：…」「后记：…」「（今日经历）」）、邮箱链接图片占位；用户点名删的整篇 |
| 去重 | 新增素材与原集锦去重，素材内部也去重 |
| 润色 | 名言、古文、诗词、书摘、引号里的原话**一字不动**；只改作者自己写的错别字、病句、残缺句、读不顺的地方，以及不方便朗读的写法（斜杠、「1，2，」编号、括号注释）；观点和篇幅不变；偏激语气和粗话保留。改完必须出**润色对照页** |
| 长文 | 不要拆到两集；单篇太长时，用户可能要求「保留最重要的段落和含义，改写成原文三分之一」 |
| 摘出 | 用户点名的条目（如「哈佛教授 14 种实用方法」）从集锦和音频里拿掉，单独做一张 A4 打印页，并放进电子书附录 |
| PDF | A4 **双栏 9.5 号**宋体；**一页只放一个类别**；每页底部留一点空白（约 7%），不要塞满到底，也不要大片空白；内容少的页自动放大字号（≤10.5pt）、拉开篇间距 |
| 换行 | 原文已分段的保持；单段超过 60 字的按句号/问号/叹号/分号断开，太短的并到前句，短文≤4 段、长文≤6 段；引号没闭合不断开。「要有最基础的换行，但是不要太多」 |
| MP3 | 一页 = 一集，每集 3～5 分钟，**6 分钟以内都接受**；云希 +8%；条与条之间停 2 秒、段与段之间停 1 秒（用户嫌「段之间停顿太少听不出来」后定的）；一篇内要连贯，不要断句太碎；英文原句不读；柔和底乐 |
| MOBI | 「正常排版即可」；目录两级：类别 → 集 |
| 命名 | MP3：`01_一、行动·自律·成长_第1集.mp3`；成品：`<标题>.pdf/.mobi/.txt`、`<条目名>_打印页.pdf` |
| 流程 | 先出 HTML 预览让用户看，确认后再出 PDF/MP3；拿不准的细节先问 |

## 步骤

### 1. 拆条 + 去重
```bash
PYTHONIOENCODING=utf-8 python ~/.claude/skills/quote-collection-publish/scripts/parse_txt.py <原集锦.txt> [新增素材.txt] --out <工作目录>/raw_items.json
```
读 raw_items.json，逐条看：
- 有没有该拆没拆的（几句话来自不同出处、意思不相干）——拆开；
- 口水话、评论区附言——删掉；
- 去重结果是否合理（`dups` 列表）。

### 2. 分类、排小主题 → 写 collection.json
由你按内容判断（不要照搬原 txt 的分类）。格式：
```json
{
  "title": "厉害文字集锦",
  "cats": [
    {"name": "一、行动·自律·成长",
     "items": [{"t": "正文，段落之间用空行", "topic": "行动胜过空想"}, ...]}
  ],
  "extract": {"title": "14 种实用方法", "file": "哈佛教授14种实用方法", "items": ["…"]}
}
```
- items 的顺序就是最终顺序：同一小主题的条目放在一起，小主题之间也按意思衔接。
- `extract` 可选，没有摘出条目就不写。
- 条目很多时（几百条），可以按类别分给子任务并行分类/润色，每个子任务只处理一个类别，返回 JSON。

### 3. 润色（用户要求时，或首次整理时主动提出）
规则见上表。条目多时按类别分给子任务并行做，每个子任务返回 `[{"k": 序号, "new": "改后", "why": "一句话理由"}]`，并让它们**标出改动较大、需要用户确认的几条**（补意、改结构、猜原意）。把结果并进 collection.json，再把改动条目整理成 changes.json 生成对照页：
```bash
PYTHONIOENCODING=utf-8 python ~/.claude/skills/quote-collection-publish/scripts/polish_diff.py <工作目录>/changes.json --title <标题> --out <输出目录>
```
向用户汇报：改了多少条、几类典型改动各举一例、需要他确认的几条。

### 4. 分页 HTML（预览，先给用户看）
```bash
PYTHONIOENCODING=utf-8 python ~/.claude/skills/quote-collection-publish/scripts/build_pages.py <工作目录>/collection.json --out <输出目录>
```
会在输出目录生成 `<标题>_分页.html` 和打印页 HTML，在工作目录（collection.json 旁边）生成 pages.json。脚本末尾打印每页的预估分钟、填充率和溢出页。
- 检查：溢出页应为「无」；每页 3～6 分钟。某类最后一页太空或某页超过 6 分钟，告诉用户并给方案（压缩某篇长文、调整小主题）。
- 用户改了任何文字 → 改 collection.json → 重跑这一步 → 再重跑下游所有产物（分页可能变，MP3 必须跟着重做）。

### 5. PDF
```bash
PYTHONIOENCODING=utf-8 python ~/.claude/skills/quote-collection-publish/scripts/export_pdf.py <输出目录>/<标题>_分页.html <输出目录>/<标题>.pdf [<打印页.html> <打印页.pdf>]
```
页数应等于 pages.json 的页数，尺寸 210×297。抽 2～3 页用 pymupdf 渲染成图片看一眼。

### 6. MP3（耗时长，放后台跑）
```bash
PYTHONIOENCODING=utf-8 python ~/.claude/skills/quote-collection-publish/scripts/make_episode.py <工作目录>/pages.json --out <源目录>/音频 all
```
- 第一次做时先只出第 1 集给用户听（把 `all` 换成 `1`），确认语速和停顿再跑全部。
- 已存在的文件会跳过；分页变了要先删旧 mp3 再跑。
- 跑完用 ffprobe 核对每集时长和 pages.json 的 `min` 差不多（±1 分钟内）。

### 7. TXT + MOBI
```bash
PYTHONIOENCODING=utf-8 python ~/.claude/skills/quote-collection-publish/scripts/make_book.py <工作目录>/pages.json --out <输出目录>
```
脚本会把 MOBI 转回 epub 自检目录条数，应约等于「类别数 + 集数 + 附录」。

### 8. 汇总到桌面
```bash
PYTHONIOENCODING=utf-8 python ~/.claude/skills/quote-collection-publish/scripts/collect.py --title <标题> --src <输出目录> --audio <源目录>/音频
```
如果同时做了文字壁纸（quote-wallpaper），壁纸放进同一个桌面文件夹的「壁纸」子文件夹。

## 汇报格式
用一张表列出桌面文件夹里每样产物：文件、内容（页数/集数/时长范围/目录结构）。另外说明：哪些只抽查了、没逐一核对（例如 PDF 抽看了哪几页，MP3 的听感需要用户自己听）。

## 常见坑
- Chrome 无头模式偶尔不返回结果：重跑一次；仍不行检查 `qcp_prof` 临时配置目录是否被占用。
- Calibre 目录 XPath 要写 `//*[name()='h1']`，写 `//h:h1` 会认不出目录（脚本已处理）。
- 生成中途改了分段规则或文字 → PDF、MP3、TXT、MOBI 全部重做，保证四者一致。
- 旧 MP3 被播放器占用删不掉时，先换名另存，最后再清理。
