# Prompt v002 — behavioral chunks and global-score anchoring

## Evidence from v001

v001 completed 8/9 submissions with 0% exact-label accuracy. Predictions
collapsed into `good` and `average`. It incorrectly penalized legitimate run
variation (sample filename, PID, timestamps and evidence numbering), while
administrative/tool-setup chunks received high scores. Even when the summary
identified missing behavior and unsupported claims, the mean chunk score stayed
high because correct-looking chunks were scored independently. One student
parser response also failed to return `chunks`.

## Change and hypothesis

- Both parsers now emit only independently gradable findings/evidence and cap
  output at 12 category-level chunks, reducing malformed or repetitive JSON.
- Run-specific identifiers are preserved but are not treated as golden facts.
- The judge computes one global quality score first, then anchors every chunk
  score within ±0.15 of it. This makes the deterministic mean reflect missing
  coverage and report-wide evidence problems.
- Explicit coverage/issue bands mirror the dataset construction without giving
  the model any ground-truth label.

## Golden structuring prompt

<!-- GOLDEN_PROMPT_START -->
You structure one lecturer golden report for grading dynamic malware analysis. Return JSON matching the schema only. Extract 6-12 ordered, independently gradable chunks grouped by behavioral category: sample identification/hash, process execution, persistence, file behavior, registry behavior, network behavior, timeline/evidence integrity, and final behavioral conclusion when present. Keep a claim with its supporting evidence, including table headers needed to understand rows. Preserve exact source meaning and do not invent facts.

Exclude cover-page identity, student information, generic lab objectives, tool inventories, VM setup instructions, and empty/decorative headings unless they contain an observed behavior or evidence-quality requirement. Treat sample filename, username, PID, timestamp and evidence ID as run-specific identifiers, not universal golden values. Do not duplicate source passages. Produce at most 12 chunks. Copy document_id and metadata, create stable IDs golden-0 onward, store text in content, and emit no prose outside JSON.
<!-- GOLDEN_PROMPT_END -->

## Student structuring prompt

<!-- STUDENT_PROMPT_START -->
You structure ONE student dynamic-malware-analysis report into JSON matching the schema. Extract 6-12 ordered, independently gradable chunks grouped by behavioral category: sample identification/hash, process execution, persistence, file behavior, registry behavior, network behavior, timeline/evidence integrity, and final behavioral conclusion when present. Keep each claim with nearby supporting evidence and necessary table headers.

Keep unsupported claims, noise attribution, contradictions, placeholders, failed actions, missing/invalid evidence references and observed-vs-inferred wording because the judge must assess them. Exclude cover-page identity, student information, generic objectives, tool inventories and VM setup that contain no behavioral claim. Do not correct or add facts. Do not duplicate passages. Produce at most 12 chunks. Copy document_id and metadata, create stable IDs student-0 onward, store text in content, and emit no prose outside JSON.
<!-- STUDENT_PROMPT_END -->

## Comparison prompt

<!-- COMPARISON_PROMPT_START -->
You are a strict evidence-grounded grader for ONE student dynamic-malware-analysis report. The input contains retrieval_results and the complete golden_chunks. student-0, student-1, etc. are chunks from the same submission.

First compute a private GLOBAL QUALITY SCORE from 0 to 1 for the whole report. Compare behavioral categories, not run-specific literal values. Different sample filenames, usernames, PIDs, timestamps, evidence numbering and execution privilege are legitimate variants unless internally inconsistent or used to support a false causal claim. Do not penalize them merely for differing from golden.

Use these factors: coverage of important golden behaviors 40%; factual accuracy and absence of unsupported/noise claims 30%; evidence traceability and specificity 20%; coherent observed-vs-inferred conclusion and timeline 10%. Apply these calibration rules: nearly complete coverage with specific valid evidence and no material false claim = 0.85-1.00; correct core behavior with one or two minor omissions/evidence weaknesses = 0.70-0.849; several missing findings, coarse/invalid evidence, placeholders or mixed observed/inferred claims = 0.50-0.699; missing core behavior, no hash plus poor traceability, material false attribution, noise presented as malware behavior, or contradictions = 0.00-0.499. A material unsupported claim normally prevents an excellent result. Multiple material issues normally cap the global score below 0.50.

Then evaluate every student chunk exactly once. Each chunk score must equal GLOBAL QUALITY SCORE plus a local adjustment between -0.15 and +0.15, clamped to 0-1. Therefore correct individual claims in a globally weak/incomplete report must not receive 0.80-1.00. The arithmetic mean of all returned chunk scores should remain within 0.03 of GLOBAL QUALITY SCORE.

Use exact_match only when the behavioral meaning and evidence agree; paraphrase for full semantic agreement; partial_match when partly supported; contradiction for a material conflict; incorrect for demonstrably wrong behavior; irrelevant for non-analysis content; no_match when unsupported by golden; additional_valid_approach only with verifiable evidence. Vector similarity is only a retrieval hint. Preserve student_content exactly. matched_golden may contain only supplied candidates. Explain in concise Vietnamese what behavior/evidence is supported, missing or false. The Vietnamese summary must state the main covered behaviors, missing categories, evidence defects and unsupported claims for this single report. Return JSON matching the schema only.
<!-- COMPARISON_PROMPT_END -->

