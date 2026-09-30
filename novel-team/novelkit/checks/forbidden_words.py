"""禁用词检查插件（v2 Phase 2：由 tools/gate-check.py _check_forbidden_words 移植，判定逻辑逐行保真）。

v1 语义：命中任一禁用词 → warning（P1），逐词追加 details。
（修前此函数名为 _check_unknown_entities；09-29 分级去掉「最后」。）
"""

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core.results import CheckResult, CheckStatus, Severity

# v1 字面量原样保留。
# 09-29 分级：去掉「最后」（序数用法"最后一口/最后一刀"被误伤）；
# 议论文总结腔「最后，…」改由 cliche 检测（CLICHE_PATTERNS）按句首拦截。
FORBIDDEN_WORDS = ["首先", "其次", "综上所述"]


@register
class ForbiddenWordsCheck:
    name = "forbidden_words"
    default_severity = Severity.WARN  # v1 _classify_gate: forbidden_words ∈ P1

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        try:
            # —— 以下移植自 v1 _check_forbidden_words（tools/gate-check.py:440），仅 content 改为 chapter.body ——
            raw = {"status": "pass", "details": []}

            # 检查禁用词
            for word in FORBIDDEN_WORDS:
                if word in chapter.body:
                    raw["status"] = "warning"
                    raw["details"].append(f"检测到禁用词：{word}")
            # —— 移植结束 ——
        except Exception as e:
            # v1 教训：检查没跑必须可见，不静默为 pass
            raw = {"status": "warning",
                   "details": [f"forbidden_words 执行异常（{e}），该检查项未覆盖"]}
        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}[raw["status"]]
        return CheckResult(check=self.name, status=status,
                           severity=self.default_severity,
                           details=list(raw.get("details", [])), raw=raw)
