# Palette log

Palette is the owner's cross-project research library. Its uses table records which saved sources each project used and how. When the `palette` command is installed, Frankenmine leaves one note there per reviewed donor, so later work can see which sources fed which product. These notes, and any save they need, are the only writes outside the output folder. They go through the CLI only: never edit library files, and never confirm, reject, merge, lock or delete library entries. Skip it when the user says not to log.

## Palette absent

If `palette` is not on PATH, or `palette status` fails, say once "Palette absent: not logged" and deliver as usual. Nothing else changes.

## When and what

At delivery (step 6), log one row for each donor that ended `reviewed`, whether or not any part of it was selected. Deferred, blocked and unprocessed donors get no row; their reasons stay in the reply or record.

1. Find the item: `palette check "<canonical URL>"`. If the donor is not saved but informed the design, save it first with `palette save "<canonical URL>" --why "<one line>"`; otherwise say "not in Palette" for that donor and move on.
2. Log the use:

   ```text
   palette log-use ITEM --project <product-slug> --purpose donor --artifact "<dossier or run path>#<donor id>" --decision "<one line>" [--pointer "frankenmine:<absolute run.json path>#<donor id>"]
   ```

   - `--project`: the new product's Palette project slug.
   - `--artifact`: the dossier or run record and the donor's ID. An answer with no file uses `answer <YYYY-MM-DD>`.
   - `--decision`: what was taken and by which route (for example `selected: checkpoint store, pattern-only`), or `reviewed; nothing selected` with the reason.
   - `--pointer`, full tier only: `palette pointers check` resolves the donor ID inside run.json, and `palette export frankenmine-decisions` hands the same IDs back to `init --decisions`. Its `--project` filter returns only items the owner has confirmed in that project.
3. In the closing report, list the item IDs logged, or say Palette was absent.

A logged donor points to this run's evidence. It is not evidence for a later run: re-pin and re-read before reusing anything.
