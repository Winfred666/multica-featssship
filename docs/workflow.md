# Shipping flow

```mermaid
flowchart TD
  main["MAIN drafting: prepare delegation config"] -->|propose| grill["grilling: inspect clarity"]
  grill -->|unclear point| ask["Ask human one question with a recommendation; wait"]
  ask -->|answer| edit["edit: patch one config field"]
  edit --> grill
  grill -->|clear: dispatch| dispatch["Create feature and compile Reviewer"]
  dispatch --> dev["Developer: implement, commit and submit"]
  dev --> review["Independent Reviewer: inspect exact commit and answer questions"]
  review -->|corrections| dev
  review -->|approved| hold{"Manual hold accepted or absent?"}
  hold -->|no| human["Wait for human acceptance"]
  human --> hold
  hold -->|yes| integrate["Developer: merge approved commit, test and push main"]
  integrate -->|conflict or failed check| dev
  integrate -->|pushed| source{"Linked GitHub issue?"}
  source -->|yes| close["Comment: integrated commit + Developer resolution<br/>Close issue; reuse comment on retry"]
  source -->|no| receipt["Send MAIN one verified result; feature enters in_review"]
  close --> receipt
  receipt --> received["MAIN receives; human owns done"]
```

| Executable procedure | States and callback internals |
| --- | --- |
| [MAIN delegation](../controller.py) | [Delegation graph](../DEBUG.md) |
| [Developer](../roles/developer.py) | [Developer graphs](../roles/developer-debug.md) |
| [Reviewer](../roles/reviewer.py) | [Reviewer graphs](../roles/reviewer-debug.md) |

The fixture simulates Multica/GitHub actions with real Git operations. Live agent
judgment and server routing remain outside that evidence. Integration locking
covers one host; normal Git push rejects competing updates across hosts.
