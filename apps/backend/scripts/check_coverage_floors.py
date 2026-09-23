"""安全關鍵模組的覆蓋率下限檢查（Issue #101，計畫檔 B8）。

全域覆蓋率是訊號，不是安全保證；認證、租戶隔離、防護、額度這些面要個別守下限，
不能被其他模組的高覆蓋率平均掉。讀 coverage.xml（pytest --cov-report=xml），
依下表以「行覆蓋率」檢查，任何一條不足或 pattern 對不到任何檔案（表過期）都回傳 1。

用法：uv run python scripts/check_coverage_floors.py <coverage.xml>
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fnmatch import fnmatch

# (路徑 pattern 們（相對 src/，fnmatch）, 下限 %, 理由)。改下限要附理由。
FLOORS: list[tuple[tuple[str, ...], float, str]] = [
    (
        (
            "interfaces/api/deps.py",
            "interfaces/api/client_version_middleware.py",
            "interfaces/api/rate_limit_middleware.py",
        ),
        90,
        "認證／版本／限流入口",
    ),
    (("infrastructure/auth/*",), 90, "JWT、密碼雜湊"),
    (("application/auth/*",), 90, "登入、refresh、api key"),
    (("application/security/*", "domain/security/*"), 85, "防護管線"),
    (
        (
            "application/knowledge/_admin_kb_check.py",
            "application/*/_tenant_guard.py",
        ),
        100,
        "租戶隔離 helper",
    ),
    (("infrastructure/db/repositories/*",), 75, "租戶過濾條件所在"),
    (("application/widget/identity_use_cases.py",), 85, "widget 匿名訪客身分＝認證"),
    (
        ("application/shared/idempotency_guard.py", "infrastructure/idempotency/*"),
        85,
        "重放防護",
    ),
    (("application/abuse/*", "infrastructure/abuse/*"), 85, "濫用分級"),
    (
        ("application/billing/quota_preflight.py", "domain/billing/exhaustion.py"),
        85,
        "額度閘門（付費邊界）",
    ),
    (
        ("infrastructure/db/session_middleware.py",),
        90,
        "session 清理（pool leak 紅線）",
    ),
    (
        (
            "application/line/handle_webhook_use_case.py",
            "infrastructure/line/*",
        ),
        85,
        "LINE 通路（webhook 簽章＝認證）",
    ),
]


@dataclass
class FloorResult:
    patterns: tuple[str, ...]
    floor: float
    reason: str
    files: int
    lines: int
    covered: int

    @property
    def rate(self) -> float:
        return 100.0 * self.covered / self.lines if self.lines else 0.0

    @property
    def ok(self) -> bool:
        return self.files > 0 and self.rate >= self.floor


def load_line_counts(xml_path: str) -> dict[str, tuple[int, int]]:
    """filename（相對 src/）→ (可執行行數, 已覆蓋行數)。"""
    root = ET.parse(xml_path).getroot()
    counts: dict[str, tuple[int, int]] = {}
    for cls in root.iter("class"):
        lines = cls.find("lines")
        if lines is None:
            continue
        total = len(lines)
        hit = sum(1 for ln in lines if int(ln.get("hits", "0")) > 0)
        name = cls.get("filename", "")
        prev = counts.get(name, (0, 0))
        counts[name] = (prev[0] + total, prev[1] + hit)
    return counts


def evaluate(
    counts: dict[str, tuple[int, int]],
    floors: list[tuple[tuple[str, ...], float, str]] = FLOORS,
) -> list[FloorResult]:
    results = []
    for patterns, floor, reason in floors:
        matched = [f for f in counts if any(fnmatch(f, p) for p in patterns)]
        lines = sum(counts[f][0] for f in matched)
        covered = sum(counts[f][1] for f in matched)
        results.append(
            FloorResult(patterns, floor, reason, len(matched), lines, covered)
        )
    return results


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    results = evaluate(load_line_counts(argv[1]))
    for r in results:
        status = "OK  " if r.ok else "FAIL"
        note = "（對不到任何檔案：下限表過期）" if r.files == 0 else ""
        print(
            f"{status} {r.rate:6.2f}% ≥ {r.floor:5.1f}%  "
            f"{r.covered:5}/{r.lines:<5} {r.files:3} 檔  {r.reason}{note}"
        )
        print(f"       {', '.join(r.patterns)}")
    failed = [r for r in results if not r.ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} 條下限通過")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
