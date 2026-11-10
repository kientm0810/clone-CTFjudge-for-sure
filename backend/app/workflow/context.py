from dataclasses import dataclass, field
from typing import Any


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

