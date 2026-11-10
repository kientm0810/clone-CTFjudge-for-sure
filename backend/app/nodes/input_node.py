from uuid import uuid4

from app.nodes.base import BaseNode, NodeResult
from app.schemas.workflow import NodeDefinition
from app.workflow.context import WorkflowContext
from app.workflow.exceptions import NodeExecutionError


class InputNode(BaseNode):
    async def execute(
        self,
        definition: NodeDefinition,
        inputs: dict,
        context: WorkflowContext,
    ) -> NodeResult:
        input_key = definition.config.get("input_key", definition.id)
        if input_key not in context.runtime_inputs:
            raise NodeExecutionError(definition.id, f"Missing runtime input '{input_key}'")

        raw_value = context.runtime_inputs[input_key]
        if isinstance(raw_value, dict) and "content" in raw_value:
            document = dict(raw_value)
            document.setdefault("document_id", str(uuid4()))
            document.setdefault("document_type", definition.config.get("document_type", "generic"))
            document.setdefault("metadata", {})
        else:
            document = {
                "document_id": str(uuid4()),
                "document_type": definition.config.get("document_type", "generic"),
                "content": str(raw_value),
                "metadata": {},
            }
        return NodeResult(value=document)

