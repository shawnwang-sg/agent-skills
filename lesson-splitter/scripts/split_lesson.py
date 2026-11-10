"""Split MP3 lessons into balanced approximately six-minute MP3 parts, aligned SRTs and a Word transcript.

Usage: python -I split_lesson.py <audio.mp3 | folder> [--target 6] [--min 4.2] [--out DIR]
       [--ffmpeg DIR] [--copy] [--srt FILE]
Short tails are spread across the final parts (minimum defaults to 70% of target). Default encoding is libmp3lame 192k.
--copy preserves encoded audio but cut times can differ by one MP3 frame.
"""
import argparse
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

def plan(duration, target, min_len):
    """Keep early parts near target; distribute short tails over the final parts."""
    n = max(1, math.ceil(duration / target))
    while n > 1 and duration / n < min_len:
        n -= 1
    for k in range(1, n + 1):
        tail = (duration - (n - k) * target) / k
        if min_len <= tail <= target:
            return [target] * (n - k) + [tail] * k
    return [duration / n] * n


# ---------------------------------------------------------------- time + srt helpers
def ts(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def label(sec):
    sec = int(round(sec))
    return f"{sec // 60:02d}m{sec % 60:02d}s"


def parse_ts(t):
    h, m, rest = t.strip().split(":")
    s, ms = rest.replace(".", ",").split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(path):
    cues = []
    text_all = Path(path).read_text(encoding="utf-8-sig", errors="replace").strip()
    for block in re.split(r"\n\s*\n", text_all):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        idx = 1 if "-->" in lines[1] else 0
        if "-->" not in lines[idx]:
            continue
        a, b = lines[idx].split("-->")[:2]
        text = " ".join(lines[idx + 1:])
        text = re.sub(r"<[^>]+>", "", text)  # html-ish tags from vtt
        text = text.replace("\\h", " ").replace(" ", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            cues.append((parse_ts(a), parse_ts(b.split()[0]), text))
    return cues


def dedupe_rolling(cues):
    """YouTube auto-captions repeat the previous line in each cue; drop text already seen."""
    out, prev = [], ""
    for a, b, text in cues:
        if prev and text.startswith(prev):
            text = text[len(prev):].strip()
        if text:
            out.append((a, b, text))
            prev = text
    return out


def write_srt(cues, path, offset):
    out = [f"{i}\n{ts(a - offset)} --> {ts(b - offset)}\n{text}\n" for i, (a, b, text) in enumerate(cues, 1)]
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")


SENT_END = re.compile(r'[.!?]["\')\]]?$')
SENT_SPLIT = re.compile(r'(?:(?<=[.!?])|(?<=[.!?]["\')\]]))\s+(?=["\'(\[]?[A-Z0-9])')


def to_paragraphs(cues):
    """Join cue text into sentences, then paragraphs; break on long pauses or every ~6 sentences."""
    pieces_all, prev_end = [], None
    for a, b, text in cues:
        text = re.sub(r"^[A-Z][a-z]+:\s*", "", text)  # speaker label like "Vanessa:"
        if not text:
            continue
        gap = 0 if prev_end is None else a - prev_end
        for j, piece in enumerate(SENT_SPLIT.split(text)):
            pieces_all.append((piece, gap if j == 0 else 0))
        prev_end = b
    sentences, cur, cur_gap = [], "", 0
    for piece, gap in pieces_all:
        if not cur:
            cur_gap = gap
        cur = (cur + " " + piece).strip()
        if SENT_END.search(cur):
            sentences.append((cur, cur_gap))
            cur = ""
    if cur:
        sentences.append((cur + ".", cur_gap))
    paras, cur = [], []
    for sent, gap in sentences:
        if cur and ((gap >= 1.5 and len(cur) >= 3) or len(cur) >= 7):
            paras.append(" ".join(cur))
            cur = []
        cur.append(sent)
    if cur:
        paras.append(" ".join(cur))
    return paras


# ---------------------------------------------------------------- docx helpers
def set_font(run, size, bold=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")


def new_document():
    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Cm(2.0)
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(13)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    style.paragraph_format.line_spacing = 1.5
    return doc


def add_page(doc, title, i, n, start, end, paras, last):
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(h.add_run(title), 17, bold=True)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(sub.add_run(f"Part {i} / {n}   ({label(start)} - {label(end)})"), 12, bold=True)
    doc.add_paragraph()
    for para in paras:
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Cm(0.92)
        p.paragraph_format.space_after = Pt(6)
        set_font(p.add_run(para), 13)
    if not last:
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ---------------------------------------------------------------- file discovery
def find_ffmpeg(explicit):
    if explicit:
        return Path(explicit)
    exe = shutil.which("ffmpeg")
    if exe:
        return Path(exe).parent
    local = os.environ.get("LOCALAPPDATA", "")
    hits = glob.glob(os.path.join(local, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "ffmpeg-*", "bin", "ffmpeg.exe"))
    if hits:
        return Path(sorted(hits)[-1]).parent
    sys.exit("ffmpeg not found: install it (winget install Gyan.FFmpeg) or pass --ffmpeg DIR")


def find_srt(video):
    stem = video.with_suffix("")
    for cand in [Path(str(stem) + ".en.srt"), Path(str(stem) + ".srt")] + sorted(video.parent.glob(glob.escape(stem.name) + ".*.srt")):
        if cand.exists():
            return cand
    return None


def split_name(video):
    """'18 - THINK and SPEAK in English： your daily routine [nnDVoc5GwSc]' -> ('18', 'THINK and SPEAK in English - your daily routine')"""
    stem = video.stem
    stem = re.sub(r"\s*\[[\w-]{11}\]\s*$", "", stem)  # trailing youtube id
    m = re.match(r"^(\d+)\s*[-._ ]\s*(.+)$", stem)
    prefix, title = (m.group(1), m.group(2)) if m else (stem[:20], stem)
    title = title.replace("：", " -").replace("？", "?").replace("！", "!").replace("｜", "-")
    title = re.sub(r'[\\/:*?"<>|]', "-", title)
    return prefix, re.sub(r"\s+", " ", title).strip()


# ---------------------------------------------------------------- main work
def process(video, srt, out_root, ffdir, target, min_len, copy_mode):
    ffmpeg, ffprobe = str(ffdir / "ffmpeg.exe"), str(ffdir / "ffprobe.exe")
    prefix, title = split_name(video)
    out = Path(out_root) if out_root else video.parent / f"{prefix} - {title[:40]} (MP3拆分)"
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    duration = float(subprocess.check_output(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)]).decode().strip())
    cues = dedupe_rolling(parse_srt(srt))
    lengths = plan(duration, target, min_len)
    bounds = [0.0]
    for length in lengths:
        bounds.append(bounds[-1] + length)
    bounds[-1] = duration
    manifest = {"source": str(video.resolve()), "source_duration": duration,
                "target_seconds": target, "minimum_seconds": min_len, "parts": []}
    print(f"\n== {video.name}\n   {duration / 60:.1f} min -> {len(lengths)} parts, cuts at {[label(b) for b in bounds]}", flush=True)

    doc = new_document()
    for i in range(1, len(bounds)):
        start, end = bounds[i - 1], bounds[i]
        tag = f"{prefix}-{i:02d}"
        base = out / f"{tag} {title} ({label(start)}-{label(end)})"
        if copy_mode:
            codec = ["-c:a", "copy"]
        else:
            codec = ["-c:a", "libmp3lame", "-b:a", "192k"]
        cmd = [ffmpeg, "-n", "-v", "error", "-ss", f"{start:.3f}", "-i", str(video), "-t", f"{end - start:.3f}",
               "-map", "0:a:0", "-vn", *codec, str(base) + ".mp3"]
        print(f"   [{tag}] {label(start)} -> {label(end)} ...", end=" ", flush=True)
        subprocess.run(cmd, check=True)
        manifest["parts"].append({"file": base.name + ".mp3", "start": start, "end": end})
        part = [(max(a, start), min(b, end), t) for a, b, t in cues if not (b <= start or a >= end)]
        write_srt(part, str(base) + ".en.srt", start)
        add_page(doc, title, i, len(lengths), start, end, to_paragraphs(part), last=(i == len(lengths)))
        print(f"{len(part)} cues", flush=True)
    docx_path = out / f"{prefix} {title} - 文稿.docx"
    doc.save(str(docx_path))
    (out / "split_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   docx: {docx_path.name}\n   -> {out}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="MP3 file or folder of MP3 files")
    ap.add_argument("--target", type=float, default=6.0, help="minutes per part (default 6)")
    ap.add_argument("--min", dest="min_len", type=float, default=None, help="minimum minutes per part (default 0.7*target)")
    ap.add_argument("--out", default=None, help="output folder (single video) or output root (folder mode)")
    ap.add_argument("--ffmpeg", default=None, help="folder containing ffmpeg.exe and ffprobe.exe")
    ap.add_argument("--copy", action="store_true", help="stream-copy instead of re-encoding")
    ap.add_argument("--srt", default=None, help="subtitle file (single video only)")
    args = ap.parse_args()

    if not math.isfinite(args.target) or args.target <= 0:
        ap.error("--target must be positive and finite")
    minimum = args.min_len if args.min_len is not None else args.target * 0.7
    if not math.isfinite(minimum) or not 0 < minimum <= args.target:
        ap.error("--min must be positive and no greater than --target")
    target = args.target * 60
    min_len = minimum * 60
    ffdir = find_ffmpeg(args.ffmpeg)
    src = Path(args.input)

    if src.is_dir():
        videos = sorted(p for p in src.glob("*.mp3"))
        done, skipped = 0, []
        for v in videos:
            srt = find_srt(v)
            if not srt:
                skipped.append(v.name)
                continue
            out_root = Path(args.out) / f"{split_name(v)[0]} - {split_name(v)[1][:40]} (MP3拆分)" if args.out else None
            process(v, srt, out_root, ffdir, target, min_len, args.copy)
            done += 1
        print(f"\nDone: {done} MP3 lessons split." + (f" Skipped (no .srt): {skipped}" if skipped else ""))
    else:
        srt = Path(args.srt) if args.srt else find_srt(src)
        if not srt or not srt.exists():
            sys.exit(f"no subtitle found for {src.name}; pass --srt FILE")
        process(src, srt, args.out, ffdir, target, min_len, args.copy)


if __name__ == "__main__":
    main()
