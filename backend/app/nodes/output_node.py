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
                value = build_ctfjudge_report(value, definition.config.get("formula_weights"))
            except ValueError as exc:
                raise NodeExecutionError(definition.id, str(exc)) from exc
        return NodeResult(value=value)

