from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.persistence import RunCreate, RunSummary, WorkflowCreate, WorkflowDetail, WorkflowSummary
from app.schemas.workflow import WorkflowDefinition, WorkflowRunRequest, WorkflowRunResult
from app.services.llm_service import LLMService
from app.services.vector_service import PgVectorService
from app.workflow.context import WorkflowServices
from app.workflow.exceptions import WorkflowError
from app.workflow.executor import WorkflowExecutor
from app.workflow.validator import WorkflowValidator
from app.services.workflow_store import WorkflowStore


router = APIRouter(prefix="/workflows", tags=["workflows"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post("/validate")
async def validate_workflow(workflow: WorkflowDefinition) -> dict:
    try:
        execution_order = WorkflowValidator.validate(workflow)
    except WorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"valid": True, "execution_order": execution_order}


@router.post("/execute", response_model=WorkflowRunResult)
async def execute_workflow(request: WorkflowRunRequest) -> WorkflowRunResult:
    services = WorkflowServices(
        llm=LLMService(),
        vector_store=PgVectorService(),
    )
    try:
        return await WorkflowExecutor().execute(
            request.workflow,
            runtime_inputs=request.inputs,
            services=services,
        )
    except WorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=WorkflowDetail, status_code=status.HTTP_201_CREATED)
async def create_workflow(payload: WorkflowCreate, session: SessionDependency) -> WorkflowDetail:
    try:
        WorkflowValidator.validate(payload.definition)
    except WorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    workflow, version = await WorkflowStore(session).create_workflow(payload)
    return WorkflowDetail(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        current_version=workflow.current_version,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        definition=WorkflowDefinition.model_validate(version.definition),
    )


@router.get("", response_model=list[WorkflowSummary])
async def list_workflows(session: SessionDependency) -> list[WorkflowSummary]:
    workflows = await WorkflowStore(session).list_workflows()
    return [WorkflowSummary.model_validate(workflow) for workflow in workflows]


@router.get("/{workflow_id}", response_model=WorkflowDetail)
async def get_workflow(workflow_id: str, session: SessionDependency) -> WorkflowDetail:
    stored = await WorkflowStore(session).get_workflow(workflow_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    workflow, version = stored
    return WorkflowDetail(
        id=workflow.id,
        name=workflow.name,
        description=workflow.description,
        current_version=workflow.current_version,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        definition=WorkflowDefinition.model_validate(version.definition),
    )


@router.post("/{workflow_id}/runs", response_model=RunSummary, status_code=status.HTTP_202_ACCEPTED)
async def start_workflow_run(
    workflow_id: str,
    payload: RunCreate,
    session: SessionDependency,
) -> RunSummary:
    run = await WorkflowStore(session).create_run(workflow_id, payload.inputs)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow not found")

    from app.workers.workflow_task import run_workflow

    task = run_workflow.delay(run.id)
    run.celery_task_id = task.id
    await session.commit()
    await session.refresh(run)
    return RunSummary.model_validate(run)

