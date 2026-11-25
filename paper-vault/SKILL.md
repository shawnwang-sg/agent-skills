---
name: paper-vault
description: >-
  把一篇论文「加工」成本地静态、翻页式、中英对照的三遍法阅读库（鸟瞰/理解/吃透），
  按 Keshav《How to Read a Paper》的三遍法逐遍产出，带原文逐字核验和质量门。
  触发：当用户给出 arxiv 链接 / 本地 PDF / 论文截图 / 飞书文档，并说「加工这篇」「读这篇论文」
  「加进阅读库」「做成三遍法」「精读这篇」「重做这篇」「paper-vault」「整理成中英对照」时。
  区别于普通「总结一下」（本 skill 要保留论文原文句段、逐遍加深、生成可翻页站点）和低密度幻灯片。
  仅本地私用，不公开发布版权全文。
---

# paper-vault

把论文加工成 **L1 论文库 → L2 单篇三模式门户 → L3 翻页阅读器** 的本地阅读库。
一份引擎 `build.py` + 质量门 `validate.py`，三种入口（本 skill / `AGENTS.md` / 手动直跑）。

## 硬规则

1. **三遍 = 三次不同的阅读，各有固定产出**（详见 `references/three-pass.md`）：
   - 鸟瞰：决定值不值得读；另有一页「技术分析与基础概念」，先讲读懂这篇论文需要的基础概念，再分析它的技术方案。
   - 理解：抓主线和证据，全部图表都要讲。
   - 吃透：虚拟重做，包括推演、分类问答，以及强项、弱项和隐藏假设。
   原文比例只是其中一项检查。
2. **原文必须是真原文。** 原文块标 `origin: "paper"` 和 `source_page`，能在 PDF 那一页逐字找到，不能改写、不能重复。讲解块标 `origin: "editorial"`，不算进原文比例。
3. **先有原始 PDF，再动笔。** 先准备好 `source.pdf`、`source.txt`、`source.json`；全文词数从 PDF 提取，不手填。
4. **图表全覆盖。** 每张编号图和表都要用原页裁图，在 `assets/provenance.json` 记页码、裁框和哈希，并写解读。
5. **一篇一篇做，先出样稿。** 新批次先做 1 篇给用户看，认可后再继续。每篇单独校验、单独提交；禁止多篇一起生成、一起提交。
6. **不合格不算完成。** `reading_status` 只能由 `validate.py --write` 写入。没通过就是 `needs_rework`。「下载完成」「页面生成成功」都不算精读完成。
7. **标题用论文原始英文名和作者**，不译不改。每个内容块中英成对。
8. **仅本地私用**：含论文全文的仓库必须是 private，不公开发布。

## 工作流

1. **抓原文**：下载 PDF，提取文本、页数、词数，裁出全部图表（见 `references/fetch.md`）。
2. **写 `papers/<slug>/paper.json`**：
   - meta：原名、作者、source、url、分类、300–500 字中文概述（结论先行）、`source_words`。
   - 按 `references/three-pass.md` 依次写鸟瞰、理解、吃透，数据格式见 `references/schema.md`。
3. **过质量门**：`python validate.py --vault <vault> <slug>`，按报告补齐，直到通过（门槛见 `references/quality-gates.md`）。
   通过后运行 `validate.py --write`，写入审核记录和状态。
4. **生成**：`python build.py --vault <vault>`（加 `--strict` 时，质量门不合格以退出码 1 结束）。打开 `<vault>/index.html` 检查。
5. **提交**：这一篇单独提交。

## 站点自带能力（生成后即有，无需额外说明）

- **L2 顶栏**：模式切换（鸟瞰 / 理解 / 吃透）、语言切换（对照 / 原文 / 中文）、目录、A− / A+ 字号、主题◐、全屏、原文 PDF。
- **键盘**：`←/→` 翻页，`1/2/3` 切模式，`L` 语言，`T` 目录，`F` 全屏，`Esc` 关目录；触摸屏横滑翻页。
- **我的概括**：理解模式每一节末尾有概括框；鸟瞰的一句话结论先遮住，自己写完再看。「提交并评分」由 `serve.py` 调本机已登录的 `claude` 打 1–10 分，并指出说对的、漏掉的（附原文）、说错的，给参考概括。记录存在 `~/OneDrive/self-meta/paper-vault/notes.json`（环境变量 `PAPER_VAULT_META` 可改），不进论文库仓库。
- **划词收藏**：在英文原文上选中文字，弹出「收藏词 / 收藏句」，经 `serve.py` 转给语言教练（lang-coach，默认 `http://127.0.0.1:5310`，`--coach` 可改）：词进单词库的「学术英语」，句子进难句本。
- **L1**：
  - 右上角搜索框（按 `/` 定位）。
  - 左栏「内容 / 会议 / 作者」三种视图。会议页有介绍、CCF 分级、时间地点和链接，资料在 vault 的 `venues.json`；作者页列出库里的论文和合作者。左栏底部是找新论文的友情链接。
  - 每篇论文有 ☆ 收藏和「在读」标签，对应左侧置顶的「★ 收藏」「◔ 正在读」。
  - 左侧分类树可以编辑。
  - 分类树、收藏和在读都存在 `folders.json`；用 `python serve.py` 打开，改动才会存进这个文件。
  - 卡片可折叠，显示概述；三套主题。

## 按需读表（references/）

- `three-pass.md`：三遍各自的目的、必备部分、怎么做。
- `quality-gates.md`：质量门的全部门槛和用法。
- `fetch.md`：抓原文、裁图规范。
- `schema.md`：paper.json 和 block 数据模型（含 `origin`、`source_page`、`kind`、`cat`）。
- `classify.md`：分类规范。

## 合规

论文全文和翻译属于版权或演绎内容，**仅本地私用**。重写的代码用 MIT 许可；保留 frontend-slides 的 MIT 署名（见 `NOTICE-frontend-slides-MIT.txt`）。
