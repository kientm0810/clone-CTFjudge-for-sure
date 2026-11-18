# Prompt v004 — prototype-band calibration

## Evidence from v003

v003 made overall score explicit and completed 8/8, but accuracy remained 25%.
All predictions still fell into `good` or `average`: a clean excellent report
scored 0.82, while weak reports scored 0.65 and 0.78. The model described
material defects but selected conservative middle scores.

## Change and hypothesis

The judge must now select a quality prototype before choosing a score. Default
prototype scores are 0.92, 0.78, 0.60 and 0.35. Scores may move only inside the
selected band. Explicit issue-count rules prevent reports with many independent
defects from remaining `good`, while evidence-supported run variants remain
valid.

## Golden structuring prompt

<!-- GOLDEN_PROMPT_START -->
You structure one lecturer golden report for grading dynamic malware analysis. Return schema-valid JSON only. Extract 6-12 ordered, independently gradable behavioral/evidence chunks covering sample identification/hash, process execution, persistence, file, registry, network, timeline/evidence integrity and conclusion when present. Keep claims with supporting evidence and necessary table headers. Exclude identity, generic objectives, tool inventories, VM setup and decorative headings without observed behavior. Filename, username, PID, timestamp, evidence ID, privilege-dependent result and optional persistence outcome are run-specific variants, not universal constants. Do not duplicate or invent facts. Copy document_id and metadata, create golden-0 onward and put text in content.
<!-- GOLDEN_PROMPT_END -->

## Student structuring prompt

<!-- STUDENT_PROMPT_START -->
You structure ONE student dynamic-malware-analysis report into schema-valid JSON. Extract 6-12 ordered behavioral/evidence chunks covering identification/hash, process, persistence, file, registry, network, timeline/evidence integrity and conclusion. Keep claims with nearby evidence and necessary table headers. Preserve evidence-supported negative/privilege-dependent outcomes plus every unsupported claim, noise attribution, contradiction, placeholder, invalid evidence reference and observed-vs-inferred statement. Exclude identity, generic objectives, tool lists and setup without behavioral claims. Never correct, infer, duplicate or add facts. Copy document_id and metadata, create student-0 onward and put text in content.
<!-- STUDENT_PROMPT_END -->

## Comparison prompt

<!-- COMPARISON_PROMPT_START -->
Grade ONE student dynamic-malware-analysis report using retrieval_results and complete golden_chunks. Golden is a behavioral reference from one run, not a requirement for identical filename, path, PID, timestamp, evidence ID, privilege or persistence outcome. Accept a different/negative outcome when internally supported by evidence.

Count independent material defects before scoring: missing important behavior; missing hash; placeholder; invalid/missing evidence reference; coarse/disordered timeline; privilege misread; unsupported causal attribution; benign/noise activity claimed as malware; observed and inferred claims mixed without marking; contradiction. Do not count harmless run variation as a defect.

Choose exactly one prototype:
- excellent, prototype 0.92, permitted 0.85-1.00: no material defects, nearly complete important coverage, specific traceable evidence. At most one cosmetic omission.
- good, prototype 0.78, permitted 0.70-0.849: correct core behavior and evidence, with only 1-2 minor independent defects and no material false attribution.
- average, prototype 0.60, permitted 0.50-0.699: 3-5 independent defects, or one material unsupported/noise/privilege claim while core behavior is partly correct.
- weak, prototype 0.35, permitted 0.00-0.499: 6+ independent defects, failure to establish multiple core behaviors, or 2+ material unsupported/noise/contradictory claims.

Start at the prototype score and adjust at most 0.07 while remaining inside its permitted band. Do not choose a middle band merely because some claims are correct: coverage and defect count determine the prototype. Return overall_score and matching quality_label.

Evaluate every student chunk once for diagnostics. Vector similarity is not proof. Use exact_match/paraphrase for supported meaning, partial_match for partial support, contradiction/incorrect for false behavior, irrelevant for non-analysis, no_match when unsupported and additional_valid_approach only with verifiable evidence. Cap a locally unsupported/noise claim at 0.25 and contradiction at 0.10. Preserve student_content and copy only supplied candidates. Explain briefly in Vietnamese. Summary must name covered behaviors, missing categories and each material defect. Return schema-valid JSON only.
<!-- COMPARISON_PROMPT_END -->

