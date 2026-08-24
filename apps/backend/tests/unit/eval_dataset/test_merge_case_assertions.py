"""Regression: 優化路徑把 dataset default_assertions 併入每個 case（H16）。"""

from src.application.eval_dataset.run_use_cases import merge_case_assertions


def test_defaults_prepended_to_case_assertions():
    defaults = [{"type": "no_system_prompt_leak", "params": {}}]
    case = [{"type": "contains", "params": {"keywords": ["退貨"]}}]
    merged = merge_case_assertions(defaults, case)
    assert merged == defaults + case
    # 安全預設必須出現在合併結果（否則優化評分忽略它）
    assert {"type": "no_system_prompt_leak", "params": {}} in merged


def test_empty_defaults_returns_case_only():
    case = [{"type": "contains", "params": {}}]
    assert merge_case_assertions([], case) == case


def test_none_safe():
    assert merge_case_assertions(None, None) == []
