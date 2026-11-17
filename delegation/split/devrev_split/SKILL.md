---
name: multica-featssship-devrev-split
description: Reviewer-owned experiment with addressed development and one private score.
metadata: {sop: symbolic}
---

Reviewer runs `multica sop run multica-featssship-devrev-split` from the target
repository in the Reviewer exp issue. Prepare the Developer exp child, then wait
for its native questionnaire answer. Developer does not run this SoP.
Run the single private evaluation, inspect the score and answer the direction's
review questions. Report score JSON plus concise review to MAIN. No integration,
merge, source correction loop or push-to-main. Missing evaluation inputs or OS
access policy are errors, never synthetic scores. A started evaluation cannot
be rerun, including after failure or interruption.
