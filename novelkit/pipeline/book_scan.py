"""novelkit.pipeline.book_scan — 全书扫描（Phase 4 新能力）。

对全书章节逐个复用门禁 Orchestrator（进程内调用，含 hash 缓存加速），
汇总成书级报告。单个章节失败不中断整书扫描。
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from novelkit.core import log as _log
from novelkit.core.resolve import resolve
from novelkit.pipeline.orchestrator import Orchestrator

log = _log

_CH_NO_RE = re.compile(r"(\d+)")


@dataclass
class ChapterScanResult:
    file: str
    chapter_no: Optional[int]
    passed: bool
    p0: int
    p1: int
    p2: int
    tier_1a: Optional[float]
    error: Optional[str] = None  # 本章 check 抛异常时的说明

    def to_dict(self) -> Dict:
        return {
            "file": self.file,
            "chapter_no": self.chapter_no,
            "passed": self.passed,
            "p0": self.p0,
            "p1": self.p1,
            "p2": self.p2,
            "tier_1a": self.tier_1a,
            "error": self.error,
        }


@dataclass
class BookScanReport:
    novel_id: str
    chapters: List[ChapterScanResult] = field(default_factory=list)
    total: int = 0
    passed_count: int = 0
    failed_count: int = 0
    scanned_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "novel_id": self.novel_id,
            "total": self.total,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "scanned_at": self.scanned_at,
            "chapters": [c.to_dict() for c in self.chapters],
        }


def _chapter_no(path: str) -> Optional[int]:
    m = _CH_NO_RE.search(Path(path).stem)
    return int(m.group(1)) if m else None


def scan_book(novel_id: str, chapter_files: List[str],
              mode: str = "write", use_cache: bool = True) -> BookScanReport:
    """扫描全书章节，返回书级报告并落盘。

    每章复用 Orchestrator.check()（v1 形状 dict）；单章异常记 error，
    不中断后续章节。
    """
    report = BookScanReport(
        novel_id=novel_id,
        scanned_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    orch = Orchestrator(novel_id=novel_id, mode=mode,
                        no_cache=not use_cache)

    for f in chapter_files:
        try:
            res = orch.check(f)
            checks = res.get("checks", {}) or {}
            ai_tone = checks.get("ai_tone", {}) or {}
            summary = res.get("summary", {}) or {}
            report.chapters.append(ChapterScanResult(
                file=f,
                chapter_no=_chapter_no(f),
                passed=bool(res.get("passed")),
                p0=int(summary.get("p0_blockers", len(res.get("p0_failures", [])))),
                p1=int(summary.get("p1_warnings", len(res.get("p1_warnings", [])))),
                p2=int(summary.get("p2_suggestions", len(res.get("p2_suggestions", [])))),
                tier_1a=ai_tone.get("tier_1a"),
            ))
        except Exception as e:  # 单章失败不拖死整书
            log.error(f"扫描章节失败 {f}: {e}")
            report.chapters.append(ChapterScanResult(
                file=f,
                chapter_no=_chapter_no(f),
                passed=False,
                p0=0, p1=0, p2=0,
                tier_1a=None,
                error=str(e),
            ))

    report.total = len(report.chapters)
    report.passed_count = sum(1 for c in report.chapters if c.passed)
    report.failed_count = report.total - report.passed_count

    _save_report(novel_id, report)
    return report


def _save_report(novel_id: str, report: BookScanReport) -> Optional[Path]:
    """扫描报告落盘（风格同 orchestrator._save_result）。"""
    try:
        result_dir = resolve(novel_id).root_dir / "reports"
        result_dir.mkdir(parents=True, exist_ok=True)
        p = result_dir / f"book-scan-{int(time.time())}.json"
        p.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
                     encoding="utf-8")
        return p
    except OSError as e:
        log.error(f"扫描报告落盘失败: {e}")
        return None
