from typing import Any, Protocol

from app.nodes.base import NodeResult
from app.schemas.workflow import NodeDefinition


class ExecutionObserver(Protocol):
    async def node_started(
        self,
        definition: NodeDefinition,
        inputs: dict[str, Any],
        sequence: int,
    ) -> None: ...

    async def node_completed(
        self,
        definition: NodeDefinition,
        result: NodeResult,
        sequence: int,
    ) -> None: ...

    async def node_failed(
        self,
        definition: NodeDefinition,
        error: Exception,
        sequence: int,
    ) -> None: ...


class NullExecutionObserver:
    async def node_started(self, definition: NodeDefinition, inputs: dict, sequence: int) -> None:
        return None

    async def node_completed(self, definition: NodeDefinition, result: NodeResult, sequence: int) -> None:
        return None

    async def node_failed(self, definition: NodeDefinition, error: Exception, sequence: int) -> None:
        return None

