"""LLM-based Wiki compiler — 從文件內容擷取概念 + 關係。

設計借鑑 Graphify（MIT, https://github.com/safishamsi/graphify）的 Pass 2
prompt，改寫為繁體中文客服知識庫場景。主要差異：
- Graphify 跑在 Claude Code subagent，我們改走自家 LLMService port
- Graphify 支援 code + image + paper，我們只處理純文字客服文件
- Graphify 用 tree-sitter 先做 AST pass，我們跳過（客服場景無程式碼）
- 不支援 hyperedges（MVP 不需要）
"""

from __future__ import annotations

import json
import re
import uuid

from src.domain.rag.services import LLMService
from src.domain.wiki.services import (
    ExtractedEdge,
    ExtractedGraph,
    ExtractedNode,
    WikiCompilerService,
)
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


_SYSTEM_PROMPT = """你是客服知識庫 Wiki 編譯器。\
你的任務是從一份文件中擷取結構化的知識圖譜片段。

**只輸出有效 JSON**，不要任何解釋、markdown 圍欄、前言。

### 擷取規則

1. **節點（nodes）** — 文件中提到的關鍵概念、實體、流程、政策：
   - `id`: snake_case 英文短詞（從 label 產生，全文唯一）
   - `label`: 繁體中文的人類可讀標籤
   - `type`: concept（概念）| entity（具名實體）| process（流程）| policy（政策）
   - `summary`: 一句話摘要（≤40 字），必要時留空字串

2. **邊（edges）** — 節點之間的語意關係：
   - `relation`: 動詞或介系詞描述的關係
     （如 "requires"、"references"、"triggers"、"applies_to"、"part_of"、"similar_to"）
   - `confidence`: 三擇一
     * `EXTRACTED` — 文件明確寫出
       （如「若要退貨，需先聯絡客服」→ 退貨 requires 聯絡客服）
     * `INFERRED` — 合理推論（上下文隱含的依賴關係）
       附 `confidence_score` 0.6-0.9
     * `AMBIGUOUS` — 不確定但值得標記，附 `confidence_score` 0.1-0.3
   - `confidence_score`: EXTRACTED 一律 1.0，其他依推論強度給 0.1-0.9

### 關鍵原則

- 優先擷取「業務規則」、「流程步驟」、「政策限制」—— 客服回答最需要的
- 避免擷取過於瑣碎的名詞（如「按鈕」、「畫面」）
- 若兩個概念解決相同問題但文件沒明說，用 `similar_to` + INFERRED 標記
- 最多 30 個節點、50 條邊 / 次（避免爆 token），超過請挑重要的

### 輸出格式（嚴格遵守）

```json
{
  "nodes": [
    {
      "id": "return_policy",
      "label": "退貨政策",
      "type": "policy",
      "summary": "30 天內可無理由退貨"
    }
  ],
  "edges": [
    {
      "source": "return_request",
      "target": "contact_support",
      "relation": "requires",
      "confidence": "EXTRACTED",
      "confidence_score": 1.0
    }
  ]
}
```

絕對不要輸出任何 JSON 之外的文字。"""


_USER_PROMPT_TEMPLATE = """請從以下客服文件擷取知識圖譜片段：

文件 ID: {document_id}

===== 文件內容開始 =====
{content}
===== 文件內容結束 =====

直接輸出 JSON。"""


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_RAW_JSON_RE = re.compile(r"(\{[^{}]*?(?:\{[^{}]*?\}[^{}]*?)*\})", re.DOTALL)


