"""覆蓋率下限檢查腳本（Issue #101）：判讀規則本身要有測試，否則閘門可能靜默放行。"""

from pathlib import Path

from scripts.check_coverage_floors import evaluate, load_line_counts, main

_XML = """<?xml version="1.0" ?>
<coverage><packages><package name="p"><classes>
  <class filename="interfaces/api/deps.py"><lines>
    <line number="1" hits="1"/><line number="2" hits="1"/>
    <line number="3" hits="1"/><line number="4" hits="0"/>
  </lines></class>
  <class filename="application/auth/login.py"><lines>
    <line number="1" hits="1"/><line number="2" hits="1"/>
  </lines></class>
</classes></package></packages></coverage>
"""


def _xml(tmp_path: Path) -> str:
    p = tmp_path / "coverage.xml"
    p.write_text(_XML)
    return str(p)


def test_依_pattern_加總行覆蓋率並比對下限(tmp_path):
    counts = load_line_counts(_xml(tmp_path))
    [deps, auth] = evaluate(
        counts,
        [
            (("interfaces/api/deps.py",), 80, "x"),
            (("application/auth/*",), 100, "y"),
        ],
    )
    assert (deps.lines, deps.covered, deps.ok) == (4, 3, False)  # 75% < 80
    assert (auth.rate, auth.ok) == (100.0, True)


def test_pattern_對不到任何檔案視為失敗_表過期要紅(tmp_path):
    [r] = evaluate(load_line_counts(_xml(tmp_path)), [(("gone/*",), 0, "z")])
    assert r.files == 0
    assert not r.ok


def test_main_任何下限不足回傳_1(tmp_path, capsys):
    assert main(["prog", _xml(tmp_path)]) == 1
    assert "FAIL" in capsys.readouterr().out
