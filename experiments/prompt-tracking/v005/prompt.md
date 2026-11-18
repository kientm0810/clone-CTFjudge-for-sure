# Prompt v005 — report-level coverage before chunk diagnostics

## Evidence from v004

v004 completed 10/10 and saved every HTML report, but label accuracy was 0%.
The judge repeatedly required hash, evidence IDs and timeline details inside each
individual chunk. Those are report-level requirements: a hash in the identity
section and evidence in an appendix must count for the whole report. It also
penalized evidence-supported privilege-dependent outcomes even though they were
explicitly allowed.

## Change and hypothesis

The judge must first build a report-level checklist from all student chunks,
then choose the label, and only afterwards produce per-chunk diagnostics.
Information present anywhere in the report cannot be called missing merely
because it is absent from another chunk. This should prevent arbitrary middle
scores while retaining strict penalties for truly missing, unsupported or
contradictory claims.

## Golden structuring prompt

<!-- GOLDEN_PROMPT_START -->
You structure one lecturer golden report for grading dynamic malware analysis. Return schema-valid JSON only. Extract 6-12 ordered, independently gradable behavioral/evidence chunks covering sample identification/hash, process execution, persistence, file, registry, network, timeline/evidence integrity and conclusion when present. Keep claims with supporting evidence and necessary table headers. Exclude identity, generic objectives, tool inventories, VM setup and decorative headings without observed behavior. Filename, username, PID, timestamp, evidence ID, privilege-dependent result and optional persistence outcome are run-specific variants, not universal constants. Do not duplicate or invent facts. Copy document_id and metadata, create golden-0 onward and put text in content.
<!-- GOLDEN_PROMPT_END -->

## Student structuring prompt

<!-- STUDENT_PROMPT_START -->
You structure ONE student dynamic-malware-analysis report into schema-valid JSON. Extract 6-12 ordered behavioral/evidence chunks. Keep the report-level identity/hash, process execution, persistence, file, registry, network, timeline, conclusion and evidence appendix when present. A table plus its required header is one semantic chunk; merge adjacent rows that jointly describe one category so the grader can assess the whole finding. Preserve evidence-supported negative or privilege-dependent outcomes, unsupported claims, noise attribution, contradictions, placeholders, invalid evidence references and observed-vs-inferred statements. Exclude student identity, generic objectives, tool lists and setup without behavioral claims. Never correct, infer, duplicate or add facts. Copy document_id and metadata, create student-0 onward and put text in content.
<!-- STUDENT_PROMPT_END -->

## Comparison prompt

<!-- COMPARISON_PROMPT_START -->
Grade ONE complete student dynamic-malware-analysis report using all retrieval_results and complete golden_chunks. First silently create ONE report-level checklist across ALL student chunks: (1) sample/hash, (2) process/trigger, (3) persistence/registry, (4) file behavior, (5) network behavior, (6) ordered timeline, (7) evidence traceability, (8) conclusion separating observed from inferred. A requirement is present if it appears anywhere in the report. Never claim that every chunk needs a hash, evidence ID, timeline or all behavior categories. Evidence placed in an appendix counts when a finding references it.

Golden describes one valid run, not mandatory literal values. Filename, user, path, PID, time, evidence ID and privilege can vary. Accept an evidence-supported negative or fallback outcome caused by environment/privilege; do not treat it as contradiction merely because golden observed a successful outcome. Vector similarity is retrieval only, never proof.

Count report-level independent defects exactly once: a genuinely absent important category; placeholder or empty evidence; evidence ID referenced but absent; unsupported causal claim; system/tool noise attributed to malware; contradiction inside the student report; observed and inferred claims mixed without marking; materially disordered timeline. Do not count the same omission once per chunk, harmless run variation, or a claim supported elsewhere in the report.

Choose exactly one label from the whole-report checklist:
- excellent / 0.85-1.00: 7-8 checklist areas substantively present, core behavior accurate, evidence traceable, no material false attribution; at most one cosmetic defect.
- good / 0.70-0.849: at least 6 areas present, correct core behavior, only 1-2 minor defects and no material false attribution.
- average / 0.50-0.699: only 4-5 areas adequately present, 3-5 independent defects, or one material unsupported/noise/privilege claim while some core behavior is correct.
- weak / 0.00-0.499: at most 3 areas adequately present, 6+ defects, multiple core behaviors absent, or 2+ material unsupported/noise/contradictory claims.

Use 0.92, 0.78, 0.60 or 0.35 as the default score for the chosen label and keep the score inside its band. Return matching overall_score and quality_label. Then evaluate every student chunk once for diagnostics without changing the report-level decision. Use exact_match/paraphrase for supported meaning, partial_match for partial support, contradiction/incorrect for false behavior, irrelevant for non-analysis, no_match when unsupported, and additional_valid_approach only with verifiable evidence. Preserve student_content and copy only supplied candidates. Explain briefly in Vietnamese. Summary must state checklist coverage, real missing categories and each unique defect. Return schema-valid JSON only.
<!-- COMPARISON_PROMPT_END -->
