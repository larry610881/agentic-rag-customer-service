"""PromptBlock domain 抽象單元測試 — S-LLM-Cache.1 Step 1."""
from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from src.domain.llm import BlockRole, CacheHint, PromptBlock


def test_default_is_user_role_none_cache():
    block = PromptBlock(text="hello")
    assert block.role == BlockRole.USER
    assert block.cache == CacheHint.NONE


def test_explicit_system_role_and_ephemeral_cache():
    block = PromptBlock(
        text="You are a helpful assistant",
        role=BlockRole.SYSTEM,
        cache=CacheHint.EPHEMERAL,
    )
    assert block.role == BlockRole.SYSTEM
    assert block.cache == CacheHint.EPHEMERAL


def test_block_is_frozen_cannot_reassign():
    block = PromptBlock(text="immutable")
    with pytest.raises(FrozenInstanceError):
        block.text = "mutated"  # type: ignore[misc]


def test_block_role_enum_string_value():
    # Role value 用在 OpenAI messages[{role: "system" | "user"}]
    assert BlockRole.SYSTEM.value == "system"
    assert BlockRole.USER.value == "user"


def test_cache_hint_enum_string_value():
    # CacheHint value 直接對應 Anthropic cache_control type 格式
    assert CacheHint.EPHEMERAL.value == "ephemeral"
    assert CacheHint.NONE.value == "none"


def test_block_equality_by_value():
    a = PromptBlock(text="same", role=BlockRole.USER, cache=CacheHint.EPHEMERAL)
    b = PromptBlock(text="same", role=BlockRole.USER, cache=CacheHint.EPHEMERAL)
    assert a == b


def test_block_is_hashable_for_caching():
    # frozen dataclass → hashable，可作 dict key / set member
    block = PromptBlock(text="x")
    assert hash(block) is not None
    assert {block} == {PromptBlock(text="x")}
