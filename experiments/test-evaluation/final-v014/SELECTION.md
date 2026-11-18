# Final prompt selection

## Selection rule

The held-out test split was not inspected when selecting the prompt. Prompt
selection uses train results only and compares paired high-quality and
low-quality batches from the same lab so that one favorable label mix cannot
dominate the decision.

## Selected prompt

`experiments/prompt-tracking/v014/prompt.md`

The L05 pair (`v013` + `v014`) achieved 9 correct labels from 19 completed train
reports (47.37%), the strongest paired result among labs evaluated with the
stable lossless evidence-audit workflow. It also produced the best low-quality
batch accuracy (55.56%), which matters because earlier prompts systematically
over-scored average and weak reports. v014 retains full appendix/table evidence,
audits golden behavior report-wide, deduplicates defects, and explicitly treats
PID, timestamps, filenames, paths, privilege and environment outcomes as run
variants when internally supported.

The prompt is frozen before test execution. No test result may be used to alter
it or rerun the held-out set for prompt tuning.
