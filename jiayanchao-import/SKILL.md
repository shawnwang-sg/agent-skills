---
name: jiayanchao-import
description: 把名言、金句、摘抄批量加入用户本地 growth-planner 应用的「嘉言钞」（jiayanchao，C:\Users\Shugu\growth-planner\data\data.json 的 quotes），自动和已有句子去重、把长段拆成适合轮播的短句、拆出「——出处」，改前先备份。触发词：「加到嘉言钞」「导入 jiayanchao」「放进 growth-plan(ner)」「加到我的名言库」「嘉言钞去重」，或用户做完名言集锦后说「把这些都加到 growth-plan 里」。
---

# 导入 growth-planner 嘉言钞

嘉言钞是 growth-planner 里轮播/展示名言的地方，数据存在 `C:\Users\Shugu\growth-planner\data\data.json` 的 `quotes` 数组，每句是 `{"id", "text", "source", "enabled"}`。用户的要求只有一句「注意去掉重复的」，但背后有几件事要做对：

- **去重要比字面更宽**：同一句话常有原文版和润色版、带不带出处、标点不同，都算重复。
- **长段要拆**：嘉言钞的句子要能一眼读完，库里原有句子中位约 40 字、最长约 150 字，所以超过约 160 字的段落按句子拆成 ≤120 字左右的几句。
- **不能动用户原有的数据**：只追加，先备份，保持文件原来的换行风格（diff 只出现新增行）。

依赖：Python。命令都加 `PYTHONIOENCODING=utf-8`。

## 步骤

1. **找到数据文件**：默认 `C:\Users\Shugu\growth-planner\data\data.json`。不在的话先在用户目录下找 `growth-planner*`，再看 `src/views/JiayanchaoView.tsx`、`src/domain/quotes.ts` 确认字段没变（`quotes[]` 的 `id/text/source/enabled`）。字段变了就先调整脚本再导入。
2. **先空跑看统计**：
   ```bash
   PYTHONIOENCODING=utf-8 python ~/.claude/skills/jiayanchao-import/scripts/import_quotes.py <输入> --source <来源名> --dry-run
   ```
   输入可以是 quote-collection-publish 的 pages.json（会带上附录）、JSON 字符串列表或空行分隔的 txt。`--source` 一般填集锦标题，比如「厉害文字集锦」。
   看「整条重复 / 片段重复 / 新增」的数量和样例。重复率异常高或异常低（比如新增是 0，或几乎全部新增但用户说过以前导过）时，先抽几条核对再写。
3. **正式写入**：去掉 `--dry-run` 再跑一次。脚本会自动备份为 `data/data.backup-<时间>.json`。
4. **核对**：`git -C C:\Users\Shugu\growth-planner diff --stat data/data.json` 或和备份 diff，确认只有新增行、没有删除行。
5. **提醒用户刷新**：growth-planner 平时开在 `http://localhost:5173`。要刷新页面才看得到新句子；页面里如果有没保存的改动，先保存再刷新，否则可能提示冲突或被覆盖。

## 汇报
新增多少句、现在一共多少句；跳过了多少重复（举一两个原文版/润色版这种例子）；长段拆分后最长多少字；带出处的填进了出处字段；备份文件路径；提醒刷新。
