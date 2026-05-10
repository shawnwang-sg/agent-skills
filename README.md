# Agent Skills

Personal collection of skills for AI coding agents — Claude Code, Codex, Gemini, and others.

Each skill is a self-contained folder with a `SKILL.md` describing when to trigger it and how to run it. Drop the folder into your agent's skills directory (path varies by tool) and the agent will pick it up.

## Repository layout

```
agent-skills/
├── <skill-name>/        ← one folder per skill, each with SKILL.md
│   └── SKILL.md
├── glossary/            ← shared domain term lists used by skills (太极, 网球, ...)
│   ├── README.md
│   ├── tools/           ← helpers for building glossaries (.qcel parser, etc.)
│   └── <domain>.md
└── README.md
```

## Skills

| Skill | Description |
| --- | --- |
| [subtitle-cleanup](./subtitle-cleanup) | Process SRT/VTT/TXT/LRC subtitles. Mode A cleans into a paragraph 演讲文稿 `.docx`; Mode B merges fragmented timestamped lines into coherent sentences for English study. Loads matching `glossary/<domain>.md` when the user names a domain. |

## Glossary

Domain-specific term lists in [`glossary/`](./glossary) prime skills with the right vocabulary so they can recognize canonical terms and auto-fix common ASR transcription errors. Invoke by mentioning the domain when calling a skill:

> 合并字幕，主题是太极

The skill loads `glossary/太极.md` and uses it during cleanup. Each glossary file has three sections:

- **一句话上下文** — primer for the model
- **专有名词（保持原样）** — canonical terms (don't "correct" these)
- **易错（ASR 错 → 正字）** — known transcription errors and their fixes

Currently shipped glossaries:

| Domain | File | Sources |
| --- | --- | --- |
| 太极拳 | [glossary/太极.md](./glossary/太极.md) | QQ 输入法 .qcel 词库 + 百度百科·杨氏太极拳 + 实际校对积累 |

### Tools

Helpers in [`glossary/tools/`](./glossary/tools) for building glossaries from common sources:

| Tool | Purpose |
| --- | --- |
| [parse_qcel.py](./glossary/tools/parse_qcel.py) | Parse Sogou `.scel` / QQ `.qcel` Chinese IME cell-dictionary files. Drop the binary in, get out `<word>\t<pinyin>` per line. Useful starting point — Chinese IME stores hundreds of curated domain terms per file. |

Run it with:

```bash
python glossary/tools/parse_qcel.py path/to/dict.qcel
# writes path/to/dict.glossary.txt
```

### Adding a new domain

1. Find a starting source — IME dictionary (`.scel` / `.qcel`), book glossary/index (OCR if needed), or Wikipedia/Baidu Baike page
2. Extract terms (use `tools/parse_qcel.py` for IME files; OCR + manual for books)
3. Create `glossary/<domain>.md` following the three-section template in [glossary/README.md](./glossary/README.md)
4. As you use it, append discovered ASR errors to the "易错" section

## Install

### Claude Code

Copy or symlink any skill into `~/.claude/skills/`:

```bash
# macOS / Linux / Git Bash — copy
cp -r subtitle-cleanup ~/.claude/skills/

# macOS / Linux / Git Bash — symlink (edits in this repo take effect immediately)
ln -s "$(pwd)/subtitle-cleanup" ~/.claude/skills/subtitle-cleanup

# Windows PowerShell — copy
Copy-Item -Recurse subtitle-cleanup $env:USERPROFILE\.claude\skills\

# Windows — directory junction (no admin needed)
cmd /c mklink /J "%USERPROFILE%\.claude\skills\subtitle-cleanup" "C:\Code\agent-skills\subtitle-cleanup"
```

The `glossary/` folder lives in this repo and is referenced by skills via absolute path — no separate install needed if your skills are symlinked back here.

### Other agents

Most agent frameworks accept the same `SKILL.md` format. Point your agent's skills/prompts directory at this repo (or a subfolder) and adjust the trigger description if needed.
