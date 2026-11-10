# 抓取规范（fetch）

目标：拿到论文**全文 + 章节结构 + 图**，供写 paper.json 用。避开 PDF 双栏/公式乱码。

## arxiv（优先 HTML）

1. 把 `arxiv.org/abs/<ID>` 或 `arxiv.org/pdf/<ID>` 归一为 ID。
2. 优先抓 `https://arxiv.org/html/<ID>`（WebFetch）。
3. 失败退 `https://ar5iv.org/abs/<ID>`。
4. 再退 abs 页（拿 meta/摘要）+ LaTeX source `https://arxiv.org/e-print/<ID>`（拿正文/公式）。

## 本地 PDF

- 内置 Read 工具分页读（`pages` 参数，≤20 页/次）。
- 或命令行 `pdftotext -layout file.pdf -`（需安装 poppler）。

## 截图 / 图片

- Read 工具直接读图（视觉理解）。

## 飞书 / lark

- `lark-cli docs fetch --api-version v2 --doc "<url>" --doc-format markdown`。

## 图表

- 能下原图就下到 `papers/<slug>/assets/`，paper.json 里用 `figure.src` 引用（相对该 paper 目录）。
- 下不到就内联 `svg` 简单重绘：`viewBox≈0 0 820 420`，基本形状 + 中文标注，合法自包含 svg。
