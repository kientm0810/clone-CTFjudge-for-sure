from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.workflow import Workflow
from app.schemas.persistence import (
    RunCreate,
    RunHistoryItem,
    RunSummary,
    WorkflowCreate,
    WorkflowDetail,
    WorkflowSummary,
    WorkflowVersionCreate,
    WorkflowVersionDetail,
    WorkflowVersionSummary,
)
from app.schemas.workflow import WorkflowDefinition, WorkflowRunRequest, WorkflowRunResult
from app.services.llm_service import LLMService
from app.services.run_cleanup import owned_vector_collections
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


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(workflow_id: str, session: SessionDependency) -> None:
    store = WorkflowStore(session)
    runs = await store.list_all_runs_with_nodes(workflow_id)
    if runs is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if any(run.status in {"PENDING", "RUNNING"} for run in runs):
        raise HTTPException(
            status_code=409,
            detail="Workflow đang chạy. Hãy đợi chạy xong rồi mới xóa.",
        )

    collections = set().union(
        *(owned_vector_collections(run.id, run.node_runs) for run in runs),
    ) if runs else set()
    await PgVectorService().delete_collections(collections)
    await store.delete_workflow(workflow_id)


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


@router.get("/{workflow_id}/versions", response_model=list[WorkflowVersionSummary])
async def list_workflow_versions(
    workflow_id: str,
    session: SessionDependency,
) -> list[WorkflowVersionSummary]:
    stored = await WorkflowStore(session).list_versions(workflow_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    workflow, versions = stored
    return [
        WorkflowVersionSummary(
            id=version.id,
            workflow_id=version.workflow_id,
            version=version.version,
            created_at=version.created_at,
            is_current=version.version == workflow.current_version,
        )
        for version in versions
    ]


@router.get("/{workflow_id}/versions/{version_number}", response_model=WorkflowVersionDetail)
async def get_workflow_version(
    workflow_id: str,
    version_number: int,
    session: SessionDependency,
) -> WorkflowVersionDetail:
    store = WorkflowStore(session)
    version = await store.get_version(workflow_id, version_number)
    if version is None:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    workflow = await session.get(Workflow, workflow_id)
    return WorkflowVersionDetail(
        id=version.id,
        workflow_id=version.workflow_id,
        version=version.version,
        created_at=version.created_at,
        is_current=bool(workflow and workflow.current_version == version.version),
        definition=WorkflowDefinition.model_validate(version.definition),
    )


@router.delete("/{workflow_id}/versions/{version_number}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_version(
    workflow_id: str,
    version_number: int,
    session: SessionDependency,
) -> None:
    store = WorkflowStore(session)
    workflow = await session.get(Workflow, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    version = await store.get_version(workflow_id, version_number)
    if version is None:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    if workflow.current_version == version_number:
        raise HTTPException(
            status_code=409,
            detail="Không thể xóa version đang ACTIVE. Hãy rollback sang version khác trước.",
        )

    runs = await store.list_version_runs_with_nodes(version.id)
    if any(run.status in {"PENDING", "RUNNING"} for run in runs):
        raise HTTPException(
            status_code=409,
            detail="Version đang có workflow chạy. Hãy đợi chạy xong rồi mới xóa.",
        )
    collections = set().union(
        *(owned_vector_collections(run.id, run.node_runs) for run in runs),
    ) if runs else set()
    await PgVectorService().delete_collections(collections)
    await store.delete_version(version.id)


@router.post("/{workflow_id}/versions", response_model=WorkflowDetail, status_code=status.HTTP_201_CREATED)
async def create_workflow_version(
    workflow_id: str,
    payload: WorkflowVersionCreate,
    session: SessionDependency,
) -> WorkflowDetail:
    try:
        WorkflowValidator.validate(payload.definition)
    except WorkflowError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    stored = await WorkflowStore(session).create_version(workflow_id, payload.definition)
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


@router.post("/{workflow_id}/versions/{version_number}/activate", response_model=WorkflowDetail)
async def activate_workflow_version(
    workflow_id: str,
    version_number: int,
    session: SessionDependency,
) -> WorkflowDetail:
    stored = await WorkflowStore(session).activate_version(workflow_id, version_number)
    if stored is None:
        raise HTTPException(status_code=404, detail="Workflow version not found")
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


@router.get("/{workflow_id}/runs", response_model=list[RunHistoryItem])
async def list_workflow_runs(
    workflow_id: str,
    session: SessionDependency,
    limit: int = 50,
) -> list[RunHistoryItem]:
    rows = await WorkflowStore(session).list_runs(workflow_id, min(max(limit, 1), 200))
    if rows is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return [
        RunHistoryItem(
            **RunSummary.model_validate(run).model_dump(),
            workflow_id=workflow_id,
            version_number=version.version,
        )
        for run, version in rows
    ]

