"""Check edited entries against the originals.

Usage: python -X utf8 edcheck.py ed_inK.txt ed_outK.txt
Flags entries that deleted more than 10% of their non-punctuation characters,
inserted more than 3 new characters, or lost any character of a quoted sentence.
Ends with "violations N of M".
"""
import difflib
import re
import sys

PUN = r"[\s，。、；：！？“”‘’「」『』《》（）()…—·,.;:!?\"'\-~～*]"


def core(s):
    return re.sub(PUN, "", s)


def load(p):
    with open(p, encoding="utf-8") as f:
        t = f.read().replace("\r", "")
    return {int(m[1]): m[2].strip()
            for m in re.finditer(r"^@@@ (\d+)\n(.*?)(?=^@@@ |\Z)", t, re.S | re.M)}


a, b = load(sys.argv[1]), load(sys.argv[2])
bad = 0
for i in a:
    if i not in b:
        print(i, "MISSING")
        bad += 1
        continue
    x, y = core(a[i]), core(b[i])
    ops = difflib.SequenceMatcher(None, x, y, autojunk=False).get_opcodes()
    dele = sum(i2 - i1 for op, i1, i2, _, _ in ops if op in ("delete", "replace"))
    ins = sum(j2 - j1 for op, _, _, j1, j2 in ops if op in ("insert", "replace"))
    lost = [q for q in re.findall(r"[“「『\"]([^”」』\"]{2,})[”」』\"]", a[i]) if core(q) not in y]
    if dele > max(2, 0.10 * len(x)) or ins > 3 or lost:
        bad += 1
        print(i, f"deleted {dele}/{len(x)} inserted {ins}", ("LOST QUOTE: " + " | ".join(lost)) if lost else "")
print("violations", bad, "of", len(a))
