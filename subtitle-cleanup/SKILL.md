---
name: subtitle-cleanup
description: Process SRT/VTT/TXT subtitles in one of two modes. (A) Transcript mode — clean fragmented subtitles into a paragraph-formatted 演讲文稿 Word document. (B) Learning mode — merge timestamped fragments into coherent sentences while keeping timestamps and changing ZERO content, output as SRT for English study. Trigger on "合并字幕"、"清理字幕"、"字幕转文稿"、"字幕英语学习"、"srt合并句子"、"保留时间戳"、"clean subtitles"、"merge subtitles"、"subtitles for english learning". Also when user points at a .srt/.vtt/.txt and asks to 整理/段落化/合并/merge it. Routing: if input has NO timestamps → transcript mode. If input HAS timestamps → ASK the user which mode before proceeding.
---

# Subtitle Cleanup Skill

## ⚠️ HARD TRIGGER — read first
If the user's message contains the four characters **「合并字幕」**, you MUST run this skill's full workflow end-to-end (Step 0 → B5 / A6). No shortcuts, no manually merging in your head, no skipping B1/B2 block-count checks, no writing the output without going through the documented Bash steps. This applies even if the file is small enough that you "could just do it" — the user has explicitly opted into the workflow by typing those four characters. Treat it as non-negotiable.

## Domain glossary (load if user names a domain)
If the user mentions a domain (e.g. "主题是太极", "topic: tennis", "网球内容"), **before starting the workflow**, look for `<repo>/tools/subtitle-glossary/<domain>.md` and read it. The glossary file has three sections:

- **一句话上下文** — primer; use to interpret ambiguous terms.
- **专有名词（保持原样）** — these are correct as-written; do NOT "fix" them.
- **易错（ASR 错 → 正字）** — apply these substitutions during cleanup, both in Mode A (transcript) and Mode B (learning, where it counts as a permitted typo correction since the source is verifiably wrong).

If the named glossary doesn't exist, proceed without it but flag that to the user at the end so they know to build one. The skill repo location is typically `~/.claude/skills/subtitle-cleanup` → resolve `../../tools/subtitle-glossary/<domain>.md`, or use the user-provided absolute path if symlinked from elsewhere (e.g. `C:\Code\agent-skills\tools\subtitle-glossary\<domain>.md`).

This skill has **two modes**. Always run Step 0 first to decide which.

- **Mode A — Transcript**: clean into a paragraph 演讲文稿 `.docx`. Removes disfluencies, fixes punctuation, allows minor cleanup.
- **Mode B — Learning**: merge fragmented SRT lines into coherent sentences, **keep timestamps**, change **zero content** (no disfluency removal, no rewording, no punctuation fixes beyond joining what was already split). Output is `.srt`.

---

## Step 0 — Detect & route (ALWAYS first)

### Detect timestamps
Check whether the input carries timestamps:
```bash
head -n 30 "<dir>/<input>" | grep -cE '\-\->'
```
- File extension `.srt` or `.vtt`, OR the grep above returns ≥1 → **has timestamps**.
- File extension `.txt` AND grep returns 0 → **no timestamps**.

### Route
- **No timestamps** → go straight to **Mode A (Transcript)**. Don't ask.
- **Has timestamps** → **ASK the user** which mode, using AskUserQuestion. Phrase the question in the user's language. Two options:
  - 「文稿模式 (Transcript)」— 合并成段落演讲文稿 .docx,会去除口头语
  - 「英语学习模式 (Learning)」— 保留时间戳,合并碎片为完整句子,完全不改内容,输出 .srt

  Wait for the user's choice before proceeding. Do not assume.

---

## Mode A — Transcript (paragraph .docx)

### Allowed edits (Mode A only)
1. Remove disfluencies: 嗯/呃/啊/那个/就是那个/对对对, um/uh/you know/like.
2. Collapse stutters: "我我我觉得"→"我觉得".
3. Join fragments into sentences; paragraphs of 3–8 sentences, break on topic shift.
4. Add obvious punctuation (。,?!) where line-breaks split sentences.

### Chinese paragraph formatting (必须遵守)
When the transcript is Chinese:
- **段首缩进**：每个段落开头必须加两个全角空格 `　　`（U+3000 × 2，约等于两个汉字宽度）。这是中文排版标准留白。**不要**用半角空格或 tab。
- **段间无空行**：段落之间直接换行（单个 `\n`），**不要**留空行。整个文稿是连续的段落块，靠缩进而非空行区分段落。
- 英文/混合文稿不加缩进，按原有习惯空行分段。

