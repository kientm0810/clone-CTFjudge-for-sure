# Node contracts

Every node implements one method:

```python
async def execute(definition, inputs, context) -> NodeResult
```

`inputs` is keyed by upstream node ID. `context` contains runtime inputs, replaceable services, the run ID, and artifacts produced so far.

## Input

Required configuration:

```json
{"input_key": "golden", "document_type": "golden_solution"}
```

## Agent

Required configuration:

```json
{"prompt": "Return JSON only."}
```

Optional configuration: `model`, `temperature`.

For a local model, use a prefixed name such as `ollama/qwen2.5:3b`. An optional `output_schema` object is passed to Ollama's `format` field so the node can require structured JSON.

## Database

Upsert configuration:

```json
{
  "operation": "upsert",
  "collection": "golden-solutions",
  "embedding_model": "openai/text-embedding-3-small"
}
```

Search configuration adds `top_k` and `score_threshold`. Upsert expects an upstream `chunks` list. Search accepts `query_chunks` or `chunks`.

The collection name may contain `{{run_id}}`. The Database node replaces it at runtime,
which lets an upsert/search pair share an isolated collection for each execution:

```json
{"collection": "comparison-{{run_id}}"}
```

## Output

The output node returns its single upstream artifact. When multiple edges enter it, values are keyed by upstream node ID.

