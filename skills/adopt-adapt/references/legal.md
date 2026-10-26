<!-- R4: distilled from legal-research.md (shipped alongside; 2026-10-09 PT). Not legal advice. -->
# Legal flag and defensible-route analysis

R6 artifact boundary: apply this gate separately to acquiring inputs, analyzing them, any access-control step, copying/adapting source, and publishing tools/source/translated code/binaries/content. Record the actual intended distribution in the [method contract](re-methods.md). A tool's license, an AI rewrite, separate assets or a user-supplied copy do not by themselves resolve every artifact's rights. Repository contribution/AI policies are distinct from downstream license permissions. This is a review checklist, not a new legal conclusion; existing unresolved primary-law checks below remain unresolved.

**Notice:** Research flags and process guidance only — **not legal counsel**. No attorney–client relationship. Escalate before shipping, decompiling, scraping personal data at scale, or touching console/DRM stacks. Full dossier + source table: [legal-research.md](legal-research.md) (shipped in this package).

Every donor run emits `ledger.legal` with `flag`, `route`, ladder steps, and cited sources (URL + accessed date). Recipient overlays may raise the flag.

## Flags

| Flag | Meaning | Live transfer (ADOPT/ADAPT/ADAPT-with-prerequisite)? |
|---|---|---|
| **GREEN** | License + ToS + anti-circumvention support the route with primary cites; hard lines clear | Allowed |
| **YELLOW** | Defensible route exists only with conditions (idea-only, subset, API, permission, clean-room, counsel) | Only ADAPT-with-prerequisite naming the condition |
| **RED** | Hard line, or ladder exhausted without a lawful rung | **Blocks** transfer plan |
| **UNKNOWN** | Decisive fact missing (no LICENSE, unread ToS, unclear TPM, blocked CFR fetch) | **Blocks** until resolved or explicit user waiver recorded |

