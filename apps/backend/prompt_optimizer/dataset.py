from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from prompt_optimizer.assertions import ASSERTION_REGISTRY

logger = logging.getLogger(__name__)


class DatasetValidationError(Exception):
    """Dataset validation error."""


@dataclass(frozen=True)
class Assertion:
    type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TestCase:
    id: str
    question: str
    priority: str = "P1"  # P0 | P1 | P2
    category: str = ""
    assertions: tuple[Assertion, ...] = ()
    conversation_history: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class CostConfigData:
    token_budget: int = 2000
    quality_weight: float = 0.85
    cost_weight: float = 0.15


@dataclass(frozen=True)
class DatasetMetadata:
    tenant_id: str = ""
    bot_id: str = ""
    target_prompt: str = "base_prompt"
    agent_mode: str = "router"
    description: str = ""
    cost_config: CostConfigData = field(default_factory=CostConfigData)


@dataclass(frozen=True)
class Dataset:
    metadata: DatasetMetadata
    test_cases: tuple[TestCase, ...]
    default_assertions: tuple[Assertion, ...] = ()


class DatasetLoader:
    """Loads and validates eval dataset from YAML files."""

    def __init__(self, schema_path: Path | None = None):
        if schema_path is None:
            schema_path = Path(__file__).parent / "datasets" / "_schema.json"
        self._schema = (
            json.loads(schema_path.read_text()) if schema_path.exists() else None
        )

    def load(self, path: Path) -> Dataset:
        """Load a dataset YAML file, resolving includes."""
        raw = self._read_yaml(path)
        self._validate_schema(raw)

        # Resolve includes
        all_cases_raw = list(raw.get("test_cases", []))
        for include_path in raw.get("includes", []):
            resolved = (path.parent / include_path).resolve()
            if not resolved.exists():
                raise DatasetValidationError(f"Include file not found: {include_path}")
            included = self._read_yaml(resolved)
            all_cases_raw.extend(included.get("test_cases", []))

        # Parse default assertions
        default_assertions = tuple(
            Assertion(type=a["type"], params=a.get("params", {}))
            for a in raw.get("default_assertions", [])
        )

        # Validate assertion types
        self._validate_assertion_types(default_assertions, all_cases_raw)

        # Parse test cases
        test_cases = self._parse_cases(all_cases_raw, default_assertions)

        # Check duplicate IDs
        ids = [tc.id for tc in test_cases]
        duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
        if duplicates:
            raise DatasetValidationError(f"Duplicate case IDs: {set(duplicates)}")

        # Parse metadata
        metadata = self._parse_metadata(raw.get("metadata", {}))

        return Dataset(
            metadata=metadata,
            test_cases=test_cases,
            default_assertions=default_assertions,
        )

    def load_from_string(self, content: str, base_dir: Path | None = None) -> Dataset:
        """Load dataset from a YAML string (useful for testing)."""
        raw = yaml.safe_load(content)
        if not isinstance(raw, dict):
            raise DatasetValidationError("Invalid YAML: expected a mapping")
        self._validate_schema(raw)

        all_cases_raw = list(raw.get("test_cases", []))
        for include_path in raw.get("includes", []):
            if base_dir is None:
                raise DatasetValidationError("Cannot resolve includes without base_dir")
            resolved = (base_dir / include_path).resolve()
            if not resolved.exists():
                raise DatasetValidationError(f"Include file not found: {include_path}")
            included = self._read_yaml(resolved)
            all_cases_raw.extend(included.get("test_cases", []))

        default_assertions = tuple(
            Assertion(type=a["type"], params=a.get("params", {}))
            for a in raw.get("default_assertions", [])
        )
        self._validate_assertion_types(default_assertions, all_cases_raw)
        test_cases = self._parse_cases(all_cases_raw, default_assertions)

        ids = [tc.id for tc in test_cases]
        duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
        if duplicates:
            raise DatasetValidationError(f"Duplicate case IDs: {set(duplicates)}")

        metadata = self._parse_metadata(raw.get("metadata", {}))
        return Dataset(
            metadata=metadata,
            test_cases=test_cases,
            default_assertions=default_assertions,
        )

    def _read_yaml(self, path: Path) -> dict:
        with open(path) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise DatasetValidationError(f"Invalid YAML in {path}: expected a mapping")
        return data

    def _validate_schema(self, raw: dict) -> None:
        if self._schema:
            try:
                jsonschema.validate(raw, self._schema)
            except jsonschema.ValidationError as e:
                raise DatasetValidationError(
                    f"Schema validation failed: {e.message}"
                ) from e

    def _validate_assertion_types(
        self, defaults: tuple[Assertion, ...], cases_raw: list[dict]
    ) -> None:
        all_types: set[str] = set()
        for a in defaults:
            all_types.add(a.type)
        for case in cases_raw:
            for a in case.get("assertions", []):
                all_types.add(a["type"])
        unknown = all_types - set(ASSERTION_REGISTRY.keys())
        if unknown:
            raise DatasetValidationError(f"Unknown assertion types: {unknown}")

    def _parse_metadata(self, meta_raw: dict) -> DatasetMetadata:
        cost_raw = meta_raw.get("cost_config", {})
        return DatasetMetadata(
            tenant_id=meta_raw.get("tenant_id", ""),
            bot_id=meta_raw.get("bot_id", ""),
            target_prompt=meta_raw.get("target_prompt", "base_prompt"),
            agent_mode=meta_raw.get("agent_mode", "router"),
            description=meta_raw.get("description", ""),
            cost_config=CostConfigData(
                token_budget=cost_raw.get("token_budget", 2000),
                quality_weight=cost_raw.get("quality_weight", 0.85),
                cost_weight=cost_raw.get("cost_weight", 0.15),
            ),
        )

    def _parse_cases(
        self, cases_raw: list[dict], defaults: tuple[Assertion, ...]
    ) -> tuple[TestCase, ...]:
        results = []
        for raw in cases_raw:
            case_assertions = list(defaults)  # Start with defaults
            for a in raw.get("assertions", []):
                case_assertions.append(
                    Assertion(type=a["type"], params=a.get("params", {}))
                )
            history = tuple(raw.get("conversation_history", []))
            results.append(
                TestCase(
                    id=raw["id"],
                    question=raw["question"],
                    priority=raw.get("priority", "P1"),
                    category=raw.get("category", ""),
                    assertions=tuple(case_assertions),
                    conversation_history=history,
                )
            )
        return tuple(results)


