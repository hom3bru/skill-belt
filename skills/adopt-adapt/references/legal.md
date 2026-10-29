# Legal flag and defensible-route analysis

Artifact boundary: apply this gate separately to acquiring inputs, analyzing them, any access-control step, copying/adapting source, and publishing tools/source/translated code/binaries/content. Record the actual intended distribution in the [method contract](re-methods.md). A tool's license, an AI rewrite, separate assets or a user-supplied copy do not by themselves resolve every artifact's rights. Repository contribution/AI policies are distinct from downstream license permissions. This is a review checklist, not a new legal conclusion; unresolved primary-law checks stay unresolved ([legal-research](legal-research.md) lists them).

**Notice:** Research flags and process guidance only — **not legal counsel**. No attorney–client relationship. Escalate before shipping, decompiling, scraping personal data at scale, or touching console/DRM stacks. Full dossier + source table: [legal-research.md](legal-research.md) (shipped in this package).

Every donor run emits `ledger.legal` with `flag`, `route`, ladder steps, and cited sources (URL + accessed date). Recipient profiles may raise the flag (each lists its own overlay: privacy/egress/anti-detect, paid elements, stealth, holdout or live-data rules; injection, undisclosed persistence or unclear skill licences for skill recipients and SELF).

## Flags

| Flag | Meaning | Live transfer (ADOPT/ADAPT/ADAPT-with-prerequisite)? |
|---|---|---|
| **GREEN** | License + ToS + anti-circumvention support the route with primary cites; hard lines clear. **GREEN(idea-only)**: idea-only reuse from a public source with no terms restriction and no patent signal | Allowed |
| **YELLOW** | Defensible route exists only with conditions (idea-only with an open terms or patent question, subset, API, permission, clean-room, counsel) | Only ADAPT-with-prerequisite naming the condition |
| **RED** | Hard line; code or text reuse from a source with no licence; or ladder exhausted without a lawful rung | **Blocks** transfer plan |
| **UNKNOWN** | Decisive fact missing (a licence that exists but is unclear, unread terms on an access path that required assent, unclear TPM, blocked CFR fetch) | **Blocks** until resolved. Only an unclear licence can be waived: the owner's recorded `waiver` makes it YELLOW |

