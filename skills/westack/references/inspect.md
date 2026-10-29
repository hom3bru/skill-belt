# Inspect

Read applicable repository instructions before edits. Inspect the relevant implementation, callers, interfaces, configuration and tests. Record the actual revision and patch fingerprint (the recipe in SKILL.md) and dirty-state limitations; `validate.py fingerprint --repo <repo> --root <evidence-root>` prints both and the Git root it used. Observe the tests and configuration your evidence depends on, even where you may not edit, with `init --observe-path`. Hashes are of raw bytes, so a checkout that rewrites line endings changes the patch. Preserve unrelated work. Isolation requirements come from the host, user and repository; an unavailable required worktree blocks dependent writes, not safe reads.

For unfamiliar APIs, identify the project's installed/pinned version and consult current primary documentation. Record target version, observed documentation version, original URL, retrieved date and revalidation deadline. A cached page for another version cannot establish compatibility. Write target and observed versions at the same granularity (both `1.x`, or both exact): the checker compares them as exact strings. No documentation service needs installing.

For source claims distinguish directly inspected implementation, maintainer documentation, supplied summary and index-only records. Popularity measures attention at a date, not efficacy. Aliases and ports are not extra capabilities. Keep hypotheses distinct from observed facts.

On resume, re-inspect changed files (a failed `task --repo` lists them when a manifest is stored) and affected callers. If documentation or a lesson expires or targets another revision, revalidate before relying on it. Unknown facts stay unknown; inspect the smallest source that could resolve them.

