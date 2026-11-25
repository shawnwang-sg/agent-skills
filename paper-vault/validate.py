"""paper-vault 三遍法质量门（references/quality-gates.md 的可执行版本）。

用法：
  python validate.py --vault <vault> <slug>            # 校验一篇，打印报告
  python validate.py --vault <vault> --all             # 校验全部，打印汇总 + 批次体检
  python validate.py --vault <vault> <slug> --write    # 写 reading-audit.json，并由结果决定 meta.reading_status
退出码：有不合格的论文时为 1。
"""
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

# ── 门槛（与 references/quality-gates.md 保持一致）────────────────────────────
RATIO = {"skim": (0.15, 0.25), "grasp": (0.30, 0.45), "master": (0.40, 0.60)}
SKIM_KINDS = {"conclusion", "five_c", "excerpts", "verdict", "questions"}
GRASP_KINDS = {"evidence", "open_questions"}
MASTER_KINDS = {"reproduction", "derivations", "qa", "critique", "future", "structure"}
QA_CATS = {"reproduce", "assumption", "failure", "evidence", "compare"}
QA_MIN, QA_PER_CAT, QA_SHORT_WORDS, QA_SHORT_MAX = 24, 3, 40, 0.20
QA_CITE_MIN = 1 / 3
DERIV_MIN = 12
TERMS_MIN = 8
EVIDENCE_MIN = 3
CRITIQUE_MIN = 8
FUTURE_MIN = 2
MASTER_PARAS = 40            # 正文 ≥ 8000 词时；更短的论文按 词数/200 折算
GRASP_SECTIONS_MIN = 6
SIMILAR_Q = 0.8              # 和其他论文问题的词集合 Jaccard ≥ 0.8 视为模板化
SIMILAR_MAX = 0.20
STATUS_OK, STATUS_BAD = "three_pass_verified", "needs_rework"

FIG_RE = re.compile(r"(?m)^\s*(Figure|Fig\.|Table)\s*(\d+)\s*[:.]")
CITE_RE = re.compile(r"(Figure|Fig\.|Table|Section|§|Eq\.|\d)")


def normalize(text):
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"([A-Za-z])-\s*\n\s*([a-z])", r"\1\2", text)
    text = re.sub(r"(?m)^\s*\d{1,3}\s*$", "", text)
    return " ".join(text.split())


def words(s):
    return len((s or "").split())


def blocks_of(sections):
    for s in sections:
        for b in s.get("blocks", []):
            yield b


def page_texts(folder):
    """逐页的规范化文本：优先用 PDF（pymupdf），否则只有整篇 source.txt。"""
    pdf = folder / "source.pdf"
    try:
        import pymupdf
        return [normalize(p.get_text()) for p in pymupdf.open(pdf)]
    except Exception:
        txt = folder / "source.txt"
        return None if not txt.exists() else [normalize(txt.read_text(encoding="utf-8"))]


def figure_labels(folder):
    txt = folder / "source.txt"
    if not txt.exists():
        return set()
    return {("Table" if m.group(1) == "Table" else "Figure") + " " + m.group(2)
            for m in FIG_RE.finditer(txt.read_text(encoding="utf-8"))}


def provenance_labels(folder):
    f = folder / "assets" / "provenance.json"
    if not f.exists():
        return None
    out = set()
    data = json.loads(f.read_text(encoding="utf-8"))
    if isinstance(data, dict):   # 旧格式：{文件名: {...}} 或 {"crops": [...]}
        data = data.get("crops") or data.get("figures") or [
            dict(v, file=k) if isinstance(v, dict) else {"file": k} for k, v in data.items()]
    for a in data:
        if isinstance(a, str):
            a = {"file": a}
        if a.get("label"):
            out.add(a["label"])
        m = re.match(r"(fig|figure|table)[-_]?(\d+)", a.get("file", ""), re.I)
        if m:
            out.add(("Table" if m.group(1).lower() == "table" else "Figure") + " " + m.group(2))
    return out


