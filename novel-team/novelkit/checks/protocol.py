"""协议解析检查插件（v2 Phase 2：由 tools/gate-check.py _check_protocol 移植，判定逻辑逐行保真）。

v1 语义：检查 frontmatter 元数据完整性。缺任一必填字段 → fail（P0）。
"""

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core.results import CheckResult, CheckStatus, Severity

# v1 GATE_CONFIG["metadata"]["required_fields"] 原样保留。
# 注：统一配置 novelkit.json 未收录此字段列表（阈值类才进统一配置），
# 此处内联 v1 字面量，避免对已删除的 GATE_CONFIG 产生依赖。
REQUIRED_FIELDS = ["title", "author", "date", "word_count"]


@register
class ProtocolCheck:
    name = "protocol"
    default_severity = Severity.BLOCK  # v1 _classify_gate: protocol ∈ P0

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        try:
            # —— 以下移植自 v1 _check_protocol（tools/gate-check.py:338），仅 content/metadata 改为 chapter.body/chapter.meta ——
            raw = {"status": "pass", "details": []}

            # 检查元数据完整性
            for field in REQUIRED_FIELDS:
                if field not in chapter.meta:
                    raw["status"] = "fail"
                    raw["details"].append(f"缺少元数据字段：{field}")
            # —— 移植结束 ——
        except Exception as e:
            # v1 教训：检查没跑必须可见，不静默为 pass
            raw = {"status": "warning",
                   "details": [f"protocol 执行异常（{e}），该检查项未覆盖"]}
        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}[raw["status"]]
        return CheckResult(check=self.name, status=status,
                           severity=self.default_severity,
                           details=list(raw.get("details", [])), raw=raw)
