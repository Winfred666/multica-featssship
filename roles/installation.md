---
name: multica-featssship-installation
description: Adjust config for the requested workflow, then install after human confirmation.
---

Use only on the assigned installation issue. README.md in the featssship source
owns entry via install.py. Keep that source checkout available until finished.
In grilling, update only what is needed for the requested workflow. Keep settings
that already fit, and return to editing as needed. Ask one human question only
when context leaves something unclear. Pass
`--thread <trigger UUID>` on a comment-triggered invocation.

After edit, the script comments the tidy config and asks the human to edit or
confirm. Exit silently as instructed. The human only replies `confirm`; no command
or UUID is needed. The agent then runs confirmed, which finds the reply automatically.
Installation then configures MAIN, subscribes CEO, copies only process settings to MAIN metadata and marks
the installer done. Init settings and installed_* checkpoints stay on the installer;
no local answers or binding JSON exists.
Follow returned errors; reconcile external writes before retrying.