## Hard lines (never ladder around)
1. Circumvent a TPM/DRM **without** §1201(f), §1201(j), or a matching **current** triennial class (17 U.S.C. § 1201 — https://www.law.cornell.edu/uscode/text/17/1201 , fetched 2026-10-09).
2. Use leaked, stolen, pirated, or shadow-library inputs (Bartz v. Anthropic, N.D. Cal. June 23, 2025 — https://docs.justia.com/cases/federal/district-courts/california/candce/3:2024cv05417/434709/231 ).
3. Bypass auth walls, CAPTCHA-as-gate, paywalls, or private APIs on third-party hosts (Van Buren gates logic — https://www.supremecourt.gov/opinions/20pdf/19-783_k53l.pdf ).
4. Social-engineer humans or invent accounts for closed material.
5. Ignore a recipient profile's privacy, robots, ToS, egress, anti-detect, no-paid or no-stealth overlay.
6. Claim “clean-room” when the implementing agent already saw protected source or tests.

## Persistence ladder (try in order; record `route`)
Idea-only transfers start at rung 2: nothing is copied, so searching for a permissive alternative donor (rung 1) adds nothing. Code or text reuse climbs from rung 1.
1. **Permissive alternative donor** (MIT/Apache/BSD).
2. **Idea-only** from public docs/papers/talks (Sega; Oracle; SAS — ideas/function ≠ expression). Run the **patent-signal check** first; it reads the material you hold, not a patent database, for patent notices, "patented"/"patent pending", a PATENTS or NOTICE grant, or the mechanism being the donor's advertised invention. In what you read, nothing found is `none`; `unknown` means a file that could carry one went unread. Record `patent_signal` (none/hit/unknown) and `terms_restriction` (none/present/unknown). A public page read without assent (no login, clickwrap or paywall) is `terms_restriction: none`; read terms only where access required accepting them, and terms that do not restrict use of ideas are also `none`. Both `none` on a public source → GREEN(idea-only); a patent hit → YELLOW plus counsel before implementation (`escalate_to_lawyer: true`); anything else → YELLOW. An idea taken from unlicensed source code transfers as a behaviour-level contract, never its structure or sequence. Public patents are idea OSINT only, never freedom-to-operate.
3. **License-compatible subset** (SPDX per file).
4. **Documented public APIs / official SDKs**.
5. **Ask author / buy license**.
6. **Clean-room** (Team A specs; firewall; Team B never saw source; paper trail).
7. **Statutory interoperability** only with counsel: §1201(f); EU Software Dir. Art. 6 / UK CDPA s.50B (https://www.legislation.gov.uk/ukpga/1988/48/section/50B , fetched 2026-10-09 — contract override void).
8. **DISCARD**.

**Patent signal on every reuse route.** Record `patent_signal` on every route that reuses anything (every route except `discard`), not only idea-only: MIT and BSD carry no patent grant, and Apache-2.0 or GPL-3.0 grants cover only contributors' own patents. GREEN needs `none`; a hit is YELLOW plus counsel.

## Decision tree
```
hard line? → RED (every part too)
else license OK for planned form of taking?
  no licence → code or text reuse RED; idea-only GREEN(idea-only) if both idea checks are none, else YELLOW
  licence present but unclear → UNKNOWN (owner waiver → YELLOW)
else ToS blocks planned access? → YELLOW/RED; climb ladder
else TPM and no fitting exemption? → RED for that path
else closed-source? → default YELLOW idea-only / public-API / clean-room unless both idea checks are none
else GREEN (+ profile overlays)
```

## License compatibility (per salvaged part)
- No LICENSE → all rights reserved: code or text reuse RED; idea-only per the rung 2 checks.
- NOASSERTION or an unclear licence → UNKNOWN until read per file; only the owner's recorded waiver turns it into YELLOW.
- GPL → copyleft vs proprietary recipient → idea-only or counsel.
- **AGPL** → network-interaction source offer (re-fetch gnu.org; fetch blocked here 2026-10-09 → treat as YELLOW/RED for a hosted proprietary recipient until verified).
- **SSPL** §13 service trigger (https://www.mongodb.com/legal/licensing/server-side-public-license , fetched 2026-10-09).
- BSL / FSL / Elastic / Commons Clause / PolyForm Noncommercial → source-available; usually not OSI; default idea-only or paid license.
- MIT/Apache/BSD → usually GREEN with notice preservation.

## ToS / EULA / robots
- Pin ToS URL+date. Unknown → UNKNOWN/YELLOW (a profile may default to human review).
- Anti-RE clauses can be enforceable despite copyright fair use (**Bowers**, 320 F.3d 1317; **Davidson**, 422 F.3d 630). UK s.50B(4) voids contrary terms for permitted decompilation.
- Browsewrap ≠ automatic assent (**X Corp. v. Bright Data**, Meta v. Bright Data — fact-specific).
- robots.txt is **not** authorization (RFC 9309 https://www.rfc-editor.org/rfc/rfc9309.html ) but honor it by default; a profile may make it a hard gate.
- Public scraping CFAA limits: Van Buren; hiQ **PI** (31 F.4th 1180) — case **ended in Dec. 2022 consent judgment restricting hiQ** (RECAP docket; re-read before citing terms). Meta/Bright Data (Jan. 23, 2024) and X/Bright Data (2024) are district-level and ToS-version specific.

## §1201 + triennials
- Fair use is not a §1201 defense (§1201(c)(1)).
- **(f)** interoperability; **(j)** security testing with owner/operator authorization.
- **2024 final rule** 89 Fed. Reg. 85437 (Oct. 28, 2024) https://www.govinfo.gov/content/pkg/FR-2024-10-28/html/2024-24563.htm — match exact class. eCFR §201.40 fetch CAPTCHA-blocked 2026-10-09 → UNKNOWN until re-fetched.
- **2027 cycle** NOI June 9, 2026 (https://www.copyright.gov/1201/2027/ ); 2024 classes remain until new final rule.
- Console/keys donors (Yuzu judgment Mar. 6, 2024 https://storage.courtlistener.com/recap/gov.uscourts.rid.56980/gov.uscourts.rid.56980.11.0.pdf ; Nintendo DMCA 2026-08-17) → presume RED for domain code.

## Fair use, AI rulings, EU/UK/privacy overlays
Dated status notes (fetched 2026-10-09) live in [legal-research](legal-research.md), section "Status notes moved from legal.md". Read them when the donor involves model training, EU/UK personal data, TDM opt-outs or trade secrets, and re-fetch before relying; never invent a ruling.

## Clean-room
Team A (may read source) → functional spec only; Team B (no source/tests in context) implements; logged Q&A; hashes. Agents that ingested donor source **cannot** be Team B.

## Escalate to counsel
RED before implement; console/DRM; decompile/clean-room for shipping; AGPL/SSPL into hosted product; large-scale PII scrape; fair use/§1201 as sole ship basis; a patent-signal hit or patent FTO; cross-border RE compatibility layers.

## Output schema (`ledger.legal`)
```
flag, route, ladder_steps_tried[], license_parts[], tos{}, section_1201{},
fair_use_note, hard_line_hit, escalate_to_lawyer, advice_notice,
sources[{title,url,accessed}], patent_signal (every reuse route), terms_restriction (idea-only routes),
waiver{by, covers: licence, text, date} (an UNKNOWN licence only),
parts[{id, part, flag, route, basis, patent_signal?, terms_restriction?, waiver?}]
```
`aa.py validate` enforces these fields as [records](records.md) lists them; a `hard_line_hit` makes the donor and every part RED.

## Whole-tool flag versus a transferred part
`flag` is the whole-tool flag. When a clean part is transferred from a donor whose whole-tool flag is RED or UNKNOWN, record that part in `parts[]` with its own flag, rung and basis, name it in the decision's `legal_part`, and keep the whole tool DISCARD. The transferred part's flag then gates the transfer exactly as the table above. Flags recorded for specific donors in earlier reviews are history (`historical-findings.md` section A where an edition ships it); always re-derive the flag at the pinned revision.
