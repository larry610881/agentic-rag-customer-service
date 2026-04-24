"""Unit test — previous_year_month utility (S-Ledger-Unification Tier 1 T1.2)"""

from __future__ import annotations

import pytest

from src.domain.ledger.entity import previous_year_month


def test_previous_year_month_within_same_year():
    assert previous_year_month("2026-05") == "2026-04"
    assert previous_year_month("2026-12") == "2026-11"
    assert previous_year_month("2026-02") == "2026-01"


def test_previous_year_month_cross_year_boundary():
    assert previous_year_month("2026-01") == "2025-12"
    assert previous_year_month("2025-01") == "2024-12"


@pytest.mark.parametrize("bad_input", ["2026", "2026-13", "2026-00", "abc", ""])
def test_previous_year_month_rejects_invalid(bad_input):
    with pytest.raises((ValueError, IndexError)):
        previous_year_month(bad_input)
