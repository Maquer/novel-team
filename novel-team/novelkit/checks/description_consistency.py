"""描写一致性检查插件（v2 Phase 2：由 tools/gate-check.py _check_description_consistency 移植，判定逻辑逐行保真）。"""

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core.results import CheckResult, CheckStatus, Severity


@register
class DescriptionConsistencyCheck:
    name = "description_consistency"
    default_severity = Severity.ADVICE  # v1 _classify_gate：P2

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        try:
            raw = self._run(chapter)
        except Exception as e:
            # v1 风格：异常必须可见，不静默为 pass
            raw = {"status": "warning",
                   "details": [f"description_consistency 执行异常（{e}），该检查项未覆盖"]}
        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}[raw["status"]]
        return CheckResult(check=self.name, status=status,
                           severity=self.default_severity,
                           details=list(raw.get("details", [])), raw=raw)

    def _run(self, chapter: Chapter) -> dict:
        """5. 描写一致性检查"""
        result = {"status": "pass", "details": []}
        content = chapter.body

        # 检查段落长度
        paragraphs = content.split("\n")
        long_paragraphs = [p for p in paragraphs if len(p) > 300]

        if long_paragraphs:
            result["status"] = "warning"
            result["details"].append(f"检测到{len(long_paragraphs)}个超长段落（>300字）")

        return result
