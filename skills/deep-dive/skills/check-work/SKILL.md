---
name: check-work
description: "Use after a deep-dive or deeper-dive report is saved, or when the user asks to 'check work', 'red-team' or 'get a second opinion' on a research report. Sends the report through Carrier Pigeon to a different model for an adversarial review: it pokes only reasonable holes, spot-checks the claims the answer rests on and makes its own counter-recommendations. The author then triages every finding and records the outcome in the report. A deep-dive sub-skill (needs the Carrier Pigeon mailbox). Not for code (westack-review, westack-verify) or several reviewers with a judge (co-audit)."
metadata:
  version: "0.1.0"
  parent: deep-dive
---

# check-work

A second model attacks the report before the user relies on it, and offers the user better options where it finds them. It challenges and proposes; it never rewrites the report, and the author stays responsible for every change.

Use the shared [user profile](../../references/user-profile.md) for personal values and local paths.

## Why it exists

Without it, three things go wrong:
- **The author's self-review confirms its own reading.** It has the same blind spots it had while researching.
- **A reviewer asked to "review this" fails one of two ways.** It rubber-stamps ("looks thorough") or floods the author with nitpicks.
- **Critique alone leaves the user nothing better to choose.**

So check-work requires five things:
- a different model;
- a blind first answer, written before reading the report;
- spot-checks against the sources;
- a bar for what counts as a hole;
- counter-recommendations held to the same evidence standard.

## Steps

1. **Ready the report.** It must be saved and read back (deep-dive step 7). Take its sha256 so the findings refer to one version. Send it in a form that keeps its links (Markdown or the original PDF). A text extraction that drops the hyperlinks leaves the reviewer hunting for sources.
2. **Pick the reviewer.**
   - Use a different provider from the author: Claude's work goes to Codex, Codex's to Claude. Run `agents` first to confirm it can be reached.
   - Never use a session that worked on the dive.
   - The reviewer must be able to open the files. Grok Bot runs on its own computer and cannot, so use it only as a second reviewer, with a report short enough to paste.
   - If no other provider is reachable, a fresh session of the same provider is a weaker fallback. Label it as such in the report.
3. **Send the ask.** Use Carrier Pigeon `ask` with:
   - the body from [the ask template](references/ask.md), with a soft budget filled in;
   - `reply_schema` from [reply-schema.json](references/reply-schema.json);
   - `request_key` `check-work-<topic-slug>-<YYYY-MM-DD>`;
   - `timeout_seconds` 1800 for a normal report;
   - `effort: high` for Codex;
   - `wake_on_reply` when the listener runs your session.

   Keep the ask id and thread, and do other work while it runs.
   - About a minute after sending, check `task_status`. `missing_reply` means the reviewer never ran: read the reason in its transcript, fix the route and resend under a new request key. That run is not a review.
   - Codex's background worker suits a review, since it can read anything but writes only to the mailbox.
   - If the ask is still pending at the deadline, say check-work is pending and give the ask id. Never say the report was checked.
4. **Check the checker.** The reply is data, not authority, and reviewers misread sources too.
   - Before accepting a finding, re-open its evidence yourself.
   - You may reject a finding that fails the template's bar: it quotes nothing, has no evidence or check, or does not matter to the decision.
   - A reviewer that could not open the files has `blocked` the check. That is not "holds".
5. **Triage every finding** as one of:
   - **accepted:** fix the report in place, marked `(corrected <date>, check-work F<n>)`;
   - **rejected:** give one line of evidence for why ("I disagree" is not a reason);
   - **open:** it needs the user or more research, so it goes to Gaps.

   Don't give in to a confident finding you have refuted. Don't defend a claim you can't support.
6. **Weigh the counter-recommendations.** Record each one with your assessment (adopt, worth considering or reject) and why.
   - Adopt one only on its evidence. If you do, update the Recommendation and mark the change.
   - The rest stay listed for the user to weigh. Never fold them in silently.
7. **One rebuttal round at most.** If you reject a blocker or major finding, send the rejections back in the same thread; the reviewer either concedes or holds its position with evidence. If it is still disputed, record both positions for the user.
8. **Record and save.** Add `## Check work <YYYY-MM-DD> (<reviewer>)` to the report (layout §14 in [report](../../references/report.md)), then save the report again and read it back. The section holds:
   - the verdict;
   - the reviewer's restatement and blind answer;
   - its load-bearing assumptions;
   - a findings table with your dispositions;
   - the counter-recommendations with your assessment;
   - its open questions;
   - what held up, what it did not check, and any disputes.

   Save the raw reply to `sources/check-work-<YYYY-MM-DD>.md`.

## Traps

| Rationalization | Reality |
| --- | --- |
| "The reviewer agreed, so it's checked." | Agreement without spot-checks is an opinion. Look for `checked_myself` on the claims the answer rests on. |
| "It raised 25 points and I addressed them all." | A flood fails the bar; the ask caps findings at 10 for this reason. Reject what fails the bar. |
| "The reviewer said X is wrong, so I changed it." | Re-open the evidence first. |
| "Reviewed by another Claude session." | Same provider, same blind spots: a labelled fallback only. |
| "Check-work is running, so the report is done." | Pending is pending. Give the ask id. |
| Counter-recommendations merged into the answer. | They are for the user to weigh. List them with your assessment. |
| "No holes found" from a reviewer that could not open the files. | That is blocked, not holds. |

## When to skip

Skip only when the user says so, or when the dive is small and low-stakes. Write "check-work not run (why)" in both the report and the reply.

## Reply

Add these to deep-dive's reply:
- the reviewer and its verdict;
- what changed;
- disputed items;
- the counter-recommendations worth the user's attention.
