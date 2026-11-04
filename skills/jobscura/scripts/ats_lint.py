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
STANDARD_HEADINGS = {
    "experience": re.compile(r"^(?:work |professional |relevant |employment )?(?:experience|history|employment)\b", re.I),
    "education": re.compile(r"^(?:education|academic|qualifications|training)\b", re.I),
    "skills": re.compile(r"^(?:skills|technical skills|core skills|competenc|expertise|tools)\b", re.I),
}
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


class Findings:
    def __init__(self):
        self.items = []

    def add(self, code, severity, message, evidence=None):
        item = {"id": code, "severity": severity, "message": message}
        if evidence is not None:
            item["evidence"] = evidence
        self.items.append(item)


def text_checks(text, findings, facts):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    facts["words"] = len(re.findall(r"\b\w+\b", text))
    facts["has_email"] = bool(EMAIL.search(text))
    facts["has_phone"] = bool(PHONE.search(text))
    found = {name for name, pattern in STANDARD_HEADINGS.items() if any(pattern.match(line) and len(line) <= 40 for line in lines)}
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
    odd = sorted({c for c in text if 0xE000 <= ord(c) <= 0xF8FF})
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
                     tracked_insertions=count("ins"), tracked_deletions=count("del") + count("moveFrom"),
                     comment_references=count("commentReference"))
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
        # w:vanish is an on/off property: val="0", "false" or "off" explicitly makes text visible.
        hidden_runs = sum(1 for v in root.iter(W + "vanish")
                          if (v.get(W + "val") or "true").strip().casefold() not in {"0", "false", "off"})
        white_runs = sum(1 for c in root.iter(W + "color") if (c.get(W + "val") or "").upper() in {"FFFFFF", "FFFFFE"})
        tiny_runs = sum(1 for s in root.iter(W + "sz") if (s.get(W + "val") or "").isdigit() and int(s.get(W + "val")) <= 4)
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


def lint(path):
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
        text_checks(text, findings, facts)
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
    args = parser.parse_args(argv)
    return common.run_cli(lambda: common.emit(lint(args.document), args.out))


if __name__ == "__main__":
    raise SystemExit(main())
