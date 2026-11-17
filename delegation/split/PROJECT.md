## Split experiment development and review

For Developer and Reviewer `exp` issues only: prefer an ontology module dictionary
with named responsibilities and inputs/outputs, and connect those modules into a
detailed local pipeline. Reuse the project's existing format, not a new framework.
Each Reviewer experiment owns one named variant of that dictionary/pipeline.
Show its changed modules, connections and detailed local pipeline in the candidate,
visual and review, so the variant is identifiable rather than just a score.
Developer attaches an initial visual image when development starts and updates
it as the pipeline changes. Reviewer inspects that variant and submits one
canonical score JSON plus concise review directly to MAIN. No experiment merge,
integration or push-to-main; MAIN's next-step policy is outside this procedure.
