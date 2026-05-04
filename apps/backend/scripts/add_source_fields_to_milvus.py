"""External Producer Integration — add source / source_id first-class fields
to existing Milvus collections (Issue #44 Phase 1).

Existing collections were created before source / source_id were promoted to
first-class fields, so this script:

1. Reads the existing schema for each collection
2. Adds the missing fields via ``MilvusClient.add_field`` (Milvus 2.4+) with
   ``default_value`` so legacy rows backfill cleanly
3. Adds an INVERTED index on each new field for O(log n) filter performance
4. Reloads the collection

Idempotent: if the field is already present, that field is skipped.

Usage:
    # Local docker
    cd apps/backend && uv run python -m scripts.add_source_fields_to_milvus

    # Dry-run (read-only — describe state only)
    uv run python -m scripts.add_source_fields_to_milvus --dry-run

    # GCP VM (via IAP SSH; .env carries MILVUS_URI)
    ssh ... "cd .../apps/backend && set -a && source .env && set +a && \\
             uv run python -m scripts.add_source_fields_to_milvus"

Each collection becomes briefly unavailable (~3 s) during the release/load
cycle. Run off-peak.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from pymilvus import DataType, MilvusClient  # noqa: E402

NEW_FIELDS = [
    {
        "name": "source",
        "data_type": DataType.VARCHAR,
        "max_length": 64,
        # Legacy chunks (pre-migration) get a recognizable marker so they can
        # be excluded from real producer filters.
        "default_value": "legacy",
    },
    {
        "name": "source_id",
        "data_type": DataType.VARCHAR,
        "max_length": 128,
        "default_value": "",
    },
]


def _existing_field_names(client: MilvusClient, collection: str) -> set[str]:
    try:
        desc = client.describe_collection(collection_name=collection)
    except Exception as e:
        print(f"  describe_collection failed: {e}")
        return set()
    fields = desc.get("fields", []) if isinstance(desc, dict) else []
    return {f.get("name") for f in fields if isinstance(f, dict)}


def _add_one_field(
    client: MilvusClient,
    collection: str,
    field_spec: dict,
    existing: set[str],
) -> str:
    name = field_spec["name"]
    if name in existing:
        return "already exists, skip"

    try:
        client.add_field(
            collection_name=collection,
            field_name=name,
            data_type=field_spec["data_type"],
            max_length=field_spec["max_length"],
            default_value=field_spec["default_value"],
        )
    except Exception as e:
        return f"add_field FAILED: {e}"

    # Index the new field — high-frequency filter target for dedup / DELETE
    # by-source / search filter.
    try:
        index_params = client.prepare_index_params()
        index_params.add_index(field_name=name, index_type="INVERTED")
        client.create_index(
            collection_name=collection, index_params=index_params
        )
        return "added + INVERTED indexed"
    except Exception as e:
        return f"added but index FAILED: {e}"


def _migrate_collection(client: MilvusClient, collection: str) -> dict:
    result: dict = {"collection": collection, "fields": {}}

    existing = _existing_field_names(client, collection)
    if existing:
        # If both fields already present, nothing to do — skip the
        # release/load cycle entirely.
        all_present = all(f["name"] in existing for f in NEW_FIELDS)
        if all_present:
            for f in NEW_FIELDS:
                result["fields"][f["name"]] = "already exists, skip"
            result["loaded"] = "untouched"
            return result

    # release before schema mutation (Milvus requirement for add_field)
    try:
        client.release_collection(collection_name=collection)
    except Exception as e:
        result["release"] = f"warn: {e}"

    for field_spec in NEW_FIELDS:
        result["fields"][field_spec["name"]] = _add_one_field(
            client, collection, field_spec, existing
        )

    try:
        client.load_collection(collection_name=collection)
        result["loaded"] = True
    except Exception as e:
        result["loaded"] = f"load failed: {e}"

    return result


def _describe(client: MilvusClient, collection: str) -> dict:
    info: dict = {"collection": collection, "fields": {}}
    try:
        stats = client.get_collection_stats(collection_name=collection)
        info["row_count"] = stats.get("row_count", "?")
    except Exception as e:
        info["row_count"] = f"err: {e}"

    existing = _existing_field_names(client, collection)
    for f in NEW_FIELDS:
        info["fields"][f["name"]] = "present" if f["name"] in existing else "missing"
    return info


def run() -> None:
    dry_run = "--dry-run" in sys.argv
    uri = os.environ.get("MILVUS_URI", "http://localhost:19530")
    token = os.environ.get("MILVUS_TOKEN") or None
    db_name = os.environ.get("MILVUS_DB_NAME", "default")

    mode = "DRY-RUN (read only)" if dry_run else "EXECUTE (will modify)"
    print(f"=== Milvus Source Fields Migration — {mode} ===")
    print(f"Target: {uri} (db={db_name})")

    client = MilvusClient(uri=uri, token=token, db_name=db_name)
    collections = client.list_collections()
    print(f"Found {len(collections)} collections")

    if dry_run:
        print("\n| collection | rows | source | source_id |")
        print("|---|---|---|---|")
        for c in collections:
            info = _describe(client, c)
            print(
                f"| {c[:40]} | {info['row_count']} | "
                f"{info['fields'].get('source','?')} | "
                f"{info['fields'].get('source_id','?')} |"
            )
        print(
            "\nTo execute migration (each collection unavailable ~3s):"
            "\n  uv run python -m scripts.add_source_fields_to_milvus"
        )
        return

    for c in collections:
        print(f"\n=== {c} ===")
        result = _migrate_collection(client, c)
        for field, status in result["fields"].items():
            print(f"  {field}: {status}")
        print(f"  load: {result.get('loaded', '?')}")


if __name__ == "__main__":
    run()
