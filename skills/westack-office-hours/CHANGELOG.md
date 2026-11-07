# Changelog

## Public release preparation, unreleased

The choice checker loads `user_name` and optional `legacy_user_names` aliases from the local Skill Belt profile. The neutral default is "the user", with "they" also retained. Names are matched literally and case-insensitively. Invalid profiles fail the check with a value-free diagnostic. The personal-name literal is removed. Eight added regression tests cover configured and neutral owners, explicit legacy aliases, literal matching, invalid profiles, recommendation rejection and the CLI.

## 1.0.0-alpha.0 (first build), unreleased

The first westack-office-hours: a session on an idea before planning. Two modes chosen from the user's goal (demand, for startups and sponsored internal projects; builder, for side projects, research and learning), questions one at a time routed by stage, pushback twice then respect for a second refusal, positions taken without hedging, premises the user marks, two or three approaches with a hard stop until the user chooses, a design document recording that choice in the user's words, and one next action. A search of the space only on the user's yes and with general terms. `scripts/ohcheck.py doc` checks the document's shape and the ruled-out hedges. Ideas from gstack's office-hours (its diagnostic and builder sections and its design-document templates) at the mirror pin, in westack's words; its YC branding, founder resources, builder profile, telemetry and tiered closing are left out. `tests/test_ohcheck.py`: 8 tests; a copy that skips the Choice check fails one.
