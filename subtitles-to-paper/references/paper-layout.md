# 双栏论文排版

## 约定的版式

这是用户选定的美式双栏阅读稿样式，不宣称美国所有学校采用统一标准。

| 项目 | 默认值 |
|---|---|
| 纸张 | US Letter，8.5 × 11 英寸 |
| 页边距 | 四边 0.75 英寸 |
| 栏数与栏距 | 双栏，栏距 0.25 英寸 |
| 正文字号 | 10bp |
| 行距 | 名义 14bp，1.3 倍系数，实际约 18.2bp |
| 引用正文 | 9bp，名义 11bp 行距；网址沿用正文字体并允许换行 |
| 英文 | Times New Roman |
| 中文 | SimSun（宋体）；粗体 SimHei，斜体 KaiTi |
| 颜色 | 正文、标题、链接均为黑色 |

英中论文分文件，使用同一套对话编号。全宽区只放标题和简短节目、人物元信息；人物介绍、正文、引用都在正常双栏区域分页，避免长导读把首页挤坏。

顺序：标题与元信息 → 必要人物介绍或用户要求的导读 → 原访谈正文 → 引用与资料来源。不得虚构学术摘要、方法或研究结果。成品正文不写字幕制作流程。

## 排版输入

辅助脚本读取 UTF-8 JSON，示例见 `../assets/example.json`：

- `document_id`：稳定篇目标识，用于对话 ID 和输出追溯；不要求登记到任何项目。
- `original_language`：`en` 或 `zh`。
- `title`：按语言保存的标题，如 `{"en":"...","zh":"..."}`。
- `program`：可选，分语言节目名称；`interview_date`：可选，已确认日期，未知可省略。
- `speakers`：键为稳定角色键，值为分语言显示名，如 `{"host":{"en":"Host","zh":"主持人"}}`；真实未知身份应明确标记。
- `introduction`：可选，分语言人物介绍。默认简短必要信息；完整导读仅在用户要求时加入，必须保持编辑文字与原话分离。
- `sources`：来源数组，每条含 `id`、分语言 `text` 和可选 `url`。完整条目写作者/机构、标题、发布日期或未知、访问日期；URL 与来源文字分开。
- `paragraphs`：按正文顺序排列，每条含唯一 `id`、对应 `speakers` 的 `speaker`、分语言 `text`、非空 `source_refs` 数组。`source_refs` 可写 `R01:cues 12-19`、`input.txt:lines 20-25`，须真实可追溯，不是自动验证过的证据。

英文原文默认要求 `en`、`zh` 字段都完整，不能缺译文时回退到原文。用户只要一种语言可传 `--languages en` 或 `--languages zh`。中文原文只允许中文输出。

JSON 应从确认后的正文和映射构建，并与确认后的 TXT/Markdown 逐段独立比较。脚本能检测结构错误、重复 ID 和缺语言字段，不能证明译义准确或来源覆盖完整。

## 使用随附脚本

```text
python <技能目录>/scripts/render_paper.py paper-input.json --output-dir paper-v1
```

输出包括 `paper-v1/en/main.tex`、`paper-v1/en/transcript.txt`、对应中文目录及 `render_manifest.json`。输出目录必须不存在，防止覆盖已确认成果。这只是为本次排版写输出文件，不建立访谈项目、Git 仓库或登记篇目。

脚本只依赖 Python 标准库，模板按脚本所在位置读取，可整体迁移技能文件夹。用 `--latin-font`、`--cjk-font`、`--cjk-bold-font`、`--cjk-italic-font` 指定确实安装的字体；找不到默认字体时选择合适替代并在交付说明注明，不默默更换。

## 编译

先检查已有 Tectonic 或 XeLaTeX 及字体。模板使用 Unicode/CJK 字体，不用 pdfLaTeX。

```text
tectonic --keep-logs --outdir paper-v1/en paper-v1/en/main.tex
tectonic --keep-logs --outdir paper-v1/zh paper-v1/zh/main.tex
```

也可在各语言输出目录内执行 `xelatex -interaction=nonstopmode -halt-on-error main.tex`，按交叉引用情况复编。编译器未入 PATH 时使用当前环境核实的可执行文件路径，不复制旧机器路径。Tectonic 首次可能需要网络获取 TeX 包。

环境提供内置 LaTeX 编译工具时也可使用；源文件与模板保留在正常文件目录中，编译失败不等于应重建正文。

注意 `[` 开头的文字可能被误当作前一个 TeX 命令的可选参数；模板在说话人后显式使用 `\nopagebreak[4]` 并结束命令。正文的 `% & _ # $ { } \ ^ ~` 必须按文本转义，不能直接把字幕当作 TeX 代码。长网址使用可换行的 URL 排版。

编译完成后按 [验收规则](quality-and-recovery.md) 检查，验收前不把 PDF 标为最终版。交付用有篇名、语言和版本的文件名，避免多个成品都叫 `main.pdf`。
