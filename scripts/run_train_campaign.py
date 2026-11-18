"""Run the remaining fixed train batches with versioned calibration prompts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TRACKING = ROOT / "experiments" / "prompt-tracking"
LABEL_RANK = {"weak": 0, "average": 1, "good": 2, "excellent": 3}


def calibration(previous_version: str) -> tuple[str, dict]:
    metrics = json.loads(
        (TRACKING / previous_version / "metrics.json").read_text(encoding="utf-8")
    )
    rows = [
        json.loads(line)
        for line in (TRACKING / previous_version / "results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    completed = [row for row in rows if row["status"] == "COMPLETED"]
    drift = (
        sum(LABEL_RANK[row["predicted"]] - LABEL_RANK[row["expected"]] for row in completed)
        / len(completed)
        if completed
        else 0
    )
    if drift > 0.25:
        guidance = (
            "The previous train batch was systematically over-scored "
            f"(mean label-rank drift {drift:+.2f}). Be stricter: audit raw evidence "
            "and appendix integrity, do not count headings as coverage, and explicitly "
            "search for every missing golden semantic step before choosing a label."
        )
    elif drift < -0.25:
        guidance = (
            "The previous train batch was systematically under-scored "
            f"(mean label-rank drift {drift:+.2f}). Do not penalize supported run, "
            "privilege, path, time or environment variants; count only unique material defects."
        )
    else:
        guidance = (
            f"The previous train batch had stable label direction (mean drift {drift:+.2f}). "
            "Keep the current evidence audit and apply all thresholds consistently."
        )
    return guidance, metrics


def create_prompt(version: str, previous_version: str) -> None:
    guidance, metrics = calibration(previous_version)
    base = (TRACKING / "v007" / "prompt.md").read_text(encoding="utf-8")
    base = base.replace("# Prompt v007 — lossless evidence audit across a new lab", f"# Prompt {version} — calibrated train campaign", 1)
    note = (
        "\n## Calibration from the previous train batch\n\n"
        f"Source: `{previous_version}`; completed {metrics['completed']}, failed "
        f"{metrics['failed']}, exact-label accuracy {metrics['accuracy']:.1%}.\n\n"
        f"{guidance}\n"
    )
    first_section = base.find("\n## Evidence from v006")
    base = base[:first_section] + note + base[first_section:]
    base = base.replace(
        "<!-- COMPARISON_PROMPT_END -->",
        f"\nCalibration instruction for this batch: {guidance}\n<!-- COMPARISON_PROMPT_END -->",
        1,
    )
    version_dir = TRACKING / version
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "prompt.md").write_text(base, encoding="utf-8")


def run_batch(version: str, batch_index: int, provider_reference: str) -> None:
    subprocess.run(
        [
            sys.executable,
            "-u",
            str(ROOT / "scripts" / "run_prompt_batch.py"),
            "--version",
            version,
            "--batch-index",
            str(batch_index),
            "--use-train-split",
            "--provider-reference",
            provider_reference,
        ],
        cwd=ROOT,
        check=True,
    )


def commit_version(version: str) -> None:
    subprocess.run(
        ["git", "add", str(TRACKING / version)], cwd=ROOT, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", f"experiment: complete {version} train batch"],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-batch", type=int, default=4)
    parser.add_argument("--end-batch", type=int, default=16)
    parser.add_argument("--provider-reference", required=True)
    parser.add_argument("--commit-each", action="store_true")
    args = parser.parse_args()

    previous_version = f"v{args.start_batch + 3:03d}"
    for batch_index in range(args.start_batch, args.end_batch + 1):
        version = f"v{batch_index + 4:03d}"
        if (TRACKING / version / "metrics.json").exists():
            print(f"SKIP {version}: already completed", flush=True)
            previous_version = version
            continue
        create_prompt(version, previous_version)
        print(f"START {version}: train batch {batch_index}", flush=True)
        run_batch(version, batch_index, args.provider_reference)
        if args.commit_each:
            commit_version(version)
        previous_version = version
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
