"""Built-in tool domain entity + repository interface.

對稱於 domain/platform/entity.py 的 McpServerRegistration 機制，
但主鍵為 tool name（hardcoded 於 BUILT_IN_TOOLS_DEFAULTS，可由系統管理員
切換 scope 與白名單）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable


@dataclass
class BuiltInTool:
    """系統內建工具，scope + tenant_ids 控制跨租戶可見性"""

    name: str
    label: str
    description: str
    requires_kb: bool = False
    scope: str = "global"  # "global" | "tenant"
    tenant_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def is_accessible_by(self, tenant_id: str) -> bool:
        """是否對指定租戶開放（global 全開；tenant 僅白名單）"""
        if self.scope == "global":
            return True
        if self.scope == "tenant":
            return tenant_id in self.tenant_ids
        return False


BUILT_IN_TOOL_DEFAULTS: list[BuiltInTool] = [
    BuiltInTool(
        name="rag_query",
        label="知識庫查詢",
        description="對 bot 連結的知識庫做向量檢索，適合一般文字問答。",
        requires_kb=True,
    ),
    BuiltInTool(
        name="query_dm_with_image",
        label="DM 圖卡查詢",
        description=(
            "對 catalog PDF 知識庫（如家樂福 DM）檢索，命中頁面圖卡由各通路自動"
            "顯示（LINE Flex / Web Gallery / Widget），適合促銷 / 商品查詢場景。"
        ),
        requires_kb=True,
    ),
    BuiltInTool(
        name="transfer_to_human_agent",
        label="轉接真人客服",
        description=(
            "當使用者要求轉人工、情緒激動或議題複雜（如退款爭議、帳務核對）時，"
            "讓 LLM 呼叫此工具顯示客服聯絡按鈕。需要 Bot「能力」頁設定客服 URL。"
        ),
        requires_kb=False,
    ),
]


class BuiltInToolRepository(ABC):
    @abstractmethod
    async def find_all(self) -> list[BuiltInTool]:
        """系統管理員用：所有 built-in tools，含 scope 與白名單"""
        ...

    @abstractmethod
    async def find_accessible(self, tenant_id: str) -> list[BuiltInTool]:
        """租戶用：global + 白名單包含該 tenant_id 的工具"""
        ...

    @abstractmethod
    async def find_by_name(self, name: str) -> BuiltInTool | None: ...

    @abstractmethod
    async def upsert(self, tool: BuiltInTool) -> None:
        """更新 scope 與 tenant_ids（不動 label/description/requires_kb）"""
        ...

    @abstractmethod
    async def seed_defaults(self, defaults: Iterable[BuiltInTool]) -> None:
        """啟動時冪等 seed：
        - 新 tool：INSERT 全欄位
        - 既有 tool：UPDATE label/description/requires_kb，保留 scope/tenant_ids
        """
        ...
