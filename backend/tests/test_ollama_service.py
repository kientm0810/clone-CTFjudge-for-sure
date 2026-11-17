import json

import httpx
import pytest

from app.services.llm_service import EmbeddingService, LLMService, OllamaClient


@pytest.mark.asyncio
async def test_ollama_chat_uses_native_api_and_json_schema() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": '{"score": 9}'}, "done": True},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://ollama.test",
    ) as client:
        service = LLMService(ollama=OllamaClient(client=client))
        result = await service.complete(
            prompt="Grade this answer",
            model="ollama/qwen2.5:3b",
            temperature=0,
            output_schema={"type": "object", "properties": {"score": {"type": "number"}}},
        )

    assert result == {"score": 9}
    assert captured["model"] == "qwen2.5:3b"
    assert captured["stream"] is True
    assert captured["format"]["type"] == "object"


@pytest.mark.asyncio
async def test_ollama_embeddings_use_native_embed_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://ollama.test",
    ) as client:
        service = EmbeddingService(ollama=OllamaClient(client=client))
        result = await service.embed(["one", "two"], model="ollama/nomic-embed-text")

    assert result == [[0.1, 0.2], [0.3, 0.4]]