### Forbidden (Mode A)
- ❌ Summarize, paraphrase, translate, reorder, or drop substantive sentences.
- ❌ Add headings inside the body. Title + outline only belong in the header block, not inline.
- When unsure if a word is filler or content, **keep it**.

### Workflow

#### A1 — Preprocess (Bash only, no Read)
If input is `.srt`/`.vtt`, strip timecodes and indices first. Use absolute paths:
```bash
grep -vE '^[0-9]+$|-->|^WEBVTT' "<dir>/input.srt" | sed '/^$/d' > "<dir>/input.stripped.txt"
```
Then check size: `wc -l "<dir>/input.stripped.txt"`.

#### A2 — Single pass or chunk
- **≤1500 lines or ~40KB**: Read the (stripped) file once, clean in one pass, Write the body to `<dir>/temp/<name>_body.txt`. Go to A4.
- **Larger**: go to A3.

#### A3 — Chunked (Bash splits, model only cleans)
1. Create `<dir>/temp/` as a standalone command (reuse, never wipe):
   ```bash
   mkdir -p "<dir>/temp"
   ```
2. Split with Bash — do NOT Read the file to chunk it. Pass `dir` and `name` into awk and build absolute output paths:
   ```bash
   awk -v dir="<dir>" -v name="<name>" 'NR%400==1{f=sprintf("%s/temp/%s_chunk_%03d.txt",dir,name,++i)} {print > f}' "<dir>/<input>"
   ```
   Adjust `400` so you get 10–100 chunks. Zero-padded names make glob sort correctly.
3. For each chunk: Read → clean → Write `<dir>/temp/<name>_chunk_NNN_clean.txt`. When splitting by fixed line count, a chunk may end mid-sentence — leave the tail unpunctuated, next chunk continues it. Apply Chinese paragraph formatting (全角双空格缩进、无段间空行) inside each chunk as you clean.
4. **Segment break detection** (for multi-material files): if a chunk contains a hard boundary to a *different source material* — new greeting/host/guest, unrelated subject, clearly a different lecture/interview/article — insert a single line `[[SEG_BREAK]]` at the boundary inside the clean chunk. Use this only for **distinct materials concatenated into one file**, NOT for ordinary topic shifts within one speech. Also keep a one-line topic note per chunk *with its segment index* so you can synthesize per-segment headers later.
5. Concatenate via Bash, no Read, absolute paths:
   ```bash
   cat "<dir>/temp/<name>_chunk_"*_clean.txt > "<dir>/temp/<name>_body.txt"
   ```
6. Never delete `<dir>/temp/`.

#### A4 — Build header(s) and assemble
The body lives at `<dir>/temp/<name>_body.txt`. Count segment breaks:
```bash
grep -c '\[\[SEG_BREAK\]\]' "<dir>/temp/<name>_body.txt"   # 0 = single segment; N = N+1 segments
```

Each header has this format (no 全角 indent — headers are metadata, not body paragraphs):
```
标题：<one-line noun phrase>
纲要：
一、<topic 1>
二、<topic 2>
...
```
A single blank line separates header from body. 5–15 outline bullets.

##### Single segment (0 breaks)
Write the header to `<dir>/temp/<name>_header.txt`. The body is already at `<dir>/temp/<name>_body.txt`. That's all you prepare in this step — the assembly into a single file happens in A5 via the docx skill.

