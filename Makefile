.PHONY: dev-up dev-down dev-ps dev-backend install test test-backend test-frontend lint lint-backend lint-frontend seed-data seed-knowledge

COMPOSE_FILE := infra/docker-compose.yml
COMPOSE_DEV  := infra/docker-compose.dev.yml
COMPOSE_CMD  := docker compose -f $(COMPOSE_FILE) -f $(COMPOSE_DEV)

# ─── Docker Compose ──────────────────────────────────────────
dev-up:
	$(COMPOSE_CMD) up -d
	@echo "Waiting for services to become healthy..."
	@$(COMPOSE_CMD) ps

dev-down:
	$(COMPOSE_CMD) down

dev-ps:
	$(COMPOSE_CMD) ps

# ─── Dev Server ──────────────────────────────────────────────
dev-backend:
	cd apps/backend && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port ${PORT:-8001}

# ─── Install ─────────────────────────────────────────────────
install:
	cd apps/backend && uv sync
	cd apps/frontend && npm install

# ─── Test ────────────────────────────────────────────────────
test: test-backend test-frontend

test-backend: test-backend-unit test-backend-integration test-backend-e2e

test-backend-unit:
	cd apps/backend && uv run python -m pytest tests/unit/ -v --tb=short --cov=src --cov-report=term-missing

test-backend-integration:
	cd apps/backend && uv run python -m pytest tests/integration/ -v --tb=short -p no:asyncio

test-backend-e2e:
	@if [ -d apps/backend/tests/e2e ]; then cd apps/backend && uv run python -m pytest tests/e2e/ -v --tb=short -p no:asyncio; fi

test-frontend:
	cd apps/frontend && npx vitest run --passWithNoTests

# ─── Lint ────────────────────────────────────────────────────
lint: lint-backend lint-frontend

lint-backend:
	cd apps/backend && uv run ruff check src/ tests/
	cd apps/backend && uv run mypy src/

lint-frontend:
	cd apps/frontend && npx eslint src/
	cd apps/frontend && npx tsc --noEmit

# ─── Data ────────────────────────────────────────────────────
seed-data:
	cd apps/backend && uv run python -m src.infrastructure.db.seed

seed-knowledge:
	cd apps/backend && uv run python ../../data/seeds/seed_knowledge.py
