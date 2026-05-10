# subtitle-glossary

Domain-specific term lists used by [`subtitle-cleanup`](../../subtitle-cleanup) (and any future skill needing domain context) to catch ASR transcription errors and recognize proper nouns.

## How to use

When invoking a skill on domain-specific content, mention the domain:

> 合并字幕，主题是太极

The skill will load `tools/subtitle-glossary/<domain>.md` and use it to:
- Recognize canonical terms (don't "correct" them)
- Auto-fix common ASR misrenderings (e.g., `驴` → `捋`, `much` → `慢`)

## File format

Each domain file has three sections:

```markdown
# <领域名>

## 一句话上下文
<one-line description that primes the model>

## 专有名词（保持原样）
- term1
- term2
...

## 易错（ASR 错 → 正字）
- 篮雀尾 → 揽雀尾
- 驴 → 捋
- much → 慢
...
```

## Currently shipped

| Domain | File | Sources |
| --- | --- | --- |
| 太极拳 | [太极.md](./太极.md) | QQ 输入法 .qcel 词库 + 百度百科·杨氏太极拳 + 实际校对积累 |

## Building new glossaries

Sources, in order of effort/yield:

1. **Chinese IME dictionaries (`.scel` / `.qcel`)** — fastest, 100–500 curated terms in one shot. Use [parse_qcel.py](./parse_qcel.py):

   ```bash
   python tools/subtitle-glossary/parse_qcel.py path/to/dict.qcel
   # writes path/to/dict.glossary.txt with `<word>\t<pinyin>` per line
   ```

2. **Wikipedia / Baidu Baike pages** — fetch the domain article and extract terminology by category.

3. **Book glossaries / indexes** — OCR the index pages (Umi-OCR for scanned PDFs).

4. **Hand-collected corrections** — when running `subtitle-cleanup`, append discovered ASR errors to the "易错" section as you encounter them.
