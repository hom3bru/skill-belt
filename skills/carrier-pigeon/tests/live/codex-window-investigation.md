# Part A: Codex window startup investigation

Date: 2026-11-02. Branch at start: `codex/cp-0.16`. Investigation only; no runtime/configuration changes or commits.

## Finding and local evidence

- Read root `AGENTS.md`. Inspected `host/carrier-pigeon-host.mjs` window helpers/adapter and window binding lookup, the existing host window tests, `tests/live/codex-window-followup.mjs`, and its prior qualification in `tests/live/README.md`.
- Configured executable was read from the installed listener configuration, rather than using the npm wrapper on PATH. Direct `--version` returned `codex-cli 0.166.0-alpha.5.1`.
- Direct `--no-daemon --help` exited 0. It describes `--no-daemon` as running without the shared background server and supports `-c, --config <key=value>` as an invocation override. Help does not advertise a model-refresh disable flag.
- Read-only byte search of that executable found `model_catalog_json`, `model_catalog_url`, `models_cache.json`, and `app-server\\src\\models_refresh_worker.rs`. Strings alone establish presence, not control flow.
- Read-only SQLite queries against local `logs_2.sqlite` found `codex_models_manager::manager`, `models-manager\\src\\manager.rs:551`: `list_models{refresh_strategy=online}: failed to refresh available models: request timed out` at 2026-11-02 00:50:18, 00:53:15, 00:54:54, 04:35:58 and 06:05:37 UTC. These rows are not individually correlated to harness process IDs; they corroborate the failure class, not a newly reproduced window failure.
- Existing live-check documentation records two startup timeouts and a model-list retry about 4.5 minutes later. The harness itself notes this delay before finding the rollout. A launch receipt only establishes terminal launch; the adapter cannot find the new conversation until Codex writes its rollout. Network refresh before that point explains the observed apparent hang. The underlying network/transport timeout cause remains undiagnosed.

## Supported process option and source evidence

No local Rust checkout was located in the targeted searches. Source evidence below is upstream source at the exact reported version tag, not a claim of a locally reproduced build or binary/source equivalence.

- [Tagged config loader](https://github.com/openai/codex/blob/rust-v0.166.0-alpha.5.1/codex-rs/core/src/config/mod.rs#L2086): `load_catalog_json` reads `model_catalog_json` as `ModelsResponse` and rejects an empty model list.
- [Tagged provider factory](https://github.com/openai/codex/blob/rust-v0.166.0-alpha.5.1/codex-rs/model-provider/src/provider.rs#L498): a supplied catalog selects `StaticModelsManager` before constructing a remote catalog endpoint.
- [Tagged static manager](https://github.com/openai/codex/blob/rust-v0.166.0-alpha.5.1/codex-rs/models-manager/src/manager.rs#L814): returns the supplied models regardless of refresh strategy; ETag refresh is also inert at line 840. This bypasses model catalog network refresh, not model inference or all startup networking.

The supported launch argument array is:

```js
['--no-daemon', '-c', "model_catalog_json='C:/path/catalog.json'"]
```

Use an existing, valid, nonempty catalog with metadata for the intended model. The TOML literal string avoids native PowerShell loss of embedded double quotes and permits spaces; use forward slashes and a path without apostrophes for this exact form. This is a process override, not a global settings edit. A static catalog freezes metadata and can become stale; it does not establish model availability or authentication. No catalog contents or private identity metadata were copied into this repository.

The existing `codexWindow.args` extension already passes these arguments before `-C`; host main needs no change. The live harness hardcodes `['--no-daemon']` and does not consume configured window arguments, so changing only private listener configuration would not exercise this option in that harness. Leave any harness invocation change and real launch to an approved follow-up.

## Regression and verification limits

Added required host-suite regressions: custom-terminal argument preservation and real hidden PowerShell invocation of a fake Node executable, covering a TOML catalog path with spaces. It verifies transport through the current window launcher, not Codex catalog loading or startup recovery. Run with `node skills/carrier-pigeon/host/carrier-pigeon-host.test.mjs` from the repository root.

Executed that focused command: 2 passed, 0 failed, 0 skipped (exit 0). PowerShell emitted its first-use module progress output; the captured native argument JSON matched exactly. Both new files were checked for LF-only endings. No existing file was edited.

No live harness, interactive Codex launch, model call, install, settings edit, listener restart, push or commit was performed. Full suite is being run by the lead Codex session; no full-suite result is claimed here. Remaining live check, only after Matt approval: launch the same binary with a vetted static catalog, confirm the first rollout/frame appears without catalog-refresh timeout, then run the two-turn window follow-up harness with the same arguments and retain its report. Authentication, hooks and other startup networking may still delay startup.
