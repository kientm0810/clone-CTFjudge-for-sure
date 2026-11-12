from typing import Any

import pytest

from app.schemas.workflow import WorkflowDefinition
from app.workflow.context import WorkflowServices
from app.workflow.executor import WorkflowExecutor
from app.workflow.exceptions import WorkflowValidationError
from app.workflow.validator import WorkflowValidator


class FakeLLM:
    async def complete(self, **kwargs: Any) -> dict:
        return {"summary": "processed", "prompt_received": bool(kwargs.get("prompt"))}


class FakeVectorStore:
    async def upsert(self, **kwargs: Any) -> dict:
        return {"indexed_chunks": len(kwargs["chunks"])}

    async def search(self, **kwargs: Any) -> list:
        return []


class RagLLM:
    async def complete(self, **kwargs: Any) -> dict:
        prompt = kwargs["prompt"]
        if "golden solution" in prompt:
            return {
                "chunks": [
                    {
                        "chunk_id": "golden-1",
                        "document_id": "golden-doc",
                        "content": "Use parameterized SQL queries.",
                    }
                ]
            }
        if "student submission" in prompt:
            return {
                "chunks": [
                    {
                        "chunk_id": "student-1",
                        "document_id": "student-doc",
                        "content": "Use prepared statements.",
                    }
                ]
            }
        return {
            "summary_score": 0.9,
            "summary": "The answer matches the golden solution.",
            "comparisons": [
                {
                    "student_chunk_id": "student-1",
                    "student_content": "Use prepared statements.",
                    "classification": "paraphrase",
                    "score": 0.9,
                    "explanation": "Prepared statements are parameterized queries.",
                    "matched_golden": [
                        {
                            "chunk_id": "golden-1",
                            "content": "Use parameterized SQL queries.",
                            "similarity_score": 0.92,
                        }
                    ],
                }
            ],
        }


class RagVectorStore:
    def __init__(self) -> None:
        self.upsert_collection: str | None = None
        self.search_collection: str | None = None

    async def upsert(self, **kwargs: Any) -> dict:
        self.upsert_collection = kwargs["collection"]
        return {"indexed_chunks": len(kwargs["chunks"]), "collection": kwargs["collection"]}

    async def search(self, **kwargs: Any) -> list:
        self.search_collection = kwargs["collection"]
        chunk = kwargs["query_chunks"][0]
        return [
            {
                "student_chunk_id": chunk["chunk_id"],
                "student_content": chunk["content"],
                "candidates": [
                    {
                        "golden_chunk_id": "golden-1",
                        "content": "Use parameterized SQL queries.",
                        "similarity_score": 0.92,
                    }
                ],
            }
        ]


@pytest.mark.asyncio
async def test_executor_runs_input_agent_output() -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "simple",
            "nodes": [
                {
                    "id": "student-input",
                    "type": "input",
                    "config": {"input_key": "student", "document_type": "student_submission"},
                },
                {
                    "id": "student-agent",
                    "type": "agent",
                    "config": {"prompt": "Summarize the submission as JSON."},
                },
                {"id": "report", "type": "output"},
            ],
            "edges": [
                {"source": "student-input", "target": "student-agent"},
                {"source": "student-agent", "target": "report"},
            ],
        }
    )
    result = await WorkflowExecutor().execute(
        workflow,
        runtime_inputs={"student": "student answer"},
        services=WorkflowServices(llm=FakeLLM(), vector_store=FakeVectorStore()),
    )

    assert result.status == "COMPLETED"
    assert result.outputs["report"]["summary"] == "processed"
    assert [record.status for record in result.node_runs] == ["COMPLETED"] * 3


