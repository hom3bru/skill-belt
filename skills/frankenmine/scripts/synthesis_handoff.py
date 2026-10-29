"""Read-only continuation projection. JSON pointers locate authoritative source fields."""
from pathlib import Path

import frankenmine as fm


def build_index(run, source, errors, decisions=None):
    """Join exact IDs only; recorded stages and byte checks never establish benefit."""
    shape = fm.record_schema_errors(run)
    if shape:
        raise ValueError("Cannot index malformed record: " + "; ".join(shape))
    groups = fm.GROUPS
    identifiers = [x["id"] for group in groups for x in run.get(group, [])]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Cannot index duplicate stable IDs")
    source = Path(source).resolve()

    def ref(pointer, path=source):
        path = Path(path).resolve()
        return dict(path=str(path), pointer=pointer, link=path.as_uri() + "#" + pointer)

    by = {group: {x["id"]: (i, x) for i, x in enumerate(run.get(group, []))} for group in groups}
    pending, contracts, joins = [], [], []

    def owners(name):
        return [dict(owner=x["owner"], key=x["key"], source=ref("/ownership/" + str(i)))
                for i, x in enumerate(run["ownership"]) if fm.norm_name(x["owner"]) == fm.norm_name(name)]

    # Preserve conflicting declarations instead of resolving ownership by array order.
    # Keys compare as the validator does: case, whitespace and separators are ignored.
    keys = list(dict.fromkeys(fm.norm_key(x["key"]) for x in run["ownership"]))
    for key in keys:
        claims = [dict(owner=x["owner"], key=x["key"], source=ref("/ownership/" + str(i)))
                  for i, x in enumerate(run["ownership"]) if fm.norm_key(x["key"]) == key]
        if len(claims) > 1:
            pending.append(dict(kind="ownership", id=claims[0]["key"], state="conflict", owners=claims,
                                source=claims[0]["source"], next="Resolve authoritative owner in the record"))

    if decisions is not None:
        # Reuse registration's parser only for declarations; nothing is fetched or qualified.
        declared = fm.decision_donors(decisions)
        for i, decision in enumerate(declared):
            entry = by["donors"].get(decision["id"])
            state = "missing-donor" if entry is None else (
                "matched" if entry[1]["url"] == decision["url"] else "source-mismatch")
            join = dict(id=decision["id"], source_url=decision["url"], join=state,
                        source=ref("/decisions/" + str(i), decisions),
                        donor=ref("/donors/" + str(entry[0])) if entry else None)
            joins.append(join)
            if state != "matched":
                pending.append(dict(kind="decision-join", id=decision["id"], state=state,
                    source=join["source"], owners=[], next="Reconcile the exact decision ID and source URL"))
        declared_ids = {x["id"] for x in declared}
        for i, donor in enumerate(run["donors"]):
            if donor["id"] not in declared_ids:
                joins.append(dict(id=donor["id"], source_url=donor["url"], join="run-only",
                                  source=ref("/donors/" + str(i)), donor=ref("/donors/" + str(i))))

    def test_view(ident):
        entry = by["tests"].get(ident)
        shared = [c["id"] for c in run["candidates"] if ident in (c["acceptance"], c["negative_control"])]
        if entry is None:
            return dict(id=ident, status="missing", integrity="invalid", source=None, receipts=[], shared_by=shared)
        i, test = entry
        problems = []
        try:
            if fm.digest(fm.local_bytes(source.parent, test["oracle"])) != test["oracle_sha256"]:
                problems.append("oracle hash mismatch")
        except (OSError, ValueError) as exc:
            problems.append(str(exc))
        receipts = []
        # Ordered history: earlier failing attempts stay visible; the last entry decides status.
        history = sorted((x for x in enumerate(run["receipts"]) if x[1]["test"] == ident),
                         key=lambda x: x[1].get("sequence") or 0)
        for ri, receipt in history:
            invalid = [e for e in errors if e.startswith((receipt["id"] + ":", receipt["id"] + " raw:"))]
            receipts.append(dict(id=receipt["id"], source=ref("/receipts/" + str(ri)),
                raw=ref("", source.parent / receipt["raw_output"]),
                integrity="invalid" if invalid else "current-bytes-consistent",
                errors=invalid, control_detected=receipt["control_detected"],
                cases=receipt["cases"], passed=receipt["passed"], failed=receipt["failed"],
                skipped=receipt["skipped"], exit_code=receipt["exit_code"], sequence=receipt.get("sequence"),
                latest=(ri, receipt) == history[-1]))
        problems.extend(e for e in errors if e.startswith((ident + ":", ident + " oracle:")))
        if any(r["integrity"] == "invalid" for r in receipts):
            problems.append("invalid receipt")
        return dict(id=ident, purpose=test["purpose"], status=test["status"], source=ref("/tests/" + str(i)),
                    integrity="invalid" if problems else "current-bytes-consistent", errors=problems,
                    receipts=receipts, shared_by=shared)

    # In design mode no test is expected to have run: not-run is the honest state, not a pending defect.
    design = run["mode"] == "design"

    def expected(view):
        return design and view["status"] == "not-run" and view["integrity"] != "invalid"

    for i, inter in enumerate(run["interactions"]):
        if inter["status"] == "independent":
            # Disjoint declared touches need no receipt; an invalid claim stays pending.
            problems = [e for e in errors if e.startswith("interaction " + " / ".join(inter["components"]) + ":")]
            if problems:
                pending.append(dict(kind="interaction", id=inter["components"], state="independent-claim-invalid",
                    source=ref("/interactions/" + str(i)), test=None, errors=problems, owners=[],
                    next="Declare disjoint touches or verify the pair with an interaction/integration test"))
            continue
        evidence = test_view(inter.get("test"))
        settled = inter["status"] in ("compatible", "resolved") and "test" in inter
        if not settled or (evidence["status"] != "pass" and not expected(evidence)) or evidence["integrity"] == "invalid":
            pending.append(dict(kind="interaction", id=inter["components"], state=inter["status"],
                source=ref("/interactions/" + str(i)), test=evidence,
                owners=[dict(id=c["id"], owner=c["owner"], source=ref("/candidates/" + str(ci)),
                             ownership=owners(c["owner"])) for ci, c in enumerate(run["candidates"])
                        if c["id"] in inter["components"]], next="Resolve or verify the recorded interaction"))
    for i, c in enumerate(run["candidates"]):
        tests = [test_view(c["acceptance"]), test_view(c["negative_control"])]
        donor = by["donors"].get(c["donor"])
        valid = all(t["status"] == "pass" and t["integrity"] != "invalid" for t in tests)
        # Passing acceptance/control only verifies their bounded recorded checks.
        verified = valid and not any(e.startswith(c["id"] + ":") for e in errors)
        # Integration evidence: an integration acceptance, or an interaction/integration test of a pair or
        # group that includes this part. Declared is not verified; only a passing, intact receipt verifies.
        joint = ([c["acceptance"]] if tests[0].get("purpose") == "integration" else []) + [
            inter["test"] for inter in run["interactions"] if c["id"] in inter["components"] and "test" in inter]
        views = [v for v in (test_view(t) for t in dict.fromkeys(joint))
                 if v.get("purpose") in ("integration", "interaction")]
        passing = [v for v in views if v["status"] == "pass" and v["integrity"] != "invalid"]
        integration = dict(status="verified" if passing else "declared" if views else "not-recorded",
                           test=(passing or views)[0]["id"] if views else None)
        item = dict(id=c["id"], source=ref("/candidates/" + str(i)), design=c["phase"],
            implementation=c["implementation"], contract=c["contract"], owner=c["owner"], owners=owners(c["owner"]),
            approval_boundary=c["approval_boundary"], caller=c["caller"],
            donor=dict(id=c["donor"], source=ref("/donors/" + str(donor[0])) if donor else None,
                       url=donor[1]["url"] if donor else None),
            tests=tests, verification="recorded-checks-pass" if verified else "unverified", integration=integration)
        contracts.append(item)
        if c["phase"] in ("selected", "design-reviewed"):
            for t in tests:
                if (t["status"] != "pass" and not expected(t)) or t["integrity"] == "invalid":
                    pending.append(dict(kind="test", id=t["id"], state=t["status"],
                        source=t["source"] or item["source"], owners=item["owners"], evidence=t,
                        next="Resolve this contract's missing, failed or invalid check within recorded authorization"))
            # In design mode implementation is a separate authorization (the closing "authorization" item).
            if not design and (c["implementation"] == "not-started" or not verified):
                pending.append(dict(kind="contract", id=c["id"], state=c["implementation"], source=item["source"],
                    owners=item["owners"], next="Advance the next slice within recorded authorization" if c["implementation"] == "not-started"
                    else "Resolve missing, failed or invalid acceptance/control receipts"))
            if item["integration"]["status"] == "not-recorded":
                pending.append(dict(kind="integration", id=c["id"], state="not-recorded", source=item["source"],
                    owners=item["owners"], next="Record integration evidence if the intended claim requires it"))
    review = run["review"]
    if fm.review_issues(review):
        pending.append(dict(kind="review", id=review["reviewer"], state=review["disposition"],
            independence=review.get("independence"), problems=fm.review_issues(review),
            source=ref("/review"), owners=[], next="Obtain and adjudicate the required independent design review"))
    for i, text in enumerate(run["unresolved"]):
        pending.append(dict(kind="unresolved", id=None, state=text, source=ref("/unresolved/" + str(i)),
                            owners=[], next="Resolve or explicitly scope the recorded blocker"))
    if errors:
        pending.append(dict(kind="record-consistency", id=run["id"], state="blocked", source=ref(""),
                            owners=[], next="Resolve the existing validator errors; do not infer readiness"))
    if design:
        pending.append(dict(kind="authorization", id=run["id"], state="design-mode", source=ref("/mode"), owners=[],
                            next="Design mode: implementing needs the user's explicit authorization and an isolated "
                                 "output root; record both and set mode to implementation before any slice"))
    return dict(format="frankenmine-handoff-1", run_id=run["id"], source=ref(""),
        authority="Derived view only; edit the source record/dossier and regenerate",
        authorization=run["brief"]["authorization"],
        status="blocked" if errors or any(j["join"] in ("missing-donor", "source-mismatch") for j in joins) else "record-consistent",
        temporal_freshness="unknown-no-timestamps", benefit="not-established-by-helper",
        validation_errors=errors, decisions=joins,
        donors=[dict(id=d["id"], url=d["url"], status=d["status"], reason=d["reason"],
                     source=ref("/donors/" + str(i))) for i, d in enumerate(run["donors"])],
        contracts=contracts, pending=pending, next=pending[0] if pending else None)