def dataset_to_yaml(dataset: Dataset) -> str:
    """Export a Dataset to YAML string."""
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "metadata": {
            "tenant_id": dataset.metadata.tenant_id,
            "bot_id": dataset.metadata.bot_id,
            "target_prompt": dataset.metadata.target_prompt,
            "agent_mode": dataset.metadata.agent_mode,
            "description": dataset.metadata.description,
            "cost_config": {
                "token_budget": dataset.metadata.cost_config.token_budget,
                "quality_weight": dataset.metadata.cost_config.quality_weight,
                "cost_weight": dataset.metadata.cost_config.cost_weight,
            },
        },
        "default_assertions": [
            {"type": a.type, "params": a.params} for a in dataset.default_assertions
        ],
        "test_cases": [],
    }

    # Exclude default assertions from case-level assertions
    default_types = {(a.type, str(a.params)) for a in dataset.default_assertions}

    for tc in dataset.test_cases:
        case_assertions = [
            {"type": a.type, "params": a.params}
            for a in tc.assertions
            if (a.type, str(a.params)) not in default_types
        ]

        case_data: dict[str, Any] = {
            "id": tc.id,
            "question": tc.question,
            "priority": tc.priority,
        }
        if tc.category:
            case_data["category"] = tc.category
        if tc.conversation_history:
            case_data["conversation_history"] = list(tc.conversation_history)
        if case_assertions:
            case_data["assertions"] = case_assertions

        data["test_cases"].append(case_data)

    return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
