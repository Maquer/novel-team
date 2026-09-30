"""套路/AI 腔检测插件（v2 Phase 2：由 tools/gate-check.py _check_cliche 移植）。

P2 建议级，不阻断。命中即 status=fail → 进 p2_suggestions 桶（v1 语义）。
模块级常量（CLICHE_PATTERNS / TIME_REPORT_* / SCENE_JUMP_*）随检查一起搬入，
含 FIX 2026-09-30 的注释（SCENE_JUMP_* 在 v1 原包中被引用但未定义致 NameError）。
"""

import re

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core.results import CheckResult, CheckStatus, Severity


# 套路/AI腔黑名单（09-29 多模型测试新增）：拦『一眼假』的主要来源。
# 依据：字数门禁已软化，但"金句/套路结尾/陈旧比喻"此前无人检测——这正是
# 写作者说"一眼假、没有故事性"的根因。命中即 P2 提示（不阻断），允许少量误报。
CLICHE_PATTERNS = [
    (re.compile(r"故事.{0,4}才刚.{0,4}开始"), "套路结尾『故事才刚刚开始』"),
    (re.compile(r"才刚刚开始"), "套路『才刚刚开始』"),
    (re.compile(r"他知道.{0,6}(这不是|不是暂时的|是倒计时)"), "直白金句『他知道…是倒计时』"),
    (re.compile(r"他明白了[。．]"), "直白『他明白了』"),
    (re.compile(r"眼中闪过一丝"), "套路『眼中闪过一丝』"),
    (re.compile(r"湿透的黑布"), "陈旧比喻『湿透的黑布』"),
    (re.compile(r"沉甸甸地压"), "套路『沉甸甸地压』"),
    (re.compile(r"他的故事"), "套路『他的故事』"),
    (re.compile(r"(?:我要[^。；\n]{1,15}。){3,}"), "排比三连『我要…我要…我要…』"),
    (re.compile(r"(?m)^\s*最后[，,]"), "议论文总结腔『最后，…』（序数用法如『最后一口』不受影响）"),
]
# 日历报数阈值：一章内出现「第X天/周/夜/日」超过 N 处 → 疑似流水账（09-29 洞察：好故事靠事件驱动，不靠日历报数）
TIME_REPORT_THRESHOLD = 2
TIME_REPORT_RE = re.compile(r"第[一二三四五六七八九十0-9]{1,3}(天|周|夜|日)")
# 场景跳跃阈值：一章内硬切场景超过 N 处 → 疑似缺少过渡桥段（09-29 洞察）
# FIX 2026-09-30：SCENE_JUMP_PATTERNS / SCENE_JUMP_THRESHOLD 在原包中被 _check_cliche 引用
# 但从未定义，导致每次 check() 跑到此处即 NameError 崩溃（P0：门禁主流程必经之路）。
# 此处补上定义；模式与阈值为经验取值（设计决策），命中仅进 P2 建议、永不阻断。
SCENE_JUMP_THRESHOLD = 3
SCENE_JUMP_PATTERNS = [
    (re.compile(r"与此同时"), "硬切『与此同时』"),
    (re.compile(r"另一边"), "硬切『另一边』"),
    (re.compile(r"画面一转"), "硬切『画面一转』"),
    (re.compile(r"镜头(一转|转向)"), "硬切『镜头一转/转向』"),
    (re.compile(r"视角(一切换|转换为)"), "硬切『视角切换』"),
]


@register
class ClicheCheck:
    """套路/AI 腔检测（P2 建议级，不阻断）——09-29 多模型测试新增。"""

    name = "cliche"
    default_severity = Severity.ADVICE

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        raw = {"status": "pass", "details": []}
        # v1 门禁开关：GATE_CONFIG["cliche"]["enabled"] 默认为 True。
        # 统一配置 config/novelkit.json 未设 cliche 节 → 保持默认启用（与 v1 一致）。
        content = chapter.body
        for pat, label in CLICHE_PATTERNS:
            if pat.search(content):
                raw["details"].append(label)
        # A（09-29）：日历报数检测——把『淡化时间、事件驱动』洞察门禁化
        n_report = len(TIME_REPORT_RE.findall(content))
        if n_report > TIME_REPORT_THRESHOLD:
            raw["details"].append(
                f"日历报数 {n_report} 处『第X天/周』（疑似流水账，建议事件驱动/淡化时间）")
        # B（09-29）：场景跳跃检测——把『连贯过渡』洞察门禁化
        n_jumps = sum(1 for pat, _ in SCENE_JUMP_PATTERNS if pat.search(content))
        if n_jumps > SCENE_JUMP_THRESHOLD:
            raw["details"].append(
                f"场景跳跃 {n_jumps} 处（疑似硬切，建议加过渡桥段：行走/等待/天气变化）")
        if raw["details"]:
            raw["status"] = "fail"  # P2 gate：fail → 进 p2_suggestions 桶，不阻断

        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}.get(raw["status"], CheckStatus.ERROR)
        return CheckResult(
            check=self.name,
            status=status,
            severity=self.default_severity,
            details=list(raw.get("details", [])),
            raw=raw,
        )
