---
name: multica-featssship-installation
description: Install after human confirmation; retain the existing MAIN for repo-local updates.
---

Use only on the assigned installation issue. From the target repository root,
run `python3 <this-skill-directory>/wrapper.py`. The README also documents
`installation/install.py`. Keep the source or standalone package for updates.
Entry reads the installer-owned `featssship-config.json` through its metadata
reference. It creates defaults only when the document is absent. Installation
retains ordinary state `finished` with only `update`; re-entry never starts another
MAIN. Retries and updates use the saved MAIN issue ID.
In grilling, update only what is needed for the requested workflow. Keep settings
that already fit, and return to editing as needed. Ask one human question only
when context leaves something unclear. Pass
`--thread <trigger UUID>` on a comment-triggered invocation.

After edit, the script attaches tidy JSON in the existing thread and asks the
human to edit or confirm. Download/read the newest attachment to inspect it. Directly and silently end this turn if outer confirmation has not been received yet; after confirmation, continue. The human only replies `confirm`; no command
or UUID is needed. The agent then runs confirmed, which finds the reply automatically.
Installation creates MAIN without a parent, subscribes CEO, and links MAIN
to that same master document.
MAIN continues independently. Settings and reusable agent IDs stay in the master attachment. Skills deploy only to the target repository's `.agents/skills/`. The retained SoP
record saves the active MAIN ID immediately after creation for retries and updates;
no local answers or cached settings exist.

For an update request, run `git -C /path/to/multica-featssship pull --ff-only`,
then `python3 /path/to/multica-featssship/installation/install.py update` from the
target repository in this installation issue. Rebuild a standalone installer from
the latest source before using its `wrapper.py update`. Update refreshes only
the saved MAIN's delegation bundle and installation-owned entry/context references,
then returns to `finished`. Preserve configuration, MAIN identity and delegation
progress. Do not rebind platform skills or update existing dev-rev issues/packages.
There is no legacy metadata fallback or automatic configuration merger.
Follow returned errors; reconcile external writes before retrying.
