---
name: multica-featssship
description: Draft a batch for outer approval.
metadata: {sop: symbolic}
---

Inputs: a batch request in MAIN DEV: and optional `--config '{"issues":[{}]}'`.
Use per-item `manual: true` for outer approval or `false` for automatic integration
after review. Supply `action` (for example `fix`, `feat` or `simplify`) and a short
`title`, or an existing `<action>(<direction>): <summary>` title matching the selected direction.

From the target repository in MAIN DEV:, run
`multica sop run multica-featssship --thread <request UUID>`.

Edit the shown JSON offline and run the returned `refresh --config-file PATH`
command to publish it. Outer confirms or requests changes through the native
questionnaire; do not answer on outer's behalf. Follow the returned reply and
error guidance, then end the publication turn.
If the installed SoP is missing or dispatch fails, report that prerequisite;
do not substitute `issue create` or a system distribution SoP.
