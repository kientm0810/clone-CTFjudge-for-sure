import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.database import SessionLocal
from app.models.workflow import ExecutionProgress


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionProgressWriter:
    def __init__(self, execution_kind: str, execution_id: str) -> None:
        self.execution_kind = execution_kind
        self.execution_id = execution_id
        self._lock = asyncio.Lock()

    async def update(self, node_id: str, update: dict[str, Any]) -> None:
        async with self._lock, SessionLocal() as session:
            progress = await session.scalar(
                select(ExecutionProgress).where(
                    ExecutionProgress.execution_kind == self.execution_kind,
                    ExecutionProgress.execution_id == self.execution_id,
                    ExecutionProgress.node_id == node_id,
                )
            )
            now = utc_now()
            if progress is None:
                progress = ExecutionProgress(
                    execution_kind=self.execution_kind,
                    execution_id=self.execution_id,
                    node_id=node_id,
                    started_at=now,
                )
                session.add(progress)

            for field in (
                "stage",
                "message",
                "prompt_tokens",
                "generated_tokens",
                "max_tokens",
            ):
                if field in update:
                    setattr(progress, field, update[field])
            progress.elapsed_seconds = max(
                float(update.get("elapsed_seconds", (now - progress.started_at).total_seconds())),
                0,
            )
            progress.heartbeat_at = now
            progress.updated_at = now
            await session.commit()


async def list_execution_progress(
    execution_kind: str,
    execution_id: str,
) -> list[ExecutionProgress]:
    async with SessionLocal() as session:
        result = await session.scalars(
            select(ExecutionProgress)
            .where(
                ExecutionProgress.execution_kind == execution_kind,
                ExecutionProgress.execution_id == execution_id,
            )
            .order_by(ExecutionProgress.started_at)
        )
        return list(result)
