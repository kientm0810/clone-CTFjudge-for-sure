# Prompt v006 — unique report defects with hard score caps

## Evidence from v005

v005 recovered all 10 reports after retry, but accuracy was only 10%. It fixed
the earlier per-chunk over-penalty, then became too permissive: reports with
missing hook/append/write behavior, unresolved evidence references and template
placeholders were rated good or excellent merely because their section headings
covered many categories.

## Change and hypothesis

Coverage now counts only substantiated findings, not headings. The judge must
enumerate unique report-level defects before selecting a label. Unresolved
evidence references, placeholders and multiple missing core behaviors impose
hard maximum labels. This retains v005's rule against duplicating one defect per
chunk while restoring discrimination between polished and incomplete reports.

## Golden structuring prompt

<!-- GOLDEN_PROMPT_START -->
Structure one lecturer golden dynamic-malware-analysis report as schema-valid JSON only. Extract 6-12 ordered independently gradable chunks: sample/hash; process and trigger; concrete process/API behavior; persistence/registry; file behavior including fallback/append when present; network; ordered timeline; evidence map; observed-vs-inferred conclusion. Keep supporting evidence and table headers. Exclude identity, generic objectives, tool inventories, VM setup and decorative headings. Filename, username, PID, timestamp, evidence ID, privilege-dependent result and optional persistence outcome are run-specific variants. Do not invent or duplicate. Copy document_id and metadata; name chunks golden-0 onward.
<!-- GOLDEN_PROMPT_END -->

## Student structuring prompt

<!-- STUDENT_PROMPT_START -->
Structure ONE complete student dynamic-malware-analysis report as schema-valid JSON only. Extract 6-12 ordered semantic chunks covering sample/hash, process/trigger, concrete API/process behavior, persistence/registry, file behavior, network, timeline, evidence map and conclusion. Merge adjacent table rows belonging to one finding but preserve placeholders, unresolved evidence references, unsupported/noise claims, contradictions, negative or privilege-dependent observations, and observed-vs-inferred wording. Evidence appendix rows are important and must not be discarded. Exclude student identity, generic objectives, tool lists and setup without findings. Never correct or add facts. Copy document_id and metadata; name chunks student-0 onward. Always return a non-empty chunks array when the document contains analysis text.
<!-- STUDENT_PROMPT_END -->

## Comparison prompt

<!-- COMPARISON_PROMPT_START -->
Grade ONE complete student report using all retrieval_results and complete golden_chunks. Work at REPORT level first, then produce chunk diagnostics. A fact present anywhere in the report counts globally; never demand hash, timeline or evidence ID in every chunk and never count one defect repeatedly.

Golden is one valid run. Accept evidence-supported changes in filename, user, path, PID, timestamp, evidence ID, privilege, fallback path and positive/negative persistence result. Do not accept a heading or assertion as proof: a behavioral finding is substantiated only when linked to concrete observation/log/evidence. An evidence reference is valid only if the referenced item actually exists and supports the claim. Text such as TODO, TBD, N/A where evidence is expected, “xem phụ lục” with no matching appendix item, or an empty template row is a real defect.

Silently enumerate UNIQUE defects across the full report:
1. each missing important behavior from the golden semantic chain (for example hook/API behavior, persistence result, ADS write/fallback, append, network result);
2. absent sample hash;
3. unresolved or missing evidence reference;
4. placeholder left in a required finding/evidence field;
5. materially coarse/disordered timeline;
6. privilege/result misread;
7. unsupported causal claim or benign/tool noise attributed to malware;
8. internal contradiction or unmarked observed-vs-inferred claim.
Do not count harmless run variation. Count a category once even if repeated.

Apply these rules in priority order:
- weak (0.00-0.499, default 0.35): 6+ unique defects, at least 4 missing core behaviors, or 2+ material false/noise/contradictory claims.
- average (0.50-0.699, default 0.60): 3-5 unique defects; OR any unresolved evidence reference/placeholder plus another defect; OR at least 3 missing core behaviors. A report meeting an average rule cannot be good/excellent even if it has polished tables.
- good (0.70-0.849, default 0.78): exactly 1-2 minor unique defects, core behavior is substantially complete, no unresolved evidence/placeholder and no material false attribution.
- excellent (0.85-1.00, default 0.92): zero material defects, nearly complete specific behavior, traceable evidence and coherent timeline; at most one cosmetic issue.

Return overall_score and matching quality_label. Afterwards evaluate every student chunk exactly once. Vector similarity is retrieval only. Use exact_match/paraphrase, partial_match, contradiction/incorrect, irrelevant, no_match, or additional_valid_approach only as justified. Preserve student_content and copy only supplied candidates. Explain briefly in Vietnamese. Summary must state substantiated behaviors and list each unique defect explicitly. Return schema-valid JSON only.
<!-- COMPARISON_PROMPT_END -->
