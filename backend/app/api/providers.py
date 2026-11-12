import json
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.models.provider import AIModelConnection
from app.schemas.provider import (
    AIModelConnectionDetail,
    AIModelConnectionUpdate,
    AIModelConnectionWrite,
    AIModelOption,
    AIModelTestResult,
)
from app.services.llm_service import OllamaClient, OpenAICompatibleClient


router = APIRouter(prefix="/providers", tags=["providers"])


def connection_detail(connection: AIModelConnection) -> AIModelConnectionDetail:
    return AIModelConnectionDetail(
        id=connection.id,
        reference=f"registered/{connection.id}",
        name=connection.name,
        model_name=connection.model_name,
        endpoint_url=connection.endpoint_url,
        additional_headers=connection.additional_headers or {},
        timeout_seconds=connection.timeout_seconds,
        supports_json_schema=connection.supports_json_schema,
        enabled=connection.enabled,
        has_api_key=bool(connection.api_key),
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )


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


@router.get("/models")
async def list_model_options(session: AsyncSession = Depends(get_session)) -> dict:
    options: list[AIModelOption] = []
    warnings: list[str] = []
    try:
        ollama_models = await OllamaClient(timeout=5).list_models()
        for model in ollama_models:
            name = str(model.get("name") or model.get("model") or "")
            if not name:
                continue
            details = model.get("details") if isinstance(model.get("details"), dict) else {}
            capabilities = model.get("capabilities") if isinstance(model.get("capabilities"), list) else []
            inferred = capabilities or (["embedding"] if "embed" in name.lower() else ["completion"])
            options.append(AIModelOption(
                reference=f"ollama/{name}",
                name=name,
                provider="ollama",
                model_name=name,
                capabilities=inferred,
                details={key: str(value) for key, value in details.items() if value is not None},
            ))
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        warnings.append(f"Không kết nối được Ollama: {exc}")

    result = await session.execute(
        select(AIModelConnection).where(AIModelConnection.enabled.is_(True)).order_by(AIModelConnection.name)
    )
    options.extend(
        AIModelOption(
            reference=f"registered/{connection.id}",
            name=connection.name,
            provider="openai-compatible",
            model_name=connection.model_name,
            capabilities=["completion"],
            details={"endpoint": connection.endpoint_url},
        )
        for connection in result.scalars()
    )
    return {"models": [option.model_dump() for option in options], "warnings": warnings}


@router.get("/registered-models", response_model=list[AIModelConnectionDetail])
async def list_registered_models(session: AsyncSession = Depends(get_session)) -> list[AIModelConnectionDetail]:
    result = await session.execute(select(AIModelConnection).order_by(AIModelConnection.updated_at.desc()))
    return [connection_detail(connection) for connection in result.scalars()]


@router.post("/registered-models", response_model=AIModelConnectionDetail, status_code=status.HTTP_201_CREATED)
async def create_registered_model(
    payload: AIModelConnectionWrite,
    session: AsyncSession = Depends(get_session),
) -> AIModelConnectionDetail:
    connection = AIModelConnection(**payload.model_dump())
    session.add(connection)
    await session.commit()
    await session.refresh(connection)
    return connection_detail(connection)


@router.put("/registered-models/{model_id}", response_model=AIModelConnectionDetail)
async def update_registered_model(
    model_id: str,
    payload: AIModelConnectionUpdate,
    session: AsyncSession = Depends(get_session),
) -> AIModelConnectionDetail:
    connection = await session.get(AIModelConnection, model_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Registered model not found")
    values = payload.model_dump()
    if not values.get("api_key"):
        values.pop("api_key", None)
    for key, value in values.items():
        setattr(connection, key, value)
    await session.commit()
    await session.refresh(connection)
    return connection_detail(connection)


@router.post("/registered-models/{model_id}/test", response_model=AIModelTestResult)
async def test_registered_model(
    model_id: str,
    session: AsyncSession = Depends(get_session),
) -> AIModelTestResult:
    connection = await session.get(AIModelConnection, model_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Registered model not found")
    started = time.perf_counter()
    try:
        result = await OpenAICompatibleClient(
            endpoint_url=connection.endpoint_url,
            api_key=connection.api_key,
            additional_headers=connection.additional_headers,
            timeout=connection.timeout_seconds,
        ).chat(
            prompt="Reply with exactly: CONNECTION_OK",
            model=connection.model_name,
            temperature=0,
        )
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Model connection failed: {exc}") from exc
    latency_ms = round((time.perf_counter() - started) * 1000)
    preview = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    return AIModelTestResult(ok=True, latency_ms=latency_ms, response_preview=preview[:500])


@router.delete("/registered-models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_registered_model(model_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    connection = await session.get(AIModelConnection, model_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Registered model not found")
    await session.delete(connection)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

