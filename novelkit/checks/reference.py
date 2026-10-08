"""引用校验检查插件（v2 Phase 2：由 tools/gate-check.py _check_references 移植，判定逻辑逐行保真）。

v1 语义：用正则提取"角色名：…"/"地点名：…"引用；未检测到角色名引用 → details 追加提示，
status 保持 pass（纯提示项，不阻断）。
"""

import re

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core.results import CheckResult, CheckStatus, Severity


@register
class ReferenceCheck:
    name = "reference"
    default_severity = Severity.ADVICE  # v1 _classify_gate: reference ∉ P0/P1 → P2

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        try:
            # —— 以下移植自 v1 _check_references（tools/gate-check.py:350），仅 content 改为 chapter.body ——
            raw = {"status": "pass", "details": []}

            # 检查角色名、地点名引用
            character_pattern = r"[角色名：](.+?)[，,。]"
            location_pattern = r"[地点名：](.+?)[，,。]"

            characters = re.findall(character_pattern, chapter.body)
            locations = re.findall(location_pattern, chapter.body)

            if not characters:
                raw["details"].append("警告：未检测到角色名引用")
            # —— 移植结束 ——
        except Exception as e:
            # v1 教训：检查没跑必须可见，不静默为 pass
            raw = {"status": "warning",
                   "details": [f"reference 执行异常（{e}），该检查项未覆盖"]}
        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}[raw["status"]]
        return CheckResult(check=self.name, status=status,
                           severity=self.default_severity,
                           details=list(raw.get("details", [])), raw=raw)
