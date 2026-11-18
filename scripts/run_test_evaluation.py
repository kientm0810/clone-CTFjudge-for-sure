"""Run the locked final prompt once against the 40-item held-out test set."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path

from run_prompt_batch import (
    DATASET,
    ROOT,
    SPLIT_FILE,
    create_workflow,
    extract_docx,
    extract_prompts,
    golden_path,
    load_metadata,
    prepare_golden,
    publish,
    start_runs,
    wait_runs,
    write_outputs,
)


LABELS = ["excellent", "good", "average", "weak"]
OUTPUT_ROOT = ROOT / "experiments" / "test-evaluation" / "final-v014"


def test_rows_by_lab() -> dict[str, list[dict]]:
    split = json.loads(SPLIT_FILE.read_text(encoding="utf-8"))
    metadata = {row["file"]: row for row in load_metadata()}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in split["test"]:
        grouped[item["lab_id"]].append(metadata[item["file"]])
    return dict(sorted(grouped.items()))


def combine_results() -> dict:
    results = []
    for result_file in sorted(OUTPUT_ROOT.glob("*/results.jsonl")):
        results.extend(
            json.loads(line)
            for line in result_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    with (OUTPUT_ROOT / "results.jsonl").open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    completed = [item for item in results if item["status"] == "COMPLETED"]
    confusion = {
        expected: {predicted: 0 for predicted in LABELS}
        for expected in LABELS
    }
    by_lab: dict[str, dict] = {}
    for item in completed:
        confusion[item["expected"]][item["predicted"]] += 1
    for lab_id in sorted({item["lab_id"] for item in results}):
        lab_items = [item for item in results if item["lab_id"] == lab_id]
        lab_completed = [item for item in lab_items if item["status"] == "COMPLETED"]
        correct = sum(item["expected"] == item["predicted"] for item in lab_completed)
        by_lab[lab_id] = {
            "total": len(lab_items),
            "completed": len(lab_completed),
            "failed": len(lab_items) - len(lab_completed),
            "accuracy": round(correct / len(lab_completed), 4) if lab_completed else 0,
        }
    correct = sum(item["expected"] == item["predicted"] for item in completed)
    metrics = {
        "prompt_source": "v014",
        "split": "held-out-test",
        "total": len(results),
        "completed": len(completed),
        "failed": len(results) - len(completed),
        "accuracy": round(correct / len(completed), 4) if completed else 0,
        "confusion": confusion,
        "by_lab": by_lab,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (OUTPUT_ROOT / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-reference", required=True)
    parser.add_argument("--api-url", default="http://localhost:8800")
    args = parser.parse_args()

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    prompts = extract_prompts("v014")
    grouped = test_rows_by_lab()
    for lab_id, rows in grouped.items():
        lab_dir = OUTPUT_ROOT / lab_id
        if (lab_dir / "metrics.json").exists():
            print(f"SKIP {lab_id}: already completed", flush=True)
            continue
        lab_dir.mkdir(parents=True, exist_ok=True)
        environment = f"test-v014-{lab_id[:3].lower()}"
        workflow_id = create_workflow(
            args.api_url,
            args.provider_reference,
            prompts,
            f"Held-out test v014 {lab_id}",
        )
        publish(workflow_id, environment)
        snapshot = prepare_golden(
            args.api_url,
            environment,
            extract_docx(args.api_url, golden_path(lab_id)),
        )
        print(f"{lab_id}: golden frozen ({snapshot['chunk_count']} chunks)", flush=True)
        runs = start_runs(args.api_url, environment, rows)
        details = wait_runs(args.api_url, lab_dir, runs)
        for retry_number in range(1, 3):
            failed_ids = [run_id for run_id, detail in details.items() if detail["status"] != "COMPLETED"]
            if not failed_ids:
                break
            failed_rows = [runs[run_id] for run_id in failed_ids]
            print(f"{lab_id}: RETRY {retry_number}/2 ({len(failed_rows)} submissions)", flush=True)
            retry_runs = start_runs(args.api_url, environment, failed_rows)
            retry_details = wait_runs(args.api_url, lab_dir, retry_runs)
            for run_id in failed_ids:
                runs.pop(run_id, None)
                details.pop(run_id, None)
            runs.update(retry_runs)
            details.update(retry_details)
        write_outputs(args.api_url, lab_dir, runs, details)
        (lab_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "prompt_source": "v014",
                    "split": "held-out-test",
                    "lab": lab_id,
                    "environment": environment,
                    "workflow_id": workflow_id,
                    "golden_snapshot_id": snapshot["id"],
                    "files": [row["file"] for row in rows],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        metrics = combine_results()
        print(json.dumps(metrics, ensure_ascii=False, indent=2), flush=True)
    final_metrics = combine_results()
    if final_metrics["total"] != 40 or final_metrics["completed"] != 40:
        raise RuntimeError(f"Held-out test incomplete: {final_metrics['completed']}/40 completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
