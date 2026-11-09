---
name: multica-featssship
description: Delegate one configured feature or fix to separate Developer and Reviewer agents and receive its verified result.
---

From the installed MAIN DEV: issue and target repository root, run
`python3 <this-skill-directory>/entry.py`. Dispatch the original request, title
and configured direction; use `--question` to override acceptance and `--thread`
to reply to a trigger comment. Installation is in README.md.

The callback creates the feature issue and Reviewer package. End the turn;
receive the verified result in the dispatch thread.
