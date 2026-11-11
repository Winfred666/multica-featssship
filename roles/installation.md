---
name: multica-featssship-installation
description: Adjust config for the requested workflow, then install after human confirmation.
---

Use only on the assigned installation issue. README.md in the featssship source
owns entry via install.py. Keep that source checkout available until finished.
Entry reads installation metadata before creating defaults, and only creates
defaults when empty. After a completed installation, entry begins a new cycle
from that saved config and creates another MAIN after confirmation. An unfinished
cycle resumes its own MAIN using its saved issue ID.
In grilling, update only what is needed for the requested workflow. Keep settings
that already fit, and return to editing as needed. Ask one human question only
when context leaves something unclear. Pass
`--thread <trigger UUID>` on a comment-triggered invocation.

After edit, the script comments the tidy config and asks the human to edit or
confirm. Exit silently if outer confirmation has not been received yet; after confirmation, continue. The human only replies `confirm`; no command
or UUID is needed. The agent then runs confirmed, which finds the reply automatically.
Installation creates MAIN without a parent, subscribes CEO, and copies process
settings with an explicit installation-config reference to MAIN metadata.
The installer finishes while MAIN continues independently. Init settings and installed_* checkpoints stay on the installer;
`installed_main_issue_id` identifies the last completed MAIN. The active SoP
record saves the active MAIN ID immediately after creation for retry resumption;
no local answers or binding JSON exists.
Follow returned errors; reconcile external writes before retrying.
