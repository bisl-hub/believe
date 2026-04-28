# Believe

A web platform for automated biomedical hypothesis validation. Given a natural-language hypothesis and a literature query, Believe fetches relevant PubMed articles and uses an LLM to classify each article as **supporting**, **rejecting**, or **neutral** toward the hypothesis — then aggregates the results into statistics and visualizations.

## Architecture

```
Browser / API client
        │
        ▼
┌─────────────────────┐
│  Nginx (port 15001) │  React SPA + reverse proxy
│  hypothesis-frontend│
└────────┬────────────┘
         │ /api/
         ▼
┌─────────────────────┐
│  FastAPI             │  REST API, auth, job queue
│  hypothesis-backend  │
└────────┬────────────┘
         │  PostgreSQL
         ▼
┌─────────────────────┐
│  hypothesis-db       │  Postgres 15, persistent volume
└─────────────────────┘
         
Backend also spawns per-job Docker containers:
┌─────────────────────┐
│  hypothesis-validator│  Pipeline: fetch → LLM eval → save results
└─────────────────────┘
```

### Components

| Directory | Description |
|---|---|
| `frontend/` | React + TypeScript + Vite + Tailwind CSS |
| `backend/` | FastAPI + SQLAlchemy + PostgreSQL |
| `pipeline/` | Per-job Docker image: literature fetch + LLM evaluation |

## Features

- **Multi-project workspace** — create isolated projects, each with their own datasets, configs, and jobs
- **4 literature sources** — `qwen_retriever` (semantic/vector), `pubtator3` (entity-tagged MeSH), `pubmed` (keyword/MeSH), `txt_file` (manual PMID list)
- **Two-level caching** — query cache (PMID lists) + article cache (title/abstract), shared across projects
- **Parallel job execution** — queue manager runs up to 10 pipeline containers concurrently
- **Model config management** — save reusable LLM configurations (endpoint, model, temperature, concurrency)
- **Dataset pre-download** — fetch and cache articles before running analysis
- **Project-scoped API keys** — `blv_*` keys allow full platform access without login
- **API docs** — built-in reference at `/api-docs`

## Quick Start

### Prerequisites

- Docker + Docker Compose
- The `hypothesis-validator:latest` pipeline image (built separately)

### Setup

```bash
# 1. Copy env template and fill in values
cp .env.example .env
$EDITOR .env

# 2. Build the pipeline image (only needed once, or after pipeline changes)
docker compose --profile builder up hypothesis-pipeline-builder

# 3. Build and start everything
docker compose up -d --build

# 4. Open http://localhost:15001
```

### Environment Variables (`.env`)

```env
# PostgreSQL
POSTGRES_USER=user
POSTGRES_PASSWORD=secret
POSTGRES_DB=hypothesis_db
DATABASE_URL=postgresql://user:secret@hypothesis-db:5432/hypothesis_db

# JWT
SECRET_KEY=your-secret-key

# LLM (optional defaults; can be overridden per model config)
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_BASE_URL=

# Qwen Retriever (semantic search server)
QWEN_RETRIEVER_BASE_URL=http://your-server:8001
```

## REST API

All API endpoints live under `/api/v1/` and require an `X-Api-Key` header.

```bash
curl -H "X-Api-Key: blv_your_key" http://localhost:15001/api/v1/project
```

See the full reference at `/api-docs` or the [API Docs page](http://localhost:15001/api-docs).

### Typical workflow

```python
import json, time, requests

BASE = "http://localhost:15001/api/v1"
H    = {"X-Api-Key": "blv_your_key"}

# Create and pre-download a dataset
ds = requests.post(f"{BASE}/datasets", headers=H, json={
    "name": "Dopamine schizophrenia — semantic",
    "source_type": "qwen_retriever",
    "query": json.dumps({"q": "dopamine schizophrenia nucleus accumbens", "n": 1000}),
}).json()
requests.post(f"{BASE}/datasets/{ds['id']}/pre-download", headers=H)

# Run analysis using a saved model config
job = requests.post(f"{BASE}/jobs", headers=H, json={
    "name": "DA Hypothesis Run 1",
    "query_term": json.dumps({"q": "dopamine schizophrenia nucleus accumbens", "n": 1000}),
    "hypothesis": "Dopaminergic neurotransmission from nucleus accumbens to caudate is elevated in schizophrenia.",
    "source_type": "qwen_retriever",
    "max_articles": 500,
    "model_config_id": 1,
}).json()

# Poll until done
while True:
    info = requests.get(f"{BASE}/jobs/{job['id']}", headers=H).json()
    if info["status"] == "completed": break
    time.sleep(10)

# Get results
stats = requests.get(f"{BASE}/jobs/{job['id']}/stats", headers=H).json()
print(stats["verdict_counts"])
```

## Generating API Keys

1. Log in to the web UI
2. Go to **Project Settings** (gear icon)
3. Under **API Keys**, click **New Key**
4. Copy the key — it is shown only once

## Development

```bash
# Backend (hot-reload)
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend (hot-reload)
cd frontend
npm install
npm run dev

# Rebuild pipeline image after pipeline/ changes
docker compose --profile builder up --build hypothesis-pipeline-builder
```

## Project Structure

```
believe/
├── backend/
│   ├── app/
│   │   ├── api/          # Route handlers (auth, jobs, configs, api_keys, v1)
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # QueueManager, business logic
│   │   └── main.py       # FastAPI app + router registration
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/        # Analysis, History, Datasets, Configs, ApiDocs, …
│   │   ├── components/   # Layout, shared UI
│   │   └── lib/          # axios client, ProjectContext
│   ├── nginx.conf
│   └── Dockerfile
├── pipeline/
│   ├── src/
│   │   ├── clients/      # pubtator, pubmed, qwen_retriever, openai_client
│   │   ├── llm_worker/   # LLM evaluation logic
│   │   └── main.py       # Pipeline entrypoint
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── batch_process.py      # CLI batch runner (alternative to the API)
```
