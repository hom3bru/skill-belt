# Frame

Separate the user's exact requirements, your assumptions and unknowns. Recover goal, non-goals, acceptance conditions and current authority from the conversation and applicable rules before asking anything. Ask only a question whose answer changes a consequential choice. For a reversible low-impact choice, state a reasonable assumption and proceed when scope permits. Never ask what the repository, tools or conversation can answer: look it up, without holding other questions back while you do. Batch only the questions whose prerequisites are already settled, each with a recommended answer that a plain yes accepts.

Never resolve a vague quantifier ("the usual", "soon", "standard size") silently; record it as an assumption or an open question. For ambiguous dictation or several conflicting messages, briefly echo the interpretation, listing your inferences and filled gaps separately from what the user said. A clear instruction needs no new approval ritual. Later user corrections supersede earlier requirements; record the previous choice as superseded, retain parked topics, and invalidate dependent plans/approvals when their action or scope changes.

Example: “offline; no cloud storage” cannot become a hosted database requirement. “Actually use a JSON file; no database” supersedes an earlier SQLite choice. Do not claim the user selected a framework merely because you selected one.

Persistent records use [contract.json](../contracts/contract.json), especially requirements.origin, supersedes and scope_id; a choice you made rather than the user goes in `decisions` with origin `assumption`. The record documents authority; it cannot grant it.