class LLMWikiCompilerService(WikiCompilerService):
    """用既有 LLMService port 實作 Wiki 編譯。

    透過依賴 `LLMService` 抽象，任何 provider（OpenAI / Anthropic / DeepSeek）都能用。
    Token usage 會跟著 LLMResult 回傳，由上層 use case 累計。
    """

    def __init__(
        self,
        llm_service: LLMService,
        *,
        max_content_chars: int = 12000,
    ) -> None:
        self._llm = llm_service
        # 文件太長會爆 context，截斷保護（約 4000 tokens 中文）
        self._max_chars = max_content_chars

    async def extract(
        self,
        *,
        document_id: str,
        content: str,
        language: str = "zh-TW",
    ) -> ExtractedGraph:
        if not content or not content.strip():
            logger.info(
                "wiki.compiler.skip_empty",
                document_id=document_id,
            )
            return ExtractedGraph()

        truncated = content[: self._max_chars]
        if len(content) > self._max_chars:
            logger.info(
                "wiki.compiler.content_truncated",
                document_id=document_id,
                original_length=len(content),
                truncated_length=self._max_chars,
            )

        user_message = _USER_PROMPT_TEMPLATE.format(
            document_id=document_id,
            content=truncated,
        )

        try:
            result = await self._llm.generate(
                system_prompt=_SYSTEM_PROMPT,
                user_message=user_message,
                context="",
                temperature=0.0,  # deterministic structured output
                max_tokens=4000,
            )
        except Exception as exc:
            logger.exception(
                "wiki.compiler.llm_error",
                document_id=document_id,
                error=str(exc),
            )
            return ExtractedGraph()

        parsed = self._parse_json_payload(result.text)
        if parsed is None:
            logger.warning(
                "wiki.compiler.parse_failed",
                document_id=document_id,
                raw_preview=result.text[:200],
            )
            return ExtractedGraph(usage=result.usage)

        nodes = self._build_nodes(parsed.get("nodes", []), document_id)
        edges = self._build_edges(parsed.get("edges", []))

        logger.info(
            "wiki.compiler.extracted",
            document_id=document_id,
            node_count=len(nodes),
            edge_count=len(edges),
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        )
        return ExtractedGraph(
            nodes=tuple(nodes),
            edges=tuple(edges),
            usage=result.usage,
        )

    @staticmethod
    def _parse_json_payload(text: str) -> dict | None:
        """Best-effort JSON parsing — handles fenced, bare, or polluted output."""
        if not text:
            return None
        stripped = text.strip()
        # Direct parse
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass
        # Try fenced code block
        m = _JSON_FENCE_RE.search(stripped)
        if m:
            try:
                return json.loads(m.group(1))
            except (json.JSONDecodeError, ValueError):
                pass
        # Last resort: find the outermost balanced braces
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = stripped[start : end + 1]
            try:
                return json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                return None
        return None

    @staticmethod
    def _build_nodes(
        raw_nodes: list, document_id: str
    ) -> list[ExtractedNode]:
        nodes: list[ExtractedNode] = []
        seen_ids: set[str] = set()
        for item in raw_nodes:
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("id", "")).strip()
            label = str(item.get("label", "")).strip()
            if not label:
                continue
            node_id = raw_id or _slugify(label)
            if not node_id or node_id in seen_ids:
                # Avoid duplicates; fall back to unique suffix
                node_id = f"{node_id or 'node'}_{uuid.uuid4().hex[:6]}"
            seen_ids.add(node_id)
            nodes.append(
                ExtractedNode(
                    id=node_id,
                    label=label,
                    type=str(item.get("type", "concept")) or "concept",
                    summary=str(item.get("summary", "") or ""),
                    source_doc_id=document_id,
                )
            )
        return nodes

    @staticmethod
    def _build_edges(raw_edges: list) -> list[ExtractedEdge]:
        edges: list[ExtractedEdge] = []
        for item in raw_edges:
            if not isinstance(item, dict):
                continue
            src = str(item.get("source", "")).strip()
            tgt = str(item.get("target", "")).strip()
            relation = str(item.get("relation", "")).strip()
            if not (src and tgt and relation):
                continue
            confidence = str(item.get("confidence", "EXTRACTED")).upper()
            if confidence not in ("EXTRACTED", "INFERRED", "AMBIGUOUS"):
                confidence = "INFERRED"
            try:
                score = float(item.get("confidence_score", 1.0))
            except (TypeError, ValueError):
                score = 1.0
            # Clamp
            score = max(0.0, min(1.0, score))
            if confidence == "EXTRACTED":
                score = 1.0
            edges.append(
                ExtractedEdge(
                    source=src,
                    target=tgt,
                    relation=relation,
                    confidence=confidence,
                    confidence_score=score,
                )
            )
        return edges


def _slugify(label: str) -> str:
    """Generate a safe snake_case ID from any label (including CJK)."""
    # Replace non-alphanumeric with underscore
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", label.lower())
    slug = slug.strip("_")
    if not slug:
        return ""
    # Cap length for readability
    return slug[:60]
