---
name: multica-featssship
description: Draft a feature delegation, clarify one point at a time with the human, then dispatch separate Developer and Reviewer agents.
---

Use in the installed MAIN DEV: issue. From the target repository root, run
`python3 <this-skill-directory>/entry.py` and follow its choices. On comment
triggers, pass `--thread <trigger UUID>` first.

Follow `drafting` and `grilling`. To reopen a draft in a new native task, pass
`--spec <draft UUID>` and choose `propose`.

An optional GitHub URL is a source link for mirroring and closure. Scope and
acceptance come from the delegation config. Never create GitHub issues
routinely. MAIN receives the final result and ends the turn when instructed.
[State and callback graphs](DEBUG.md). Installation: README.md.
