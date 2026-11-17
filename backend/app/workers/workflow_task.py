import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, init_database
from app.models.workflow import GoldenSnapshot, NodeRun, WorkflowRun, WorkflowVersion
from app.nodes.base import NodeResult
from app.schemas.workflow import NodeDefinition, WorkflowDefinition
from app.services.llm_service import LLMService
from app.services.execution_progress import ExecutionProgressWriter
from app.services.vector_service import PgVectorService
from app.services.run_cleanup import owned_vector_collections
from app.workflow.context import WorkflowServices
from app.workflow.executor import WorkflowExecutor
from app.workers.celery_app import celery_app


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


logger = logging.getLogger(__name__)


async def cleanup_run_vectors(session: AsyncSession, run_id: str) -> int:
    node_runs = list(
        await session.scalars(select(NodeRun).where(NodeRun.workflow_run_id == run_id))
    )
    collections = owned_vector_collections(run_id, node_runs)
    return await PgVectorService().delete_collections(collections)


def completion_time(started_at: datetime | None) -> datetime:
    now = utc_now()
    return max(now, started_at) if started_at is not None else now


class DatabaseExecutionObserver:
    def __init__(self, session: AsyncSession, run_id: str) -> None:
        self.session = session
        self.run_id = run_id
        self.progress = ExecutionProgressWriter("run", run_id)

    async def _get_node_run(self, node_id: str) -> NodeRun | None:
        return await self.session.scalar(
            select(NodeRun).where(
                NodeRun.workflow_run_id == self.run_id,
                NodeRun.node_id == node_id,
            )
        )

    async def node_started(
        self,
        definition: NodeDefinition,
        inputs: dict[str, Any],
        sequence: int,
    ) -> None:
        node_run = NodeRun(
            workflow_run_id=self.run_id,
            node_id=definition.id,
            node_type=definition.type.value,
            sequence=sequence,
            status="RUNNING",
            input_data=inputs,
            started_at=utc_now(),
        )
        self.session.add(node_run)
        await self.session.commit()
        await self.progress.update(
            definition.id,
            {
                "stage": "STARTING",
                "message": f"Đang bắt đầu node {definition.name or definition.id}.",
                "generated_tokens": 0,
                "max_tokens": (
                    int(definition.config.get("max_tokens", 4096))
                    if definition.type.value == "agent"
                    else None
                ),
            },
        )

    async def node_completed(
        self,
        definition: NodeDefinition,
        result: NodeResult,
        sequence: int,
    ) -> None:
        node_run = await self._get_node_run(definition.id)
        if node_run is None:
            return
        node_run.status = "COMPLETED"
        node_run.output_data = result.value
        node_run.completed_at = completion_time(node_run.started_at)
        await self.session.commit()
        await self.progress.update(
            definition.id,
            {"stage": "COMPLETED", "message": "Node đã hoàn tất."},
        )

    async def node_failed(
        self,
        definition: NodeDefinition,
        error: Exception,
        sequence: int,
    ) -> None:
        node_run = await self._get_node_run(definition.id)
        if node_run is None:
            return
        node_run.status = "FAILED"
        node_run.error = str(error).strip() or error.__class__.__name__
        node_run.completed_at = completion_time(node_run.started_at)
        await self.session.commit()
        await self.progress.update(
            definition.id,
            {"stage": "FAILED", "message": node_run.error},
        )

    async def node_progress(
        self,
        definition: NodeDefinition,
        update: dict[str, Any],
    ) -> None:
        await self.progress.update(definition.id, update)


class SnapshotExecutionObserver:
    def __init__(self, snapshot_id: str) -> None:
        self.progress = ExecutionProgressWriter("snapshot", snapshot_id)

    async def node_started(
        self,
        definition: NodeDefinition,
        inputs: dict[str, Any],
        sequence: int,
    ) -> None:
        await self.progress.update(
            definition.id,
            {
                "stage": "STARTING",
                "message": f"Đang bắt đầu node {definition.name or definition.id}.",
                "generated_tokens": 0,
                "max_tokens": (
                    int(definition.config.get("max_tokens", 4096))
                    if definition.type.value == "agent"
                    else None
                ),
            },
        )

    async def node_completed(
        self,
        definition: NodeDefinition,
        result: NodeResult,
        sequence: int,
    ) -> None:
        await self.progress.update(
            definition.id,
            {"stage": "COMPLETED", "message": "Node đã hoàn tất."},
        )

    async def node_failed(
        self,
        definition: NodeDefinition,
        error: Exception,
        sequence: int,
    ) -> None:
        await self.progress.update(
            definition.id,
            {
                "stage": "FAILED",
                "message": str(error).strip() or error.__class__.__name__,
            },
        )

    async def node_progress(
        self,
        definition: NodeDefinition,
        update: dict[str, Any],
    ) -> None:
        await self.progress.update(definition.id, update)


