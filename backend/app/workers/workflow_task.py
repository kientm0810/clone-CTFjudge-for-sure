import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, init_database
from app.models.workflow import NodeRun, WorkflowRun, WorkflowVersion
from app.nodes.base import NodeResult
from app.schemas.workflow import NodeDefinition, WorkflowDefinition
from app.services.llm_service import LLMService
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


@celery_app.task(name="ctfjudge.run_workflow")
def run_workflow(run_id: str) -> dict[str, Any]:
    return asyncio.run(_run_workflow(run_id))


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
            result = await WorkflowExecutor().execute(
                WorkflowDefinition.model_validate(version.definition),
                runtime_inputs=run.runtime_inputs,
                services=WorkflowServices(
                    llm=LLMService(),
                    vector_store=PgVectorService(),
                ),
                run_id=run.id,
                observer=observer,
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

