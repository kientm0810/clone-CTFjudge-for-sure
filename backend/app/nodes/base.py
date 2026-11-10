from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.schemas.workflow import NodeDefinition
from app.workflow.context import WorkflowContext


@dataclass
class NodeResult:
    value: Any
    metadata: dict[str, Any] | None = None


class BaseNode(ABC):
    @abstractmethod
    async def execute(
        self,
        definition: NodeDefinition,
        inputs: dict[str, Any],
        context: WorkflowContext,
    ) -> NodeResult:
        raise NotImplementedError

