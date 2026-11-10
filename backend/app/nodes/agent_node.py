import json

from app.nodes.base import BaseNode, NodeResult
from app.schemas.workflow import NodeDefinition
from app.workflow.context import WorkflowContext
from app.workflow.exceptions import NodeExecutionError


class AgentNode(BaseNode):
    async def execute(
        self,
        definition: NodeDefinition,
        inputs: dict,
        context: WorkflowContext,
    ) -> NodeResult:
        prompt = definition.config.get("prompt")
        if not prompt:
            raise NodeExecutionError(definition.id, "Agent node requires a prompt")

        payload = json.dumps(inputs, ensure_ascii=False, indent=2)
        rendered_prompt = f"{prompt}\n\nINPUT DATA:\n{payload}"
        result = await context.services.llm.complete(
            prompt=rendered_prompt,
            model=definition.config.get("model"),
            temperature=definition.config.get("temperature"),
            output_schema=definition.config.get("output_schema"),
        )
        return NodeResult(
            value=result,
            metadata={"model": definition.config.get("model", "default")},
        )

