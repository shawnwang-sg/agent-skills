"""去掉阅读稿里回潮的句尾语气词（啊、呀、嘛、是吧），只动 body，不碰正文意思。

只删紧挨标点前的「啊/呀/嘛」和独立成句的「是吧」，不删词中的字（如「干嘛」里的嘛前面有字，也只在标点前才删）。
用法：python strip_fillers.py <done 里的 json 文件> [...]   会原地改写，并打印每篇删了几处。
"""
import json, re, sys
from pathlib import Path

END = r"(?=[，。！？；：、,.!?;:\n]|$)"
RULES = [
    (re.compile(r"[，,]\s*是吧" + END), ""),          # ……，是吧，
    (re.compile(r"(?<![干])(啊|呀|嘛)+" + END), ""),  # 句尾语气词；保留「干嘛」
    (re.compile(r"(?<=[，。！？])\s*(那么|那)[，,]"), ""),  # 句首孤立的「那，」
    (re.compile(r"[，,]{2,}"), "，"),
]


def clean(s):
    n = 0
    for pat, rep in RULES:
        s, k = pat.subn(rep, s)
        n += k
    s = re.sub(r"，([。！？])", r"\1", s)
    return s, n


def main():
    for f in sys.argv[1:]:
        p = Path(f)
        data = json.loads(p.read_text(encoding="utf-8"))
        total = 0
        for x in data:
            if x.get("body"):
                body, n = clean(x["body"])
                gold, _ = clean(x.get("gold") or "")
                if gold and gold.replace("**", "") in body.replace("**", ""):
                    x["gold"] = gold
                x["body"] = body
                total += n
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(p.name, "删去语气词", total, "处")


if __name__ == "__main__":
    main()
