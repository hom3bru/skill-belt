# User profile

Personal values come from the local profile ~/.claude/skill-belt-profile.json if present; otherwise ask the user.

Resolve local paths from the profile when available, otherwise ask the user for the paths needed by the task. Placeholders represent local directories and must be resolved before file operations.

- `<research_root>` holds saved research reports, logs and sources.
- `<palette_home>` holds the local Palette library.
- `<plans_dir>` holds local plans.
- `<cp_home>` holds the local Carrier Pigeon mailbox and runtime.
- `<projects_root>` holds local project checkouts.
