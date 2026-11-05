#!/usr/bin/env python3
"""Offline parse-safety and hygiene lint for an application document (.docx, .pdf, .txt).

Finds what commonly breaks applicant-tracking parsing or leaks private material:
tables, text boxes, multi-column layouts, contact details only in headers/footers,
image-only PDFs, encryption, tracked changes, comments, hidden or white text
(keyword stuffing), macros, embedded files and identifying metadata.

Heuristics, not a vendor ATS: parsers differ, and a clean result is not a
guarantee. Never edits the document.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import zlib

import jobscura_common as common
from jobscura_common import W, ToolError, excerpt, require

VERSION = "1.0.0"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]?\d{3,4}[\s.-]?\d{3,4}")
# Independently authored vocabulary; complete phrases keep prose out of sections.
HEADING_SYNONYMS = {
    "en": {"experience": ("experience", "work experience", "professional experience", "relevant experience", "volunteer experience", "employment experience", "work history", "career history", "professional history", "employment history", "employment"),
           "education": ("education", "academic", "qualifications", "training"),
           "skills": ("skills", "technical skills", "core skills", "competencies", "expertise", "tools"),
           "projects": ("projects",), "summary": ("summary", "profile", "objective"),
           "certifications": ("certifications", "licenses"), "awards": ("awards",),
           "publications": ("publications",), "volunteer": ("volunteer",),
           "languages": ("languages",), "interests": ("interests",), "references": ("references",)},
    "es": {"experience": ("experiencia", "experiencia laboral", "experiencia profesional"),
           "education": ("educación", "formación", "formación académica"),
           "skills": ("habilidades", "competencias", "aptitudes")},
    "fr": {"experience": ("expérience", "expériences", "expérience professionnelle", "expériences professionnelles"),
           "education": ("formation", "formations", "éducation"),
           "skills": ("compétences", "compétences techniques")},
    "pt": {"experience": ("experiência", "experiência profissional"),
           "education": ("educação", "formação", "formação acadêmica", "formação académica"),
           "skills": ("habilidades", "competências")},
    "de": {"experience": ("berufserfahrung", "erfahrung", "beruflicher werdegang"),
           "education": ("ausbildung", "bildung", "studium"),
           "skills": ("fähigkeiten", "kenntnisse", "kompetenzen")},
    "it": {"experience": ("esperienza", "esperienze", "esperienza professionale", "esperienze professionali"),
           "education": ("istruzione", "formazione"),
           "skills": ("competenze", "abilità")},
}
STANDARD_HEADINGS = {"experience", "education", "skills"}
JOINER = re.compile(r"\s+(?:&|and|y|et|e|und)\s+", re.I)

DATE_STYLES = {
    "Mon YYYY": re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? (?:19|20)\d{2}\b"),
    "MM/YYYY": re.compile(r"\b(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}\b"),
    "YYYY-MM": re.compile(r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])\b"),
}
CORE = {"creator": "{http://purl.org/dc/elements/1.1/}creator",
        "last_modified_by": "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}lastModifiedBy",
        "title": "{http://purl.org/dc/elements/1.1/}title",
        "subject": "{http://purl.org/dc/elements/1.1/}subject",
        "description": "{http://purl.org/dc/elements/1.1/}description",
        "keywords": "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}keywords"}
APP_COMPANY = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}Company"
APP_TEMPLATE = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}Template"


# ------------------------------------------------------------------ parse preview
# What a simple rule-based resume parser would probably extract: contact block, section
# titles, dated experience entries and education lines. Independent rules, inspired by the
# documented approach of open-source parsers (profile block + section titles + field scoring).
DATE_TOKEN = (r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(?:19|20)\d{2}"
              r"|(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}|(?:19|20)\d{2})")
DATE_RANGE = re.compile(DATE_TOKEN + r"\s*(?:-|–|—|to|until)\s*(?:" + DATE_TOKEN + r"|present|current|now|today)", re.I)
INSTITUTION = re.compile(r"\b(university|college|institute|school|academy|polytechnic|conservatoire)\b", re.I)
DEGREE = re.compile(r"\b(bachelor\w*|master\w*|ph\.?\s?d|doctorate|diploma|certificate|associate|mba|b\.?sc|m\.?sc|b\.?a|m\.?a|"
                    r"gcse|a-levels?)\b", re.I)
LINK = re.compile(r"(?:https?://|www\.)\S+|\b(?:linkedin\.com|github\.com)/\S+", re.I)
PLACE = re.compile(r"\b[A-Z][a-zA-Z.'\- ]{1,40},\s*(?:[A-Z]{2}\b|[A-Z][a-zA-Z]+)")


def heading_text(line):
    raw = line.strip().rstrip(":")
    text = " ".join(raw.split())
    letters = text.split()
    # Only rejoin capitals, never ordinary prose or short initialisms.
    if len(letters) >= 5 and all(len(c) == 1 and c.isalpha() and c.isupper() for c in letters):
        return " ".join("".join(word.split()) for word in re.split(r"\s{2,}", raw))
    return text


def heading_sections(line, lang=None):
    normalized = heading_text(line)
    text = normalized.casefold()
    tables = HEADING_SYNONYMS.values() if lang is None else (HEADING_SYNONYMS[lang],)
    lookup = {word: canonical for table in tables for canonical, words in table.items() for word in words}
    if text in lookup:
        return [lookup[text]]
    parts = JOINER.split(text)
    if len(parts) > 1 and all(part in lookup for part in parts):
        return list(dict.fromkeys(lookup[part] for part in parts))
    words = text.split()
    styled = normalized.isupper() or all(
        word[:1].isupper() or word.casefold() in {"of", "&"} for word in normalized.split())
    # Restrict the flexible route to labels, keeping sentences and possessives out.
    if (1 < len(words) <= 4 and styled and
            not set(words) & {"in", "and", "or", "my", "your", "y", "et", "e", "und"} and
            not re.search(r"[:.!?]", text)):
        for word in (words[0], words[-1]):
            if word in lookup:
                return [lookup[word]]
    return []


def section_of(line, lang=None):
    sections = heading_sections(line, lang)
    return sections[0] if sections else None


def name_score(line, lang=None):
    text = line.strip()
    words = text.split()
    score = 0
    if re.fullmatch(r"[A-Za-zÀ-ɏ .'\-]+", text):
        score += 3
    if 2 <= len(words) <= 4:
        score += 2
    if text.isupper() or all(w[0].isupper() for w in words if w[0].isalpha()):
        score += 1
    if "@" in text or re.search(r"\d|https?:|www\.", text):
        score -= 5
    if section_of(text, lang) or re.search(r"\b(resume|résumé|curriculum vitae|cv)\b", text, re.I):
        score -= 4
    if len(words) > 5:
        score -= 3
    return score


def parse_preview(text, lang=None):
    lines = [(n, l.strip()) for n, l in enumerate(text.splitlines(), 1) if l.strip()]
    sections, current, profile = [], None, []
    for number, line in lines:
        canonical = section_of(line, lang)
        if canonical:
            current = {"title": heading_text(line), "as": canonical, "line": number, "lines": []}
            sections.append(current)
        elif current is None:
            profile.append((number, line))
        else:
            current["lines"].append((number, line))
    head = profile[:8]
    scored = sorted(((name_score(l, lang), n, l) for n, l in head), key=lambda x: (-x[0], x[1]))
    name = scored[0] if scored and scored[0][0] > 0 else None
    first = lambda pattern, pool: next((m.group(0) for _, l in pool for m in [pattern.search(l)] if m), None)
    contact = {"email": first(EMAIL, head), "phone": first(PHONE, head),
               "location": next((m.group(0) for _, l in head if "@" not in l for m in [PLACE.search(l)] if m), None),
               "links": [m.group(0) for _, l in head for m in LINK.finditer(l)][:5]}
    experience, education = [], []
    for section in sections:
        previous = None
        for number, line in section["lines"]:
            match = DATE_RANGE.search(line)
            if section["as"] == "experience" and match:
                heading = line.replace(match.group(0), "").strip(" |,-–—\t") or previous
                experience.append({"line": number, "dates": match.group(0), "heading": excerpt(heading or "", 120)})
            if section["as"] == "education" and (INSTITUTION.search(line) or DEGREE.search(line)):
                education.append({"line": number, "text": excerpt(line, 120)})
            if not common.BULLET.match(line):
                previous = line
    warnings = []
    if not name:
        warnings.append("No line in the top block looks like a name; parsers may leave the name blank.")
    if not contact["email"] and EMAIL.search(text):
        warnings.append("The email appears only below the top block; many parsers read contact details from the top.")
    if not sections:
        warnings.append("No section titles a parser would recognise (Experience, Education, Skills...).")
    elif not any(s["as"] == "experience" for s in sections):
        warnings.append("No experience section title was recognised.")
    elif not experience:
        warnings.append("Experience entries have no recognisable date range (e.g. 'Jan 2021 - Present').")
    return {"name": name[2] if name else None, "contact": contact,
            "sections": [{"title": s["title"], "read_as": s["as"], "line": s["line"]} for s in sections],
            "experience_entries": experience, "education_lines": education, "warnings": warnings,
            "limits": "Heuristic preview of a simple rule-based parser; commercial systems differ."}


class Findings:
    def __init__(self):
        self.items = []

    def add(self, code, severity, message, evidence=None):
        item = {"id": code, "severity": severity, "message": message}
        if evidence is not None:
            item["evidence"] = evidence
        self.items.append(item)


def text_checks(text, findings, facts, lang=None):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    facts["words"] = len(re.findall(r"\b\w+\b", text))
    facts["has_email"] = bool(EMAIL.search(text))
    facts["has_phone"] = bool(PHONE.search(text))
    found = {name for line in lines for name in heading_sections(line, lang) if name in STANDARD_HEADINGS}
    facts["standard_sections"] = sorted(found)
    missing = sorted(set(STANDARD_HEADINGS) - found)
    if missing:
        findings.add("nonstandard_section_headings", "warning",
                     "Common parsers look for conventional headings; none found for: " + ", ".join(missing) +
                     ". Rename creative headings if this is a resume (ignore for letters).")
    styles = {name for name, pattern in DATE_STYLES.items() if pattern.search(text)}
    facts["date_styles"] = sorted(styles)
    if len(styles) > 1:
        findings.add("mixed_date_formats", "info", "Several date formats are used; one consistent style parses more reliably.",
                     sorted(styles))
    spaced = [line for line in lines if heading_text(line) != line.rstrip(":").strip()
              and section_of(line, lang) and re.fullmatch(r"(?:[^\W\d_]\s+){4,}[^\W\d_]:?", line)]
    if spaced:
        findings.add("letter_spaced_headings", "warning",
                     "Some parsers read letter-spaced headings as separate letters.", spaced)
    cid = re.findall(r"\(cid:\d+\)", text)
    remainder = re.sub(r"\(cid:\d+\)", "", text)
    private = lambda c: (0xE000 <= ord(c) <= 0xF8FF or 0xF0000 <= ord(c) <= 0xFFFFD
                         or 0x100000 <= ord(c) <= 0x10FFFD)
    counts = {"cid": len(cid), "replacement": text.count("\ufffd"),
              "private_use": sum(private(c) for c in text),
              "ligature": sum(0xFB00 <= ord(c) <= 0xFB06 for c in text)}
    # A CID placeholder represents one extracted glyph, not its seven-plus ASCII characters.
    visible = sum(not c.isspace() for c in remainder) + len(cid)
    ratio = sum(counts.values()) / visible if visible else 0.0
    facts["garbled_glyphs"] = {"classes": {k: v for k, v in counts.items() if v},
                               "visible_characters": visible, "ratio": ratio}
    if ratio >= 0.005:
        findings.add("garbled_glyphs", "blocker" if ratio >= 0.05 else "warning",
                     "Extracted text contains suspect glyphs: " + ", ".join(k for k, v in counts.items() if v) +
                     ". Check the source document and its text export.", facts["garbled_glyphs"])
    odd = sorted({c for c in text if private(c)})
    if odd:
        findings.add("private_use_glyphs", "warning", "Private-use characters (often icon fonts or symbol bullets) may "
                     "extract as garbage.", [f"U+{ord(c):04X}" for c in odd[:10]])


# ------------------------------------------------------------------ DOCX
def lint_docx(data, findings, facts):
    archive, names = common.docx_parts(data)
    with archive:
        if any(n.casefold().endswith("vbaproject.bin") for n in names):
            findings.add("macros_present", "blocker", "The package contains macros (vbaProject.bin). Many systems reject it; "
                         "export a macro-free .docx or PDF.")
        root = common.xml_root(archive, "word/document.xml")
        body_paragraphs = common.docx_paragraphs(root)
        body = "\n".join(body_paragraphs)
        count = lambda tag: sum(1 for _ in root.iter(W + tag))
        facts.update(tables=count("tbl"), text_boxes=count("txbxContent"), images=count("drawing") + count("pict"),
                     tracked_insertions=0, tracked_deletions=0, comment_references=0)
        facts["privacy_parts"] = []
        hidden_runs = white_runs = tiny_runs = 0
        story_names = sorted(n for n in names if re.fullmatch(
            r"word/(?:document|header[^/]*|footer[^/]*|footnotes|endnotes)\.xml", n))
        for name in story_names:
            story = root if name == "word/document.xml" else common.xml_root(archive, name)
            insertions = sum(1 for tag in ("ins", "moveTo") for _ in story.iter(W + tag))
            deletions = sum(1 for tag in ("del", "moveFrom") for _ in story.iter(W + tag))
            facts["tracked_insertions"] += insertions
            facts["tracked_deletions"] += deletions
            facts["comment_references"] += sum(1 for _ in story.iter(W + "commentReference"))
            # Explicit false values disable this on/off property.
            hidden = sum(1 for v in story.iter(W + "vanish")
                         if (v.get(W + "val") or "true").strip().casefold() not in {"0", "false", "off"})
            white = sum(1 for c in story.iter(W + "color")
                        if (c.get(W + "val") or "").upper() in {"FFFFFF", "FFFFFE"})
            tiny = sum(1 for z in story.iter(W + "sz")
                       if (z.get(W + "val") or "").isdigit() and int(z.get(W + "val")) <= 4)
            hidden_runs += hidden
            white_runs += white
            tiny_runs += tiny
            if insertions or deletions or hidden or white or tiny:
                facts["privacy_parts"].append(name)
        if facts["tables"]:
            findings.add("tables", "warning", f"{facts['tables']} table(s). Some parsers read tables out of order or skip "
                         "them; keep core experience in plain paragraphs.")
        if facts["text_boxes"]:
            findings.add("text_boxes", "warning", f"{facts['text_boxes']} text box(es). Text in shapes/text boxes is often "
                         "skipped by parsers.")
        columns = [int(c.get(W + "num", "1")) for c in root.iter(W + "cols") if c.get(W + "num", "1").isdigit()]
        if any(n > 1 for n in columns):
            findings.add("multi_column", "warning", "Multi-column section layout; parsers may interleave the columns.")
        if facts["tracked_insertions"] or facts["tracked_deletions"]:
            findings.add("tracked_changes", "blocker", "Tracked changes are still in the file. Accept or reject all changes "
                         "before sending; deleted text can be recovered by the recipient.")
        if facts["comment_references"] or "word/comments.xml" in names:
            findings.add("comments", "blocker", "Review comments are stored in the file. Delete all comments before sending.")
        if hidden_runs or white_runs or tiny_runs:
            findings.add("hidden_or_invisible_text", "blocker", "Hidden, white or microscopic text found. Parsers read it, "
                         "reviewers may treat it as keyword stuffing; remove it.",
                         {"hidden_runs": hidden_runs, "white_text_runs": white_runs, "tiny_text_runs": tiny_runs})
        if any(n.startswith("word/embeddings/") for n in names):
            findings.add("embedded_objects", "warning", "Embedded files/objects are present; remove them unless requested.")
        side = []
        for name in sorted(n for n in names if re.fullmatch(r"word/(?:header|footer)\d*\.xml", n)):
            side.append("\n".join(common.docx_paragraphs(common.xml_root(archive, name))))
        side_text = "\n".join(side)
        facts["header_footer_has_contact"] = bool(EMAIL.search(side_text) or PHONE.search(side_text))
        if facts["header_footer_has_contact"] and not (EMAIL.search(body) or PHONE.search(body)):
            findings.add("contact_only_in_header_footer", "warning", "Contact details appear only in the header/footer, "
                         "which some parsers ignore. Repeat them in the body.")
        metadata = {}
        if "docProps/core.xml" in names:
            core = common.xml_root(archive, "docProps/core.xml")
            for key, tag in CORE.items():
                node = core.find(tag)
                if node is not None and (node.text or "").strip():
                    metadata[key] = excerpt(node.text, 120)
        if "docProps/app.xml" in names:
            app = common.xml_root(archive, "docProps/app.xml")
            for key, tag in (("company", APP_COMPANY), ("template", APP_TEMPLATE)):
                node = app.find(tag)
                if node is not None and (node.text or "").strip():
                    metadata[key] = excerpt(node.text, 120)
        facts["metadata"] = metadata
        exposed = {k: v for k, v in metadata.items() if k in {"creator", "last_modified_by", "company", "description", "keywords"}}
        if exposed:
            findings.add("identifying_metadata", "info", "Document properties travel with the file. Confirm these are "
                         "intended (an old employer, another person or a template author can show here).", exposed)
    return body


# ------------------------------------------------------------------ PDF
STREAM = re.compile(rb"<<(?P<dict>(?:(?!>>).){0,2000}?)>>\s*stream\r?\n", re.S)
TEXT_OPERATOR = re.compile(rb"(?:\)|>|\])\s*(?:Tj|TJ|'|\")")
PDF_META = re.compile(rb"/(Author|Creator|Producer|Title|Subject|Keywords)\s*\((.{0,200}?)(?<!\\)\)", re.S)


def lint_pdf(data, findings, facts):
    require(data.startswith(b"%PDF-"), "file is not a PDF (missing %PDF- header)")
    facts["pages"] = len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))
    facts["encrypted"] = b"/Encrypt" in data
    facts["javascript"] = bool(re.search(rb"/(?:JS|JavaScript)\b", data))
    facts["forms"] = b"/AcroForm" in data
    facts["fonts"] = len(re.findall(rb"/Type\s*/Font\b", data))
    facts["images"] = len(re.findall(rb"/Subtype\s*/Image\b", data))
    text_ops, budget, inspected = 0, 60 * 1024 * 1024, 0
    for match in STREAM.finditer(data):
        start = match.end()
        end = data.find(b"endstream", start)
        if end < 0:
            break
        raw = data[start:end]
        content = raw
        if b"/FlateDecode" in match.group("dict"):
            try:
                inflater = zlib.decompressobj()
                content = inflater.decompress(raw, 20 * 1024 * 1024)
            except zlib.error:
                continue
        inspected += len(content)
        if inspected > budget:
            break
        text_ops += len(TEXT_OPERATOR.findall(content))
    facts["text_operators"] = text_ops
    if facts["encrypted"]:
        findings.add("encrypted_pdf", "blocker", "The PDF is encrypted or permission-restricted; many systems cannot read it. "
                     "Export an unrestricted PDF.")
    if facts["javascript"]:
        findings.add("pdf_javascript", "blocker", "The PDF contains JavaScript; security filters may reject it.")
    if not text_ops and not facts["encrypted"]:
        findings.add("no_text_layer", "blocker" if facts["images"] else "warning",
                     "No text-drawing operators found: this looks like an image-only or outlined PDF that a parser "
                     "cannot read. Export from the source document with selectable text.")
    if facts["pages"] > 3:
        findings.add("long_document", "info", f"{facts['pages']} pages; check the employer's length guidance.")
    metadata = {m.group(1).decode(): excerpt(m.group(2).decode("latin-1", "replace"), 120) for m in PDF_META.finditer(data)}
    facts["metadata"] = metadata
    exposed = {k: v for k, v in metadata.items() if k in {"Author", "Keywords", "Subject"}}
    if exposed:
        findings.add("identifying_metadata", "info", "PDF properties travel with the file; confirm they are intended.", exposed)
    return ""


def lint(path, lang=None):
    require(lang is None or lang in HEADING_SYNONYMS, "unsupported heading language")
    p = Path(path)
    data = common.read_input(p)
    suffix = p.suffix.casefold()
    findings, facts = Findings(), {"file": p.name, "bytes": len(data), "format": suffix.lstrip(".")}
    if suffix == ".docx":
        text = lint_docx(data, findings, facts)
    elif suffix == ".pdf":
        text = lint_pdf(data, findings, facts)
    elif suffix in {".txt", ".md"}:
        try:
            text = data.decode("utf-8")
        except UnicodeError as exc:
            raise ToolError("text document must be UTF-8") from exc
    else:
        raise ToolError("supported formats: .docx, .pdf, .txt, .md")
    if text:
        text_checks(text, findings, facts, lang)
        preview = parse_preview(text, lang)
        facts["parse_preview"] = preview
        if preview["sections"]:  # resume-like; letters and the headings check above cover the rest
            for warning in preview["warnings"]:
                findings.add("parse_preview", "warning", warning)
    elif suffix == ".pdf":
        facts["parse_preview"] = {"available": False, "why": "no standard-library PDF text extraction; preview the "
                                                             "source DOCX or a text export instead"}
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,100}", p.name):
        findings.add("filename", "info", "Plain ASCII filenames (for example First_Last_Resume.pdf) upload most reliably.")
    order = {"blocker": 0, "warning": 1, "info": 2}
    items = sorted(findings.items, key=lambda f: order[f["severity"]])
    status = ("blocking_issues" if any(f["severity"] == "blocker" for f in items) else
              "warnings" if any(f["severity"] == "warning" for f in items) else "no_issues_found")
    return {"schema_version": 1, "tool": "ats_lint", "tool_version": VERSION, "status": status, "findings": items,
            "facts": facts,
            "limits": "Structural heuristics only. Applicant-tracking systems differ; a clean result is not a "
                      "guarantee, and layout must still be checked visually in a renderer."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("document", help=".docx, .pdf, .txt or .md file")
    parser.add_argument("--out")
    parser.add_argument("--lang", choices=sorted(HEADING_SYNONYMS),
                        help="heading language; omit to accept all supported languages")
    args = parser.parse_args(argv)
    return common.run_cli(lambda: common.emit(lint(args.document, args.lang), args.out))


if __name__ == "__main__":
    raise SystemExit(main())
