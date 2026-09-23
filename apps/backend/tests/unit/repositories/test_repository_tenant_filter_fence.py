"""Fence（Issue #101 B8）：repository 查詢缺租戶條件時，必須顯式列名並寫明檢查在哪。

背景：跨租戶 IDOR（C2 對話、C4–C7 eval dataset、C8/C9 bot）的根因都是
「repository 以 id 查、不帶 tenant_id，呼叫端也忘了比對」。本測試以 AST 靜態掃描
``src/infrastructure/db/repositories/`` 全部 repository class 的每個 public async
方法：只要它對「有 tenant_id 欄位的 model」建 select / update / delete（或
``session.get``、``text()`` 原生 SQL 碰到該表），方法本體就必須引用
``<Model>.tenant_id``（WHERE 條件或 join 到有租戶的父表）、或把 ``tenant_id``
傳給 scope helper；否則必須出現在 ALLOWLIST，理由寫明租戶檢查「在哪裡」做。

新增一個以 id / 父 id 查詢的方法 → 這裡會紅 → 先確認呼叫端真的有歸屬檢查，
再登記。登記理由過期（方法消失或已自帶 tenant 條件）也會紅，清單要誠實。

本檔建立時逐一追過呼叫端，追出的缺口已修並留 regression：
tests/unit/repositories/test_cross_tenant_callers.py。
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import re
from pathlib import Path

import pytest

import src.infrastructure.db.models as models_pkg
from src.infrastructure.db.base import Base

BACKEND = Path(__file__).resolve().parents[3]
REPO_DIR = BACKEND / "src" / "infrastructure" / "db" / "repositories"
STATEMENT_BUILDERS = {"select", "update", "delete", "get"}

# 共用理由片語
_KB_SCOPE = (
    "kb_id 歸屬由 ensure_kb_accessible 驗（application/knowledge/_admin_kb_check.py；"
    "document_router 以 require_kb_document_scope 對全 router 套用）"
)
_DOC_SCOPE = (
    "document/chunk 歸屬由呼叫端驗：document_router.require_kb_document_scope"
    "（doc.kb_id == 已驗 KB）、chunk use case 以 tenant_match_or_admin 比對 "
    "chunk/doc/kb 三層；其餘呼叫端是 worker（process/reprocess/split/classify/"
    "reap），參數來自已驗歸屬的 enqueue"
)
_BOT_SCOPE = (
    "bot 歸屬由呼叫端比對 bot.tenant_id：ensure_bot_tenant（application/bot/"
    "_tenant_guard.py）或 `bot.tenant_id != tenant_id → 404`（prompt_gate/"
    "version_use_cases、gate_run_use_cases、replay_use_cases、upload_bot_icon、"
    "send_message._load_bot_config）；LINE webhook 以 channel 簽章認證"
)
_VERSION_SCOPE = (
    "版本以 bot_id / version_id 操作，呼叫前 version_use_cases / gate_run_use_cases "
    "/ replay_use_cases / update_bot_use_case 已驗 bot.tenant_id，版本本身以 "
    "find_by_id(version_id, tenant_id) 取得"
)
_UPSERT = (
    "寫入：以 entity 主鍵查既有列做 upsert，entity 由已驗歸屬的 use case 載入或"
    "新建，tenant_id 取自 entity 本身"
)
_SYSTEM_ADMIN = "僅 system_admin 端點（require_role('system_admin')）"
_BACKGROUND = "僅背景作業 / 排程（worker.py、outbox drainer），無使用者輸入的 id"

ALLOWLIST: dict[tuple[str, str], str] = {
    # ---- bot / 版本
    ("SQLAlchemyBotRepository", "find_by_id"): _BOT_SCOPE,
    ("SQLAlchemyBotRepository", "delete"): (
        "DeleteBotUseCase 先 find_by_id + ensure_bot_tenant 才刪"
    ),
    ("SQLAlchemyBotRepository", "find_by_short_code"): (
        "short_code 是公開識別碼（widget / LINE 入口），回傳的 bot 即決定租戶；"
        "widget_router / handle_webhook 以 bot.tenant_id 作後續全部 scope"
    ),
    ("SQLAlchemyBotRepository", "save"): _UPSERT,
    ("SQLAlchemyBotConfigVersionRepository", "save"): _UPSERT,
    ("SQLAlchemyBotConfigVersionRepository", "save_status_transition"): _VERSION_SCOPE,
    ("SQLAlchemyBotConfigVersionRepository", "find_current"): _VERSION_SCOPE,
    ("SQLAlchemyBotConfigVersionRepository", "next_version_no"): _VERSION_SCOPE,
    ("SQLAlchemyBotConfigVersionRepository", "set_current"): _VERSION_SCOPE,
    ("SQLAlchemyBotConfigVersionRepository", "revert_validating_to_draft"): (
        _BACKGROUND + "：gate run 收尾（gate_run_use_cases）以自身 run 的版本 id 回滾"
    ),
    ("SQLAlchemyBotConfigVersionRepository", "revert_stale_validating_versions"): (
        _BACKGROUND + "：啟動時清理卡在 validating 的版本（全平台）"
    ),
    # ---- 知識庫 / 文件 / chunk / 分類
    ("SQLAlchemyKnowledgeBaseRepository", "find_by_id"): (
        "ensure_kb_accessible 本身即以此查 KB 再比對 kb.tenant_id；其他呼叫端"
        "（query_rag 存在性檢查、reembed/process worker、milvus admin 列表）"
        "不回傳 KB 內容給他租戶"
    ),
    ("SQLAlchemyKnowledgeBaseRepository", "update"): (
        "僅 extract_dm_metadata worker（kb_id 來自 process_document 已驗歸屬的文件）"
    ),
    ("SQLAlchemyKnowledgeBaseRepository", "delete"): (
        "DeleteKnowledgeBaseUseCase 先 ensure_kb_accessible 才刪；outbox 路徑同"
    ),
    ("SQLAlchemyDocumentRepository", "find_by_id"): _DOC_SCOPE,
    ("SQLAlchemyDocumentRepository", "find_by_ids"): (
        "dm_image_query_tool：document_id 來自已帶 tenant_id filter 的向量檢索結果"
    ),
    ("SQLAlchemyDocumentRepository", "delete"): (
        "DeleteDocumentUseCase 以路徑 kb_id 比對 doc.kb_id（router 已驗 KB 歸屬）"
    ),
    ("SQLAlchemyDocumentRepository", "update_status"): _DOC_SCOPE,
    ("SQLAlchemyDocumentRepository", "update_storage_path"): (
        "UploadDocumentUseCase 先 ensure_kb_accessible 再建文件，id 為剛建立的文件"
    ),
    ("SQLAlchemyDocumentRepository", "update_content"): _DOC_SCOPE,
    ("SQLAlchemyDocumentRepository", "update_quality"): _DOC_SCOPE,
    ("SQLAlchemyDocumentRepository", "find_all_by_kb"): _KB_SCOPE,
    ("SQLAlchemyDocumentRepository", "find_top_level_by_kb"): _KB_SCOPE,
    ("SQLAlchemyDocumentRepository", "find_stale_pending"): (
        _BACKGROUND + "：reap_stale_documents 全平台掃卡住的文件"
    ),
    ("SQLAlchemyDocumentRepository", "find_children"): _DOC_SCOPE,
    ("SQLAlchemyDocumentRepository", "count_children_by_status"): _DOC_SCOPE,
    ("SQLAlchemyDocumentRepository", "delete_chunks_by_document"): _DOC_SCOPE,
    ("SQLAlchemyDocumentRepository", "find_chunks_by_document_paginated"): _DOC_SCOPE,
    ("SQLAlchemyDocumentRepository", "find_chunk_ids_by_kb"): _KB_SCOPE,
    ("SQLAlchemyDocumentRepository", "update_chunks_category"): (
        "classify_kb worker：kb_id 來自 knowledge_base_router 已驗歸屬後的 enqueue"
    ),
    ("SQLAlchemyDocumentRepository", "find_chunks_by_category"): (
        "GetCategoryChunksUseCase：router 先 _require_accessible_kb，再比對 "
        "cat.kb_id == 路徑 kb_id"
    ),
    ("SQLAlchemyDocumentRepository", "find_chunk_by_id"): (
        "update/delete/assign chunk use case 以 tenant_match_or_admin 比對 "
        "chunk/doc/kb；admin_chunk_router.re_embed_chunk 入列前同樣比對"
    ),
    ("SQLAlchemyDocumentRepository", "update_chunk"): (
        "UpdateChunkUseCase 先以 tenant_match_or_admin 驗 chunk/doc/kb 三層"
    ),
    ("SQLAlchemyDocumentRepository", "delete_chunk"): (
        "DeleteChunkUseCase 先以 tenant_match_or_admin 驗 chunk/doc/kb 三層"
    ),
    ("SQLAlchemyDocumentRepository", "find_chunks_by_kb_paginated"): _KB_SCOPE,
    ("SQLAlchemyChunkCategoryRepository", "find_by_kb"): _KB_SCOPE,
    ("SQLAlchemyChunkCategoryRepository", "find_by_id"): (
        "呼叫端（knowledge_base_router.update_category、Assign/Delete category "
        "use case、GetCategoryChunks）先驗 KB 歸屬，再比對 cat.kb_id == 路徑 kb_id"
    ),
    ("SQLAlchemyChunkCategoryRepository", "update_name"): (
        "knowledge_base_router.update_category：_require_accessible_kb + "
        "cat.kb_id == kb_id 後才改名"
    ),
    ("SQLAlchemyChunkCategoryRepository", "delete_by_id"): (
        "DeleteCategoryUseCase：ensure_kb_accessible + category.kb_id == kb_id"
    ),
    ("SQLAlchemyChunkCategoryRepository", "assign_chunks"): (
        "AssignChunksUseCase：ensure_kb_accessible，chunk 逐一比對 tenant 與 kb"
    ),
    ("SQLAlchemyChunkCategoryRepository", "delete_by_kb"): (
        "classify_kb worker：kb_id 來自 knowledge_base_router 已驗歸屬後的 enqueue"
    ),
    ("SQLAlchemyChunkCategoryRepository", "update_chunk_counts"): (
        "classify_kb worker（同上）；計數寫回的是真實值，不讀出他租戶資料"
    ),
    # ---- 對話 / 回饋 / 記憶
    ("SQLAlchemyConversationRepository", "find_by_id"): (
        "呼叫端比對 conversation.tenant_id：send_message（C2，含 bot_id）、"
        "submit_feedback、get_conversation_token_usage；feedback_router 的 id "
        "來自已依 tenant 查出的回饋；generate_summary 為 worker"
    ),
    ("SQLAlchemyConversationRepository", "find_by_ids"): (
        "search_conversations：id 來自已帶 tenant_id filter 的 Milvus 摘要檢索"
    ),
    ("SQLAlchemyConversationRepository", "find_latest_by_visitor"): (
        "LINE webhook：bot 由簽章驗過的 channel 決定，visitor_id 為 LINE user"
    ),
    ("SQLAlchemyConversationRepository", "find_pending_summary"): (
        _BACKGROUND + "：worker 摘要排程"
    ),
    ("SQLAlchemyConversationRepository", "save"): _UPSERT,
    ("SQLAlchemyFeedbackRepository", "find_by_message_id"): (
        "SubmitFeedbackUseCase 先驗 conversation.tenant_id，並拒絕他租戶既有回饋；"
        "LINE postback 的 message_id 由伺服器產生的按鈕帶回"
    ),
    ("SQLAlchemyFeedbackRepository", "update"): (
        "SubmitFeedbackUseCase：find_by_message_id 後已比對 existing.tenant_id"
    ),
    ("SQLAlchemyFeedbackRepository", "find_by_conversation"): (
        "ListFeedbackUseCase.execute_by_conversation 以 f.tenant_id == tenant_id 過濾"
    ),
    ("SQLAlchemyMemoryFactRepository", "find_by_profile"): (
        "profile_id 由 ResolveIdentityUseCase 以 (tenant_id, source, external_id) "
        "解析（conversation_memory_service），不接受外部傳入"
    ),
    ("SQLAlchemyMemoryFactRepository", "upsert_by_key"): (
        "ExtractMemoryUseCase（worker）：profile_id 同上由租戶內身分解析"
    ),
    ("SQLAlchemyMemoryFactRepository", "delete"): (
        "目前 src/ 無呼叫端；新呼叫端須先以租戶內身分解析 profile 再刪"
    ),
    ("SQLAlchemyVisitorProfileRepository", "find_by_id"): (
        "目前 src/ 無呼叫端；profile 一律經 find_identity(tenant_id, …) 解析"
    ),
    ("SQLAlchemyVisitorProfileRepository", "save"): _UPSERT,
    # ---- eval / 優化
    ("SQLAlchemyEvalDatasetRepository", "find_by_id"): (
        "ensure_dataset_read / ensure_dataset_write（application/eval_dataset/"
        "_tenant_guard.py）；EstimateCostUseCase 同樣呼叫 ensure_dataset_read"
    ),
    ("SQLAlchemyEvalDatasetRepository", "delete"): (
        "DeleteEvalDatasetUseCase 先 ensure_dataset_write"
    ),
    ("SQLAlchemyEvalDatasetRepository", "find_all"): (
        "ListEvalDatasetsUseCase 只在 tenant_id=None 時呼叫，router 僅 "
        "system_admin 傳 None"
    ),
    ("SQLAlchemyEvalDatasetRepository", "find_platform_base"): (
        "平台通用集設計上供全部租戶讀取（gate run 強制注入），唯讀"
    ),
    ("SQLAlchemyOptimizationRunRepository", "get_iterations"): (
        "run_use_cases 取得後一律 _check_run_tenant(iterations, tenant_id)"
    ),
    ("SQLAlchemyOptimizationRunRepository", "get_best_iteration"): (
        "目前 src/ 無呼叫端；新呼叫端須比照 run_use_cases 做 _check_run_tenant"
    ),
    # ---- 系統 / 背景 / 認證
    ("SQLAlchemyErrorEventRepository", "get_by_id"): _SYSTEM_ADMIN,
    ("SQLAlchemyErrorEventRepository", "resolve"): _SYSTEM_ADMIN,
    ("SQLAlchemyErrorEventRepository", "cleanup_before"): _BACKGROUND,
    ("SQLAlchemyLogRetentionPolicyRepository", "cleanup_logs_before"): _BACKGROUND,
    ("SQLAlchemyOutboxEventRepository", "claim_batch"): _BACKGROUND,
    ("SQLAlchemyOutboxEventRepository", "update"): _BACKGROUND,
    ("SQLAlchemyOutboxEventRepository", "find_by_id"): (
        _SYSTEM_ADMIN + "（outbox admin router）"
    ),
    ("SQLAlchemyOutboxEventRepository", "delete"): _SYSTEM_ADMIN + "（outbox admin）",
    ("SQLAlchemyOutboxEventRepository", "count_by_status"): (
        _SYSTEM_ADMIN + "／健康檢查"
    ),
    ("SQLAlchemyOutboxEventRepository", "oldest_pending_age_seconds"): (
        _SYSTEM_ADMIN + "／健康檢查"
    ),
    ("SQLAlchemyProcessingTaskRepository", "find_by_id"): (
        "task_router 取得後比對 task.tenant_id；confirm_upload 比對 "
        "task.document_id 與已驗 KB 的文件"
    ),
    ("SQLAlchemyProcessingTaskRepository", "find_by_document_id"): (
        _BACKGROUND + "：reap_stale_documents"
    ),
    ("SQLAlchemyProcessingTaskRepository", "update_status"): (
        _BACKGROUND + "：process/reprocess worker 更新自己的 task"
    ),
    ("SQLAlchemyQuotaAlertLogRepository", "find_undelivered"): (
        _BACKGROUND + "：quota_email_dispatch"
    ),
    ("SQLAlchemyQuotaAlertLogRepository", "mark_delivered"): (
        _BACKGROUND + "：quota_email_dispatch"
    ),
    ("SQLAlchemyRateLimitConfigRepository", "delete"): (
        _SYSTEM_ADMIN + "（admin_router rate-limits）"
    ),
    ("SQLAlchemyRateLimitConfigRepository", "save"): (
        _UPSERT + "；僅 system_admin 的 admin_router 寫入"
    ),
    ("SQLAlchemyTokenLedgerRepository", "find_all_for_cycle"): (
        "list_all_tenants_quotas（admin_router，require_role('system_admin')）與 "
        "process_quota_alerts 背景作業"
    ),
    ("SQLAlchemyTokenLedgerRepository", "save"): _UPSERT,
    ("SQLAlchemyUserRepository", "find_by_id"): (
        "user_id 來自已驗簽 JWT（auth）或稽核紀錄 actor；admin_router.get_user "
        "僅 system_admin"
    ),
    ("SQLAlchemyUserRepository", "find_by_email"): (
        "登入 / 註冊：email 全平台唯一，是認證本身（login_use_case）"
    ),
    ("SQLAlchemyUserRepository", "save"): _UPSERT,
    ("SQLAlchemyApiKeyRepository", "find_by_id"): (
        "RevokeApiKeyUseCase 比對 key.tenant_id（tenant_id=None 僅 system_admin）；"
        "client_credentials 交換以 client_secret 驗證，key 決定租戶（認證本身）"
    ),
    ("SQLAlchemyApiKeyRepository", "list_all"): (
        "ListApiKeysUseCase 只在 tenant_id=None 時呼叫，api_key_router 僅 "
        "system_admin 傳 None"
    ),
    ("SQLAlchemyApiKeyRepository", "touch_last_used"): (
        "client_credentials 交換成功後以已驗 secret 的 key.id 更新"
    ),
    ("SQLAlchemyApiKeyRepository", "save"): _UPSERT,
    ("SQLAlchemyAuditLogRepository", "find_by_entity"): (
        "ListBotAuditLogsUseCase 先 find_by_id + ensure_bot_tenant，entity_id 為"
        "該 bot 或 tenant:{bot.tenant_id}"
    ),
    ("SQLAlchemyAuditLogRepository", "find_by_entity_or_parent"): (
        "ListBotAuditLogsUseCase 先 find_by_id + ensure_bot_tenant 才以 bot.id 查"
    ),
    ("SQLAlchemyPromptGateRunRepository", "mark_orphans_error"): (
        _BACKGROUND + "：啟動時把孤兒 gate run 標 error（全平台）"
    ),
    ("SQLAlchemyPromptGateRunRepository", "save"): _UPSERT,
    ("SQLAlchemyConfigSnapshotRepository", "timeline_for_bot"): (
        "config_snapshot_router.get_bot_config_timeline 先 GetBotUseCase.execute"
        "(bot_id, tenant_id, role)（ensure_bot_tenant）才查 trace"
    ),
}


# ---------------------------------------------------------------- 掃描器


def _load_models() -> tuple[set[str], set[str], dict[str, str]]:
    """(有 tenant_id 的 model 名, 全部 model 名, 表名 → model 名)。"""
    for mod in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module(f"{models_pkg.__name__}.{mod.name}")
    tenant_models: set[str] = set()
    all_models: set[str] = set()
    tables: dict[str, str] = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        all_models.add(cls.__name__)
        if "tenant_id" in cls.__table__.c:
            tenant_models.add(cls.__name__)
            tables[cls.__table__.name] = cls.__name__
    return tenant_models, all_models, tables


TENANT_MODELS, ALL_MODELS, TENANT_TABLES = _load_models()


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _model_aliases(fn: ast.AsyncFunctionDef) -> dict[str, str]:
    """`t = AgentExecutionTraceModel` 這類區域別名 → model 名。"""
    aliases = {m: m for m in ALL_MODELS}
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Name)
            and node.value.id in ALL_MODELS
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    aliases[target.id] = node.value.id
    return aliases


def _touched_tenant_models(fn: ast.AsyncFunctionDef) -> set[str]:
    touched: set[str] = set()
    aliases = _model_aliases(fn)
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and _call_name(node) in STATEMENT_BUILDERS:
            for arg in node.args:
                for sub in ast.walk(arg):
                    if (
                        isinstance(sub, ast.Name)
                        and aliases.get(sub.id) in TENANT_MODELS
                    ):
                        touched.add(aliases[sub.id])
        # text() 原生 SQL：以表名判斷
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for table, model in TENANT_TABLES.items():
                if re.search(rf"\b{re.escape(table)}\b", node.value):
                    touched.add(model)
    return touched


def _references_tenant(fn: ast.AsyncFunctionDef) -> bool:
    aliases = _model_aliases(fn)
    for node in ast.walk(fn):
        # Model.tenant_id（WHERE 或 join 到有租戶的父表；含區域別名）
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "tenant_id"
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
        ):
            return True
        # text() 原生 SQL 內的 tenant_id 條件
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "tenant_id" in node.value
            and "WHERE" in node.value.upper()
        ):
            return True
        # 以 tenant_id 為主鍵：session.get(Model, tenant_id / x.tenant_id)
        if isinstance(node, ast.Call) and _call_name(node) == "get":
            for arg in node.args[1:]:
                if (isinstance(arg, ast.Name) and arg.id == "tenant_id") or (
                    isinstance(arg, ast.Attribute) and arg.attr == "tenant_id"
                ):
                    return True
        # scope helper：self._bot_scope(bot_id, tenant_id, …)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
        ):
            values = [*node.args, *(k.value for k in node.keywords)]
            if any(isinstance(v, ast.Name) and v.id == "tenant_id" for v in values):
                return True
    return False


def scan_source(source: str) -> tuple[dict[tuple[str, str], set[str]], set]:
    """回傳 ({(class, method): 碰到的有租戶 model}（缺 tenant 條件者）, 全部方法)。"""
    tree = ast.parse(source)
    unscoped: dict[tuple[str, str], set[str]] = {}
    methods: set[tuple[str, str]] = set()
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        for fn in cls.body:
            if not isinstance(fn, ast.AsyncFunctionDef) or fn.name.startswith("_"):
                continue
            methods.add((cls.name, fn.name))
            touched = _touched_tenant_models(fn)
            if touched and not _references_tenant(fn):
                unscoped[(cls.name, fn.name)] = touched
    return unscoped, methods


def _scan_all() -> tuple[dict[tuple[str, str], set[str]], set]:
    unscoped: dict[tuple[str, str], set[str]] = {}
    methods: set[tuple[str, str]] = set()
    for path in sorted(REPO_DIR.glob("*.py")):
        u, m = scan_source(path.read_text(encoding="utf-8"))
        unscoped |= u
        methods |= m
    return unscoped, methods


UNSCOPED, METHODS = _scan_all()


# ---------------------------------------------------------------- 測試


def test_scanner_sees_the_repository_layer():
    """防止掃描器因路徑或解析錯誤而空轉（空轉 = 永遠綠）。"""
    classes = {c for c, _ in METHODS}
    assert len(classes) >= 40, classes
    assert {"BotModel", "DocumentModel", "ConversationModel"} <= TENANT_MODELS
    assert "PlanModel" not in TENANT_MODELS  # 全域表不算


def test_every_unscoped_query_is_allowlisted():
    missing = sorted(set(UNSCOPED) - set(ALLOWLIST))
    assert missing == [], (
        "repository 方法查有租戶的表卻沒有 tenant_id 條件。先追呼叫端確認有歸屬"
        "檢查（沒有就是跨租戶漏洞：補條件或補檢查），再以理由登記 ALLOWLIST："
        + "".join(f"\n  {c}.{m} → {sorted(UNSCOPED[(c, m)])}" for c, m in missing)
    )


def test_allowlist_is_not_stale():
    gone = sorted(k for k in ALLOWLIST if k not in METHODS)
    scoped_now = sorted(k for k in ALLOWLIST if k in METHODS and k not in UNSCOPED)
    assert gone == [], f"ALLOWLIST 的方法已不存在：{gone}"
    assert scoped_now == [], f"ALLOWLIST 的方法已自帶 tenant 條件，請移除：{scoped_now}"


@pytest.mark.parametrize("key", sorted(ALLOWLIST))
def test_allowlist_reason_names_the_check(key):
    reason = ALLOWLIST[key]
    assert len(reason) >= 15, f"{key} 的理由太短，要寫明租戶檢查在哪裡做"


# ---- 掃描器自我檢查（合成原始碼，確保規則本身不會漏判）

_SAMPLE = '''
class SQLAlchemyFooRepository:
    async def by_id(self, x):
        return await self._s.execute(select(BotModel).where(BotModel.id == x))

    async def by_tenant(self, x, tenant_id):
        return await self._s.execute(
            select(BotModel).where(BotModel.id == x, BotModel.tenant_id == tenant_id)
        )

    async def via_parent(self, x, tenant_id):
        return await self._s.execute(
            select(DocumentModel).join(KnowledgeBaseModel)
            .where(KnowledgeBaseModel.tenant_id == tenant_id)
        )

    async def via_helper(self, x, tenant_id):
        return await self._s.execute(
            select(BotModel).where(*self._scope(x, tenant_id))
        )

    async def via_alias(self, x):
        t = BotModel
        return await self._s.execute(select(t.id).where(t.id == x))

    async def via_alias_scoped(self, x, tenant_id):
        t = BotModel
        return await self._s.execute(select(t.id).where(t.tenant_id == tenant_id))

    async def by_get(self, x):
        return await self._s.get(ConversationModel, x)

    async def assigns_tenant_only(self, x):
        m = (await self._s.execute(select(BotModel).where(BotModel.id == x))).first()
        m.tenant_id = "t"

    async def raw_sql(self):
        return await self._s.execute(text("SELECT * FROM bots"))

    async def raw_sql_scoped(self, tenant_id):
        return await self._s.execute(
            text("SELECT * FROM bots WHERE tenant_id = :tenant_id")
        )

    async def keyed_by_tenant(self, tenant_id):
        return await self._s.get(ConversationModel, tenant_id)

    async def global_table(self):
        return await self._s.execute(select(PlanModel))

    async def _private(self, x):
        return await self._s.execute(select(BotModel).where(BotModel.id == x))
'''


def test_scanner_rules_on_synthetic_source():
    unscoped, methods = scan_source(_SAMPLE)
    flagged = {m for _, m in unscoped}
    assert flagged == {
        "by_id",
        "via_alias",
        "by_get",
        "assigns_tenant_only",
        "raw_sql",
    }
    assert ("SQLAlchemyFooRepository", "_private") not in methods
    assert unscoped[("SQLAlchemyFooRepository", "by_get")] == {"ConversationModel"}
