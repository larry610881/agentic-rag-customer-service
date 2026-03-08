"""Tool Registry — 集中管理工具後設資料與實例

統一管理 Router 模式的工具描述和 ReAct 模式的工具實例，
避免工具資訊散落在各個 service 中。
"""

from typing import Any


class ToolRegistry:
    """工具註冊中心"""

    def __init__(self) -> None:
        self._descriptions: dict[str, str] = {}
        self._tools: dict[str, Any] = {}  # LangChain BaseTool instances

    def register(
        self,
        name: str,
        description: str,
        lc_tool: Any | None = None,
    ) -> None:
        """註冊工具的後設資料和可選的 LangChain BaseTool 實例。

        Args:
            name: 工具名稱（唯一鍵）
            description: 工具描述（Router prompt 使用）
            lc_tool: LangChain BaseTool 實例（ReAct 模式使用）
        """
        self._descriptions[name] = description
        if lc_tool is not None:
            self._tools[name] = lc_tool

    def get_descriptions(
        self, names: list[str] | None = None
    ) -> dict[str, str]:
        """取得工具描述（供 Router prompt 使用）。

        Args:
            names: 篩選特定工具名稱，None 時回傳全部

        Returns:
            {name: description} 字典
        """
        if names is None:
            return dict(self._descriptions)
        return {
            n: self._descriptions[n]
            for n in names
            if n in self._descriptions
        }

    def get_tools(
        self, names: list[str] | None = None,
    ) -> list[Any]:
        """取得 LangChain BaseTool 實例（供 ReAct 使用）。

        Args:
            names: 篩選特定工具名稱，None 時回傳全部

        Returns:
            BaseTool 實例列表
        """
        if names is None:
            return list(self._tools.values())
        return [
            self._tools[n]
            for n in names
            if n in self._tools
        ]

    def list_names(self) -> list[str]:
        """列出所有已註冊的工具名稱"""
        return list(self._descriptions.keys())

    def has(self, name: str) -> bool:
        """檢查工具是否已註冊"""
        return name in self._descriptions
