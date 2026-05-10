# Glossary

Domain-specific term lists used by `subtitle-cleanup` (and any future skill needing
domain context) to catch ASR transcription errors and recognize proper nouns.

## How to use

When invoking a skill on domain-specific content, mention the domain:

> 合并字幕，主题是太极

The skill will load `glossary/太极.md` and use it to:
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

## How the term lists are built

- Hand-collected from corrections during subtitle-cleanup runs
- Extracted from Chinese IME dictionaries (`.scel` / `.qcel`) using
  `tools/parse_qcel.py` — these give 100-500 canonical terms per domain
  in one shot
- Pulled from book glossaries / indexes via OCR