##### Multi-segment (≥1 breaks)
1. Split the body on the marker into per-segment parts (absolute paths, no `cd`, **no `rm` cleanup** — see Bash hygiene Rule B; awk's `print > f` truncates on open so fresh writes are fine):
   ```bash
   awk -v dir="<dir>" -v name="<name>" 'BEGIN{n=1; f=sprintf("%s/temp/%s_part_%02d.txt",dir,name,n)} /^\[\[SEG_BREAK\]\]$/{n++; f=sprintf("%s/temp/%s_part_%02d.txt",dir,name,n); next} {print > f}' "<dir>/temp/<name>_body.txt"
   ```
2. Write one header per segment: `<dir>/temp/<name>_header_01.txt`, `..._header_02.txt`, ... Each header's title + outline covers only its own segment, synthesized from that segment's topic notes.
3. No cat assembly here — A5 hands the ordered list of (header, part) pairs to the docx skill along with the separator instruction. **Reference parts by explicit index up to `N = grep -c SEG_BREAK + 1`, not by glob** — any stale `part_(N+1)` from a previous run with more segments stays on disk harmlessly and is ignored.

**Token discipline:** in chunked mode, synthesize titles + outlines at the end from the topic notes you jotted per chunk — do NOT re-Read the body. In single-pass mode, generate header(s) during the same read as cleanup.

#### A5 — Generate the `.docx` via anthropic-skills:docx
The final file is always a Word document saved **in the input's directory**, named `<短标题>.docx`.

**Short title**:
- Single segment: derived from the title you generated.
- Multi-segment: use the first segment's title, or a short joint phrase if the segments are unrelated (e.g. `对话两则`, `演讲合辑`). Do not concatenate all segment titles.
- Sanitize: strip `/\:*?"<>|` and control chars, trim whitespace, cap at ~20 full-width characters (~40 bytes). Keep Chinese characters as-is.
- **Collision check (model-side, no shell loops).** Claude Code blocks compound Bash commands that mix variable expansion with `while`/arithmetic (`${var}`, `$((…))`, `while [ -e "$f" ]`) under *"Contains expansion"*. Do NOT try to resolve the final path with a shell loop. Instead:
  1. Run a single read-only listing:
     ```bash
     ls "<dir>"
     ```
     Read-only globs and listings are always allowed, so this never prompts.
  2. **You** scan the result for anything that would collide with `<短标题>.docx`. If `<短标题>.docx` is free, use it. Otherwise pick the lowest `<短标题>_<N>.docx` (N=2, 3, …) that is not in the listing. The model does this inline — no shell loop, no variable expansion, no subshell arithmetic.
  3. Pass the resulting absolute path (just a literal string, e.g. `C:/Users/Shugu/Desktop/draft/回忆录中的五十年代_2.docx`) directly to the docx skill.

**Invoke the docx skill** via the Skill tool (`skill: "anthropic-skills:docx"`) with a self-contained instruction that tells it exactly what to build. The prompt must include:
1. **The output path** (the `$final` value from the collision check).
2. **The list of input text files in order** — for single-segment: `[<dir>/temp/<name>_header.txt, <dir>/temp/<name>_body.txt]`. For multi-segment: `[header_01, part_01, header_02, part_02, ...]` (all absolute paths).
3. **Styling instructions**:
   - **Page margins**: left and right margins set to **0.32 cm** (roughly 1/10 of Word's default 3.17 cm). Top and bottom margins stay at Word's default (2.54 cm). This is wide-body layout — narrow left/right for long Chinese paragraphs.
   - **Default font**: 宋体 (East Asian) / Times New Roman (Latin), **13pt**. Line spacing 1.5.
   - Header files are metadata. The first line of each header (`标题：...`) is a centered, bold, 17pt heading (drop the `标题：` prefix). The `纲要：` line is bold 13pt. Outline items (`一、...`、`二、...`) are regular 13pt paragraphs, no indent. Insert one empty paragraph between the outline and the body.
   - Body files are clean paragraphs, one per line (blank lines ignored). Strip any leading `　` (U+3000) full-width spaces from each paragraph before adding — the text-form indent is replaced by a real **first-line indent of 2 characters** (Word's `firstLineChars=200`, or ~0.92 cm at 13pt).
   - Between segments in multi-segment mode, insert a centered paragraph containing `────────────────` (sixteen U+2500) as a visual divider. No divider after the final segment.
4. **A note that it must NOT summarize, paraphrase, or drop any body content** — straight pass-through with only the leading-space strip.

Hand the full spec to the docx skill in one Skill tool call. Wait for it to confirm the file was written at the target path.

#### A6 — Report
One terse line: input size, chunk count (if any), segment count (if >1), output `.docx` path.

### Merging existing clean files (Mode A shortcut)
If the user asks to merge pre-existing `*_clean.*` files, it's pure `cat` — never Read them, and use absolute paths:
```bash
cat "<dir>/a_clean.txt" "<dir>/b_clean.txt" ... > "<dir>/merged.txt"
```

---

## Mode B — Learning (merged-sentence .srt)

**Goal**: produce an SRT where each block is a *complete coherent sentence* with the timestamp range covering its original source blocks. Designed for English-learning use (Anki, study, side-by-side reading, re-subbing the original video).

### Hard rules (Mode B — read carefully, this differs from Mode A)
- ❌ **Do NOT remove disfluencies** ("um", "uh", "you know", "like", "I mean", repeated words). Keep them all.
- ❌ **Do NOT change wording, capitalization, or spelling** in any way. Not even obvious typos.
- ❌ **Do NOT add or change punctuation.** If the original had no period, don't add one. If a sentence is split across two SRT blocks with a comma, keep the comma.
- ❌ **Do NOT translate or paraphrase.**
- ✅ **Allowed**: when joining text from two consecutive blocks, replace the line-break / block-break with a **single space**. Collapse runs of internal whitespace to one space. That's the *only* textual edit.
- ✅ **Allowed**: assign new sequential index numbers to the merged blocks (1, 2, 3, …).

### Output format
Standard SRT. Each merged block:
```
<index>
<start_time> --> <end_time>
<merged sentence text>

```
- `<start_time>` = start time of the *first* source block in the merge.
- `<end_time>` = end time of the *last* source block in the merge.
- Time format: keep whatever the source used (`HH:MM:SS,mmm` for SRT, `HH:MM:SS.mmm` for VTT — but always emit SRT with comma-millisecond format in the output).
- One blank line between blocks. No blank line after the final block (or one — both are valid SRT).

### Sentence boundary rule
Merge consecutive blocks until you reach a sentence-final punctuation mark (`.`, `?`, `!`, `…`) **that already exists in the source**. That ends the merged block; the next block starts a new merge.

**English minimum-length rule (HARD)**: every merged English block must contain **at least 10 words**. Short fragments like "looking for patterns", "were they smarter", "of people they liked", "and that in turn made them more likable" are NOT acceptable as standalone blocks — they must be merged forward into the next block (or backward into the previous one) until the resulting block reaches 10+ words. Fragmentation is the enemy: a learner needs full thoughts, not 3-word stubs. This rule overrides "1–3 source blocks per merged block" — keep merging as many source blocks as needed to clear 10 words. The 25-word cap still applies as the upper bound; if a single sentence runs long, prefer the natural breath point closest to but under 25 words.

Edge cases:
- **No sentence-final punctuation in the whole file** (common in auto-generated captions): fall back to merging on **clear semantic clause boundaries** — typically a long pause inferable from a gap between block end-time and next block start-time (≥ 1.0 s), or a clear discourse marker starting a new thought. **Do not exceed ~25 words per merged block** even if the speaker keeps going — split at the most natural breath point. Combined with the 10-word minimum above, target range is **10–25 words per merged block**.
- **Mid-sentence semicolons or colons**: do not break on these.
- **Quoted speech**: keep quotes attached to the surrounding sentence; don't break inside a quote.
- **Single-block sentences**: pass through unchanged (just renumber).

### Workflow

#### B1 — Normalize input
If input is `.vtt`, strip the `WEBVTT` header and any cue-setting lines, and convert dot-millisecond to comma-millisecond. Use absolute paths, no `cd`:
```bash
sed -e '/^WEBVTT/d' -e '/^Kind:/d' -e '/^Language:/d' \
    -e 's/\([0-9][0-9]\):\([0-9][0-9]\)\.\([0-9][0-9][0-9]\)/\1:\2,\3/g' \
    "<dir>/<input>.vtt" > "<dir>/temp/<name>_normalized.srt"
```
For `.srt`, copy or just point to the original file directly — no normalization needed.

Make sure `<dir>/temp/` exists:
```bash
mkdir -p "<dir>/temp"
```

#### B2 — Block count check
```bash
grep -c -- '-->' "<dir>/<srt_input>"
```
- **≤ 400 blocks**: single-pass — go to B3a.
- **> 400 blocks**: chunked — go to B3b.

#### B3a — Single-pass merge
1. Read the SRT file in full.
2. Walk through blocks in order. For each, decide: continue current merged block, or close the current merged block and start a new one (apply the sentence boundary rule).
3. Build the output SRT in memory. Renumber merged blocks starting from 1.
4. Write to `<dir>/<name>_merged.srt`. Final output. Skip to B4.

#### B3b — Chunked merge
1. Split the SRT at block boundaries (blank lines). Each chunk gets ~300 source blocks. Bash only — no Read for splitting:
   ```bash
   awk -v dir="<dir>" -v name="<name>" '
     BEGIN { i=1; b=0; f=sprintf("%s/temp/%s_srtchunk_%03d.srt",dir,name,i) }
     /-->/ { b++; if (b > 300 && prev=="") { i++; b=1; f=sprintf("%s/temp/%s_srtchunk_%03d.srt",dir,name,i) } }
     { print > f; prev=$0 }
   ' "<dir>/<srt_input>"
   ```
   (The `prev==""` guard splits only at a true blank line so we never break inside a block.)
2. For each chunk: Read → merge sentences within the chunk → Write `<dir>/temp/<name>_srtchunk_NNN_merged.srt`. **Do NOT renumber yet** — write each merged block with index `0` (placeholder) so a final pass can renumber globally. Or, simpler: omit the index line entirely and let the renumber pass insert it.
   - Recommended: in each chunk's merged output, emit blocks as just `<time> --> <time>\n<text>\n\n` (no index line).
3. A chunk may end mid-sentence. That's fine — close out the in-progress merged block at the chunk's end (use the last block's end-time). The next chunk starts a new merged block. This may cause a small number of "false splits" at chunk boundaries; acceptable trade-off for token economy.
4. Concatenate (input glob OK, write target is exact):
   ```bash
   cat "<dir>/temp/<name>_srtchunk_"*_merged.srt > "<dir>/temp/<name>_merged_unnumbered.srt"
   ```
5. Renumber with awk — adds an index line before every timestamp line:
   ```bash
   awk 'BEGIN{n=0} /-->/ {n++; print n} {print}' "<dir>/temp/<name>_merged_unnumbered.srt" > "<dir>/<name>_merged.srt"
   ```

#### B4 — Sanity check
```bash
grep -c -- '-->' "<dir>/<name>_merged.srt"
```
Compare to input block count from B2. The merged count should be **smaller** (typically 30–70% of input). If it's equal or larger, something went wrong — investigate before reporting done.

Also spot-check: Read the first and last ~30 lines of the output, confirm timestamps look monotonic and text looks like complete sentences with no content drift.

#### B5 — Report
One terse line: input block count → output sentence count, output `.srt` path.

---

## Core principle: mechanical work stays in Bash
Anything deterministic — timecode stripping, chunking, concatenation, counting, splitting on markers, renumbering — runs in Bash. The model only Reads text it needs to *understand and rewrite* (Mode A) or *segment into sentences* (Mode B). Never Read a file just to cat it, split it, or strip timecodes.

## Bash hygiene — MUST FOLLOW (both modes)
Claude Code's Bash sandbox enforces two hard rules that override any pre-approval on this skill. Violate them and the user sees a manual-confirm prompt even though they already said "always allow" for the skill. Both rules are about **write operations** where the affected paths can't be statically verified:

### Rule A — No `cd` chained with writes
A single call that combines `cd` with any write op (`mkdir`, `mv`, `cp`, redirect `>`/`>>`, `awk ... > f`, etc.) is blocked with *"Compound command contains cd with write operation — manual approval required to prevent path resolution bypass."* The fix is trivial:

1. **Never use `cd`.** Not even chained with `&&`. Not even for "convenience."
2. **Always pass absolute paths.** Treat the input file's directory as a variable `<dir>` and build every output path as `"<dir>/..."`.
3. **Pass `<dir>` and `<name>` into `awk` with `-v`**, then use `sprintf` to build absolute output filenames. Don't rely on the awk process's CWD.
4. Commands can still chain with `&&` — just drop the `cd` link.

### Rule B — No shell globs in write operations
A call that applies a shell glob (`*`, `?`, `[…]`) to `rm`, `mv`, `cp`, `mkdir`, or any other command whose affected paths are the *write target*, is blocked with *"Glob patterns are not allowed in write operations. Please specify an exact file path."*

What this means in practice:
- ❌ `rm "<dir>/temp/<name>_part_"*.txt` — blocked. The glob expands into the rm argument list, which is the write target set.
- ❌ `mv "<dir>/*.txt" "<dir>/old/"` — blocked.
- ✅ `cat "<dir>/temp/<name>_chunk_"*_clean.txt > "<dir>/temp/<name>_body.txt"` — **fine**. The glob feeds cat's *input*; the write target (`> body.txt`) is an exact path.
- ✅ `ls "<dir>/temp/<name>_part_"*.txt`, `wc -l "<dir>/temp/..."`, `grep -c ... "<dir>/..."` — fine. Read ops.
- ✅ `rm -f "<dir>/temp/<name>_part_01.txt" "<dir>/temp/<name>_part_02.txt"` — fine. Explicit paths, no glob.

**Do not add `rm` cleanup steps the workflow doesn't ask for.** Every `awk` write opens target files with `>` (truncate-on-open), so rerunning the skill overwrites same-named outputs in place. Stale files from an earlier run with a different chunk count are harmless — downstream steps reference parts by explicit index or by an exact-path glob into a read position, not by globbing into a write target.
