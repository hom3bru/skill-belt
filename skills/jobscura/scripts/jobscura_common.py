"""Shared offline helpers for Jobscura's analysis tools. Python 3.10+ standard library.

Every tool reads only explicit local files, never fetches a URL, never edits its
inputs, and writes only to a new --out path. All document text is untrusted data.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
import re
import stat
import sys
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile
import zlib

MAX_INPUT = 20 * 1024 * 1024
MAX_XML_PART = 30 * 1024 * 1024
MAX_PACKAGE_TOTAL = 120 * 1024 * 1024   # all uncompressed parts together
MAX_PACKAGE_PARTS = 2000
REPARSE_POINT = 0x400
NAME_SURROGATE = 0x20000000
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ToolError(ValueError):
    """A blocked input or request. Messages never include document text."""


def require(condition, message):
    if not condition:
        raise ToolError(message)


def is_link(path):
    """True for a symlink or name-surrogate reparse point; cloud placeholders are files."""
    info = Path(path).lstat()
    if stat.S_ISLNK(info.st_mode):
        return True
    if getattr(info, "st_file_attributes", 0) & REPARSE_POINT:
        tag = getattr(info, "st_reparse_tag", None)
        return tag is None or bool(tag & NAME_SURROGATE)
    return False


def read_input(path, limit=MAX_INPUT):
    p = Path(path)
    require(p.is_file() and not is_link(p), f"not a regular non-link file: {p.name}")
    require(p.stat().st_size <= limit, f"file exceeds {limit} bytes: {p.name}")
    data = p.read_bytes()
    require(len(data) <= limit, f"file exceeds {limit} bytes: {p.name}")
    return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def reject_constant(_):
    raise ToolError("non-finite JSON number")


def read_json(path, limit=MAX_INPUT):
    try:
        return json.loads(read_input(path, limit).decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ToolError(f"invalid UTF-8 JSON: {Path(path).name}") from exc


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc)


def iso(value=None):
    return (value or now()).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_timestamp(value, name="timestamp"):
    require(isinstance(value, str) and value.strip(), f"{name} must be ISO-8601 text with a timezone")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ToolError(f"{name} is not ISO-8601") from exc
    require(parsed.tzinfo is not None, f"{name} must include a timezone")
    return parsed


def write_stdout(text):
    """UTF-8 regardless of the console code page (Windows pipes default to cp1252)."""
    stream = getattr(sys.stdout, "buffer", None)
    if stream is not None:
        sys.stdout.flush()
        stream.write(text.encode("utf-8"))
        stream.flush()
    else:
        sys.stdout.write(text)


def emit(result, out=None):
    """Print JSON; also write it to a new file when requested (never overwrite)."""
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if out:
        with Path(out).open("x", encoding="utf-8") as handle:
            handle.write(text)
    write_stdout(text)


# Malformed archives and inputs raise these besides ValueError/OSError; all of them are
# "blocked" outcomes, never tracebacks.
INPUT_ERRORS = (ToolError, OSError, ValueError, KeyError, TypeError, AttributeError, IndexError,
                BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError, csv.Error, RecursionError)


def run_cli(function):
    """Uniform exit contract shared with the packet helper: 0 result, 2 blocked."""
    try:
        function()
        return 0
    except INPUT_ERRORS as exc:
        if isinstance(exc, ToolError):
            message = str(exc)
        elif isinstance(exc, OSError):
            message = f"{type(exc).__name__}: {exc.strerror or 'file error'}"
            if exc.filename:
                message += f" ({Path(str(exc.filename)).name})"
        else:
            message = type(exc).__name__ + ": input could not be processed"
        text = json.dumps({"status": "blocked", "error": message}, ensure_ascii=False) + "\n"
        stream = getattr(sys.stderr, "buffer", None)
        if stream is not None:
            sys.stderr.flush()
            stream.write(text.encode("utf-8"))
            stream.flush()
        else:
            sys.stderr.write(text)
        return 2


# ---------------------------------------------------------------- HTML text
BLOCK_TAGS = {"p", "div", "li", "section", "article", "header", "footer", "main", "aside", "nav",
              "h1", "h2", "h3", "h4", "h5", "h6", "label", "tr", "ul", "ol", "dl", "dt", "dd",
              "table", "blockquote", "pre", "form", "fieldset", "legend", "figcaption", "td", "th"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
             "source", "track", "wbr"}
IMPLICIT_CLOSE = {"p", "li", "option", "tr", "td", "th", "dt", "dd"}
HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?:\.0+)?(?:px|pt|em|rem|%)?\s*(?:;|$|!)"
    r"|opacity\s*:\s*0(?:\.0+)?\s*(?:;|$|!)|(?:left|top|text-indent)\s*:\s*-\d{3,}"
    r"|(?<![-\w])color\s*:\s*(?:#fff(?:fff)?\b|white\b|rgba?\(\s*255\s*,\s*255\s*,\s*255)"
    r"|clip\s*:\s*rect\(\s*0|height\s*:\s*0(?:px)?\s*;[^\"]*overflow\s*:\s*hidden", re.I)
SR_ONLY = re.compile(r"\b(?:sr-only|visually-hidden|screen-reader-text|screenreader)\b", re.I)


class HTMLText(HTMLParser):
    """Visible text, hidden text and JSON-LD blocks from static HTML. Executes nothing."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.visible, self.hidden, self.jsonld = [], [], []
        self.stack = []          # (tag, hidden_reason or None)
        self.script = None       # None, "jsonld" or "other"
        self.script_buffer = []

    def hidden_reason(self):
        for _, reason in reversed(self.stack):
            if reason:
                return reason
        return None

    def handle_starttag(self, tag, attrs):
        attrs = {k.casefold(): (v or "") for k, v in attrs}
        if tag in {"script", "style", "template", "noscript"}:
            kind = attrs.get("type", "").casefold()
            # JSON-LD is parsed as data; noscript/template text is invisible in a normal
            # browser view but still reaches text extractors, so it is reported as hidden.
            self.script = ("jsonld" if tag == "script" and "ld+json" in kind else
                           "hidden" if tag in {"noscript", "template"} else "other")
            self.script_buffer = []
            return
        if tag == "br" and not self.hidden_reason():
            self.visible.append("\n")
        if tag in VOID_TAGS:
            return
        if tag in IMPLICIT_CLOSE and self.stack and self.stack[-1][0] == tag:
            self.handle_endtag(tag)
        if tag == "li" and not self.hidden_reason():
            self.visible.append("\n• ")  # keep list structure visible to section parsing
        reason = None
        if "hidden" in attrs:
            reason = "hidden attribute"
        elif attrs.get("aria-hidden", "").casefold() == "true":
            reason = "aria-hidden"
        elif HIDDEN_STYLE.search(attrs.get("style", "")):
            reason = "inline style hides text"
        elif SR_ONLY.search(attrs.get("class", "")):
            reason = "screen-reader-only class"
        self.stack.append((tag, reason))

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template", "noscript"}:
            if self.script == "jsonld":
                self.jsonld.append("".join(self.script_buffer))
            elif self.script == "hidden" and "".join(self.script_buffer).strip():
                self.hidden.append(("noscript/template content", " ".join(self.script_buffer)))
            self.script, self.script_buffer = None, []
            return
        if any(t == tag for t, _ in self.stack):
            while self.stack:
                closed, _ = self.stack.pop()
                if closed == tag:
                    break
        if tag in BLOCK_TAGS and not self.hidden_reason():
            self.visible.append("\n")

    def handle_comment(self, data):
        if data.strip() and not self.script:
            self.hidden.append(("HTML comment", data))

    def handle_data(self, data):
        if self.script:
            if self.script in {"jsonld", "hidden"}:
                self.script_buffer.append(data)
            return
        reason = self.hidden_reason()
        if reason:
            if data.strip():
                self.hidden.append((reason, data))
        else:
            self.visible.append(data)

    def result(self):
        text = "".join(self.visible)
        text = re.sub(r"[ \t\r\f\v]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        hidden = []
        for item in self.hidden:
            if isinstance(item, tuple):
                hidden.append({"reason": item[0], "text": " ".join(item[1].split())})
        return text, hidden, self.jsonld


def html_to_text(source):
    parser = HTMLText()
    parser.feed(source)
    parser.close()
    return parser.result()


# ---------------------------------------------------------------- DOCX text
def docx_parts(data):
    """Open a DOCX safely: bounded part sizes, no external entities (expat never fetches)."""
    try:
        archive = ZipFile(BytesIO(data))
    except BadZipFile as exc:
        raise ToolError("file is not a readable DOCX/ZIP package") from exc
    infos = archive.infolist()
    names = {info.filename for info in infos}
    require("word/document.xml" in names, "DOCX has no word/document.xml")
    require(len(infos) <= MAX_PACKAGE_PARTS, "DOCX has too many parts to inspect safely")
    require(all(info.file_size <= MAX_XML_PART for info in infos), "DOCX part is too large to inspect safely")
    require(sum(info.file_size for info in infos) <= MAX_PACKAGE_TOTAL, "DOCX expands too far to inspect safely")
    return archive, names


def xml_root(archive, name):
    try:
        return ElementTree.fromstring(archive.read(name))
    except (ElementTree.ParseError, RecursionError) as exc:
        raise ToolError(f"DOCX part is not well-formed XML: {name}") from exc
    except (BadZipFile, zlib.error, EOFError, NotImplementedError, RuntimeError) as exc:
        # Corrupt deflate data, bad CRC, encryption or an unsupported compression method.
        raise ToolError(f"DOCX part could not be read (corrupt, encrypted or unsupported): {name}") from exc


def docx_paragraphs(root):
    """Paragraph texts in document order; deleted (tracked) text is excluded."""
    out = []

    def walk(node, buffer):
        if node.tag == W + "p":
            own = []
            for child in node:
                walk(child, own)
            out.append("".join(own))
            return
        if buffer is not None:
            if node.tag == W + "t" and node.text:
                buffer.append(node.text)
            elif node.tag == W + "tab":
                buffer.append("\t")
            elif node.tag in (W + "br", W + "cr"):
                buffer.append("\n")
        for child in node:
            walk(child, buffer)

    try:
        walk(root, None)
    except RecursionError as exc:
        raise ToolError("DOCX nesting is too deep to inspect safely") from exc
    return out


def docx_text(data):
    archive, _ = docx_parts(data)
    with archive:
        return "\n".join(docx_paragraphs(xml_root(archive, "word/document.xml")))


# ---------------------------------------------------------------- any document
def document_text(path):
    """Plain text from .txt/.md/.html/.htm/.docx/.json evidence files."""
    p = Path(path)
    data = read_input(p)
    suffix = p.suffix.casefold()
    if suffix == ".docx":
        return docx_text(data)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ToolError(f"text input must be UTF-8: {p.name}") from exc
    if suffix in {".html", ".htm"}:
        return html_to_text(text)[0]
    if suffix == ".json":
        try:
            value = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise ToolError(f"invalid JSON evidence: {p.name}") from exc
        return "\n".join(flatten_strings(value))
    require(suffix in {".txt", ".md", ".markdown", ".text", ""}, f"unsupported evidence format: {p.name}")
    return text


def flatten_strings(value, limit=100000):
    found = []

    def walk(item):
        if len(found) >= limit:
            return
        if isinstance(item, str):
            if item.strip():
                found.append(item)
        elif isinstance(item, dict):
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
    walk(value)
    return found


# ---------------------------------------------------------------- text units
BULLET = re.compile(r"^\s*(?:[-*+•‣▪●◦⁃∙·–—>]|\d{1,2}[.)]|[a-z][.)])\s+")
SENTENCE_BREAK = re.compile(r"(?<=[.!?])[\"')\]]?\s+(?=[\"'(\[]?[A-Z0-9])")
STOPWORDS = frozenset("""a about above after again against all also am an and any are as at be because been
before being below between both but by can could did do does doing down during each either few for from
further had has have having he her here hers him his how i if in into is it its itself just me more most
my no nor not now of off on once only or other our ours out over own same she should so some such than
that the their theirs them then there these they this those through to too under until up very was we
were what when where which while who whom why will with would you your yours within across per via etc
including include includes using use used well new strong excellent good great able ability work working
skills skill knowledge experience experienced years year related relevant demonstrated proven must
preferred required requirements plus ideal ideally candidate role team position job""".split())


def strip_bullet(line):
    return BULLET.sub("", line, count=1)


def units(text, source="text"):
    """Sentence-level units with 1-based line numbers; bullets are units of their own."""
    result = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = strip_bullet(raw).strip()
        if not line:
            continue
        for piece in SENTENCE_BREAK.split(line):
            piece = piece.strip()
            if piece:
                result.append({"source": source, "line": number, "text": piece})
    return result


def stem(token):
    for suffix in ("ations", "ation", "ings", "ing", "ments", "ment", "ies", "ied", "ers", "er", "ed", "es", "ly", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            return token[: -len(suffix)] + ("y" if suffix in {"ies", "ied"} else "")
    return token


def content_tokens(text):
    """Stemmed content words. Short tokens survive when they look technical: acronyms
    (AI, QA, UX, R) and symbol names (C#, C++), never the articles 'A' and 'I'."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.-]*[A-Za-z0-9+#]|[A-Za-z]", text)
    keep = set()
    for word in words:
        lowered = word.casefold()
        if lowered in STOPWORDS:
            continue
        if len(word) >= 3:
            keep.add(stem(lowered))
        elif ("+" in word or "#" in word) or (word.isupper() and word not in {"A", "I"}):
            keep.add(lowered)
    return keep


# ---------------------------------------------------------------- identity and similarity
SENIORITY_NOISE = {"i", "ii", "iii", "iv", "1", "2", "3", "the", "and", "of", "for", "-", "&"}


def employer_key(value):
    """Casefolded, whitespace-collapsed employer name; no fuzzy brand matching."""
    return " ".join(str(value or "").split()).casefold()


def title_tokens(value):
    return {t for t in re.findall(r"[a-z0-9+#]+", str(value or "").casefold()) if t not in SENIORITY_NOISE}


def jaccard(left, right):
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def title_similarity(left, right):
    """Jaccard, or containment when two or more words are shared: 'Program Coordinator' and
    'Program Coordinator (Fixed term)' are the same role re-advertised with a qualifier."""
    a, b = title_tokens(left), title_tokens(right)
    shared = len(a & b)
    if not shared:
        return 0.0
    containment = shared / min(len(a), len(b)) if shared >= 2 else 0.0
    return round(max(jaccard(a, b), containment), 2)


def shingles(text, size=5):
    """Word shingles for near-duplicate text (reposted descriptions); works without a corpus."""
    words = re.findall(r"[a-z0-9]+", str(text or "").casefold())
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}


def normalized_link(value):
    """Scheme/host casefolded, fragment kept, trailing slash dropped, for identity comparison only."""
    text = str(value or "").strip()
    match = re.match(r"^(https?)://([^/?#]+)(.*)$", text, re.I)
    if not match:
        return None
    rest = match.group(3)
    path, sep, tail = rest.partition("?")
    return f"{match.group(1).casefold()}://{match.group(2).casefold()}{path.rstrip('/')}{sep}{tail}"


def excerpt(text, limit=240):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
