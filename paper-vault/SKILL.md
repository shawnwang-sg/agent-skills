---
name: paper-vault
description: >-
  把一篇论文「加工」成本地静态、翻页式、中英对照的三遍法阅读库（鸟瞰/理解/吃透）。
  触发：当用户给出 arxiv 链接 / 本地 PDF / 论文截图 / 飞书文档，并说「加工这篇」「读这篇论文」
  「加进阅读库」「做成三遍法」「paper-vault」「整理成中英对照」时。区别于普通「总结一下」
  （本 skill 要保留论文原文句段、逐级加深、生成可翻页站点）和低密度幻灯片。仅本地私用，
  不公开发布版权全文。
---

# paper-vault

把论文加工成 **L1 论文库 → L2 单篇三模式门户 → L3 翻页阅读器** 的本地阅读库。
一份引擎 `build.py`，三种入口（本 skill / `AGENTS.md` / 手动直跑）。

## 第一条规矩

- **标题用论文原始英文名 + 作者**，不译不改。
- **严格中英对照（硬规则）**：每个内容块**必须同时给 en（原文句段）+ zh（准确翻译）**，缺一不可（`code`/`math` 例外）。
  build 会做「中英对照校验」，缺对照即报错并以退出码 1 结束。别把原文改写成摘要。
- 三模式是 **三档原文密度**：鸟瞰≈1/5、理解≈1/3、吃透≈1/2，**允许 ±20% 误差**。
  在 `meta.source_words` 写全文英文词数；build 会自检并标 OK/LOW/HIGH，超界则**修订该模式重跑，最多 2 次**。
- **仅本地私用**：含论文全文的内容只进 private 私库的 `reading` 分支，绝不推公开 `master`。

## 四步工作流（§详见 references）

1. **抓全文 + 结构 + 图**（见 `references/fetch.md`）。
2. **写 `papers/<slug>/paper.json`**：meta（原名 / 作者 / source / url / 分类 / 300–500 字中文概述，结论先行 / **source_words 全文英文词数**）
   + 三模式内容（见 `references/modes.md` 与 `references/schema.md`；吃透模式固定三段、≥10 个 qa、尽量保留原文）。
   图用 `figure`（优先原图 `src`，下不到就内联 `svg` 重绘）。
3. **生成 + 自检**：`python3 build.py --vault <vault>` 会打印各模式比例 OK/LOW/HIGH。
   若有 LOW/HIGH，修订对应模式（LOW 补原文、HIGH 精简）重跑，**最多 2 次**（用 `--strict` 可让超界返回退出码 1）。
4. **打开** `<vault>/index.html`。
   reading 分支上 `git add -f papers index.html assets` 提交；引擎改动走 master。

## 站点自带能力（生成后即有，无需额外说明）

- L2 顶栏：模式切换（鸟瞰/理解/吃透）、语言切换（对照/原文/中文）、目录、A−/A+ 字号、主题◐、全屏。
- 键盘：`←/→` 翻页、`1/2/3` 切模式、`L` 语言、`T` 目录、`F` 全屏、`Esc` 关目录；触摸横滑翻页。
- L1：分类 chip 筛选、卡片折叠展开概述、三套主题（暖纸/纯白/暗色）。

## 按需读表（references/）

- `fetch.md` — 抓取规范（arxiv HTML 优先、PDF、截图、飞书、图表）。
- `modes.md` — 三模式内容规范（比例目标 + 结构）。
- `schema.md` — paper.json / block 数据模型。
- `classify.md` — 分类规范（动态 2–6 字中文类目，复用优先）。

## 合规

论文全文 + 翻译 = 版权/演绎内容，**仅本地私用**。`.gitignore` 默认只提交引擎、忽略论文内容；
公开仓只含生成器。重写代码用 MIT；保留 frontend-slides 的 MIT 署名（见 `NOTICE-frontend-slides-MIT.txt`）。
