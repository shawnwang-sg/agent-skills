---
name: moerduo-collection
description: 整理「磨耳朵」英语听力跟读素材库。两件事:(A) 把桌面上的单集文件夹(如「058 transform your finances」)搬运并重命名进磨耳朵合集目录;(B) 维护磨耳朵合集 Word 文档(磨耳朵.docx)——按集号重排、把碎片字幕重排成阅读友好的逐行文稿、干净重建。触发词:「整理磨耳朵」「搬进磨耳朵」「磨耳朵合集」「磨耳朵docx」「磨耳朵重排」「magnetic ear」,或用户指着 001-磨耳朵 文件夹/磨耳朵.docx 让你整理、重命名、重排、合并、补集。
---

# 磨耳朵素材库整理 Skill

「磨耳朵」= 英语听力跟读素材。每一集有音视频 + 字幕 + 文稿,汇总进一个合集 Word 文档供跟读。

**关键路径**
- 合集目录(目标):`C:\Users\Shugu\OneDrive\short videos\001-磨耳朵`
- 合集文档:`<合集目录>\磨耳朵.docx`
- 单集来源:桌面文件夹,命名如 `NNN <英文标题>`(例:`058 transform your finances`)

**Bash 红线(两种操作都适用,违反会触发手动确认)**
- 绝不用 `cd` 和写操作(`mv`/`cp`/`>`/`awk>f`)链在一起 → 一律用绝对路径。
- 写操作目标不能用通配符 `*`(读操作如 `cat in* > out` 可以)。显式列文件名。

---

## 模式 A — 搬运 + 重命名单集进合集

### 命名规则(核心:只保留数字前缀)
把一集的所有文件统一改名为 `NNN.<原扩展名>`:
- `058 transform your finances.mp3` → `058.mp3`,`.mp4`/`.q99` 同理。
- **文件名不含数字时**(如 059 文件夹里文件叫 `tt合集01.*`)→ 用**文件夹的数字前缀**命名为 `059.*`。

### 保留 / 丢弃
| 处理 | 文件 |
|------|------|
| ✅ 搬并改名 `NNN.ext` | `.mp3` `.mp4` `.q99`、**merged 字幕**、**文稿 `.docx`** |
| ✅ 多版本字幕只留 merged | `NNN_merged.srt` → `NNN.srt`;**原始 `.srt` 不搬**(丢弃) |
| ❌ 不搬 | `.pdf`、`*_merged.stripped.txt`(中间产物)、`temp/`(工作目录) |

### 冲突处理
目标已存在同名(常见 `NNN.q99`)→ 直接覆盖(`mv -f`)。

### 执行方式
- 用 `mv -f`(搬运 = move),逐个**显式绝对路径**,用 `&&` 串联,**不要 cd**。
- 搬完桌面会残留 原始 `.srt` + `temp/`,告知用户由其决定是否删。
- 范例命令见 `scripts/move_episode.sh`(模板,按需替换路径)。

### 搬完后核对
列目标目录确认 `NNN.*` 齐全;列桌面残留并报告。

---

## 模式 B — 磨耳朵.docx 文档格式规范

合集文档是一份**单栏、带章标题、每章独立分页、首页自动目录**的跟读稿(v2 格式;v1 是两栏 10pt 无标题的旧格式,已弃用)。

**页面 / sectPr(单栏)**
- 纸张 US Letter:`<w:pgSz w:w="12240" w:h="15840"/>`
- **单栏**:`<w:cols w:space="720"/>`(不要 `w:num="2"`)
- 边距:`<w:pgMar w:top="1440" w:right="1080" w:bottom="1440" w:left="1080" w:header="720" w:footer="720"/>`(上下 1″、左右 0.75″)

**章标题(每章一个,进目录)**
- 文本 = `NNN　标题`(全角空格分隔,如 `057　直接的权力`)。**标题 ≤10 个汉字**,读该集内容后拟定(见模式 C)。
- 用 `Heading1` 样式 + `<w:pageBreakBefore/>` + `<w:outlineLvl w:val="0"/>` + 居中加粗 16pt(`sz=32`)。pageBreakBefore 实现「每章独立分页」,outlineLvl/Heading1 让 TOC 域能收录。
- styles.xml 若无 `Heading1` 样式,注入一个(`name=heading 1`,`outlineLvl 0`,`b`,`sz 32`)。

**正文行**:字号 **22 半角点(=11pt)**;`spacing after=40 line=264 lineRule=auto`;每意群行一段,长停顿处空段分段。

**首页目录(TOC 域 + 自动页码)**
- 封面行:`磨耳朵 · 英语跟读合集`(22pt 粗)、`目录`(16pt 粗)、一行提示「页码未显示请按 F9 更新域」。
- TOC 域:`<w:fldSimple w:instr=' TOC \o "1-1" \h \z \u '>…占位…</w:fldSimple>`(instr 用单引号包,内含双引号)。
- **关键**:改 `word/settings.xml`,在 `<w:settings…>` 后插 `<w:updateFields w:val="true"/>` —— Word 打开时自动重算目录与页码。

