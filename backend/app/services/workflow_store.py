from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.workflow import NodeRun, Workflow, WorkflowRun, WorkflowVersion
from app.schemas.persistence import WorkflowCreate


class WorkflowStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_workflow(self, payload: WorkflowCreate) -> tuple[Workflow, WorkflowVersion]:
        workflow = Workflow(
            name=payload.definition.name,
            description=payload.description,
            current_version=payload.definition.version,
        )
        version = WorkflowVersion(
            workflow=workflow,
            version=payload.definition.version,
            definition=payload.definition.model_dump(mode="json"),
        )
        self.session.add_all([workflow, version])
        await self.session.commit()
        await self.session.refresh(workflow)
        await self.session.refresh(version)
        return workflow, version

    async def list_workflows(self) -> list[Workflow]:
        result = await self.session.scalars(select(Workflow).order_by(Workflow.updated_at.desc()))
        return list(result)

    async def get_workflow(self, workflow_id: str) -> tuple[Workflow, WorkflowVersion] | None:
        statement = (
            select(Workflow, WorkflowVersion)
            .join(
                WorkflowVersion,
                (WorkflowVersion.workflow_id == Workflow.id)
                & (WorkflowVersion.version == Workflow.current_version),
            )
            .where(Workflow.id == workflow_id)
        )
        row = (await self.session.execute(statement)).first()
        return (row[0], row[1]) if row else None

    async def create_run(self, workflow_id: str, inputs: dict) -> WorkflowRun | None:
        stored = await self.get_workflow(workflow_id)
        if stored is None:
            return None
        _, version = stored
        run = WorkflowRun(
            workflow_version_id=version.id,
            status="PENDING",
            runtime_inputs=inputs,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_run(self, run_id: str, include_nodes: bool = False) -> WorkflowRun | None:
        statement = select(WorkflowRun).where(WorkflowRun.id == run_id)
        if include_nodes:
            statement = statement.options(selectinload(WorkflowRun.node_runs))
        return await self.session.scalar(statement)

    async def reset_run(self, run: WorkflowRun) -> None:
        await self.session.execute(delete(NodeRun).where(NodeRun.workflow_run_id == run.id))
        run.status = "PENDING"
        run.result = None
        run.error = None
        run.started_at = None
        run.completed_at = None
        run.celery_task_id = None
        await self.session.commit()

