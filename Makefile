.PHONY: dev-up dev-down dev-ps install test test-backend test-frontend lint lint-backend lint-frontend seed-data seed-knowledge seed-kaggle seed-mock seed-reset seed-reset-all seed-status seed-enrich seed-vectorize

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

# ─── Install ─────────────────────────────────────────────────
install:
	cd apps/backend && uv sync
	cd apps/frontend && npm install

# ─── Test ────────────────────────────────────────────────────
test: test-backend test-frontend

test-backend:
	cd apps/backend && uv run python -m pytest tests/ -v --tb=short

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

seed-kaggle:
	cd apps/backend && uv run python ../../data/seeds/manage_data.py download
	cd apps/backend && uv run python ../../data/seeds/manage_data.py seed --kaggle

seed-mock:
	cd apps/backend && uv run python ../../data/seeds/manage_data.py seed --mock

seed-reset:
	cd apps/backend && uv run python ../../data/seeds/manage_data.py reset

seed-reset-all:
	cd apps/backend && uv run python ../../data/seeds/manage_data.py reset --all

seed-status:
	cd apps/backend && uv run python ../../data/seeds/manage_data.py status

seed-enrich:
	cd apps/backend && uv run python ../../data/seeds/manage_data.py enrich

seed-vectorize:
	cd apps/backend && uv run python ../../data/seeds/manage_data.py vectorize
