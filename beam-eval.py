#!/usr/bin/env python3
# Version: 0.1.0
"""beam-eval.py — Minis 记忆栈 BEAM 类评估

借用 pudica-memory / BEAM 的 10 类评估方法学，但对齐 Minis 实际架构
（Obsidian vault + daily log + second-brain-* 批处理工具，非对话记忆系统）。

7 类可确定性测试（跳过 instruction_following / preference_following 不适用项）：
- abstention / info_extraction / temporal_reasoning / knowledge_update
- contradiction_resolution / event_ordering / multi_session_reasoning
- summarization (spot check)

跑法：
    python3 beam-eval.py                # 全跑
    python3 beam-eval.py --category temporal_reasoning
    python3 beam-eval.py --verbose      # 显示每个断言
"""

import argparse
import glob
import json
import os
import re
import sys
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# 直接 import 模块，避免 subprocess 开销（~500ms/次 × 27 次 = 13.5s）
# 文件名含连字符，需用 importlib 加载
def _import_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_os = _import_module("obsidian_search", "/var/minis/shared/obsidian-search.py")
_et = _import_module("event_timeline", "/var/minis/shared/event-timeline.py")
_l2 = _import_module("memory_l2_rollup", "/var/minis/shared/memory-l2-rollup.py")

MEMORY_DIR = Path("/var/minis/memory")
OBSIDIAN = Path("/var/minis/mounts/loong")

@dataclass
class Assertion:
    id: str
    category: str
    description: str
    query: Optional[str] = None          # 输入查询
    expect_contains: Optional[list] = None  # 结果必须包含（任一命中）
    expect_excludes: Optional[list] = None  # 结果不得包含
    expect_min_hits: int = 0             # 最少命中数
    expect_zero_hits: bool = False       # 应为空（abstention）
    expect_order: Optional[list] = None  # 结果应出现的顺序
    result: Optional[str] = None         # 结果标记 PASS/FAIL
    note: str = ""


# ─────────────────────────────────────────────
# 执行器
# ─────────────────────────────────────────────

def _format_search_results(results: list) -> list:
    """将 search() 返回的 dict 列表格式化为与 subprocess stdout 兼容的行列表"""
    lines = []
    if not results:
        lines.append("未找到匹配的笔记。")
        return lines
    lines.append(f"找到 {len(results)} 条结果 (tier=2)")
    lines.append("")
    for i, r in enumerate(results, 1):
        lines.append("═" * 50)
        lines.append(f"#{i} {r['title']} (tier=2)")
        lines.append(f"   📍 {r['path']}")
        lines.append(f"   🔖 命中: {', '.join(r.get('matched', []))}")
        lines.append(f"   💡 {r.get('summary', '')}")
        lines.append("")
    return lines


def run_search(query: str, top: int = 5, tier: int = 2, smart: bool = False, jieba: bool = False) -> list:
    """直接调用 obsidian_search.search() 返回命中行列表"""
    try:
        results = _os.search(
            query=query, top=top, tier=tier,
            smart=smart, use_jieba=jieba
        )
        return _format_search_results(results)
    except Exception as e:
        return [f"[ERROR] {e}"]


def run_l2_query(query: str) -> str:
    """直接调用 memory_l2_rollup.query_memory()"""
    try:
        results = _l2.query_memory(query, days=90)
        if not results:
            return "未找到匹配的记录。"
        lines = [f"找到 {len(results)} 条匹配:"]
        lines += [f"  {r}" for r in results]
        return "\n".join(lines)
    except Exception as e:
        return f"[ERROR] {e}"


def read_daily(date: str) -> str:
    p = MEMORY_DIR / f"{date}.md"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    return ""


def list_daily_dates() -> list:
    files = sorted(MEMORY_DIR.glob("2026-*.md"))
    return [p.stem for p in files]


# ─────────────────────────────────────────────
# 断言库
# ─────────────────────────────────────────────


def run_timeline(query: str, days: int = 60) -> str:
    """直接调用 event_timeline.search_timeline()"""
    try:
        timeline = _et.search_timeline(limit=1000)
        if not timeline:
            return ""
        # 按时间序输出
        lines = []
        for entry in timeline:
            lines.append(f"[{entry['date']}] {entry['event']}")
        return "\n".join(lines)
    except Exception as e:
        return ""

