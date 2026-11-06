# Index governance

## Trust tiers

Each repository has a tier in the user's policy file, `%APPDATA%\westack\index-policy.json` (or `$WESTACK_CONFIG_DIR`, or `~/.config/westack`), keyed by its normalised remote URL (protocol, user and `.git` stripped, `host:path` as `host/path`, lower case) or, with no remote, its absolute path in lower case.

| Tier | build, update | search and the graph | guidance ping |
| --- | --- | --- | --- |
| read-write | yes | yes | yes |
| unset (no entry) | yes | yes | yes |
| read-only | refused | yes | refused |
| deny | refused | refused | refused |

`codeindex.py` enforces the tier itself and exits 77 on a refusal; `doctor` reports it. `policy --repo R` shows the tier; `policy --repo R --set TIER` writes it. Setting a tier is persistent configuration: ask the user first, name the tier and the repository key, and never lower a tier the user set.

A policy file that is not valid JSON in the `westack-index-policy-1` format, or names an unknown tier, is moved aside as `index-policy.json.corrupt-<time>`. While a moved-aside file exists and no new policy has been written, every repository is read-only: a broken file never opens access. `doctor` lists the moved-aside files; the user restores one or writes a new policy.

## The search-guidance block

`guidance --repo R [--file AGENTS.md|CLAUDE.md]` checks that the index answers: it indexes a throwaway page in the index (never in the repository), searches for it with up to three tries, deletes it and confirms it is gone. Then:

- all three steps pass: the block between `<!-- westack:index-guidance:start -->` and `<!-- westack:index-guidance:end -->` is written, or left alone when it already matches;
- any step fails (or the tier refuses the ping): the block is removed if present.

Without `--write` it only reports what it would do. `--write` edits an instruction file: run it only under the user's grant to edit AGENTS.md or CLAUDE.md, and say so in the report. It is the one command that writes inside the repository, and only between those markers. Run it again after the index changes state, so the block never claims a search that does not work.

Provenance: gstack's gbrain repository policy and sync-gbrain guidance block at the mirror pin (absorption.json `gstack.gbrain.trust-policy`, `gstack.gbrain.guidance-block`), and gbrain's trust and managed-block ideas, in westack's words. gstack never enforced its read-only tier; westack does.
