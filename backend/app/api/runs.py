from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.persistence import NodeRunDetail, RunDetail, RunSummary
from app.services.workflow_store import WorkflowStore


router = APIRouter(prefix="/runs", tags=["runs"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, session: SessionDependency) -> RunDetail:
    run = await WorkflowStore(session).get_run(run_id, include_nodes=True)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return RunDetail(
        **RunSummary.model_validate(run).model_dump(),
        node_runs=[NodeRunDetail.model_validate(node_run) for node_run in run.node_runs],
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

