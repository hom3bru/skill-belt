# Reading results

`campaign.py analyse` writes `results/result-NNNN.json`. Read the campaign verdict first, then each comparison.

## Campaign verdict

| Verdict | Means |
| --- | --- |
| `valid` | Every gate held. Read the comparisons (or the routing matrix). |
| `invalid` | The instrument refused. The reason names the gate; no comparison in this result counts. |
| `not-run` | Nothing was measured: zero gradable runs, or no grades yet. |

Invalid reasons and what to do:

| Reason starts with | Cause | Do |
| --- | --- | --- |
| not pre-registered / pre-registration mismatch | the design, a fixture or the skill changed after registration | start a new campaign folder; report the old one |
| the ledger holds runs made under a different pre-registration / hash chain broken | outputs predate the registration, or the ledger was edited | the same |
| outputs were never blinded / the blind leaked | grading would not be blind, or a sentinel reached a host | fix the cause (a prompt naming the skill, a missing redaction) in a new campaign |
| grades rejected / not the registered grader | the builder graded, an item is missing, a model grader quoted no evidence for a credit or exposed a tool, or a different grader was used | grade again with the registered, separate grader |
| grader failed calibration | the grader passed a known-bad canary, caught one for a reason other than the criterion it targets, failed a known-good one (an alternative-valid answer included), or scored everything alike | fix the grader or its checks, in a new campaign |
| used a skill copy that differs | the skill changed during the campaign | a new campaign |
| the arms ran under a different run command or environment | a flag, model, timeout or variable reached one arm only, so the gap is not the skill's | a new campaign |
| the broken-copy control was judged better | the instrument can be fooled; counts a control that would have been better but for the power gate at the observed tie rate (`withheld_verdict`) | fix the rubric or grader before trusting any result |

## Comparison verdicts

| Verdict | Needs |
| --- | --- |
| `better` | one-sided exact sign test p at or below alpha, the case-level 90% interval of the net win rate above zero, power at least the target at the declared tie rate and, when the observed tie rate differs from it in either direction, at the observed rate too, and two or more cases |
| `worse` | the same test and interval the other way (reported even when underpowered at the declared rate, with a warning that the harm is likely overstated; not when power at a differing observed tie rate is below the target) |
| `equivalent` | powered (at the observed tie rate too, when it differs), not significant, and the 90% interval inside plus or minus the margin |
| `inconclusive` | anything else; the reasons say why (underpowered, not significant, a single case) and how many cases would settle it. Power at a fixed margin changes with the tie rate, so when it is below the target at a differing observed rate, a result that would be better, worse or equivalent is inconclusive with one reason naming both rates and both powers, and `withheld_verdict` keeps what it would have been. Without an independence argument, better, worse and equivalent land here, marked `descriptive` |
| `invalid` | more cases lost than the registered `max_dropped`; the reason counts them |
| `not-run` | no case had a gradable run in both arms |

Each comparison also gives: `n_cases`, wins, losses and ties, the sign test, `net_win_rate` and `mean_difference` (each with an estimate, `ci90` and `ci95` from a seeded case-level bootstrap), `power_at_n`, `required_n`, `cases_dropped`, `engagement`, `usable_n`, `aggregation`, `cost`, `untouched` and `limits`. Report the effect, its interval, n and the limits together. Never round "inconclusive" up to "probably better".

**Engagement.** For each arm that installs a skill, `engagement` counts its gradable runs, those whose ledger line records the host's skill list, those where the host loaded the skill and those where it also used it (a Skill call, or the arm's slash prefix naming a listed skill). An arm with zero engaged runs measured two bare runs: the comparison is `inconclusive`, `not_engaged` names the arm, `drop_or_slim` decides nothing, and the gap is never read as no effect; fix the install or invocation and run again. Report engagement beside every skill-versus-bare difference; partial engagement is a limit, and a run with no record, or `unobservable`, is unknown, not none.

**Before reading any rate,** read `criteria`, which tabulates each criterion across the arms (runs, pass rate, mean) with flags: `always-pass` (full marks everywhere, so it cannot separate the arms), `always-fail` (may be broken or unreachable) and `flaky` (the same case and arm disagreed across replicates). Fix or drop those criteria in a new campaign before leaning on a rate that uses them. `grader_gaps` is the grader's list of wrong outputs that would still pass and behaviours no criterion covers; `excluded_unknown` and `excluded_grader_error` list runs a grader marked unknown or errored on a criterion, which left the comparison rather than counting as failures. `untouched` is the noise floor: read it before any p-value. `canary_labelling` builder means weak calibration.

