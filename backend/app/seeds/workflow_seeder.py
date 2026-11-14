import json
from importlib.resources import files

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow, WorkflowDeployment, WorkflowVersion
from app.schemas.workflow import WorkflowDefinition
from app.workflow.validator import WorkflowValidator


DEFAULT_WORKFLOW_ID = "00000000-0000-4000-8000-000000000001"
DEFAULT_VERSION_ID = "00000000-0000-4000-8000-000000000002"
DEFAULT_ENVIRONMENT = "prod"


def load_default_definition() -> WorkflowDefinition:
    seed_file = files("app.seeds").joinpath("ctfjudge_rag_workflow.json")
    definition = WorkflowDefinition.model_validate(json.loads(seed_file.read_text(encoding="utf-8")))
    WorkflowValidator.validate(definition)
    return definition


async def ensure_default_workflow(session: AsyncSession) -> None:
    """Install the built-in RAG workflow without overwriting user data."""
    workflow = await session.get(Workflow, DEFAULT_WORKFLOW_ID)

    if workflow is None:
        definition = load_default_definition()
        workflow = Workflow(
            id=DEFAULT_WORKFLOW_ID,
            name=definition.name,
            description=(
                "Built-in CTFJudge workflow: chunk golden solution and student writeup, "
                "index and retrieve evidence with pgvector, then produce a similarity report."
            ),
            current_version=definition.version,
        )
        version = WorkflowVersion(
            id=DEFAULT_VERSION_ID,
            workflow=workflow,
            version=definition.version,
            definition=definition.model_dump(mode="json"),
        )
        session.add_all([workflow, version])
        await session.flush()
    else:
        version = await session.scalar(
            select(WorkflowVersion).where(
                WorkflowVersion.workflow_id == workflow.id,
                WorkflowVersion.version == workflow.current_version,
            )
        )
        if version is None:
            raise RuntimeError("Built-in workflow exists without its current version")

    deployment = await session.get(WorkflowDeployment, DEFAULT_ENVIRONMENT)
    if deployment is None:
        session.add(
            WorkflowDeployment(
                environment=DEFAULT_ENVIRONMENT,
                workflow_id=workflow.id,
                workflow_version_id=version.id,
            )
        )

    await session.commit()
