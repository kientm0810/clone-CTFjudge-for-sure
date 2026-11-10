# CTFJudge: LLM as a Judge for Offensive Security Agents
This is the official repository for CTFJudge from "Towards Effective Offensive Security LLM Agents: Hyperparameter Tuning, LLM as a Judge, and a Lightweight CTF Benchmark" (AAAI'26) [[paper](https://arxiv.org/abs/2508.05674)].

> This repository is being extended with a Docker-based visual workflow MVP. The original evaluation scripts remain available at the repository root while the new implementation is developed under `backend/` and `frontend/`.

## Workflow MVP

The new architecture provides four extensible node types: Input, Agent, Database, and Output. Its first workflow chunks a golden solution and a student submission, indexes the golden chunks in pgvector, retrieves relevant evidence, and asks a configurable judge model for a structured comparison.

```bash
copy .env.example .env
docker compose up --build
```

- UI: `http://localhost:3000`
- API docs: `http://localhost:8400/docs`
- Architecture: [`docs/architecture.md`](docs/architecture.md)
- Example workflow: [`examples/simple-comparison-workflow.json`](examples/simple-comparison-workflow.json)

The default development provider is local Ollama: `ollama/qwen2.5:3b` for chat and `ollama/nomic-embed-text` for embeddings. Docker reaches the host Ollama server through `http://host.docker.internal:11434`.

Workflow definitions and immutable versions are stored in PostgreSQL. Runs execute asynchronously through Redis and Celery, with each node's status, input, output, and error persisted for inspection.

To test without writing API payloads, open `http://localhost:3000`, create the Ollama demo workflow, edit its input JSON, and run it. The dashboard polls the persisted run and displays the graph status plus per-node artifacts.

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
