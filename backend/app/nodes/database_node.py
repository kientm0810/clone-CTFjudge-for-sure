from typing import Any

from app.config import get_settings
from app.nodes.base import BaseNode, NodeResult
from app.schemas.workflow import NodeDefinition
from app.workflow.context import WorkflowContext
from app.workflow.exceptions import NodeExecutionError


def _find_list_by_keys(value: Any, keys: tuple[str, ...]) -> list[dict]:
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, list):
                return candidate
        for nested in value.values():
            found = _find_list_by_keys(nested, keys)
            if found:
                return found
    if isinstance(value, list):
        for nested in value:
            found = _find_list_by_keys(nested, keys)
            if found:
                return found
    return []


class DatabaseNode(BaseNode):
    async def execute(
        self,
        definition: NodeDefinition,
        inputs: dict,
        context: WorkflowContext,
    ) -> NodeResult:
        operation = definition.config.get("operation")
        collection_template = str(definition.config.get("collection", "golden-solutions"))
        collection = collection_template.replace("{{run_id}}", context.run_id)
        embedding_model = definition.config.get(
            "embedding_model",
            get_settings().default_embedding_model,
        )

        if operation == "upsert":
            chunks = inputs.get("chunks") if isinstance(inputs.get("chunks"), list) else None
            chunks = chunks or _find_list_by_keys(inputs, ("chunks",))
            if not chunks:
                raise NodeExecutionError(definition.id, "Upsert requires an input containing 'chunks'")
            result = await context.services.vector_store.upsert(
                collection=collection,
                chunks=chunks,
                embedding_model=embedding_model,
            )
            return NodeResult(value=result)

        if operation == "search":
            query_chunks = inputs.get("query_chunks") if isinstance(inputs.get("query_chunks"), list) else None
            query_chunks = query_chunks or _find_list_by_keys(inputs, ("query_chunks", "chunks"))
            if not query_chunks:
                raise NodeExecutionError(definition.id, "Search requires query chunks")
            result = await context.services.vector_store.search(
                collection=collection,
                query_chunks=query_chunks,
                embedding_model=embedding_model,
                top_k=int(definition.config.get("top_k", 5)),
                score_threshold=float(definition.config.get("score_threshold", 0.4)),
            )
            return NodeResult(value={"retrieval_results": result})

        raise NodeExecutionError(definition.id, "Database operation must be 'upsert' or 'search'")

