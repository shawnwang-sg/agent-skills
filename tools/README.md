# Tools

Cross-skill utilities. If a tool would only ever be used by **one** skill, put it inside that skill's folder instead. If it's specific to a subsystem (e.g. building glossaries), put it under that subsystem's `tools/`.

## Registry

| Tool | Purpose | Usage | Deps |
| --- | --- | --- | --- |
| _(empty — add tools below)_ | | | |

<!-- Example row, uncomment when you add the first tool:
| [ocr_image.py](./ocr_image.py) | Extract Chinese text from a PNG/JPG using PaddleOCR | `python tools/ocr_image.py <image>` → text on stdout | paddleocr |
-->

## Conventions

Every tool in this folder must satisfy:

1. **Single file, single purpose.** No multi-file packages. If logic grows, split into multiple tools.
2. **Self-contained CLI.** Runnable as `python tools/<name>.py <args>` (or `pwsh tools/<name>.ps1`). Read from args / stdin, write to stdout / a file. **Never** require skills to `import` your module — agent environments have inconsistent `sys.path`.
3. **Top-of-file docstring** with: one-line summary, usage example, and any non-stdlib dependencies marked `# requires: <pkg>`.
4. **Stdlib first.** Avoid pip dependencies unless the tool genuinely needs them. If you do need one, document it in the registry table above and in the docstring.
5. **Verb-phrase filename.** `extract_index.py` not `index.py`; `compress_video.py` not `video.py`. Makes the registry readable.
6. **Update the registry table above** when you add a tool — that's how skills discover what's available.

## Skeleton template

Drop this in as the starting point for any new tool:

```python
"""
<one-line summary>

Usage:
    python tools/<name>.py <args>

Example:
    python tools/extract_index.py book.pdf > index.txt

# requires: <pip-package-1>, <pip-package-2>   (omit line if stdlib-only)
"""
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1
    # ... actual work ...
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

PowerShell variant:

```powershell
<#
.SYNOPSIS
    <one-line summary>
.EXAMPLE
    pwsh tools/<name>.ps1 -Input foo.txt
#>
param(
    [Parameter(Mandatory)] [string]$Input
)

# ... actual work ...
```
