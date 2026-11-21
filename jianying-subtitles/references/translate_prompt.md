# 分句翻译子代理提示词模板

主代理先填好 `{D}`、`{IDS}`、`{REF_ID}` 和背景提示，再交给后台 general-purpose 子代理。

---

Folder: {D} (call it D). Raw JianYing subtitle exports are in D\剪映原始字幕\ named "<base>.jy.srt" for ids {IDS} (base names start with the id, e.g. "22-12 Title (66m00s-72m00s)"). Each .jy.srt (UTF-8) contains N English blocks followed by N Chinese machine-translation blocks with identical timestamps.

For EACH id:
1. Read the .jy.srt. The merge script treats every block containing NO CJK character as English; number those 1..N in order (if an "English" block is actually Chinese, the script skips it — number according to the script's rule).
2. Group consecutive English blocks into sentence-sized units of roughly 10–25 words (merge fragments into complete sentences; break at natural sentence ends/pauses). Groups must be contiguous, 1-based inclusive [a,b], cover every English block exactly once, starting at 1 and ending at N.
3. For each group write a natural, fluent spoken-style Chinese translation (fix obvious mis-transcriptions in meaning only; English itself is never changed). {CONTEXT_HINTS — e.g. speaker names often mis-transcribed and how to render them; the previous clip ended mid-sentence "..."}
   HARD RULE: every Chinese string must START with a CJK ideograph (U+4E00–U+9FFF) — not a quote mark, ellipsis, digit, Latin letter, book-title mark, or punctuation. E.g. "他说……" not "……他说"; "第三，" not "3，".
4. Write D\剪映原始字幕\<id>.job.json (UTF-8) as {"groups": [[1,3],[4,6],...], "zh": ["...", ...]} with len(groups)==len(zh). Use D\剪映原始字幕\{REF_ID}.job.json as a format reference (if one exists).
5. Run the merge script from Python via subprocess (avoid shell path escaping): python -I {SKILL}\scripts\jy_merge.py "<path to .jy.srt>" "<path to job.json>" "D" "<base>" (base = .jy.srt filename without ".jy.srt"). It must exit 0 and print "<base>: 英文 N 块 -> M 句". Fix and re-run on assertion errors.

Do not touch any other files. Report per id: block count, sentence count, notable mis-transcriptions (brief).

---

经验：一个子代理处理 2～3 段，约 2～3 分钟。几个子代理可以并行，它们写的文件互不冲突。
