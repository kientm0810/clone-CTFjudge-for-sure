from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class NodeType(StrEnum):
    INPUT = "input"
    AGENT = "agent"
    DATABASE = "database"
    OUTPUT = "output"


class NodePosition(BaseModel):
    x: float
    y: float


class NodeDefinition(BaseModel):
    id: str = Field(min_length=1)
    type: NodeType
    name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    position: NodePosition | None = None


class EdgeDefinition(BaseModel):
    source: str
    target: str
    source_handle: str = "output"
    target_handle: str = "input"


class WorkflowDefinition(BaseModel):
    name: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    nodes: list[NodeDefinition] = Field(min_length=1)
    edges: list[EdgeDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def node_ids_are_unique(self) -> "WorkflowDefinition":
        ids = [node.id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("Workflow node IDs must be unique")
        return self


class WorkflowRunRequest(BaseModel):
    workflow: WorkflowDefinition
    inputs: dict[str, Any] = Field(default_factory=dict)


class NodeExecutionRecord(BaseModel):
    node_id: str
    node_type: NodeType
    status: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    error: str | None = None


class WorkflowRunResult(BaseModel):
    run_id: str
    status: str
    outputs: dict[str, Any] = Field(default_factory=dict)
    node_runs: list[NodeExecutionRecord] = Field(default_factory=list)

