# CTFJudge workflow architecture

The new implementation is a small, extensible DAG workflow system. It intentionally starts with four node types:

- `input`: converts runtime values into documents.
- `agent`: sends a prompt plus upstream artifacts to a configured chat model.
- `database`: embeds and upserts chunks, or retrieves similar chunks from pgvector.
- `output`: exposes the final upstream artifact as the workflow result.

```text
Golden input -> Golden parser agent -> Database(upsert) --+
                                                       |
Student input -> Student parser agent -----------------+-> Database(search)
                                                               |
                                                               v
                                                        Comparison agent
                                                               |
                                                               v
                                                             Output
```

## Runtime boundaries

- The API validates definitions and starts executions.
- The workflow engine only understands nodes, edges, and typed artifacts.
- The visual editor serializes its canvas back to the same node/edge definition consumed by the API; no execution logic lives in the browser.
- Node implementations call services through `WorkflowContext`.
- Model and vector implementations can be replaced without changing the executor.
- Database collections can use `{{run_id}}` so vectors from concurrent submissions stay isolated.
- CTFJudge qualitative ratings come from the judge model, while the Output node owns deterministic weighted-score calculation.
- Redis/Celery is the asynchronous execution boundary. Workflow, run, and per-node execution state are persisted in PostgreSQL. A synchronous endpoint remains available for development and tests.

## Persisted execution lifecycle

1. `POST /workflows` validates and stores an immutable workflow version.
2. `POST /workflows/{id}/versions` appends an immutable version; activating an older version only moves the workflow's current-version pointer.
3. `POST /workflows/{id}/runs` creates a pending run and enqueues it in Redis.
4. The Celery worker executes nodes sequentially and records each node's input, output, status, and timestamps.
5. `GET /runs/{id}` exposes live progress; `GET /runs/{id}/result` exposes the completed result.
6. Failed or completed runs can be reset and queued again through `POST /runs/{id}/retry`.
7. `GET /workflows/{id}/runs` lists executions across workflow versions. Terminal runs can be deleted through `DELETE /runs/{id}`; run-scoped vector collections are cleaned with them.

## Storage

PostgreSQL stores application state. The `vector` extension stores chunk embeddings. Uploaded files and large artifacts use Docker volumes during the MVP. Object storage can replace those volumes later.

