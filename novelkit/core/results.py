"""统一结果模型。替代各工具自创的 JSON schema（问题 #6）。

契约（设计文档 §7）：to_dict() 必须可 JSON 序列化，字段名锁定，
tests/test_contract.py 覆盖。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class Severity:
    """三级语义，与 v1 一致，原样保留。"""
    BLOCK = "P0"    # 阻断创作流程
    WARN = "P1"     # 警告，不阻断
    ADVICE = "P2"   # 建议，不阻断


class CheckStatus:
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    ERROR = "error"   # 检查本身没跑起来（v1 教训：必须可见，不能静默为 pass）
    SKIPPED = "skipped"  # modify 模式下跳过的检查（不参与判定，v1 语义保留）


@dataclass
class CheckResult:
    check: str                      # 检查名，如 "ai_tone"
    status: str                     # pass / fail / warning / error / skipped
    severity: str                   # P0 / P1 / P2
    score: Optional[float] = None   # 数值分（无则 None）
    details: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)  # v1 形状的原始结果 dict，供门禁 CLI 兼容输出

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check": self.check,
            "status": self.status,
            "severity": self.severity,
            "score": self.score,
            "details": list(self.details),
            "suggestions": list(self.suggestions),
            "raw": dict(self.raw),
        }


@dataclass
class GateReport:
    passed: bool
    will_block: bool
    p0_failures: List[CheckResult] = field(default_factory=list)
    p1_warnings: List[CheckResult] = field(default_factory=list)
    p2_suggestions: List[CheckResult] = field(default_factory=list)
    tier_1a_score: Optional[float] = None
    chapter_file: str = ""
    errors: List[str] = field(default_factory=list)  # 检查执行错误（error 级）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "will_block": self.will_block,
            "chapter_file": self.chapter_file,
            "tier_1a_score": self.tier_1a_score,
            "p0_failures": [r.to_dict() for r in self.p0_failures],
            "p1_warnings": [r.to_dict() for r in self.p1_warnings],
            "p2_suggestions": [r.to_dict() for r in self.p2_suggestions],
            "errors": list(self.errors),
        }
