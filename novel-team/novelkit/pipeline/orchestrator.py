"""novelkit/pipeline/orchestrator.py — 门禁编排器（v2 Phase 2）。

替代 v1 tools/gate-check.py 的 GateChecker 上帝对象：
- 检查逻辑已拆为 novelkit/checks/ 下的 13 个插件，此处只负责编排、
  结果汇总、判定、落盘与事件发射。
- 对外输出的 results dict 与 v1 check() 返回体形状逐字段一致
  （CLI 兼容：tools/gate-check.py 垫片直接打印它）。
- 判定/汇总/_save_result/generate_fix_order 均从 v1 逐行移植
  （含全部 FIX/BUG 注释的语义），仅 _sync_to_ledger 修了 v1 的 bug：
  v1 `from fact_ledger import FactLedger` 恒 ImportError 又被静默吞掉，
  门禁结果从未同步到账本；现改用 novelkit.stores.fact_store.FactStore，
  失败时写 stderr 可见。
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

from novelkit.checks import CHECK_ORDER
from novelkit.checks.base import (
    Context,
    error_result,
    get_check,
    skipped_result,
)
from novelkit.core.chapter import Chapter
from novelkit.core.config import get_config
from novelkit.core import log as _log
from novelkit.core.resolve import resolve
from novelkit.core.results import CheckResult, CheckStatus, GateReport, Severity
from novelkit.pipeline.cache import CheckCache  # Phase 3：文件 hash 缓存
from novelkit.stores import Stores  # Phase 3：stores 全量接入
from novelkit.stores.fact_store import FactStore

log = _log

# v1 常量移植（tools/gate-check.py）
MODIFY_SKIP_GATES = [
    "ai_tone",       # 修改模式不跑完整质检
    "word_count",    # 小改动可跳过字数检查
    "forbidden_words",  # 修改模式不重复扫禁用词
    "hook",          # 钩子检查非必需
]

# 必须执行的检查项（无论什么模式）
MODIFY_REQUIRED_GATES = [
    "fact_consistency",  # 事实一致性不可跳过
    "protocol",          # 协议完整性
    "blueprint",         # 蓝图出场
    "logic_review",      # 逻辑审查
]

# v1 _classify_gate 的级别映射（P0_GATES / P1_GATES，其余 P2）
_P0_GATES = ["ai_tone", "fact_consistency", "protocol"]
_P1_GATES = ["word_count", "forbidden_words", "hook"]

# v1 BLOCK_GATES（_evaluate_results 阻断层）
_BLOCK_GATES = ["fact_consistency", "ai_tone", "protocol"]


class Orchestrator:
    """门禁编排器：跑插件 → 汇总 → 判定 → 落盘。"""

    def __init__(self, novel_id: str = "my-novel",
                 flexible: bool = False, mode: str = "write",
                 no_cache: bool = False):
        self.novel_id = novel_id
        self.flexible = flexible
        self.mode = mode
        self.no_cache = no_cache  # Phase 3：--no-cache 强制重跑
        self.config = get_config()
        self.project_dir = resolve(novel_id).root_dir
        # 仓库根 = novelkit 所在树根（tools/ 的父目录），供插件加载 tools/*.py
        self.repo_root = Path(__file__).resolve().parent.parent.parent
        self.cache = CheckCache(self.project_dir)
        self.last_evaluation = None

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def check(self, chapter_file: str) -> Dict:
        """执行门禁检查（v1 GateChecker.check 语义，返回 v1 形状 dict）。"""
        results = {
            "chapter_file": chapter_file,
            "flexible_mode": self.flexible,
            "mode": self.mode,
            "checks": {},
            "passed": True,
            "warnings": [],
            "errors": [],
            "p0_failures": [],  # P0阻断级
            "p1_warnings": [],  # P1警告级
            "p2_suggestions": [],  # P2建议级
            "summary": {},  # 汇总统计
        }

        if self.mode == "modify":
            return self._check_modify(chapter_file, results)

        # 默认完整流程
        try:
            chapter = Chapter.load(chapter_file)
        except Exception as e:
            log.error(f"无法读取章节文件 {chapter_file}: {e}")
            results["passed"] = False
            results["errors"].append("无法读取章节文件")
            return results

        ctx = self._make_ctx(chapter)

        # Phase 3：文件 hash 缓存——内容/模式/配置均未变则跳过检查
        cache_key = None
        if not self.no_cache:
            cache_key = self.cache.key(
                chapter.raw, self.novel_id, self.mode, self.flexible,
                self.config.to_dict())
            hit = self.cache.get(cache_key)
            if hit is not None:
                log.info(f"缓存命中，跳过检查: {chapter_file}")
                return hit

        for name in CHECK_ORDER:
            results["checks"][name] = self._run_check(name, ctx).raw

        self._finalize(results)
        self._save_result(results)
        if cache_key is not None:
            # 注意：_finalize/_save_result 之后落缓存；命中时不再重做
            # 报告落盘/账本同步/事件发射等副作用
            self.cache.put(cache_key, results)
        return results

    def _check_modify(self, chapter_file: str, results: Dict) -> Dict:
        """修改模式：最小化检查，只跑必要门禁（v1 _check_modify 移植）。"""
        try:
            chapter = Chapter.load(chapter_file)
        except Exception as e:
            log.error(f"无法读取章节文件 {chapter_file}: {e}")
            results["passed"] = False
            results["errors"].append("无法读取章节文件")
            return results

        ctx = self._make_ctx(chapter)

        # Phase 3：modify 模式同样走 hash 缓存
        cache_key = None
        if not self.no_cache:
            cache_key = self.cache.key(
                chapter.raw, self.novel_id, self.mode, self.flexible,
                self.config.to_dict())
            hit = self.cache.get(cache_key)
            if hit is not None:
                log.info(f"缓存命中，跳过检查: {chapter_file}")
                return hit

        # 必须执行的检查项
        for gate in MODIFY_REQUIRED_GATES:
            results["checks"][gate] = self._run_check(gate, ctx).raw

        # 其他检查项标记为跳过
        for gate in MODIFY_SKIP_GATES:
            results["checks"][gate] = skipped_result(
                gate, self._classify_gate(gate),
                f"修改模式下跳过：{gate}").raw

        # 判定
        results["passed"] = self._evaluate_results(results["checks"], flexible=False)
        results["warnings"] = self._collect_warnings(results["checks"])
        results["errors"] = self._collect_errors(results["checks"])

        results["summary"] = {
            "mode": "modify",
            "p0_blockers": len(results["errors"].get("p0", [])),
            "p1_warnings": len(results["errors"].get("p1", [])) + len(results["warnings"].get("p1", [])),
            "p2_suggestions": len(results["errors"].get("p2", [])) + len(results["warnings"].get("p2", [])),
            "skipped_gates": MODIFY_SKIP_GATES,
            "total_issues": sum([
                len(results["errors"].get("p0", [])),
                len(results["errors"].get("p1", [])) + len(results["warnings"].get("p1", [])),
                len(results["errors"].get("p2", [])) + len(results["warnings"].get("p2", [])),
            ]),
        }

        self._save_result(results)
        if cache_key is not None:
            self.cache.put(cache_key, results)
        return results

    # ------------------------------------------------------------------
    # 插件执行
    # ------------------------------------------------------------------
    def _make_ctx(self, chapter: Chapter) -> Context:
        return Context(
            config=self.config,
            novel_id=self.novel_id,
            chapter=chapter,
            project_dir=self.project_dir,
            repo_root=self.repo_root,
            flexible=self.flexible,
            mode=self.mode,
            stores=Stores.for_novel(self.novel_id),  # Phase 3：stores 全量接入
        )

    def _classify_gate(self, gate_name: str) -> str:
        """将门禁归类到 P0/P1/P2 级别（v1 _classify_gate 移植）。"""
        if gate_name in _P0_GATES:
            return Severity.BLOCK
        elif gate_name in _P1_GATES:
            return Severity.WARN
        else:
            return Severity.ADVICE

    def _run_check(self, name: str, ctx: Context) -> CheckResult:
        """运行单个插件。插件自身已做异常→可见映射；此处是最后兜底。"""
        check_cls = get_check(name)
        if check_cls is None:
            log.error(f"检查插件未注册: {name}")
            raw = {"status": "warning",
                   "details": [f"{name} 插件未注册，该检查项未覆盖"]}
            return CheckResult(check=name, status=CheckStatus.WARNING,
                               severity=self._classify_gate(name),
                               details=list(raw["details"]), raw=raw)
        try:
            return check_cls().run(ctx.chapter, ctx)
        except Exception as e:
            # 兜底：插件不应抛异常，万一抛了也必须可见（记 warning，不静默 pass）
            log.error(f"检查 {name} 异常: {e}")
            raw = {"status": "warning",
                   "details": [f"{name} 执行异常（{type(e).__name__}: {e}），该检查项未覆盖"]}
            return CheckResult(check=name, status=CheckStatus.WARNING,
                               severity=self._classify_gate(name),
                               details=list(raw["details"]), raw=raw)

    # ------------------------------------------------------------------
    # 判定与汇总（v1 _evaluate_results / _collect_warnings / _collect_errors 移植）
    # ------------------------------------------------------------------
    def _finalize(self, results: Dict) -> None:
        """判定结果（v1 check() 尾段移植）。"""
        results["passed"] = self._evaluate_results(results["checks"], self.flexible)
        results["warnings"] = self._collect_warnings(results["checks"])
        results["errors"] = self._collect_errors(results["checks"])

        # 生成汇总统计
        # BUG 8 修复：P1/P2 gate 的 status=="fail" 归入 errors.p1/p2，
        # 而 summary 原先只读 warnings.p1/p2（仅收 status=="warning"）→ P1 失败被漏计。
        # 现两级桶都计入，与 generate_fix_order 的读取口径一致。
        _e, _w = results["errors"], results["warnings"]
        _p1 = len(_e.get("p1", [])) + len(_w.get("p1", []))
        _p2 = len(_e.get("p2", [])) + len(_w.get("p2", []))
        results["summary"] = {
            "p0_blockers": len(_e.get("p0", [])),
            "p1_warnings": _p1,
            "p2_suggestions": _p2,
            "total_issues": len(_e.get("p0", [])) + _p1 + _p2,
        }

        # BUG 7 配套：把阻断评估结果合并进返回体（此前算完就丢）
        if getattr(self, "last_evaluation", None):
            results["evaluation"] = self.last_evaluation
            # FIX 2026-09-30：顶层 p0_failures/p1_warnings/p2_suggestions 原恒为空数组
            # （09-28 历史门禁"顶层通过、子检查 fail"的表现层残留：09-29 只同步了
            # evaluation，顶层字段仍空），现与 evaluation 同步，供只读顶层的调用方
            # （test-degradation、外部工作流）使用。
            results["p0_failures"] = self.last_evaluation.get("p0_failures", [])
            results["p1_warnings"] = self.last_evaluation.get("p1_warnings", [])
            results["p2_suggestions"] = self.last_evaluation.get("p2_suggestions", [])

    def _evaluate_results(self, checks: Dict, flexible: bool) -> bool:
        """评估检查结果（四档质量债务 + 两种阻断机制；v1 移植）。"""
        p0_failures = []
        p1_warnings = []
        p2_suggestions = []

        # BUG 1 修复：修前 data_integrity_error 全文只有 3 处引用且全是读取、从未赋值，
        # 导致阻断层 0% 生效——20/20 章无条件 passed=True，哪怕有 gate 判 fail。
        block_gates = _BLOCK_GATES
        data_integrity_error = None
        for gname in block_gates:
            g = checks.get(gname)
            if isinstance(g, dict) and g.get("status") == "fail":
                data_integrity_error = (
                    f"{gname}: " + "；".join(str(d) for d in g.get("details", [])[:3]))
                break

        for check_name, check_result in checks.items():
            if check_result.get("status") == "skipped":
                continue  # 跳过项不参与判定

            level = self._classify_gate(check_name)

            if check_result["status"] == "fail":
                if level == "P0":
                    p0_failures.extend(check_result.get("details", []))
                elif level == "P1":
                    p1_warnings.extend(check_result.get("details", []))
                else:
                    p2_suggestions.extend(check_result.get("details", []))

            elif check_result["status"] == "warning":
                if level == "P0":
                    p0_failures.extend(check_result.get("details", []))
                elif level == "P1":
                    p1_warnings.extend(check_result.get("details", []))
                else:
                    p2_suggestions.extend(check_result.get("details", []))

        results = {
            "p0_failures": p0_failures,
            "p1_warnings": p1_warnings,
            "p2_suggestions": p2_suggestions,
            "warnings": p1_warnings + p2_suggestions,
            "errors": p0_failures,
            "data_integrity_error": data_integrity_error,
            "debts_recorded": len(p0_failures) + len(p1_warnings) + len(p2_suggestions),
            "will_block": False,
            "block_reason": None,
        }

        # BUG 7 修复：修前此 results dict 构建后从未返回（函数只 return bool），
        # will_block / block_reason / debts_recorded 整个结构被丢弃。
        # 现挂到 self.last_evaluation，由 check() 合并进返回结果。
        results["will_block"] = bool(data_integrity_error)
        results["block_reason"] = "data_integrity_failure" if data_integrity_error else None
        results["continue_creation"] = not data_integrity_error
        self.last_evaluation = results

        if data_integrity_error:
            return False
        return True

    def _collect_warnings(self, checks: Dict) -> Dict:
        """收集所有警告（按级别分类；v1 移植）。"""
        warnings = []
        p1_warnings = []
        p2_warnings = []

        for check_name, check_result in checks.items():
            if check_result.get("status") == "skipped":
                continue
            if check_result["status"] == "warning":
                detail = "; ".join(str(d) for d in (check_result.get("details") or []))
                detail = detail.strip()
                if not detail:      # BUG 5：跳过空 detail
                    continue
                msg = f"[{self._classify_gate(check_name)}] {detail}"
                warnings.append(msg)
                if self._classify_gate(check_name) == "P1":
                    p1_warnings.append(msg)
                else:
                    p2_warnings.append(msg)

        return {
            "all": warnings,
            "p1": p1_warnings,
            "p2": p2_warnings,
        }

    def _collect_errors(self, checks: Dict) -> Dict:
        """收集所有错误（按级别分类；v1 移植）。

        BUG 2 修复：修前只有 all 与 p0 两个桶，没有 p1/p2。
        而 summary 统计与 generate_fix_order 都读 errors["p1"]/errors["p2"]
        → 字数等 P1/P2 失败既进不了 summary，也进不了修复顺序列表。
        """
        errors = []
        p0_errors, p1_errors, p2_errors = [], [], []

        for check_name, check_result in checks.items():
            if not isinstance(check_result, dict):
                continue
            if check_result.get("status") == "skipped":
                continue
            if check_result["status"] != "fail":
                continue
            level = self._classify_gate(check_name)
            detail = "; ".join(str(d) for d in (check_result.get("details") or []))
            detail = detail.strip()
            if not detail:      # BUG 5：修前 details 为空时产出 "[P2] " 空项
                continue
            msg = f"[{level}] {detail}"
            errors.append(msg)
            {"P0": p0_errors, "P1": p1_errors}.get(level, p2_errors).append(msg)

        return {
            "all": errors,
            "p0": p0_errors,
            "p1": p1_errors,
            "p2": p2_errors,
        }

    # ------------------------------------------------------------------
    # 落盘 / 账本同步 / 事件发射（v1 移植；_sync_to_ledger 修 bug）
    # ------------------------------------------------------------------
    def _save_result(self, result: Dict):
        """保存检查结果（v1 _save_result 移植）。"""
        result_dir = self.project_dir / "reports"
        result_dir.mkdir(parents=True, exist_ok=True)

        result_file = result_dir / f"gate-check-{int(time.time())}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        self._sync_to_ledger(result)
        self._emit_gate_event(result)

    def _emit_gate_event(self, result: Dict):
        """门禁通过时写入事件总线（v1 _emit_gate_event 移植）。

        只在 passed=True 时发射 CHAPTER_GATE_PASSED。失败不发射——
        没有注册对应链，发了只会在 .events/ 里堆积未消费事件污染 status。
        """
        if not result.get("passed"):
            return
        try:
            cf = str(result.get("chapter_file", ""))
            # 从文件名提取章节号：chapter-001.md → 1
            m = re.search(r'(\\d+)', Path(cf).stem)
            chapter = int(m.group(1)) if m else None
            payload = {
                "chapter": chapter,
                "passed": True,
                "mode": result.get("mode", "write"),
                "chapter_file": cf,
                "summary": result.get("summary", {}),
            }
            cmd = [
                sys.executable, "/var/minis/shared/event-bus.py", "emit",
                "--source", self.novel_id,
                "--type", "CHAPTER_GATE_PASSED",
                "--payload", json.dumps(payload, ensure_ascii=False),
                "--quiet",
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                # 契约：诊断信息进 stderr，stdout 保持纯 JSON（修前污染 stdout 导致机器端 JSON.parse 失败）
                print(f"📡 已发射事件 CHAPTER_GATE_PASSED (ch{chapter}) → .events/{self.novel_id}.jsonl", file=sys.stderr)
            else:
                print(f"⚠️ 事件发射失败: {r.stderr.strip()[:200]}", file=sys.stderr)
        except Exception as e:
            # 事件失败绝不能阻断门禁结果输出
            print(f"⚠️ 事件发射异常: {e}", file=sys.stderr)

    def _sync_to_ledger(self, result: Dict):
        """将门禁结果同步到事实账本。

        v1 bug 修复：v1 写的是 `from fact_ledger import FactLedger`，
        但实际文件名是 fact-ledger.py → 恒 ImportError，又被
        `except ImportError: pass` 静默吞掉 → 门禁结果从未同步到账本。
        现改用 novelkit.stores.fact_store.FactStore；同步失败写 stderr 可见，
        不再静默。
        """
        try:
            ledger = FactStore(self.novel_id)
            ledger.add_fact(
                category="gate_check",
                content=f"门禁结果: {'通过' if result['passed'] else '未通过'} | 模式:{result.get('mode', 'write')} | P0阻断:{len(result.get('p0_failures', []))} | P1警告:{len(result.get('p1_warnings', []))}",
                source=result['chapter_file'],
                allow_test=True,
            )
        except Exception as e:
            print(f"⚠️ 同步到 fact-ledger 失败: {e}", file=sys.stderr)

    # ------------------------------------------------------------------
    # 修复顺序（v1 generate_fix_order 移植；CLI --fix-order 用）
    # ------------------------------------------------------------------
    def generate_fix_order(self, result: Dict) -> list:
        """按优先级生成修复建议列表（D2 实测用；v1 移植）。

        优先级规则（来自 TEAM.md §并发故障降级策略）：
        设定矛盾(P0) > 角色掉线(P0) > AI味(P0) > 字数(P1) > 禁用词(P1) > 钩子(P1) > 细节建议(P2)

        输入 result 的 errors/warnings 字段是字符串列表，如 "[P1] 字数不足：..."
        """
        GATE_LABELS = {
            "事实冲突": "fact_consistency",
            "设定矛盾": "fact_consistency",
            "角色掉线": "character_consistency",
            "AI味": "ai_tone",
            "字数不足": "word_count",
            "禁用词": "forbidden_words",
            "钩子": "hook",
            "协议": "protocol",
            "蓝图": "blueprint",
            "一致": "consistency",
            "引用": "reference",
            "实体": "unknown_entities",
            "描述一致": "description_consistency",
            "逻辑": "logic_review",
            "暗线": "darkthread",
        }

        # 同级别次级优先级：TEAM.md §并发故障降级策略 声明的完整链
        # 修前缺陷：sort 只用 priority(1/2/3)，同级别内退化为插入顺序，
        #   即「设定矛盾优先于AI味」从未生效（见 TEAM.md v0.60 D2a）。
        GATE_SUB_PRIORITY = {
            "fact_consistency": 1, "character_consistency": 2, "ai_tone": 3,
            "word_count": 4, "forbidden_words": 5, "hook": 6,
            "protocol": 7, "blueprint": 8, "consistency": 9,
            "reference": 10, "unknown_entities": 11,
            "description_consistency": 12, "logic_review": 13, "darkthread": 14,
        }
        SUB_FALLBACK = 99

        def parse_issue(line: str):
            """从 '[P1] 钩子缺失：...' 提取 level/gate/label/detail"""
            m = re.match(r'\[(P[0-9])\]\s*(.+)', line)
            if not m:
                return None
            level = m.group(1)
            text = m.group(2).strip()
            # 提取 gate：查找 keyword → gate 映射
            gate = None
            for keyword, g in GATE_LABELS.items():
                if keyword in text:
                    gate = g
                    break
            # label = gate关键字 + 冒号后内容（完整描述）
            colon_idx = text.find("：") if "：" in text else text.find(":")
            if colon_idx >= 0:
                label = text[:colon_idx]  # "钩子缺失"
                detail = text[colon_idx+1:].strip()
            else:
                label = text
                detail = ""
            return {"level": level, "gate": gate or "unknown", "label": label, "detail": detail}

        def item_priority(level):
            if "P0" in level: return 1
            if "P1" in level: return 2
            return 3

        fix_list = []
        seen = set()
        for section in ["errors", "warnings"]:
            sec = result.get(section, {})
            for level_key in ["p0", "p1", "p2"]:
                items = sec.get(level_key, [])
                for line in items:
                    parsed = parse_issue(str(line))
                    if not parsed:
                        continue
                    # 修前用 gate 去重：同 gate 的第二个问题被静默丢弃（D2b）。
                    # 改为按 (level, gate, label, detail) 去重，只合并真正的重复行。
                    key = (parsed["level"], parsed["gate"], parsed["label"], parsed["detail"])
                    if key in seen:
                        continue
                    seen.add(key)
                    fix_list.append({
                        "priority": item_priority(parsed["level"]),
                        "sub_priority": GATE_SUB_PRIORITY.get(parsed["gate"], SUB_FALLBACK),
                        "level": parsed["level"],
                        "gate": parsed["gate"],
                        "label": parsed["label"],
                        "detail": parsed["detail"],
                    })
        fix_list.sort(key=lambda x: (x["priority"],
                                     GATE_SUB_PRIORITY.get(x["gate"], SUB_FALLBACK)))
        return fix_list

    # ------------------------------------------------------------------
    # 新架构输出：GateReport（API/程序化调用用；CLI 仍走 v1 形状 dict）
    # ------------------------------------------------------------------
    def report(self, chapter_file: str) -> GateReport:
        """进程内调用入口：返回结构化 GateReport（不落盘、不发射事件）。"""
        try:
            chapter = Chapter.load(chapter_file)
        except Exception as e:
            r = CheckResult(check="__load__", status=CheckStatus.ERROR,
                            severity=Severity.BLOCK,
                            details=[f"无法读取章节文件: {e}"],
                            raw={"status": "error", "details": ["无法读取章节文件"]})
            return GateReport(passed=False, will_block=True,
                              p0_failures=[r], chapter_file=chapter_file,
                              errors=list(r.details))

        ctx = self._make_ctx(chapter)
        names = MODIFY_REQUIRED_GATES if self.mode == "modify" else CHECK_ORDER
        results = [self._run_check(n, ctx) for n in names]

        p0 = [r for r in results
              if r.severity == Severity.BLOCK
              and r.status in (CheckStatus.FAIL, CheckStatus.WARNING, CheckStatus.ERROR)]
        p1 = [r for r in results
              if r.severity == Severity.WARN
              and r.status in (CheckStatus.FAIL, CheckStatus.WARNING, CheckStatus.ERROR)]
        p2 = [r for r in results
              if r.severity == Severity.ADVICE
              and r.status in (CheckStatus.FAIL, CheckStatus.WARNING, CheckStatus.ERROR)]
        errors = [d for r in results if r.status == CheckStatus.ERROR
                  for d in r.details]
        ai_tone = next((r for r in results if r.check == "ai_tone"), None)
        return GateReport(
            passed=not p0,
            will_block=bool(p0),
            p0_failures=p0,
            p1_warnings=p1,
            p2_suggestions=p2,
            tier_1a_score=(ai_tone.score if ai_tone else None),
            chapter_file=chapter_file,
            errors=errors,
        )
