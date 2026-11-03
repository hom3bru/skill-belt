---
name: jobscura
description: Coordinate a source-grounded job search from intake and a canonical tracker through history, writing, reviewed application packets and interview practice. Load private user context only when explicitly selected; use the six focused workflows for the actual task.
metadata:
  version: "0.4.1"
---

# Jobscura

Use Jobscura as a cohesive toolkit for the user's existing job-search work.
Start with the current request and available evidence, then load the relevant
workflow below. Preserve canonical documents, tracker identity, history and live
permissions. A saved preference never grants permission to act.

| Capability | Load |
| --- | --- |
| Intake and fit assessment | [application-intake](skills/application-intake/SKILL.md) |
| Status, deadlines and morning changes | [application-tracking](skills/application-tracking/SKILL.md) |
| Earlier decisions, evidence and submitted versions | [application-history](skills/application-history/SKILL.md) |
| Drafting, revision and final checks | [application-writing](skills/application-writing/SKILL.md) |
| Offline capture, read-only matching and attachment packets | [application-packet](skills/application-packet/SKILL.md) |
| Grounded interview coaching and practice | [interview-preparation](skills/interview-preparation/SKILL.md) |

Read [loadable user context](context/README.md) when the user has selected a private
context file. Validate it through `scripts/user_context.py`; use its data only for
the relevant task. Never search arbitrary paths, open referenced sources silently,
or export private context into a package. Credentials belong in separate secret
storage. The toolkit remains useful with conversation-supplied evidence when no
context is selected. Ask only for a missing fact that materially affects the work.

Use the host's real source, document and automation tools. Jobscura includes no
background scheduler and never establishes application submission, employer
contact, durable storage or reminder delivery merely by describing a workflow.
