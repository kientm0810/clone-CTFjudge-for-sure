from collections import defaultdict
from typing import Any
from uuid import uuid4

from app.nodes.default_registry import build_default_registry
from app.nodes.registry import NodeRegistry
from app.schemas.workflow import (
    NodeExecutionRecord,
    NodeType,
    WorkflowDefinition,
    WorkflowRunResult,
)
from app.workflow.context import WorkflowContext, WorkflowServices
from app.workflow.exceptions import NodeExecutionError
from app.workflow.observer import ExecutionObserver, NullExecutionObserver
from app.workflow.validator import WorkflowValidator


class WorkflowExecutor:
    def __init__(self, registry: NodeRegistry | None = None) -> None:
        self.registry = registry or build_default_registry()

    async def execute(
        self,
        workflow: WorkflowDefinition,
        runtime_inputs: dict[str, Any],
        services: WorkflowServices,
        run_id: str | None = None,
        observer: ExecutionObserver | None = None,
    ) -> WorkflowRunResult:
        ordered_ids = WorkflowValidator.validate(workflow)
        node_by_id = {node.id: node for node in workflow.nodes}
        incoming: dict[str, list[str]] = defaultdict(list)
        for edge in workflow.edges:
            incoming[edge.target].append(edge.source)

        context = WorkflowContext(
            run_id=run_id or str(uuid4()),
            runtime_inputs=runtime_inputs,
            services=services,
        )
        results: dict[str, Any] = {}
        records: list[NodeExecutionRecord] = []
        execution_observer = observer or NullExecutionObserver()

        for sequence, node_id in enumerate(ordered_ids):
            definition = node_by_id[node_id]
            node_inputs = {source: results[source] for source in incoming[node_id]}
            record = NodeExecutionRecord(
                node_id=node_id,
                node_type=definition.type,
                status="RUNNING",
                input=node_inputs,
            )
            records.append(record)
            try:
                await execution_observer.node_started(definition, node_inputs, sequence)
                implementation = self.registry.create(definition.type)
                node_result = await implementation.execute(definition, node_inputs, context)
                results[node_id] = node_result.value
                context.artifacts[node_id] = {
                    "value": node_result.value,
                    "metadata": node_result.metadata or {},
                }
                record.status = "COMPLETED"
                record.output = node_result.value
                await execution_observer.node_completed(definition, node_result, sequence)
            except Exception as exc:
                record.status = "FAILED"
                record.error = str(exc)
                await execution_observer.node_failed(definition, exc, sequence)
                if isinstance(exc, NodeExecutionError):
                    raise
                raise NodeExecutionError(node_id, str(exc)) from exc

        outputs = {
            node_id: results[node_id]
            for node_id in ordered_ids
            if node_by_id[node_id].type == NodeType.OUTPUT
        }
        return WorkflowRunResult(
            run_id=context.run_id,
            status="COMPLETED",
            outputs=outputs,
            node_runs=records,
        )

