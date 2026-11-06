# Changelog

## Public release preparation, unreleased

Session discovery uses the nearest `.claude` or `.codex` directory to label logs, so an ancestor cache name cannot override the host directory. A regression check covers nested host paths.

## 1.0.0-alpha.0 (first build), unreleased

The first westack-retro: a retrospective from the record. Repository, compare and global modes; local-midnight windows; a stale-window guard that stops instead of reporting a quiet week; metrics from one documented `git log` saved by the agent (commits apart from merges, lines, the test ratio, weighted commits, active days, 45-minute sessions split deep, medium and micro, commit types and the fix ratio, commit sizes, hours, focus, hotspots, the biggest commit, contributors, AI co-authors counted apart, streaks); features counted only from the changelog or merged pull requests; a comparison with the last saved retro; and a global mode that finds repositories from local Claude Code and Codex session logs. `scripts/retro.py` parses saved output and runs no command, like every westack helper. Ideas from gstack's retro at the mirror pin, in westack's words; its gbrain context load, factory scorecard, review-bot signal, shortcut-debt ledger, skill-usage log and eureka log are left out. `tests/test_retro.py`: 12 tests; a copy with a two-hour session gap fails the session test.
