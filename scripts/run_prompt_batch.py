"""Run one tracked prompt batch against a frozen golden snapshot."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import time

import requests


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "datamau"
TRACKING = ROOT / "experiments/prompt-tracking"
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}
LABELS = ["excellent", "good", "average", "weak"]
BATCH_QUOTAS = [
    {"excellent": 2, "good": 3, "average": 2, "weak": 2},
    {"excellent": 2, "good": 3, "average": 2, "weak": 1},
    {"excellent": 1, "good": 2, "average": 3, "weak": 2},
]


def request(method: str, url: str, **kwargs):
    response = requests.request(method, url, timeout=kwargs.pop("timeout", 180), **kwargs)
    response.raise_for_status()
    return response


def load_metadata() -> list[dict]:
    return [
        json.loads(line)
        for line in (DATASET / "metadata.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def select_batch(lab_id: str, batch_index: int) -> list[dict]:
    rows = [row for row in load_metadata() if row["lab_id"] == lab_id]
    by_label = {
        label: [row for row in rows if row["quality_level"] == label]
        for label in LABELS
    }
    offsets = {label: 0 for label in LABELS}
    batches: list[list[dict]] = []
    for quota in BATCH_QUOTAS:
        batch: list[dict] = []
        for label in LABELS:
            start = offsets[label]
            stop = start + quota[label]
            batch.extend(by_label[label][start:stop])
            offsets[label] = stop
        batches.append(batch)
    if sorted(row["file"] for batch in batches for row in batch) != sorted(row["file"] for row in rows):
        raise RuntimeError(f"Batch plan does not cover exactly 25 files for {lab_id}")
    return batches[batch_index]


def extract_prompts(version: str) -> dict[str, str | None]:
    text = (TRACKING / version / "prompt.md").read_text(encoding="utf-8")
    prompts: dict[str, str | None] = {}
    for key in ("GOLDEN", "STUDENT", "COMPARISON"):
        match = re.search(
            rf"<!-- {key}_PROMPT_START -->\s*(.*?)\s*<!-- {key}_PROMPT_END -->",
            text,
            re.S,
        )
        prompts[key.lower()] = match.group(1).strip() if match else None
    if prompts["comparison"] is None:
        legacy = re.search(r"<!-- PROMPT_START -->\s*(.*?)\s*<!-- PROMPT_END -->", text, re.S)
        prompts["comparison"] = legacy.group(1).strip() if legacy else None
    if prompts["comparison"] is None:
        raise RuntimeError(f"Comparison prompt markers are missing in {version}/prompt.md")
    return prompts


def extract_docx(api_url: str, path: Path) -> str:
    with path.open("rb") as handle:
        response = request(
            "POST",
            f"{api_url}/documents/extract-docx",
            files={"file": (path.name, handle, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
    return response.json()["content"]


def golden_path(lab_id: str) -> Path:
    matches = sorted((DATASET / "golden_solution").glob(f"{lab_id}_*.docx"))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one golden solution for {lab_id}, found {len(matches)}")
    return matches[0]


def create_workflow(
    api_url: str,
    provider_reference: str,
    prompts: dict[str, str | None],
    name: str,
) -> str:
    definition = json.loads((ROOT / "backend/app/seeds/ctfjudge_rag_workflow.json").read_text(encoding="utf-8"))
    definition["name"] = name
    definition["version"] = 1
    for node in definition["nodes"]:
        if node["type"] == "agent":
            node["config"]["model"] = provider_reference
            node["config"]["temperature"] = 0
            node["config"]["max_tokens"] = 20000
        if node["id"] == "golden-parser" and prompts["golden"]:
            node["config"]["prompt"] = prompts["golden"]
        if node["id"] == "student-parser" and prompts["student"]:
            node["config"]["prompt"] = prompts["student"]
        if node["id"] == "comparison-agent":
            node["config"]["prompt"] = prompts["comparison"]
            node["inputs"]["golden_chunks"] = "{{ steps.golden-parser.output.chunks }}"
            schema = node["config"]["output_schema"]
            schema["properties"]["overall_score"] = {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            }
            schema["properties"]["quality_label"] = {
                "type": "string",
                "enum": ["excellent", "good", "average", "weak"],
            }
            schema["required"] = list(dict.fromkeys([
                *schema.get("required", []),
                "overall_score",
                "quality_label",
            ]))
    response = request(
        "POST",
        f"{api_url}/workflows",
        json={"definition": definition, "description": "Tracked prompt evaluation batch"},
    )
    return response.json()["id"]


def publish(workflow_id: str, environment: str) -> None:
    code = """
import asyncio, sys
from app.database import SessionLocal
from app.services.workflow_store import WorkflowStore
async def main():
    async with SessionLocal() as session:
        if await WorkflowStore(session).publish(sys.argv[1], sys.argv[2]) is None:
            raise RuntimeError('workflow not found')
