#!/usr/bin/env python3
"""Render reviewed, attributed dialogue JSON to separate-language TeX and TXT.

Python standard library only. This command does not translate or compile PDFs.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlsplit


LANGUAGES = ("en", "zh")
LABELS = {
    "en": {"introduction": "Introduction", "body": "Interview transcript",
           "sources": "References and sources", "edition": "English"},
    "zh": {"introduction": "访谈简介", "body": "访谈正文",
           "sources": "引用与资料来源", "edition": "中文"},
}
ESCAPES = {
    "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}",
    "#": r"\#", "$": r"\$", "%": r"\%", "&": r"\&", "_": r"\_",
    "^": r"\textasciicircum{}", "~": r"\textasciitilde{}",
    "\t": r"\hspace*{2em}",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty_string(value, location):
    require(isinstance(value, str) and bool(value.strip()),
            f"{location} must be a nonempty string")
    require(not any(ord(char) < 32 and char not in "\t\r\n" for char in value),
            f"{location} contains an unsupported control character")
    return value


def language_texts(value, location, languages):
    require(isinstance(value, dict), f"{location} must be a language-to-text object")
    require(all(key in LANGUAGES for key in value),
            f"{location} supports only language keys en and zh")
    for language in languages:
        require(language in value, f"{location}.{language} is required for this edition")
    for language, content in value.items():
        nonempty_string(content, f"{location}.{language}")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"JSON contains duplicate object key {key!r}")
        result[key] = value
    return result


def validate(data, requested_languages):
    require(isinstance(data, dict), "The input JSON must be an object")
    document_id = nonempty_string(data.get("document_id"), "document_id")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", document_id),
            "document_id must start with a letter or digit and contain only letters, digits, _, -, or .")
    original_language = data.get("original_language")
    require(original_language in LANGUAGES, "original_language must be en or zh")
    languages = requested_languages or (["en", "zh"] if original_language == "en" else ["zh"])
    require(len(languages) == len(set(languages)), "--languages must not contain duplicates")
    require(all(language in LANGUAGES for language in languages), "Supported languages are en and zh")
    require(original_language != "zh" or languages == ["zh"],
            "A Chinese original may only generate the zh edition; use --languages zh")
    language_texts(data.get("title"), "title", languages)
    for optional_field in ("program", "introduction"):
        if optional_field in data:
            language_texts(data[optional_field], optional_field, languages)
    if "interview_date" in data:
        nonempty_string(data["interview_date"], "interview_date")

    speakers = data.get("speakers")
    require(isinstance(speakers, dict) and bool(speakers), "speakers must be a nonempty object")
    for key, names in speakers.items():
        nonempty_string(key, "speakers key")
        language_texts(names, f"speakers.{key}", languages)

    sources = data.get("sources")
    require(isinstance(sources, list), "sources must be a list (use [] when no bibliography is supplied)")
    source_ids = set()
    for index, source in enumerate(sources):
        location = f"sources[{index}]"
        require(isinstance(source, dict), f"{location} must be an object")
        source_id = nonempty_string(source.get("id"), f"{location}.id")
        require(source_id not in source_ids, f"Duplicate source ID: {source_id}")
        source_ids.add(source_id)
        language_texts(source.get("text"), f"{location}.text", languages)
        if "url" in source:
            url = nonempty_string(source["url"], f"{location}.url")
            require(not any(char.isspace() or ord(char) == 127 for char in url),
                    f"{location}.url must not contain whitespace or control characters; percent-encode them")
            parsed = urlsplit(url)
            require(parsed.scheme.lower() in ("http", "https") and bool(parsed.netloc),
                    f"{location}.url must be an absolute http(s) URL")

    paragraphs = data.get("paragraphs")
    require(isinstance(paragraphs, list) and bool(paragraphs), "paragraphs must be a nonempty list")
    dialogue_ids = set()
    for index, paragraph in enumerate(paragraphs):
        location = f"paragraphs[{index}]"
        require(isinstance(paragraph, dict), f"{location} must be an object")
        dialogue_id = nonempty_string(paragraph.get("id"), f"{location}.id")
        match = re.fullmatch(re.escape(document_id) + r"-D([0-9]{4,})", dialogue_id)
        require(match is not None, f"{location}.id must match {document_id}-D0001 (at least four digits)")
        number = int(match.group(1))
        require(number > 0 and match.group(1) == f"{number:04d}",
                f"{location}.id must use a positive number padded to at least four digits")
        require(dialogue_id not in dialogue_ids, f"Duplicate dialogue ID: {dialogue_id}")
        dialogue_ids.add(dialogue_id)
        speaker = nonempty_string(paragraph.get("speaker"), f"{location}.speaker")
        require(speaker in speakers, f"{location}.speaker {speaker!r} has no entry in speakers")
        language_texts(paragraph.get("text"), f"{location}.text", languages)
        refs = paragraph.get("source_refs")
        require(isinstance(refs, list) and bool(refs), f"{location}.source_refs must be a nonempty list")
        for ref_index, reference in enumerate(refs):
            nonempty_string(reference, f"{location}.source_refs[{ref_index}]")
    return languages


def tex_escape(value):
    # CRLF and CR are line endings; TXT retains the original string verbatim.
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(r"\par\noindent{}" + "\n" if char == "\n"
                   else ESCAPES.get(char, char) for char in value)


def tex_url(value):
    # Keep URL syntax, but encode Unicode and TeX argument delimiters.
    # The original URL is retained in TXT. xurl supports line wrapping.
    return quote(value, safe=":/?#[]@!$&'()*+,;=%-._~")


def font_name(value):
    nonempty_string(value, "font name")
    require(not any(char in value for char in "\\{}[]%#$&_^~\r\n\t"),
            "Font names must be plain family names without TeX syntax or line breaks")
    return value


def render(data, language, fonts, template):
    labels = LABELS[language]
    metadata = []
    if "program" in data:
        metadata.append(data["program"][language])
    if "interview_date" in data:
        metadata.append(data["interview_date"])
    metadata.append(labels["edition"])
    body = []
    plain = [data["title"][language], " · ".join(metadata)]
    if "introduction" in data:
        introduction = data["introduction"][language]
        body.extend([r"\section*{" + labels["introduction"] + "}", tex_escape(introduction), r"\par"])
        plain.extend([labels["introduction"], introduction])
    body.append(r"\section*{" + labels["body"] + "}")
    plain.append(labels["body"])
    for paragraph in data["paragraphs"]:
        speaker = data["speakers"][paragraph["speaker"]][language]
        body.extend([r"\Speaker{" + tex_escape(speaker) + "}{" + tex_escape(paragraph["id"]) + "}",
                     tex_escape(paragraph["text"][language]), r"\par"])
        plain.extend([f"{paragraph['id']} | {speaker}", paragraph["text"][language]])
    if data["sources"]:
        body.append(r"\section*{" + labels["sources"] + "}")
        body.append(r"\begingroup\fontsize{9bp}{11bp}\selectfont")
        plain.append(labels["sources"])
        for source in data["sources"]:
            body.append(r"\Needspace{2\baselineskip}\noindent [" + tex_escape(source["id"]) + "] "
                        + tex_escape(source["text"][language]) + r"\par")
            plain.append(f"[{source['id']}] {source['text'][language]}")
            if "url" in source:
                body.append(r"\nopagebreak[4]\noindent\url{" + tex_url(source["url"]) + r"}\par")
                plain.append(source["url"])
            body.append(r"\smallskip")
        body.append(r"\endgroup")
    values = {
        "TITLE": tex_escape(data["title"][language]),
        "METADATA": tex_escape(" · ".join(metadata)),
        "BODY": "\n".join(body),
        **{key.upper(): value for key, value in fonts.items()},
    }
    required = {"TITLE", "METADATA", "BODY", "LATIN_FONT", "CJK_FONT", "CJK_BOLD_FONT", "CJK_ITALIC_FONT"}
    tokens = set(re.findall(r"@@([A-Z_]+)@@", template))
    require(tokens == required, "paper.tex has missing or unknown template placeholders; restore the skill's template")
    tex = re.sub(r"@@([A-Z_]+)@@", lambda match: values[match.group(1)], template)
    return {f"{language}/main.tex": tex.encode("utf-8"),
            f"{language}/transcript.txt": ("\n\n".join(plain) + "\n").encode("utf-8")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, metavar="INPUT.json")
    parser.add_argument("--output-dir", type=Path, required=True, metavar="NEW_DIRECTORY")
    parser.add_argument("--languages", nargs="+", choices=LANGUAGES, metavar="LANGUAGE",
                        help="default: en zh for an English original, zh for a Chinese original")
    parser.add_argument("--latin-font", default="Times New Roman")
    parser.add_argument("--cjk-font", default="SimSun")
    parser.add_argument("--cjk-bold-font", default="SimHei")
    parser.add_argument("--cjk-italic-font", default="KaiTi")
    args = parser.parse_args(argv)
    output_dir = args.output_dir.expanduser().absolute()
    created_output = False
    try:
        require(not output_dir.exists() and not output_dir.is_symlink(),
                f"Output directory already exists: {output_dir}. Choose a new directory; nothing will be overwritten")
        input_path = args.input.expanduser()
        input_bytes = input_path.read_bytes()
        data = json.loads(input_bytes.decode("utf-8-sig"), object_pairs_hook=unique_object)
        languages = validate(data, args.languages)
        fonts = {name: font_name(getattr(args, name)) for name in
                 ("latin_font", "cjk_font", "cjk_bold_font", "cjk_italic_font")}
        template_path = Path(__file__).resolve().parents[1] / "assets" / "paper.tex"
        template = template_path.read_text(encoding="utf-8")
        files = {}
        for language in languages:
            files.update(render(data, language, fonts, template))
        manifest = {
            "schema_version": 1,
            "document_id": data["document_id"],
            "input_file": input_path.name,
            "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
            "original_language": data["original_language"],
            "languages": languages,
            "paragraph_count": len(data["paragraphs"]),
            "paragraph_ids": [paragraph["id"] for paragraph in data["paragraphs"]],
            "paragraphs": [{key: paragraph[key] for key in ("id", "speaker", "source_refs")}
                           for paragraph in data["paragraphs"]],
            "source_count": len(data["sources"]),
            "font_settings": fonts,
            "output_sha256": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()},
            "compilation_status": "not_run",
            "qa_status": "not_run",
        }
        files["render_manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        # All input, template and font validation finishes before the first write.
        output_dir.mkdir(parents=True, exist_ok=False)
        created_output = True
        for name, content in files.items():
            destination = output_dir / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write(content)
        print(f"Generated {', '.join(languages)} TeX/TXT in {output_dir}; PDF compilation and QA have not run.")
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        if created_output:
            print(f"A partial output directory may remain at {output_dir}; inspect it and retry with a new directory.",
                  file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
