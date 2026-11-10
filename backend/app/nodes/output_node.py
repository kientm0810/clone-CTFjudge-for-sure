from app.nodes.base import BaseNode, NodeResult
from app.schemas.workflow import NodeDefinition
from app.workflow.context import WorkflowContext


class OutputNode(BaseNode):
    async def execute(
        self,
        definition: NodeDefinition,
        inputs: dict,
        context: WorkflowContext,
    ) -> NodeResult:
        if len(inputs) == 1:
            return NodeResult(value=next(iter(inputs.values())))
        return NodeResult(value=inputs)

