from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class WorkflowServices:
    llm: Any
    vector_store: Any


@dataclass
class WorkflowContext:
    run_id: str
    runtime_inputs: dict[str, Any]
    services: WorkflowServices
    artifacts: dict[str, Any] = field(default_factory=dict)
    progress_callback: ProgressCallback | None = None

    async def report_progress(self, node_id: str, update: dict[str, Any]) -> None:
        if self.progress_callback is not None:
            await self.progress_callback(node_id, update)

