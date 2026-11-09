# Developer states

```mermaid
flowchart TD
  resume --> implement
  resume --> await_review
  resume --> integrate
  resume --> finished
  implement -->|prepare| implement
  implement -->|submit| await_review
  await_review -->|corrections| implement
  await_review -->|approved| integrate
  integrate -->|failed merge or check| implement
  integrate -->|pushed, source closed if linked, MAIN notified| finished
```

State: resume

```mermaid
flowchart LR
  entry[Own native task] --> check[Check identity and native thread]
  check --> route{Latest evidence}
  route --> implement
  route --> await_review
  route --> integrate
  route --> finished
```

State: implement

```mermaid
flowchart LR
  entry[Check binding] --> prepare[Prepare feature branch]
  prepare --> source[Implement; amend the same feature commit for corrections]
  source --> commits[Require one feature commit against fetched main]
  commits --> submit[Test, then push with lease on the previous submission]
  submit --> compile[Report line totals and top three files; compile and steer Reviewer for fresh approval]
  compile --> await_review
```

State: await_review

```mermaid
flowchart TD
  entry[Read native verdict] --> verdict{Current submission reviewed?}
  verdict -->|no| stop[End turn and await native reply]
  verdict -->|rework| implement
  verdict -->|approved| integrate
```

State: integrate

```mermaid
flowchart TD
  entry[Check current Reviewer approval of latest submission] --> hold{Manual hold accepted by member?}
  hold -->|no| wait[End turn for human]
  hold -->|yes or absent| lock[Acquire host integration lock]
  lock -->|busy| retry[End turn; retry integration]
  lock -->|acquired| revision[Fetch main; verify approved branch head]
  revision --> saved{Integration already recorded?}
  saved -->|yes| verify[Verify recorded revision is on main]
  saved -->|no| merge[Merge approved commit in disposable checkout]
  merge --> test[Test integrated checkout]
  test -->|pass| push[Push main; record integration]
  merge -->|conflict| implement
  test -->|fail| implement
  push --> linked{Linked GitHub source?}
  verify --> linked
  linked -->|yes| comment[Post integrated commit and Developer resolution only; reuse existing comment]
  comment --> close[Close source issue; verify closure]
  comment -->|error| retry
  close -->|error| retry
  close --> receipt[Send or reuse one inline result; steer MAIN]
  linked -->|no| receipt
  receipt --> review[Feature enters in_review; human owns done]
  review --> finished
```
