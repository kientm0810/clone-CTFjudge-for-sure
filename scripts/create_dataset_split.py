"""Create the fixed stratified 160/40 train-test split."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datamau/metadata.jsonl"
TARGET = ROOT / "experiments/dataset-split-160-40.json"
TEST_QUOTA_6 = {"excellent": 1, "good": 2, "average": 2, "weak": 1}
TEST_QUOTA_5 = {"excellent": 1, "good": 2, "average": 1, "weak": 1}
SEED = "ctfjudge-split-v1"


def stable_key(filename: str) -> str:
    return hashlib.sha256(f"{SEED}:{filename}".encode()).hexdigest()


rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line]
groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
for row in rows:
    groups[(row["lab_id"], row["quality_level"])].append(row)

test_files: set[str] = set()
for (lab_id, label), items in groups.items():
    if lab_id == "L01_keylogger_ads":
        quota = 0
    elif lab_id <= "L06_process_injection":
        quota = TEST_QUOTA_6[label]
    else:
        quota = TEST_QUOTA_5[label]
    selected = sorted(items, key=lambda item: stable_key(item["file"]))[:quota]
    test_files.update(item["file"] for item in selected)

def compact(row: dict) -> dict:
    return {
        "file": row["file"],
        "lab_id": row["lab_id"],
        "quality_level": row["quality_level"],
    }

train = [compact(row) for row in rows if row["file"] not in test_files]
test = [compact(row) for row in rows if row["file"] in test_files]
train_batches = []
for lab_id in sorted({row["lab_id"] for row in train}):
    lab_rows = sorted(
        (row for row in train if row["lab_id"] == lab_id),
        key=lambda row: row["file"],
    )
    for index in range(0, len(lab_rows), 10):
        train_batches.append({
            "lab_id": lab_id,
            "files": [row["file"] for row in lab_rows[index:index + 10]],
        })

payload = {
    "seed": SEED,
    "strategy": "L01 is train-only because it was used before the split. L02-L06 contribute 6 stratified test files; L07-L08 contribute 5 each.",
    "train": train,
    "test": test,
    "train_batches": train_batches,
}
assert len(payload["train"]) == 160
assert len(payload["test"]) == 40
assert sum(len(batch["files"]) for batch in train_batches) == 160
assert all(len(batch["files"]) <= 10 for batch in train_batches)
TARGET.parent.mkdir(parents=True, exist_ok=True)
TARGET.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {TARGET}: train={len(payload['train'])}, test={len(payload['test'])}")
