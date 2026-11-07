# Severity

Only a confirmed finding has a severity. It is read from one table and never argued afterwards: to change it, change an input with a stated reason, never the output. `secaudit.py check` refuses a severity that is not the table's.

## Inputs

**Impact**, from what the result showed:

- `severe`: code execution, authentication bypass, access across tenants, credential theft or loss of bulk data, on the shipped path;
- `high`: other users' data read or changed, or privilege gained inside one tenant;
- `moderate`: limited data or one user's actions affected, or one feature made unavailable;
- `low`: information that helps a later attack, or a narrow misuse;
- `minimal`: a weakness with no direct effect yet shown.

**Likelihood**, from how reachable it is:

- `demonstrated`: reproduced on the real path, with a receipt;
- `likely`: the trace is complete and the principal can reach it without special conditions;
- `possible`: reachable under conditions that occur in a supported configuration;
- `unlikely`: needs conditions that are rare in practice;
- `unknown`: reachability not established.

## The table

| Impact | demonstrated | likely | possible | unlikely | unknown |
| --- | --- | --- | --- | --- | --- |
| severe | critical | critical | high | medium | medium |
| high | high | high | medium | low | low |
| moderate | medium | medium | medium | low | low |
| low | low | low | low | low | low |
| minimal | low | low | low | low | low |

## Rules

- **Critical needs named evidence.** Set `critical_evidence` to one of `remote-code-execution`, `authentication-bypass`, `cross-tenant-access`, `credential-theft` or `bulk-data-loss`, backed by the result.
- **Capped at what was shown.** `impact` may not exceed `demonstrated_impact`, the impact the result itself showed. The report's highest severity is the highest confirmed one, so it never rises above demonstrated impact.
- **Reach.** Self-only and privileged-only paths drop out unless they gain privilege ([assess](assess.md)). A real low-impact finding is rated low, not discarded.
- **Confidence is separate.** `confidence` (low, medium or high) orders triage; it never moves a cell.
- **Outside severities stay outside.** A scanner's or vendor's label is kept verbatim in `scanner_severity`; it is never this severity and never ranks findings.
- **One scale.** In a recorded task and in westack-review, critical, high, medium and low are P0, P1, P2 and P3 (review `rules.md`).

## Prompt injection

Judge it by what the harness permits as a result, not by what the model could choose to do. Injected text that only changes what the model writes is a hardening note. It is a finding when the harness, acting on it, releases a credential, skips an approval or a decision, calls a tool outside the grant or sends data out; name that effect in `harness_effect` (`credential-released`, `approval-skipped`, `decision-skipped`, `tool-call-outside-grant`, `data-sent`). Use a rule family starting `prompt-injection` so `check` applies this test.
