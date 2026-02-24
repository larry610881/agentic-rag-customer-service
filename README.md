# Agentic RAG Customer Service

> AI-powered customer service platform with RAG (Retrieval-Augmented Generation) and multi-agent orchestration for e-commerce.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js_15-000000?style=flat-square&logo=next.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square&logo=langchain&logoColor=white)

## Features

- **Multi-Tenant Architecture** — Tenant isolation with per-tenant knowledge bases and bots
- **Knowledge Base Management** — Upload documents, auto-chunking, and vector embedding
- **RAG Pipeline** — Retrieval-augmented generation with source citation
- **AI Agent Orchestration** — LangGraph-based multi-step agent with tool calling
- **Streaming Chat** — Real-time SSE streaming with conversation history
- **Bot Management** — Create and configure bots with custom system prompts and LLM parameters
- **LINE Integration** — Webhook-based LINE Bot channel support
- **Admin Dashboard** — Next.js dashboard for managing tenants, knowledge bases, bots, and conversations

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 15)                 │
│              Dashboard / Chat / Knowledge               │
└────────────────────────┬────────────────────────────────┘
                         │ REST + SSE
┌────────────────────────▼────────────────────────────────┐
│                   Backend (FastAPI)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ Tenant   │ │Knowledge │ │   RAG    │ │   Agent   │  │
│  │ Context  │ │ Context  │ │ Context  │ │  Context  │  │
│  └──────────┘ └──────────┘ └────┬─────┘ └─────┬─────┘  │
│                                 │             │         │
│                           ┌─────▼─────────────▼──┐      │
│                           │     LangGraph        │      │
│                           │  Agent Orchestrator  │      │
│                           └──────────┬───────────┘      │
│                                      │                  │
│              ┌───────────┬───────────┼──────────┐       │
│              │           │           │          │       │
│           Qdrant      MySQL      OpenAI     LINE API   │
│          (Vector)     (RDBMS)   (LLM/Embed)            │
└─────────────────────────────────────────────────────────┘
```

DDD 4-Layer architecture: Domain → Application → Infrastructure → Interfaces. See `CLAUDE.md` for full details.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router), shadcn/ui, Tailwind CSS, Zustand, TanStack Query |
| Backend | Python 3.12+, FastAPI, dependency-injector, SQLAlchemy 2.0 (async) |
| AI/RAG | LangGraph, Qdrant, OpenAI / Azure OpenAI (Embedding + LLM) |
| Database | MySQL 8, Qdrant (vector) |
| Testing | pytest + pytest-bdd (backend), Vitest + RTL + MSW + Playwright (frontend) |
| DevOps | Docker Compose, Make |

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker & Docker Compose | latest | Database, Qdrant, and service containers |
| Python | 3.12+ | Backend runtime |
| uv | latest | Python package manager |
| Node.js | 20+ | Frontend runtime |
| Make | any | Unified command entry point |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/larry610881/agentic-rag-customer-service.git
cd agentic-rag-customer-service

# 2. Start infrastructure (MySQL, Qdrant, Redis)
make dev-up

# 3. Configure environment
cp apps/backend/.env.example apps/backend/.env
cp apps/frontend/.env.example apps/frontend/.env.local
# Edit .env files with your API keys (OpenAI, etc.)

# 4. Install dependencies
make install

# 5. Seed database
make seed-data

# 6. Run development servers
cd apps/backend && uv run uvicorn src.main:app --reload --port 8000 &
cd apps/frontend && npm run dev &
```

Backend: http://localhost:8000/docs | Frontend: http://localhost:3000

## Make Targets

| Target | Description |
|--------|------------|
| `make dev-up` | Start Docker Compose services |
| `make dev-down` | Stop Docker Compose services |
| `make install` | Install backend + frontend dependencies |
| `make test` | Run all tests (backend + frontend) |
| `make test-backend` | Run backend pytest suite |
| `make test-frontend` | Run frontend Vitest suite |
| `make lint` | Lint all (ruff + mypy + ESLint + tsc) |
| `make seed-data` | Seed database with initial data |
| `make seed-knowledge` | Seed knowledge base with sample documents |

## Project Structure

```
agentic-rag-customer-service/
├── apps/
│   ├── backend/                # Python FastAPI — DDD 4-Layer
│   │   ├── src/
│   │   │   ├── domain/         # Entities, Value Objects, Repository Interfaces
│   │   │   ├── application/    # Use Cases, Command/Query Handlers
│   │   │   ├── infrastructure/ # DB, Qdrant, LangGraph, External APIs
│   │   │   └── interfaces/     # FastAPI Routers, CLI
│   │   └── tests/
│   └── frontend/               # Next.js 15 App Router
│       ├── src/
│       │   ├── app/            # App Router pages
│       │   ├── components/     # Shared UI components (shadcn/ui)
│       │   ├── features/       # Feature modules (chat, knowledge, auth)
│       │   ├── hooks/          # Shared hooks + TanStack Query
│       │   ├── stores/         # Zustand stores
│       │   └── test/           # Test infrastructure (fixtures, MSW)
│       └── e2e/                # Playwright E2E tests
├── infra/                      # Docker Compose configs
├── data/                       # Seed data, test documents
├── Makefile                    # Unified command entry point
└── CLAUDE.md                   # Development conventions
```

## License

MIT
