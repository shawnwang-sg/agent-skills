# 质量门（quality-gates）

`validate.py` 按下表逐项检查。有一项 ✗ 就不合格：`reading_status` 写成 `needs_rework`，不能算精读完成。
全部通过才写 `three_pass_verified`。门槛的数值写在 `validate.py` 开头，改门槛就两处一起改。

| 检查 | 门槛 |
|---|---|
| 原始材料 | `source.pdf` / `source.txt` / `source.json` 齐全；PDF 的 sha256 和记录一致；`meta.source_words` 等于从 PDF 提取的词数 |
| 原文真实 | 每个 `origin: "paper"` 块都有 `source_page`，并能在那一页逐字找到；同一模式里不重复 |
| 原文比例（只算原文块） | 鸟瞰 15–25%，理解 30–45%，吃透 40–60% |
| 鸟瞰结构 | 有 `conclusion`、`five_c`、`excerpts`、`verdict`、`questions`；5C 满 5 项 |
| 理解结构 | ≥ 6 节；术语 ≥ 8 个；`evidence` 证据链 ≥ 3 条；有 `open_questions` |
| 图表覆盖 | `source.txt` 里出现的每个 "Figure N" / "Table N" 都在 `assets/provenance.json` 里有裁图；引用的图片文件都存在 |
| 吃透原文 | 正文 ≥ 8000 词时 ≥ 40 段，更短的论文按「词数 ÷ 200」折算（最少 10 段） |
| 推演 | `derivations` 里 ≥ 12 个 `h3` |
| 问答数量 | ≥ 24 组，无重复问题 |
| 问答分类 | `reproduce` / `assumption` / `failure` / `evidence` / `compare` 各 ≥ 3 组 |
| 问答深度 | 答案不到 40 个英文词的不超过 20%；≥ 1/3 的答案引用图表、章节或数字 |
| 评判 | `critique` 合计 ≥ 8 条，`future` ≥ 2 条 |
| 防模板 | 和其他论文问题几乎一样的（词集合相似度 ≥ 0.8）不超过 20% |

另有两项警告（不判不合格，但要看一眼）：

- 图的解读不到 15 个英文词。
- 批次体检：≥ 3 篇论文的结构完全相同（各模式节数、问答数、图数都一样），多半是批量套模板。

## 用法

```
python validate.py --vault <vault> <slug>          # 一篇，列出全部问题
python validate.py --vault <vault> --all           # 全库汇总
python validate.py --vault <vault> <slug> --write  # 写 reading-audit.json，并更新 reading_status
python build.py --vault <vault> --strict           # 生成后跑质量门，有不合格就以退出码 1 结束
```
