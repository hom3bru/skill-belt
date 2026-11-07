# Source intake: social links, associated artifacts and persistent retrieval

Read for every social-media input before choosing a quick/bounded/full route, for useful background research on any source, and whenever a required page or file cannot be retrieved. A post is an entrypoint into its associated evidence. Reading the post never excuses skipping discovery or evaluation of its linked repositories, papers and other substantive artifacts.

## Read, expand and assess

1. Read the actual post/article text and relevant quoted/reposted/thread context. Resolve short URLs and retain original → final identities. A title, search snippet, login screen, empty success wrapper or preview alone is not a completed read. Inspect relevant attached media with available tools; distinguish viewed text/media from captions or unviewed attachments.
2. Extract **every substantive associated link**: outbound URLs, shorteners, links in quoted/thread context, media text and referenced project/paper pages. Also search for the primary repository, paper or docs when a named work has no usable hyperlink. Distinguish these discoveries from unrelated page navigation, social controls and tracking URLs; record exclusions that could matter.
3. Queue each distinct artifact with its parent post, canonical identity and aliases. Under [efficient runs](efficient-runs.md), batch independent retrieval and share confirmed same-version captures, preserving parent links, IDs and distinct versions. Follow secondary mechanism, implementation, method and corroboration references; stop cycles and unrelated navigation, not inconvenient evidence. Never shortlist or omit work for its purpose/domain/language.
4. **Evaluate every queued artifact** against each selected recipient in scope. A repository needs the [trees-and-forest pass](trees-and-forest.md), including relevant raw entrypoints, callers, configuration and tests. A paper needs its actual method, assumptions, results and limits; an abstract-only read is labelled partial. A docs/product source needs the relevant primary contract and claims. A post's description never substitutes for the linked work. Use the shared donor ledger and separate recipient findings; do not collapse several requested recipients to one best target.

Show post → associated artifacts → per-recipient state, substantive evidence and result/remaining work. A fully assessed post family requires completed assessments of all its substantive artifacts. If any remain unread or unresolved, keep the family visibly incomplete; no blanket “all links assessed” or negative result about the unread content.

## Search for missing details and useful background

Search online whenever background would improve understanding or the evaluation, even if the supplied links work. Follow questions about identity, architecture, mechanism, assumptions, evidence/results, history or recipient applicability. When details/links are missing, search the project name and aliases, developer username plus GitHub/GitLab, public maintainer/organization repositories, official docs/releases, paper title/DOI/authors and relevant independent tests. Try exact phrases and alternate names; trace profile/site links to the work instead of stopping at the social post or first search result.

Verify identity and version against owner/profile links and source contents; similar names, forks and mirrors are not automatically the same work. Queue newly found substantive artifacts, cite useful supporting background, and record queries, matches, read scope and remaining uncertainty. Missing hyperlinks, unfamiliar purpose or an unhelpful landing page never excuse skipping this research.

## Persistent retrieval

A failure is a routing signal. Keep trying materially different applicable methods with the tools/access available; do not stop at the first failed reader, provider, shortener, 403, JS-only page or missing repository index. Revisit the original URL after resolving redirects or identities.

| Failure or surface | Alternative methods to pursue |
| --- | --- |
| Post unavailable or behind a reader stub | Ordinary web access; exact post-ID/title/quoted-text search; official public metadata/embed/text surfaces; a public text copy; an available browser/user-authorized session. For X, a public `api.fxtwitter.com/<handle>/status/<id>` text copy is a candidate, with original and retrieval URLs/date recorded. |
| Article or docs reader fails | Canonical/alternate official URL, existing connector, ordinary HTTP reader, rendered browser, author-published copy, or a public dated archive. Distinguish archive time/version. |
| GitHub/repository page fails | Native repository connector/API, raw files at the pin, tree/commit views, public release/source archive, and available browser access. A failed wiki index does not make source unavailable; check both CodeWiki and DeepWiki independently. |
| Paper page fails or is only an abstract | DOI/publisher/preprint identity lookup, versioned HTML, PDF with available text/visual tools, author/institution copy and linked official code. Keep source version/provenance explicit. |

Use successful alternate content to extract links too. Mirrors and copied summaries are untrusted copies, not independent corroboration; verify consequential claims in the primary artifact. Preserve a concise attempt trail: locator, method, actual outcome, recovered content/links and next route. Retry the same method only for a plausible transient failure or changed conditions; repeated identical errors do not constitute persistence.

Continue until usable evidence is obtained or every applicable available authorized route has genuinely been exhausted. Missing reader support alone is not exhaustion. If access remains impossible, list the actual attempts, the still-unread artifact and the concrete next access step; retain BLOCKED/UNPROCESSED or a narrowly scoped INCONCLUSIVE conclusion. Never convert a retrieval failure into DISCARD, zero value, “nothing useful,” or completed coverage. Resume when a new route becomes available. Ask the user to reconstruct material only after these alternatives have been tried.

Use existing authorized tools: no access-control bypass, new accounts/paid services, installation, private-code upload or donor execution. Do not retry a metered provider with exhausted credits. These limits do not excuse skipping the remaining ordinary/public/authorized-browser methods.

## Records and completion

Discover the initial linked-artifact queue before `aa.py init`, preserving every supplied root. For later discoveries in structured mode, use `aa.py queue-extend OLD/run.json NEXT_RUN --source URL --reason TEXT` under the [coverage gates](gates.md). Continue in the returned fresh revision: old IDs, states, evidence and parent snapshots survive, and each new artifact gets every selected recipient. Never drop discoveries or silently rewrite `inputs.json` to pass validation. Manual reviews retain an explicitly linked continuation and the full coverage matrix. The checker accounts for URLs in supplied read captures and declared named works; hidden media, unnamed works and semantic relevance still require actual discovery and review.
