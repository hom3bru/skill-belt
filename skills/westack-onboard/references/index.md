# The repository index

`scripts/codeindex.py` is standard-library Python. It runs no command: it reads the repository's files and its `.git` folder (HEAD, refs, the index file, config) and writes only its own cache.

## Commands

| Command | Does | Exit |
| --- | --- | --- |
| `build --repo R` | a fresh index of every tracked file | 0, 1 failures held the watermark, 75 locked |
| `update --repo R [--skip-failed]` | re-indexes what changed: size and time first, then content hash; renames by matching content; deletions kept as soft deletes | same |
| `search --repo R [--budget conservative\|balanced] [--limit N] words` | ranked files with their best chunks, inside the token budget | 0, 69 no index |
| `show --repo R path` | a file's chunks (symbol, kind, lines) and backlinks | 0, 69 |
| `doctor --repo R` | OK, WARN or ERR: search engine, chunker version, watermark against HEAD, failures, lock, counts | 0, 1 on ERR |

| `def --repo R [--in PATH] name` | where a symbol is defined (`Class.method` or a bare name) | 0 |
| `callers --repo R [--in PATH] name` | chunks that call it, each linked "same file", "names the module" or "by name"; with `--in`, only the first two | 0 |
| `callees --repo R [--in PATH] name` | what it calls: `obj.m(...)` resolves only to methods, `f(...)` only to functions and classes, a same-file definition wins; the rest listed as unresolved | 0 |
| `refs --repo R [--in PATH] name` | every chunk that mentions it as a whole word, with the first such line | 0 |
| `context --repo R [--in PATH] [--budget ...] name` | its definition, then its callees, then its callers, inside the token budget; what did not fit is listed | 0 |
| `delta --repo R --since COMMIT` | files added, modified, renamed and deleted since the last clean run at that commit (seven or more characters); re-chunking is not a change | 0, 2 not in this index's log |

The graph is by name, from Python's `ast` and from call patterns in other languages: a lead to read, never proof. A build starts the change log afresh.

`--db FILE` overrides the location; `--files LIST` takes a saved `git ls-files` output when the `.git` index cannot be read (index version 4) or there is no `.git` folder (without either, the folder is walked, skipping build and dependency folders).

## Storage

`%LOCALAPPDATA%\westack\index\<name>.sqlite` (or `$WESTACK_INDEX_DIR`, or `~/.cache/westack/index`), named from the normalised remote URL (protocol, user and `.git` stripped, `host:path` as `host/path`, lowercase) or the absolute path when there is no remote. Beside it: `.lock` and `.state.json`. Deleting the three files resets the index; nothing else depends on them.

## What is indexed

Tracked files (as `git ls-files` lists them, from the working tree's content), except files over 5 MB, binary files and files that are not UTF-8: those are listed as skipped. Untracked files are not indexed.

Chunks: Python by `ast` (functions, classes, methods, and the module code between them); JavaScript, TypeScript, Go, Rust, Ruby, C-like languages and shell scripts by definition patterns; Markdown by headings (fenced code ignored); anything else in 300-word windows overlapping by 50. A chunk over about 2,000 tokens is split. Markdown links between files are recorded as backlinks.

## Ranking

Two arms, fused by reciprocal rank (k 60): chunks by BM25 with the file title (path and first heading) weighted 4, the symbol 3 and the body 1, and files by their title alone. Then boosts: every query word in the title ×1.25, changed within 30 days of the newest file ×1.1, and ×1.02 per backlinking file up to 10. Results carry up to three chunks each, until the budget (conservative 4,000 tokens, balanced 12,000) runs out. Without FTS5 the same weights run in pure-Python BM25. The numbers live in [index.json](index.json).

## Sync rules

- The watermark (the commit the index reflects) moves only when a run ends with no unacknowledged failures. A file that fails is recorded with its reason; the rest are still indexed. `--skip-failed` acknowledges the current failures so the watermark can move.
- A chunker version change re-walks every file on the next update.
- One run at a time: a lock beside the database, taken over when older than five minutes.
- The state file is written to a temporary file and moved into place, so a reader never sees half of it.

Provenance: gbrain's schema, search, chunkers, sync and doctor, and gstack's gbrain sync orchestrator, at the mirror pins (absorption.json `gbrain.*` and `gstack.gbrain.sync-orchestrator`), in westack's words.
