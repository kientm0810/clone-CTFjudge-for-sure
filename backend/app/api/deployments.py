from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.workflow import GoldenSnapshot
from app.schemas.persistence import (
    BatchRunCreate,
    BatchRunItem,
    GoldenSnapshotCreate,
    GoldenSnapshotDetail,
    RunCreate,
    RunSummary,
    WorkflowDeploymentDetail,
)
from app.schemas.workflow import WorkflowDefinition
from app.services.golden_snapshot_service import (
    find_golden_freeze_node,
    get_active_snapshot,
    snapshot_content_hash,
    snapshot_detail,
)
from app.services.execution_progress import list_execution_progress
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


@router.get(
    "/{environment}/golden-snapshot",
    response_model=GoldenSnapshotDetail,
)
async def get_deployment_golden_snapshot(
    environment: str,
    session: SessionDependency,
) -> GoldenSnapshotDetail:
    stored = await WorkflowStore(session).get_deployment(environment)
    if stored is None:
        raise HTTPException(status_code=404, detail="Chưa có workflow nào được publish lên môi trường này.")
    deployment, _, _ = stored
    snapshot = await get_active_snapshot(session, deployment.workflow_version_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Chưa có golden solution được chuẩn bị.")
    progress = await list_execution_progress("snapshot", snapshot.id)
    return snapshot_detail(snapshot, progress)


@router.post(
    "/{environment}/golden-snapshots",
    response_model=GoldenSnapshotDetail,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_deployment_golden_snapshot(
    environment: str,
    payload: GoldenSnapshotCreate,
    session: SessionDependency,
) -> GoldenSnapshotDetail:
    stored = await WorkflowStore(session).get_deployment(environment)
    if stored is None:
        raise HTTPException(status_code=404, detail="Chưa có workflow nào được publish lên môi trường này.")
    deployment, _, version = stored
    definition = WorkflowDefinition.model_validate(version.definition)
    expected_node_id = find_golden_freeze_node(definition)
    if expected_node_id is None:
        raise HTTPException(
            status_code=422,
            detail="Workflow này chưa có database node upsert dành cho golden solution.",
        )
    requested_node_id = payload.frozen_node_id or expected_node_id
    if requested_node_id != expected_node_id:
        raise HTTPException(
            status_code=422,
            detail=f"Node được phép freeze là '{expected_node_id}'.",
        )
    in_progress = await session.scalar(
        select(GoldenSnapshot.id).where(
            GoldenSnapshot.workflow_version_id == deployment.workflow_version_id,
            GoldenSnapshot.status.in_(["PENDING", "RUNNING"]),
        ).limit(1)
    )
    if in_progress:
        raise HTTPException(status_code=409, detail="Một golden snapshot khác đang được chuẩn bị.")

    snapshot = GoldenSnapshot(
        workflow_version_id=deployment.workflow_version_id,
        frozen_node_id=expected_node_id,
        status="PENDING",
        input_data=payload.inputs,
        content_hash=snapshot_content_hash(payload.inputs),
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)

    from app.workers.workflow_task import prepare_golden_snapshot

    prepare_golden_snapshot.delay(snapshot.id)
    return snapshot_detail(snapshot)


@router.get(
    "/{environment}/golden-snapshots/{snapshot_id}",
    response_model=GoldenSnapshotDetail,
)
async def get_deployment_golden_snapshot_by_id(
    environment: str,
    snapshot_id: str,
    session: SessionDependency,
) -> GoldenSnapshotDetail:
    stored = await WorkflowStore(session).get_deployment(environment)
    if stored is None:
        raise HTTPException(status_code=404, detail="Chưa có workflow nào được publish lên môi trường này.")
    deployment, _, _ = stored
    snapshot = await session.get(GoldenSnapshot, snapshot_id)
    if snapshot is None or snapshot.workflow_version_id != deployment.workflow_version_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy golden snapshot này.")
    progress = await list_execution_progress("snapshot", snapshot.id)
    return snapshot_detail(snapshot, progress)


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
    deployment, _, version = stored
    definition = WorkflowDefinition.model_validate(version.definition)
    run_inputs = dict(payload.inputs)
    if find_golden_freeze_node(definition):
        snapshot = await get_active_snapshot(session, deployment.workflow_version_id)
        if snapshot is None:
            raise HTTPException(
                status_code=409,
                detail="Hãy chuẩn bị và freeze golden solution trước khi chấm bài.",
            )
        run_inputs["__golden_snapshot_id"] = snapshot.id
    run = await store.create_run_for_version(deployment.workflow_version_id, run_inputs)
    if run is None:
        raise HTTPException(status_code=409, detail="Version đã publish không còn tồn tại.")

    from app.workers.workflow_task import run_workflow

    task = run_workflow.delay(run.id)
    run.celery_task_id = task.id
    await session.commit()
    await session.refresh(run)
    return RunSummary.model_validate(run)


@router.post(
    "/{environment}/runs/batch",
    response_model=list[BatchRunItem],
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_deployment_batch_runs(
    environment: str,
    payload: BatchRunCreate,
    session: SessionDependency,
) -> list[BatchRunItem]:
    store = WorkflowStore(session)
    stored = await store.get_deployment(environment)
    if stored is None:
        raise HTTPException(status_code=404, detail="Chưa có workflow được publish lên môi trường này.")
    deployment, _, version = stored
    definition = WorkflowDefinition.model_validate(version.definition)
    snapshot = None
    if find_golden_freeze_node(definition):
        snapshot = await get_active_snapshot(session, deployment.workflow_version_id)
        if snapshot is None:
            raise HTTPException(
                status_code=409,
                detail="Hãy chuẩn bị và freeze golden solution trước khi chấm batch.",
            )

    from app.workers.workflow_task import run_workflow

    created: list[BatchRunItem] = []
    for submission in payload.submissions:
        run_inputs = dict(submission.inputs)
        run_inputs["__submission_filename"] = submission.filename
        if snapshot is not None:
            run_inputs["__golden_snapshot_id"] = snapshot.id
        run = await store.create_run_for_version(deployment.workflow_version_id, run_inputs)
        if run is None:
            raise HTTPException(status_code=409, detail="Version đã publish không còn tồn tại.")
        task = run_workflow.delay(run.id)
        run.celery_task_id = task.id
        await session.commit()
        await session.refresh(run)
        created.append(
            BatchRunItem(filename=submission.filename, run=RunSummary.model_validate(run))
        )
    return created
