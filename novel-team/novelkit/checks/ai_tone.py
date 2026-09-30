"""AI 味检查插件（v2 Phase 2：由 tools/gate-check.py _check_ai_tone 移植）。

v1 通过 subprocess 调用 novel-humanizer.py --chapter-file --json 并解析 stdout；
v2 改为进程内调用其 detect_all(text, threshold)（importlib 加载连字符文件名）。

输入等价性：v1 的 main() 读的是章节文件原文（含 frontmatter），detect_all 内部
_strip_markdown 会剥 frontmatter → 进程内直接传 chapter.raw，输入与 v1 完全一致。

判定逻辑、阈值、details 文案逐行保真。异常映射照搬 v1：任何异常 → status=fail
（不是 warning，别改错——v1 的 except Exception 分支是 fail）。

v1 → 统一配置映射（config/novelkit.json）：
- max_score=15 → ai_tone.threshold=15.0（传给 detect_all；门禁用的是 tier_1a 原始分）
- fail_line=15*1.05=15.75 → ai_tone.block_at=16.0（tier_1a 恒为整数，>15.75 ⇔ >=16）
- warn_at=13 → ai_tone.warn_at=13
文案里的"> 15"来自 v1 的 int(fail_line)=int(15.75)，此处写成 block_at-1，保持逐字一致。
"""

import importlib.util

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core import log
from novelkit.core.results import CheckResult, CheckStatus, Severity

_HUMANIZER_MOD = None  # 进程内只加载一次


def _load_humanizer(ctx: Context):
    """importlib 加载 tools/novel-humanizer.py（连字符文件名，非合法模块名）。"""
    global _HUMANIZER_MOD
    if _HUMANIZER_MOD is not None:
        return _HUMANIZER_MOD
    path = ctx.repo_root / "tools" / "novel-humanizer.py"
    spec = importlib.util.spec_from_file_location("novel_humanizer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _HUMANIZER_MOD = mod
    return mod


@register
class AiToneCheck:
    """AI 味检查（P0 阻断）。"""

    name = "ai_tone"
    default_severity = Severity.BLOCK  # v1 _classify_gate：p0_gates

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        raw = {"status": "pass", "details": [], "tier_1a": None}
        try:
            cfg = ctx.config.get("ai_tone") or {}
            threshold = cfg.get("threshold", 15.0)
            block_at = int(cfg.get("block_at", 16.0))
            warn_at = cfg.get("warn_at", 13)

            mod = _load_humanizer(ctx)
            # FIX 2026-09-30（内化）：v1 的 main() 读取文件原文（含 frontmatter），
            # detect_all 内部 _strip_markdown 负责剥离 → 此处传 chapter.raw，
            # 输入与 v1 的 --chapter-file 路径逐字节一致。
            data = mod.detect_all(chapter.raw, threshold=threshold)
            tier_1a = data.get("tier_1a", 0)
            raw["tier_1a"] = tier_1a

            # FIX 2026-09-30：tier_1a 恒为整数（各 rule score 之和），原
            # `elif tier_1a > threshold:`（即 15 < tier_1a <= 15.75）无整数解、
            # 永远不可达。阻断语义保持不变（tier_1a >= 16 → fail）；
            # warning 改为"接近阈值"预警：warn_at <= tier_1a <= max_score，
            # 提醒作者在触发阻断前收敛，而非等超标后再返工。
            # 统一配置以 block_at=16.0 记录阻断线（>15.75 ⇔ >=16）；
            # 文案中的"> 15"即 v1 的 int(fail_line)=int(15.75)，写成 block_at-1 保持逐字一致。
            if tier_1a >= block_at:
                raw["status"] = "fail"
                raw["details"].append(
                    f"AI味严重超标：tier_1a={tier_1a} > {block_at - 1}"
                )
            elif tier_1a >= warn_at:
                raw["status"] = "warning"
                raw["details"].append(
                    f"AI味接近阈值：tier_1a={tier_1a}（阻断线 {block_at - 1}，建议收敛表达）"
                )
        except Exception as e:
            # v1 映射：humanizer 输出非 JSON / 超时 / 其他异常 → 全部记 fail。
            # 进程内调用无"输出非 JSON"与 30s 超时语义，统一走本分支。
            raw["status"] = "fail"
            raw["details"].append(f"AI味检查异常：{e}")
            log.warn(f"ai_tone 执行异常：{e}")

        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}.get(raw["status"], CheckStatus.ERROR)
        return CheckResult(
            check=self.name,
            status=status,
            severity=self.default_severity,
            score=raw["tier_1a"],
            details=list(raw.get("details", [])),
            raw=raw,
        )
