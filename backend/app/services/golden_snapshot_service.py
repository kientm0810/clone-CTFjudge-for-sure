import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import GoldenSnapshot
from app.schemas.persistence import ExecutionProgressDetail, GoldenSnapshotDetail
from app.schemas.workflow import NodeType, WorkflowDefinition


def find_golden_freeze_node(definition: WorkflowDefinition) -> str | None:
    preferred = next(
        (
            node.id
            for node in definition.nodes
            if node.type == NodeType.DATABASE
            and node.config.get("operation") == "upsert"
            and node.config.get("freeze") is True
        ),
        None,
    )
    if preferred:
        return preferred
    return next(
        (
            node.id
            for node in definition.nodes
            if node.type == NodeType.DATABASE
            and node.config.get("operation") == "upsert"
            and node.id == "golden-index"
        ),
        None,
    )


def snapshot_content_hash(inputs: dict) -> str:
    payload = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshot_detail(
    snapshot: GoldenSnapshot,
    progress: list | None = None,
) -> GoldenSnapshotDetail:
    return GoldenSnapshotDetail(
        id=snapshot.id,
        workflow_version_id=snapshot.workflow_version_id,
        frozen_node_id=snapshot.frozen_node_id,
        status=snapshot.status,
        content_hash=snapshot.content_hash,
        collection_name=snapshot.collection_name,
        embedding_model=snapshot.embedding_model,
        chunk_count=snapshot.chunk_count,
        is_active=snapshot.is_active,
        error=snapshot.error,
        frozen_node_ids=list(snapshot.outputs.keys()),
        created_at=snapshot.created_at,
        completed_at=snapshot.completed_at,
        progress=[ExecutionProgressDetail.model_validate(item) for item in (progress or [])],
    )


async def get_active_snapshot(
    session: AsyncSession,
    workflow_version_id: str,
) -> GoldenSnapshot | None:
    return await session.scalar(
        select(GoldenSnapshot)
        .where(
            GoldenSnapshot.workflow_version_id == workflow_version_id,
            GoldenSnapshot.status == "READY",
            GoldenSnapshot.is_active.is_(True),
        )
        .order_by(GoldenSnapshot.created_at.desc())
        .limit(1)
    )
