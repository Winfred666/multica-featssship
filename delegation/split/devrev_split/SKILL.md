---
name: multica-featssship-devrev-split
description: Reviewer-owned experiment with addressed development and one private score.
metadata: {sop: symbolic}
---

Reviewer runs `multica sop run multica-featssship-devrev-split --thread <thread>`
using the thread in the Reviewer exp issue description, from the target repository.
Prepare the Developer exp child, then wait
for its native questionnaire answer. Developer does not run this SoP.
Developer attaches an initial pipeline image and updates it during development.
The candidate_ready answer requires the commit, summary, committed local pipeline
and visual image attachment ID. Reviewer inspects the named variant and direction
questions, then runs `submit --review TEXT`. This single action evaluates once,
validates finite score JSON, posts it plus review directly to MAIN and enters
terminal `finished`. A publication retry reuses the saved score; closed experiments
do not restart. No integration,
merge, source correction loop or push-to-main. Missing evaluation inputs or OS
access policy are errors, never synthetic scores. A started evaluation cannot
be rerun, including after failure or interruption.
