# Drop or slim, and the quality-defer bar

## The rule

A westack sub-skill earns its body only by beating the bare host on its own pre-registered cases. The primary comparison (skill versus bare) decides, and `result.drop_or_slim` applies the rule:

| Primary verdict | Decision |
| --- | --- |
| `better`, net win rate at or above the margin | **keep** |
| `better`, but below the margin | **slim** |
| `equivalent` | **slim**: no difference as large as the margin |
| `inconclusive` | **slim**, and measure again with at least `required_n` cases before investing more |
| `worse` | **drop**, or rebuild and measure again |
| anything but `worse`, `invalid` or `not-run`, with a golden case that failed its first attempt or was never checked | **failed-gate** (exit 3): a must-not-regress case is a gate no average offsets |
| `invalid`, `not-run`, or no independence argument | **none**: fix the measurement first |

Slim means a thin wrapper: the Minimum Core block plus a short fallback card that routes to the core workflow. Spend no further synthesis on a slimmed sub-skill until a new campaign shows it beats the bare host. The burden of proof is on the skill: "not shown to help" is slimmed, not kept on faith.

Report a comparison as a small table of dimensions (`criteria`): a criterion on which the skill is worse is a finding even when the net win rate is better, and a weak dimension is never averaged away.

Record each decision with the campaign id, the result file, the verdict, the effect and interval, n, and the cost.

## The quality-defer bar

The capability map's example bar was 20 pairs, and the candidate's 95% Wilson interval wholly above ours. That cannot be met (`python scripts/evalstats.py bar --own 14 --n 20`):

| Our pass rate (of 20) | Candidate needs | Margin |
| --- | --- | --- |
| 10 | 19 | +45 points |
| 13 | 20 | +35 points |
| 14 or more | impossible | none |

So it was a "never defer on quality" rule presented as a measurement. The replacement keeps the defer-map fields (`quality_criterion`: `suite`, `pairs`, `test`, `margin_points`) and gives them a test that can pass:

- **Test.** Paired, on the same cases: the exact sign test on discordant pairs (for pass/fail outcomes this is the exact McNemar test), with a case-level bootstrap interval. The candidate qualifies when that comparison is `better` with a net win rate at or above the margin, which is the same bar a westack sub-skill must clear against the bare host.
- **Pairs chosen from the margin.** `python scripts/evalstats.py quality --pairs 20 --margin-points 15` fails: 20 pairs have about 15% power for a 15-point margin. Pairs needed for 80% power at alpha 0.05, one-sided (`evalstats.py plan`):

| Margin | Tie rate 0.3 | Tie rate 0.5 | Tie rate 0.7 |
| --- | --- | --- | --- |
| 10 points | 450 | 326 | 199 |
| 15 points | 203 | 148 | 89 |
| 20 points | 116 | 83 | 50 |
| 30 points | 51 | 37 | 21 |

- **Validity.** The evidence must name the candidate commit equal to the installed one and must not have expired, as `defer.md` already requires. A changed candidate makes it stale.

Integration note for the core (not done in this package): `defer.md` and the defer-map validation should call `evalstats.check_quality_criterion` so an entry whose pairs cannot detect its margin is rejected.
