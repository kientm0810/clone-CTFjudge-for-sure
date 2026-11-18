"""Cache token, latency and inference metrics for train/test runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

from run_prompt_batch import ROOT, summarize_run_metrics


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def enrich(rows: list[dict], api_url: str) -> list[dict]:
    enriched = []
    for index, row in enumerate(rows, 1):
        detail = requests.get(f"{api_url}/runs/{row['run_id']}", timeout=60)
        detail.raise_for_status()
        enriched.append({**row, **summarize_run_metrics(detail.json())})
        if index % 20 == 0 or index == len(rows):
            print(f"Cached {index}/{len(rows)} runs", flush=True)
    return enriched


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://localhost:8800")
    args = parser.parse_args()
    output_dir = ROOT / "experiments" / "analysis"

    train = []
    for number in range(4, 21):
        version = f"v{number:03d}"
        rows = read_jsonl(ROOT / "experiments" / "prompt-tracking" / version / "results.jsonl")
        train.extend({**row, "version": version, "split": "train"} for row in rows)
    write_jsonl(output_dir / "train-runs.jsonl", enrich(train, args.api_url))

    test_path = ROOT / "experiments" / "test-evaluation" / "final-v014" / "results.jsonl"
    if test_path.exists():
        test = [{**row, "split": "test"} for row in read_jsonl(test_path)]
        write_jsonl(output_dir / "test-runs.jsonl", enrich(test, args.api_url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
