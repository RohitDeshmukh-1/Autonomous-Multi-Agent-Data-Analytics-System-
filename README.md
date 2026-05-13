# Cloud Data Analyst Agent v2.0

A full-stack, AI-powered data analyst that accepts natural language questions about your data and returns SQL/Pandas code, results, charts, and analytical insights — all orchestrated by a **self-correcting LangGraph agent** with **real-time observability**, **multi-turn conversations**, and **proactive anomaly detection**.

## ✨ What's New in v2.0

| Feature | Description |
|---------|-------------|
| 🧠 **Multi-Turn Conversations** | Follow-up queries like "now filter that to Q4" or "break it down by region" |
| 🔍 **Anomaly Detection** | Proactive statistical analysis — outliers, spikes, null concentrations |
| 📊 **Agent Trace Visualization** | Real-time pipeline view showing each node's status and latency |
| 🎯 **Query Explainability** | "Show Your Work" panel with query plan, complexity, self-correction chain |
| 📈 **Data Profiler** | One-click dataset overview with type inference, distributions, correlations |
| 📉 **Metrics Dashboard** | p50/p95/p99 latencies, cache hit ratios, self-correction rates |
| ⚡ **Connection Pooling** | ~1-2s faster per query via warm DB connections |
| 🔒 **Free Embeddings** | Local sentence-transformers (no API key, no cost) |
| 🛡️ **Rate Limiting** | slowapi-based request throttling for production |

## Architecture

```
User query
    │
    ▼
FastAPI (SSE stream with trace events)
    │
    ▼
LangGraph Agent (traced, self-correcting)
    ├── Intent Router        (Groq llama-3.1-8b)
    ├── Memory Retriever     (pgvector cosine search)
    ├── Query Planner        (schema-aware, conversation-aware)
    ├── SQL / Pandas Gen     (Groq llama-3.1-70b, multi-turn context)
    ├── Safety Validator     (sqlglot AST + RestrictedPython)
    ├── Executor             (Neon / SQLite / Pandas sandbox)
    ├── Error Classifier →
    │   Self Corrector  (up to 3 retries)
    ├── Insight Synthesizer  (Groq)
    ├── Anomaly Detector     (Z-score, spike detection, null analysis)
    ├── Visualizer           (Plotly JSON)
    └── Memory Updater       (pgvector write)

React + Tailwind frontend  ←→  FastAPI backend
```

## Tech Stack (100% Free Tier)

| Layer | Service | Free tier |
|-------|---------|-----------| 
| LLM inference | [Groq](https://console.groq.com) | ✅ 30 req/min |
| Embeddings | **Local** (sentence-transformers) | ✅ No API key needed |
| Database + pgvector | [Neon](https://neon.tech) | ✅ 0.5 GB |
| Cache | [Upstash Redis](https://upstash.com) | ✅ 10K req/day |
| File storage | [Supabase Storage](https://supabase.com) | ✅ 1 GB |
| Backend hosting | [Railway](https://railway.app) | ✅ $5 credit / mo |
| Frontend hosting | [Railway / Vercel](https://railway.app) | ✅ Free |


## Local Development

### 1. Prerequisites

- Python 3.11+
- Node.js 20+
- Groq, Neon, Upstash, Supabase API keys (see `.env.example`)
- **No embedding API key needed** — embeddings run locally

### 2. Backend

```bash
# Clone and set up environment
cp .env.example .env
# Fill in keys (Groq, Neon, Upstash, Supabase — no Together AI needed)

# Install dependencies
pip install -r requirements.txt

# Run database migrations
psql $NEON_DATABASE_URL -f scripts/migrate.sql

# (Optional) Seed demo e-commerce data
python scripts/seed_demo.py

# Start API server
uvicorn api.main:app --reload --port 8000
```

> ⏳ First startup downloads the embedding model (~420MB). Subsequent starts are instant.

API docs at: http://localhost:8000/docs

### 3. Frontend

```bash
cd frontend
npm install
cp ../.env.example .env.local
# Set VITE_API_BASE_URL=http://localhost:8000

npm run dev
# Frontend at http://localhost:5173
```

## Project Structure

```
├── agent/              LangGraph agent nodes + graph
│   ├── graph.py        Traced agent pipeline
│   ├── trace.py        Real-time execution tracing
│   ├── metrics.py      In-memory metrics collector
│   └── nodes/
│       ├── anomaly_detector.py   Proactive anomaly detection
│       ├── data_profiler.py      Dataset profiling engine
│       └── ...                   All other pipeline nodes
├── api/                FastAPI routers + main app
│   └── routers/
│       ├── metrics.py  Observability endpoint
│       ├── profile.py  Data profiling endpoint
│       └── ...
├── connectors/         Neon, CSV, SQLite, Sheets connectors
├── dashboard/          Dashboard panel persistence
├── db/                 Connection pooling
├── eval/               Evaluation dataset + runner
├── frontend/           React + Tailwind + Plotly UI
│   └── src/pages/
│       ├── MetricsPage.tsx   Observability dashboard
│       ├── ProfilePage.tsx   Data profiler UI
│       └── ...
├── llm/                Groq client + local embeddings
├── reports/            PDF generator (WeasyPrint + Jinja2)
├── sandbox/            SQL (sqlglot) + Python (RestrictedPython)
├── schema/             Schema ingestion + pgvector retrieval
├── scripts/            migrate.sql, seed_demo.py
├── storage/            Supabase Storage helpers
├── render.yaml         Render deployment spec
└── requirements.txt
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/query/run` | Run agent, return full JSON result with trace |
| `POST` | `/api/query/stream` | SSE stream: trace events + insight tokens |
| `POST` | `/api/upload/file` | Upload CSV/SQLite, ingest schema |
| `GET` | `/api/history/{session_id}` | List query history |
| `DELETE` | `/api/history/{id}` | Delete history record |
| `POST` | `/api/dashboard/panel` | Pin chart to dashboard |
| `GET` | `/api/dashboard/panel/{user_id}` | List dashboard panels |
| `DELETE` | `/api/dashboard/panel/{id}` | Remove panel |
| `POST` | `/api/report/generate` | Download PDF report |
| `POST` | `/api/schema/ingest` | Re-ingest connector schema |
| `GET` | `/api/schema/{connector_id}` | Get schema summary |
| `GET` | `/api/metrics/` | System observability metrics |
| `POST` | `/api/profile/` | Generate data profile |
| `GET` | `/health` | Health check |

## Security Model

| Layer | Mechanism |
|-------|-----------|
| SQL | sqlglot AST — blocks all DML/DDL (DROP, DELETE, UPDATE, INSERT, …) |
| Python | RestrictedPython + AST walk — no filesystem, os, subprocess, socket |
| DB | Neon read-only session (`SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY`) |
| API | CORS origin whitelist + slowapi rate limiting |
| Embeddings | Fully local — no data sent to third-party embedding APIs |

## Key Differentiators

1. **Self-Correcting Agent** — Automatically fixes broken SQL/Python up to 3 times
2. **Multi-Turn Context** — Follow-up queries reference previous results
3. **Real-Time Observability** — Live pipeline trace + latency/token metrics
4. **Proactive Anomaly Detection** — Surfaces statistical insights you didn't ask for
5. **Production Security** — AST-level code validation, read-only DB, rate limiting
6. **100% Free Stack** — Every service uses free tiers, including local embeddings
