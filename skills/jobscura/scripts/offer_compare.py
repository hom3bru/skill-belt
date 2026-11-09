#!/usr/bin/env python3
"""Deterministic multi-year comparison of job offers from user-supplied terms.

Computes year-by-year pre-tax value: base with raises, target bonus x expected
payout, sign-on and relocation, equity vesting (cliff, monthly/quarterly/annual or
an explicit per-year schedule; RSUs or options at a stated growth rate),
refreshers, retirement match, benefits and recurring costs, plus equity
sensitivity at 0%, 50%, 100% and 150% of the stated value.

Arithmetic on the user's numbers only: not tax, legal or investment advice.
Private-company equity can be worth nothing; the 0% scenario is always shown.
"""
from __future__ import annotations

import argparse
import math

import jobscura_common as common
from jobscura_common import ToolError, require

VERSION = "1.0.0"
FREQUENCY_MONTHS = {"monthly": 1, "quarterly": 3, "semiannual": 6, "annual": 12}
SCENARIOS = (0.0, 0.5, 1.0, 1.5)


def number(value, name, low=0.0, high=1e12, default=None, integer=False):
    if value is None:
        require(default is not None, f"{name} is required")
        return default
    require(type(value) in (int, float) and math.isfinite(value), f"{name} must be a finite number")
    require(low <= value <= high, f"{name} must be between {low:g} and {high:g}")
    if integer:
        require(float(value).is_integer(), f"{name} must be a whole number")
        return int(value)
    return float(value)


