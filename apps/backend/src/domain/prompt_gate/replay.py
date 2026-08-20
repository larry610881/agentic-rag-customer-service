"""真實流量回放 pairwise 對比 — 純判定邏輯（spec §14 層次 2）

Pairwise judge 換位雙判：正序（1=baseline, 2=candidate）與換位
（1=candidate, 2=baseline）兩次判定意見一致才計勝負，否則平手——
這是 LLM judge position bias 的標準防護。
"""

from __future__ import annotations

from dataclasses import dataclass, field

RESULT_CANDIDATE = "candidate"
RESULT_BASELINE = "baseline"
RESULT_TIE = "tie"

_TIE_TOKENS = frozenset({"平手", "tie", "0"})


def _normalize(raw: str) -> str:
    text = (raw or "").strip().lower()
    if text.startswith("1"):
        return "1"
    if text.startswith("2"):
        return "2"
    if any(t in text for t in _TIE_TOKENS):
        return "tie"
    return "tie"  # 無法解析視為平手（fail-open）


def consistent_verdict(normal: str, swapped: str) -> str:
    """normal：正序判定（1=baseline 佳, 2=candidate 佳）；
    swapped：換位判定（1=candidate 佳, 2=baseline 佳）。"""
    n, s = _normalize(normal), _normalize(swapped)
    if n == "2" and s == "1":
        return RESULT_CANDIDATE
    if n == "1" and s == "2":
        return RESULT_BASELINE
    return RESULT_TIE


@dataclass(frozen=True)
class ReplaySummary:
    total: int
    candidate_wins: int
    baseline_wins: int
    ties: int

    @property
    def win_rate(self) -> float:
        """candidate 勝率（分母含平手；無題 = 0）。"""
        return self.candidate_wins / self.total if self.total else 0.0


def aggregate_replay(results: list[str]) -> ReplaySummary:
    return ReplaySummary(
        total=len(results),
        candidate_wins=sum(1 for r in results if r == RESULT_CANDIDATE),
        baseline_wins=sum(1 for r in results if r == RESULT_BASELINE),
        ties=sum(1 for r in results if r == RESULT_TIE),
    )


@dataclass(frozen=True)
class ReplayQuestionResult:
    question: str
    baseline_answer: str
    candidate_answer: str
    verdict: str  # candidate | baseline | tie
    judge_normal: str = ""
    judge_swapped: str = ""
    baseline_cost: float = 0.0
    candidate_cost: float = 0.0
    extra: dict = field(default_factory=dict)
