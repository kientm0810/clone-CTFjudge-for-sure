from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.workflow import NodeRun, Workflow, WorkflowRun, WorkflowVersion
from app.schemas.persistence import WorkflowCreate
from app.schemas.workflow import WorkflowDefinition


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

    async def create_version(
        self,
        workflow_id: str,
        definition: WorkflowDefinition,
    ) -> tuple[Workflow, WorkflowVersion] | None:
        workflow = await self.session.scalar(
            select(Workflow).where(Workflow.id == workflow_id).with_for_update()
        )
        if workflow is None:
            return None
        latest = await self.session.scalar(
            select(func.max(WorkflowVersion.version)).where(WorkflowVersion.workflow_id == workflow_id)
        )
        version_number = int(latest or 0) + 1
        versioned_definition = definition.model_copy(update={"version": version_number})
        version = WorkflowVersion(
            workflow=workflow,
            version=version_number,
            definition=versioned_definition.model_dump(mode="json"),
        )
        workflow.name = versioned_definition.name
        workflow.current_version = version_number
        self.session.add(version)
        await self.session.commit()
        await self.session.refresh(workflow)
        await self.session.refresh(version)
        return workflow, version

    async def list_versions(self, workflow_id: str) -> tuple[Workflow, list[WorkflowVersion]] | None:
        workflow = await self.session.get(Workflow, workflow_id)
        if workflow is None:
            return None
        versions = list(
            await self.session.scalars(
                select(WorkflowVersion)
                .where(WorkflowVersion.workflow_id == workflow_id)
                .order_by(WorkflowVersion.version.desc())
            )
        )
        return workflow, versions

    async def get_version(self, workflow_id: str, version_number: int) -> WorkflowVersion | None:
        return await self.session.scalar(
            select(WorkflowVersion).where(
                WorkflowVersion.workflow_id == workflow_id,
                WorkflowVersion.version == version_number,
            )
        )

    async def activate_version(
        self,
        workflow_id: str,
        version_number: int,
    ) -> tuple[Workflow, WorkflowVersion] | None:
        workflow = await self.session.scalar(
            select(Workflow).where(Workflow.id == workflow_id).with_for_update()
        )
        if workflow is None:
            return None
        version = await self.get_version(workflow_id, version_number)
        if version is None:
            return None
        definition = WorkflowDefinition.model_validate(version.definition)
        workflow.current_version = version.version
        workflow.name = definition.name
        await self.session.commit()
        await self.session.refresh(workflow)
        return workflow, version

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

    async def list_runs(
        self,
        workflow_id: str,
        limit: int = 50,
    ) -> list[tuple[WorkflowRun, WorkflowVersion]] | None:
        workflow_exists = await self.session.scalar(
            select(Workflow.id).where(Workflow.id == workflow_id)
        )
        if workflow_exists is None:
            return None
        rows = await self.session.execute(
            select(WorkflowRun, WorkflowVersion)
            .join(WorkflowVersion, WorkflowRun.workflow_version_id == WorkflowVersion.id)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
        )
        return [(row[0], row[1]) for row in rows]

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

    async def delete_run(self, run: WorkflowRun) -> None:
        await self.session.delete(run)
        await self.session.commit()

