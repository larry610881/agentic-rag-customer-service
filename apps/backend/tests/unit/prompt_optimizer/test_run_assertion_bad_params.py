"""Regression: run_assertion 對非法 params 回 fail 而非崩潰整個 run（M33）。"""

from prompt_optimizer.assertions import AssertionContext, run_assertion


def _ctx():
    return AssertionContext(response_text="hello", user_message="q")


def test_bad_params_returns_failed_not_raises():
    # max_length 是 kw-only(max_chars)，typo maxChars → 原本 TypeError 拖垮整批
    res = run_assertion("max_length", _ctx(), {"maxChars": 100})
    assert res.passed is False
    assert "Invalid assertion params" in res.message


def test_missing_required_param_returns_failed():
    res = run_assertion("max_length", _ctx(), {})  # 缺 max_chars
    assert res.passed is False


def test_unknown_type_returns_failed():
    res = run_assertion("no_such_assertion", _ctx(), {})
    assert res.passed is False
    assert "Unknown assertion" in res.message


def test_valid_params_still_work():
    res = run_assertion("max_length", _ctx(), {"max_chars": 100})
    assert res.passed is True
