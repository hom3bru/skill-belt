# Coverage, scope and the record check

Coverage and scope are read in audit mode; the record check in every mode, before the report.

## Coverage and scope

"Covered" means a ledger closed the file. Reuse westack-review's checker on a diff from the empty tree:

```text
git diff --no-color --no-ext-diff --no-textconv 4b825dc642cb6eb9a060e54bf8d69288fbee4904 <rev> -- <scope> > audit.diff
python "<westack-review>/scripts/diffscope.py" coverage audit.diff ledger.json
git ls-files -z > tracked.bin
python "<this skill>/scripts/secaudit.py" scope <root> --tracked tracked.bin
```

Each file is reviewed, or skipped with a reason and still counted unchecked; an unmarked file fails. A path-scoped run is partial. Untracked files are not in the diff: list them apart; the scope digest covers them. The scope receipt is the revision for a clean checkout, else the digest, never with a remote URL's credentials. Without westack-review installed, coverage is not-run and the audit partial.

## Check the record

```text
python "<this skill>/scripts/secaudit.py" check findings.json <root>
python "<this skill>/scripts/secaudit.py" report findings.json --root <root> --out report.md
```

`check` applies the rules in [record](record.md), each snippet compared with its lines on disk. `report` renders only a passing record; regenerate it, never edit it. Exit 0 clean, 1 problems, 2 unreadable, 64 usage. It runs nothing; a clean record is not a secure system.
