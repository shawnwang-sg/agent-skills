# Agent Skills

Personal collection of skills for AI coding agents — Claude Code, Codex, Gemini, and others.

Each skill is a self-contained folder with a `SKILL.md` describing when to trigger it and how to run it. Drop the folder into your agent's skills directory (path varies by tool) and the agent will pick it up.

## Skills

| Skill | Description |
| --- | --- |
| [subtitle-cleanup](./subtitle-cleanup) | Process SRT/VTT/TXT/LRC subtitles. Mode A cleans into a paragraph 演讲文稿 `.docx`; Mode B merges fragmented timestamped lines into coherent sentences for English study. |

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

### Other agents

Most agent frameworks accept the same `SKILL.md` format. Point your agent's skills/prompts directory at this repo (or a subfolder) and adjust the trigger description if needed.
