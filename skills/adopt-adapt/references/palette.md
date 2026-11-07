# Palette log

Palette is the owner's cross-project research library. Its uses table records which saved sources each project used and how. When the `palette` command is installed, the review record (§8) also leaves one note there per READY pair, so later work can find the assessment. These notes, and any save they need, are the only writes outside the write scope (§1). They go through the CLI only: never edit library files, and never confirm, reject, merge, lock or delete library entries. Skip them when the user says not to log.

## Palette absent

If `palette` is not on PATH, or `palette status` fails, say once "Palette absent: not logged" and finish as usual. Nothing else changes.

## After publishing the report

1. Find the item: `palette check "<locator>"`. If a source is not saved but informed the assessment, save it first with `palette save "<locator>" --why "<one line>"`; otherwise say "not in Palette" for that source.
2. Log one row per READY pair:

   ```text
   palette log-use ITEM --project <recipient-slug> --purpose assessed --artifact "<report path>#<pair id>" --decision "assessed for <recipient>" [--pointer "adopt-adapt:<absolute run.json path>#<item id>"]
   ```

   - `--project`: the recipient's Palette project; for an OPPORTUNITY, the launch project.
   - `--artifact`: the published report and the pair's anchor. A chat-only manual assessment uses `chat <YYYY-MM-DD>`.
   - `--pointer`, structured runs only: `palette pointers check` resolves the item inside run.json.
   - `--decision` names what was assessed and for whom. It never carries the result, mechanism value, confidence or fit (§0.8). Palette shows `assessed` and the pointer; the verdict stays in the report.

## After the owner's answer

For ADOPT/ADAPT, §8 asks accept / defer / decline. Log one more row for the same item and project:

| Owner's answer | `--purpose` |
| --- | --- |
| accepts an ADOPT | `adopted` |
| accepts an ADAPT or ADAPT-with-prerequisite | `adapted` |
| declines | `rejected` |
| defers | no row |

`--artifact` names the plan, or the commit once it is implemented. `--decision` records the owner's answer and its date in one line.

## Reading back

A later run may use `palette check` and `palette find` to locate saved sources and earlier searches. Earlier uses (assessed, adopted, adapted, rejected) point to reports. They are never inputs to a fresh judgment (§0.8): re-verify any reused fact for identity, revision and freshness.
