---
name: multica-featssship-installation
description: Adjust config for the requested workflow, then install after human confirmation.
---

Use only on the assigned installation issue. From the target repository root,
run `python3 <this-skill-directory>/wrapper.py`. The README also documents
`installation/install.py`. Keep the source or standalone package until finished.
Entry reads the installer-owned `featssship-config.json` through its metadata
reference. It creates defaults only when the document is absent. After a completed installation, entry begins a new cycle
from that saved config and creates another MAIN after confirmation. An unfinished
cycle resumes its own MAIN using its saved issue ID.
In grilling, update only what is needed for the requested workflow. Keep settings
that already fit, and return to editing as needed. Ask one human question only
when context leaves something unclear. Pass
`--thread <trigger UUID>` on a comment-triggered invocation.

After edit, the script attaches tidy JSON in the existing thread and asks the
human to edit or confirm. Download/read the newest attachment to inspect it. Directly and silently end this turn if outer confirmation has not been received yet; after confirmation, continue. The human only replies `confirm`; no command
or UUID is needed. The agent then runs confirmed, which finds the reply automatically.
Installation creates MAIN without a parent, subscribes CEO, and links MAIN
to that same master document.
The installer finishes while MAIN continues independently. Settings and reusable installed agent/skill IDs stay in the master attachment. The active SoP
record saves the active MAIN ID immediately after creation for retry resumption;
no local answers, cached settings or binding JSON exists.
There is no legacy metadata fallback or automatic configuration merger.
Follow returned errors; reconcile external writes before retrying.
