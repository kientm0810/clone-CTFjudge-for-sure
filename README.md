# CTFJudge: LLM as a Judge for Offensive Security Agents
This is the official repository for CTFJudge from "Towards Effective Offensive Security LLM Agents: Hyperparameter Tuning, LLM as a Judge, and a Lightweight CTF Benchmark" (AAAI'26) [[paper](https://arxiv.org/abs/2508.05674)].

> This repository is being extended with a Docker-based visual workflow MVP. The original evaluation scripts remain available at the repository root while the new implementation is developed under `backend/` and `frontend/`.

## Workflow MVP

The new architecture provides four extensible node types: Input, Agent, Database, and Output. Its first workflow chunks a golden solution and a student submission, indexes the golden chunks in pgvector, retrieves relevant evidence, and asks a configurable judge model for a structured comparison.

The CTFJudge RAG template also restores the original six-dimension cybersecurity rubric. The model selects qualitative ratings and explains evidence; the Output node deterministically applies the configured `17/17/17/17/16/16` weights to calculate the final score.

```bash
copy .env.example .env
docker compose up --build
```

- UI: `http://localhost:3000`
- API docs: `http://localhost:8400/docs`
- Architecture: [`docs/architecture.md`](docs/architecture.md)
- Production deployment: [`docs/production.md`](docs/production.md)
- Example workflow: [`examples/simple-comparison-workflow.json`](examples/simple-comparison-workflow.json)

The default development provider is local Ollama: `ollama/qwen2.5:3b` for chat and `ollama/nomic-embed-text` for embeddings. Docker reaches the host Ollama server through `http://host.docker.internal:11434`.

## Production quick start: Ubuntu server + Ollama

The steps below install Ollama directly on the host and run the rest of CTFJudge with Docker Compose. They are intended for a fresh Ubuntu 22.04/24.04 server. Run them in order.

Recommended minimum for the complete stack with `qwen2.5:3b` is 4 vCPU, 16 GB RAM, and 60 GB disk. CPU-only inference works but is slower than GPU inference.

### 1. Install Git and Docker

```bash
sudo apt update
sudo apt install -y ca-certificates curl git

sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Log out of SSH and reconnect so the Docker group change takes effect, then verify:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

### 2. Install and configure Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama --version
```

Ollama binds to `127.0.0.1` by default. The application runs in containers, so make Ollama listen on the host interfaces and limit CPU/RAM concurrency:

```bash
sudo systemctl edit ollama
```

Paste this override, save, and exit:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_NUM_PARALLEL=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_KEEP_ALIVE=5m"
Environment="OLLAMA_CONTEXT_LENGTH=4096"
```

Reload and verify Ollama:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
sudo systemctl status ollama --no-pager
curl http://localhost:11434/api/tags
```

Do not create a public firewall rule for port `11434`. Only the application containers need to reach this port through the Docker host gateway.

### 3. Download the default models

```bash
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
ollama list
```

Optional smoke tests:

```bash
ollama run qwen2.5:3b "Reply with exactly: model ready"

curl http://localhost:11434/api/embed \
  -H "Content-Type: application/json" \
  -d '{"model":"nomic-embed-text","input":"embedding test"}'
```

### 4. Clone the repository

```bash
git clone https://github.com/kientm0810/clone-CTFjudge-for-sure.git
cd clone-CTFjudge-for-sure
```

When updating an existing installation, use `git pull` instead.

### 5. Create the production environment

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

At minimum, replace these values:

```env
APP_SECRET_KEY=replace-with-a-long-random-secret
POSTGRES_PASSWORD=replace-with-a-strong-database-password

# Use the server IP for initial HTTP deployment.
SITE_ADDRESS=http://YOUR_SERVER_IP
CORS_ORIGINS=http://YOUR_SERVER_IP
API_ROOT_PATH=/api
SEED_DEFAULT_WORKFLOW=true

DEFAULT_CHAT_MODEL=ollama/qwen2.5:3b
DEFAULT_EMBEDDING_MODEL=ollama/nomic-embed-text
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

`SEED_DEFAULT_WORKFLOW=true` installs the built-in **CTFJudge RAG - Golden vs Student** workflow when the API starts. On a fresh database it is also published to the `prod` environment automatically, so both the workflow editor and `/prod` are ready without importing JSON manually. Existing workflows and an existing prod deployment are never overwritten. Set this value to `false` only when you intentionally want an empty installation.

Generate a suitable application secret with:

```bash
openssl rand -hex 32
```

If a domain already points to this server, use the domain without `http://` so Caddy can provision HTTPS automatically:

```env
SITE_ADDRESS=judge.example.com
CORS_ORIGINS=https://judge.example.com
```

### 6. Start CTFJudge

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

Only Caddy publishes host ports `80` and `443`. PostgreSQL, Redis, Next.js, and the API remain inside the Compose network.

### 7. Verify the services

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 api worker web caddy
curl http://YOUR_SERVER_IP/api/health
```

Then open:

- Application: the value configured in `SITE_ADDRESS`
- API documentation: `<SITE_ADDRESS>/api/docs`

The cloud firewall should allow inbound TCP `80` and `443` only. Ports `3000`, `8400`, `5432`, `6379`, and `11434` must not be public.

### 8. Update or restart later

```bash
git pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

Useful operational commands:

```bash
# Follow application logs
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f api worker web caddy

# Follow Ollama logs
journalctl -u ollama -f

# Restart the application without deleting data
docker compose --env-file .env.prod -f docker-compose.prod.yml restart

# Stop the application without deleting data
docker compose --env-file .env.prod -f docker-compose.prod.yml down
```

Never use `docker compose down -v` during a normal update because `-v` deletes PostgreSQL and other persistent volumes. More production notes and build troubleshooting are available in [`docs/production.md`](docs/production.md).

Open the **AI Models** tab to register another OpenAI-compatible chat endpoint. Enter the full `/v1/chat/completions` URL and the model identifier expected by that server, save it, then use **Test connection**. Enabled registered models appear automatically in every Agent node dropdown. Requests are sent as JSON directly from the API service; no temporary payload file is created.

Workflow definitions and immutable versions are stored in PostgreSQL. Runs execute asynchronously through Redis and Celery, with each node's status, input, output, and error persisted for inspection.

To test without writing API payloads, open `http://localhost:3000`. The built-in RAG workflow is created automatically, so you can select it, edit its input JSON, and run it immediately. The dashboard polls the persisted run and displays the graph status plus per-node artifacts.

### Reuse one Golden solution for many submissions

Open `/prod` after publishing the RAG workflow. In **Step 1**, paste the Golden solution and select **Prepare & Freeze**. The worker runs only the Golden branch, stores its parsed output and vector collection as an active snapshot, and marks those nodes as `FROZEN`. In **Step 2**, enter one student submission at a time; each grading run reuses the active Golden snapshot instead of embedding it again. Preparing a replacement keeps the current snapshot active until the new one reaches `READY`.

For CTFTiny benchmark, please refer to [CTFTiny Official Repository](https://github.com/NYU-LLM-CTF/CTFTiny/tree/main).

## Overview
This system uses three LLM-powered agents to:

1.**Agent 1**: Decompose writeups into structured solution steps

2.**Agent 2**: Extract and summarize trajectory actions from JSON logs

3.**Agent 3**: Perform qualitative comparison and scoring between writeup and trajectory


## Prerequisites

- Python 3.8+
- Anthropic API key


```bash
export ANTHROPIC_API_KEY='your-api-key'
```

## Usage

```bash
# Run evaluation on all challenge pairs
python run_evaluation.py --writeups-dir <path> --trajs-dir <path>

# Run evaluation on a specific challenge
python run_evaluation.py --challenge <challenge_name> --writeups-dir <path> --trajs-dir <path>
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--challenge`, `-c` | None | Evaluate a specific challenge by name (without extension) |
| `--writeups-dir` | `writeups` | Directory containing `.txt` writeup files |
| `--trajs-dir` | `trajs` | Directory containing `.json` trajectory files |
| `--outputs-dir` | `outputs` | Directory for intermediate agent outputs |
| `--evaluations-dir` | `evaluations` | Directory for final evaluation reports |
| `--errors-dir` | `errors` | Directory for error logs |

## Notes

- Challenge names should match the full docker container names (e.g., `2023q-web-smug_dino`)
- Writeup and trajectory files must share the same base name (`<name>.txt` ↔ `<name>.json`)
- Modify the config file to adjust model selection and token limits (applies to all 3 agents)
- Modifications may be required if using a different trajectory format other than [nyuctf_agents](https://github.com/NYU-LLM-CTF/nyuctf_agents) format.