@pytest.mark.asyncio
async def test_executor_runs_isolated_rag_comparison() -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "rag-comparison",
            "nodes": [
                {"id": "golden-input", "type": "input", "config": {"input_key": "golden"}},
                {
                    "id": "golden-parser",
                    "type": "agent",
                    "inputs": {"document": "{{ steps.golden-input.output }}"},
                    "config": {"prompt": "Chunk the golden solution."},
                },
                {
                    "id": "golden-index",
                    "type": "database",
                    "inputs": {"chunks": "{{ steps.golden-parser.output.chunks }}"},
                    "config": {"operation": "upsert", "collection": "comparison-{{run_id}}"},
                },
                {"id": "student-input", "type": "input", "config": {"input_key": "student"}},
                {
                    "id": "student-parser",
                    "type": "agent",
                    "inputs": {"document": "{{ steps.student-input.output }}"},
                    "config": {"prompt": "Chunk the student submission."},
                },
                {
                    "id": "golden-search",
                    "type": "database",
                    "inputs": {"query_chunks": "{{ steps.student-parser.output.chunks }}"},
                    "config": {"operation": "search", "collection": "comparison-{{run_id}}"},
                },
                {
                    "id": "comparison-agent",
                    "type": "agent",
                    "inputs": {
                        "retrieval_results": "{{ steps.golden-search.output.retrieval_results }}"
                    },
                    "config": {"prompt": "Compare retrieved candidates."},
                },
                {
                    "id": "report",
                    "type": "output",
                    "inputs": {
                        "analysis": "{{ steps.comparison-agent.output }}",
                        "retrieval_results": "{{ steps.golden-search.output.retrieval_results }}",
                        "golden_chunks": "{{ steps.golden-parser.output.chunks }}",
                    },
                    "config": {"format": "comparison_report"},
                },
            ],
            "edges": [
                {"source": "golden-input", "target": "golden-parser"},
                {"source": "golden-parser", "target": "golden-index"},
                {"source": "student-input", "target": "student-parser"},
                {"source": "golden-index", "target": "golden-search"},
                {"source": "student-parser", "target": "golden-search"},
                {"source": "golden-search", "target": "comparison-agent"},
                {"source": "comparison-agent", "target": "report"},
            ],
        }
    )
    vector_store = RagVectorStore()

    result = await WorkflowExecutor().execute(
        workflow,
        runtime_inputs={"golden": "Use parameterized SQL queries.", "student": "Use prepared statements."},
        services=WorkflowServices(llm=RagLLM(), vector_store=vector_store),
        run_id="run-123",
    )

    assert result.status == "COMPLETED"
    assert result.outputs["report"]["comparisons"][0]["classification"] == "paraphrase"
    assert vector_store.upsert_collection == "comparison-run-123"
    assert vector_store.search_collection == "comparison-run-123"
    assert [record.status for record in result.node_runs] == ["COMPLETED"] * 8
    report_run = next(record for record in result.node_runs if record.node_id == "report")
    assert report_run.input["golden_chunks"][0]["chunk_id"] == "golden-1"
    assert report_run.input["retrieval_results"][0]["student_chunk_id"] == "student-1"


def test_validator_rejects_expression_from_unconnected_branch() -> None:
    workflow = WorkflowDefinition.model_validate(
        {
            "name": "invalid-cross-branch-reference",
            "nodes": [
                {"id": "input-a", "type": "input"},
                {"id": "input-b", "type": "input"},
                {
                    "id": "agent-a",
                    "type": "agent",
                    "inputs": {"document": "{{ steps.input-b.output }}"},
                    "config": {"prompt": "A"},
                },
                {"id": "agent-b", "type": "agent", "config": {"prompt": "B"}},
                {"id": "output", "type": "output"},
            ],
            "edges": [
                {"source": "input-a", "target": "agent-a"},
                {"source": "input-b", "target": "agent-b"},
                {"source": "agent-a", "target": "output"},
                {"source": "agent-b", "target": "output"},
            ],
        }
    )

    with pytest.raises(WorkflowValidationError, match="connected upstream"):
        WorkflowValidator.validate(workflow)

