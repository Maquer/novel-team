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

v3 改动（2026-10-03：基于康熙实测数据升级）：
- 数据来源：《我的公公叫康熙》302章统计，P50=2596字，P10=2288字，70%章节在2000-3000字
- 新增三级门槛：
  - hard_min=1500：低于此为 P0 阻断（信息严重不足）
  - soft_min=2000：低于此为 P1 警告（建议扩充）
  - target=2500：写作目标，不阻断但提示
  - warn_above=3500：高于此为 P2 提示（考虑是否拖沓）
- 判定逻辑：
  - word_count < hard_min → FAIL (P0)
  - hard_min <= word_count < soft_min → WARNING (P1)
  - soft_min <= word_count < target → PASS（静默）
  - target <= word_count < warn_above → PASS（达标）
  - word_count >= warn_above → WARNING (P2)
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
            hard_min = cfg["hard_min"]      # 1500：P0 阻断线
            soft_min = cfg["soft_min"]      # 2000：P1 警告线
            target = cfg["target"]          # 2500：写作目标
            warn_above = cfg["warn_above"]  # 3500：P2 提示线

            if word_count < hard_min:
                # P0：硬底线，信息严重不足
                raw["status"] = "fail"
                raw["details"].append(
                    f"字数严重不足：{word_count} < 硬底线 {hard_min}（必须重写）")
            elif word_count < soft_min:
                # P1：软下限，提示警告
                raw["status"] = "warning"
                raw["details"].append(
                    f"字数偏少：{word_count} < 软下限 {soft_min}（建议扩充到{target}字）")
            elif word_count >= warn_above:
                # P2：超长提示
                raw["status"] = "warning"
                raw["details"].append(
                    f"字数超标：{word_count} >= {warn_above}（考虑拆分或精简）")
            # else: PASS（达标区间）

            # 补充字数统计元数据
            raw["word_count"] = word_count
            raw["hard_min"] = hard_min
            raw["soft_min"] = soft_min
            raw["target"] = target
            raw["warn_above"] = warn_above
        except Exception as e:
            # v1 教训：检查没跑必须可见，不静默为 pass
            raw = {"status": "warning",
                   "details": [f"word_count 执行异常（{e}），该检查项未覆盖"],
                   "word_count": 0}
        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}[raw["status"]]
        # 注意：Severity 只有 BLOCK/WARN/ADVICE 三级（无 ERROR）。
        # fail → P0 阻断（BLOCK），warning → P1 警告（WARN），pass → 无严重级。
        severity = {"fail": Severity.BLOCK, "warning": Severity.WARN,
                    "pass": None}[raw["status"]]
        return CheckResult(check=self.name, status=status,
                           severity=severity,
                           score=float(chapter.char_count()),
                           details=list(raw.get("details", [])), raw=raw)
