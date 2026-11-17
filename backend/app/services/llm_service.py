import asyncio
from contextlib import suppress
import json
import re
import time
from typing import Any, Awaitable, Callable

import httpx

from app.config import get_settings


LLMProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]


class _StreamProgress:
    def __init__(
        self,
        callback: LLMProgressCallback | None,
        max_tokens: int,
    ) -> None:
        self.callback = callback
        self.max_tokens = max_tokens
        self.started_at = time.monotonic()
        self.stage = "LOADING_PROMPT"
        self.message = "Đang nạp prompt vào model."
        self.prompt_tokens: int | None = None
        self.generated_tokens = 0
        self._heartbeat_task: asyncio.Task | None = None
        self._last_token_emit = 0.0

    def payload(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "message": self.message,
            "prompt_tokens": self.prompt_tokens,
            "generated_tokens": self.generated_tokens,
            "max_tokens": self.max_tokens,
            "elapsed_seconds": round(time.monotonic() - self.started_at, 1),
        }

    async def start(self) -> None:
        if self.callback is None:
            return
        await self.callback(self.payload())
        self._heartbeat_task = asyncio.create_task(self._heartbeat())

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(1)
            if self.callback is not None:
                await self.callback(self.payload())

    async def token_received(self) -> None:
        self.stage = "GENERATING"
        self.generated_tokens += 1
        self.message = (
            f"Đã sinh khoảng {self.generated_tokens}/{self.max_tokens} tokens."
        )
        now = time.monotonic()
        if self.callback is not None and now - self._last_token_emit >= 0.75:
            self._last_token_emit = now
            await self.callback(self.payload())

    async def parsing(
        self,
        *,
        prompt_tokens: int | None = None,
        generated_tokens: int | None = None,
    ) -> None:
        if prompt_tokens is not None:
            self.prompt_tokens = prompt_tokens
        if generated_tokens is not None:
            self.generated_tokens = generated_tokens
        self.stage = "PARSING"
        self.message = "Đã nhận đủ phản hồi, đang kiểm tra và parse JSON."
        if self.callback is not None:
            await self.callback(self.payload())

    async def close(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task


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
        try:
            if self._client is not None:
                response = await self._client.post(path, json=payload)
            else:
                async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
                    response = await client.post(path, json=payload)
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Không thể kết nối Ollama tại {self.base_url}. "
                "Hãy kiểm tra Ollama đang chạy và OLLAMA_BASE_URL đúng."
            ) from exc
        response.raise_for_status()
        return response.json()

    async def chat(
        self,
        *,
        prompt: str,
        model: str,
        temperature: float,
        output_schema: dict[str, Any] | None = None,
        max_tokens: int = 4096,
        progress_callback: LLMProgressCallback | None = None,
    ) -> Any:
        payload: dict[str, Any] = {
            "model": _ollama_model_name(model),
            "messages": [{"role": "user", "content": prompt}],
            "format": output_schema or "json",
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": True,
        }
        reporter = _StreamProgress(progress_callback, max_tokens)
        content_parts: list[str] = []
        prompt_tokens: int | None = None
        generated_tokens: int | None = None
        await reporter.start()
        try:
            if self._client is not None:
                stream = self._client.stream("POST", "/api/chat", json=payload)
            else:
                client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
                stream = client.stream("POST", "/api/chat", json=payload)
            try:
                async with stream as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        delta = data.get("message", {}).get("content") or ""
                        if delta:
                            content_parts.append(delta)
                            await reporter.token_received()
                        if data.get("done"):
                            prompt_tokens = data.get("prompt_eval_count")
                            generated_tokens = data.get("eval_count")
            finally:
                if self._client is None:
                    await client.aclose()
            await reporter.parsing(
                prompt_tokens=prompt_tokens,
                generated_tokens=generated_tokens,
            )
            return _parse_model_output("".join(content_parts))
        finally:
            await reporter.close()

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
        max_tokens: int = 4096,
        progress_callback: LLMProgressCallback | None = None,
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
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": max_tokens,
        }
        if output_schema and supports_json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "node_output", "schema": output_schema},
            }
        reporter = _StreamProgress(progress_callback, max_tokens)
        content_parts: list[str] = []
        prompt_tokens: int | None = None
        generated_tokens: int | None = None
        await reporter.start()
        try:
            if self._client is not None:
                stream = self._client.stream(
                    "POST", self.endpoint_url, json=payload, headers=self.headers
                )
            else:
                client = httpx.AsyncClient(timeout=self.timeout)
                stream = client.stream(
                    "POST", self.endpoint_url, json=payload, headers=self.headers
                )
            try:
                async with stream as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw_data = line[5:].strip()
                        if not raw_data or raw_data == "[DONE]":
                            continue
                        data = json.loads(raw_data)
                        usage = data.get("usage") or {}
                        if usage:
                            prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                            generated_tokens = usage.get("completion_tokens", generated_tokens)
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content") or ""
                        reasoning = delta.get("reasoning_content") or ""
                        if content:
                            content_parts.append(content)
                        if content or reasoning:
                            await reporter.token_received()
            finally:
                if self._client is None:
                    await client.aclose()
            await reporter.parsing(
                prompt_tokens=prompt_tokens,
                generated_tokens=generated_tokens,
            )
            return _parse_model_output("".join(content_parts))
        finally:
            await reporter.close()


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
        max_tokens: int = 4096,
        progress_callback: LLMProgressCallback | None = None,
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
                max_tokens=max_tokens,
                progress_callback=progress_callback,
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
                max_tokens=max_tokens,
                progress_callback=progress_callback,
            )

        from litellm import acompletion

        kwargs: dict[str, Any] = {
            "model": selected_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": selected_temperature,
            "max_tokens": max_tokens,
        }
        reporter = _StreamProgress(progress_callback, max_tokens)
        await reporter.start()
        if output_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "node_output", "schema": output_schema},
            }
        try:
            response = await acompletion(**kwargs)
            usage = getattr(response, "usage", None)
            await reporter.parsing(
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                generated_tokens=getattr(usage, "completion_tokens", None),
            )
            return _parse_model_output(response.choices[0].message.content)
        finally:
            await reporter.close()


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

