---
name: multica-featssship
description: Draft a batch for outer approval.
metadata: {sop: symbolic}
---

Inputs: a batch request in MAIN DEV: and optional `--config '{"issues":[{}]}'`.
Use per-item `manual: true` for outer approval or `false` for automatic integration
after review.

From the target repository in MAIN DEV:, run
`multica sop run multica-featssship --thread <request UUID>`.
Confirmation resolves Git from this installed bundle's target checkout, even
when the callback's saved workdir is MAIN's task context. Retry partial dispatch
with `confirm`; saved children are reused.

Edit the shown JSON offline and run the returned `refresh --config-file PATH`
command to publish it. Outer confirms or requests changes through the native
questionnaire; do not answer on outer's behalf. Follow the returned reply and
error guidance, then end the publication turn.