**Outcomes.** `outcomes` types every run (passed, task-failed, timeout, cheat; unusable: infrastructure-error, grader-error, not-checked) and gives the usable n; print it beside every rate. A timeout is scored on what it produced and typed timeout only if that failed.

**Aggregation.** Single-run success is the headline; `aggregation` adds all-trials and any-trial rates as secondary views. A case that passes some replicates is flaky; a lucky pass never upgrades a claim.

A `truncated` stop leaves planned runs unmade: those cases leave the comparison, never read as misses. Before trusting a score, read the failed transcripts and report "transcripts read: k of n; grader defects: ..."; the rest are not examined. For a case with a planted defect, record the stage that lost each miss: never raised, dropped at validation, cut by a cap or a dedup, or unparseable output. When transcripts show many turns on repeated mechanical work (lookups, greps, parsing), write a deterministic helper that does it in one call (P-6, `craft.md`), and record the turn counts before and after with the same result.

The campaign-level `limits` and `confounds` belong in the report too: an unregistered grader, several graders analysed, host-noise denials, a budget stop, the shared user instruction file, the fact that outputs can reveal their arm through behaviour, and that canaries carry no artefacts.

## Routing results

- `matrix.splits.dev` and `matrix.splits.held-out`: `n`, `correct`, `accuracy` with a Wilson interval, the `confusion` (expected to decided counts; an answer off the skill list goes in `UNRECOGNISED`, never a misroute pair), `false_triggers` (should-not requests that triggered a skill) and `misses` (should-trigger requests that triggered nothing).
- `pairs`: for each sibling pair with any misroute, both directions with k, n, rate and Wilson interval. `flag` is true when either direction reaches `misroute_rule` (10%): merge the pair or make their triggers distinct, then measure again. A flag resting on fewer than ten cases says so.
- `matrix.splits.*.explicit`: a prompt that names a skill outright (`/name`, `$name`) is the user's call, not the model's choice. The host expands a typed command without a Skill call, so the run counts as routed to that skill when the stream shows it loaded: a Skill call, a read of its SKILL.md, or a leading `/name` that the host's own skill list names, with a model call (the reply text alone is never evidence; the ledger's `explicit` says which). These cases leave `n`, `accuracy` and the misroute rates and are tallied here: `n`, `loaded` with its interval, `correct`, `manual_only` and `by_skill`. A manual-only skill is reached only this way, so no model-chosen accuracy exists for it to inflate.
- `AMBIGUOUS:a|b` (proxy only) is a tie at the top and counts as a misroute to each.
- `lint.shared_triggers` lists pairs whose descriptions overlap before any run.
- `backend.label`: a proxy result describes description overlap, never host behaviour. A host result measures routing from front matter only, one request per run, with the confounds listed. `backend.routing_tools` and a `routing tools:` confound name the tools the host had (`skill-only` or `read-only`); compare results only within one setting.
- `heldout.clean` false means the held-out cases were already scored against another description version and now count as dev.

## Promoting a change

Write the rule into the campaign's `hypothesis` before registration (it is hashed): a threshold per metric you will weigh, and a harm cap (hard-failed items, forbidden actions, new failures) that no gain elsewhere offsets. With more than one host, each host is its own comparison and one decision covers them all: release only if none is `worse` and at least one is `better`; a host that got worse is a harm no better host offsets, and an inconclusive host is reported as unproven. A hard-failed item only scores 0 inside the win rate, so read hard fails per arm from the grades. Among changes that clear every threshold, prefer the best gain per cost (net win rate over `cost`), not the largest gain.

A claim across several campaigns (the stack beats the bare host) comes only from a pool registered before any member ran: [pooled studies](pooled.md). A pool registered later says POST-HOC on every output and its verdict stays descriptive.

## Cost

`cost` gives dollars charged (unknown costs at the cap, for the budget), `measured_usd` (a floor; see `complete`), tokens and runs; `unfinished` lists crashed attempts. Report cost and time only as measured: a missing figure is N/A, never zero or free, and `cost.difference_usd` is N/A when either arm has a gap. For an API-backed host, a local token-counting proxy between the agent and the provider, counting per call, is firmer than the agent's own report; say which hosts are counted that way (none yet: every figure comes from the host stream). Report it beside the verdict.

Read context size from usage the same way. A turn's context is its last call's input, never the sum of every call's input (three calls of about 40k input each read as about 40k, not 120k), and repeated usage reports for one response merge by their maximum. The room a prompt has is the smaller of the input limit and the context window, which also holds the reply.
