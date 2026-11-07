# Pooled studies

One campaign per skill rarely holds enough cases to settle anything. A pooled study asks one question across several paired campaigns (do the skills, taken together, beat the bare host?) and it counts only if it was planned before any member ran. Pooling finished campaigns by hand is choosing the analysis after seeing the results: the instrument calls that significant but underpowered, with the effect likely overstated.

## When to register

Register every member campaign first (`campaign.py register`), then the pool, then run the members. `pool.py register` refuses a member whose ledger already holds a run or a started one, and names it.

`--post-hoc` registers such a pool anyway. The pool record, `verify`, every analysis and every summary line then say POST-HOC, and the pooled verdict stays descriptive: never `better`, `worse` or `equivalent`. Use it to describe a measurement, never to back a claim.

## Register

```text
python scripts/pool.py register POOL_DIR CAMPAIGN_DIR... --margin 0.2 --tie-rate 0.5 --seed 20261101 \
    --independence "why cases from different members share no state, time, rate limit, cache or instruction file"
```

`pool-prereg.json` is written once and holds:

| Field | Holds |
| --- | --- |
| `members` | per member: campaign id, folder, the sha256 of its `prereg.json`, its cases, the skills under test, runs at registration |
| `primary` | the comparison, `--treatment skill --baseline bare` by default; every member must have both arms and register that comparison |
| `unit`, `test` | the case (replicates averaged first, untouched cases out); an exact one-sided sign test on per-case outcomes and a seeded case-level bootstrap of the mean difference |
| `analysis` | alpha, power, margin, tie rate, seed, bootstrap resamples, the independence argument |
| `planned_cases`, `required_n`, `power_at_planned_n` | the members' cases summed, and the cases the margin needs at the declared tie rate |
| `secondary` | hard-fail rate, cost per run and turns per run, each better lower |
| `grades` | the sheet read from each member (`--grades`, default `grades/deterministic.json`) |

If `planned_cases` is below `required_n`, add members or cases before anything runs, as for a single campaign ([protocol](protocol.md), step 2).

## Analyse

Run, blind, grade and analyse every member with `campaign.py` as usual, then `python scripts/pool.py analyse POOL_DIR` (exit 0 valid, 1 invalid, 2 not-run). The result goes to `POOL_DIR/results/result-NNNN.json`.

The pool is **invalid** when `pool-prereg.json` was edited, a member's `prereg.json` bytes changed or the member no longer matches its own registration, a member run started before the pool was registered (that pool is post-hoc in fact), a member's newest result is not valid, the registered sheet is not one `campaign.py` analysed or the newest result used another grader's, or re-scoring a member does not reproduce its own wins, losses, ties and mean difference. It is **not-run** while a member is unanalysed.

Scoring follows `campaign.py` exactly: each member's runs are re-scored from its sealed mapping and sheet (a forbidden attempt is a hard fail; an unknown or grader-error criterion leaves the run out), each arm's replicates are averaged within a case, and each case enters the pool once, ties included. The pooled rows then go through the same sign test, bootstrap, power check and verdict rule as one campaign, so a one-member pool with that member's plan gives the member's own numbers. The pool adds three gates: the verdict stays descriptive when the pool or any member lacks an independence argument, and when the pool is post-hoc; it is inconclusive when a member's skill arm never engaged.

## Reading a pooled result

- `pooled`: the verdict (and `descriptive_verdict` when gated), n, wins, losses and ties, the sign test, `mean_difference` and `net_win_rate` with 90% and 95% intervals, `power_at_n`, `required_n`, `planned_cases` and `cases_dropped`.
- `per_skill`: each member's own n, wins, losses, ties, mean difference with its interval, p, power, verdict, engagement, hard fails, cost and turns per run. A pooled `better` says the skills help on average over this mix of cases, weighted by each member's case count; it says nothing about any one skill. Read that skill's own row.
- `secondary`: each metric per arm with `winner` (the lower value; `tie`; null when a figure is missing, which is N/A, never zero). Declared at registration, untested, and never a reason to change the verdict. "Beats the bare host on every metric" needs the primary `better` and every secondary won; report a lost one beside the verdict.
- `summary` holds plain lines for a report; `limits` names the case-count weighting, the unstratified bootstrap and each member's own limits.
