# Shipping flow

```dot
digraph shipping {
  node [shape=box];
  main [label="MAIN drafting: prepare delegation config"];
  grill [label="grilling: inspect clarity"];
  ask [label="Ask human one question with a recommendation; wait"];
  edit [label="edit: patch one config field"];
  dispatch [label="Create feature with shared shipping binding"];
  dev [label="Developer: implement, commit and submit"];
  review [label="Independent Reviewer: inspect exact commit and answer questions"];
  hold [shape=diamond, label="Manual hold accepted or absent?"];
  human [label="Wait for human acceptance"];
  integrate [label="Developer: merge approved commit, test and push main"];
  source [shape=diamond, label="Linked GitHub issue?"];
  close [label="Comment: integrated commit + Developer resolution\nClose issue; reuse comment on retry"];
  receipt [label="Send MAIN one verified result; feature enters in_review"];
  received [label="MAIN receives; human owns done"];
  main -> grill [label="propose"];
  grill -> ask [label="unclear point"];
  ask -> edit [label="answer"];
  edit -> grill;
  grill -> dispatch [label="clear: dispatch"];
  dispatch -> dev;
  dev -> review;
  review -> dev [label="corrections"];
  review -> hold [label="approved"];
  hold -> human [label="no"];
  human -> hold;
  hold -> integrate [label="yes"];
  integrate -> dev [label="conflict or failed check"];
  integrate -> source [label="pushed"];
  source -> close [label="yes"];
  source -> receipt [label="no"];
  close -> receipt;
  receipt -> received;
}
```

| Executable procedure | State graph and callback logic |
| --- | --- |
| [MAIN delegation](../controller.py) | `workflow`; `propose`, `edit`, `dispatch` docstrings |
| [Shared Developer–Reviewer shipping](../roles/feature.py) | `workflow`; phase identity guard and action docstrings |

The runtime compiles each state graph from its `Workflow` declarations. Action
docstrings supply local logic only. Enable `DEBUG` in the installed package's
`config.json` for a selectable HTML preview; package rebuilds retain this setting
and existing issue state.

The fixture simulates Multica/GitHub actions with real Git operations. Live agent
judgment and server routing remain outside that evidence. The platform serializes agents within an issue; normal Git push rejects competing
main updates across issues.
