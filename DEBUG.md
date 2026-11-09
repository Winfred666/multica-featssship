# MAIN specification and delegation SOP

```mermaid
flowchart TD
  drafting["drafting: prepare delegation config"] -->|propose| grilling["grilling: inspect clarity"]
  grilling -->|edit: one point after one human question| grilling
  grilling -->|dispatch| finished["finished: end turn; receive result"]
```

State: drafting

```mermaid
flowchart TD
  entry["Check installed workspace, root and MAIN identity"] --> source{"Existing draft supplied with --spec?"}
  source -->|no| draft["Agent drafts behavior, scope, acceptance and verification from request and known facts"]
  draft --> propose["propose: publish config in MAIN thread"]
  source -->|yes| reopen["propose: read existing config unchanged"]
  propose --> grilling["grilling"]
  reopen --> grilling
```

State: grilling — unfolded interaction

```mermaid
flowchart TD
  inspect["Agent inspects draft clarity"] --> clear{"Any unclear point?"}
  clear -->|yes| ask["Ask human one question with a recommended answer"]
  ask --> wait["End turn; wait for answer"]
  wait --> answer["Human answers that question"]
  answer --> edit["edit: all config flags optional; supply one field"]
  edit --> patch["Preserve other fields; publish patched config"]
  patch --> inspect
  clear -->|no| dispatch["dispatch directly"]
```

State: grilling — unfolded dispatch callback

```mermaid
flowchart TD
  entry["Read current delegation config"] --> reuse{"Dispatch already recorded for this spec?"}
  reuse -->|yes| prepared{"Feature binding published and agent started?"}
  prepared -->|yes| finished
  prepared -->|no| compile
  reuse -->|no| create["Create parked feature assigned to Developer"]
  create --> feature["Create feature comment thread for submissions and verdicts"]
  feature --> receipt["Record feature ID and thread ID in MAIN receipt comment"]
  receipt --> compile["Compile Reviewer from scope and acceptance"]
  compile --> bind["Write feature binding to its issue description"]
  bind --> start["Promote prepared feature to todo; Developer starts"]
  start --> finished["finished: MAIN ends turn"]
```

State: finished

```mermaid
flowchart LR
  review["Reviewer verdict in feature thread"] --> dev["Developer: corrections or approved integration"]
  dev -->|verified and pushed| result["Developer posts one final result in MAIN receipt thread"]
  result --> main["MAIN receives"]
```

| Graph operation | Code and durable record |
| --- | --- |
| Workspace/root/identity check | [`configured`](controller.py): native IDs must match `installation.json` |
| Draft config | [`propose`, `read_spec`](controller.py): config in MAIN's native thread |
| Human interaction and one-point patch | [`grilling` state prompt and `edit`](controller.py): optional edit flags; native questions and answers |
| Park or reuse feature | [`dispatch`](controller.py): `issue create --status backlog`; MAIN dispatch record reuses its ID |
| Threads and retry checkpoint | [`dispatch`](controller.py): feature comment + MAIN receipt; local `.state/<spec UUID>-dispatch.json` caches IDs |
| Review and final result | [`verdict`](roles/reviewer.py) steers Developer; [`integration`](roles/developer.py) delivers to MAIN |
