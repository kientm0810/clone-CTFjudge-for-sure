# Final evaluation analysis — frozen prompt v014

## Protocol

- Dataset split: 160 train / 40 held-out test.
- Prompt selection used train results only.
- Frozen prompt: `experiments/prompt-tracking/v014/prompt.md`.
- The held-out test was executed once across L02-L08. A failed parser attempt was
  retried for completion, but the prompt and expected labels were never changed
  or sent to the model.
- Golden preparation was frozen once per lab. Token and latency metrics below
  describe per-submission grading (`student-parser` + `comparison-agent`) and do
  not repeatedly charge the shared golden preparation step.

## Why v014 was selected

Individual train batches have different label distributions, so selecting the
largest single-batch accuracy would be biased. We compare the high-quality and
low-quality batches of the same lab as a pair. The L05 pair (`v013 + v014`)
achieved 9/19 exact labels (47.37%), the best paired train result. v014 alone
achieved 5/9 (55.56%) on average/weak reports, the main failure mode of earlier
prompts.

The selected prompt also has the intended architecture:

1. Lossless extraction of behavioral findings, tables and evidence appendices.
2. Report-level comparison rather than requiring every chunk to contain every
   field.
3. Deduplication of defects across chunks.
4. Explicit tolerance for internally supported run variants such as PID,
   timestamp, filename, path, privilege and environment-dependent outcomes.
5. Structured defect diagnostics while leaving the final score to the model;
   train experiments showed that a deterministic defect-count formula amplified
   false defects produced by the 8B model.

## Train campaign

The 160 train reports were used across prompt versions v004-v020, so aggregate
train accuracy is a campaign diagnostic rather than the performance of one
fixed prompt.

| Metric | Value |
|---|---:|
| Completed reports | 160 / 160 |
| Aggregate exact-label accuracy | 28.13% |
| Aggregate macro-F1 | 24.65% |
| Input tokens | 3,160,651 |
| Output tokens | 2,131,641 |
| Total token cost | 5,292,292 |
| Mean tokens per report | 33,077 |
| Mean latency per report | 167.75 s |
| Median latency | 163.26 s |
| P95 latency | 273.16 s |
| Mean inference speed | 4,908 output tokens/min |

## Held-out test results

| Metric | Value |
|---|---:|
| Completed reports | 40 / 40 |
| Exact-label accuracy | 30.00% |
| Macro-F1 | 20.34% |
| Input tokens | 846,380 |
| Output tokens | 582,201 |
| Total token cost | 1,428,581 |
| Mean tokens per report | 35,715 |
| Mean latency per report | 182.62 s |
| Median latency | 189.31 s |
| P95 latency | 259.18 s |
| Mean inference speed | 4,930 output tokens/min |

### Accuracy and runtime by lab

| Lab | Correct | Accuracy | Mean tokens/report | Mean latency | Tokens/min |
|---|---:|---:|---:|---:|---:|
| L02 ransomware | 2/6 | 33.33% | 37,620 | 176.1 s | 4,622 |
| L03 downloader/schtask | 2/6 | 33.33% | 40,400 | 195.2 s | 4,863 |
| L04 HTTP beacon | 2/6 | 33.33% | 32,487 | 162.7 s | 5,354 |
| L05 stealer/FTP | 3/6 | 50.00% | 34,814 | 169.2 s | 5,196 |
| L06 process injection | 1/6 | 16.67% | 37,828 | 214.7 s | 4,649 |
| L07 service persistence | 2/5 | 40.00% | 35,682 | 176.5 s | 4,783 |
| L08 clipboard hijacker | 0/5 | 0.00% | 30,256 | 182.9 s | 5,038 |

### Per-label performance

| Label | Precision | Recall | F1 |
|---|---:|---:|---:|
| excellent | 0.000 | 0.000 | 0.000 |
| good | 0.280 | 0.500 | 0.359 |
| average | 0.500 | 0.417 | 0.455 |
| weak | 0.000 | 0.000 | 0.000 |

The confusion matrix shows a strong center-class bias:

- All 7 excellent reports were reduced to good/average.
- All 7 weak reports were promoted to good.
- Good and average are the only classes with non-zero recall.
- L08 is the weakest generalization domain; L05 is the strongest.

## Interpretation

The test accuracy (30%) is below the selected train-pair result (47.37%), a
17.37-point generalization gap. More importantly, macro-F1 is only 20.34%
because the model never predicts the two extreme classes correctly. This is not
primarily a vector-retrieval failure: similarity is sufficient to retrieve
candidate evidence, but the 8B judge is conservative and inconsistent when
turning a long evidence audit into an ordinal label.

Token cost is also high. A submission consumes roughly 35.7K tokens across
student parsing and comparison. Test reports use 8% more tokens and take about
9% longer than the train-campaign average, while inference throughput remains
almost unchanged. The extra latency therefore comes mainly from larger prompts
and outputs, not a slower GPU.

## Recommended next experiment

Do not tune again on these 40 held-out labels. Preserve them as the final test
result. For a new development cycle, create a fresh validation split and test:

1. Replace free-form defect discovery with a fixed per-lab behavioral checklist
   produced from the golden solution.
2. Ask the LLM for binary/ternary checklist judgments only, then compute the
   final label deterministically from validated fields.
3. Reduce duplicated appendix content before comparison to lower token cost.
4. Evaluate a larger judge model or a smaller specialized classifier for the
   final ordinal label.
5. Keep per-chunk explanations for UX, but separate them from the global grade
   calculation.

All plots and executable calculations are in
`notebooks/train_test_analysis.ipynb`.
