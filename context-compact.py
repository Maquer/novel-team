#!/usr/bin/env python3
# Version: 0.1.0
"""
context-compact.py — 上下文压缩建议器（非自动执行）

基于 BeataI 上下文工程六技工具箱（2026-08-20）。
读取 session-status + 最近 daily log + 工具调用统计，
输出「保留/丢弃/摘要」三段压缩建议。

用法:
  python3 context-compact.py                # 默认：分析当前会话
  python3 context-compact.py --turns 20     # 只看最近 N 轮
  python3 context-compact.py --json         # 结构化输出（供 minis-cli 调用）
  python3 context-compact.py --inject       # 输出可直接注入的压缩提示词

设计约束（iSH 环境）：
  - 无法直接读取模型 token 计数器（App 层功能）
  - 用轮次 × 平均 tool 调用量估算上下文占用（偏差 ±30%）
  - 压缩建议 = 给人看的，不是给机器执行的

压缩保留/丢弃清单（BeataI 原文直译）：
  ✅ 保留：决策+原因 / 约束 / 精确标识符（文件路径/ID/函数名） / 未解决问题
  ⚠️ 降级：原始工具输出 → 结论摘要（"尝试 X → 失败，因为 Y"）
  ❌ 丢弃：原始输出 / 无关客套 / 死胡同（仅保留一行）
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

STATUS_SCRIPT = "/var/minis/shared/session-status.py"
DAILY_LOG = os.path.expanduser("/var/minis/memory/{}.md".format(
    datetime.now().strftime("%Y-%m-%d")))

# 压缩触发阈值（估算轮次，非真实 token）
COMPACT_THRESHOLD_TURNS = 30
COMPACT_HEAVY_THRESHOLD_TURNS = 60


def _estimate_ctx(usage):
    turns = usage.get("turns", 0)
    tools = usage.get("total_tool_calls", 0)
    if turns <= COMPACT_THRESHOLD_TURNS:
        level = "normal"
    elif turns <= COMPACT_HEAVY_THRESHOLD_TURNS:
        level = "warn"   # 70% 等效
    else:
        level = "critical"  # 85% 等效
    return {"turns": turns, "tool_calls": tools, "level": level}


def _daily_log_summary(max_blocks=6):
    """最近 N 个 memory block（按 ### 分隔）作为工作集"""
    if not os.path.exists(DAILY_LOG):
        return ""
    try:
        with open(DAILY_LOG, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception:
        return ""

    blocks = re.split(r"\n(?=### )", raw)
    recent = blocks[-max_blocks:]
    lines = []
    for b in recent:
        header = b.split("\n", 1)[0][:60]
        body_len = len(b)
        lines.append(f"[{body_len}B] {header}")
    return "\n".join(lines)


def analyze(turns_limit=20, json_out=False):
    """返回压缩建议 dict"""
    usage = {}
    try:
        import subprocess
        r = subprocess.run(
            ["python3", STATUS_SCRIPT, "--json"],
            capture_output=True, text=True, timeout=10
        )
        usage = json.loads(r.stdout) if r.stdout else {}
    except Exception:
        pass

    ctx = _estimate_ctx(usage)
    log_summary = _daily_log_summary()

    suggestions = []
    if ctx["level"] == "critical":
        suggestions.append({
            "type": "compact_now",
            "action": "建议立即压缩",
            "detail": f"当前 {ctx['turns']} 轮，估算超 85% 阈值",
            "retain": ["决策+原因（为什么选 A 不选 B）", "精确文件路径/ID/函数名",
                        "未解决问题清单", "用户明确约束"],
            "downgrade": ["工具原始输出 → 一行结论",
                          "重复文件读取 → 结论摘要",
                          "调试过程 → '尝试X→失败因为Y'"],
            "discard": ["客套/过渡句", "无关工具定义引用",
                        "已解决的中间错误细节"],
        })
    elif ctx["level"] == "warn":
        suggestions.append({
            "type": "monitor",
            "action": "接近压缩阈值",
            "detail": f"当前 {ctx['turns']} 轮，约 70% 占用。建议整理工作集笔记。",
        })
    else:
        suggestions.append({
            "type": "normal",
            "action": "上下文正常",
            "detail": f"当前 {ctx['turns']} 轮，无需压缩。",
        })

    # 外部存储器健康检查（对齐六技#3）
    external_mem = _check_external_memory()

    report = {
        "timestamp": datetime.now().isoformat(),
        "context": ctx,
        "daily_log_recent": log_summary,
        "external_memory": external_mem,
        "suggestions": suggestions,
    }

    if json_out:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)

    return report


def _check_external_memory():
    """检查 plan.md / notes.md 是否存在（六技#3）"""
    checks = {}
    for label, path in [
        ("plan.md", "/var/minis/workspace/plan.md"),
        ("notes.md", "/var/minis/workspace/notes.md"),
        ("daily_log", DAILY_LOG),
        ("L3_graph", "/var/minis/memory/L3-knowledge-graph.md"),
    ]:
        checks[label] = "exists" if os.path.exists(path) else "missing"
    return checks


def _print_human(r):
    print("=" * 52)
    print(f"  上下文压缩建议器  |  {r['timestamp'][:16]}")
    print("=" * 52)
    ctx = r["context"]
    bar = {"normal": "░░░░░░░░░░",
           "warn":   "███████░░░",
           "critical":"██████████"}[ctx["level"]]
    print(f"  轮次: {ctx['turns']:>3}  工具调用: {ctx['tool_calls']}")
    print(f"  占用估算: [{bar}] {ctx['level']}")
    print()

    for sug in r["suggestions"]:
        print(f"  ▶ {sug['action']}  ({sug['detail']})")
        if "retain" in sug:
            print("  ✅ 保留:")
            for item in sug["retain"]:
                print(f"      + {item}")
            print("  ⚠️ 降级为摘要:")
            for item in sug["downgrade"]:
                print(f"      ~ {item}")
            print("  ❌ 丢弃:")
            for item in sug["discard"]:
                print(f"      - {item}")

    ext = r.get("external_memory", {})
    if ext:
        print()
        print("  📁 外部存储器状态:")
        for label, status in ext.items():
            mark = "✅" if status == "exists" else "❌"
            print(f"      {mark} {label}")
    print()


def inject_prompt(report=None):
    """输出可粘贴到会话末尾的压缩提示词"""
    if report is None:
        report = analyze(json_out=True)
        return  # json mode 已打印

    prompt = """上下文压缩指令（粘贴到对话末尾）：

---
⚠️ 执行上下文压缩。保留以下内容：
- 所有已做出的决策及其原因
- 约束条件和精确标识符（文件路径/ID/函数名）
- 未解决的问题和开放问题

降级为摘要：
- 原始工具输出 → 结论（如："读取 X → 发现 Y"）
- 调试过程 → 一行"尝试X → 失败，因为Y"

丢弃：
- 客套话/过渡句
- 已解决的中间错误细节
- 重复引用的内容

请按上述规则总结当前会话，输出压缩后的工作记忆摘要。
---"""
    print(prompt)


def main():
    ap = argparse.ArgumentParser(description="上下文压缩建议器")
    ap.add_argument("--turns", type=int, default=20, help="只分析最近 N 轮")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--inject", action="store_true", help="输出压缩提示词")
    args = ap.parse_args()

    if args.inject:
        inject_prompt()
    else:
        analyze(turns_limit=args.turns, json_out=args.json)


if __name__ == "__main__":
    main()
