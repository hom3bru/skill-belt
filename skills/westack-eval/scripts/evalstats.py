"""westack-eval statistics: exact sign test, Wilson intervals, power of the paired sign test, seeded
case-level bootstrap intervals and the paired verdict.

  python evalstats.py plan --margin 0.15 --tie-rate 0.5 [--alpha 0.05] [--power 0.8] [--n 20]
  python evalstats.py sign --wins 3 --losses 0
  python evalstats.py bar --own 14 --n 20
  python evalstats.py quality --pairs 20 --margin-points 15 [--tie-rate 0.5]

The unit is the case. Each case yields one paired difference (treatment minus baseline, replicates
averaged first). The test is a one-sided exact sign test on wins and losses (ties dropped). The margin is
on the net-win-rate scale ((wins - losses) / cases), which for pass/fail scores equals the pass-rate
difference. "better" needs significance, a case-level interval above zero and a design powered to detect
the margin at the declared tie rate; one case never qualifies. Power depends on the tie rate, so when the
observed rate differs from the declared one (either way) and power there is below the target, none of
better, worse or equivalent is returned. Standard library only; runs nothing.
"""
import argparse
import json
import math
import random
import sys

FORMAT = "westack-eval-stats-1"
EPS = 1e-9
LIMIT = 2000
Z95 = 1.959963984540054


def sign_test(wins, losses):
    """Exact sign test (Bin(wins + losses, 0.5)): one-sided p-values both ways and two-sided."""
    n = wins + losses

    def upper(k):  # P(X >= k), exact
        if k <= 0:
            return 1.0
        if k > n:
            return 0.0
        return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n

    greater = upper(wins)
    less = 1.0 - upper(wins + 1)
    return {"wins": wins, "losses": losses, "n": n, "p_greater": greater, "p_less": less,
            "p_two_sided": min(1.0, 2 * min(greater, less))}


