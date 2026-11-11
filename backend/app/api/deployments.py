from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.persistence import RunCreate, RunSummary, WorkflowDeploymentDetail
from app.schemas.workflow import WorkflowDefinition
from app.services.workflow_store import WorkflowStore


router = APIRouter(prefix="/deployments", tags=["deployments"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def deployment_detail(stored) -> WorkflowDeploymentDetail:
    deployment, workflow, version = stored
    return WorkflowDeploymentDetail(
        environment=deployment.environment,
        workflow_id=workflow.id,
        workflow_name=workflow.name,
        workflow_version_id=version.id,
        version_number=version.version,
        published_at=deployment.published_at,
        updated_at=deployment.updated_at,
        definition=WorkflowDefinition.model_validate(version.definition),
    )


@router.get("/{environment}", response_model=WorkflowDeploymentDetail)
async def get_deployment(environment: str, session: SessionDependency) -> WorkflowDeploymentDetail:
    stored = await WorkflowStore(session).get_deployment(environment)
    if stored is None:
        raise HTTPException(status_code=404, detail="Chưa có workflow nào được publish lên môi trường này.")
    return deployment_detail(stored)


@router.post("/{environment}/runs", response_model=RunSummary, status_code=status.HTTP_202_ACCEPTED)
async def start_deployment_run(
    environment: str,
    payload: RunCreate,
    session: SessionDependency,
) -> RunSummary:
    store = WorkflowStore(session)
    stored = await store.get_deployment(environment)
    if stored is None:
        raise HTTPException(status_code=404, detail="Chưa có workflow nào được publish lên môi trường này.")
    deployment, _, _ = stored
    run = await store.create_run_for_version(deployment.workflow_version_id, payload.inputs)
    if run is None:
        raise HTTPException(status_code=409, detail="Version đã publish không còn tồn tại.")

    from app.workers.workflow_task import run_workflow

    task = run_workflow.delay(run.id)
    run.celery_task_id = task.id
    await session.commit()
    await session.refresh(run)
    return RunSummary.model_validate(run)
