import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.services.llm_service import EmbeddingService


class PgVectorService:
    def __init__(
        self,
        engine: AsyncEngine | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.engine = engine or create_async_engine(
            get_settings().database_url,
            poolclass=NullPool,
        )
        self.embedding_service = embedding_service or EmbeddingService()
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self.engine.begin() as connection:
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS vector_chunks (
                        id TEXT PRIMARY KEY,
                        collection_name TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        embedding_model TEXT NOT NULL,
                        embedding vector NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_vector_chunks_collection "
                    "ON vector_chunks (collection_name, document_id)"
                )
            )
        self._initialized = True

    async def upsert(
        self,
        *,
        collection: str,
        chunks: list[dict[str, Any]],
        embedding_model: str,
    ) -> dict[str, Any]:
        await self.initialize()
        if not chunks:
            return {"collection": collection, "indexed_chunks": 0, "embedding_model": embedding_model}

        embeddings = await self.embedding_service.embed(
            [str(chunk["content"]) for chunk in chunks],
            model=embedding_model,
        )
        async with self.engine.begin() as connection:
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                chunk_id = str(chunk["chunk_id"])
                metadata = dict(chunk.get("metadata", {}))
                metadata["_source_chunk_id"] = chunk_id
                await connection.execute(
                    text(
                        """
                        INSERT INTO vector_chunks
                            (id, collection_name, document_id, content, embedding_model, embedding, metadata)
                        VALUES
                            (:id, :collection, :document_id, :content, :embedding_model,
                             CAST(:embedding AS vector), CAST(:metadata AS jsonb))
                        ON CONFLICT (id) DO UPDATE SET
                            collection_name = EXCLUDED.collection_name,
                            document_id = EXCLUDED.document_id,
                            content = EXCLUDED.content,
                            embedding_model = EXCLUDED.embedding_model,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata
                        """
                    ),
                    {
                        "id": f"{collection}:{chunk_id}",
                        "collection": collection,
                        "document_id": str(chunk["document_id"]),
                        "content": str(chunk["content"]),
                        "embedding_model": embedding_model,
                        "embedding": json.dumps(embedding),
                        "metadata": json.dumps(metadata),
                    },
                )
        return {
            "collection": collection,
            "indexed_chunks": len(chunks),
            "embedding_model": embedding_model,
        }

    async def search(
        self,
        *,
        collection: str,
        query_chunks: list[dict[str, Any]],
        embedding_model: str,
        top_k: int,
        score_threshold: float,
    ) -> list[dict[str, Any]]:
        await self.initialize()
        if not query_chunks:
            return []
        embeddings = await self.embedding_service.embed(
            [str(chunk["content"]) for chunk in query_chunks],
            model=embedding_model,
        )
        results: list[dict[str, Any]] = []
        async with self.engine.connect() as connection:
            for chunk, embedding in zip(query_chunks, embeddings, strict=True):
                rows = await connection.execute(
                    text(
                        """
                        SELECT id, content, metadata,
                               1 - (embedding <=> CAST(:embedding AS vector)) AS similarity_score
                        FROM vector_chunks
                        WHERE collection_name = :collection
                          AND embedding_model = :embedding_model
                          AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :score_threshold
                        ORDER BY embedding <=> CAST(:embedding AS vector)
                        LIMIT :top_k
                        """
                    ),
                    {
                        "embedding": json.dumps(embedding),
                        "collection": collection,
                        "embedding_model": embedding_model,
                        "score_threshold": score_threshold,
                        "top_k": top_k,
                    },
                )
                candidates = []
                for row in rows:
                    metadata = dict(row.metadata or {})
                    source_chunk_id = metadata.pop("_source_chunk_id", row.id)
                    candidates.append(
                        {
                            "golden_chunk_id": source_chunk_id,
                            "content": row.content,
                            "similarity_score": float(row.similarity_score),
                            "metadata": metadata,
                        }
                    )
                results.append(
                    {
                        "student_chunk_id": str(chunk["chunk_id"]),
                        "student_content": str(chunk["content"]),
                        "candidates": candidates,
                    }
                )
        return results

    async def delete_collections(self, collections: set[str]) -> int:
        if not collections:
            return 0
        await self.initialize()
        deleted = 0
        async with self.engine.begin() as connection:
            for collection in collections:
                result = await connection.execute(
                    text("DELETE FROM vector_chunks WHERE collection_name = :collection"),
                    {"collection": collection},
                )
                deleted += int(result.rowcount or 0)
        return deleted

