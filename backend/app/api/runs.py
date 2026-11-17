from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.models.provider import AIModelConnection
from app.models.workflow import WorkflowVersion
from app.schemas.persistence import NodeRunDetail, RunDetail, RunSummary
from app.schemas.persistence import ExecutionProgressDetail
from app.schemas.workflow import WorkflowDefinition
from app.services.execution_progress import list_execution_progress
from app.services.html_report_service import build_run_html_report
from app.services.run_cleanup import owned_vector_collections
from app.services.workflow_store import WorkflowStore
from app.services.vector_service import PgVectorService


router = APIRouter(prefix="/runs", tags=["runs"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/{run_id}/report.html")
async def download_run_html_report(run_id: str, session: SessionDependency) -> Response:
    run = await WorkflowStore(session).get_run(run_id, include_nodes=True)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if run.status != "COMPLETED":
        raise HTTPException(status_code=409, detail="Chỉ có thể tải báo cáo khi run đã hoàn tất.")

    version = await session.get(WorkflowVersion, run.workflow_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Workflow version for this run no longer exists")

    definition = WorkflowDefinition.model_validate(version.definition)
    settings = get_settings()
    references = {
        str(node.config.get("model") or settings.default_chat_model)
        for node in definition.nodes
        if node.type.value == "agent"
    }
    registered_ids = [
        reference.split("/", 1)[1]
        for reference in references
        if reference.startswith("registered/") and "/" in reference
    ]
    connections = list(
        await session.scalars(
            select(AIModelConnection).where(AIModelConnection.id.in_(registered_ids))
        )
    ) if registered_ids else []
    connections_by_id = {item.id: item for item in connections}
    model_names: dict[str, str] = {}
    for node in definition.nodes:
        if node.type.value != "agent":
            continue
        reference = str(node.config.get("model") or settings.default_chat_model)
        if reference.startswith("registered/"):
            connection = connections_by_id.get(reference.split("/", 1)[1])
            model_names[node.id] = (
                f"{connection.name} · {connection.model_name}" if connection else reference
            )
        else:
            model_names[node.id] = reference

    progress = await list_execution_progress("run", run.id)
    html = build_run_html_report(run, definition, progress, model_names)
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="ctfjudge-{run.id[:8]}.html"'
        },
    )


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, session: SessionDependency) -> RunDetail:
    run = await WorkflowStore(session).get_run(run_id, include_nodes=True)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    progress_by_node = {
        item.node_id: item for item in await list_execution_progress("run", run.id)
    }
    return RunDetail(
        **RunSummary.model_validate(run).model_dump(),
        node_runs=[
            NodeRunDetail(
                **NodeRunDetail.model_validate(node_run).model_dump(exclude={"progress"}),
                progress=(
                    ExecutionProgressDetail.model_validate(progress_by_node[node_run.node_id])
                    if node_run.node_id in progress_by_node
                    else None
                ),
            )
            for node_run in run.node_runs
        ],
    )


@router.get("/{run_id}/result")
async def get_run_result(run_id: str, session: SessionDependency) -> dict:
    run = await WorkflowStore(session).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if run.status in {"PENDING", "RUNNING"}:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail={"status": run.status, "message": "Workflow is still running"},
        )
    if run.status == "FAILED":
        raise HTTPException(status_code=422, detail={"status": run.status, "error": run.error})
    return run.result or {}


@router.post("/{run_id}/retry", response_model=RunSummary, status_code=status.HTTP_202_ACCEPTED)
async def retry_run(run_id: str, session: SessionDependency) -> RunSummary:
    store = WorkflowStore(session)
    run = await store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if run.status in {"PENDING", "RUNNING"}:
        raise HTTPException(status_code=409, detail="Workflow run is already active")

    await store.reset_run(run)
    from app.workers.workflow_task import run_workflow

    task = run_workflow.delay(run.id)
    run.celery_task_id = task.id
    await session.commit()
    await session.refresh(run)
    return RunSummary.model_validate(run)


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(run_id: str, session: SessionDependency) -> None:
    store = WorkflowStore(session)
    run = await store.get_run(run_id, include_nodes=True)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if run.status in {"PENDING", "RUNNING"}:
        raise HTTPException(status_code=409, detail="Active workflow runs cannot be deleted")

    collections = owned_vector_collections(run.id, run.node_runs)
    await PgVectorService().delete_collections(collections)
    await store.delete_run(run)