asyncio.run(main())
"""
    subprocess.run(
        ["docker", "compose", "exec", "-T", "api", "python", "-c", code, workflow_id, environment],
        cwd=ROOT,
        check=True,
    )


def prepare_golden(api_url: str, environment: str, content: str) -> dict:
    snapshot = request(
        "POST",
        f"{api_url}/deployments/{environment}/golden-snapshots",
        json={"inputs": {"golden": content}},
    ).json()
    while snapshot["status"] not in {"READY", "FAILED"}:
        time.sleep(2)
        snapshot = request(
            "GET",
            f"{api_url}/deployments/{environment}/golden-snapshots/{snapshot['id']}",
        ).json()
    if snapshot["status"] != "READY":
        raise RuntimeError(snapshot.get("error") or "Golden snapshot failed")
    return snapshot


def start_runs(api_url: str, environment: str, rows: list[dict]) -> dict[str, dict]:
    submissions = []
    for row in rows:
        path = DATASET / row["file"]
        submissions.append({"filename": path.name, "inputs": {"student": extract_docx(api_url, path)}})
    items = request(
        "POST",
        f"{api_url}/deployments/{environment}/runs/batch",
        json={"submissions": submissions},
    ).json()
    metadata = {row["file"]: row for row in rows}
    return {item["run"]["id"]: metadata[item["filename"]] for item in items}


def wait_runs(api_url: str, runs: dict[str, dict]) -> dict[str, dict]:
    pending = set(runs)
    details: dict[str, dict] = {}
    last = ""
    while pending:
        counts = Counter()
        for run_id in list(pending):
            detail = request("GET", f"{api_url}/runs/{run_id}", timeout=60).json()
            counts[detail["status"]] += 1
            if detail["status"] in TERMINAL:
                details[run_id] = detail
                pending.remove(run_id)
        message = " ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        if message != last:
            print(datetime.now().strftime("%H:%M:%S"), message, flush=True)
            last = message
        if pending:
            time.sleep(3)
    return details


def predicted_label(score: float) -> str:
    if score >= 0.85:
        return "excellent"
    if score >= 0.70:
        return "good"
    if score >= 0.50:
        return "average"
    return "weak"


def write_outputs(api_url: str, version_dir: Path, runs: dict[str, dict], details: dict[str, dict]) -> None:
    reports = version_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    results = []
    for run_id, metadata in runs.items():
        detail = details[run_id]
        result = {
            "file": metadata["file"],
            "lab_id": metadata["lab_id"],
            "expected": metadata["quality_level"],
            "run_id": run_id,
            "status": detail["status"],
            "error": detail.get("error"),
        }
        if detail["status"] == "COMPLETED":
            report = detail["result"]["outputs"]["report"]
            score = float(report.get("summary_score", 0))
            result.update(
                score=score,
                predicted=predicted_label(score),
                similarity_score=report.get("similarity_score"),
                comparisons=len(report.get("comparisons") or []),
            )
            html = request("GET", f"{api_url}/runs/{run_id}/report.html").content
            (reports / f"qwen3-8b-q4_{Path(metadata['file']).stem}.html").write_bytes(html)
        results.append(result)

    with (version_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")

    completed = [item for item in results if item["status"] == "COMPLETED"]
    correct = sum(item["expected"] == item["predicted"] for item in completed)
    confusion = {
        expected: {predicted: 0 for predicted in LABELS}
        for expected in LABELS
    }
    for item in completed:
        confusion[item["expected"]][item["predicted"]] += 1
    metrics = {
        "completed": len(completed),
        "failed": len(results) - len(completed),
        "accuracy": round(correct / len(completed), 4) if completed else 0,
        "confusion": confusion,
    }
    (version_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = "\n".join(
        f"| {item['file']} | {item['expected']} | {item.get('predicted', 'FAILED')} | {item.get('score', 0):.3f} |"
        for item in results
    )
    matrix = "\n".join(
        f"| {expected} | " + " | ".join(str(confusion[expected][predicted]) for predicted in LABELS) + " |"
        for expected in LABELS
    )
    summary = f"""# Batch result

- Completed: {metrics['completed']}
- Failed: {metrics['failed']}
- Exact-label accuracy: {metrics['accuracy']:.1%}

## Confusion matrix

| Expected \\ Predicted | excellent | good | average | weak |
|---|---:|---:|---:|---:|
{matrix}

## Submissions

| File | Expected | Predicted | Score |
|---|---|---|---:|
{rows}
"""
    (version_dir / "batch-summary.md").write_text(summary, encoding="utf-8")
    print(json.dumps(metrics, indent=2), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--lab", required=True)
    parser.add_argument("--batch-index", required=True, type=int, choices=[0, 1, 2])
    parser.add_argument("--provider-reference", required=True)
    parser.add_argument("--api-url", default="http://localhost:8800")
    args = parser.parse_args()

    version_dir = TRACKING / args.version
    rows = select_batch(args.lab, args.batch_index)
    prompts = extract_prompts(args.version)
    environment = f"eval-{args.lab[:3].lower()}-{args.version}"
    workflow_id = create_workflow(
        args.api_url,
        args.provider_reference,
        prompts,
        f"Prompt eval {args.version} {args.lab} batch {args.batch_index + 1}",
    )
    publish(workflow_id, environment)
    snapshot = prepare_golden(
        args.api_url,
        environment,
        extract_docx(args.api_url, golden_path(args.lab)),
    )
    print(f"Golden frozen: {snapshot['chunk_count']} chunks", flush=True)
    runs = start_runs(args.api_url, environment, rows)
    details = wait_runs(args.api_url, runs)
    write_outputs(args.api_url, version_dir, runs, details)
    manifest = {
        "version": args.version,
        "lab": args.lab,
        "batch_index": args.batch_index,
        "environment": environment,
        "workflow_id": workflow_id,
        "golden_snapshot_id": snapshot["id"],
        "files": [row["file"] for row in rows],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (version_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
