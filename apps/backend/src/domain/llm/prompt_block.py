"""PromptBlock — provider-agnostic 結構化 prompt 單元 (S-LLM-Cache.1)。

設計目標
--------
讓 service 層用同一份結構化 prompt 跨所有 LLM provider 工作，cache 行為由
infrastructure adapter 自行翻譯：

- **Anthropic**：cacheable block 加 `cache_control: {type: "ephemeral"}` marker
- **OpenAI / DeepSeek / Qwen / Google / OpenRouter / LiteLLM**：自動 prefix
  caching，adapter 按 role 拼字串送出，cacheable hint 影響的是 caller 把
  cacheable block 放前面以維持 byte-stable prefix
- **Ollama / vLLM 自架推理**：runtime KV cache 自己處理，hint 完全 no-op

Caller 寫的 code 與 provider 無關，例：

```python
blocks = [
    PromptBlock(text=f"<document>\\n{doc}\\n</document>",
                role=BlockRole.USER, cache=CacheHint.EPHEMERAL),
    PromptBlock(text=f"<chunk>{chunk}</chunk>\\n請描述...", role=BlockRole.USER),
]
result = await call_llm(model_spec=..., prompt=blocks, ...)
```

Ordering contract
-----------------
Caller 自己負責把可 cache 的 block 放前面：
- Anthropic：靠 marker 不靠順序，但保持「先固定後變動」順序方便閱讀
- OpenAI auto-prefix：必須 byte-stable prefix，cacheable block **必須在前**

無 type 欄位（純 text）— 圖像 / tool result block 留 v2 (BlockType enum) 處理。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BlockRole(str, Enum):
    """Block 在 chat 訊息中的角色 — 對應 LLM API 的 system / user 區分。"""

    SYSTEM = "system"
    USER = "user"


class CacheHint(str, Enum):
    """Cache 提示 — 各 provider 自行決定如何利用。

    - **EPHEMERAL**：Anthropic 標 `cache_control: ephemeral` (5 分鐘 TTL)；
      其他 provider 視為「caller 已維持此 block byte-stable，請利用 prefix cache」
    - **NONE**：明確不 cache（變動內容如 user query / per-chunk content）
    """

    EPHEMERAL = "ephemeral"
    NONE = "none"


@dataclass(frozen=True)
class PromptBlock:
    """單一 prompt 段落 — 文字 + 角色 + cache 提示。

    `frozen=True` 確保 caller 不會在 adapter 翻譯前後不小心改寫 block；
    跨 async task 傳遞也安全。
    """

    text: str
    role: BlockRole = BlockRole.USER
    cache: CacheHint = CacheHint.NONE
