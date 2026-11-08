---
name: multica-featssship
description: Delegate one configured feature or fix to separate Developer and Reviewer agents and receive its verified result.
---

Use in the installed MAIN DEV: root issue. Required inputs are the original
feature/fix request, title and configured direction; an acceptance question may
override the installed direction's question. Installation is in README.md.

From the target repository root, run `python3 <this-skill-directory>/entry.py`.
Follow the returned `dispatch` command. Supply `--thread` with the native trigger
comment when replying. The callback creates one feature issue and a compiled
Reviewer package. MAIN ends its turn and receives the verified result there.

Every invocation uses its own native task, issue and identity. Follow returned
error guidance, reconcile external writes before retrying, use `repaired` once
for assertion failures, and report a repeated failure through native Multica
block. Keep evidence in native comments and local untracked artifacts.
