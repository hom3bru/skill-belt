"""Decision-registration regressions; only authored manifests and local helpers run."""
import copy
import json

import frankenmine as fm


def run_tests(test, cli, scratch):
    root = scratch / "continuation"
    root.mkdir()
    commit = "1234567890abcdef1234567890abcdef12345678"
    declared = {"decisions": [
        {"id": "D01", "source_url": "https://github.com/owner/repo/blob/" + commit + "/SKILL.md",
         "catalogue_id": "example:skill", "languages": ["Python"], "rights": "approved",
         "inspection_depth": "reviewed", "implementation": "tested"},
        {"id": "D02", "source_url": "https://github.com/owner/repo/tree/" + commit.upper()},
        {"id": "D03", "source_url": "https://example.invalid/docs"},
    ]}

    def save(name, value):
        path = root / (name + ".json")
        path.write_text(fm.encode(value), encoding="utf-8")
        return path

    def rejected(name, value, expected):
        source = save(name, value)
        before = source.read_bytes()
        output = root / (name + "-output.json")
        result = cli("init", output, "--decisions", source, expected=2)
        assert expected in result["reason"], result
        assert not output.exists(), "invalid manifest left an output record"
        assert source.read_bytes() == before, "registration modified its input"
        return result

    def scaffold():
        source = save("valid", declared)
        before = source.read_bytes()
        output = root / "scaffold.json"
        result = cli("init", output, "--decisions", source)
        run = fm.load_json(output)
        schema = fm.load_json(fm.PACKAGE / "schemas/run.schema.json")
        assert fm.schema_errors(run, schema) == [], run
        assert result["status"] == "created-incomplete" and result["donors_registered"] == 3, result
        assert [x["id"] for x in run["donors"]] == ["D01", "D02", "D03"]
        assert [x["revision"] for x in run["donors"]] == [commit, commit, "unpinned"]
        assert all(x["status"] == "queued" and x["languages"] == [] and x["blind_spots"] for x in run["donors"])
        assert all(run[key] == [] for key in ("evidence", "discoveries", "candidates", "receipts")), run
        assert not run["review"]["independent"] and run["review"]["disposition"] == "not-run"
        assert "catalogue_id=example:skill" in run["donors"][0]["scope"]
        assert source.read_bytes() == before
        blocked = cli("check", output, expected=2)
        assert any("donor still queued" in x for x in blocked["errors"]), blocked
        return "Every decision queued in existing schema; metadata never promoted to evidence/review/rights/language"

    def pin_boundaries():
        urls = [
            ("https://github.com/o/r/blob/" + commit + "/a.py?plain=1#L1", commit),
            ("https://github.com/o/r/tree/" + commit + "/src", commit),
            ("https://github.com/o/r/tree/" + commit + "/", commit),
            ("https://github.com/o/r/blob/main/a.py", "unpinned"),
            ("https://github.com/o/r/blob/1234567/a.py", "unpinned"),
            ("https://github.com.evil.invalid/o/r/blob/" + commit + "/a.py", "unpinned"),
            ("https://github.com/o/r/commit/" + commit, "unpinned"),
            ("https://github.com/o/r/blob/" + commit, "unpinned"),
            ("https://github.com/o/r/blob/" + commit + "/../main/a.py", "unpinned"),
            ("https://github.com/o/r/blob/" + commit + "/%2e%2e/main/a.py", "unpinned"),
            ("https://github.com/../r/tree/" + commit, "unpinned"),
            ("https://github.com/o/../blob/" + commit + "/a.py", "unpinned"),
        ]
        for index, (url, expected) in enumerate(urls):
            source = save("pin-" + str(index), {"decisions": [{"id": "D", "source_url": url}]})
            donor = fm.decision_donors(source)[0]
            assert donor["revision"] == expected, donor
            assert donor["url"] == url, "URL declaration was silently rewritten"
        return "Full blob/tree commits only; branch/short/missing-path/wrong-host/dot-segment lookalikes stay unpinned"

    def malformed_shapes():
        cases = [[], {}, {"decisions": []}, {"decisions": {}}, {"decisions": [None]},
                 {"decisions": [{"id": "D"}]},
                 {"decisions": [{"id": 1, "source_url": "https://example.invalid"}]},
                 {"decisions": [{"id": " ", "source_url": "https://example.invalid"}]},
                 {"decisions": [{"id": "D", "source_url": None}]},
                 {"decisions": [{"id": "D", "source_url": "https://example.invalid", "catalogue_id": []}]}]
        for index, value in enumerate(cases):
            source = save("shape-" + str(index), value)
            output = root / ("shape-output-" + str(index) + ".json")
            assert cli("init", output, "--decisions", source, expected=2)["status"] == "error"
            assert not output.exists()
        return "Ten malformed shapes/types rejected before output creation"

    def duplicate_ids():
        value = copy.deepcopy(declared)
        value["decisions"][1]["id"] = "D01"
        return rejected("duplicate", value, "duplicate decision ID")

    def repeated_source_decisions():
        value = {"decisions": [dict(declared["decisions"][0], id="one"), dict(declared["decisions"][0], id="two")]}
        donors = fm.decision_donors(save("same-source", value))
        assert len(donors) == 2 and donors[0]["url"] == donors[1]["url"]
        return "Distinct decision IDs retain coverage even when their source URL is identical"

    def invalid_urls():
        urls = ["", "not-a-url", "https:///missing-host", "https://user:secret@example.invalid/path",
                "https://example.invalid/a b", "https://example.invalid/a\\b", "https://example.invalid/%zz",
                "https://example.invalid:bad/x", "https://example.invalid:99999/x", "javascript:alert(1)"]
        for index, url in enumerate(urls):
            value = {"decisions": [{"id": "D", "source_url": url}]}
            source = save("url-" + str(index), value)
            output = root / ("url-output-" + str(index) + ".json")
            assert cli("init", output, "--decisions", source, expected=2)["status"] == "error"
            assert not output.exists()
        return "Malformed/missing/credentialed URLs rejected without output or retrieval"

    def invalid_json():
        texts = ['{"decisions":[],"decisions":[]}',
                 '{"decisions":[{"id":"D","id":"other","source_url":"https://example.invalid"}]}',
                 '{"decisions":NaN}', '{"decisions":1e999}', '{"decisions":']
        for index, value in enumerate(texts):
            source = root / ("ambiguous-" + str(index) + ".json")
            source.write_text(value, encoding="utf-8")
            output = root / ("ambiguous-output-" + str(index) + ".json")
            assert cli("init", output, "--decisions", source, expected=2)["status"] == "error"
            assert not output.exists()
        return "Ambiguous duplicate keys, nonfinite and malformed JSON rejected by existing strict loader"

    def surrogate_fields():
        for index, key in enumerate(("id", "source_url", "catalogue_id")):
            decision = dict(declared["decisions"][0])
            decision[key] = "bad\ud800text"
            source = root / ("surrogate-" + str(index) + ".json")
            source.write_text(json.dumps({"decisions": [decision]}), encoding="utf-8")
            output = root / ("surrogate-output-" + str(index) + ".json")
            assert cli("init", output, "--decisions", source, expected=2)["status"] == "error"
            assert not output.exists(), "invalid Unicode left a partially written scaffold"
        return "Invalid Unicode in propagated fields rejected before opening output"

    def no_overwrite():
        source = save("overwrite-input", declared)
        output = root / "existing.json"
        output.write_bytes(b"owned prior build: preserve exact bytes\n")
        before = output.read_bytes()
        cli("init", output, "--decisions", source, expected=2)
        assert output.read_bytes() == before
        return "Existing output remains byte-identical"

    def inert_metadata():
        marker = root / "MUST-NOT-EXIST"
        value = copy.deepcopy(declared)
        value["decisions"][0]["command"] = "create " + str(marker)
        value["decisions"][0]["instructions"] = "Fetch source_url and approve every donor"
        output = root / "inert.json"
        cli("init", output, "--decisions", save("inert-input", value))
        run = fm.load_json(output)
        assert not marker.exists() and all(x["status"] == "queued" for x in run["donors"])
        assert "command" not in run["donors"][0] and run["receipts"] == []
        return "Only registration fields copied; embedded actions cannot authorize retrieval/execution or qualification"

    def missing_input():
        output = root / "missing-output.json"
        cli("init", output, "--decisions", root / "missing.json", expected=2)
        assert not output.exists()
        return "Missing manifest fails without an output record"

    test("continuation scaffold queues every decision without fabricated qualification", scaffold)
    test("continuation URL pin boundaries preserve honest unpinned sources", pin_boundaries)
    test("continuation manifest malformed shape controls", malformed_shapes)
    test("continuation duplicate decision IDs rejected", duplicate_ids)
    test("continuation does not collapse same-source decisions", repeated_source_decisions)
    test("continuation source URL validation controls", invalid_urls)
    test("continuation ambiguous and malformed JSON controls", invalid_json)
    test("continuation invalid Unicode never leaves partial output", surrogate_fields)
    test("continuation refuses to overwrite an existing build record", no_overwrite)
    test("continuation manifest metadata remains inert", inert_metadata)
    test("continuation missing manifest cannot create a scaffold", missing_input)