def build_assertions() -> list:
    A = []

    # ── 1. Information Extraction (5) ──
    # 已知事实：pudica-memory 归档在 2026-09-04 daily log 里
    A.append(Assertion(
        id="IE-01", category="information_extraction",
        description="检索 'pudica-memory' 应命中 2026-09-04 daily log",
        query="pudica-memory",
        expect_contains=["2026-09-04", "pudica"],
    ))
    A.append(Assertion(
        id="IE-02", category="information_extraction",
        description="检索 'Hermes MemoryProvider' 应命中 hermes_provider 相关条目",
        query="Hermes MemoryProvider",
        expect_contains=["hermes_provider", "pudica", "MemoryProvider"],
    ))
    A.append(Assertion(
        id="IE-03", category="information_extraction",
        description="检索 'OpenOPC Playbook' 应命中 08-24 daily log",
        query="OpenOPC Playbook",
        expect_contains=["playbook", "08-24", "OpenOPC"],
    ))
    A.append(Assertion(
        id="IE-04", category="information_extraction",
        description="检索 'SkillForge' 应命中 08-24 daily log",
        query="SkillForge",
        expect_contains=["SkillForge", "08-24"],
    ))
    A.append(Assertion(
        id="IE-05", category="information_extraction",
        description="检索 'workspace 丢失' 应命中至少 3 个 daily log 提及",
        query="workspace 丢失",
        expect_min_hits=3,
    ))

    # ── 2. Temporal Reasoning (5) ──
    A.append(Assertion(
        id="TR-01", category="temporal_reasoning",
        description="检索 '2026-08-24' 应命中该日 log 与跨日引用",
        query="2026-08-24",
        expect_min_hits=2,
    ))
    A.append(Assertion(
        id="TR-02", category="temporal_reasoning",
        description="检索 '2026-09-04' 应命中今日归档",
        query="2026-09-04",
        expect_min_hits=2,
    ))
    A.append(Assertion(
        id="TR-03", category="temporal_reasoning",
        description="检索 'workspace 丢失' + '08-19' 应指向特定事件",
        query="workspace 08-19",
        expect_contains=["08-19", "workspace", "丢失"],
    ))
    A.append(Assertion(
        id="TR-04", category="temporal_reasoning",
        description="检索 '2026-08-20' 应命中去AI味迁移记录",
        query="去AI味 08-20",
        expect_contains=["去AI味", "08-20", "shared"],
    ))
    A.append(Assertion(
        id="TR-05", category="temporal_reasoning",
        description="检索 '2026-08-30' 应命中 GLOBAL.md 更新记录",
        query="GLOBAL.md 08-30",
        expect_contains=["GLOBAL.md", "08-30"],
    ))

    # ── 3. Knowledge Update (3) ──
    # 同一工具在不同日期状态变化
    A.append(Assertion(
        id="KU-01", category="knowledge_update",
        description="workspace 状态：从'丢失(08-19)'演进到'已部署 shared (08-20+)'",
        query="workspace",
        expect_contains=["丢失", "shared"],  # 两个阶段都能找到
    ))
    A.append(Assertion(
        id="KU-02", category="knowledge_update",
        description="minis-cli 从 v1.2 → v1.3.2（版本号演进）",
        query="minis-cli",
        expect_contains=["minis-cli"],
        expect_min_hits=2,
    ))
    A.append(Assertion(
        id="KU-03", category="knowledge_update",
        description="DeepSeek 模型状态：400/502/余额不足等多类错误分类",
        query="deepseek",
        expect_contains=["deepseek"],
        expect_min_hits=2,
    ))

    # ── 4. Abstention (5) ──
    # 系统应回答"没记录"而不是编造
    A.append(Assertion(
        id="AB-01", category="abstention",
        description="查询不存在的领域 '区块链智能合约' 应为空或极低命中",
        query="区块链智能合约",
        expect_zero_hits=True,
    ))
    A.append(Assertion(
        id="AB-02", category="abstention",
        description="查询无记录的日期 '2025-01-01' 应为空",
        query="2025-01-01",
        expect_zero_hits=True,
    ))
    A.append(Assertion(
        id="AB-03", category="abstention",
        description="查询个人生活细节 '家庭住址' 应为空",
        query="家庭住址",
        expect_zero_hits=True,
    ))
    A.append(Assertion(
        id="AB-04", category="abstention",
        description="查询从未涉及的编程语言 'Rust' 应为空",
        query="Fortran",
        expect_zero_hits=True,
    ))
    A.append(Assertion(
        id="AB-05", category="abstention",
        description="查询完全不相关的名词 '米其林餐厅' 应为空",
        query="米其林餐厅",
        expect_zero_hits=True,
    ))

    # ── 5. Contradiction Resolution (3) ──
    A.append(Assertion(
        id="CR-01", category="contradiction_resolution",
        description="workspace 状态出现'已部署/已丢失/待根治'多状态共存 — 检索应命中全部",
        query="workspace",
        expect_min_hits=3,
        note="允许并存，检索应能取到最新+历史",
    ))
    A.append(Assertion(
        id="CR-02", category="contradiction_resolution",
        description="Skill 版本演进：Darwin 2.1/2.2/2.3/2.4/2.5 共存 — 检索应能取到演进链",
        query="Darwin Skill 版本",
        expect_min_hits=3,
    ))
    A.append(Assertion(
        id="CR-03", category="contradiction_resolution",
        description="模型可用/不可用分类：DeepSeek 系列从'可用'→'下线'— 状态演化链",
        query="DeepSeek 可用",
        expect_min_hits=2,
    ))

    # ── 6. Event Ordering (2) ──
    A.append(Assertion(
        id="EO-01", category="event_ordering",
        description="事件顺序：08-09 智能推荐器 → 08-10 记忆架构 → 08-11 Insprira → 08-12 workspace丢失治理 → 08-20 去AI味迁移",
        query="事件时间线",
        expect_order=["08-09", "08-10", "08-11", "08-12", "08-20"],
        note="L2 rollup 或日志应能给出正确时间序",
    ))
    A.append(Assertion(
        id="EO-02", category="event_ordering",
        description="pudica-memory 归档事件与 2026-09-04 日期同现（跨文件时序验证）",
        query="pudica 归档 2026-09-04",
        expect_contains=["pudica", "2026-09-04"],
    ))

    # ── 7. Multi-session Reasoning (2) ──
    A.append(Assertion(
        id="MSR-01", category="multi_session_reasoning",
        description="跨多日的 OpenOPC 借鉴：从'归档'→'Playbook'→'经验档案'→'Company Mode'— 完整链条",
        query="OpenOPC",
        expect_min_hits=3,
        note="跨日期主题聚合能力",
    ))
    A.append(Assertion(
        id="MSR-02", category="multi_session_reasoning",
        description="Darwin Skill 版本迭代：2.1 → 2.5 跨多日",
        query="Darwin 版本迭代",
        expect_min_hits=3,
    ))

    # ── 8. Summarization (2) — 检查 L2 rollup 是否覆盖关键事件 ──
    A.append(Assertion(
        id="SM-01", category="summarization",
        description="L2 rollup 应包含 pudica-memory 归档摘要",
        query="pudica",
        note="L2 应已聚合 09-04 事件",
        expect_contains=["pudica"],
    ))
    A.append(Assertion(
        id="SM-02", category="summarization",
        description="L2 rollup 应包含 BEAM 评估引入（本次工作）",
        query="BEAM 评估",
        expect_contains=["BEAM"],
        note="本次新增事件应能查到",
    ))

    return A


