"""KeywordSentimentService — 關鍵字匹配情緒偵測"""

import re

from src.domain.agent.services import SentimentService
from src.domain.agent.value_objects import SentimentResult

_NEGATIVE_KEYWORDS = re.compile(
    r"投訴|生氣|不滿|太慢|爛|差勁|失望|憤怒|垃圾|騙人|退款|ridiculous|angry|terrible"
)
_POSITIVE_KEYWORDS = re.compile(
    r"謝謝|感謝|很棒|太好了|滿意|excellent|great|thanks|wonderful"
)


class KeywordSentimentService(SentimentService):
    async def analyze(self, text: str) -> SentimentResult:
        if _NEGATIVE_KEYWORDS.search(text):
            return SentimentResult(
                sentiment="negative",
                score=0.8,
                should_escalate=True,
            )
        if _POSITIVE_KEYWORDS.search(text):
            return SentimentResult(
                sentiment="positive",
                score=0.8,
                should_escalate=False,
            )
        return SentimentResult(
            sentiment="neutral",
            score=0.5,
            should_escalate=False,
        )
