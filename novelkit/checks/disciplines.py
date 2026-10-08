"""创作纪律检查插件（v2 Phase 2：由 tools/gate-check.py _check_disciplines 移植）。

接入 anti-ai-12.py 的 12 条纪律，P2 建议级，不阻断。
v1 已是 in-process 接入（importlib 加载并直接调用 check(text)，不拉 subprocess），
此处原样移植，仅把模块路径改为 ctx.repo_root 下的 tools/anti-ai-12.py。

FIX 2026-09-30（保留）：此前门禁完全不调用 anti-ai-12 的 12 条纪律，
纪律 1–8、10–12 的正则在门禁链路中无任何对应实现——写了等于没跑。

安全说明：anti-ai-12.py 顶层只有常量/类定义（有 __main__ 守卫）；
AntiAI12Checker.__init__ 仅只读加载自定义禁词（损坏则忽略），
check(text) 为纯读操作，不触发任何文件写入。
"""

import importlib.util

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core import log
from novelkit.core.results import CheckResult, CheckStatus, Severity

_ANTI_AI_12_MOD = None  # 进程内只加载一次


def _load_anti_ai_12(ctx: Context):
    global _ANTI_AI_12_MOD
    if _ANTI_AI_12_MOD is not None:
        return _ANTI_AI_12_MOD
    # 文件名含连字符，不是合法模块名，用 spec_from_file_location 加载
    mod_path = ctx.repo_root / "tools" / "anti-ai-12.py"
    spec = importlib.util.spec_from_file_location("anti_ai_12", mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _ANTI_AI_12_MOD = mod
    return mod


@register
class DisciplinesCheck:
    """创作纪律检查（P2 建议级，不阻断）。"""

    name = "disciplines"
    default_severity = Severity.ADVICE

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        raw = {"status": "pass", "details": []}
        try:
            mod = _load_anti_ai_12(ctx)
            checker = mod.AntiAI12Checker()
            hits = checker.check(chapter.body)
        except Exception as e:
            # 接入失败不影响主流程：记一条提示，不判 fail
            raw["details"].append(f"纪律检查未执行（{e}）")
            log.warn(f"disciplines 接入失败：{e}")
        else:
            for h in hits:
                raw["details"].append(
                    f"纪律{h.get('id')}「{h.get('name')}」命中{h.get('matches', 0)}处"
                )
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