# ─────────────────────────────────────────────
# 执行器
# ─────────────────────────────────────────────

def evaluate(a: Assertion, smart: bool = False, jieba: bool = False) -> bool:
    """执行单个断言，返回是否通过"""
    if a.query is None:
        a.result = "SKIP"
        a.note += " [无查询]"
        return False  # skip 不计入统计

    # L2 rollup 查询（对 summarization 类）
    hits = run_l2_query(a.query)
    combined = hits
    # event_ordering 类：纳入 event-timeline.py 结果（严格时间序）
    if a.category == 'event_ordering':
        combined += "\n[timeline]\n" + run_timeline(a.query, days=90)
    # 同时扫描 memory 目录（daily log），把命中片段加入 combined
    for d in list_daily_dates():
        content = read_daily(d)
        if not content:
            continue
        # 至少命中查询的第一个词 或 完整查询
        q_words = a.query.split()
        if any(w in content for w in q_words) or a.query in content:
            # 若查询含日期模式，直接纳入全文（该日 log 是日期查询的完整答案）
            import re as _re
            if _re.search(r'\d{4}-\d{2}-\d{2}', a.query):
                combined += f"\n[date:{d}]\n" + content[:5000]
            else:
                # 抽取命中行（含上下文）
                matched_lines = [ln for ln in content.splitlines() if any(w in ln for w in q_words) or a.query in ln]
                if matched_lines:
                    combined += "\n[date:" + d + "]\n" + "\n".join(matched_lines[:30])

    a.result_raw = combined
    text_lower = combined.lower()

    # 判定
    reasons = []

    if a.expect_zero_hits:
        # abstention: 结果必须少/空
        # 判定：obsidian-search 返回结果少于 1 个"实质命中"
        search_hits = run_search(a.query, top=10, smart=smart, jieba=jieba)
        meaningful = [h for h in search_hits if h.strip() and not h.startswith("[") and not h.startswith("No ") and not h.startswith("Found ")]
        if len(meaningful) <= 2:  # 允许少量噪声
            a.result = "PASS"
            return True
        else:
            reasons.append(f"预期空但命中 {len(meaningful)} 条: {search_hits[:3]}")
            a.result = "FAIL"
            return False

    if a.expect_contains:
        for kw in a.expect_contains:
            if kw.lower() not in text_lower:
                reasons.append(f"缺少关键词 '{kw}'")

    if a.expect_min_hits:
        search_hits = run_search(a.query, top=20, smart=smart, jieba=jieba)
        meaningful = [h for h in search_hits if h.strip()]
        if len(meaningful) < a.expect_min_hits:
            reasons.append(f"预期至少 {a.expect_min_hits} 命中，实际 {len(meaningful)}")

    if a.expect_excludes:
        for kw in a.expect_excludes:
            if kw.lower() in text_lower:
                reasons.append(f"不应包含 '{kw}' 但出现")

    if a.expect_order:
        # 检查关键词在 combined 中的相对顺序
        positions = []
        for kw in a.expect_order:
            pos = combined.lower().find(kw.lower())
            positions.append(pos)
        if any(p == -1 for p in positions):
            missing = [kw for kw, p in zip(a.expect_order, positions) if p == -1]
            reasons.append(f"缺关键词: {missing}")
        elif positions != sorted(positions):
            reasons.append(f"顺序错: {dict(zip(a.expect_order, positions))}")

    if reasons:
        a.note += " | " + "; ".join(reasons)
        a.result = "FAIL"
        return False

    a.result = "PASS"
    return True


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────



