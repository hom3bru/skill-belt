# Public editions

Skill Belt publishes author-owned public editions of adopt-adapt, Frankenmine and westack. The westack edition is generated from its canonical skill source by `scripts/build_public.py`, so `skills/westack` is not edited by hand. The Frankenmine and adopt-adapt editions are hand-made portfolio editions of earlier baselines. Installed skills are never edited.

```sh
python -B scripts/build_public.py --westack DIR [--check]
python -B scripts/generate_manifest.py
python -B scripts/verify.py
```

The build copies the canonical skill into a staging directory inside this repository and drops the `exclude` globs listed in [public-build.json](../public-build.json). It then applies that skill's overlays: public replacement files under `public-overlays/<skill>/`, each pinned to the SHA-256 of the canonical file it was derived from. An optional `description` override replaces only the SKILL.md description line, pinned the same way. If a pinned canonical file has changed, the build fails until the overlay is re-derived.

The staged copy must also:

- contain no links or junctions;
- pass the leak-pattern scan and the local-link check;
- carry `references/evidence-vocabulary.md` byte-identical to `shared/evidence-vocabulary.md`, when the skill links to it.

Only when every named skill passes is `skills/<name>` replaced. `--check` stages and checks without replacing anything. The report gives source and edition tree hashes, so a rebuild can be compared byte for byte. Canonical sources are only read. A private identifier that is useless to readers is removed in the canonical source rather than overlaid.

Policy: omit private build and session identifiers, machine-specific transcripts and local audit logs; keep contracts, runnable tests, source URLs and inspection limits.

| Skill | Edition | Omitted | Changed or overlaid |
| --- | --- | --- | --- |
| westack | 0.3.1, generated | `tests/results/` receipts except `usage-trials.json` and `tests-final.json` (29 files) | `provenance/RIGHTS.md`, because this collection also publishes adopt-adapt. Every other published file is byte-identical to the 0.3.1 source commit (37feb98), and nothing is generated. Two records ship, `provenance/ARTIFACT_REVIEW.md` and `tests/results/tests-final.json`: both are clean on the leak patterns, and the skill's own rename guard lists both, so an edition without them would fail that guard. |
| Frankenmine | 0.1.2-portfolio.2, hand-made | Private source citations, transfer identifiers and local audit logs | One research note is a redacted public copy, with its expected published hash updated explicitly. Runtime contracts and authored fixtures remain. Version `-portfolio.2` renames the bundled example and its mentions to westack. |
| adopt-adapt | 3.0.0-grok-draft.r13-portfolio.1, hand-made | Private project and machine details | General recipient routing, context-supplied profiles and path rules replace them. The portable edition is versioned separately and retains proprietary ownership. |

westack (then called estack) 0.3.0 passed a blind not-worse check; this collection publishes it as westack 0.3.1, the same content under the new name. No later Frankenmine or adopt-adapt edition is published here.

Per-skill manifests identify the published bytes rather than claiming equality with the canonical sources. Skill snapshots and overlays preserve byte fidelity across Git checkout platforms. New validation results should be generated from the current checkout; private historical logs are not bundled as release evidence.

The helpers and synthetic fixtures were independently authored. Source references credit the research lineage and do not imply that third-party implementations are bundled, endorsed or comprehensively qualified. See the skills' research and provenance notes and the root [ownership notice](../NOTICE.md).

Full agent effectiveness, repeated comparative model trials, native host behavior and hostile-filesystem security remain outside the scope of a passing collection check.