def validate(folder, others_q=None):
    """返回 (fails, warns, metrics)。fails 非空即不合格。"""
    fails, warns, M = [], [], {}
    obj = json.loads((folder / "paper.json").read_text(encoding="utf-8"))
    meta, modes = obj.get("meta", {}), obj.get("modes", {})

    # 1. 原始 PDF 先行
    sj = folder / "source.json"
    src = json.loads(sj.read_text(encoding="utf-8")) if sj.exists() else {}
    for f in ("source.pdf", "source.txt", "source.json"):
        if not (folder / f).exists():
            fails.append("缺 %s（先有原始 PDF 再动笔）" % f)
    if (folder / "source.pdf").exists() and src.get("sha256"):
        if hashlib.sha256((folder / "source.pdf").read_bytes()).hexdigest() != src["sha256"]:
            fails.append("source.pdf 和 source.json 的 sha256 不一致")
    sw = int(meta.get("source_words") or src.get("source_words") or 0)
    if not sw:
        fails.append("没有全文词数 source_words")
    elif src.get("source_words") and int(src["source_words"]) != sw:
        fails.append("meta.source_words 和 source.json 不一致（词数必须从 PDF 提取）")
    M["source_words"] = sw
    if set(modes) != {"skim", "grasp", "master"}:
        return fails + ["三个模式不全"], warns, M

    # 2. 原文必须是真原文：只统计 origin=paper，逐字回查对应页
    pages = page_texts(folder)
    whole_pdf = " ".join(pages or [])
    whole_txt = normalize((folder / "source.txt").read_text(encoding="utf-8")) if (folder / "source.txt").exists() else ""
    page_off = 0
    for key in ("skim", "grasp", "master"):
        seen, total, paras = set(), 0, 0
        for b in blocks_of(modes[key]["sections"]):
            if b.get("origin") != "paper" or b.get("type") not in ("p", "quote"):
                continue
            en = normalize(b.get("en"))
            pg = b.get("source_page")
            if not pg:
                fails.append("%s：原文块缺 source_page：%s…" % (key, en[:50]))
            elif pages:
                # 允许 3、"3"、"3-4"、[3, 4]：跨页段落在相邻页拼起来找
                nums = [int(x) for x in re.findall(r"\d+", str(pg))]
                if len(nums) == 2 and nums[1] > nums[0]:
                    nums = list(range(nums[0], nums[1] + 1))
                nums = [n for n in nums if 0 < n <= len(pages)]
                hay = " ".join(pages[n - 1] for n in nums) if len(pages) > 1 and nums else " ".join(pages)
                if en not in hay and (en in whole_pdf or en in whole_txt):
                    page_off += 1
                elif en not in hay:
                    fails.append("%s：原文在第 %s 页找不到（改写过？）：%s…" % (key, pg, en[:50]))
            if en in seen:
                fails.append("%s：原文段重复：%s…" % (key, en[:50]))
            seen.add(en)
            total += words(b.get("en"))
            paras += 1
        r = total / sw if sw else 0
        lo, hi = RATIO[key]
        M[key + "_ratio"] = round(r, 3)
        M[key + "_paras"] = paras
        if not lo <= r <= hi:
            fails.append("%s：原文比例 %.1f%%，要求 %d–%d%%（只算 origin=paper）" % (key, r * 100, lo * 100, hi * 100))

    if page_off:
        warns.append("%d 段原文能在全文找到，但不在标的页码上（页码可能按别的提取方式算的）" % page_off)

    kinds = {k: [s.get("kind") for s in modes[k]["sections"]] for k in modes}

    # 3. 第一遍：鸟瞰
    miss = SKIM_KINDS - set(kinds["skim"])
    if miss:
        fails.append("鸟瞰缺这些部分：%s" % "、".join(sorted(miss)))
    five = [b for s in modes["skim"]["sections"] if s.get("kind") == "five_c"
            for b in s["blocks"] if b.get("type") == "terms"]
    if five and sum(len(b.get("items", [])) for b in five) < 5:
        fails.append("5C 卡不足 5 项")

    # 4. 第二遍：理解
    miss = GRASP_KINDS - set(kinds["grasp"])
    if miss:
        fails.append("理解缺这些部分：%s" % "、".join(sorted(miss)))
    M["grasp_sections"] = len(modes["grasp"]["sections"])
    if M["grasp_sections"] < GRASP_SECTIONS_MIN:
        fails.append("理解只有 %d 节，至少 %d 节（按论文真实章节）" % (M["grasp_sections"], GRASP_SECTIONS_MIN))
    terms = sum(len(b.get("items", [])) for b in blocks_of(modes["grasp"]["sections"]) if b.get("type") == "terms")
    M["terms"] = terms
    if terms < TERMS_MIN:
        fails.append("术语卡 %d 个，至少 %d 个" % (terms, TERMS_MIN))
    ev = sum(len(b.get("items", [])) for s in modes["grasp"]["sections"] if s.get("kind") == "evidence"
             for b in s["blocks"] if b.get("type") == "list")
    M["evidence"] = ev
    if ev < EVIDENCE_MIN:
        fails.append("证据链 %d 条，至少 %d 条" % (ev, EVIDENCE_MIN))

    # 图表全覆盖 + 可追溯
    want = figure_labels(folder)
    have = provenance_labels(folder)
    figs = [b for m in modes.values() for b in blocks_of(m["sections"]) if b.get("type") == "figure"]
    M["figures"] = len(figs)
    M["figure_labels"] = len(want)
    if want:
        if have is None:
            fails.append("缺 assets/provenance.json（裁图的页码、裁框、哈希）")
        else:
            lost = sorted(want - have, key=lambda x: (x.split()[0], int(x.split()[1])))
            if lost:
                fails.append("图表没覆盖：%s" % "、".join(lost[:12]) + ("…" if len(lost) > 12 else ""))
    for b in figs:
        if b.get("src") and not (folder / b["src"]).exists():
            fails.append("图片不存在：%s" % b["src"])
    thin = [b for b in blocks_of(modes["grasp"]["sections"]) if b.get("type") == "figure" and words(b.get("caption_en")) < 15]
    if thin:
        warns.append("%d 张图的解读不到 15 个英文词" % len(thin))

    # 5. 第三遍：吃透
    miss = MASTER_KINDS - set(kinds["master"])
    if miss:
        fails.append("吃透缺这些部分：%s" % "、".join(sorted(miss)))
    need = MASTER_PARAS if sw >= 8000 else max(10, sw // 200)
    if M["master_paras"] < need:
        fails.append("吃透原文 %d 段，至少 %d 段" % (M["master_paras"], need))
    deriv = sum(1 for s in modes["master"]["sections"] if s.get("kind") == "derivations"
                for b in s["blocks"] if b.get("type") == "h3")
    M["derivations"] = deriv
    if deriv < DERIV_MIN:
        fails.append("推演 %d 项，至少 %d 项（每项一个 h3：输入、步骤、结果）" % (deriv, DERIV_MIN))
    qas = [b for b in blocks_of(modes["master"]["sections"]) if b.get("type") == "qa"]
    M["qa"] = len(qas)
    if len(qas) < QA_MIN:
        fails.append("问答 %d 组，至少 %d 组" % (len(qas), QA_MIN))
    cats = Counter(b.get("cat") for b in qas)
    M["qa_cats"] = dict(cats)
    lack = [c for c in sorted(QA_CATS) if cats.get(c, 0) < QA_PER_CAT]
    if lack:
        fails.append("问答类别不足 %d 组：%s" % (QA_PER_CAT, "、".join(lack)))
    if qas:
        short = sum(1 for b in qas if words(b.get("a_en")) < QA_SHORT_WORDS)
        if short / len(qas) > QA_SHORT_MAX:
            fails.append("%d/%d 组问答答案不到 %d 个英文词" % (short, len(qas), QA_SHORT_WORDS))
        cited = sum(1 for b in qas if CITE_RE.search(b.get("a_en") or ""))
        if cited / len(qas) < QA_CITE_MIN:
            fails.append("引用具体图表或数字的答案只有 %d/%d" % (cited, len(qas)))
    if len({normalize(b.get("q_en")) for b in qas}) != len(qas):
        fails.append("问答有重复问题")
    crit = sum(len(b.get("items", [])) for s in modes["master"]["sections"] if s.get("kind") == "critique"
               for b in s["blocks"] if b.get("type") == "list")
    fut = sum(len(b.get("items", [])) for s in modes["master"]["sections"] if s.get("kind") == "future"
              for b in s["blocks"] if b.get("type") == "list")
    M["critique"], M["future"] = crit, fut
    if crit < CRITIQUE_MIN:
        fails.append("强项/弱项/隐藏假设/缺失 共 %d 条，至少 %d 条" % (crit, CRITIQUE_MIN))
    if fut < FUTURE_MIN:
        fails.append("未来工作 %d 条，至少 %d 条" % (fut, FUTURE_MIN))

    # 6. 防模板：和其他论文的问题太像
    if others_q and qas:
        mine = [set(normalize(b.get("q_en")).lower().split()) for b in qas]
        sim = sum(1 for q in mine if any(len(q & o) / max(1, len(q | o)) >= SIMILAR_Q for o in others_q))
        if sim / len(qas) > SIMILAR_MAX:
            fails.append("%d/%d 个问题和其他论文的问题几乎一样（模板化）" % (sim, len(qas)))

    M["signature"] = (len(modes["skim"]["sections"]), len(modes["grasp"]["sections"]),
                      len(modes["master"]["sections"]), len(qas), len(figs))
    return fails, warns, M


def questions_of(folder):
    try:
        obj = json.loads((folder / "paper.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    return [set(normalize(b.get("q_en")).lower().split())
            for b in blocks_of(obj.get("modes", {}).get("master", {}).get("sections", [])) if b.get("type") == "qa"]


def main():
    ap = argparse.ArgumentParser(description="paper-vault 三遍法质量门")
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--vault", default=".")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--write", action="store_true", help="写 reading-audit.json 并更新 meta.reading_status")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    vault = Path(a.vault).resolve()
    folders = sorted(p.parent for p in (vault / "papers").glob("*/paper.json"))
    pick = folders if a.all or not a.slugs else [vault / "papers" / s for s in a.slugs]
    allq = {f.name: questions_of(f) for f in folders}
    results, sig = {}, defaultdict(list)
    for f in pick:
        others = [q for n, qs in allq.items() if n != f.name for q in qs]
        fails, warns, M = validate(f, others)
        results[f.name] = {"pass": not fails, "fails": fails, "warns": warns, "metrics": M}
        sig[M.get("signature")].append(f.name)
        if a.write:
            p = f / "paper.json"
            obj = json.loads(p.read_text(encoding="utf-8"))
            obj["meta"]["reading_status"] = STATUS_OK if not fails else STATUS_BAD
            p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
            audit = {"gate": "paper-vault three-pass quality gates v1", "pass": not fails, "fails": fails,
                     "warns": warns, "metrics": {k: v for k, v in M.items() if k != "signature"},
                     "content_sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            (f / "reading-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    # 批次体检：结构完全一样的论文扎堆 → 多半是批量套模板
    for s, names in sig.items():
        if s and len(names) >= 3:
            for n in names:
                results[n]["warns"].append("和另外 %d 篇结构完全相同 %s（疑似批量套模板）" % (len(names) - 1, s))
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for n, r in results.items():
            print("%s  %s" % ("通过" if r["pass"] else "不合格", n))
            if len(results) == 1 or not r["pass"]:
                for x in r["fails"][: (99 if len(results) == 1 else 3)]:
                    print("    ✗ " + x)
            for x in r["warns"][:2]:
                print("    ! " + x)
        ok = sum(r["pass"] for r in results.values())
        print("\n合计 %d 篇：通过 %d，不合格 %d" % (len(results), ok, len(results) - ok))
    sys.exit(0 if all(r["pass"] for r in results.values()) else 1)


if __name__ == "__main__":
    main()
