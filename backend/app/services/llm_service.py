import json
import re
from typing import Any

import httpx

from app.config import get_settings


def _parse_model_output(content: Any) -> Any:
    if not isinstance(content, str):
        return content
    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        content.strip(),
        flags=re.IGNORECASE,
    ).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"content": content}


def _is_ollama_model(model: str) -> bool:
    return model.startswith("ollama/") or model.startswith("local/")


def _ollama_model_name(model: str) -> str:
    return model.split("/", 1)[1] if "/" in model else model


def _is_registered_model(model: str) -> bool:
    return model.startswith("registered/")


def _registered_model_id(model: str) -> str:
    return model.split("/", 1)[1]


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        configured_url = base_url or settings.ollama_base_url
        self.base_url = re.sub(r"/api/(?:chat|embed)/?$", "", configured_url.rstrip("/"))
        self.timeout = timeout or settings.ollama_timeout_seconds
        self._client = client

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._client is not None:
            response = await self._client.post(path, json=payload)
        else:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    async def chat(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float,
        output_schema: dict[str, Any] | None = None,
    ) -> Any:
        payload: dict[str, Any] = {
            "model": _ollama_model_name(model),
            "messages": [{"role": "user", "content": prompt}],
            "format": output_schema or "json",
            "options": {"temperature": temperature},
            "stream": False,
        }
        data = await self._post("/api/chat", payload)
        return _parse_model_output(data.get("message", {}).get("content", ""))

    async def embed(self, *, texts: list[str], model: str) -> list[list[float]]:
        data = await self._post(
            "/api/embed",
            {"model": _ollama_model_name(model), "input": texts},
        )
        embeddings = data.get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise ValueError("Ollama returned an invalid embeddings response")
        return embeddings

    async def list_models(self) -> list[dict[str, Any]]:
        if self._client is not None:
            response = await self._client.get("/api/tags")
        else:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                response = await client.get("/api/tags")
        response.raise_for_status()
        return response.json().get("models", [])


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        endpoint_url: str,
        api_key: str | None = None,
        additional_headers: dict[str, str] | None = None,
        timeout: float = 180,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json; charset=utf-8", **(additional_headers or {})}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        self._client = client

    async def chat(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float,
        output_schema: dict[str, Any] | None = None,
        supports_json_schema: bool = False,
    ) -> Any:
        effective_prompt = prompt
        if output_schema and not supports_json_schema:
            effective_prompt = (
                f"{prompt}\n\n"
                "REQUIRED OUTPUT JSON SCHEMA:\n"
                f"{json.dumps(output_schema, ensure_ascii=False, indent=2)}\n\n"
                "Return JSON only. Use the exact property names from this schema. "
                "Do not rename, omit, or wrap the required properties."
            )
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": effective_prompt}],
            "temperature": temperature,
            "stream": False,
        }
        if output_schema and supports_json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "node_output", "schema": output_schema},
            }
        if self._client is not None:
            response = await self._client.post(self.endpoint_url, json=payload, headers=self.headers)
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.endpoint_url, json=payload, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("OpenAI-compatible endpoint returned no choices")
        content = choices[0].get("message", {}).get("content", "")
        return _parse_model_output(content)


async def get_registered_model(model_reference: str):
    from app.database import SessionLocal
    from app.models.provider import AIModelConnection

    async with SessionLocal() as session:
        connection = await session.get(AIModelConnection, _registered_model_id(model_reference))
        if connection is None:
            raise ValueError(f"Registered model does not exist: {model_reference}")
        if not connection.enabled:
            raise ValueError(f"Registered model is disabled: {connection.name}")
        return connection


class LLMService:
    def __init__(self, ollama: OllamaClient | None = None) -> None:
        self.ollama = ollama or OllamaClient()

    async def complete(
        self,
        *,
        prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> Any:
        settings = get_settings()
        selected_model = model or settings.default_chat_model
        selected_temperature = settings.default_temperature if temperature is None else temperature
        if _is_ollama_model(selected_model):
            return await self.ollama.chat(
                prompt=prompt,
                model=selected_model,
                temperature=selected_temperature,
                output_schema=output_schema,
            )

        if _is_registered_model(selected_model):
            connection = await get_registered_model(selected_model)
            return await OpenAICompatibleClient(
                endpoint_url=connection.endpoint_url,
                api_key=connection.api_key,
                additional_headers=connection.additional_headers,
                timeout=connection.timeout_seconds,
            ).chat(
                prompt=prompt,
                model=connection.model_name,
                temperature=selected_temperature,
                output_schema=output_schema,
                supports_json_schema=connection.supports_json_schema,
            )

        from litellm import acompletion

        kwargs: dict[str, Any] = {
            "model": selected_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": selected_temperature,
        }
        if output_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "node_output", "schema": output_schema},
            }
        response = await acompletion(**kwargs)
        return _parse_model_output(response.choices[0].message.content)


class EmbeddingService:
    def __init__(self, ollama: OllamaClient | None = None) -> None:
        self.ollama = ollama or OllamaClient()

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        settings = get_settings()
        selected_model = model or settings.default_embedding_model
        if _is_ollama_model(selected_model):
            return await self.ollama.embed(texts=texts, model=selected_model)

        from litellm import aembedding

        response = await aembedding(model=selected_model, input=texts)
        ordered = sorted(
            response.data,
            key=lambda item: item["index"] if isinstance(item, dict) else item.index,
        )
        return [item["embedding"] if isinstance(item, dict) else item.embedding for item in ordered]


LiteLLMService = LLMService
LiteLLMEmbeddingService = EmbeddingService

