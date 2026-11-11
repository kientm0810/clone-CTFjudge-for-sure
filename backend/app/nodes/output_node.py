from app.nodes.base import BaseNode, NodeResult
from app.schemas.workflow import NodeDefinition
from app.workflow.context import WorkflowContext
from app.workflow.exceptions import NodeExecutionError
from app.services.report_service import build_ctfjudge_report


class OutputNode(BaseNode):
    async def execute(
        self,
        definition: NodeDefinition,
        inputs: dict,
        context: WorkflowContext,
    ) -> NodeResult:
        value = next(iter(inputs.values())) if len(inputs) == 1 else inputs
        if definition.config.get("format") == "ctfjudge_report":
            try:
                report_value = value
                retrieval_results = None
                if len(inputs) > 1:
                    report_value = next(
                        (item for item in inputs.values() if isinstance(item, dict) and "competency_matrix" in item),
                        None,
                    )
                    retrieval_source = next(
                        (item for item in inputs.values() if isinstance(item, dict) and "retrieval_results" in item),
                        None,
                    )
                    retrieval_results = retrieval_source.get("retrieval_results") if retrieval_source else None
                value = build_ctfjudge_report(
                    report_value,
                    definition.config.get("formula_weights"),
                    retrieval_results=retrieval_results,
                )
            except ValueError as exc:
                raise NodeExecutionError(definition.id, str(exc)) from exc
        return NodeResult(value=value)

