---
name: multica-featssship
description: Draft a JSON batch for native outer dispatch or change requests.
metadata: {sop: symbolic}
---

In MAIN DEV:, run `multica sop run multica-featssship` from the target
repository with `--thread <request UUID>` and optional `--config '{"issues":[{}]}'`
(one item by default).

Each item accepts `manual: true` or `manual: false` to override the installation
default; explicit `false` selects automatic review approval.

Edit the shown JSON file offline, then run `refresh --config-file PATH` to
validate and publish the whole batch, including its first publication. Follow
`this_round_reply_guidance` to briefly explain the changes and end the turn.
The native questionnaire in this issue's current thread lets outer `confirm`
to dispatch directly, or `request_changes --change-request TEXT` to return batch changes
to MAIN in `edit`. Outer owns `outer_decide` in this issue/current thread;
the owner dict's agent ID is callback transport, not decision ownership.
Do not answer outer's questionnaire on its behalf.

Retry partial batches with `confirm`; successful children are reused. Do not
edit or refresh once a child exists. Follow errors, reconcile writes before
retrying, and use `repaired` once for assertions.