def wilson(k, n, z=Z95):
    """Wilson score interval for k successes in n trials; (0, 1) when n is 0."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, centre - half), min(1.0, centre + half))


def _pmf(n, p):
    """Binomial probabilities for 0..n, computed in log space."""
    if p <= 0:
        return [1.0] + [0.0] * n
    if p >= 1:
        return [0.0] * n + [1.0]
    lp, lq, base = math.log(p), math.log1p(-p), math.lgamma(n + 1)
    return [math.exp(base - math.lgamma(k + 1) - math.lgamma(n - k + 1) + k * lp + (n - k) * lq)
            for k in range(n + 1)]


class _Rejection:
    """table[d] = P(Bin(d, q) >= k(d)): the chance the sign test rejects given d discordant cases, where
    k(d) is the smallest win count whose one-sided p-value is at most alpha. Extended incrementally."""

    def __init__(self, q, alpha):
        self.q, self.alpha = q, alpha
        self.half, self.alt, self.table = [1.0], [1.0], [0.0]

    @staticmethod
    def _step(pmf, p):
        out = [0.0] * (len(pmf) + 1)
        for i, value in enumerate(pmf):
            out[i] += value * (1 - p)
            out[i + 1] += value * p
        return out

    def upto(self, n):
        while len(self.table) <= n:
            self.half = self._step(self.half, 0.5)
            self.alt = self._step(self.alt, self.q)
            d, tail, critical = len(self.table), 0.0, None
            for w in range(d, -1, -1):
                tail += self.half[w]
                if tail > self.alpha:
                    break
                critical = w
            self.table.append(sum(self.alt[critical:]) if critical is not None else 0.0)
        return self.table


_TABLES = {}


def _check_margin(margin, tie_rate):
    if not 0 < margin <= 1:
        raise ValueError("margin must be in (0, 1]")
    if not 0 <= tie_rate < 1:
        raise ValueError("tie_rate must be in [0, 1)")
    if margin > 1 - tie_rate + EPS:
        raise ValueError("margin %.3f exceeds 1 - tie_rate (%.3f): no paired design can show it"
                         % (margin, 1 - tie_rate))


def power_sign_test(n, margin, tie_rate, alpha=0.05):
    """Chance that the one-sided sign test at alpha rejects with n cases when the true net win rate is
    `margin` and a share `tie_rate` of cases tie."""
    _check_margin(margin, tie_rate)
    discordant = 1 - tie_rate
    q = min(1.0, (discordant + margin) / (2 * discordant))
    table = _TABLES.setdefault((round(q, 12), alpha), _Rejection(q, alpha)).upto(n)
    return sum(p * table[d] for d, p in enumerate(_pmf(n, discordant)))


def required_n(margin, tie_rate, alpha=0.05, power=0.8, limit=LIMIT):
    """Smallest number of cases whose power reaches `power`, or None within `limit`."""
    _check_margin(margin, tie_rate)
    for n in range(1, limit + 1):
        if power_sign_test(n, margin, tie_rate, alpha) >= power:
            return n
    return None


def bootstrap(rows, seed, resamples, levels=(0.90, 0.95)):
    """Percentile intervals of the mean of each column of `rows` (one row per case), resampling cases."""
    n, columns = len(rows), len(rows[0])
    rng = random.Random(seed)
    means = [[] for _ in range(columns)]
    for _ in range(resamples):
        picks = [rows[rng.randrange(n)] for _ in range(n)]
        for c in range(columns):
            means[c].append(sum(row[c] for row in picks) / n)
    out = []
    for c in range(columns):
        ordered = sorted(means[c])
        intervals = {}
        for level in levels:
            lo = ordered[max(0, int(math.floor((1 - level) / 2 * resamples)))]
            hi = ordered[min(resamples - 1, int(math.ceil((1 + level) / 2 * resamples)) - 1)]
            intervals[level] = [lo, hi]
        out.append(intervals)
    return out


def check_plan(analysis):
    """Errors in an analysis plan (alpha, power, margin, tie_rate, seed, bootstrap)."""
    errors = []
    a = analysis if isinstance(analysis, dict) else {}

    def number(key):
        return isinstance(a.get(key), (int, float)) and not isinstance(a.get(key), bool)

    if not (number("alpha") and 0 < a["alpha"] < 0.5):
        errors.append("analysis.alpha must be in (0, 0.5)")
    if not (number("power") and 0.5 <= a["power"] < 1):
        errors.append("analysis.power must be in [0.5, 1)")
    if not (number("margin") and 0 < a["margin"] <= 1):
        errors.append("analysis.margin must be in (0, 1] on the net-win-rate scale")
    if not (number("tie_rate") and 0 <= a["tie_rate"] < 1):
        errors.append("analysis.tie_rate must be in [0, 1)")
    if not errors and a["margin"] > 1 - a["tie_rate"] + EPS:
        errors.append("analysis.margin %.3f exceeds 1 - tie_rate (%.3f): with that many ties no design can show it"
                      % (a["margin"], 1 - a["tie_rate"]))
    if not isinstance(a.get("seed"), int) or isinstance(a.get("seed"), bool):
        errors.append("analysis.seed must be an integer")
    if not isinstance(a.get("bootstrap"), int) or a.get("bootstrap", 0) < 1000:
        errors.append("analysis.bootstrap must be an integer of at least 1000 resamples")
    return errors


def compare(per_case, analysis):
    """Paired verdict for one comparison. per_case: [{"case", "treatment", "baseline"}], scores in [0, 1]."""
    errors = check_plan(analysis)
    result = {"format": FORMAT, "n_cases": len(per_case), "verdict": None, "reasons": [], "limits": []}
    if errors:
        return dict(result, verdict="invalid", reasons=errors)
    alpha, target, margin, tie = analysis["alpha"], analysis["power"], analysis["margin"], analysis["tie_rate"]
    n = len(per_case)
    if n == 0:
        return dict(result, verdict="not-run", reasons=["no case has a gradable run in both arms"])
    diffs = [c["treatment"] - c["baseline"] for c in per_case]
    signs = [1 if d > EPS else -1 if d < -EPS else 0 for d in diffs]
    wins, losses = signs.count(1), signs.count(-1)
    ties = n - wins - losses
    test = sign_test(wins, losses)
    net_ci, mean_ci = bootstrap([[s, d] for s, d in zip(signs, diffs)], analysis["seed"], analysis["bootstrap"])
    power = power_sign_test(n, margin, tie, alpha)
    need = required_n(margin, tie, alpha, target)
    powered = power >= target
    observed_tie = ties / n
    # Power at a fixed margin depends on the tie rate, so a declared rate that differs from the observed one is
    # rechecked in either direction (fewer ties than declared lowers it; so does a margin the ties make impossible).
    rechecked = abs(observed_tie - tie) > EPS
    observed_power = power
    if rechecked:
        observed_power = power_sign_test(n, margin, observed_tie, alpha) if margin <= 1 - observed_tie + EPS else 0.0
    net90 = net_ci[0.90]
    better = test["p_greater"] <= alpha and net90[0] > 0
    worse = test["p_less"] <= alpha and net90[1] < 0
    inside = -margin < net90[0] and net90[1] < margin
    # What the numbers say before the observed-rate power gate: the verdict this would be, if it claims anything.
    claim = ("worse" if worse else "better" if better and powered and n >= 2
             else "equivalent" if powered and n >= 2 and not better and inside else None)
    # Below the target at the observed rate, none of better, worse or equivalent is claimed; the claim is recorded
    # as withheld_verdict so a gate that needs to know what the data said (the broken-copy control's) can still see it.
    demoted = rechecked and observed_power < target and claim is not None
    need_text = str(need) if need else "more than %d" % LIMIT
    reasons, limits = [], []
    if n < 2:
        reasons.append("single case: one case (however many replicates) can never show a difference")
    if worse and not demoted:
        verdict = "worse"
        reasons.append("one-sided sign test p = %.4f (wins %d, losses %d, ties %d); 90%% interval of the net "
                       "win rate [%.3f, %.3f]" % (test["p_less"], wins, losses, ties, net90[0], net90[1]))
        if not powered:
            limits.append("underpowered design: the size of the harm is likely overstated")
    elif better and powered and not demoted and n >= 2:
        verdict = "better"
        reasons.append("one-sided sign test p = %.4f (wins %d, losses %d, ties %d); 90%% interval of the net "
                       "win rate [%.3f, %.3f]; power %.2f at the %.2f margin"
                       % (test["p_greater"], wins, losses, ties, net90[0], net90[1], power, margin))
    elif powered and n >= 2 and not better and inside and not demoted:
        verdict = "equivalent"
        reasons.append("the 90%% interval of the net win rate [%.3f, %.3f] lies inside +/-%.3f: no difference as "
                       "large as the margin" % (net90[0], net90[1], margin))
    else:
        verdict = "inconclusive"
        if not powered:
            reasons.append("underpowered: power %.2f at n=%d cases for a %.2f margin (declared tie rate %.2f); "
                           "needs at least %s cases" % (power, n, margin, tie, need_text))
        if better and not powered:
            reasons.append("the difference is significant but the design is underpowered, so the effect is likely "
                           "overstated; rerun with at least %s cases" % need_text)
        if demoted:
            reasons.append("underpowered at the observed tie rate: the design declared tie rate %.2f (power %.2f) but "
                           "the cases show %.2f (power %.2f, target %.2f), so none of better, worse or equivalent is "
                           "claimed" % (tie, power, observed_tie, observed_power, target))
        else:
            if not better:
                reasons.append("not significant: one-sided sign test p = %.4f (wins %d, losses %d, ties %d)"
                               % (test["p_greater"], wins, losses, ties))
            if powered and not better:
                reasons.append("the 90%% interval [%.3f, %.3f] is not inside +/-%.3f, so equivalence is not shown "
                               "either" % (net90[0], net90[1], margin))
    limits.append("the unit is the case; replicates are averaged within a case before pairing")
    limits.append("the sign test drops ties (%d of %d cases)" % (ties, n))
    limits.append("intervals are case-level percentile bootstrap (%d resamples, seed %d)"
                  % (analysis["bootstrap"], analysis["seed"]))
    if abs(observed_tie - tie) > 0.2:
        limits.append("declared tie rate %.2f, observed %.2f: the power figure rests on the declared value"
                      % (tie, observed_tie))
    withheld = {"withheld_verdict": claim} if demoted else {}
    return dict(result, verdict=verdict, reasons=reasons, limits=limits, wins=wins, losses=losses, ties=ties,
                sign_test=test, power_at_n=power, required_n=need, powered=powered, margin=margin, alpha=alpha,
                net_win_rate={"estimate": (wins - losses) / n, "ci90": net_ci[0.90], "ci95": net_ci[0.95]},
                mean_difference={"estimate": sum(diffs) / n, "ci90": mean_ci[0.90], "ci95": mean_ci[0.95]}, **withheld)


def wilson_nonoverlap_bar(own, n, z=Z95):
    """The capability map's old defer bar: the candidate's Wilson interval must sit wholly above ours."""
    own_upper = wilson(own, n, z)[1]
    needs = next((k for k in range(own, n + 1) if wilson(k, n, z)[0] > own_upper), None)
    return {"rule": "candidate's 95% Wilson lower bound above our upper bound, n each", "own": own, "n": n,
            "own_upper": own_upper, "candidate_needs": needs, "possible": needs is not None,
            "margin_points": None if needs is None else round(100 * (needs - own) / n)}


def check_quality_criterion(criterion, tie_rate=0.5, alpha=0.05, power=0.8):
    """Errors in a defer-map quality_criterion: its pairs must be able to detect its stated margin."""
    errors = []
    c = criterion if isinstance(criterion, dict) else {}
    pairs, points = c.get("pairs"), c.get("margin_points")
    if not isinstance(pairs, int) or isinstance(pairs, bool) or pairs < 1:
        errors.append("pairs must be a positive integer")
    if c.get("test") not in {"mcnemar", "paired-bootstrap"}:
        errors.append("test must be mcnemar or paired-bootstrap")
    if not isinstance(points, int) or isinstance(points, bool) or not 1 <= points <= 100:
        errors.append("margin_points must be an integer from 1 to 100")
    if errors:
        return errors
    margin = points / 100
    try:
        need = required_n(margin, tie_rate, alpha, power)
    except ValueError as exc:
        return ["pairs cannot help: " + str(exc)]
    if need is None:
        return ["pairs: a %d-point margin needs more than %d pairs at tie rate %.2f" % (points, LIMIT, tie_rate)]
    if pairs < need:
        return ["pairs %d cannot detect a %d-point margin (power %.2f at tie rate %.2f, alpha %.2f); choose at "
                "least %d pairs or a larger margin"
                % (pairs, points, power_sign_test(pairs, margin, tie_rate, alpha), tie_rate, alpha, need)]
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="cases needed to detect a margin")
    plan.add_argument("--margin", type=float, required=True)
    plan.add_argument("--tie-rate", type=float, required=True)
    plan.add_argument("--alpha", type=float, default=0.05)
    plan.add_argument("--power", type=float, default=0.8)
    plan.add_argument("--n", type=int, help="also report the power at this many cases")
    sign = sub.add_parser("sign", help="exact sign test")
    sign.add_argument("--wins", type=int, required=True)
    sign.add_argument("--losses", type=int, required=True)
    bar = sub.add_parser("bar", help="the old non-overlapping-interval defer bar")
    bar.add_argument("--own", type=int, required=True)
    bar.add_argument("--n", type=int, required=True)
    quality = sub.add_parser("quality", help="check a defer-map quality_criterion")
    quality.add_argument("--pairs", type=int, required=True)
    quality.add_argument("--margin-points", type=int, required=True)
    quality.add_argument("--test", default="mcnemar")
    quality.add_argument("--tie-rate", type=float, default=0.5)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            out = {"margin": args.margin, "tie_rate": args.tie_rate, "alpha": args.alpha, "power": args.power,
                   "required_cases": required_n(args.margin, args.tie_rate, args.alpha, args.power)}
            if args.n:
                out.update(n=args.n, power_at_n=power_sign_test(args.n, args.margin, args.tie_rate, args.alpha))
        elif args.command == "sign":
            out = sign_test(args.wins, args.losses)
        elif args.command == "bar":
            out = wilson_nonoverlap_bar(args.own, args.n)
        else:
            errors = check_quality_criterion({"pairs": args.pairs, "margin_points": args.margin_points,
                                              "test": args.test, "suite": "cli"}, args.tie_rate)
            out = {"status": "failed" if errors else "passed", "errors": errors}
    except ValueError as exc:
        sys.stderr.write("evalstats.py: " + str(exc) + "\n")
        return 64
    sys.stdout.write(json.dumps(dict(out, format=FORMAT), indent=2) + "\n")
    return 1 if out.get("status") == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
