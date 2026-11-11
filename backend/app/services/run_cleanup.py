from collections.abc import Iterable
from typing import Any


def owned_vector_collections(run_id: str, node_runs: Iterable[Any]) -> set[str]:
    """Return vector collections that are clearly scoped to one workflow run."""
    collections: set[str] = set()
    for node_run in node_runs:
        output = node_run.output_data
        if not isinstance(output, dict):
            continue
        collection = output.get("collection")
        if isinstance(collection, str) and run_id in collection:
            collections.add(collection)
    return collections

