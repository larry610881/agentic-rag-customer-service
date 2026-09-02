"""執行時有效設定與指紋（Issue #60）

鑑識要回答「這一輪實際跑的是什麼設定」。不是版本化每張設定表，而是在 prompt
組裝完成的瞬間，把**解析後**的有效值（覆蓋後 system prompt、命中的 worker、guard
規則集、模型與參數、檢索參數、KB）做標準化 JSON 並取 sha256。內容定址：設定
沒變就是同一個 hash，不重複寫入。密鑰欄位在序列化時一律剝除。
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

SNAPSHOT_SCHEMA = 1

# 任何鍵名含這些片段的欄位都不進 snapshot（大小寫不敏感）
_SECRET_KEY_FRAGMENTS = (
    "api_key", "apikey", "secret", "token", "password", "env_values",
    "authorization", "credential",
)


def _is_secret_key(key: str) -> bool:
    k = key.lower()
    return any(frag in k for frag in _SECRET_KEY_FRAGMENTS)


def _scrub(value: Any) -> Any:
    """遞迴剝除密鑰鍵、把 dataclass / set 轉成可 JSON 的型別。"""
    if is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, dict):
        return {
            str(k): _scrub(v)
            for k, v in value.items()
            if not _is_secret_key(str(k))
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    if isinstance(value, set):
        return sorted(_scrub(v) for v in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True)
class EffectiveConfig:
    channel: str
    bot_id: str
    system_prompt: str
    platform_prompt_fallback: bool = False
    worker_name: str = ""
    llm_provider: str = ""
    llm_model: str = ""
    router_model: str = ""
    llm_params: dict[str, Any] = field(default_factory=dict)
    retrieval: dict[str, Any] = field(default_factory=dict)
    enabled_tools: list[str] | None = None
    max_tool_calls: int = 0
    guard: dict[str, Any] | None = None
    memory_enabled: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_snapshot(self) -> dict[str, Any]:
        """可持久化、可顯示的 snapshot（已剝除密鑰）。"""
        raw = {
            "schema": SNAPSHOT_SCHEMA,
            "channel": self.channel,
            "bot_id": self.bot_id,
            "system_prompt": self.system_prompt,
            "platform_prompt_fallback": self.platform_prompt_fallback,
            "worker_name": self.worker_name,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "router_model": self.router_model,
            "llm_params": self.llm_params,
            "retrieval": self.retrieval,
            "enabled_tools": self.enabled_tools,
            "max_tool_calls": self.max_tool_calls,
            "guard": self.guard,
            "memory_enabled": self.memory_enabled,
            "extra": self.extra,
        }
        scrubbed = _scrub(raw)
        assert isinstance(scrubbed, dict)  # noqa: S101 — _scrub 對 dict 輸入恆回 dict
        return scrubbed

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_snapshot(), sort_keys=True, ensure_ascii=False,
            separators=(",", ":"),
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


def diff_effective_snapshots(a: dict[str, Any], b: dict[str, Any]) -> dict[str, dict]:
    """兩份 snapshot 的欄位差異：{field: {"before": ..., "after": ...}}。
    巢狀 dict 以 dotted path 展開一層（llm_params.temperature），list 整體比較。"""
    out: dict[str, dict] = {}

    def _walk(prefix: str, x: Any, y: Any) -> None:
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y)):
                _walk(f"{prefix}.{k}" if prefix else k, x.get(k), y.get(k))
            return
        if x != y:
            out[prefix] = {"before": x, "after": y}

    _walk("", a, b)
    return out


class ConfigSnapshotRepository(ABC):
    @abstractmethod
    async def ensure(self, config_hash: str, snapshot: dict, schema: int) -> None:
        """冪等寫入（ON CONFLICT DO NOTHING）。"""

    @abstractmethod
    async def find_by_hash(self, config_hash: str) -> dict | None:
        """回 {"hash", "snapshot", "schema", "first_seen_at"} 或 None。"""

    @abstractmethod
    async def timeline_for_bot(self, bot_id: str, limit: int = 50) -> list[dict]:
        """該 bot 出現過的 hash 與首次 / 最後生效時間、輪次數（由 trace 反查）。"""
