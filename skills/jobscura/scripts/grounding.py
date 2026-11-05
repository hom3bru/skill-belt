#!/usr/bin/env python3
"""Offline claim grounding and requirement coverage for application drafts.

claims    Build a claim ledger: every number, date, named entity, credential,
          superlative and authority verb in a draft, checked against the user's
          own evidence files *in context* (the evidence sentence must share
          content words with the draft sentence, so a real number cannot be
          silently moved to the wrong employer or project). Flags authority
          escalation, e.g. evidence says "supported" while the draft says "led".
coverage  Map a posting's required/preferred items to evidence and to a draft:
          addressed, evidence not used, addressed without found evidence, or no
          evidence found. Suggests only terms that the evidence itself contains.

Lexical review aids, not truth certification: a "supported" atom means matching
words were found near related words, not that the claim is accurate.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

import jobscura_common as common
from jobscura_common import ToolError, content_tokens, excerpt, require

VERSION = "1.0.0"
MONTHS = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
NUMBER = re.compile(r"(?<![\w.])(?P<cur>[$£€])?\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
                    r"(?:\s?(?P<scale>%|percent\b|per ?cent\b|[kK]\b|[mM]\b|[bB]n?\b|million\b|billion\b|thousand\b))?(?P<plus>\+)?")
YEAR = re.compile(r"^(?:19|20)\d{2}$")
MONTH_YEAR = re.compile(rf"\b{MONTHS}\.?\s+(?:19|20)\d{{2}}\b", re.I)
ENTITY = re.compile(r"\b(?:[A-Z][a-zA-Z0-9&'’.-]*[a-zA-Z0-9]|[A-Z]{2,}[a-z]?)(?:\s+(?:of|and|&|for|the|de|du|la|von|van)?\s*"
                    r"(?:[A-Z][a-zA-Z0-9&'’.-]*[a-zA-Z0-9]|[A-Z]{2,}))*")
CREDENTIALS = re.compile(r"\b(?:Ph\.?\s?D|MBA|M\.?Sc|B\.?Sc|CPA|PMP|CFA|CISSP|CISA|CISM|SHRM-(?:CP|SCP)|PRINCE2|CAPM|ACCA|CIPD|"
                         r"RN|LPN|JD|LLM|PE|CSM|ITIL|AWS Certified[\w -]*)\b|\b(?:certified|certification|licensed|license[ds]?|"
                         r"licence[ds]?|chartered|accredited|bachelor'?s|master'?s|doctorate|degree)\b", re.I)
AUTHORITY = re.compile(r"\b(?:led|lead|leading|managed|manage|managing|directed|directing|supervised|supervise|oversaw|"
                       r"oversee|overseeing|headed|owned|owning|founded|co-founded|launched|spearheaded|built|"
                       r"established|architected|drove|chaired|ran|hired|implemented|configured|administered|migrated|deployed|set up|reporting to me|direct reports?)\b", re.I)
VERB_STARTERS = {"led", "lead", "built", "ran", "won", "grew", "drove", "taught", "wrote", "oversaw", "spoke", "began", "made",
                 "set", "cut", "sold", "brought", "kept", "met", "took", "gave", "chose", "found", "held", "rebuilt", "redid",
                 "manage", "coordinate", "support", "deliver", "develop", "design", "create", "own", "run", "build",
                 "partner", "drive", "help", "use", "work", "serve", "plan", "write", "teach", "train", "translate"}
SUPPORT = re.compile(r"\b(?:supported|support|supporting|assisted|assist|helped|help|coordinated|coordinate|coordinating|"
                     r"contributed|participated|facilitated|collaborated|partnered|advised|recommended|proposed|drafted|"
                     r"member of|used|worked with|worked in|worked on|worked alongside|shadowed)\b", re.I)
AUTHORSHIP = re.compile(r"\b(?:implemented|configured|administered|migrated|deployed|set up)\b", re.I)
ORGANIZATION_END = re.compile(r"\b(?:Inc|Corp|Ltd|Co|LLC|PLC|GmbH|University|College|Institute)\b", re.I)
SUPERLATIVE = re.compile(r"\b(?:first|only|sole|solely|single-handedly|best|top|largest|biggest|record|record-breaking|#1|"
                         r"number one|award-winning|unprecedented|leading|world-class|unique(?:ly)?)\b", re.I)
STOP_ENTITIES = {"i", "the", "a", "an", "and", "in", "on", "at", "for", "to", "of", "my", "our", "we", "this", "that", "as",
                 "with", "by", "it", "he", "she", "they", "dear", "hiring", "manager", "sincerely", "regards", "thank", "thanks",
                 "experience", "education", "skills", "summary", "profile", "objective", "references", "work", "professional",
                 "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
                 "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                 "present", "current", "today", "yours", "please", "also", "however", "additionally", "recently"}
SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9}


# ------------------------------------------------------------------ atoms
def numbers(text):
    found = []
    for match in NUMBER.finditer(text):
        raw = match.group(0).strip()
        digits = match.group("num").replace(",", "")
        scale = (match.group("scale") or "").casefold().replace(" ", "")
        if YEAR.match(digits) and not match.group("cur") and not scale:
            found.append({"kind": "year", "value": digits, "key": digits})
            continue
        try:
            value = float(digits)
        except ValueError:
            continue
        percent = scale in {"%", "percent", "percent"} or scale.startswith("per")
        value *= SCALE.get(scale, 1)
        found.append({"kind": "percent" if percent else "number", "value": raw, "key": round(value, 6), "currency": match.group("cur")})
    return found


def entities(text):
    found, seen = [], set()
    for match in ENTITY.finditer(text):
        phrase = match.group(0).strip(" .,-")
        words = phrase.split()
        if not words:
            continue
        at_start = text[:match.start()].strip() == ""
        first = words[0].casefold()
        if at_start and len(words) > 1 and not words[0].isupper() and (
                first in VERB_STARTERS or first.endswith(("ed", "ing")) or first in STOP_ENTITIES):
            words = words[1:]  # sentence-initial capital on a verb, not part of the name
        if len(words) == 1 and ((at_start and words == phrase.split()) or words[0].casefold() in STOP_ENTITIES or len(words[0]) < 2):
            if not (words[0].isupper() and len(words[0]) >= 2):  # acronyms count even at sentence start
                continue
        while words and words[0].casefold() in STOP_ENTITIES:
            words = words[1:]
        if not words:
            continue
        phrase = " ".join(words)
        key = phrase.casefold()
        if key in seen or key in STOP_ENTITIES:
            continue
        seen.add(key)
        found.append({"kind": "entity", "value": phrase, "key": key})
    return found


def atoms(sentence):
    result = numbers(sentence)
    for match in MONTH_YEAR.finditer(sentence):
        result.append({"kind": "date", "value": match.group(0), "key": " ".join(match.group(0).casefold().replace(".", "").split())[:3]
                       + " " + match.group(0)[-4:]})
    credentials = [{"kind": "credential", "value": m.group(0), "key": m.group(0).casefold().replace(".", "").replace(" ", "")}
                   for m in CREDENTIALS.finditer(sentence)]
    credential_words = {c["value"].casefold() for c in credentials}
    result += [e for e in entities(sentence) if e["key"] not in credential_words]
    result += credentials
    for match in SUPERLATIVE.finditer(sentence):
        result.append({"kind": "superlative", "value": match.group(0), "key": match.group(0).casefold()})
    return result


# ------------------------------------------------------------------ evidence index
class Evidence:
    def __init__(self, paths):
        require(paths, "supply at least one --evidence file")
        self.units = []
        self.windows = []
        self.receipts = []
        for path in paths:
            data = common.read_input(path)
            text = common.document_text(path, data=data)
            self.receipts.append({"file": Path(path).name, "sha256": common.sha256(data)})
            file_units = common.units(text, Path(path).name)
            # Complete sentences stay separate. Only adjacent header fragments may
            # form a window: joining full employment records would hide swapped roles.
            lines = text.splitlines()
            for unit in file_units:
                self.windows.append(unit["text"])
            fragments = []
            for raw in lines:
                fragment = common.strip_bullet(raw).strip()
                identities = [a for a in atoms(fragment) if a["kind"] in {"entity", "credential", "year", "date"}]
                abbreviation = re.search(r"\b(?:Inc|Corp|Ltd|Co|LLC|PLC|Ph\.?D|B\.?Sc|M\.?Sc)\.$", fragment, re.I)
                complete = fragment.endswith(("!", "?", ";")) or fragment.endswith(".") and not abbreviation
                if (not fragment or complete or len(fragment.split()) > 14
                        or sum(a["kind"] == "entity" for a in identities) > 1):
                    fragments = []
                    continue
                organization = bool(ORGANIZATION_END.search(fragment))
                prior_dates = any(a["kind"] in {"year", "date"} for part in fragments for a in atoms(part))
                dated = any(a["kind"] in {"year", "date"} for a in identities)
                # Start another record at a new organization or date block;
                # keep employer/date/title as well as employer/title/date layouts.
                if (len(fragments) == 3 or dated and prior_dates
                        or organization and (prior_dates or any(ORGANIZATION_END.search(part) for part in fragments))):
                    fragments = []
                fragments.append(fragment)
                if len(fragments) > 1:
                    self.windows.append("\n".join(fragments))
            for unit in common.units(text, Path(path).name):
                unit["tokens"] = content_tokens(unit["text"])
                unit["lower"] = " " + " ".join(re.findall(r"[a-z0-9&+#]+", unit["text"].casefold())) + " "
                unit["numbers"] = numbers(unit["text"])
                unit["dates"] = {a["key"] for a in atoms(unit["text"]) if a["kind"] == "date"}
                unit["credentials"] = {m.group(0).casefold().replace(".", "").replace(" ", "") for m in CREDENTIALS.finditer(unit["text"])}
                unit["authority"] = bool(AUTHORITY.search(unit["text"]))
                unit["support"] = bool(SUPPORT.search(unit["text"]))
                self.units.append(unit)
        require(self.units, "evidence files contain no readable text")

    def paired(self, identity_atoms):
        # Use the same matching semantics as the ledger, scoped to one window.
        for text in self.windows:
            lower = " " + " ".join(re.findall(r"[a-z0-9&+#]+", text.casefold())) + " "
            present = atoms(text)
            if all((" " + " ".join(re.findall(r"[a-z0-9&+#]+", a["key"])) + " ") in lower
                   if a["kind"] == "entity" else
                   any(b["kind"] == a["kind"] and b["key"] == a["key"] for b in present)
                   for a in identity_atoms):
                return True
        return False

    def containing(self, atom):
        kind, key = atom["kind"], atom["key"]
        hits = []
        for unit in self.units:
            if kind in {"number", "percent"}:
                # Same magnitude and, when both sides name a currency, the same currency:
                # "$50,000" is not supported by "€50,000".
                currency = atom.get("currency")
                ok = any(n["kind"] == kind and abs(n["key"] - key) <= max(1e-9, abs(key) * 0.005)
                         and not (currency and n.get("currency") and n["currency"] != currency) for n in unit["numbers"])
            elif kind == "year":
                ok = any(n["kind"] == "year" and n["key"] == key for n in unit["numbers"])
            elif kind == "date":
                ok = key in unit["dates"]
            elif kind == "credential":
                ok = key in unit["credentials"]
            else:
                phrase = " " + " ".join(re.findall(r"[a-z0-9&+#]+", key)) + " "
                ok = phrase.strip() != "" and phrase in unit["lower"]
            if ok:
                hits.append(unit)
        return hits


def anchors(sentence, atom_values):
    excluded = set()
    for value in atom_values:
        excluded |= content_tokens(str(value))
    return content_tokens(sentence) - excluded


def best_overlap(tokens, units):
    best, score = None, 0
    for unit in units:
        overlap = len(tokens & unit["tokens"])
        if overlap > score:
            best, score = unit, overlap
    return best, score


def location(unit):
    return {"file": unit["source"], "line": unit["line"], "text": excerpt(unit["text"], 300),
            "unit_sha": common.sha256(unit["text"].encode("utf-8"))[:16]}


def action_clauses(text):
    """Separate coordinated predicates, keeping coordinated tool names together."""
    parts, start = [], 0
    for boundary in re.finditer(r"\s+(?:and|but|while|whereas)\s+|[;,]\s*", text, re.I):
        tail = re.sub(r"^(?:(?:I|we)\s+)?(?:also\s+)?", "", text[boundary.end():], flags=re.I)
        prefix = text[start:boundary.start()]
        actions = list(AUTHORSHIP.finditer(prefix))
        action_tokens = set().union(*(content_tokens(action.group(0)) for action in actions))
        if (not boundary.group(0).startswith(";") and actions
                and not (content_tokens(prefix) - action_tokens)):
            continue  # 'implemented and configured Salesforce' shares its object
        if boundary.group(0).startswith(";") or AUTHORITY.match(tail) or SUPPORT.match(tail):
            parts.append(text[start:boundary.start()])
            start = boundary.end()
    return parts + [text[start:]]


def authorship_gaps(sentence, evidence):
    """Each claimed action must share a clause with the same named tool(s)."""
    gaps = []
    for clause in action_clauses(sentence):
        named = entities(clause)
        for action in AUTHORSHIP.finditer(clause):
            hits = [{id(unit) for unit in evidence.containing(atom)} for atom in named]
            remaining = content_tokens(clause) - content_tokens(action.group(0))
            candidates = [unit for unit in evidence.units
                          if (all(id(unit) in group for group in hits) if hits else
                              bool(remaining) and remaining <= unit["tokens"])]
            confirmed = False
            for candidate in candidates:
                for evidence_clause in action_clauses(candidate["text"]):
                    lower = " " + " ".join(re.findall(r"[a-z0-9&+#]+", evidence_clause.casefold())) + " "
                    if (re.search(r"\b" + re.escape(action.group(0)) + r"\b", evidence_clause, re.I)
                            and (all(" " + " ".join(re.findall(r"[a-z0-9&+#]+", atom["key"])) + " " in lower for atom in named)
                                 if named else remaining <= content_tokens(evidence_clause))):
                        confirmed = True
                        break
                if confirmed:
                    break
            if not confirmed:
                gaps.append({"kind": "authority_unconfirmed", "value": action.group(0),
                             "evidence": location(candidates[0]) if candidates else None,
                             "why": "Evidence does not connect this implementation action to the named tool or entity; confirm its scope."})
    return gaps


def claims(draft, evidence_paths):
    evidence = Evidence(evidence_paths)
    draft_data = common.read_input(draft)
    draft_text = common.document_text(draft, data=draft_data)
    ledger, totals = [], {"atoms": 0, "supported": 0, "present_in_evidence": 0, "found_elsewhere": 0, "not_found": 0, "flags": 0}
    for unit in common.units(draft_text, Path(draft).name):
        sentence = unit["text"]
        found_atoms = atoms(sentence)
        has_authority = bool(AUTHORITY.search(sentence))
        if not found_atoms and not has_authority:
            continue
        context = anchors(sentence, [a["value"] for a in found_atoms])
        # Two shared context words (one for very short sentences) keep a real number from
        # being credited to a different project that merely shares a verb such as "raised".
        needed = min(2, len(context))
        entry = {"line": unit["line"], "text": excerpt(sentence, 400),
                 "unit_sha": common.sha256(sentence.encode("utf-8"))[:16], "atoms": [], "flags": []}
        for atom in found_atoms:
            hits = evidence.containing(atom)
            supporting = [h for h in hits if len(context & h["tokens"]) >= needed]
            if supporting:
                status, where = "supported", max(supporting, key=lambda h: len(context & h["tokens"]))
            elif hits and atom["kind"] in {"entity", "credential", "year", "date"}:
                # Names, credentials and dates often sit in header lines; their presence is weaker
                # support than co-location, but not an attribution risk the way a moved number is.
                status, where = "present_in_evidence", hits[0]
            elif hits:
                status, where = "found_elsewhere", hits[0]
            else:
                status, where = "not_found", None
            if atom["kind"] == "superlative" and status != "supported":
                entry["flags"].append({"kind": "unsupported_superlative", "value": atom["value"],
                                       "why": "Superlatives and exclusives need explicit support in context."})
            totals["atoms"] += 1
            totals[status] += 1
            entry["atoms"].append({"kind": atom["kind"], "value": atom["value"], "status": status,
                                   "evidence": location(where) if where else None})
        identities = [a for a in found_atoms if a["kind"] in {"entity", "credential", "year", "date"}
                      and evidence.containing(a)]
        if len(identities) >= 2 and not evidence.paired(identities):
            entry["flags"].append({"kind": "combination_unsupported", "values": [a["value"] for a in identities],
                                   "why": "Check that these belong together; no evidence window contains this combination."})
        if has_authority:
            # Tool names are the only anchor in terse claims such as 'Implemented Salesforce'.
            authority_context = context | set().union(*(content_tokens(a["value"]) for a in found_atoms
                                                        if a["kind"] == "entity"))
            related, score = best_overlap(authority_context, evidence.units)
            authorship = AUTHORSHIP.search(sentence)
            if authorship:
                entry["flags"].extend(authorship_gaps(sentence, evidence))
            elif related is None or score == 0:
                entry["flags"].append({"kind": "authority_unverified", "value": AUTHORITY.search(sentence).group(0),
                                       "why": "No related evidence sentence was found for this leadership/ownership claim."})
            elif related["support"] and not related["authority"]:
                entry["flags"].append({"kind": "authority_escalation", "value": AUTHORITY.search(sentence).group(0),
                                       "evidence": location(related),
                                       "why": "The closest evidence describes support or use-level work; the draft claims leadership or ownership."})
            elif not related["authority"]:
                entry["flags"].append({"kind": "authority_unconfirmed", "value": AUTHORITY.search(sentence).group(0),
                                       "evidence": location(related),
                                       "why": "Related evidence does not confirm leadership or ownership; confirm the scope of this role."})
        totals["flags"] += len(entry["flags"])
        if entry["atoms"] or entry["flags"]:
            ledger.append(entry)
    gaps = totals["found_elsewhere"] + totals["not_found"] + totals["flags"]
    return {"schema_version": 1, "tool": "grounding.claims", "tool_version": VERSION,
            "status": "review_needed" if gaps else "no_lexical_gaps_found",
            "draft": Path(draft).name, "draft_sha256": common.sha256(draft_data),
            "evidence_files": [Path(p).name for p in evidence_paths], "evidence": evidence.receipts,
            "evidence_units": len(evidence.units), "totals": totals, "ledger": ledger,
            "statuses": {"supported": "matching value found in an evidence sentence that shares context words",
                         "present_in_evidence": "name, credential or date appears in the evidence, not beside related words",
                         "found_elsewhere": "number exists in evidence but in an unrelated sentence: check attribution",
                         "not_found": "no matching value in the supplied evidence: confirm with the user or remove"},
            "limits": "Lexical review aid. It cannot judge truth, paraphrase, causality or attribution; supported "
                      "means co-located words, not a verified claim. Absent evidence is not proof a claim is false."}


# ------------------------------------------------------------------ coverage
# Boilerplate words in requirements. Exact stems only, plus a few prefixes for word
# families: a prefix list like "work" would also delete Workday or Workforce.
GENERIC = {"strong", "excellent", "proven", "ability", "abilities", "knowledge", "skill", "work", "team", "environment",
           "written", "verbal", "relevant", "related", "equivalent", "including", "minimum", "least", "plus", "nice",
           "bonus", "solid", "good", "great", "deep", "high", "level", "excellence", "effective", "effectively"}
GENERIC_PREFIXES = ("demonstrat", "proficien", "familiar", "understand", "communic", "experienc")  # stems, e.g. communication -> communic


def requirement_tokens(text):
    return {t for t in content_tokens(text) if t not in GENERIC and not t.startswith(GENERIC_PREFIXES)}


def matches(tokens, units, limit=2):
    scored = []
    for unit in units:
        shared = tokens & unit["tokens"]
        if not shared:
            continue
        ratio = len(shared) / max(1, len(tokens))
        if len(shared) >= 2 or ratio >= 0.5:
            scored.append((len(shared), ratio, unit, shared))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2]["line"]))
    return [{**location(unit), "shared_terms": sorted(shared)} for _, _, unit, shared in scored[:limit]]


def coverage(posting=None, capture=None, evidence_paths=(), draft=None):
    import posting_intel
    if capture:
        record = common.read_json(Path(capture) / "capture.json")
        text = common.read_input(Path(capture) / "posting.txt").decode("utf-8")
        require(common.sha256(text.encode("utf-8")) == record.get("text_sha256"), "capture text changed since capture")
        name = "capture"
    else:
        require(posting, "supply --posting FILE or --capture DIR")
        text = common.document_text(posting) if Path(posting).suffix.casefold() not in {".html", ".htm"} else \
            common.html_to_text(common.read_input(posting).decode("utf-8-sig"))[0]
        name = Path(posting).name
    requirements = posting_intel.extract_requirements(text)
    evidence = Evidence(list(evidence_paths))
    draft_units = []
    draft_data = common.read_input(draft) if draft else None
    if draft:
        for unit in common.units(common.document_text(draft, data=draft_data), Path(draft).name):
            unit["tokens"] = content_tokens(unit["text"])
            draft_units.append(unit)
    draft_tokens = set().union(*(u["tokens"] for u in draft_units)) if draft_units else set()
    rows, counts = [], {}
    # Requirements outside recognised sections (e.g. "Applicants must have a driving licence"
    # after the bullet list) are often eligibility conditions: always keep them, labelled.
    groups = [("required", requirements["required"]), ("preferred", requirements["preferred"]),
              ("unclassified", requirements["unclassified"])]
    for group, items in groups:
        for item in items:
            tokens = requirement_tokens(item["text"])
            if not tokens:
                # Never drop a requirement silently: an unassessable row is still a row to read.
                counts["not_assessable"] = counts.get("not_assessable", 0) + 1
                rows.append({"group": group, "line": item["line"], "requirement": excerpt(item["text"], 300),
                             "unit_sha": common.sha256(item["text"].encode("utf-8"))[:16],
                             "status": "not_assessable", "evidence": [],
                             "note": "No specific terms left after removing boilerplate; judge this one by reading."})
                continue
            in_evidence = matches(tokens, evidence.units)
            in_draft = matches(tokens, draft_units, 1) if draft else []
            if draft:
                status = ("addressed" if in_evidence and in_draft else "evidence_not_used" if in_evidence else
                          "addressed_without_found_evidence" if in_draft else "no_evidence_found")
            else:
                status = "evidence_found" if in_evidence else "no_evidence_found"
            counts[status] = counts.get(status, 0) + 1
            row = {"group": group, "line": item["line"], "requirement": excerpt(item["text"], 300), "status": status,
                   "unit_sha": common.sha256(item["text"].encode("utf-8"))[:16],
                   "evidence": in_evidence}
            if draft:
                row["draft"] = in_draft
                evidence_terms = set().union(*(set(e["shared_terms"]) for e in in_evidence)) if in_evidence else set()
                row["supported_terms_missing_from_draft"] = sorted(evidence_terms - draft_tokens)
            rows.append(row)
    return {"schema_version": 1, "tool": "grounding.coverage", "tool_version": VERSION, "posting": name,
            "draft_sha256": common.sha256(draft_data) if draft else None,
            "evidence": evidence.receipts,
            "evidence_files": [Path(p).name for p in evidence_paths], "draft": Path(draft).name if draft else None,
            "sections_detected": requirements["sections_detected"], "counts": counts, "rows": rows,
            "guidance": "Use 'evidence_not_used' to choose stronger supported material, treat "
                        "'addressed_without_found_evidence' as a fabrication risk to confirm, and keep "
                        "'no_evidence_found' as an honest gap or a question for the user. Suggested terms come only "
                        "from the user's evidence; never add a term the evidence does not support.",
            "limits": "Word-overlap heuristic over stemmed content words. It misses synonyms and paraphrase and is not "
                      "an ATS score, hiring probability or quality judgment."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    c = commands.add_parser("claims", help="claim ledger for a draft against evidence files")
    c.add_argument("--draft", required=True, help=".txt/.md/.docx/.html draft")
    c.add_argument("--evidence", required=True, nargs="+", help="evidence files (.txt/.md/.docx/.html/.json)")
    c.add_argument("--out")
    v = commands.add_parser("coverage", help="posting requirements vs evidence (and optionally a draft)")
    v.add_argument("--posting", help="posting text/HTML/DOCX file")
    v.add_argument("--capture", help="capture directory from application_packet.py")
    v.add_argument("--evidence", required=True, nargs="+")
    v.add_argument("--draft")
    v.add_argument("--out")
    args = parser.parse_args(argv)
    if args.command == "claims":
        return common.run_cli(lambda: common.emit(claims(args.draft, args.evidence), args.out))
    return common.run_cli(lambda: common.emit(coverage(args.posting, args.capture, args.evidence, args.draft), args.out))


if __name__ == "__main__":
    raise SystemExit(main())
