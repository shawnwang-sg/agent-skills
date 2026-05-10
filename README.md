# Agent Skills

Personal collection of skills for AI coding agents — Claude Code, Codex, Gemini, and others.

Each skill is a self-contained folder with a `SKILL.md` describing when to trigger it and how to run it. Drop the folder into your agent's skills directory (path varies by tool) and the agent will pick it up.

## Repository layout

```
agent-skills/
├── <skill-name>/                  ← one folder per skill, each with SKILL.md
│   ├── SKILL.md
│   └── ...                        ← skill-private scripts live here
├── tools/                         ← cross-skill + subsystem utilities
│   ├── README.md
│   └── subtitle-glossary/         ← domain term lists for subtitle-cleanup
│       ├── README.md
│       ├── parse_qcel.py          ← builder: .qcel → glossary
│       └── <domain>.md            ← 太极, 网球, ...
└── README.md
```

**Three tiers of tooling**:
- **Skill-private** (inside `<skill>/`) — only that skill ever runs it
- **Subsystem-specific** (inside `<subsystem>/tools/`) — e.g. glossary builders
- **Cross-skill** (top-level `tools/`) — anything multiple skills might call

## Skills

| Skill | Description |
| --- | --- |
| [subtitle-cleanup](./subtitle-cleanup) | Process SRT/VTT/TXT/LRC subtitles. Mode A cleans into a paragraph 演讲文稿 `.docx`; Mode B merges fragmented timestamped lines into coherent sentences for English study. Loads matching `tools/subtitle-glossary/<domain>.md` when the user names a domain. |

## Glossaries

Domain term lists live under [`tools/subtitle-glossary/`](./tools/subtitle-glossary). They prime `subtitle-cleanup` (and any future skill needing domain context) so it can recognize canonical terms and auto-fix common ASR transcription errors. Invoke by mentioning the domain when calling a skill:

> 合并字幕，主题是太极

The skill loads `tools/subtitle-glossary/太极.md`. Full docs and the new-glossary recipe live in [tools/subtitle-glossary/README.md](./tools/subtitle-glossary/README.md).

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
