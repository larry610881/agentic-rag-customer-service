from __future__ import annotations

import json
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from prompt_optimizer.config import PromptTarget

logger = logging.getLogger(__name__)

# Mapping: (level, field) -> (table, column, where_clause_template)
_TARGET_MAP = {
    ("system", "base_prompt"): (
        "system_prompt_configs",
        "base_prompt",
        "id = 'default'",
    ),
    ("bot", "system_prompt"): ("bots", "system_prompt", "id = :bot_id"),
    ("bot", "base_prompt"): ("bots", "base_prompt", "id = :bot_id"),
}


class PromptDBClient:
    def __init__(self, db_url: str):
        # Convert async URL to sync if needed (postgresql+asyncpg -> postgresql+psycopg2 or just postgresql)
        sync_url = db_url.replace("+asyncpg", "").replace("+aiosqlite", "")
        self._engine = create_engine(sync_url)

    def read_prompt(self, target: PromptTarget) -> str:
        key = (target.level, target.field)
        if key not in _TARGET_MAP:
            raise ValueError(f"Unknown target: {key}")
        table, column, where = _TARGET_MAP[key]

        query = f"SELECT {column} FROM {table} WHERE {where}"  # noqa: S608
        params: dict[str, str] = {}
        if target.bot_id:
            params["bot_id"] = target.bot_id

        with Session(self._engine) as session:
            result = session.execute(text(query), params)
            row = result.fetchone()
            if row is None:
                raise ValueError(f"No record found for target: {target}")
            return row[0] or ""

    def write_prompt(self, target: PromptTarget, prompt: str) -> None:
        key = (target.level, target.field)
        if key not in _TARGET_MAP:
            raise ValueError(f"Unknown target: {key}")
        table, column, where = _TARGET_MAP[key]

        query = f"UPDATE {table} SET {column} = :prompt WHERE {where}"  # noqa: S608
        params: dict[str, str] = {"prompt": prompt}
        if target.bot_id:
            params["bot_id"] = target.bot_id

        with Session(self._engine) as session:
            result = session.execute(text(query), params)
            if result.rowcount == 0:
                raise ValueError(f"No record updated for target: {target}")
            session.commit()
        logger.info("Prompt updated: %s.%s", table, column)

    def import_dataset(self, dataset: "Dataset") -> str:  # noqa: F821
        """Import a Dataset (from YAML) into eval_datasets + eval_test_cases tables.
        Returns the dataset ID."""
        import uuid

        from prompt_optimizer.dataset import Dataset  # noqa: F811

        assert isinstance(dataset, Dataset)

        dataset_id = str(uuid.uuid4())

        with Session(self._engine) as session:
            # Insert eval_dataset
            session.execute(
                text("""
                INSERT INTO eval_datasets (id, tenant_id, bot_id, name, description, target_prompt,
                    agent_mode, default_assertions, cost_config, include_security, created_at, updated_at)
                VALUES (:id, :tenant_id, :bot_id, :name, :description, :target_prompt,
                    :agent_mode, CAST(:default_assertions AS JSON), CAST(:cost_config AS JSON),
                    :include_security, NOW(), NOW())
            """),
                {
                    "id": dataset_id,
                    "tenant_id": dataset.metadata.tenant_id,
                    "bot_id": dataset.metadata.bot_id or None,
                    "name": dataset.metadata.description or "Imported Dataset",
                    "description": dataset.metadata.description,
                    "target_prompt": dataset.metadata.target_prompt,
                    "agent_mode": dataset.metadata.agent_mode,
                    "default_assertions": json.dumps(
                        [
                            {"type": a.type, "params": a.params}
                            for a in dataset.default_assertions
                        ]
                    ),
                    "cost_config": json.dumps(
                        {
                            "token_budget": dataset.metadata.cost_config.token_budget,
                            "quality_weight": dataset.metadata.cost_config.quality_weight,
                            "cost_weight": dataset.metadata.cost_config.cost_weight,
                        }
                    ),
                    "include_security": True,
                },
            )

            # Insert test cases
            for tc in dataset.test_cases:
                tc_id = str(uuid.uuid4())
                session.execute(
                    text("""
                    INSERT INTO eval_test_cases (id, dataset_id, case_id, question, priority,
                        category, conversation_history, assertions, tags, created_at)
                    VALUES (:id, :dataset_id, :case_id, :question, :priority,
                        :category, CAST(:conversation_history AS JSON), CAST(:assertions AS JSON),
                        CAST(:tags AS JSON), NOW())
                """),
                    {
                        "id": tc_id,
                        "dataset_id": dataset_id,
                        "case_id": tc.id,
                        "question": tc.question,
                        "priority": tc.priority,
                        "category": tc.category,
                        "conversation_history": json.dumps(list(tc.conversation_history))
                        if tc.conversation_history
                        else None,
                        "assertions": json.dumps(
                            [
                                {"type": a.type, "params": a.params}
                                for a in tc.assertions
                            ]
                        ),
                        "tags": None,
                    },
                )

            session.commit()
        return dataset_id

    def read_dataset(self, dataset_id: str) -> "Dataset":  # noqa: F821
        """Read a dataset from DB and return it as a prompt_optimizer Dataset object."""
        from prompt_optimizer.dataset import (
            Assertion,
            CostConfigData,
            Dataset,
            DatasetMetadata,
            TestCase,
        )

        with Session(self._engine) as session:
            # Read dataset
            row = session.execute(
                text("SELECT * FROM eval_datasets WHERE id = :id"),
                {"id": dataset_id},
            ).fetchone()
            if row is None:
                raise ValueError(f"Dataset not found: {dataset_id}")
            ds = row._mapping

            # Read test cases
            cases_rows = session.execute(
                text(
                    "SELECT * FROM eval_test_cases WHERE dataset_id = :dataset_id ORDER BY created_at"
                ),
                {"dataset_id": dataset_id},
            ).fetchall()

            # Parse cost_config
            cost_raw = ds.get("cost_config") or {}
            if isinstance(cost_raw, str):
                cost_raw = json.loads(cost_raw)

            # Parse default_assertions
            da_raw = ds.get("default_assertions") or []
            if isinstance(da_raw, str):
                da_raw = json.loads(da_raw)

            default_assertions = tuple(
                Assertion(type=a["type"], params=a.get("params", {})) for a in da_raw
            )

            metadata = DatasetMetadata(
                tenant_id=ds["tenant_id"],
                bot_id=ds.get("bot_id") or "",
                target_prompt=ds["target_prompt"],
                agent_mode=ds["agent_mode"],
                description=ds.get("description") or "",
                cost_config=CostConfigData(
                    token_budget=cost_raw.get("token_budget", 2000),
                    quality_weight=cost_raw.get("quality_weight", 0.85),
                    cost_weight=cost_raw.get("cost_weight", 0.15),
                ),
            )

            test_cases = []
            for cr in cases_rows:
                c = cr._mapping
                assertions_raw = c["assertions"]
                if isinstance(assertions_raw, str):
                    assertions_raw = json.loads(assertions_raw)
                conv_raw = c.get("conversation_history") or []
                if isinstance(conv_raw, str):
                    conv_raw = json.loads(conv_raw)

                # Merge default_assertions + case assertions
                case_assertions = list(default_assertions)
                for a in assertions_raw:
                    case_assertions.append(
                        Assertion(type=a["type"], params=a.get("params", {}))
                    )

                test_cases.append(
                    TestCase(
                        id=c["case_id"],
                        question=c["question"],
                        priority=c.get("priority", "P1"),
                        category=c.get("category", ""),
                        assertions=tuple(case_assertions),
                        conversation_history=tuple(conv_raw),
                    )
                )

            return Dataset(
                metadata=metadata,
                test_cases=tuple(test_cases),
                default_assertions=default_assertions,
            )

    def close(self) -> None:
        self._engine.dispose()
