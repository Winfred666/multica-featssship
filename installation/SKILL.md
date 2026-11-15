---
name: multica-featssship-installation
description: Install after outer confirmation; retain the existing MAIN for repo-local updates.
metadata: {sop: symbolic}
---

Use only on the assigned installation issue. From the target repository root,
run `multica sop run multica-featssship-installation`. See the README for source
discovery. Keep the source or standalone package for updates.
Entry reads the installer-owned `featssship-config.json` through its metadata
reference. It creates defaults only when the document is absent. Installation
retains ordinary state `finished` with only `update`; re-entry never starts another
MAIN. Retries and updates use the saved MAIN issue ID.
In `edit`, draft only the settings needed for the requested workflow. Keep
settings that already fit. Ask one human question only when context leaves
something unclear. Pass `--thread <trigger UUID>` on a comment-triggered invocation.
Use `publish --patch '<JSON merge patch>'` to attach the configuration and enter
the native `outer_decide` questionnaire in this installation issue/current thread.
Publish `{}` even when the initial configuration needs no edits. The attachment
retains the change request; native ownership publishes the questionnaire and accepts
its answer. End the publication turn silently.

Outer chooses `confirm` to execute installation directly, or `request_edit` with one
`--change-request` to return to `edit` for agent drafting. Use the engine's questionnaire
answers; no separate confirmation comment or agent confirmation command is needed.
Installation validates the configuration, creates MAIN without a parent,
subscribes CEO, and links MAIN to that same master document.
MAIN continues independently. Skills deploy only to the target repository's `.agents/skills/`.

For an update request, run `git -C /path/to/multica-featssship pull --ff-only`,
then `MULTICA_SOP_SKILL_ROOTS=/path/to/multica-featssship multica sop run multica-featssship-installation update` from the
target repository in this installation issue. Rebuild a standalone installer from
the latest source before using `multica sop run multica-featssship-installation update`. Update refreshes only
the saved MAIN's delegation bundle and installation-owned entry/context references,
then returns to `finished`. Preserve configuration, MAIN identity and delegation
progress. Do not rebind platform skills or update existing dev-rev issues/packages.
Follow returned errors; reconcile external writes before retrying.
