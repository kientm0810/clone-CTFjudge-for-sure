from types import SimpleNamespace

from app.api.runs import _owned_vector_collections


def test_owned_vector_collections_only_returns_run_scoped_collections() -> None:
    run_id = "run-123"
    node_runs = [
        SimpleNamespace(output_data={"collection": "comparison-run-123"}),
        SimpleNamespace(output_data={"collection": "shared-golden-solutions"}),
        SimpleNamespace(output_data={"retrieval_results": []}),
        SimpleNamespace(output_data=None),
    ]

    assert _owned_vector_collections(run_id, node_runs) == {"comparison-run-123"}
