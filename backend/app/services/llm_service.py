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

