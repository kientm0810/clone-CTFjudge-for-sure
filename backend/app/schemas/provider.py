from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AIModelConnectionWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    model_name: str = Field(min_length=1, max_length=255)
    endpoint_url: str = Field(min_length=8)
    api_key: str | None = None
    additional_headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=180, ge=5, le=1800)
    supports_json_schema: bool = False
    enabled: bool = True

    @field_validator("endpoint_url")
    @classmethod
    def validate_endpoint_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("API URL must start with http:// or https://")
        return normalized

    @field_validator("name", "model_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()


class AIModelConnectionUpdate(AIModelConnectionWrite):
    api_key: str | None = Field(default=None, description="Leave empty to keep the existing API key")


class AIModelConnectionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reference: str
    name: str
    model_name: str
    endpoint_url: str
    additional_headers: dict[str, str]
    timeout_seconds: float
    supports_json_schema: bool
    enabled: bool
    has_api_key: bool
    created_at: datetime
    updated_at: datetime


class AIModelOption(BaseModel):
    reference: str
    name: str
    provider: str
    model_name: str
    capabilities: list[str] = Field(default_factory=lambda: ["completion"])
    details: dict[str, str] = Field(default_factory=dict)


class AIModelTestResult(BaseModel):
    ok: bool
    latency_ms: int
    response_preview: str
