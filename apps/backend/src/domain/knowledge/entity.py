from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.knowledge.value_objects import (
    ChunkId,
    DocumentId,
    KnowledgeBaseId,
    ProcessingTaskId,
)


@dataclass
class KnowledgeBase:
    id: KnowledgeBaseId = field(default_factory=KnowledgeBaseId)
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    kb_type: str = "user"  # "user" | "system"
    ocr_mode: str = "general"  # "general" | "catalog" | "auto"
    ocr_model: str = ""
    context_model: str = ""
    classification_model: str = ""
    # Per-KB chunk_strategy override（空 = 走全域 config.chunk_strategy）。
    # 白名單由後端 API validator 強制：
    # "" | "auto" | "recursive" | "separator" | "json_record" | "csv_row"
    chunk_strategy: str = ""
    # Per-KB sliced OCR — "" 不切片；"RxC" 如 "2x3" / "3x2" 啟用切片 OCR。
    # 用於 rare brand char 提升辨識率（薈/樟腦/萃這類字形混淆 case）。
    ocr_slice_grid: str = ""
    # Issue #47 L3：KB-level DM metadata 萃取設定 + 結果儲存
    # dm_metadata_model: 抽 DM metadata 用的 LLM 模型（空 = 不啟用）
    # dm_metadata: 萃取結果 JSON（dm_period / merchant / global_activities /
    #   member_conditions / featured_categories / special_activities）
    # ExtractKBDMMetadataUseCase 在 KB 全 docs done 後自動 trigger 寫入
    # 此欄位；RAG query path 把 dm_metadata prepend 到 LLM system context
    # 作 cross-page 背景資訊（不重 embed）。
    dm_metadata_model: str = ""
    dm_metadata: dict = field(default_factory=dict)
    document_count: int = 0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class Document:
    id: DocumentId = field(default_factory=DocumentId)
    kb_id: str = ""
    tenant_id: str = ""
    filename: str = ""
    content_type: str = ""
    content: str = ""
    raw_content: bytes = b""
    storage_path: str = ""
    status: str = "pending"
    parent_id: str | None = None
    page_number: int | None = None
    chunk_count: int = 0
    avg_chunk_length: int = 0
    min_chunk_length: int = 0
    max_chunk_length: int = 0
    quality_score: float = 0.0
    quality_issues: list[str] = field(default_factory=list)
    # Issue #44: External producer reference. Empty string for documents
    # uploaded via the single-file UI; populated by bulk ingest from the
    # incoming metadata so process_document_use_case can stamp Milvus
    # chunks with these values for later DELETE /by-source dedup.
    source: str = ""
    source_id: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class Chunk:
    id: ChunkId = field(default_factory=ChunkId)
    document_id: str = ""
    tenant_id: str = ""
    content: str = ""
    context_text: str = ""
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)
    # S-KB-Studio.1: inline edit + quality summary 用；對應 ChunkModel 既有欄位
    category_id: str | None = None
    quality_flag: str | None = None


@dataclass
class ChunkCategory:
    id: str = ""
    kb_id: str = ""
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    chunk_count: int = 0
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ProcessingTask:
    id: ProcessingTaskId = field(default_factory=ProcessingTaskId)
    document_id: str = ""
    tenant_id: str = ""
    status: str = "pending"
    progress: int = 0
    error_message: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
