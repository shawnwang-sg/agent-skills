# paper.json 数据模型（schema）

每篇论文一份 `papers/<slug>/paper.json`（slug = 目录名）。

```jsonc
{
  "meta": {
    "title":    "<论文原始英文名，不译不改>",
    "authors":  "<作者，如 'A. Vaswani et al.'>",
    "source":   "<会议/期刊/年份，可空>",
    "url":      "<原文链接，可空>",
    "category": "<分类，2-6 字中文，见 classify.md>",
    "overview": "<300-500 字中文概述，结论先行>",
    "source_words": 0
  },
  "modes": {
    "skim":   { "label": "鸟瞰", "sections": [ /* section */ ] },
    "grasp":  { "label": "理解", "sections": [ /* section */ ] },
    "master": { "label": "吃透", "sections": [ /* section */ ] }
  }
}
```

- `section` = `{ "title": "<英文>", "title_zh": "<中文>", "blocks": [ /* block */ ] }`。
  一个 section 渲染成 L2 里**一页**（页内可滚动）。
- mode 的 key 固定 `skim` / `grasp` / `master`，label 固定 鸟瞰 / 理解 / 吃透。

## block 类型（每块尽量同时给 en + zh）

| type | 字段 | 渲染 |
|---|---|---|
| `p` | `en`, `zh` | 段落（en 衬线英文 + zh 灰色中文） |
| `h3` | `en`, `zh` | 小标题 |
| `list` | `items:[{en,zh}]` | 无序列表（菱形 bullet） |
| `quote` | `en`, `zh` | 引用块（左竖条） |
| `terms` | `items:[{w,zh,m_en,m}]` | 术语卡网格（`w` 英文词 / `zh` 中文词 / `m_en` 英文解释 / `m` 中文解释）；5C 用它。**解释须中英成对**：给了 `m` 就必须给 `m_en` |
| `qa` | `q_en, q_zh, a_en, a_zh` | 问答卡（Q/A 圆角徽标）；吃透模式用 |
| `figure` | `src` 或 `svg`，`caption_en`, `caption_zh` | 图：优先原图 `src`，否则内联 `svg` 重绘 |
| `math` | `tex` | 行间公式（联网 MathJax 渲染） |
| `code` | `text` | 代码块（等宽） |
| `pagebreak` | — | 在本节内强制分页（多页时页标题加 `(part/parts)`） |

## 渲染约定

- **严格中英对照（硬规则）**：每个内容块必须**同时给 en 与 zh**——`p`/`h3`/`quote` 的 `en`+`zh`、
  `list`/每个 item 的 `en`+`zh`、`terms`/每个 item 的 `w`+`zh`、`qa` 的 `q_en`+`q_zh`+`a_en`+`a_zh`、
  `figure` 的 `caption_en`+`caption_zh`。缺一即不合格：`build.py` 会报「中英对照校验」错误并以**退出码 1** 结束。
  例外：`code`/`math`（无译文）、`terms.m`（中文大白话，无英文对应）。
- 所有 en 文本套 `class="en"`、zh 套 `class="zh"`（供语言切换显隐）。
- **语言卫生（关键，影响原文/中文切换的纯净度）**：
  - 术语卡解释须**中英成对**：`terms.m_en`（英文解释，EN 显）↔ `terms.m`（中文解释，ZH 显）；词头 `terms.w`↔`terms.zh`。
  - `figure.svg` 内的文字标注与 `code.text`（含注释）**不参与 en/zh 显隐**，请一律用**原文语言（英文）**书写；
    中文解释放进 `figure.caption_zh` 或正文 `p` 的 `zh`。否则点「原文」时这些中文会漏出来，破坏学习效果。
- 文本经 HTML 转义；**`figure.svg` 例外**（svg 是可信自产，原样内联）。
- `figure.src` 路径相对该 paper 目录（与 paper.json 同级，如 `assets/fig1.png`）。
- `meta.source_words`：论文**全文英文词数**（用于 `build.py` 的三模式比例自检，见 modes.md）。可由源文文本按空白切词估算；缺省/为 0 则跳过自检。
