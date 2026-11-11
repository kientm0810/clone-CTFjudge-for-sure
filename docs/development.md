# Local development

Only Docker Desktop and Docker Compose are required.

```bash
copy .env.example .env
docker compose up --build
```

Services:

- Web: <http://localhost:3000>
- API documentation: <http://localhost:8400/docs>
- Health check: <http://localhost:8400/health>

## Local models with Ollama

Ollama runs on the Windows host while the API and worker run in Docker. Use `localhost` from host scripts and `host.docker.internal` from containers:

```dotenv
DEFAULT_CHAT_MODEL=ollama/qwen2.5:3b
DEFAULT_EMBEDDING_MODEL=ollama/nomic-embed-text
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Prepare the models on the host:

```bash
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
```

Check what the Dockerized API can see at <http://localhost:8400/providers/ollama/models>. Agent nodes use `/api/chat`; Database nodes use `/api/embed`.

## Persisted asynchronous runs

The development API supports both execution styles:

- `POST /workflows/execute`: synchronous, useful for debugging a definition.
- `POST /workflows`: save a versioned definition.
- `POST /workflows/{workflow_id}/runs`: enqueue a persisted Celery run.
- `GET /runs/{run_id}`: inspect live status and per-node artifacts.
- `GET /runs/{run_id}/result`: retrieve the final result.
- `POST /runs/{run_id}/retry`: reset and enqueue the same run again.

## Testing from the web UI

Open <http://localhost:3000>, then:

1. Click **Tạo workflow demo** to save a valid `Input -> Agent -> Output` workflow using `ollama/qwen2.5:3b`.
2. Edit the generated runtime JSON if desired.
3. Click **Run workflow**.
4. Watch the graph and status badge update while the page polls the persisted run.
5. Expand a node in **Node runs** to inspect its input, output, or error.

## Visual workflow editor

The local dashboard also includes a small n8n-style builder:

1. Click **Workflow trống** to start with Input and Output, or **Sửa & tạo version** to edit the selected workflow.
2. Drag Input, Agent, Database, or Output nodes from the palette onto the canvas.
3. Connect the right handle of an upstream node to the left handle of the next node.
4. Select a node to edit its name, Agent prompt, or full config JSON.
5. Click **Lưu workflow mới** for a new workflow, or **Lưu version mới** when editing an existing workflow. Definitions remain immutable and the new version becomes active.

The sidebar lists immutable versions. **Rollback** changes the active version pointer without deleting newer versions. A later edit always uses `max(version) + 1`, so saving after a rollback never overwrites history.

### Guided node configuration

The inspector uses type-specific forms by default. Input, Agent, Database, and Output nodes expose only relevant settings; raw configuration remains available under **Advanced JSON**. Model options come from the connected Ollama instance, and Database collection options come from `GET /vectors/collections`. The editor validates required fields and rubric weight totals before saving.

## Run history

Each workflow keeps its execution history across versions. The dashboard can reopen an old result, its original immutable graph, and node trace; retry a terminal run with the same inputs/version; or delete it. Deleting a run also removes vector collections whose names contain that run ID; shared collections are intentionally preserved.

The UI uses the asynchronous API, Redis, Celery, PostgreSQL, and Ollama; it does not simulate execution in the browser.

## CTFJudge rubric template

Click **Tạo CTFJudge RAG** to create the complete golden-solution evaluation workflow. Its judge returns chunk evidence, six qualitative competency ratings, solved/failure analysis, and key insights. The final Output node—not the model—maps ratings to numeric values and calculates the weighted overall score.

Run backend tests in Docker:

```bash
docker compose run --rm api pytest -q
```

Validate the compose model:

```bash
docker compose config
```

