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

        async def report_progress(update: dict) -> None:
            await context.report_progress(definition.id, update)

        result = await context.services.llm.complete(
            prompt=rendered_prompt,
            model=definition.config.get("model"),
            temperature=definition.config.get("temperature"),
            output_schema=definition.config.get("output_schema"),
            max_tokens=int(definition.config.get("max_tokens", 4096)),
            progress_callback=report_progress,
        )
        return NodeResult(
            value=result,
            metadata={"model": definition.config.get("model", "default")},
        )

