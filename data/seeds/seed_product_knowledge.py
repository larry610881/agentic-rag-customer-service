"""Vectorize product_catalog into system KB → Documents → Chunks → Qdrant.

Reads product_catalog table, creates a system-type KnowledgeBase per tenant,
inserts Documents (batched 50 products each), then runs chunk/embed/upsert.

Usage:
    cd apps/backend
    uv run python ../../data/seeds/seed_product_knowledge.py
"""

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg

# Ensure backend src is on the path
backend_root = Path(__file__).resolve().parent.parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_root))

from src.config import Settings  # noqa: E402
from src.domain.knowledge.entity import Chunk, Document, KnowledgeBase  # noqa: E402
from src.domain.knowledge.value_objects import (  # noqa: E402
    ChunkId,
    DocumentId,
    KnowledgeBaseId,
)
from src.infrastructure.embedding.fake_embedding_service import (  # noqa: E402
    FakeEmbeddingService,
)
from src.infrastructure.embedding.openai_embedding_service import (  # noqa: E402
    OpenAIEmbeddingService,
)
from src.infrastructure.qdrant.qdrant_vector_store import QdrantVectorStore  # noqa: E402
from src.infrastructure.text_splitter.recursive_text_splitter_service import (  # noqa: E402
    RecursiveTextSplitterService,
)

PRODUCTS_PER_DOCUMENT = 50
SYSTEM_KB_NAME = "商品目錄"
SYSTEM_KB_DESC = "系統自動建立的商品目錄知識庫，供商品推薦功能使用"


def _format_product(row: asyncpg.Record) -> str:
    """Format a single product record as structured text."""
    parts = [f"【商品】{row['product_name']}"]
    if row.get("category_en"):
        parts.append(f"分類：{row['category_en']}")

    dims: list[str] = []
    # product_catalog only has weight in description text, pull from description
    if row.get("price"):
        dims.append(f"價格：R${float(row['price']):.2f}")
    if row.get("stock") is not None:
        dims.append(f"庫存：{row['stock']} 件")
    if dims:
        parts.append(" | ".join(dims))

    parts.append(row["description"])
    return "\n".join(parts)


