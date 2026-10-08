"""逻辑审查检查插件（v2 Phase 2：由 tools/gate-check.py _check_logic_review 移植）。

v1 通过 subprocess 跑 `python -m tools.logic-review --file <章>`，再从人类可读输出里
抓取含 ❌/严重 的行作为 details；v2 改为进程内复用 logic-review.py 的
strip_meta/load_rules/load_chars/load_world 与各 rule_* 函数（importlib 加载），
issues 收集段与 main() 逐行一致（去掉 argparse/print/sys.exit）。

FIX 2026-09-30（内化）：v1 曾用 cwd 钉住工具树根以防 `python -m tools.logic-review`
的包导入随调用方工作目录漂移（"换目录即 bypass"后门）。logic-review.py 的资源
路径全部基于 `ROOT = Path(__file__).resolve().parent.parent`（绝对路径），进程内
调用天然不受 cwd 影响，该 FIX 已内化，不再需要 cwd 参数。

异常映射照搬 v1：执行失败 → status=warning + "logic-review 未执行（…），逻辑审查项未覆盖"。
"""

import importlib.util

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core import log
from novelkit.core.results import CheckResult, CheckStatus, Severity

_LOGIC_REVIEW_MOD = None  # 进程内只加载一次


def _load_logic_review(ctx: Context):
    global _LOGIC_REVIEW_MOD
    if _LOGIC_REVIEW_MOD is not None:
        return _LOGIC_REVIEW_MOD
    path = ctx.repo_root / "tools" / "logic-review.py"
    spec = importlib.util.spec_from_file_location("logic_review_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _LOGIC_REVIEW_MOD = mod
    return mod


@register
class LogicReviewCheck:
    """逻辑审查检查（P2；v1 _classify_gate：非 p0/p1 即 P2）。"""

    name = "logic_review"
    default_severity = Severity.ADVICE

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        raw = {"status": "pass", "details": []}
        try:
            mod = _load_logic_review(ctx)
            # 与 logic-review.py main() 的 issues 收集段逐行一致。
            # v1 门禁调用时未传 --chapter（chapter=None），此处保持一致。
            text = mod.strip_meta(chapter.raw)
            rules = mod.load_rules()
            # FIX 2026-10-04：世界包/角色表按项目目录动态解析（project_guard 约定：
            # current/world-packs/ 与 current/characters/），不再写死玄天大陆/my-novel。
            world_pack_dir = ctx.project_dir / "world-packs"
            world_files = sorted(world_pack_dir.glob("*.json")) if world_pack_dir.exists() else []
            world_path = str(world_files[0]) if world_files else None
            chars_path = ctx.project_dir / "characters" / "characters.json"
            chars = mod.load_chars(str(chars_path) if chars_path.exists() else None)["characters"]
            world = mod.load_world(world_path)

            issues = []
            issues += mod.rule_era_words(text, rules["era_words"])
            issues += mod.rule_realm_capability(text, rules["realm_capability"], chars, world)
            issues += mod.rule_divine_sense(text, rules["divine_sense_boundary"], chars)
            issues += mod.rule_time_contradiction(text, rules["time_contradiction"], chapter=None)
            issues += mod.rule_position_contradiction(text, rules["position_contradiction"])
            issues += mod.rule_modern_item_org(text, rules["modern_item_org_conflict"], world)
            issues += mod.rule_duplicate_sentences(text)
            issues += mod.rule_constitution_valid(text, rules.get("constitution_valid", {}), world, chars)
            issues += mod.rule_constitution_sword_match(text, rules.get("constitution_sword_match", {}), world, chars)

            errors = [i for i in issues if i.get("severity") == "error"]
            warns = [i for i in issues if i.get("severity") == "warn"]

            if errors:
                raw["status"] = "fail"
                # v1 从人类可读输出里抓取含 ❌/严重 的行：
                #   错误行形如 "  ❌ [rule] detail"；
                #   汇总行 "状态: ❌ FAIL | 错误 N | 警告 M" 含 ❌ 也会被抓取。
                # 此处按同样规则复现，保证 details 逐字一致。
                lines = []
                for i in issues:
                    tag = "❌" if i.get("severity") == "error" else "⚠️"
                    lines.append(f"  {tag} [{i['rule']}] {i.get('detail', i.get('word', ''))}")
                lines.append(
                    f"状态: {'✅ PASS' if not errors else '❌ FAIL'}"
                    f" | 错误 {len(errors)} | 警告 {len(warns)}"
                )
                for line in lines:
                    if "❌" in line or "严重" in line:
                        raw["details"].append(line.strip())
                # 若输出里没有 ❌/严重 行（如模块缺失），保留输出尾部，
                # 避免"判了 fail 却无 details"的空项（BUG 5 兜底）。
                if not raw["details"]:
                    tail = [l.strip() for l in lines if l.strip()][-3:]
                    if tail:
                        raw["details"].append("logic-review 非零退出：" + " / ".join(tail)[:200])
        except Exception as e:
            # FIX 2026-09-30：执行失败不再静默置 pass（假阴性），记 warning
            # 并写明原因——"检查没跑"必须可见，不能显示为通过。
            raw["status"] = "warning"
            raw["details"].append(f"logic-review 未执行（{e}），逻辑审查项未覆盖")
            log.warn(f"logic_review 执行异常：{e}")

        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}.get(raw["status"], CheckStatus.ERROR)
        return CheckResult(
            check=self.name,
            status=status,
            severity=self.default_severity,
            details=list(raw.get("details", [])),
            raw=raw,
        )