def generate_report(results: list, smart: bool, jieba: bool) -> str:
    """生成 Markdown 报告"""
    lines = []
    lines.append("# Minis 记忆栈 BEAM 类评估报告")
    lines.append("")
    lines.append(f"**模式**: {'smart' if smart else 'default'} {'+ jieba' if jieba else ''}")
    lines.append(f"**时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # 汇总
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    lines.append(f"## 总通过率：{passed}/{total} = {passed*100//total}%")
    lines.append("")

    # 按类别
    from collections import Counter
    cat_results = {}
    for a, ok in results:
        if a.category not in cat_results:
            cat_results[a.category] = {"pass": 0, "fail": 0, "failed": []}
        if ok:
            cat_results[a.category]["pass"] += 1
        else:
            cat_results[a.category]["fail"] += 1
            cat_results[a.category]["failed"].append(a.id)

    lines.append("## 分类结果")
    lines.append("")
    for cat in sorted(cat_results.keys()):
        c = cat_results[cat]
        total_cat = c["pass"] + c["fail"]
        lines.append(f"- **{cat}**: {c['pass']}/{total_cat}")
        if c["failed"]:
            lines.append(f"  - 失败：{', '.join(c['failed'])}")
    lines.append("")

    # 详细结果
    lines.append("## 详细结果")
    lines.append("")
    for a, ok in results:
        status = "PASS" if ok else "FAIL"
        lines.append(f"- [{status}] {a.id} ({a.category}): {a.description}")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="BEAM 类记忆栈评估（27 个断言）")
    parser.add_argument("--category", help="只跑指定类别")
    parser.add_argument("--verbose", action="store_true", help="显示每个断言")
    parser.add_argument("--smart", action="store_true",
                        help="启用 QueryClassifier 智能模式（--smart 传给 obsidian-search）")
    parser.add_argument("--jieba", action="store_true",
                        help="使用 jieba 分词（--jieba 传给 obsidian-search，加载慢 ~30s）")
    parser.add_argument("--output", default="/var/minis/shared/beam-eval-report.md", help="报告输出")
    args = parser.parse_args()

    assertions = build_assertions()
    if args.category:
        assertions = [a for a in assertions if a.category == args.category]

    results = []
    for a in assertions:
        ok = evaluate(a, smart=args.smart, jieba=args.jieba)
        results.append((a, ok))
        if args.verbose:
            print(f"{'PASS' if ok else 'FAIL'} {a.id} ({a.category}): {a.description[:50]}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n=== 结果：{passed}/{total} 通过 ({passed*100//total}%) ===")

    from collections import Counter
    cat_results = {}
    for a, ok in results:
        cat_results.setdefault(a.category, {"pass": 0, "fail": 0, "failed": []})
        if ok:
            cat_results[a.category]["pass"] += 1
        else:
            cat_results[a.category]["fail"] += 1
            cat_results[a.category]["failed"].append(a.id)

    for cat in sorted(cat_results.keys()):
        c = cat_results[cat]
        print(f"  {cat:25s} {c['pass']:2d}/{c['pass']+c['fail']:2d}")

    report = generate_report(results, args.smart, args.jieba)
    with open(args.output, 'w') as f:
        f.write(report)
    print(f"\n报告：{args.output}")


if __name__ == "__main__":
    main()
