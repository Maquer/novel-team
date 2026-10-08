"""章末钩子检查插件（v2 Phase 2：由 tools/gate-check.py _check_hook 移植，判定逻辑逐行保真）。"""

import re

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core.results import CheckResult, CheckStatus, Severity


@register
class HookCheck:
    name = "hook"
    default_severity = Severity.WARN  # v1 _classify_gate：P1

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        try:
            raw = self._run(chapter)
        except Exception as e:
            # v1 风格：异常必须可见，不静默为 pass
            raw = {"status": "warning",
                   "details": [f"hook 执行异常（{e}），该检查项未覆盖"]}
        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}[raw["status"]]
        return CheckResult(check=self.name, status=status,
                           severity=self.default_severity,
                           details=list(raw.get("details", [])), raw=raw)

    def _run(self, chapter: Chapter) -> dict:
        """8. 章末钩子检查"""
        result = {"status": "pass", "details": [], "has_hook": False}
        content = chapter.body

        paragraphs = content.split("\n")
        # 取最后15段（增加搜索范围）
        ending_paragraphs = paragraphs[-15:] if len(paragraphs) >= 15 else paragraphs

        hook_patterns = [
            r"突然", r"竟然", r"原来", r"没想到", r"居然", r"忽然",
            r"危险", r"威胁", r"杀意", r"阴谋", r"背后", r"暗中",
            r"神秘", r"未知", r"身份", r"真相", r"秘密",
            r"眼神", r"目光", r"神色", r"沉默",
            r"等等", r"且慢", r"站住", r"等一下",
            r"如果", r"难道", r"怎么",
            r"剑", r"醒了", r"异变", r"惊变", r"骤变", r"脸色",
            r"下一章", r"预告",
            r"记号", r"不一样", r"不止", r"另一", r"下面", r"底下", r"藏着", r"够不到",
            r"亮", r"发光", r"闪烁", r"异动", r"震动", r"颤抖", r"微震",
            r"变化", r"改变", r"变成", r"增多", r"减少", r"新增", r"消失",
            r"心跳", r"呼吸", r"节律", r"温度", r"温热", r"冰冷", r"异动", r"突变",
        ]

        combined_text = " ".join(ending_paragraphs)
        hits = []
        for pattern in hook_patterns:
            matches = re.findall(pattern, combined_text)
            if matches:
                hits.extend(matches)

        if hits:
            result["has_hook"] = True
            result["details"].append(f"检测到{len(hits)}处潜在钩子信号：{hits[:5]}...")
        else:
            # 调试：打印搜索范围
            result["status"] = "warning"
            result["details"].append(f"警告：章末未检测到明显钩子（搜索{len(ending_paragraphs)}段）")

        return result