## Hard lines (never ladder around)
1. Circumvent a TPM/DRM **without** §1201(f), §1201(j), or a matching **current** triennial class (17 U.S.C. § 1201 — https://www.law.cornell.edu/uscode/text/17/1201 , fetched 2026-10-09).
2. Use leaked, stolen, pirated, or shadow-library inputs (Bartz v. Anthropic, N.D. Cal. June 23, 2025 — https://docs.justia.com/cases/federal/district-courts/california/candce/3:2024cv05417/434709/231 ).
3. Bypass auth walls, CAPTCHA-as-gate, paywalls, or private APIs on third-party hosts (Van Buren gates logic — https://www.supremecourt.gov/opinions/20pdf/19-783_k53l.pdf ).
4. Social-engineer humans or invent accounts for closed material.
5. Ignore inspected recipient privacy, terms, egress, anti-detect, paid-policy or access restrictions.
6. Claim “clean-room” when the implementing agent already saw protected source or tests.

## Persistence ladder (try in order; record `route`)
1. **Permissive alternative donor** (MIT/Apache/BSD).
2. **Idea-only** from public docs/papers/talks (Sega; Oracle; SAS — ideas/function ≠ expression).
3. **License-compatible subset** (SPDX per file).
4. **Documented public APIs / official SDKs**.
5. **Ask author / buy license**.
6. **Clean-room** (Team A specs; firewall; Team B never saw source; paper trail).
7. **Statutory interoperability** only with counsel: §1201(f); EU Software Dir. Art. 6 / UK CDPA s.50B (https://www.legislation.gov.uk/ukpga/1988/48/section/50B , fetched 2026-10-09 — contract override void).
8. **DISCARD**.

## Decision tree
```
hard line? → RED
else license OK for planned form of taking?
  no/unknown → YELLOW idea-only or UNKNOWN
else ToS blocks planned access? → YELLOW/RED; climb ladder
else TPM and no fitting exemption? → RED for that path
else closed-source? → default YELLOW idea-only / public-API / clean-room
else GREEN (+ overlays)
```

## License compatibility (per salvaged part)
- No LICENSE / NOASSERTION → not permission; code copy RED; idea-only YELLOW.
- GPL → copyleft vs proprietary recipient → idea-only or counsel.
- **AGPL** → network-interaction source offer (re-fetch gnu.org; fetch blocked here 2026-10-09 → treat as YELLOW/RED for a proprietary hosted recipient until verified).
- **SSPL** §13 service trigger (https://www.mongodb.com/legal/licensing/server-side-public-license , fetched 2026-10-09).
- BSL / FSL / Elastic / Commons Clause / PolyForm Noncommercial → source-available; usually not OSI; default idea-only or paid license.
- MIT/Apache/BSD → usually GREEN with notice preservation.

## ToS / EULA / robots
- Pin ToS URL+date. Unknown → UNKNOWN/YELLOW; apply the inspected recipient review policy.
- Anti-RE clauses can be enforceable despite copyright fair use (**Bowers**, 320 F.3d 1317; **Davidson**, 422 F.3d 630). UK s.50B(4) voids contrary terms for permitted decompilation.
- Browsewrap ≠ automatic assent (**X Corp. v. Bright Data**, Meta v. Bright Data — fact-specific).
- robots.txt is **not** authorization (RFC 9309 https://www.rfc-editor.org/rfc/rfc9309.html ) but honor by default and follow any stricter inspected recipient rule.
- Public scraping CFAA limits: Van Buren; hiQ **PI** (31 F.4th 1180) — case **ended in Dec. 2022 consent judgment restricting hiQ** (RECAP docket; re-read before citing terms). Meta/Bright Data (Jan. 23, 2024) and X/Bright Data (2024) are district-level and ToS-version specific.

## §1201 + triennials
- Fair use is not a §1201 defense (§1201(c)(1)).
- **(f)** interoperability; **(j)** security testing with owner/operator authorization.
- **2024 final rule** 89 Fed. Reg. 85437 (Oct. 28, 2024) https://www.govinfo.gov/content/pkg/FR-2024-10-28/html/2024-24563.htm — match exact class. eCFR §201.40 fetch CAPTCHA-blocked 2026-10-09 → UNKNOWN until re-fetched.
- **2027 cycle** NOI June 9, 2026 (https://www.copyright.gov/1201/2027/ ); 2024 classes remain until new final rule.
- Console/keys donors (Yuzu judgment Mar. 6, 2024 https://storage.courtlistener.com/recap/gov.uscourts.rid.56980/gov.uscourts.rid.56980.11.0.pdf ; Nintendo DMCA 2026-08-17) → presume RED for domain code.

## Fair use + AI rulings (do not invent)
- §107 factors (LII).
- Sega; Connectix; Oracle (API declaring code fair use, copyrightability assumed).
- **ROSS** 3d Cir. Sept. 29, 2026 — non-generative competitive training on headnotes **not** fair use (https://www2.ca3.uscourts.gov/opinarch/252153p.pdf ).
- **Bartz** / **Kadrey** (June 2025) — district split on piracy framing; both primary PDFs in dossier.
- **Doe v. GitHub** Sept. 16, 2026 — §1202(b) output theory fails (https://cdn.ca9.uscourts.gov/datastore/opinions/2026/09/16/24-7700.pdf ).
- **NYT v. OpenAI** — SJ briefing in 2026; **no fair-use merits ruling as of 2026-10-09** (docket + secondary).

## EU / UK / privacy (overlays)
- Software Dir. 2009/24 Arts. 5–6 — **PARTIAL** (EUR-Lex wall); use SAS C-406/10 + CELEX cite; re-fetch before relying.
- DSM 2019/790 Art. 3 (research TDM, no opt-out) / Art. 4 (general TDM **with machine-readable opt-out**) — legislation.gov.uk fetched 2026-10-09.
- AI Act Art. 53(1)(c)–(d): copyright policy + comply with Art. 4(3) reservations; training summary — https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-53 (fetched 2026-10-09).
- Trade Secrets Dir. 2016/943 Art. 3(1)(b) — RE of lawfully possessed product lawful absent valid duty — https://www.legislation.gov.uk/eudr/2016/943/article/3/adopted .
- DTSA: RE not “improper means” (§1839(6)).
- GDPR: EDPB Opinion 28/2024; Guidelines 03/2026 on scraping (PDF parse incomplete → escalate for EU personal data).
- CCPA: Cal. Civ. Code §1798.140 et seq. (leginfo/CPPA).
- UK TDM commercial reform: Mar. 2026 report URL in dossier — **PARTIAL**; do not claim a new broad exception without reading the PDF.

## Patents
Public patents → idea OSINT only; not FTO. Claim-chart risk → YELLOW + counsel.

## Clean-room
Team A (may read source) → functional spec only; Team B (no source/tests in context) implements; logged Q&A; hashes. Agents that ingested donor source **cannot** be Team B.

## Recipient overlays
| Profile | Raises flag when… |
|---|---|
| User-specified application | inspected privacy, terms, egress, personal-data and anti-detect restrictions |
| User-specified research workflow | inspected paid-policy, access, holdout and evaluation restrictions |
| Coding-workflow / Self | injection; undisclosed persistence; unclear skill license |

## Escalate to counsel
RED before implement; console/DRM; decompile/clean-room for shipping; AGPL/SSPL into hosted product; large-scale PII scrape; fair use/§1201 as sole ship basis; patent FTO; cross-border RE compatibility layers.

## Output schema (`ledger.legal`)
```
flag, route, ladder_steps_tried[], license_parts[], tos{}, section_1201{},
fair_use_note, hard_line_hit, escalate_to_lawyer, advice_notice,
sources[{title,url,accessed}]
```

## UNKNOWNs carried into the skill
Live eCFR 201.40; full 2009/24 text; gnu.org GPL/AGPL bodies (403 here); hiQ consent $ terms not re-parsed; UK AI report / EDPB 03/2026 / GPAI CoP chapter PDFs not fully parsed; Ryujinx/Dolphin no merits opinions; NYT fair use unruled; AnyPS5 Sony silence ≠ clearance.

## R5 additions (evidence: [build-time source, not shipped] process-read/group1.md, group3.md)
| Donor / input | Flag for copying | Basis |
|---|---|---|
| **Claude Code** (anthropics/claude-code@2301018b, incl. hookify, security-guidance) | **RED for code/prompt/regex text; ideas only** | LICENSE.md:1 "© Anthropic PBC. All rights reserved… Commercial Terms"; README:98 (group3 P6.1) |
| dx-ball original EXE, WAV (26), SBK/PCX, MDS, DEFAULT.BDS | **methods-only**; never copy/redistribute assets or derived outputs | dx-ball test_sound_differential.py:382; test_midi_differential.py:344-346; test_powerups_differential.py:224 (group1 Pass 4-RE P4-13); repo MIT covers tooling only (P2-RE) |
| th04 cheat-modified image (`play_invincible.py`, good_ending.asm) | do not import cheat/patch tooling; publish-isolation guard idea only | group1 Pass 3-RE legal flags |
| Hopper (commercial, BYO), IDA (user-licensed) | analysis drivers = methods-only; vendor licence governs; no redistribution/patching | REA verify-linux-setup-e2e.mjs (R-new20); verify-real-ida.mjs (group3 P5.1) |
| pret/pokered, pokemon-claude-red | methods-only (no LICENSE; commercial ROM disassembly) | group2 RE #1, #5 |
| RE on third-party binaries (custom targets) | **UNKNOWN until provenance + EULA recorded**; YELLOW at best; hardened-runtime/debugger-deny must be respected, never re-signed | REA verify-real-ghidra.mjs:265-267,516-517 (KP41); verify-native-calls.mjs:211-262 |
| Browser/CDP capture of third-party sites | YELLOW (ToS, CFAA authorization, GDPR/CCPA); privacy-default and declared-secret redaction required | REA scripts/lib/browser-*.mjs (group3 P6.3-P6.4); verify-web-network-captures.mjs (P5.5) |
| ILSpy-tests submodule real-world assemblies | UNKNOWN (redistribution licences not checked) | ILSpy root AGENTS.md:51 (P2.2) |
| Codex | Apache-2.0: design reuse GREEN; code copy needs NOTICE (presence unverified) | group3 P6.1 |
| Ghidra | Apache-2.0 + US Gov work disclaimer; synthetic tests GREEN | DISCLAIMER.md; CONTRIBUTING.md:142-146 |

Carried R4 UNKNOWNs (unchanged, still not re-fetched in R5): live eCFR §201.40 (CAPTCHA), full Directive 2009/24 body, gnu.org GPL/AGPL texts, and the PARTIAL PDFs listed above.

### R5.1 legal events and lines (ai-re-trend-2026.md §2.5, §3.3; anyps5.md)
- **AnyPS5**: GPL-2.0-only (README.md:39; anyps5.md:14) → reimplement ideas, never copy into the non-GPL skill. "Clean ELF" input (USAGE.md:5) implies decrypted retail dumps — inference, unverified (anyps5.md:17). No keys shipped (README.md:35 [re-opened]). No public Sony DMCA as of early Oct 2026 — **silence ≠ clearance**. Domain fit remains recipient-specific; process ideas do not clear domain-code rights.
- **Nintendo DMCA vs yuzu forks, 2026-08-17** (github/dmca 2026/08/2026-08-17-nintendo-6.md, raw verified per ai-re-trend-2026.md L07): §1201/prod.keys used against emulator networks in this window.
- **Activision/Bethesda crackdown on viral AI decomp/recreations, 2026-10-01–03** (Kotaku, ai-re-trend-2026.md L03): add **viral AAA-IP clone/decomp** as a distribution red line — private methods only, no public assets/builds.
- **Thomson Reuters v. ROSS (3d Cir., 2026-09-29)**: non-generative competing AI training not fair use; generative left open (Ballard Spahr summary). **Doe v. GitHub (9th Cir., 2026-09-16)**: missing attribution ≠ §1202 CMI removal; ordinary infringement still live (EFF). Both as summarised in ai-re-trend-2026.md; opinions not read in full → summary-level.
- **AI "clean-room" wash** of copyleft (HN 47310160 cluster): a model that saw source/tests cannot be Team B (already hard line 6).
- **UM**: launch with `-nobattleye -noBE` (examples/…/install.sh:6,16,54) → anti-cheat adjacency; apply the recipient anti-detect gate. pret/pokered, pokemon-claude-red, Skill-RSI, skill-juror: no LICENSE at pin → ideas only (missed-sources.md §2.5-2.6; group2).

### R5.2 (group3 P7.1-P7.4)
- Claude Code security-guidance (llm.py, review_api.py, gitutil.py, diffstate.py, security_reminder_hook.py, now read in full): proprietary, **RED to copy code, prompt text, regex or rule wording; ideas only** (LICENSE.md:1, not re-opened locally).
- Ghidra unit tests: Apache-2.0 headers (testcirclerange.cc:1-15); ABI facts are functional facts → GREEN as facts.
- Codex discovery.rs: Apache-2.0 → GREEN to adapt with notice.
- REA browser fixtures: GREEN on owned 127.0.0.1 fixtures; YELLOW as applied to third-party sites.
