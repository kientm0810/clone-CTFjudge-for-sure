from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.workflow import WorkflowDefinition


class WorkflowCreate(BaseModel):
    definition: WorkflowDefinition
    description: str | None = None


class WorkflowVersionCreate(BaseModel):
    definition: WorkflowDefinition


class WorkflowSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    current_version: int
    created_at: datetime
    updated_at: datetime


class WorkflowDetail(WorkflowSummary):
    definition: WorkflowDefinition


class WorkflowVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_id: str
    version: int
    created_at: datetime
    is_current: bool = False


class WorkflowVersionDetail(WorkflowVersionSummary):
    definition: WorkflowDefinition


class RunCreate(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workflow_version_id: str
    status: str
    result: dict[str, Any] | None
    error: str | None
    celery_task_id: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class RunHistoryItem(RunSummary):
    workflow_id: str
    version_number: int


class NodeRunDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    node_id: str
    node_type: str
    sequence: int
    status: str
    input_data: dict[str, Any]
    output_data: Any = None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None


class RunDetail(RunSummary):
    node_runs: list[NodeRunDetail] = Field(default_factory=list)

