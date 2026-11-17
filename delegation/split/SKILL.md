---
name: multica-featssship-split
description: Draft an experiment batch for outer approval.
metadata: {sop: symbolic}
---

From MAIN's target repository, run
`multica sop run multica-featssship-split --thread <request UUID>`.
Draft and refresh the batch JSON. Outer confirms the native questionnaire.
Dispatch creates Reviewer exp children; each Reviewer owns a separate split SoP
and addresses development to a Developer exp child. MAIN only receives results.
Do not integrate experiments or decide MAIN's next policy here.
