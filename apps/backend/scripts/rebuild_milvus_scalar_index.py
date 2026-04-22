"""一次性 rebuild 既有 Milvus collection 的 scalar index (S-KB-Studio.0)。

原本 tenant_id / document_id 的 index_type="" 等於沒建 scalar index，
hotfix `660008a` 後新建的 collection 會用 INVERTED，但既有 collection 需
drop → create → load 才會更新。

用法：
    # Local docker
    cd apps/backend && uv run python -m scripts.rebuild_milvus_scalar_index

    # GCP VM (透過 IAP SSH 後，.env 會帶 MILVUS_URI)
    ssh ... "cd .../apps/backend && set -a && source .env && set +a && \\
             uv run python -m scripts.rebuild_milvus_scalar_index"

冪等：若 index 已是 INVERTED，此 script 是 no-op（會 drop 後重建，結果一致）。
執行期間目標 collection 會短暫 unavailable (~3 秒)，建議 off-peak 執行。
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from pymilvus import MilvusClient  # noqa: E402

TARGET_FIELDS = ["tenant_id", "document_id"]
NEW_INDEX_TYPE = "INVERTED"


def _rebuild_one(client: MilvusClient, collection: str) -> dict:
    result = {"collection": collection, "fields": {}}
    for field in TARGET_FIELDS:
        try:
            info = client.describe_index(
                collection_name=collection, index_name=field
            )
            current = (
                info.get("index_type") if isinstance(info, dict) else None
            )
            # 舊版 pymilvus 的 describe_index 可能回 list
            if isinstance(info, list) and info:
                current = info[0].get("index_type")
        except Exception:
            current = None

        if current == NEW_INDEX_TYPE:
            result["fields"][field] = f"already {NEW_INDEX_TYPE}, skip"
            continue

        # release → drop index → create index → load
        try:
            client.release_collection(collection_name=collection)
        except Exception as e:
            # 可能 collection 沒 load，忽略
            pass

        try:
            client.drop_index(collection_name=collection, index_name=field)
        except Exception as e:
            result["fields"][field] = f"drop failed (skip): {e}"
            # 可能本來就沒 index，繼續嘗試 create
        index_params = client.prepare_index_params()
        index_params.add_index(field_name=field, index_type=NEW_INDEX_TYPE)
        try:
            client.create_index(
                collection_name=collection, index_params=index_params
            )
            result["fields"][field] = f"rebuilt (was={current!r})"
        except Exception as e:
            result["fields"][field] = f"FAILED: {e}"

    # reload collection
    try:
        client.load_collection(collection_name=collection)
        result["loaded"] = True
    except Exception as e:
        result["loaded"] = f"load failed: {e}"

    return result


def _describe(client: MilvusClient, collection: str) -> dict:
    """Dry-run: 回報當前每個 scalar field 的 index 狀態"""
    info = {"collection": collection, "fields": {}}
    try:
        stats = client.get_collection_stats(collection_name=collection)
        info["row_count"] = stats.get("row_count", "?")
    except Exception as e:
        info["row_count"] = f"err: {e}"

    for field in TARGET_FIELDS:
        try:
            desc = client.describe_index(
                collection_name=collection, index_name=field
            )
            if isinstance(desc, list) and desc:
                desc = desc[0]
            current = desc.get("index_type") if isinstance(desc, dict) else "?"
            info["fields"][field] = current or "(empty string)"
        except Exception as e:
            msg = str(e)
            if "index not found" in msg.lower() or "doesn't exist" in msg.lower():
                info["fields"][field] = "no index"
            else:
                info["fields"][field] = f"err: {msg[:60]}"
    return info


def run() -> None:
    dry_run = "--dry-run" in sys.argv
    uri = os.environ.get("MILVUS_URI", "http://localhost:19530")
    token = os.environ.get("MILVUS_TOKEN") or None
    db_name = os.environ.get("MILVUS_DB_NAME", "default")
    mode = "DRY-RUN (read only)" if dry_run else "EXECUTE (will modify)"
    print(f"=== Milvus Scalar Index {mode} ===")
    print(f"Target: {uri} (db={db_name})")

    client = MilvusClient(uri=uri, token=token, db_name=db_name)
    collections = client.list_collections()
    print(f"Found {len(collections)} collections")

    if dry_run:
        print("\n| collection | rows | tenant_id | document_id |")
        print("|---|---|---|---|")
        for c in collections:
            info = _describe(client, c)
            print(
                f"| {c[:40]} | {info['row_count']} | "
                f"{info['fields'].get('tenant_id','?')} | "
                f"{info['fields'].get('document_id','?')} |"
            )
        print(
            f"\nTo execute rebuild (will briefly unavailable ~3s per collection):"
            f"\n  uv run python -m scripts.rebuild_milvus_scalar_index"
        )
        return

    for c in collections:
        print(f"\n=== Rebuilding {c} ===")
        result = _rebuild_one(client, c)
        for field, status in result["fields"].items():
            print(f"  {field}: {status}")
        print(f"  load: {result['loaded']}")


if __name__ == "__main__":
    run()
