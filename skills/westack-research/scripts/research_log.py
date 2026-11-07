"""westack-research log checker: the search log and claim ledger behind one research answer, read as files.

  python research_log.py check LOG [--record TASK] [--core DIR]

LOG is a research log (format westack-research-log-1, references/log.md). The result sets, saved originals and
index records it names are read relative to its own folder. The claim-strength words come from the core's evidence
vocabulary (references/evidence-vocabulary.md, the Claim strength table), found beside this skill or at --core.
TASK is the westack task record that cites the log: the log is an artefact behind a receipt and an observation in
that record, never a second record, and the record is read through the core's record.py and contract.

  shape        the fields, values and unique ids; a complete log with no claims is not clean
  rounds       OR-1: follow-up rounds within the declared cap (0, 1 or 2), each naming the one gap it targets;
               no query repeated after normalisation (case, punctuation, word order)
  window       OR-2: every call of one search keeps its window and ranking; a logged query ran at least once
  results      OR-3: each accepted or cited source came back in a saved result set (matched by index id, then DOI
               or arXiv id, then URL, then exact title), or was given by the user or linked from a logged source;
               two sources that are one work are duplicates
  reading      OR-4: a claim whose cites are only snippets, listings or summaries, only mirror or aggregator copies,
               or one secondary source stays claimed; tested and observed need a run with its receipt
  strength     SS-66: each claim's strength is a word of the core vocabulary; a contested claim names its check
  identifiers  FY-1: each cited DOI or arXiv id has records from two indexes whose title, year and first author
               match the source, and names the record it matched
  queries      FY-4: the query floor for the question's depth (one for straightforward, none when every source was
               given or linked; three for depth-first and breadth-first); every searched-for claim and every
               delegate's nothing-found entry maps to a logged query
  pacing       AX-2: requests to a host with a published interval start at least that far apart; every failure
               records its URL and attempt number; DS-6: a GitHub 404 is "not found or not visible to this account",
               never "does not exist" (a fetch, a call or a rejected source with `http` 404 and that wording)
  delegates    WA-83, research half: each delegate return keeps found, nothing found and not searched; a found
               entry names a logged source; a not-searched lead becomes a later round's gap or a not-done entry
  gaps         RS-1: each gap's origin is stated (with a source and location), inferred (from two sources or more)
               or speculative
  trace        FY-2: every citation names a logged source and carries its excerpt, the excerpt is in the saved
               original, every number in a claim is in its excerpts or its sources' version, dates or ids, and
               every accepted source is cited
  sources      FY-3: a rejected source says why; an accepted one is pinned (retrieval date, and a version or
               publication date) and saved, its hash unchanged; a mirror records the original and retrieval URLs;
               a partial or blocked log says why and what was not done
  licence      DG-37: a licence given as verified has its licence file saved and the host's licence field naming the
               same licence; one named only in a README or package metadata is unverified (take ideas only)
  artifacts    SI-1: a source that bundles, wraps, ports or cites another tool lists it under includes as the id of
               its own row, never itself; that row and the source, when accepted, each carry their own pin and licence
  spend        treg row 8: the running total stays within the limit; bulk spend waits for a pilot
  record       with --record: the record's shape (core contract), a receipt holding this log's SHA-256, and an
               observation citing that receipt

What it cannot check is listed in every report (NOT_CHECKED). Exit 0 clean, 1 findings, 2 unreadable, not this
format, or a check not run (no core vocabulary, or --record without the core), 64 usage. Standard library only;
it reads the files named and prints JSON; it runs no command, writes no file and opens no network connection.
"""
import argparse
import datetime as dt
import hashlib
import html
import importlib.util
import json
import pathlib
import re
import sys
import unicodedata

FORMAT = "westack-research-check-1"
LOG_FORMAT = "westack-research-log-1"
CHECKS = ("shape", "rounds", "window", "results", "reading", "strength", "identifiers", "queries", "pacing",
          "delegates", "gaps", "trace", "sources", "licence", "artifacts", "spend", "record")
FLOORS = {"straightforward": 1, "depth-first": 3, "breadth-first": 3}  # distinct queries per depth class (FY-4)
STATUSES = ("complete", "partial", "blocked")
SOURCE_STATUSES = ("accepted", "rejected")
KINDS = ("primary", "secondary", "mirror", "aggregator")
COPY_KINDS = ("mirror", "aggregator")
BASES = ("read", "ran", "snippet", "listing", "summary")
READ_BASES = ("read", "ran")
ORIGINS = ("stated", "inferred", "speculative")
LICENCE_STATUSES = ("verified", "unverified")
INDEX_FIELDS = ("title", "year", "first_author")
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*%?")
NOTE = "Checks structure, hashes and wording against saved files, not truth: a clean log can still answer badly."
NOT_CHECKED = (
    "a paraphrased query: only repeats after normalising case, punctuation and word order are caught",
    "whether a source is really primary, a mirror or an aggregator: the log's own label is read",
    "whether a paper's linked repository is its code or a framework it builds on",
    "relevance: whether a result, excerpt or claim actually answers the question or the decision",
    "whether a gap labelled stated is really stated at the cited location",
    "whether a row's strength fits its subject: read documentation supports what the docs say, not how the software behaves",
    "whether the report's prose says only what the ledger supports, beyond the numbers checked in each claim",
    "whether a saved licence file is the repository's own at its pin and grants what its name says: only that it is "
    "saved, and the host field's name, are compared",
    "whether a source bundles, wraps, ports or cites a tool its includes do not list, or a claim credits one "
    "artifact's parts to another: only the parts a row lists are checked",
    "whether a GitHub 404 hid a private resource or a missing one: only a 404 on a GitHub host read as 'does not exist' "
    "is caught, and a 404 is not found or not visible to this account either way",
)


