# Production deployment

The production stack is defined in `docker-compose.prod.yml`. Only Caddy publishes host ports. PostgreSQL, Redis, the API, the worker, and Next.js communicate through the private Compose network.

## 1. Create the production environment file

```bash
cp .env.prod.example .env.prod
nano .env.prod
```

At minimum, replace:

- `APP_SECRET_KEY`
- `POSTGRES_PASSWORD`
- `SITE_ADDRESS`
- `CORS_ORIGINS`

For an IP-only deployment:

```env
SITE_ADDRESS=http://34.21.163.229
CORS_ORIGINS=http://34.21.163.229
```

For a domain with automatic HTTPS, point its DNS A record to the server and use:

```env
SITE_ADDRESS=judge.example.com
CORS_ORIGINS=https://judge.example.com
```

## 2. Start the production stack

If the development stack is running, stop it without deleting volumes:

```bash
docker compose down
```

Build and start production:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

If BuildKit stalls while resolving provenance:

```bash
export BUILDX_NO_DEFAULT_ATTESTATIONS=1
docker compose --env-file .env.prod -f docker-compose.prod.yml build --progress=plain
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --no-build
```

## 3. Verify the deployment

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail=100 api worker web caddy
curl http://YOUR_SERVER_IP/api/health
```

From another machine, open the value configured in `SITE_ADDRESS`. API documentation is available at `/api/docs`.

## 4. Firewall

Allow inbound TCP `80` and `443`. Remove the public rules for `3000` and `8400` after the production stack is healthy. Those ports are not published by `docker-compose.prod.yml`.

## 5. Updating

```bash
git pull
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```

Do not run `docker compose down -v` during normal updates because `-v` deletes the database and persistent data volumes.

## Embedding model choices

The sample workflows explicitly use `ollama/nomic-embed-text`. `DEFAULT_EMBEDDING_MODEL` is only a fallback for nodes that do not specify an embedding model.

Production options:

1. Run Ollama on a CPU server and keep `ollama/nomic-embed-text`. This is simple but needs enough RAM and will be slower without a GPU.
2. Keep Ollama on another machine and set `OLLAMA_BASE_URL` to a private, authenticated endpoint reachable by both the API and worker containers.
3. Use a hosted embedding provider supported by LiteLLM. Set its API key in `.env.prod`, then change every Database node's `embedding_model` to the provider model identifier. Existing vectors must be re-indexed whenever the embedding model changes.

The registered models in the **AI Models** tab currently represent chat completion endpoints. They do not yet register `/v1/embeddings` endpoints.
