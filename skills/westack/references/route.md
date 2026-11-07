# Route

The core workflow. The router uses it when the chosen `westack-*` sub-skill is not installed. `/westack verify` and `/westack build` have their own core references ([verify](verify.md), [build](build.md)) for when `westack-verify` or `westack-build` is not installed; an installed one owns its command.

"Design review" is two requests. Of a plan, spec, RFC or other document it is `review` in document mode; of a built UI (a page, component or screenshot) it is `design`. Ask one question only when the artifact is unclear.

Preserve explicit intent: question, investigate, plan, design, build, repair, review, verify or finish. Plan stops at an agreed plan without edits; verify checks existing work against its acceptance conditions without changing it. An explicit mode is a routing preference, not permission for additional actions. westack runs only when invoked explicitly (`/westack` on Claude Code and Cursor; the skill picker elsewhere).

Choose tiny when the outcome and affected behavior are clear and local; bounded for a coherent feature with dependencies; cross-cutting when multiple interfaces, risks or unresolved decisions matter. These are judgments, not scores.

Tiny: inspect relevant rules/code and callers, act within existing scope, run a useful check, finish. Use [Frame](frame.md) only for a decision-changing ambiguity. Bounded/cross-cutting: recover existing decisions, inspect, [plan](plan.md) dependencies and verification, build authorized units, review as warranted, verify and finish. A read-only investigation can deliver source-audited findings without implementation.

Do not commandeer unrelated conversation or turn every factual question into a project. Requests about westack are not automatically requests to install it. Do not load all modules or donor packs for completeness. See `tests/trigger-cases.json` in the repository for intended activation examples; these are evaluation inputs, not measured model results.

