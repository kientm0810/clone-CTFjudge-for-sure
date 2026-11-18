# Prompt v007 — lossless evidence audit across a new lab

## Evidence from v006

v006 completed the five weak L01 reports without failures and saved every HTML,
but detected only one weak label. The source metadata contains 6-8 independent
issues per report. The likely cause is information loss while compressing long
tables/appendices into too few student chunks, followed by an informal defect
count that overlooks missing semantic steps.

## Change and hypothesis

Student extraction may now use up to 24 chunks and must preserve every finding,
evidence row, placeholder and unresolved reference. The judge audits every
golden behavior as substantiated, unsupported or missing before counting unique
defects. v007 starts L02 and therefore also tests cross-lab generalization.

## Golden structuring prompt

<!-- GOLDEN_PROMPT_START -->
Return schema-valid JSON only. Structure one lecturer golden dynamic-malware report into 8-16 ordered semantic chunks. Capture sample/hash, trigger/process chain, every important behavior and artifact, persistence/configuration, file/registry/network effects, ordered timeline, evidence map, and observed-vs-inferred conclusion. Preserve table headers needed to interpret rows. Exclude identity, generic objectives, tool inventory and environment setup without findings. PID, time, username, path, filename, evidence ID, privilege and environment-dependent outcome are run variants. Never invent or duplicate. Copy document_id and metadata; use golden-0 onward.
<!-- GOLDEN_PROMPT_END -->

## Student structuring prompt

<!-- STUDENT_PROMPT_START -->
Return schema-valid JSON only. Structure ONE entire student dynamic-malware report into 10-24 ordered semantic chunks without losing grading evidence. Preserve each distinct behavioral finding, timeline, IOC, evidence-map row or compact related group, appendix evidence, negative result, fallback, placeholder, TODO/TBD/N/A, unresolved “see appendix” reference, unsupported/noise claim, contradiction, and observed-vs-inferred statement. Keep table headers with their rows. Do not replace concrete text with a summary and do not silently fix claims. Exclude only student identity, generic objectives, tool lists and setup with no finding. Copy document_id and metadata; use student-0 onward. For any non-empty analysis document, chunks must be a non-empty array.
<!-- STUDENT_PROMPT_END -->

## Comparison prompt

<!-- COMPARISON_PROMPT_START -->
Grade ONE complete student report from all retrieval_results against all golden_chunks. Golden is one valid behavioral run: accept evidence-supported variants in filename, user, PID, time, path, privilege, fallback and positive/negative environmental outcome.

Before writing output, audit every important golden semantic behavior exactly once. For each, decide: SUBSTANTIATED (student has concrete supporting observation/evidence), CLAIMED_ONLY (asserted but evidence absent/unresolved), or MISSING. A heading, template row or tool name is not substantiation. Also audit hash, coherent ordered timeline, evidence-reference integrity, and separation of observed from inferred. Search across every student chunk and appendix; information present anywhere counts globally. Never require hash/timeline/evidence in every chunk and never duplicate one defect.

Count unique defects: each MISSING important behavior; each group of CLAIMED_ONLY behavior; absent hash; unresolved/missing evidence reference; placeholder in a required field; materially coarse/disordered timeline; privilege/result misread; unsupported causal claim; system/tool noise attributed to malware; internal contradiction; unmarked inference. Harmless run variation is not a defect.

Label by the audited defect list, not writing polish:
- excellent, 0.92: zero material defects and at most one cosmetic issue; complete concrete traceable chain.
- good, 0.78: 1-2 minor unique defects, substantially complete core chain, no placeholder/unresolved evidence/material false attribution.
- average, 0.60: 3-5 unique defects, or placeholder/unresolved evidence plus another defect, or three missing core behaviors.
- weak, 0.35: 6+ unique defects, four missing core behaviors, or two material false/noise/contradictory claims.
Adjust at most 0.07 inside the matching label band. Return matching overall_score and quality_label. Summary in Vietnamese must explicitly list substantiated behaviors and a numbered unique-defect list; if the list has N items, apply the N threshold above.

Then diagnose every student chunk exactly once. Vector similarity is retrieval only. Use exact_match/paraphrase, partial_match, contradiction/incorrect, irrelevant, no_match, or additional_valid_approach only when justified. Preserve student_content and copy only supplied candidates. Return schema-valid JSON only.
<!-- COMPARISON_PROMPT_END -->
