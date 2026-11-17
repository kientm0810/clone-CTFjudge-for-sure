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
from app.workflow.expressions import resolve_inputs
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
        initial_results: dict[str, Any] | None = None,
        target_node_ids: set[str] | None = None,
        result_sink: dict[str, Any] | None = None,
    ) -> WorkflowRunResult:
        ordered_ids = WorkflowValidator.validate(workflow)
        node_by_id = {node.id: node for node in workflow.nodes}
        incoming: dict[str, list[str]] = defaultdict(list)
        for edge in workflow.edges:
            incoming[edge.target].append(edge.source)

        selected_ids = set(ordered_ids)
        if target_node_ids is not None:
            missing_targets = target_node_ids - set(node_by_id)
            if missing_targets:
                raise NodeExecutionError(
                    next(iter(missing_targets)),
                    "Snapshot target does not exist in this workflow version",
                )
            selected_ids = set()
            pending = list(target_node_ids)
            while pending:
                current = pending.pop()
                if current in selected_ids:
                    continue
                selected_ids.add(current)
                pending.extend(incoming[current])

        context = WorkflowContext(
            run_id=run_id or str(uuid4()),
            runtime_inputs=runtime_inputs,
            services=services,
        )
        results: dict[str, Any] = dict(initial_results or {})
        context.artifacts.update(
            {
                node_id: {"value": value, "metadata": {"frozen": True}}
                for node_id, value in results.items()
            }
        )
        if result_sink is not None:
            result_sink.update(results)
        records: list[NodeExecutionRecord] = []
        execution_observer = observer or NullExecutionObserver()
        context.progress_callback = lambda node_id, update: execution_observer.node_progress(
            node_by_id[node_id],
            update,
        )

        for sequence, node_id in enumerate(ordered_ids):
            if node_id not in selected_ids:
                continue
            definition = node_by_id[node_id]
            if node_id in results:
                records.append(
                    NodeExecutionRecord(
                        node_id=node_id,
                        node_type=definition.type,
                        status="FROZEN",
                        input={},
                        output=results[node_id],
                    )
                )
                continue
            legacy_inputs = {source: results[source] for source in incoming[node_id]}
            record = NodeExecutionRecord(
                node_id=node_id,
                node_type=definition.type,
                status="RUNNING",
                input={},
            )
            records.append(record)
            observer_started = False
            try:
                node_inputs = (
                    resolve_inputs(
                        definition.inputs,
                        results=results,
                        runtime_inputs=runtime_inputs,
                        run_id=context.run_id,
                    )
                    if definition.inputs
                    else legacy_inputs
                )
                record.input = node_inputs
                await execution_observer.node_started(definition, node_inputs, sequence)
                observer_started = True
                implementation = self.registry.create(definition.type)
                node_result = await implementation.execute(definition, node_inputs, context)
                results[node_id] = node_result.value
                if result_sink is not None:
                    result_sink[node_id] = node_result.value
                context.artifacts[node_id] = {
                    "value": node_result.value,
                    "metadata": node_result.metadata or {},
                }
                record.status = "COMPLETED"
                record.output = node_result.value
                await execution_observer.node_completed(definition, node_result, sequence)
            except Exception as exc:
                error_message = str(exc).strip() or exc.__class__.__name__
                record.status = "FAILED"
                record.error = error_message
                if not observer_started:
                    await execution_observer.node_started(definition, {}, sequence)
                await execution_observer.node_failed(definition, exc, sequence)
                if isinstance(exc, NodeExecutionError):
                    raise
                raise NodeExecutionError(node_id, error_message) from exc

        outputs = {
            node_id: results[node_id]
            for node_id in ordered_ids
            if node_id in results and node_by_id[node_id].type == NodeType.OUTPUT
        }
        return WorkflowRunResult(
            run_id=context.run_id,
            status="COMPLETED",
            outputs=outputs,
            node_runs=records,
        )

