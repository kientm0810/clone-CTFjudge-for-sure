from typing import Any, Literal

from pydantic import BaseModel, Field


class Document(BaseModel):
    document_id: str
    document_type: Literal["golden_solution", "student_submission", "generic"] = "generic"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextChunk(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    chunk_index: int
    start_offset: int
    end_offset: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalCandidate(BaseModel):
    golden_chunk_id: str
    content: str
    similarity_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChunkRetrievalResult(BaseModel):
    student_chunk_id: str
    student_content: str
    candidates: list[RetrievalCandidate] = Field(default_factory=list)


class ChunkComparison(BaseModel):
    student_chunk_id: str
    classification: Literal[
        "exact_match",
        "paraphrase",
        "partial_match",
        "additional_valid_approach",
        "contradiction",
        "incorrect",
        "irrelevant",
        "no_match",
    ]
    matched_golden_chunk_ids: list[str] = Field(default_factory=list)
    score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    explanation: str
    missing_concepts: list[str] = Field(default_factory=list)

