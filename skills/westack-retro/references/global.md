# The global retro

A week across every repository the user worked in, found from local agent session logs.

## Find the repositories

`python scripts/retro.py discover <root> [<root> ...] --since <date>` reads session logs (JSONL files with a `cwd` field) changed since the date and lists each working folder with its session count, last activity and the tools seen. Roots on this kind of machine: `~/.claude/projects` (Claude Code) and `~/.codex/sessions` (Codex). Reading them is reading the user's own conversations: say which roots you read, and keep everything on the machine.

## For each repository

Skip folders that are not git repositories or no longer exist. For each one, save the documented `git log` ([run](run.md)) for the window and run `retro.py metrics`. A repository with sessions but no commits in the window is exploration, not shipping; list it apart.

## The narrative

- **Overview:** repositories touched, commits, features shipped and the test ratio per repository.
- **Streak across all of them:** consecutive days with a commit anywhere.
- **Context switching:** how many repositories had commits on the same day, and on how many days.
- **Tools:** sessions per tool and per repository, from the discovery output.
- **Ship of the week** across all repositories, three cross-project observations and three habits to try, each tied to a number.

Save the snapshot only with the user's yes, in the folder they name.
