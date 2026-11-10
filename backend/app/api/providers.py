import httpx
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.services.llm_service import OllamaClient


router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("/ollama/models")
async def list_ollama_models() -> dict:
    try:
        models = await OllamaClient().list_models()
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach Ollama at {get_settings().ollama_base_url}: {exc}",
        ) from exc
    return {
        "provider": "ollama",
        "base_url": get_settings().ollama_base_url,
        "models": models,
    }

