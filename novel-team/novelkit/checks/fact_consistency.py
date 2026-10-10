"""事实一致性检查插件（v2 Phase 2：由 tools/gate-check.py _check_fact_consistency 移植，判定逻辑逐行保真）。

v1 说明（BUG 6：修前 p0_gates 声明了此 gate 但无任何实现）：
两条可真实检测的冲突：
1. 提前引用：本章引用了「来源章节编号 > 本章编号」的事实 → 剧情时间线倒流
2. 提前揭示：账本中标记 hidden / planned（未揭示）的实体出现在本章正文

v2 变更（已评审）：
- 账本访问走 novelkit.stores.fact_store.FactStore（替代 v1 的直接读 JSON）。
  路径约定一致（<root>/ledger/<novel_id>/facts.json），NOVEL_TEAM_ROOT 未设置时
  与 v1 行为完全一致（差异 D3 已评审通过）。
- 注：v1 本函数并无 `from fact_ledger import FactLedger`（该已知 bug 在
  _sync_to_ledger，由编排器侧修复），此处无 import 需要替换。
- 边缘差异：v1 账本 JSON 损坏时 except → 静默 pass；v2 此处记 warning
  （"检查没跑必须可见"，与 2026-09-30 审计精神一致）。
"""

import os
import re

from novelkit.checks.base import Context, register
from novelkit.core.chapter import Chapter
from novelkit.core.results import CheckResult, CheckStatus, Severity
from novelkit.stores.fact_store import FactStore


@register
class FactConsistencyCheck:
    name = "fact_consistency"
    default_severity = Severity.BLOCK  # v1 _classify_gate：P0

    def run(self, chapter: Chapter, ctx: Context) -> CheckResult:
        try:
            raw = self._run(chapter, ctx)
        except Exception as e:
            # v1 风格：异常必须可见，不静默为 pass
            raw = {"status": "warning",
                   "details": [f"fact_consistency 执行异常（{e}），该检查项未覆盖"]}
        status = {"pass": CheckStatus.PASS, "fail": CheckStatus.FAIL,
                  "warning": CheckStatus.WARNING}[raw["status"]]
        return CheckResult(check=self.name, status=status,
                           severity=self.default_severity,
                           details=list(raw.get("details", [])), raw=raw)

    def _run(self, chapter: Chapter, ctx: Context) -> dict:
        result = {"status": "pass", "details": []}
        content = chapter.body

        m = re.search(r"chapter[-_]?(\d+)", os.path.basename(str(chapter.path)))
        if not m:
            return result
        chap_no = int(m.group(1))

        # Phase 3：账本访问走 ctx.stores.fact（契约第 2 条：文件 IO 走 ctx.stores，
        # 不自己拼路径/构造 store）。账本缺失时 facts 为空 → 循环不执行 → pass，
        # 与 v1「ledger_path 不存在 → return result」语义等价。
        store = ctx.stores.fact if ctx.stores else FactStore(ctx.novel_id)
        # H2：账本损坏时检查没跑必须可见（记 warning，不静默 pass）。
        load_errors = getattr(store, "load_errors", None) or []
        if load_errors:
            result["status"] = "warning"
            result["details"].extend(
                f"fact_consistency 未覆盖：{e}" for e in load_errors)
            return result
        facts = list(store.facts.values()) if isinstance(store.facts, dict) else store.facts

        for f in facts:
            if not isinstance(f, dict):
                continue
            body = str(f.get("content", ""))
            # 实体名 = 冒号前部分；剥离「（隐藏）」「（待创作）」等注记，
            # 否则无法与正文中的真实实体名匹配（修前 "混沌体（隐藏）" 匹配不到 "混沌体"）
            name = body.split("：")[0].strip()
            name = re.sub(r"[（(][^（）()]*[)）]", "", name).strip()
            if not name or len(name) > 10:
                continue
            status = str(f.get("status", ""))

            src_m = re.search(r"chapter[-_]?(\d+)", str(f.get("source", "")))
            src_no = int(src_m.group(1)) if src_m else None

            if src_no and src_no > chap_no:
                result["status"] = "fail"
                result["details"].append(
                    f"事实冲突：第{chap_no}章引用了第{src_no}章才记录的事实「{name}」"
                    f"（来源 {f.get('source')}，状态 {status}）")
                continue

            if status in ("hidden", "planned") and name in content:
                result["status"] = "fail"
                result["details"].append(
                    f"事实冲突：「{name}」在账本中状态为 {status}（未揭示），"
                    f"却在第{chap_no}章正文出现")

        return result
