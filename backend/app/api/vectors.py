from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.vector_service import PgVectorService


router = APIRouter(prefix="/vectors", tags=["vectors"])


class VectorCollectionSummary(BaseModel):
    name: str
    chunk_count: int
    embedding_models: list[str]
    updated_at: datetime | None = None


@router.get("/collections", response_model=list[VectorCollectionSummary])
async def list_vector_collections() -> list[dict]:
    return await PgVectorService().list_collections()