async def vectorize(database_url: str | None = None) -> None:
    """Main vectorization entry point."""
    settings = Settings()

    dsn = database_url or os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/agentic_rag",
    )
    conn = await asyncpg.connect(dsn)

    try:
        # Ensure kb_type column exists on knowledge_bases
        await conn.execute("""
            ALTER TABLE knowledge_bases
            ADD COLUMN IF NOT EXISTS kb_type VARCHAR(20) NOT NULL DEFAULT 'user'
        """)

        # Build services
        splitter = RecursiveTextSplitterService(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        if settings.embedding_provider == "fake":
            embedder = FakeEmbeddingService(
                vector_size=settings.embedding_vector_size
            )
        else:
            # Provider-specific default base URLs (mirrors container.py)
            _PROVIDER_BASE_URLS = {
                "openai": "https://api.openai.com/v1",
                "google": "https://generativelanguage.googleapis.com/v1beta/openai",
                "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            }
            base_url = (
                settings.embedding_base_url
                or _PROVIDER_BASE_URLS.get(
                    settings.embedding_provider, "https://api.openai.com/v1"
                )
            )
            embedder = OpenAIEmbeddingService(
                api_key=settings.effective_embedding_api_key,
                model=settings.embedding_model,
                base_url=base_url,
                batch_size=settings.embedding_batch_size,
                max_retries=settings.embedding_max_retries,
                timeout=settings.embedding_timeout,
                batch_delay=settings.embedding_batch_delay,
            )

        vector_store = QdrantVectorStore(
            host=settings.qdrant_host,
            port=settings.qdrant_rest_port,
        )

        # Get all tenants
        tenants = await conn.fetch("SELECT id, name FROM tenants")
        if not tenants:
            print("No tenants found. Run seed-data first.")
            return

        # Get product catalog
        products = await conn.fetch(
            "SELECT product_id, product_name, description, stock, price, category_en "
            "FROM product_catalog ORDER BY category_en, product_id"
        )
        if not products:
            print("No products in product_catalog. Run 'manage_data.py enrich' first.")
            return

        print(f"Found {len(products)} products, {len(tenants)} tenants.")

        for tenant in tenants:
            tenant_id = tenant["id"]
            tenant_name = tenant["name"]
            print(f"\nTenant: {tenant_name} ({tenant_id})")

            # Check if system KB already exists
            existing_kb = await conn.fetchrow(
                "SELECT id FROM knowledge_bases "
                "WHERE tenant_id = $1 AND kb_type = 'system' AND name = $2",
                tenant_id, SYSTEM_KB_NAME,
            )

            if existing_kb:
                kb_id = existing_kb["id"]
                print(f"  System KB already exists: {kb_id}, skipping.")
                continue

            # Create system KB
            kb_id = str(uuid4())
            await conn.execute(
                "INSERT INTO knowledge_bases (id, tenant_id, name, description, kb_type, created_at, updated_at) "
                "VALUES ($1, $2, $3, $4, 'system', NOW(), NOW())",
                kb_id, tenant_id, SYSTEM_KB_NAME, SYSTEM_KB_DESC,
            )
            print(f"  Created system KB: {kb_id}")

            # Batch products into documents
            total_chunks = 0
            total_vectors = 0
            collection_name = f"kb_{kb_id}"

            for batch_start in range(0, len(products), PRODUCTS_PER_DOCUMENT):
                batch = products[batch_start:batch_start + PRODUCTS_PER_DOCUMENT]
                content = "\n---\n".join(_format_product(p) for p in batch)

                doc_id = str(uuid4())
                batch_num = batch_start // PRODUCTS_PER_DOCUMENT + 1

                # Insert document record
                await conn.execute(
                    "INSERT INTO documents (id, kb_id, tenant_id, filename, content_type, content, status, chunk_count, created_at, updated_at) "
                    "VALUES ($1, $2, $3, $4, 'text/plain', $5, 'completed', 0, NOW(), NOW())",
                    doc_id, kb_id, tenant_id,
                    f"product_catalog_batch_{batch_num}.txt",
                    content,
                )

                # Chunk
                chunks = splitter.split(content, doc_id, tenant_id)

                # Save chunk records
                for chunk in chunks:
                    await conn.execute(
                        "INSERT INTO chunks (id, document_id, tenant_id, content, chunk_index, metadata) "
                        "VALUES ($1, $2, $3, $4, $5, $6)",
                        chunk.id.value, doc_id, tenant_id,
                        chunk.content, chunk.chunk_index,
                        "{}",
                    )

                # Embed
                texts = [c.content for c in chunks]
                vectors = await embedder.embed_texts(texts)

                # Upsert to Qdrant
                ids = [c.id.value for c in chunks]
                payloads = [
                    {
                        "content": chunk.content,
                        "document_id": doc_id,
                        "document_name": f"product_catalog_batch_{batch_num}.txt",
                        "tenant_id": tenant_id,
                        "kb_id": kb_id,
                        "chunk_index": chunk.chunk_index,
                    }
                    for chunk in chunks
                ]

                vector_dim = len(vectors[0]) if vectors else settings.embedding_vector_size
                await vector_store.ensure_collection(collection_name, vector_dim)
                await vector_store.upsert(collection_name, ids, vectors, payloads)

                # Update document chunk_count
                await conn.execute(
                    "UPDATE documents SET chunk_count = $1 WHERE id = $2",
                    len(chunks), doc_id,
                )

                total_chunks += len(chunks)
                total_vectors += len(vectors)

                print(
                    f"  Batch {batch_num}: {len(batch)} products → "
                    f"{len(chunks)} chunks → {len(vectors)} vectors"
                )

            print(
                f"  Total: {total_chunks} chunks, {total_vectors} vectors "
                f"in collection '{collection_name}'"
            )

        print("\nVectorization complete.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(vectorize())
