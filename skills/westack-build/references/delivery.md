# Delivery diff audit

Read before any "done", in every mode; the report's diff-audit item comes from it.

Before any "done", save `git diff --no-color <start revision>` and `git status --porcelain --untracked-files=all` into the evidence folder (and the status saved before the first edit), then run:

```text
python "<this skill>/scripts/diffaudit.py" <diff> --status <status> --start-status <status0> --allow <glob> ...
```

It reads the saved files and runs nothing. Exit 0 is clean. Exit 1 lists the paths that need a decision (out of scope, deferred execution, an existing test that lost a line or gained a skip, narrowed test selection, a scratch-looking file, a hunk that only reformats (whitespace, quote style or import order), a file dirty before you started): resolve or report each. Exit 2 means an empty change, which is not a fix. Without Python or outside a git repository, classify every file you created or changed by hand the same way and say so.
