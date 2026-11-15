---
name: multica-featssship-installation
description: Install or update featssship in an assigned installation issue.
metadata: {sop: symbolic}
---

Inputs: target repository, requested workflow and any known role/runtime choices.

From the target repository root in the assigned installation issue, run
`multica sop run multica-featssship-installation`. See the README for source
discovery. Pass `--thread <trigger UUID>` on comment-triggered calls.

Follow the returned drafting and publication guidance. Outer confirms or requests
edits through the native questionnaire; do not answer on outer's behalf.
Follow the returned reply guidance and end the publication turn.

For updates, use the latest source or rebuilt standalone installer and run
`multica sop run multica-featssship-installation update`. Follow the README's
update instructions and returned error guidance.
