# -*- coding: utf-8 -*-
"""按 pages.json 生成每集 MP3（一页 PDF = 一集）。

用法：python make_episode.py <工作目录>/pages.json --out <音频目录> all      # 全部
      python make_episode.py <工作目录>/pages.json --out <音频目录> 1 2 3  # 指定集（全局序号）
已存在的集会跳过；要重做先删掉对应 mp3。

规则：edge-tts 云希 +8%；每段单独合成并裁掉首尾静音，条与条之间停 2 秒、段与段之间停 1 秒
（分段规则与 PDF 一致）；英文原句不读；垫柔和合成和弦底乐，整体 -16 LUFS，128k MP3。
文件名：NN_<类别>_第N集.mp3
"""
import argparse, asyncio, json, os, re, subprocess, sys
import edge_tts
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zh_lines import paras as split_paras

ap = argparse.ArgumentParser()
ap.add_argument("pages")
ap.add_argument("--out", required=True)
ap.add_argument("--voice", default="zh-CN-YunxiNeural")
ap.add_argument("--rate", default="+8%")
ap.add_argument("--gap-item", type=float, default=2.0)
ap.add_argument("--gap-para", type=float, default=1.0)
ap.add_argument("--no-music", action="store_true")
ap.add_argument("which", nargs="+")
A = ap.parse_args()
SR = 24000
P = json.load(open(A.pages, encoding="utf-8"))["pages"]
TMP = os.path.join(os.path.dirname(os.path.abspath(A.pages)), "ep_tmp")

def speakable(t):
    """去掉英文原句，只读中文；清理残留括号和整段包裹的引号"""
    t = re.sub(r"[A-Za-z][A-Za-z0-9 ,.'’‘!?;:\-\"“”()]*[A-Za-z.!?\"”)]", "", t)
    t = re.sub(r"[（(]\s*[）)]", "", t).strip()
    m = re.fullmatch(r"[（(](.*)[）)]", t, flags=re.S)
    if m:
        t = m.group(1)
    t = re.sub(r"^[“\"](.*)[”\"]$", r"\1", t.strip(), flags=re.S)
    return t.strip(" 。.\n") + "。" if re.search(r"[一-鿿]", t) else ""

def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    return float(r.stdout.strip())

async def tts(text, path):
    for _ in range(3):
        try:
            await edge_tts.Communicate(text, A.voice, rate=A.rate).save(path); return
        except Exception:
            await asyncio.sleep(2)
    raise RuntimeError("TTS 失败: " + text[:30])

def main(n):
    ep = P[n - 1]
    name = re.sub(r"\s*·\s*", "·", ep["cat"])
    out = os.path.join(A.out, f"{n:02d}_{name}_第{ep['ep']}集.mp3")
    if os.path.exists(out):
        print("已存在，跳过", out); return
    work = os.path.join(TMP, f"{n:02d}"); os.makedirs(work, exist_ok=True)

    clips, jobs = [], []
    for ii, it in enumerate(ep["items"]):
        ps = [p for p in (speakable(x) for x in split_paras(it["t"])) if p]
        for pi, p in enumerate(ps):
            path = os.path.join(work, f"{ii:03d}_{pi:02d}.mp3")
            jobs.append(tts(p, path))
            clips.append((path, A.gap_para if pi < len(ps) - 1 else A.gap_item))

    async def go():
        sem = asyncio.Semaphore(6)
        async def lim(j):
            async with sem: await j
        await asyncio.gather(*(lim(j) for j in jobs))
    asyncio.run(go())

    # 裁掉每段首尾静音，停顿完全由 gap 控制
    trim = "silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse"
    wavs = []
    for path, gap in clips:
        w = path[:-4] + ".wav"
        run(["ffmpeg", "-y", "-i", path, "-af", trim, "-ar", str(SR), "-ac", "1", w])
        wavs.append((w, gap))

    lst, sil = os.path.join(work, "list.txt"), {}
    with open(lst, "w", encoding="utf-8") as f:
        for path, gap in wavs[:-1] + [(wavs[-1][0], 0)]:
            f.write(f"file '{path.replace(os.sep, '/')}'\n")
            if gap:
                if gap not in sil:
                    sp = os.path.join(work, f"sil_{gap}.wav")
                    run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono", "-t", str(gap), "-c:a", "pcm_s16le", sp])
                    sil[gap] = sp
                f.write(f"file '{sil[gap].replace(os.sep, '/')}'\n")
    voice = os.path.join(work, "voice.wav")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "44100", "-ac", "2", voice])

    os.makedirs(A.out, exist_ok=True)
    lead, tail = 0.8, 2.0
    total = lead + dur(voice) + tail
    if A.no_music:
        run(["ffmpeg", "-y", "-i", voice, "-af", f"adelay={int(lead*1000)}|{int(lead*1000)},apad,atrim=0:{total:.2f},loudnorm=I=-16:TP=-1.5",
             "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "128k", out])
    else:  # 柔和合成和弦底乐：5 个正弦音缓慢起伏 + 低通 + 回声
        notes = [110.0, 164.81, 220.0, 261.63, 329.63]
        inputs = ["-i", voice]
        filt = [f"[0:a]adelay={int(lead*1000)}|{int(lead*1000)},apad,atrim=0:{total:.2f}[v]"]
        for m, fr in enumerate(notes):
            inputs += ["-f", "lavfi", "-i", f"sine=frequency={fr}:duration={total:.2f}"]
            filt.append(f"[{m+1}:a]volume='0.5+0.5*sin(2*PI*{0.12+0.05*m}*t)':eval=frame[s{m}]")
        filt.append("".join(f"[s{m}]" for m in range(len(notes))) +
                    f"amix=inputs={len(notes)},lowpass=f=900,aecho=0.8:0.7:600|1100:0.35|0.25,volume=0.16,"
                    f"afade=t=in:d=2,afade=t=out:st={total-2.5:.2f}:d=2.5,aformat=channel_layouts=stereo[pad]")
        filt.append("[v][pad]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5[out]")
        run(["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
             "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "128k", out])
    print(f"完成 {out}  {dur(out)/60:.1f} 分钟（预估 {ep['min']}）, {len(ep['items'])} 篇, {len(clips)} 段", flush=True)

if __name__ == "__main__":
    which = range(1, len(P) + 1) if A.which == ["all"] else [int(x) for x in A.which]
    failed = []
    for n in which:
        for attempt in range(3):
            try:
                main(n); break
            except Exception as e:
                print("第", n, "集失败，重试：", e, flush=True)
        else:
            failed.append(n)
    print("失败的集：", failed or "无")