@celery_app.task(name="ctfjudge.run_workflow")
def run_workflow(run_id: str) -> dict[str, Any]:
    return asyncio.run(_run_workflow(run_id))


@celery_app.task(name="ctfjudge.prepare_golden_snapshot")
def prepare_golden_snapshot(snapshot_id: str) -> dict[str, Any]:
    return asyncio.run(_prepare_golden_snapshot(snapshot_id))


async def _prepare_golden_snapshot(snapshot_id: str) -> dict[str, Any]:
    await init_database()
    async with SessionLocal() as session:
        snapshot = await session.get(GoldenSnapshot, snapshot_id)
        if snapshot is None:
            raise ValueError(f"Golden snapshot '{snapshot_id}' does not exist")
        version = await session.get(WorkflowVersion, snapshot.workflow_version_id)
        if version is None:
            raise ValueError("Workflow version for golden snapshot no longer exists")

        snapshot.status = "RUNNING"
        snapshot.error = None
        await session.commit()

        captured_results: dict[str, Any] = {}
        try:
            await WorkflowExecutor().execute(
                WorkflowDefinition.model_validate(version.definition),
                runtime_inputs=snapshot.input_data,
                services=WorkflowServices(
                    llm=LLMService(),
                    vector_store=PgVectorService(),
                ),
                run_id=snapshot.id,
                target_node_ids={snapshot.frozen_node_id},
                result_sink=captured_results,
                observer=SnapshotExecutionObserver(snapshot.id),
            )
            terminal_output = captured_results.get(snapshot.frozen_node_id)
            if not isinstance(terminal_output, dict) or not terminal_output.get("collection"):
                raise ValueError("Frozen database node did not return a vector collection")

            await session.execute(
                update(GoldenSnapshot)
                .where(
                    GoldenSnapshot.workflow_version_id == snapshot.workflow_version_id,
                    GoldenSnapshot.id != snapshot.id,
                    GoldenSnapshot.is_active.is_(True),
                )
                .values(is_active=False)
            )
            snapshot.outputs = captured_results
            snapshot.collection_name = str(terminal_output["collection"])
            snapshot.embedding_model = str(terminal_output.get("embedding_model") or "") or None
            snapshot.chunk_count = int(terminal_output.get("indexed_chunks") or 0)
            snapshot.status = "READY"
            snapshot.is_active = True
            snapshot.completed_at = completion_time(None)
            await session.commit()
            return {
                "snapshot_id": snapshot.id,
                "collection": snapshot.collection_name,
                "chunk_count": snapshot.chunk_count,
            }
        except Exception as exc:
            snapshot.status = "FAILED"
            snapshot.error = str(exc).strip() or exc.__class__.__name__
            snapshot.completed_at = completion_time(None)
            await session.commit()
            raise


async def _run_workflow(run_id: str) -> dict[str, Any]:
    await init_database()
    async with SessionLocal() as session:
        run = await session.get(WorkflowRun, run_id)
        if run is None:
            raise ValueError(f"Workflow run '{run_id}' does not exist")
        version = await session.get(WorkflowVersion, run.workflow_version_id)
        if version is None:
            raise ValueError(f"Workflow version '{run.workflow_version_id}' does not exist")

        run.status = "RUNNING"
        run.started_at = utc_now()
        run.error = None
        await session.commit()

        observer = DatabaseExecutionObserver(session, run.id)
        try:
            runtime_inputs = dict(run.runtime_inputs)
            snapshot_id = runtime_inputs.pop("__golden_snapshot_id", None)
            initial_results: dict[str, Any] | None = None
            if snapshot_id:
                snapshot = await session.get(GoldenSnapshot, str(snapshot_id))
                if (
                    snapshot is None
                    or snapshot.status != "READY"
                    or snapshot.workflow_version_id != version.id
                ):
                    raise ValueError("Golden snapshot is missing, not ready, or belongs to another version")
                initial_results = dict(snapshot.outputs)

            result = await WorkflowExecutor().execute(
                WorkflowDefinition.model_validate(version.definition),
                runtime_inputs=runtime_inputs,
                services=WorkflowServices(
                    llm=LLMService(),
                    vector_store=PgVectorService(),
                ),
                run_id=run.id,
                observer=observer,
                initial_results=initial_results,
            )
        except Exception as exc:
            run.status = "FAILED"
            run.error = str(exc)
            run.completed_at = completion_time(run.started_at)
            await session.commit()
            raise
        else:
            serialized = result.model_dump(mode="json")
            run.status = "COMPLETED"
            run.result = serialized
            run.completed_at = completion_time(run.started_at)
            await session.commit()
            return serialized
        finally:
            try:
                await cleanup_run_vectors(session, run.id)
            except Exception:
                logger.exception("Could not clean vector data for run %s", run.id)

