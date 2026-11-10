"""Build / reorganise a 原文集锦 txt.

  assemble <work> <out.txt>                 parse <work>/out*.txt OCR blocks -> uncategorised collection
  list <collection.txt>                     print each entry's number + first 110 chars (for classifying)
  categorize <collection.txt> <map.json>    regroup by {"一、类名": [entry numbers], ...} and add a TOC
  split <collection.txt> <work> [--chars N] -> <work>/ed_inK.txt + cats.json (for paragraph editing)
  join <work> <collection.txt>              rebuild from <work>/ed_outK.txt + cats.json

Collection format: UTF-8 BOM + CRLF, entries separated by a line of 12 U+2014,
category headers wrapped in lines of 24 '=', TOC on top.
"""
import glob
import json
import os
import re
import sys

SEP = "\n\n" + "—" * 12 + "\n\n"
BAR = "=" * 24
PUN = r"[\s，。、；：！？“”‘’「」『』《》（）()…—·,.;:!?\"'\-~～*]"


def core(s):
    return re.sub(PUN, "", s)


def read(p):
    with open(p, encoding="utf-8-sig") as f:
        return f.read().replace("\r", "")


def write(p, text):
    with open(p, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(text.rstrip("\n") + "\n")


def clean(e):
    return re.sub(r"\n{3,}", "\n\n", "\n".join(l.strip() for l in e.split("\n")))


def parse_collection(p):
    """-> (title line, [[category or None, [entries]]])"""
    t = read(p)
    first = t.split("\n", 1)[0].strip()
    if "\n\n\n" + BAR in t:  # categorised
        rest = BAR + t.split("\n\n\n" + BAR, 1)[1]
        cats = []
        for s in re.split(r"\n\n\n(?=" + BAR + ")", rest.strip()):
            m = re.match(BAR + r"\n(.+?)\n" + BAR + r"\n\n(.*)", s, re.S)
            cats.append([m[1], [e.strip() for e in m[2].split(SEP)]])
        return first, cats
    body = t.split(BAR + "\n\n", 1)[1] if BAR in t else t
    return first, [[None, [e.strip() for e in body.split(SEP) if e.strip()]]]


def render(title, cats):
    total = sum(len(es) for _, es in cats)
    if len(cats) == 1 and cats[0][0] is None:
        return f"{title}\n（共 {total} 篇）\n\n{BAR}\n\n" + SEP.join(clean(e) for e in cats[0][1])
    toc = "\n".join(f"{c}（{len(es)} 篇）" for c, es in cats)
    head = f"{title}\n（共 {total} 篇，按主题分类）\n\n目录\n{toc}"
    secs = [f"{BAR}\n{c}\n{BAR}\n\n" + SEP.join(clean(e) for e in es) for c, es in cats]
    return head + "\n\n\n" + "\n\n\n".join(secs)


def load_blocks(p, mark):
    with open(p, encoding="utf-8") as f:
        t = f.read().replace("\r", "")
    # header line must be matched with [^\n]* (never .* under DOTALL)
    pat = r"^" + re.escape(mark) + r" (\d+)[^\n]*\n(.*?)(?=^" + re.escape(mark) + r" |\Z)"
    return {int(m[1]): m[2].strip() for m in re.finditer(pat, t, re.S | re.M)}


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "assemble":
        work, out = argv[2], argv[3]
        blocks = {}
        for f in sorted(glob.glob(os.path.join(work, "out*.txt"))):
            extra = os.path.basename(f).startswith("out0")  # user's own screenshots go last
            blocks.update({(extra, n): b for n, b in load_blocks(f, "###").items()})
        seen, ents = set(), []
        for k in sorted(blocks):
            b = blocks[k]
            if not b or b.startswith("[无文字]") or core(b) in seen:
                continue
            seen.add(core(b))
            ents.append(b)
        name = os.path.splitext(os.path.basename(out))[0].removesuffix("集锦") or "原文"
        write(out, render(f"{name} · 原文集锦", [[None, ents]]))
        print(f"{len(ents)} entries -> {out}")
    elif cmd == "list":
        _, cats = parse_collection(argv[2])
        for i, e in enumerate([e for _, es in cats for e in es], 1):
            print(f"{i:03d} [{len(e)}] {re.sub(r'\s+', ' ', e)[:110]}")
    elif cmd == "categorize":
        title, cats = parse_collection(argv[2])
        ents = [e for _, es in cats for e in es]
        with open(argv[3], encoding="utf-8") as f:
            mp = json.load(f)
        ids = [i for v in mp.values() for i in v]
        missing = set(range(1, len(ents) + 1)) - set(ids)
        dup = {i for i in ids if ids.count(i) > 1}
        if missing or dup:
            sys.exit(f"missing {sorted(missing)} duplicated {sorted(dup)}")
        new = [[c, [ents[i - 1] for i in v]] for c, v in mp.items() if v]
        write(argv[2], render(title, new))
        print("\n".join(f"{c}（{len(es)} 篇）" for c, es in new))
    elif cmd == "split":
        src, work = argv[2], argv[3]
        limit = int(argv[argv.index("--chars") + 1]) if "--chars" in argv else 5500
        title, cats = parse_collection(src)
        n, plan, flat = 0, [], []
        for c, es in cats:
            ids = []
            for e in es:
                n += 1
                ids.append(n)
                flat.append((n, e))
            plan.append([c, ids])
        with open(os.path.join(work, "cats.json"), "w", encoding="utf-8") as f:
            json.dump({"title": title, "cats": plan}, f, ensure_ascii=False)
        chunks, cur, size = [], [], 0
        for i, e in flat:
            cur.append((i, e))
            size += len(e)
            if size > limit:
                chunks.append(cur)
                cur, size = [], 0
        if cur:
            chunks.append(cur)
        for k, ch in enumerate(chunks, 1):
            with open(os.path.join(work, f"ed_in{k}.txt"), "w", encoding="utf-8") as f:
                f.writelines(f"@@@ {i:03d}\n{e}\n\n" for i, e in ch)
            print(f"ed_in{k}.txt: entries {ch[0][0]}-{ch[-1][0]}")
    elif cmd == "join":
        work, dst = argv[2], argv[3]
        with open(os.path.join(work, "cats.json"), encoding="utf-8") as f:
            meta = json.load(f)
        out = {}
        for f in glob.glob(os.path.join(work, "ed_out*.txt")):
            out.update(load_blocks(f, "@@@"))
        want = [i for _, ids in meta["cats"] for i in ids]
        if not set(want) <= set(out):
            sys.exit(f"missing edited entries {sorted(set(want) - set(out))}")
        write(dst, render(meta["title"], [[c, [out[i] for i in ids]] for c, ids in meta["cats"]]))
        short = [i for i in want if len(out[i]) < 300 and "\n\n" in out[i]]
        print(f"rebuilt {len(want)} entries -> {dst}; short entries still containing blank lines: {short}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
