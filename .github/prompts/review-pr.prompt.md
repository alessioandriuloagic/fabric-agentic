---
description: "Start one independent Review Agent session for a GitHub pull request using checklist A1-F4."
agent: "Review Agent"
argument-hint: "PR number, for example 123"
---

Review pull request #${input} in `alessioandriuloagic/fabric-agentic`.

Use the linked issue, actual diff, changed files, tests, and declared execution evidence. Follow
the Review Agent contract exactly. Emit one structured A1-F4 outcome as the final message: the
deterministic publisher sends the review submission, you do not. Do not modify code, merge, publish
the vote, access Fabric, or retrieve missing evidence from Fabric.