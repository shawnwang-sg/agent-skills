# Claude Skills

Personal collection of Claude Code skills.

## Skills

| Skill | Description |
| --- | --- |
| [subtitle-cleanup](./subtitle-cleanup) | Process SRT/VTT/TXT/LRC subtitles. Mode A cleans into a paragraph 演讲文稿 `.docx`; Mode B merges fragmented timestamped lines into coherent sentences for English study. |

## Install

Copy any skill folder into your Claude skills directory:

```bash
# macOS / Linux / Git Bash
cp -r subtitle-cleanup ~/.claude/skills/

# Windows PowerShell
Copy-Item -Recurse subtitle-cleanup $env:USERPROFILE\.claude\skills\
```

Or symlink so edits in this repo take effect immediately:

```bash
# macOS / Linux / Git Bash
ln -s "$(pwd)/subtitle-cleanup" ~/.claude/skills/subtitle-cleanup

# Windows (Developer Mode or admin shell)
mklink /D "%USERPROFILE%\.claude\skills\subtitle-cleanup" "C:\Code\claude-skills\subtitle-cleanup"
```