# ---- small helpers --------------------------------------------------------------------------------------------------
def text(value):
    return isinstance(value, str) and bool(value.strip())


def is_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def iso_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def when(value):
    """A timezone-aware datetime from an ISO timestamp, or None."""
    if not isinstance(value, str):
        return None
    try:
        stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else None


def digest(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            hasher.update(block)
    return hasher.hexdigest()


def inside(root, relative):
    """root/relative for a portable relative path (no drive, no leading slash, no ..), else None."""
    if not text(relative):
        return None
    path = relative.strip().replace("\\", "/")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        return None
    parts = [p for p in path.split("/") if p not in ("", ".")]
    if not parts or ".." in parts:
        return None
    return root.joinpath(*parts)


def normal_text(value):
    """Lower case, one space between words, compatibility forms folded: the form two wordings are compared in."""
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def query_key(query):
    """A query with case, punctuation and word order taken out (OR-1); paraphrase is out of reach."""
    words = re.findall(r"\w+", unicodedata.normalize("NFKC", str(query or "")).casefold())
    return " ".join(sorted(words))


def surname(value):
    if isinstance(value, dict):
        value = value.get("family") or value.get("name") or ""
    value = str(value or "").strip()
    if "," in value:
        return value.split(",", 1)[0].strip()
    return value.split()[-1] if value.split() else ""


def normal(value, field):
    """A field of an index record or a source in comparable form."""
    if field == "year":
        try:
            return int(str(value).strip()[:4])
        except ValueError:
            return None
    if field == "first_author":
        return normal_text(surname(value))
    return normal_text(value).rstrip(".")


def plain(raw):
    """The words of a saved original: tags dropped and entities decoded for HTML, then normalised; None if binary."""
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "\x00" in decoded:
        return None
    if re.search(r"<(?:html|body|p|div|h\d|span|b|a)\b", decoded, re.I):
        decoded = html.unescape(re.sub(r"<[^>]+>", " ", decoded))
    return normal_text(decoded)


def numbers(value, variants=True):
    """The number tokens of a text; with variants, '16%' also counts as '16' (a source's 16% supports a claim's 16)."""
    found = set()
    for token in NUMBER.findall(str(value or "")):
        token = token.rstrip(".,")
        found.add(token)
        if variants and token.endswith("%"):
            found.add(token[:-1])
    return found


def arxiv_id(value):
    match = re.search(r"(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})", str(value or ""), re.I)
    return match.group(1).lower() if match else None


def doi(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", value)
    return value or None


def url_key(value):
    value = str(value or "").strip()
    if not value:
        return None
    value = value.split("#", 1)[0]
    match = re.match(r"^(https?)://([^/]+)(.*)$", value, re.I)
    if not match:
        return value.rstrip("/")
    return match.group(1).lower() + "://" + match.group(2).lower() + match.group(3).rstrip("/")


def same_work(one, other):
    """OR-3 matching order: index id, then DOI or arXiv id, then URL, then exact title (case and spacing folded)."""
    if text(one.get("index_id")) and one.get("index_id") == other.get("id"):
        return True
    if text(other.get("index_id")) and other.get("index_id") == one.get("id"):
        return True
    if one.get("doi") and doi(one.get("doi")) == doi(other.get("doi")):
        return True
    if one.get("arxiv") and arxiv_id(one.get("arxiv")) == arxiv_id(other.get("arxiv")):
        return True
    urls = {url_key(one.get(key)) for key in ("url", "original_url")} - {None}
    if urls & ({url_key(other.get(key)) for key in ("url", "original_url")} - {None}):
        return True
    return text(one.get("title")) and normal_text(one.get("title")) == normal_text(other.get("title"))


def host(url):
    match = re.match(r"^https?://([^/:?#]+)", str(url or ""), re.I)
    return match.group(1).lower() if match else None


def licence_key(value):
    """A licence name in comparable form: case, punctuation and the word licence set aside ('MIT License' is 'MIT')."""
    words = re.sub(r"\blicen[cs]e\b", " ", unicodedata.normalize("NFKC", str(value or "")).casefold())
    return re.sub(r"[^0-9a-z]+", "", words)


def read_json(path):
    with open(path, "rb") as handle:
        return json.loads(handle.read().decode("utf-8-sig"))


# ---- the core -------------------------------------------------------------------------------------------------------
def core_root(core=None):
    return pathlib.Path(core) if core else pathlib.Path(__file__).resolve().parents[2] / "westack"


def strength_levels(core=None):
    """The claim-strength words, weakest first, read from the core vocabulary's Claim strength table; None if absent."""
    path = core_root(core) / "references" / "evidence-vocabulary.md"
    try:
        body = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if "## Claim strength" not in body:
        return None
    section = body.split("## Claim strength", 1)[1].split("\n## ", 1)[0]
    levels = []
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not line.strip().startswith("|") or len(cells) < 2:
            continue
        word = cells[0]
        if word.lower() == "level" or set(word) <= set("-: "):
            continue
        if re.fullmatch(r"[a-z][a-z-]*", word):
            levels.append(word)
    return tuple(levels) or None


def load_record_module(core=None):
    """The core's record.py, or None when it is not found or cannot load."""
    path = core_root(core) / "scripts" / "record.py"
    if not path.is_file():
        return None
    key = "westack_research_record_" + hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    module = sys.modules.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            spec.loader.exec_module(module)
        except Exception:  # an unloadable core is reported as absent
            del sys.modules[key]
            return None
    return module


# ---- the checks -----------------------------------------------------------------------------------------------------
class Run:
    """One check pass over a parsed log: findings, notes and the status of each check."""

    def __init__(self, data, root):
        self.data, self.root = data, root
        self.findings, self.notes = [], []
        self.status = {name: "not-applicable" for name in CHECKS}
        self.searches = [s for s in data.get("searches", []) if isinstance(s, dict)]
        self.sources = [s for s in data.get("sources", []) if isinstance(s, dict)]
        self.claims = [c for c in data.get("claims", []) if isinstance(c, dict)]
        self.by_source = {s.get("id"): s for s in self.sources if text(s.get("id"))}
        self.search_ids = {s.get("id") for s in self.searches if text(s.get("id"))}
        self.cited = {cite.get("source") for claim in self.claims for cite in self.cites(claim)}
        self.saved = {}  # source id -> normalised text of its saved original (or text copy), None when binary

    @staticmethod
    def cites(claim):
        return [c for c in claim.get("cites", []) if isinstance(c, dict)] if isinstance(claim.get("cites"), list) else []

    def add(self, check, code, item, detail):
        self.findings.append({"check": check, "code": code, "item": item, "detail": detail})
        self.status[check] = "failed"

    def ran(self, check):
        if self.status[check] != "failed":
            self.status[check] = "passed"

    def relevant(self):
        """Accepted sources and any source a claim cites."""
        return [s for s in self.sources if s.get("status") == "accepted" or s.get("id") in self.cited]


def check_shape(run):
    data = run.data
    for key in ("question", "decision"):
        if not text(data.get(key)):
            run.add("shape", "field-missing", key, "the log states the " + key + " the research serves")
    for key, allowed in (("depth", tuple(FLOORS)), ("status", STATUSES)):
        if key not in data:
            run.add("shape", "field-missing", key, key + " is required")
        elif data[key] not in allowed:
            run.add("shape", "bad-value", key, "%s is one of %s" % (key, ", ".join(allowed)))
    cap = data.get("follow_up_cap")
    if "follow_up_cap" not in data:
        run.add("shape", "field-missing", "follow_up_cap", "the follow-up cap (0, 1 or 2) is set before searching")
    elif not (isinstance(cap, int) and not isinstance(cap, bool) and 0 <= cap <= 2):
        run.add("shape", "bad-value", "follow_up_cap", "the follow-up cap is 0, 1 or 2 (OR-1)")
    for key in ("searches", "sources", "claims", "not_done"):
        if not isinstance(data.get(key), list):
            run.add("shape", "field-missing", key, key + " is a list (empty is allowed)")
    seen = {}
    for key in ("searches", "sources", "claims", "gaps", "delegates"):
        for item in data.get(key, []) if isinstance(data.get(key), list) else []:
            ident = item.get("id") if isinstance(item, dict) else None
            if not text(ident):
                run.add("shape", "field-missing", key, "every entry of " + key + " has an id")
            elif ident in seen:
                run.add("shape", "duplicate-id", ident, "%s is used in %s and %s" % (ident, seen[ident], key))
            else:
                seen[ident] = key
    for source in run.sources:
        if source.get("status") not in SOURCE_STATUSES:
            run.add("shape", "bad-value", source.get("id"), "a source is accepted or rejected")
        if source.get("status") == "accepted" and source.get("kind") not in KINDS:
            run.add("shape", "bad-value", source.get("id"), "kind is one of " + ", ".join(KINDS))
    for claim in run.claims:
        cites = run.cites(claim)
        if not cites:
            run.add("shape", "field-missing", claim.get("id"), "a claim cites at least one source")
        for cite in cites:
            if cite.get("basis") not in BASES:
                run.add("shape", "bad-value", claim.get("id"), "a citation's basis is one of " + ", ".join(BASES))
    if not data.get("claims") and data.get("status") == "complete":
        run.add("shape", "empty-log", None, "a complete log with no claims answers nothing; nothing to check is not clean")
    elif not data.get("claims"):
        run.notes.append("the log records a %s run with no claims" % data.get("status"))
    run.ran("shape")


def check_rounds(run):
    cap = run.data.get("follow_up_cap")
    cap = cap if isinstance(cap, int) and not isinstance(cap, bool) and 0 <= cap <= 2 else 2
    by_round, seen_queries = {}, {}
    for search in run.searches:
        number = search.get("round")
        if not (isinstance(number, int) and not isinstance(number, bool) and number >= 0):
            run.add("rounds", "bad-value", search.get("id"), "round is 0 for the first pass, then 1 or 2")
            continue
        if number > cap:
            run.add("rounds", "round-over-cap", search.get("id"),
                    "round %d is past the follow-up cap of %d set before searching (OR-1)" % (number, cap))
        if number >= 1 and not text(search.get("gap")):
            run.add("rounds", "round-no-gap", search.get("id"), "a follow-up round names the one gap it targets")
        if number >= 1 and text(search.get("gap")):
            by_round.setdefault(number, set()).add(normal_text(search.get("gap")))
        key = query_key(search.get("query"))
        if not key:
            run.add("rounds", "field-missing", search.get("id"), "the query is logged verbatim")
            continue
        if key in seen_queries:
            run.add("rounds", "repeated-query", search.get("id"),
                    "the same query as %s once case, punctuation and word order are set aside" % seen_queries[key])
        seen_queries.setdefault(key, search.get("id"))
    for number, targets in sorted(by_round.items()):
        if len(targets) > 1:
            run.add("rounds", "round-many-gaps", "round %d" % number,
                    "a round targets one named gap; this one names %d" % len(targets))
    if run.searches:
        run.ran("rounds")


def check_window(run):
    for search in run.searches:
        for key in ("window", "ranking"):
            if not text(search.get(key)):
                run.add("window", "field-missing", search.get("id"), "a search states its " + key)
        calls = search.get("calls")
        if not isinstance(calls, list) or not calls:
            run.add("window", "no-calls", search.get("id"), "a logged query with no call never ran")
            continue
        for number, call in enumerate(calls, start=1):
            if not isinstance(call, dict):
                continue
            if call.get("window") != search.get("window") or call.get("ranking") != search.get("ranking"):
                run.add("window", "window-changed", search.get("id"),
                        "call %d uses window %r and ranking %r, not the search's %r and %r (OR-2)" % (
                            number, call.get("window"), call.get("ranking"), search.get("window"),
                            search.get("ranking")))
    if run.searches:
        run.ran("window")


def result_set(run, search):
    """The saved results of one search, or None when they are not saved or not readable."""
    results = search.get("results")
    if isinstance(results, list):
        return [r for r in results if isinstance(r, dict)]
    path = inside(run.root, results) if text(results) else None
    if path is None or not path.is_file():
        return None
    try:
        loaded = read_json(path)
    except (OSError, ValueError):
        return None
    if isinstance(loaded, dict):
        loaded = loaded.get("results")
    return [r for r in loaded if isinstance(r, dict)] if isinstance(loaded, list) else None


def check_results(run):
    sets = {}
    for search in run.searches:
        found = result_set(run, search)
        if found is None:
            run.add("results", "results-unsaved", search.get("id"),
                    "the search's results are not saved as a readable JSON list (%s)" % search.get("results"))
        else:
            sets[search.get("id")] = found
    relevant = run.relevant()
    for source in relevant:
        sid, origin = source.get("id"), source.get("found_by")
        if isinstance(origin, dict) and text(origin.get("search")):
            found = sets.get(origin["search"])
            if found is None:
                run.add("results", "recalled", sid, "found by %s, which has no saved results" % origin["search"])
            elif not any(same_work(source, result) for result in found):
                run.add("results", "recalled", sid, "not in the saved results of %s: cite only what came back "
                        "(OR-3)" % origin["search"])
        elif isinstance(origin, dict) and text(origin.get("link")):
            if origin["link"] not in run.by_source or origin["link"] == sid:
                run.add("results", "recalled", sid, "linked from %s, which is not another logged source" % origin["link"])
        elif not (isinstance(origin, dict) and text(origin.get("given"))):
            run.add("results", "recalled", sid, "no found_by: a source that did not come back in this search, "
                    "was not given and was not linked is a recalled one")
    for index, source in enumerate(relevant):
        for other in relevant[index + 1:]:
            if same_work(source, other):
                run.add("results", "duplicate-source", other.get("id"),
                        "the same work as %s (id, DOI or arXiv id, URL or exact title): keep one entry" % source.get("id"))
    if run.searches or relevant:
        run.ran("results")


def check_reading(run, levels):
    if levels is None:
        run.status["reading"] = "not-run"
        return
    rank = {word: number for number, word in enumerate(levels)}
    floor = rank.get("claimed", 0)
    tested = rank.get("tested", len(levels))
    for claim in run.claims:
        level = rank.get(claim.get("strength"))
        if level is None or level <= floor:
            continue
        cites = run.cites(claim)
        read_cites = [c for c in cites if c.get("basis") in READ_BASES]
        if not read_cites:
            run.add("reading", "snippet-only", claim.get("id"),
                    "only snippets, listings or summaries back it, so it stays claimed until a source is read (OR-4)")
            continue
        firm_cites = [c for c in read_cites if run.by_source.get(c.get("source"), {}).get("kind") not in COPY_KINDS]
        if not firm_cites:
            run.add("reading", "copy-only", claim.get("id"),
                    "only a mirror or aggregator backs it: corroborate it against the original before it rises above claimed")
            continue
        primary_cites = [c for c in firm_cites if run.by_source.get(c.get("source"), {}).get("kind") == "primary"]
        firm_sources = {c.get("source") for c in firm_cites}
        if not primary_cites and len(firm_sources) < 2:
            run.add("reading", "single-secondary", claim.get("id"),
                    "one secondary source alone is claimed; read the primary or a second independent source")
        needs_run = level >= tested
        ran_receipt = any(c.get("basis") == "ran" and text(c.get("receipt")) for c in cites)
        if needs_run and not ran_receipt:
            run.add("reading", "no-run-receipt", claim.get("id"),
                    "%s needs a run you made, cited with basis ran and its receipt" % claim.get("strength"))
    if run.claims:
        run.ran("reading")


def check_strength(run, levels):
    if levels is None:
        run.status["strength"] = "not-run"
        run.notes.append("strength and reading not run: the core's evidence vocabulary was not found")
        return
    for claim in run.claims:
        if claim.get("strength") not in levels:
            run.add("strength", "unknown-strength", claim.get("id"),
                    "%r is not a claim-strength word of the core vocabulary (%s); no second scale (SS-66)" % (
                        claim.get("strength"), ", ".join(levels)))
        if claim.get("contested") is True and not text(claim.get("check")):
            run.add("strength", "contested-unchecked", claim.get("id"), "a contested claim names the check run on it")
    if run.claims:
        run.ran("strength")


def index_record(run, spec):
    """(index name, fields) for one index record given inline or as a saved file; fields is None if unreadable."""
    name = spec.get("index") if isinstance(spec, dict) else None
    if not isinstance(spec, dict):
        return name, None
    fields = spec
    if text(spec.get("file")):
        path = inside(run.root, spec["file"])
        try:
            fields = read_json(path) if path is not None else None
        except (OSError, ValueError):
            fields = None
        if not isinstance(fields, dict):
            return name, None
    found = {"title": fields.get("title"), "year": fields.get("year")}
    author = fields.get("first_author")
    if author is None and isinstance(fields.get("authors"), list) and fields["authors"]:
        author = fields["authors"][0]
    found["first_author"] = author
    return name, found


def check_identifiers(run):
    checked = False
    for source in run.relevant():
        if not (source.get("doi") or source.get("arxiv")):
            continue
        checked = True
        sid = source.get("id")
        check_spec = source.get("index_check")
        if not isinstance(check_spec, dict):
            run.add("identifiers", "identifier-unchecked", sid,
                    "a cited DOI or arXiv id is checked in two independent indexes (FY-1)")
            check_spec = {}
        listed = (check_spec or {}).get("records")
        records = listed if isinstance(listed, list) else []
        indexes = set()
        for spec in records:
            name, found = index_record(run, spec)
            if not text(name):
                run.add("identifiers", "index-incomplete", sid, "an index record names its index")
                continue
            indexes.add(name)
            if found is None:
                run.add("identifiers", "index-incomplete", sid, "the %s record cannot be read" % name)
                continue
            missing_fields = [field for field in INDEX_FIELDS if found.get(field) in (None, "", [])]
            if missing_fields:
                run.add("identifiers", "index-incomplete", sid, "the %s record lacks %s: showing that an id resolves "
                        "is not a match" % (name, ", ".join(missing_fields)))
            for field in INDEX_FIELDS:
                found_value = found.get(field)
                if found_value in (None, "", []) or source.get(field) in (None, ""):
                    continue
                if normal(found_value, field) != normal(source.get(field), field):
                    run.add("identifiers", "index-mismatch", sid, "the %s record's %s is %r, the source's is %r" % (
                        name, field, found_value, source.get(field)))
        for field in INDEX_FIELDS:
            if source.get(field) in (None, ""):
                run.add("identifiers", "index-incomplete", sid, "the source states no %s to compare" % field)
        if records:
            if len(indexes) < 2:
                run.add("identifiers", "index-not-independent", sid, "records from two different indexes are needed")
            if check_spec.get("matched") not in indexes:
                run.add("identifiers", "index-unmatched", sid, "matched names %r, not one of the records (%s)" % (
                    check_spec.get("matched"), ", ".join(sorted(indexes))))
        elif isinstance(source.get("index_check"), dict):
            run.add("identifiers", "index-not-independent", sid, "the index check lists no records")
    if checked:
        run.ran("identifiers")


def check_queries(run):
    depth = run.data.get("depth")
    if depth not in FLOORS:
        return
    floor = FLOORS[depth]
    distinct = {query_key(s.get("query")) for s in run.searches} - {""}
    accepted = [s for s in run.sources if s.get("status") == "accepted"]
    unsearched = all(isinstance(s.get("found_by"), dict) and (text(s["found_by"].get("given")) or
                     text(s["found_by"].get("link"))) for s in accepted)
    if depth == "straightforward" and not run.searches and accepted and unsearched:
        floor = 0
    if len(distinct) < floor:
        run.add("queries", "query-floor", None, "%s needs %d distinct logged queries, found %d (FY-4)" % (
            depth, floor, len(distinct)))
    search_ids = run.search_ids
    claims = [("searched_for", entry) for entry in run.data.get("searched_for", []) if isinstance(entry, dict)]
    for delegate in run.data.get("delegates", []) if isinstance(run.data.get("delegates"), list) else []:
        if isinstance(delegate, dict) and isinstance(delegate.get("nothing_found"), list):
            claims += [(delegate.get("id"), entry) for entry in delegate["nothing_found"] if isinstance(entry, dict)]
    for owner, entry in claims:
        queries = entry.get("queries") if isinstance(entry.get("queries"), list) else []
        if not queries or any(query not in search_ids for query in queries):
            run.add("queries", "search-claim-unlogged", owner, "%r claims a search with no logged query behind it" % (
                entry.get("text") or entry.get("what")))
    run.ran("queries")


def requests_of(run):
    """(owner, request) for every search call and fetch row of the log."""
    requests = []
    for search in run.searches:
        for call in search.get("calls", []) if isinstance(search.get("calls"), list) else []:
            if isinstance(call, dict):
                requests.append((search.get("id"), call))
    for fetch in run.data.get("fetches", []) if isinstance(run.data.get("fetches"), list) else []:
        if isinstance(fetch, dict):
            requests.append((fetch.get("source") or "fetch", fetch))
    return requests


GITHUB_HOSTS = ("github.com", "api.github.com", "raw.githubusercontent.com", "codeload.github.com", "gist.github.com")
ABSENT = re.compile(r"\b(?:does(?:n['\u2019]t| not) exist|did(?:n['\u2019]t| not) exist|no longer exists?|never existed|"
                    r"non-?existent|no such (?:repo|repository|user|org|organi[sz]ation|file|page|resource|release|tag|"
                    r"branch))\b", re.I)


def check_not_found(run):
    """DS-6: GitHub answers 404, not 403, for a private resource the caller cannot see, so a GitHub 404 is 'not found or
    not visible to this account'. A fetch, a search call or a rejected source on a GitHub host whose 404 is read as the
    thing not existing is a claim of absence its evidence cannot make."""
    rows = list(requests_of(run)) + [(s.get("id"), s) for s in run.sources if s.get("status") == "rejected"]
    for owner, row in rows:
        said = " ".join(str(row.get(key) or "") for key in ("result", "note", "reason"))
        if host(row.get("url")) not in GITHUB_HOSTS:
            continue
        if not (str(row.get("http")) == "404" or re.search(r"\b404\b", said)):
            continue
        if ABSENT.search(said):
            run.add("pacing", "404-read-as-absent", owner, "a GitHub 404 reads 'not found or not visible to this account' "
                    "(GitHub answers 404, not 403, for a private resource): %r is not evidence that it does not exist" % said.strip())


def check_pacing(run):
    requests = requests_of(run)
    check_not_found(run)
    if not requests:
        return
    rules = run.data.get("pacing") if isinstance(run.data.get("pacing"), dict) else {}
    timed = {}
    for owner, request in requests:
        if request.get("status") == "failed":
            if not text(request.get("url")) or not is_count(request.get("attempt")):
                run.add("pacing", "failure-unrecorded", owner, "a failed request records its URL and attempt number (AX-2)")
        stamp = when(request.get("at"))
        if stamp is None:
            run.add("pacing", "bad-time", owner, "%r is not an ISO timestamp with a time zone" % request.get("at"))
            continue
        name = host(request.get("url"))
        if name in rules:
            timed.setdefault(name, []).append((stamp, owner))
    for name, entries in sorted(timed.items()):
        minimum = rules[name]
        if not isinstance(minimum, (int, float)) or isinstance(minimum, bool):
            run.add("pacing", "bad-value", name, "a pacing rule is a number of seconds")
            continue
        entries.sort(key=lambda pair: pair[0])
        for (before, _), (after, owner) in zip(entries, entries[1:]):
            gap = (after - before).total_seconds()
            if gap < minimum:
                run.add("pacing", "too-fast", owner, "%s: %.1f s after the previous request, under the %s s the source "
                        "publishes" % (name, gap, minimum))
    run.ran("pacing")


def check_delegates(run):
    delegates = [d for d in run.data.get("delegates", []) if isinstance(d, dict)] \
        if isinstance(run.data.get("delegates"), list) else []
    if not delegates:
        return
    closed_leads = {normal_text(s.get("gap")) for s in run.searches if text(s.get("gap"))}
    closed_leads |= {normal_text(entry.get("check")) for entry in run.data.get("not_done", [])
                     if isinstance(entry, dict) and text(entry.get("check"))} if isinstance(run.data.get("not_done"), list) else set()
    for delegate in delegates:
        for key in ("found", "nothing_found", "not_searched"):
            if not isinstance(delegate.get(key), list):
                run.add("delegates", "delegate-lists", delegate.get("id"),
                        "a search delegate returns found, nothing found and not searched; %s is missing (WA-83)" % key)
        for sid in delegate.get("found", []) if isinstance(delegate.get("found"), list) else []:
            if sid not in run.by_source:
                run.add("delegates", "found-unknown", delegate.get("id"), "%r is not a logged source" % sid)
        for lead in delegate.get("not_searched", []) if isinstance(delegate.get("not_searched"), list) else []:
            if normal_text(lead) not in closed_leads:
                run.add("delegates", "lead-dropped", delegate.get("id"),
                        "%r was not searched: make it a later round's gap or a not-done entry" % lead)
    run.ran("delegates")


def check_gaps(run):
    gaps = [g for g in run.data.get("gaps", []) if isinstance(g, dict)] if isinstance(run.data.get("gaps"), list) else []
    source_ids = set(run.by_source)
    for gap in gaps:
        origin = gap.get("origin")
        if origin not in ORIGINS:
            run.add("gaps", "bad-origin", gap.get("id"), "a gap's origin is stated, inferred or speculative (RS-1)")
        elif origin == "stated":
            if not (gap.get("source") in source_ids and text(gap.get("location"))):
                run.add("gaps", "stated-unlocated", gap.get("id"), "a stated gap names its source and location")
        elif origin == "inferred":
            inferred_from = set(gap.get("from", []) if isinstance(gap.get("from"), list) else []) & source_ids
            if len(inferred_from) < 2:
                run.add("gaps", "inferred-unsourced", gap.get("id"),
                        "an inferred gap names the two or more sources whose pattern it comes from")
    if gaps:
        run.ran("gaps")


def original_words(run, source):
    """The normalised words of a source's saved original (or its text copy); None for binary, False if unreadable."""
    sid = source.get("id")
    if sid in run.saved:
        return run.saved[sid]
    value = False
    for key in ("text", "saved"):
        path = inside(run.root, source.get(key)) if text(source.get(key)) else None
        if path is None or not path.is_file():
            continue
        try:
            value = plain(path.read_bytes())
        except OSError:
            value = False
        break
    run.saved[sid] = value
    return value


def check_trace(run):
    cited_ids = set()
    for claim in run.claims:
        allowed = set()
        cites = run.cites(claim)
        for cite in cites:
            sid = cite.get("source")
            source = run.by_source.get(sid)
            if source is None:
                run.add("trace", "unknown-source", claim.get("id"), "%r has no source entry" % sid)
                continue
            cited_ids.add(sid)
            excerpt = cite.get("excerpt")
            if not text(excerpt):
                run.add("trace", "no-excerpt", claim.get("id"), "the citation of %s carries no excerpt" % sid)
                continue
            allowed |= numbers(excerpt)
            for key in ("version", "published", "retrieved", "year", "arxiv", "doi"):
                allowed |= numbers(source.get(key))
            if cite.get("basis") not in READ_BASES:
                continue
            saved_text = original_words(run, source)
            if saved_text is None:
                run.add("trace", "excerpt-unverifiable", claim.get("id"),
                        "%s's saved original is binary: save a text copy beside it (text) so excerpts can be checked" % sid)
            elif saved_text is not False:
                if normal_text(excerpt) not in saved_text:
                    run.add("trace", "excerpt-not-in-source", claim.get("id"),
                            "the excerpt cited from %s is not in its saved original" % sid)
        for token in sorted(numbers(claim.get("text"), variants=False)):
            if token not in allowed:
                run.add("trace", "number-untraced", claim.get("id"),
                        "%s is in the claim but in none of its excerpts or sources: trace it to the wording or remove "
                        "it and list it as removed (FY-2)" % token)
    for source in run.sources:
        if source.get("status") == "accepted" and source.get("id") is not None:
            if source["id"] not in cited_ids:
                run.add("trace", "uncited-source", source.get("id"), "an accepted source no claim cites")
    if run.claims or run.sources:
        run.ran("trace")


def check_sources(run):
    data = run.data
    for source in run.sources:
        sid, status, kind = source.get("id"), source.get("status"), source.get("kind")
        if status == "rejected" and not text(source.get("reason")):
            run.add("sources", "rejected-without-reason", sid, "a rejected source says why (FY-3)")
        if status != "accepted":
            continue
        if not iso_date(source.get("retrieved")) or not (text(source.get("version")) or text(source.get("published"))):
            run.add("sources", "unpinned", sid, "an accepted source has a retrieval date and a version or publication date")
        if kind == "mirror" and not (text(source.get("original_url")) and text(source.get("url"))):
            run.add("sources", "mirror-unrecorded", sid, "a mirror records the original URL and the retrieval URL")
        saved_path = inside(run.root, source.get("saved")) if text(source.get("saved")) else None
        if saved_path is None or not saved_path.is_file():
            run.add("sources", "not-saved", sid, "an accepted source is saved unsummarised (%s)" % source.get("saved"))
        elif not text(source.get("sha256")):
            run.add("sources", "not-saved", sid, "the saved original's SHA-256 is recorded")
        elif digest(saved_path) != source.get("sha256"):
            run.add("sources", "saved-changed", sid, "the saved original no longer has the recorded SHA-256")
    not_done = data.get("not_done") if isinstance(data.get("not_done"), list) else []
    for entry in not_done:
        if not (isinstance(entry, dict) and text(entry.get("check")) and text(entry.get("why"))):
            run.add("sources", "bad-value", "not_done", "each not-done entry names the check and why")
    if data.get("status") != "complete" and not (text(data.get("reason")) and data.get("not_done")):
        run.add("sources", "status-unreasoned", data.get("status"),
                "a partial or blocked log says why and lists what was not done")
    if data.get("status") in ("partial", "blocked"):
        run.notes.append("the log is labelled %s: %s" % (data["status"], data.get("reason")))
    run.ran("sources")


def licence_gap(run, licence):
    """(code, why) when a named licence is not verified, or None: verified needs the repository's licence file saved
    beside the log and the host's licence field naming the same licence (DG-37)."""
    path = inside(run.root, licence.get("file")) if text(licence.get("file")) else None
    has_file = path is not None and path.is_file()
    if not has_file:
        return "licence-unverified", ("no licence file is saved (file %r): a licence named only in a README or package "
                                      "metadata is unverified, and with no licence file take ideas only"
                                      % licence.get("file"))
    if licence_key(licence.get("host")) != licence_key(licence.get("name")):
        return "licence-mismatch", ("the host's licence field is %r, not %r: report both and settle it from the "
                                    "licence file" % (licence.get("host"), licence.get("name")))
    return None


def check_licence(run):
    """DG-37, only for sources whose licence the log names; a log without licence entries is unchanged."""
    named = [s for s in run.sources if s.get("licence") is not None]
    for source in named:
        sid, licence = source.get("id"), source["licence"]
        if not (isinstance(licence, dict) and licence_key(licence.get("name")) and licence.get("status") in LICENCE_STATUSES):
            run.add("licence", "bad-value", sid, "a licence entry gives the licence's name and its status, verified or "
                    "unverified, beside the saved licence file and the host's licence field (null when there is none)")
            continue
        gap = licence_gap(run, licence)
        if gap and licence.get("status") == "verified":
            run.add("licence", gap[0], sid, "%s is given as verified, but %s" % (licence.get("name"), gap[1]))
        elif gap:
            run.notes.append("%s: licence %s stays unverified: %s" % (sid, licence.get("name"), gap[1]))
    if named:
        run.ran("licence")


def pinned(item):
    """An accepted source's pin (FY-3): a retrieval date and a version or publication date."""
    return iso_date(item.get("retrieved")) and (text(item.get("version")) or text(item.get("published")))


def check_artifacts(run):
    """SI-1, only for sources that list includes; a log without them is unchanged. Each artifact a source bundles,
    wraps, ports or cites is its own row, and each accepted one carries its own pin and licence entry."""
    listing = [s for s in run.sources if "includes" in s]
    for source in listing:
        sid, parts = source.get("id"), source.get("includes")
        if not (isinstance(parts, list) and all(text(part) for part in parts)):
            run.add("artifacts", "bad-value", sid, "includes lists the ids of the rows for the tools this source "
                    "bundles, wraps, ports or cites")
            continue
        for part in parts:
            if not (part in run.by_source and part != sid):
                run.add("artifacts", "artifact-merged", sid, "%r is named as a part but has no row of its own: give "
                        "each artifact its own source, pin and licence, and credit none with another's parts" % part)
        for other in [source] + [run.by_source[part] for part in parts if part in run.by_source and part != sid]:
            if other.get("status") != "accepted":
                continue
            if not (pinned(other) and other.get("licence") is not None):
                run.add("artifacts", "artifact-unpinned", other.get("id"), "an artifact named on its own carries its "
                        "own pin (retrieval date, and a version or publication date) and licence entry")
    if listing:
        run.ran("artifacts")


def check_spend(run):
    spend = run.data.get("spend")
    if not isinstance(spend, dict):
        return
    limit = spend.get("limit_usd")
    limit = limit if isinstance(limit, (int, float)) and not isinstance(limit, bool) else None
    total, piloted = 0.0, False
    for number, entry in enumerate(spend.get("entries", []) if isinstance(spend.get("entries"), list) else [], start=1):
        if not isinstance(entry, dict):
            continue
        usd = entry.get("usd")
        if not isinstance(usd, (int, float)) or isinstance(usd, bool) or usd < 0:
            run.add("spend", "bad-value", entry.get("what") or number, "each spend entry records what it cost in USD")
            continue
        if entry.get("bulk") is True and not piloted:
            run.add("spend", "no-pilot", entry.get("what") or number,
                    "bulk spend comes after a small pilot whose output was read")
        if entry.get("pilot") is True:
            piloted = True
        total += usd
        if limit is not None and total > limit:
            run.add("spend", "over-budget", entry.get("what") or number,
                    "the running total reaches %.2f USD, past the %.2f USD limit: stop before the call that breaches it" % (
                        total, limit))
    run.ran("spend")


def check_record(run, record_path, log_hash, core):
    module = load_record_module(core)
    if module is None:
        run.status["record"] = "not-run"
        run.notes.append("record not checked: the core's record.py was not found")
        return
    try:
        task = read_json(record_path)
    except (OSError, ValueError) as exc:
        run.add("record", "record-shape", str(record_path), "the task record cannot be read: %s" % exc)
        return
    problems = module.shape(task, module.CONTRACT["root"]) if isinstance(task, dict) else ["$: not an object"]
    for problem in problems[:10]:
        run.add("record", "record-shape", str(record_path), problem)
    if problems:
        return
    log_receipts = [e["id"] for e in task.get("evidence", []) if e.get("artifact_sha256") == log_hash]
    if not log_receipts:
        run.add("record", "record-no-receipt", task.get("id"),
                "no receipt in the record holds this log's SHA-256: the log changed after it was cited, or was never cited")
        return
    cited_by = [o["id"] for o in task.get("observations", []) if set(o.get("evidence_ids", [])) & set(log_receipts)]
    if not cited_by:
        run.add("record", "record-uncited", task.get("id"),
                "receipt %s holds the log, but no observation cites it" % ", ".join(log_receipts))
    run.ran("record")


def unreadable(log, error):
    return {"format": FORMAT, "command": "check", "log": str(log), "status": "unreadable", "error": error,
            "checks": {}, "findings": [], "notes": [], "not_checked": list(NOT_CHECKED), "note": NOTE}


def check(log, record=None, core=None):
    """The check report for one research log (dict)."""
    path = pathlib.Path(log)
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        return unreadable(path, "the log cannot be read as JSON: %s" % exc)
    if not isinstance(data, dict) or data.get("format") != LOG_FORMAT:
        return unreadable(path, "not a %s log" % LOG_FORMAT)
    run = Run(data, path.parent)
    levels = strength_levels(core)
    check_shape(run)
    check_rounds(run)
    check_window(run)
    check_results(run)
    check_reading(run, levels)
    check_strength(run, levels)
    check_identifiers(run)
    check_queries(run)
    check_pacing(run)
    check_delegates(run)
    check_gaps(run)
    check_trace(run)
    check_sources(run)
    check_licence(run)
    check_artifacts(run)
    check_spend(run)
    log_hash = hashlib.sha256(raw).hexdigest()
    if record is not None:
        check_record(run, pathlib.Path(record), log_hash, core)
    status = "findings" if run.findings else "incomplete" if "not-run" in run.status.values() else "clean"
    return {"format": FORMAT, "command": "check", "log": str(path), "sha256": log_hash, "status": status,
            "checks": dict(run.status), "findings": run.findings, "notes": run.notes,
            "not_checked": list(NOT_CHECKED), "note": NOTE}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("check", help="check a research log")
    one.add_argument("log")
    one.add_argument("--record", help="the task record that cites the log")
    one.add_argument("--core", help="the westack core folder (default: ../westack beside this skill)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 64 if exc.code else 0
    report = check(args.log, record=args.record, core=args.core)
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return {"clean": 0, "findings": 1}.get(report["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
