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
acceptance come from the delegation config. Reuse a supplied GitHub issue.
Proactively create one only for a valuable or impressive feature after the user
explicitly approves its creation during delegation; pass its URL as
`--github-issue`. Never create feature issues for trivial fixtures or very minor
features. MAIN receives the final result and ends the turn when instructed.
[State and callback graphs](DEBUG.md). Installation: README.md.
