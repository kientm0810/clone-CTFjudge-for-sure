# Dynamic-analysis prompt tracking

This directory records the iterative evaluation of the grading prompt against
the synthetic labels in `datamau/metadata.jsonl`.

Rules for the experiment:

- The metadata label is never included in an LLM request.
- Each batch belongs to one lab and reuses one frozen golden snapshot.
- Reports, predictions, confusion matrices and timing remain attached to the
  prompt version that produced them.
- Prompt changes are justified from errors in the previous completed batch.
- The first four labs contain 25 submissions each, split into `9 + 8 + 8` so
  every batch contains all four quality levels.

Each version directory contains:

- `prompt.md`: exact comparison prompt and rationale.
- `batch-summary.md`: automatic metrics and misclassifications.
- `results.jsonl`: one machine-readable result per submission.
- `reports/`: the downloaded HTML reports.

