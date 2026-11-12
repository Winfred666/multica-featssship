---
name: multica-featssship
description: Dispatch a human-approved JSON batch.
---

In MAIN DEV:, run `python3 <this-skill-directory>/wrapper.py` from the target
repository with `--thread <request UUID>` and optional `--config '{"issues":[{}]}'`
(one item by default).

Edit the shown JSON file offline; `refresh --config-file PATH` uploads the whole
batch and invalidates approval. Run `dispatch` only after the original human
confirms or accepts the latest draft; judge intent, not exact wording. Do not call
SoP and end this turn if no outer confirmation or edition instruction.

Retry partial batches with `dispatch`; successful children are reused. Do not
refresh once a child exists. Follow errors, reconcile writes before retrying,
and use `repaired` once for assertions.
