"""CompileWikiUseCase — 把 bot 關聯的 KB 文件編譯成 WikiGraph。

流程：
1. 驗證 bot 存在、屬於 tenant、至少有一個 KB
2. 載入 KB 的所有 document（從 DocumentRepository）
3. 對每個 document 呼叫 WikiCompilerService.extract()
4. 用 graph_builder 合併 → nodes/edges/backlinks/clusters
5. Upsert WikiGraph（若已存在先刪掉再建，避免 UNIQUE(bot_id) 衝突）

此 Use Case 會被 FastAPI BackgroundTasks 呼叫
（透過 safe_background_task + lazy resolve pattern）。
必須使用 `independent_session_scope()` 避免跨 request session leak。

Token usage 累計進 WikiGraph.metadata['total_usage']。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.domain.bot.repository import BotRepository
from src.domain.knowledge.repository import DocumentRepository
from src.domain.rag.value_objects import TokenUsage
from src.domain.shared.exceptions import EntityNotFoundError, ValidationError
from src.domain.wiki.entity import WikiGraph
from src.domain.wiki.repository import WikiGraphRepository
from src.domain.wiki.services import (
    CompileResult,
    ExtractedGraph,
    WikiCompilerService,
)
from src.domain.wiki.value_objects import WikiGraphId, WikiStatus
from src.infrastructure.logging import get_logger
from src.infrastructure.wiki.graph_builder import (
    build_backlinks,
    detect_clusters_louvain,
    merge_extracted_graphs,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class CompileWikiCommand:
    bot_id: str
    tenant_id: str


class CompileWikiUseCase:
    def __init__(
        self,
        bot_repository: BotRepository,
        document_repository: DocumentRepository,
        wiki_graph_repository: WikiGraphRepository,
        wiki_compiler: WikiCompilerService,
    ) -> None:
        self._bot_repo = bot_repository
        self._doc_repo = document_repository
        self._wiki_repo = wiki_graph_repository
        self._compiler = wiki_compiler

    async def execute(self, command: CompileWikiCommand) -> CompileResult:
        log = logger.bind(
            bot_id=command.bot_id,
            tenant_id=command.tenant_id,
        )
        log.info("wiki.compile.start")

        # 1. Validate bot
        bot = await self._bot_repo.find_by_id(command.bot_id)
        if bot is None:
            raise EntityNotFoundError("Bot", command.bot_id)
        if bot.tenant_id != command.tenant_id:
            raise EntityNotFoundError("Bot", command.bot_id)
        if not bot.knowledge_base_ids:
            raise ValidationError(
                f"Bot {command.bot_id} has no knowledge base bound"
            )

        # MVP：只編譯第一個 KB（未來可擴充為多 KB 合併）
        kb_id = bot.knowledge_base_ids[0]
        log = log.bind(kb_id=kb_id)

        # 2. Mark existing graph as compiling (or create pending one first)
        existing = await self._wiki_repo.find_by_bot_id(
            command.tenant_id, command.bot_id
        )
        if existing is not None:
            existing.status = WikiStatus.COMPILING.value
            existing.updated_at = datetime.now(timezone.utc)
            await self._wiki_repo.save(existing)
            graph_id = existing.id
        else:
            placeholder = WikiGraph(
                id=WikiGraphId(),
                tenant_id=command.tenant_id,
                bot_id=command.bot_id,
                kb_id=kb_id,
                status=WikiStatus.COMPILING.value,
            )
            await self._wiki_repo.save(placeholder)
            graph_id = placeholder.id

        # 3. Load documents for the KB
        documents = await self._doc_repo.find_all_by_kb(kb_id)
        log.info("wiki.compile.docs_loaded", doc_count=len(documents))

        if not documents:
            log.warning("wiki.compile.empty_kb")
            await self._save_graph(
                graph_id=graph_id,
                tenant_id=command.tenant_id,
                bot_id=command.bot_id,
                kb_id=kb_id,
                nodes={},
                edges={},
                backlinks={},
                clusters=[],
                total_usage=None,
                doc_count=0,
                status=WikiStatus.READY.value,
            )
            return CompileResult(document_count=0)

        # 4. Extract each document
        extracted_graphs: list[ExtractedGraph] = []
        total_usage = TokenUsage(
            model="",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost=0.0,
        )
        errors: list[str] = []
        for doc in documents:
            try:
                content = doc.content or ""
                if not content.strip():
                    log.info(
                        "wiki.compile.skip_empty_doc",
                        document_id=doc.id.value,
                        filename=doc.filename,
                    )
                    continue
                g = await self._compiler.extract(
                    document_id=doc.id.value,
                    content=content,
                )
                extracted_graphs.append(g)
                if g.usage is not None:
                    total_usage = total_usage + g.usage
            except Exception as exc:
                err = f"{doc.filename}: {type(exc).__name__}: {exc}"
                log.warning(
                    "wiki.compile.doc_failed",
                    document_id=doc.id.value,
                    error=err,
                )
                errors.append(err)
                continue

        # 5. Merge + build backlinks + clusters
        nodes, edges = merge_extracted_graphs(extracted_graphs)
        backlinks = build_backlinks(edges)
        clusters = detect_clusters_louvain(nodes, edges)

        log.info(
            "wiki.compile.merged",
            node_count=len(nodes),
            edge_count=len(edges),
            cluster_count=len(clusters),
            input_tokens=total_usage.input_tokens,
            output_tokens=total_usage.output_tokens,
            estimated_cost=round(total_usage.estimated_cost, 6),
        )

        status = (
            WikiStatus.READY.value
            if len(errors) < len(documents)
            else WikiStatus.FAILED.value
        )
        await self._save_graph(
            graph_id=graph_id,
            tenant_id=command.tenant_id,
            bot_id=command.bot_id,
            kb_id=kb_id,
            nodes=nodes,
            edges=edges,
            backlinks=backlinks,
            clusters=clusters,
            total_usage=total_usage,
            doc_count=len(documents),
            status=status,
            errors=errors,
        )

        return CompileResult(
            node_count=len(nodes),
            edge_count=len(edges),
            cluster_count=len(clusters),
            document_count=len(documents),
            total_usage=total_usage,
            errors=errors,
        )

    async def _save_graph(
        self,
        *,
        graph_id: WikiGraphId,
        tenant_id: str,
        bot_id: str,
        kb_id: str,
        nodes: dict,
        edges: dict,
        backlinks: dict,
        clusters: list,
        total_usage: TokenUsage | None,
        doc_count: int,
        status: str,
        errors: list[str] | None = None,
    ) -> None:
        metadata: dict = {
            "doc_count": doc_count,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "cluster_count": len(clusters),
        }
        if total_usage is not None:
            metadata["token_usage"] = {
                "input": total_usage.input_tokens,
                "output": total_usage.output_tokens,
                "total": total_usage.total_tokens,
                "cache_read": total_usage.cache_read_tokens,
                "cache_creation": total_usage.cache_creation_tokens,
                "estimated_cost": round(total_usage.estimated_cost, 6),
            }
        if errors:
            metadata["errors"] = errors[:20]  # cap to avoid unbounded growth

        now = datetime.now(timezone.utc)
        graph = WikiGraph(
            id=graph_id,
            tenant_id=tenant_id,
            bot_id=bot_id,
            kb_id=kb_id,
            status=status,
            nodes=nodes,
            edges=edges,
            backlinks=backlinks,
            clusters=clusters,
            metadata=metadata,
            compiled_at=now,
            updated_at=now,
        )
        await self._wiki_repo.save(graph)