def vested_fraction(month, total, cliff, every):
    if month < cliff or total <= 0:
        return 0.0
    vested_months = min(total, (month // every) * every)
    return max(vested_months, cliff) / total if month >= cliff else 0.0


def equity_by_year(equity, years, name="offer"):
    if not equity:
        return [0.0] * years, None
    require(isinstance(equity, dict), "equity must be an object such as {\"type\": \"rsu\", \"grant_value\": 80000}")
    if equity.get("type", "none") == "none":
        return [0.0] * years, None
    kind = equity.get("type")
    require(kind in {"rsu", "options"}, "equity.type must be rsu, options or none")
    growth = number(equity.get("annual_growth_pct"), "equity.annual_growth_pct", -100, 1000, 0.0) / 100
    schedule = equity.get("schedule_pct")
    vesting_years = number(equity.get("vesting_years"), "equity.vesting_years", 1, 10, 4, integer=True)
    cliff = number(equity.get("cliff_months"), f"{name}.equity.cliff_months", 0, 60, 12, integer=True)
    total = vesting_years * 12
    require(cliff <= total, f"{name}.equity.cliff_months must not exceed the vesting term ({total} months)")
    if schedule is not None:
        require(isinstance(schedule, list) and schedule, "equity.schedule_pct must be a list of yearly percentages")
        shares = [number(x, "equity.schedule_pct item", 0, 100) for x in schedule]
        require(abs(sum(shares) - 100) <= 0.01, "equity.schedule_pct must sum to 100")
        fractions = [x / 100 for x in shares]
        note = "explicit yearly schedule " + "/".join(f"{x:g}" for x in shares)
    else:
        frequency = equity.get("frequency", "monthly")
        require(frequency in FREQUENCY_MONTHS, "equity.frequency must be monthly, quarterly, semiannual or annual")
        every = FREQUENCY_MONTHS[frequency]
        fractions = [vested_fraction(12 * y, total, cliff, every) - vested_fraction(12 * (y - 1), total, cliff, every)
                     for y in range(1, vesting_years + 1)]
        note = f"{vesting_years}-year {frequency} vesting, {cliff}-month cliff"
    if kind == "rsu":
        grant = number(equity.get("grant_value"), "equity.grant_value", 0, 1e11)
        values = [grant * f * (1 + growth) ** (i + 1) for i, f in enumerate(fractions)]
    else:
        shares_total = number(equity.get("shares"), "equity.shares", 0, 1e10)
        strike = number(equity.get("strike_price"), "equity.strike_price", 0, 1e7)
        fmv = number(equity.get("current_value_per_share"), "equity.current_value_per_share", 0, 1e7)
        values = [shares_total * f * max(0.0, fmv * (1 + growth) ** (i + 1) - strike) for i, f in enumerate(fractions)]
        note += "; options valued at paper spread (value minus strike), before exercise cost and tax"
    padded = (values + [0.0] * years)[:years]
    return padded, note + (f"; {growth * 100:g}% assumed annual value change" if growth else "; no value change assumed")


def offer_years(offer, years):
    name = offer.get("name")
    require(isinstance(name, str) and name.strip(), "every offer needs a name")
    base = number(offer.get("base"), f"{name}.base", 0, 1e9)
    raise_pct = number(offer.get("annual_raise_pct"), f"{name}.annual_raise_pct", -50, 100, 0.0) / 100
    bonus_pct = number(offer.get("bonus_target_pct"), f"{name}.bonus_target_pct", 0, 1000, 0.0) / 100
    payout = number(offer.get("bonus_expected_payout_pct"), f"{name}.bonus_expected_payout_pct", 0, 500, 100.0) / 100
    bonus_fixed = number(offer.get("bonus_fixed"), f"{name}.bonus_fixed", 0, 1e9, 0.0)
    sign_on = number(offer.get("sign_on"), f"{name}.sign_on", 0, 1e9, 0.0)
    relocation = number(offer.get("relocation"), f"{name}.relocation", 0, 1e8, 0.0)
    match_pct = number(offer.get("retirement_match_pct"), f"{name}.retirement_match_pct", 0, 100, 0.0) / 100
    match_cap = number(offer.get("retirement_match_cap"), f"{name}.retirement_match_cap", 0, 1e8, math.inf)
    benefits = number(offer.get("benefits_annual_value"), f"{name}.benefits_annual_value", 0, 1e8, 0.0)
    refresher = number(offer.get("refresher_annual_value"), f"{name}.refresher_annual_value", 0, 1e9, 0.0)
    refresher_start = number(offer.get("refresher_start_year"), f"{name}.refresher_start_year", 1, 10, 2, integer=True)
    costs = number(offer.get("annual_costs"), f"{name}.annual_costs", 0, 1e8, 0.0)
    equity, equity_note = equity_by_year(offer.get("equity"), years, name)
    rows = []
    for y in range(1, years + 1):
        salary = base * (1 + raise_pct) ** (y - 1)
        row = {"year": y, "base": salary, "bonus": salary * bonus_pct * payout + bonus_fixed,
               "equity": equity[y - 1], "refresher": refresher if y >= refresher_start else 0.0,
               "one_time": (sign_on + relocation) if y == 1 else 0.0,
               "retirement_match": min(salary * match_pct, match_cap), "benefits": benefits, "costs": -costs}
        row["total"] = sum(v for k, v in row.items() if k != "year")
        rows.append({k: (round(v, 2) if isinstance(v, float) else v) for k, v in row.items()})
    notes = [n for n in (equity_note,
                         f"sign-on clawback: {offer['sign_on_clawback']}" if offer.get("sign_on_clawback") else None,
                         "refreshers modeled as a flat yearly value from year %d" % refresher_start if refresher else None) if n]
    return name.strip(), rows, notes, equity


def compare(data):
    require(isinstance(data, dict), "offers file must be a JSON object")
    years = number(data.get("years"), "years", 1, 10, 4, integer=True)
    currency = data.get("currency", "")
    offers = data.get("offers")
    require(isinstance(offers, list) and 1 <= len(offers) <= 10, "offers must be a list of 1-10 offers")
    results, names = [], set()
    for offer in offers:
        require(isinstance(offer, dict), "each offer must be an object")
        name, rows, notes, equity = offer_years(offer, years)
        require(name.casefold() not in names, "offer names must be unique")
        names.add(name.casefold())
        non_equity = sum(r["total"] - r["equity"] for r in rows)
        scenarios = {f"equity_at_{int(s * 100)}pct": round(non_equity + s * sum(r["equity"] for r in rows), 2) for s in SCENARIOS}
        results.append({"name": name, "years": rows, "year_one_total": rows[0]["total"],
                        "total_over_years": round(sum(r["total"] for r in rows), 2),
                        "average_annual": round(sum(r["total"] for r in rows) / years, 2),
                        "equity_share_of_total": round(sum(r["equity"] for r in rows) / max(1e-9, sum(r["total"] for r in rows)), 4)
                        if sum(r["total"] for r in rows) > 0 else None,
                        "sensitivity": scenarios, "notes": notes,
                        "non_monetary": {k: offer[k] for k in ("pto_days", "remote", "title", "start_date", "location", "notes")
                                         if k in offer}})
    baseline = data.get("baseline") or results[0]["name"]
    base = next((r for r in results if r["name"].casefold() == str(baseline).casefold()), None)
    require(base is not None, "baseline must name one of the offers")
    for result in results:
        result["difference_vs_baseline"] = {"baseline": base["name"],
                                            "year_one": round(result["year_one_total"] - base["year_one_total"], 2),
                                            "total": round(result["total_over_years"] - base["total_over_years"], 2)}
    ranking = sorted(results, key=lambda r: -r["total_over_years"])
    return {"schema_version": 1, "tool": "offer_compare", "tool_version": VERSION, "currency": currency, "years": years,
            "offers": results, "ranking_by_total": [r["name"] for r in ranking],
            "ranking_if_equity_worthless": [r["name"] for r in sorted(results, key=lambda r: -r["sensitivity"]["equity_at_0pct"])],
            "limits": "Pre-tax arithmetic on supplied terms. Not tax, legal or investment advice. Taxes, vesting "
                      "acceleration, clawbacks, cost of living and non-monetary factors are the user's judgment."}


def markdown(result):
    lines = [f"Offer comparison over {result['years']} years ({result['currency'] or 'stated currency'}), pre-tax", "",
             "| Offer | Year 1 | Total | Avg/yr | Equity 0% | Equity 150% |", "|---|---:|---:|---:|---:|---:|"]
    for offer in result["offers"]:
        s = offer["sensitivity"]
        lines.append(f"| {offer['name']} | {offer['year_one_total']:,.0f} | {offer['total_over_years']:,.0f} | "
                     f"{offer['average_annual']:,.0f} | {s['equity_at_0pct']:,.0f} | {s['equity_at_150pct']:,.0f} |")
    lines += ["", result["limits"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--offers", required=True, help="JSON file with currency, years and offers")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    def run():
        result = compare(common.read_json(args.offers))
        if args.format == "markdown":
            text = markdown(result)
            if args.out:
                with open(args.out, "x", encoding="utf-8") as handle:
                    handle.write(text)
            common.write_stdout(text)
        else:
            common.emit(result, args.out)
    return common.run_cli(run)


if __name__ == "__main__":
    raise SystemExit(main())