**段落 XML 模板**
```
正文段: <w:p><w:pPr><w:spacing w:after="40" w:line="264" w:lineRule="auto"/><w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:pPr><w:r><w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr><w:t xml:space="preserve">{escape(文本)}</w:t></w:r></w:p>
章标题: <w:p><w:pPr><w:pStyle w:val="Heading1"/><w:pageBreakBefore/><w:outlineLvl w:val="0"/><w:jc w:val="center"/><w:spacing w:before="120" w:after="160"/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:pPr><w:r><w:rPr><w:b/><w:sz w:val="32"/></w:rPr><w:t xml:space="preserve">{escape(NNN　标题)}</w:t></w:r></w:p>
```

**实现方式**:不用 docx-js;读 `磨耳朵.docx`(zip)→ 重写 `word/document.xml`(整段 body + 单栏 sectPr)、按需补 `styles.xml`(Heading1)和 `settings.xml`(updateFields)→ 重新打包,其余条目原样保留。**整套见 `scripts/build_collection.py`**。

> ⚠️ **文件锁**:`磨耳朵.docx` 在 Word 里打开时会被锁(`PermissionError`),无法覆盖。写之前先 `open(path,'r+b')` 探测;锁住就让用户关掉 Word(并等 OneDrive 同步完),或先写到临时文件验证、解锁后再覆盖。

---

## 模式 C — docx 整理:重排 / 重排版 / 重建

### 通用铁律
1. **改写前先备份**:`cp -f 磨耳朵.docx 磨耳朵.docx.bak`。
2. **逐字不改字面**(用户偏好「只重组不动字面」):合并/拆行时**词、大小写一律不动,不增不删,不加标点**。唯一允许的编辑是把相邻碎片行用**单个空格**连接、把一段话拆成多行。
3. **保留对话分隔**:对话/问答的换行尽量保留,别把不同说话人糊成一行。
4. **集号顺序** = 数字升序 001→061。
5. 每集**文本来源优先级**:干净的 `NNN.srt`(merged)> docx 里该集标记下的内容。

### 阅读友好重排(把碎片字幕 → 意群行)
目标:每行是一个完整可跟读的意群(约 10–18 词),长停顿处空行分段。

- **有 srt(带时间戳)的集**——用时间戳断行:
  - 累积块,遇到 `块间间隔 ≥ 1.5s` → 结束当前行并插入**空段**(分段);
  - 遇到 `间隔 ≥ 0.7s` 或 `累积 ≥ 18 词` → 结束当前行(不分段);
  - 已是整句的 srt(每块就 ~17 词)→ 基本原样各自成行。
- **仅 docx(无时间戳)的集**——按词数合并:相邻行累积到 `> 16 词` 就断行;对话的短促行(≤3–4 词)倾向各自成行。

### 干净重建(当 docx 结构已缠乱时)
磨耳朵.docx 历史上出现过结构损坏:**重复的空集号块**(垃圾)、某个集号下塞着**多集揉成一坨、边界丢失的大块**。这种情况**不要在烂结构上硬改**,而是基于 `.bak` 重建:
1. 解析 `.bak`,取每个集号**首次出现**下的内容(`002–032` 等仅在 docx 的集从这里取)。
2. 有 srt 的集从 srt 重排(更干净,带时间戳)。
3. **删掉**重复空集号 / 垃圾块。
4. **边界丢失、无 srt、拆不出来的内容** → 原样塞进文末「**待拆分附录**」(也作为一章,带标题进目录),一字不丢,等以后补了 srt 再归位。**绝不为了整齐而丢内容**。
5. 按 001→061 顺序重排正文,附录在最后,套用模式 B 的 v2 排版(章标题 + 分页 + 目录)。
6. 写完做校验:`xml.dom.minidom.parseString` 检查 document/styles/settings well-formed;确认章标题数 = 章数、`pageBreakBefore` 数相符、TOC 域存在;抽查 2–3 集内容。

### 章标题怎么拟(≤10 个汉字)
- 每章一个,**读该集内容**后用中文概括主题,4–7 字最佳、**不超过 10 字**。是对话场景就抓情境(如 `谁来看孩子`、`餐厅等位`),是观点/演讲就抓主旨(如 `悲观的毛病`、`金钱与情绪`)。
- 标题只是导航/概览,**不算改原文**;正文仍逐字不动。
- 批量拟标题时,先把每章前 ~14 行抽到一个文本文件通读,再一次性产出标题表(见 `build_collection.py` 里的 `TITLES` 字典)。

**完整实现见 `scripts/build_collection.py`**(v2 全量重建:srt+.bak 取材、重排、章标题+分页、TOC 域、附录、锁检测,一步到位)。日常基本只用它——改完 srt 或标题后重跑即可。`scripts/append_to_collection.py` 是旧的「仅追加」脚本(v1 格式,无标题/分页),已被全量重建取代,保留备查。

---

## 关于 q99 文件(已知限制)
`.q99` 是「Q99 Courseware」软件的专有格式,字幕文本**加密存储**(熵≈8),逆向取不出 srt;文件里只内嵌了 MP3 音频。补缺集的字幕只能:① 用 Q99 软件本身导出,或 ② 用 Whisper 等转写 `.mp3`。别试图逆向解密 q99。

## lrc → srt(顺带)
若遇到 `.lrc`(`[H:MM:SS.cc]文本`),每行转一个 srt 块:起始=本行时间戳,结束=下一行时间戳(最后一块 +4s),厘秒补成毫秒。脚本见 `scripts/lrc2srt.py`。
