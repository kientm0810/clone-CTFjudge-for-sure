# Node contracts

Every node implements one method:

```python
async def execute(definition, inputs, context) -> NodeResult
```

`inputs` is the resolved input mapping declared by that node. `context` contains runtime inputs, replaceable services, the run ID, and artifacts produced so far.

## Input mapping expressions

Edges define execution dependencies and which nodes are upstream. A node selects the exact data it needs with an `inputs` mapping:

```json
{
  "id": "golden-index",
  "type": "database",
  "inputs": {"chunks": "{{ steps.golden-parser.output.chunks }}"}
}
```

Supported expressions:

- `{{ steps.<node-id>.output }}` returns the complete output of an upstream step.
- `{{ steps.<node-id>.output.<path> }}` returns one nested field.
- `{{ runtime.<key> }}` reads a workflow runtime input.
- `{{ run.id }}` returns the current run ID.

A full-value expression preserves arrays, objects, numbers, and booleans. An expression inside longer text is rendered as text. A step may only reference a connected ancestor; missing, unrelated, self, and downstream references fail validation.

Definitions without `inputs` retain the legacy direct-parent payload for old immutable versions. New workflows created in the editor require explicit mappings.

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

Search configuration adds `top_k` and `score_threshold`. Upsert expects an input named `chunks`; search expects `query_chunks`.

In the visual editor, `Store vectors` maps to `operation: "upsert"` and `Search vectors` maps to `operation: "search"`. Fields that do not apply to the selected operation are hidden from the guided form but remain accessible through Advanced JSON.

The collection name may contain `{{run_id}}`. The Database node replaces it at runtime,
which lets an upsert/search pair share an isolated collection for each execution:

```json
{"collection": "comparison-{{run_id}}"}
```

## Output

The Output node exposes its resolved mapping, so it can reference earlier ancestors without visual shortcut edges:

```json
{
  "id": "report",
  "type": "output",
  "inputs": {
    "analysis": "{{ steps.comparison-agent.output }}",
    "retrieval_results": "{{ steps.golden-search.output.retrieval_results }}",
    "golden_chunks": "{{ steps.golden-parser.output.chunks }}"
  },
  "config": {"format": "comparison_report"}
}
```

`format: "comparison_report"` builds the compact similarity report. `format: "json"` returns the mapped fields unchanged.

`format: "ctfjudge_report"` applies the original CTFJudge rating-to-score mapping and the default `17/17/17/17/16/16` competency weights. The upstream Agent supplies qualitative ratings; the Output node calculates `overall_score` and `formula_breakdown` deterministically, so changing the judge model does not change the scoring formula.

