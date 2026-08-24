"""Regression: eval dataset 歸屬 guard 讀/寫矩陣（C4–C7）。"""

import pytest

from src.application.eval_dataset._tenant_guard import (
    ensure_dataset_read,
    ensure_dataset_write,
)
from src.domain.eval_dataset.entity import EvalDataset
from src.domain.shared.exceptions import AuthorizationError, EntityNotFoundError


def _ds(tenant_id="owner", is_platform_base=False):
    return EvalDataset(
        name="d", tenant_id=tenant_id, is_platform_base=is_platform_base
    )


# --- 讀 ---

def test_read_owner_ok():
    ensure_dataset_read(_ds("owner"), "owner", None)  # no raise


def test_read_foreign_raises():
    with pytest.raises(EntityNotFoundError):
        ensure_dataset_read(_ds("owner"), "attacker", None)


def test_read_platform_base_allowed_for_any_tenant():
    ensure_dataset_read(_ds("owner", is_platform_base=True), "attacker", None)


def test_read_system_admin_bypass():
    ensure_dataset_read(_ds("owner"), "attacker", "system_admin")


# --- 寫 ---

def test_write_owner_ok():
    ensure_dataset_write(_ds("owner"), "owner", None)


def test_write_foreign_regular_raises_not_found():
    with pytest.raises(EntityNotFoundError):
        ensure_dataset_write(_ds("owner"), "attacker", None)


def test_write_platform_base_non_admin_forbidden():
    with pytest.raises(AuthorizationError):
        ensure_dataset_write(
            _ds("owner", is_platform_base=True), "attacker", None
        )


def test_write_platform_base_system_admin_ok():
    ensure_dataset_write(
        _ds("owner", is_platform_base=True), "attacker", "system_admin"
    )
