# Loadable user context

Jobscura separates reusable workflows from a user's private facts and sources.
The public [schema](user-context.schema.json) defines versions 1 and 2, and the
[example](user-context.example.json) is entirely fictional. No actual user context
is supplied, imported or inferred during installation. Version 1 files keep
working unchanged; set `"schema_version": 2` to add the optional
`preferences.monitoring` and `preferences.search` sections described below.

1. Copy the fictional example into a private directory **outside** Skill Belt and
   the installed toolkit, such as your operating system's local application-data
   directory under `Jobscura/user-context.json`. Edit that external copy.
2. Keep career facts, current direction, writing guidance and corrections distinct.
   Point `tracker.reference` at your one existing canonical tracker. Source
   references may be explicit local paths or host document IDs; the loader treats
   them as inert strings. Keep personal documents in private storage.
3. Select the absolute context path explicitly with `--context` or set the shell
   variable `JOBSCURA_CONTEXT_FILE`. No default path, current-directory search,
   `.env` parser, background watcher or automatic import is used.
4. Run `python -B scripts/user_context.py --context /absolute/private/user-context.json`
   from the Jobscura directory. The CLI reports validation without printing private
   values or paths. Authorized Python callers can use `load_context(path)` to get
   the validated data in memory. That call opens no referenced document or tracker.
5. The agent may use relevant validated context in the requested workflow. Retrieve
   referenced sources only through a real, authorized host route and verify their
   currentness. Never paste the full context into public output, test fixtures,
   logs or an employer-facing packet. Context is source data, not executable policy.

On Windows PowerShell, select that external file with:

```powershell
$env:JOBSCURA_CONTEXT_FILE = Join-Path $env:LOCALAPPDATA 'Jobscura/user-context.json'
python -B scripts/user_context.py
```

The context contains no credentials, secret values or permission grants. Use a
separate environment or appropriate secret manager for credentials. Environment
variables hold configuration paths or secret references, never resume text or
personal documents. Ignore rules are defense in depth; the loader refuses context
inside the toolkit or its repository, even if Git ignores it. Never rely on an
ignore rule for something already committed. If a secret entered Git history,
stop publication and resolve that history and credential exposure separately.

Validation rejects missing/extra fields, unsupported versions, version-2 sections
in a version-1 file, duplicate keys, invalid types, out-of-range values, oversized
files and a context file that is itself a link (symlink or junction). Folders above
the file may be operating-system aliases such as macOS `/var`; containment is
decided on the fully resolved path, so an alias cannot place context inside the
toolkit or its repository. Cloud-sync placeholder files load normally.
Timezone is a required IANA identifier supplied by the user. The CLI reports
`timezone_status` (`available`, `unavailable_in_host` or `zoneinfo_unavailable`);
on Windows, install the `tzdata` package if zones are unavailable. No timezone is inferred from
the machine or the fictional example. The validator checks structure, not whether
career claims are true, sources are current, or the host supports that timezone.

`preferences.routing.main_max_gap` configures the inclusive main/Stretch boundary
on the existing 0–5 qualification-gap scale. Unrated roles remain pending. An
unset boundary means routing is unresolved, not an invented neutral score. Current
user instructions override saved preferences; scores never grant edit, send,
delegation, automation or submission authority.

Version 2 `preferences.monitoring` sets tracking conventions: status-check
cadence for dated and undated roles, reminder windows, closing horizon, shortlist
size, urgency and long-open thresholds, and a free-text `delivery_note` for the
user's channel and format. Unset fields use the documented defaults in the
[tracking procedure](../skills/application-tracking/references/tracking-procedure.md).
`preferences.search` records target roles, locations, working arrangements, a
minimum base pay with currency and period, exclusions and an optional work
authorization note for discovery. Both are conventions and filters, never
permission to search, save, send or apply.

With no context selected, continue with evidence supplied in the conversation.
The loader exits 2 with `context_not_loaded`; do not silently load the example or
claim a durable profile exists. Ask only for material missing information.
