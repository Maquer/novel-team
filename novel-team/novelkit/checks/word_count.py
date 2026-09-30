"""字数检查插件（v2 Phase 2：由 tools/gate-check.py _check_word_count 移植）。

v1 语义（09-29 软化）：
- 字数 < soft_min*(1-范围)  → fail（P1，真过短/信息密度不足）
- soft_min ~ min_words      → 静默 pass（min_words 是写作目标，不是门禁）
- 字数 > max_words*(1+范围) → warning（P1，超标）

v2 改动（评审决策 D1，2026-09-30：取严，不保留 1350/1500 双轨）：
- 下限统一为统一配置的 soft_min=1500，不再打 (1-flexible_range) 折扣；
- 阈值来源改为 ctx.config（config/novelkit.json）：soft_min=1500 / warn_above=5500；
- v1 实际触发线为 max_words*(1+flexible_range)=5000*1.1=5500，与统一配置
  warn_above=5500 一致，行为不变；details 文案中的阈值数字改为 warn_above
  （v1 文案写的是 max_words=5000，与实际触发线 5500 不一致，属文案 bug）。
- 字数口径：chapter.char_count()，与 v1 的 len(re.sub(r"\\s+", "", content)) 一致。
"""

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core.results import CheckResult, CheckStatus, Severity


@register
class WordCountCheck:
    name = "word_count"
    default_severity = Severity.WARN  # v1 _classify_gate: word_count ∈ P1

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        try:
            raw = {"status": "pass", "details": []}
            word_count = chapter.char_count()
            cfg = ctx.config.word_count
            soft_min = cfg["soft_min"]      # 1500（统一配置，取严）
            warn_above = cfg["warn_above"]  # 5500（统一配置，与 v1 实际触发线一致）

            if word_count < soft_min:
                raw["status"] = "fail"
                raw["details"].append(
                    f"字数过短：{word_count} < 软下限 {soft_min}（信息密度不足）")
            elif word_count > warn_above:
                raw["status"] = "warning"
                raw["details"].append(
                    f"字数超标：{word_count} > {warn_above}（考虑拆分）")
        except Exception as e:
            # v1 教训：检查没跑必须可见，不静默为 pass
            raw = {"status": "warning",
                   "details": [f"word_count 执行异常（{e}），该检查项未覆盖"]}
        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}[raw["status"]]
        return CheckResult(check=self.name, status=status,
                           severity=self.default_severity,
                           score=float(chapter.char_count()),
                           details=list(raw.get("details", [])), raw=raw)
