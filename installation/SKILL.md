---
name: multica-featssship-installation
description: Install or update featssship in an assigned installation issue.
metadata: {sop: symbolic}
---

Inputs: target repository, requested workflow and known role/runtime choices.
Build at the persistent target's `.agents/skills/multica-featssship-installation/`
using the [README commands](https://github.com/Winfred666/multica-featssship#installer-agent).
Run `multica sop run multica-featssship-installation` from that target root in the
assigned installation issue; pass `--thread <trigger UUID>` on comment triggers.
Keep the checkout/bundle at their saved paths for callbacks; no shell-only discovery.
Follow returned drafting, publication and reply guidance. Outer confirms or requests
edits through the native questionnaire; do not answer on outer's behalf.
For updates, rebuild at the same location from current source, then run
`multica sop run multica-featssship-installation update` in the same issue/target root.
