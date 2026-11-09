---
name: multica-featssship
description: Draft a feature delegation, clarify one point at a time with the human, then dispatch a shared issue-owned Developer–Reviewer shipping flow.
---

Use in the installed MAIN DEV: issue. From the target repository root, run
`python3 <this-skill-directory>/entry.py` and follow its choices. On comment
triggers, pass `--thread <trigger UUID>` first.

Follow `drafting` and `grilling`. To reopen a completed draft, pass
`--spec <draft UUID>` and choose `propose`.

An optional GitHub URL is a source link for mirroring and closure. Scope and
acceptance come from the delegation config. Never create GitHub issues
routinely. MAIN receives the final result and ends the turn when instructed.
Use `--help` to replay the saved decision, or read this body for a new/completed issue flow.
Installation: README.md.

In every state, follow returned error guidance and finish unmet prerequisites
before retrying. Reconcile writes first. For assertion failures, use the returned
`repaired` recall once; report a repeated failure through native Multica block.
