# Shipping flow

MAIN installs/configures roles, clarifies the request and supplies the feature
branch. The child then runs one shared [procedure](../roles/feature.py):

```dot
digraph develop_review {
  rankdir=LR; node [shape=box];
  develop [label="Developer: implement, test and submit"];
  review [label="Reviewer: inspect exact revision"];
  finished [label="Merge and test, or send MAIN a manual-check note"];
  develop -> review [label="submit"];
  review -> develop [label="rework"];
  review -> finished [label="approve"];
}
```

Both roles use the current issue folder and the same metadata record. The native
agent ID guards each phase. A manual label, conflict or failed integration is
reported to the parent; the child workflow finishes. Human acceptance owns done.

The HTML graph comes from `Workflow`; action docstrings explain local logic.
Enable `DEBUG` in package `config.json` for an offline, selectable Graphviz
preview. Package rebuilds retain settings. No renderer service is required.
