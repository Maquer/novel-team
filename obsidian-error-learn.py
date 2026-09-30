#!/usr/bin/env python3
# Version: 0.1.0
"""
obsidian-error-learn.py — 错误模式学习（Error Pattern Learning）

三 层架构：
  第一层：错误模式库 — 从日志/daily log/训练记录中提取结构化错误模式
  第二层：三问判断机制 — 格式问题？方案唯一？质量确定提升？→ 自动/人工
  第三层：自动修复边界 — 格式类自动修，逻辑/架构/安全类人工介入

用法:
  # 扫描 daily log 和训练日志提取错误模式
  python3 obsidian-error-learn.py --scan

  # 三问判断：传入一个错误场景
  python3 obsidian-error-learn.py --judge --text "文件名含中文导致路径错误"

  # 查看已提取的错误模式库
  python3 obsidian-error-learn.py --patterns

  # 查看近期错误趋势
  python3 obsidian-error-learn.py --trends

  # JSON 输出（供上层调用）
  python3 obsidian-error-learn.py --scan --json
  python3 obsidian-error-learn.py --patterns --json
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

DAILY_LOG_DIR = "/var/minis/memory"
TRAIN_LOG_DIR = "/var/minis/shared/.training-state"
ERROR_STORE = "/var/minis/shared/.error-patterns.json"

# ============================================================
# 错误类型分类
# ============================================================
ERROR_TYPES = {
    "schema": {
        "label": "Schema/结构",
        "icon": "📐",
        "auto_fixable": True,
        "regexes": [
            r"缺少字段|r"r"缺少.*字段", r"JSON 解析失败", r"schema", r"字段.*错误", r"格式错误",
            r"字段名.*不一致", r"类型错误", r"type error",
        ]
    },
    "path": {
        "label": "文件路径",
        "icon": "📁",
        "auto_fixable": True,
        "regexes": [
            r"路径.*错误", r"文件.*不存在", r"文件名.*中文", r"dangerous", r"危险字符",
            r"no such file", r"file not found", r"cannot.*open",
        ]
    },
    "data": {
        "label": "数据质量",
        "icon": "📊",
        "auto_fixable": True,
        "regexes": [
            r"评分.*异常", r"score.*异常", r"zero.*score", r"空.*结果", r"empty",
            r"数据.*缺失", r"null", r"undefined", r"重复.*数据", r"duplicate",
        ]
    },
    "count": {
        "label": "计数/统计",
        "icon": "🔢",
        "auto_fixable": True,
        "regexes": [
            r"计数.*错误", r"count.*error", r"total.*mismatch", r"总数.*不一致",
            r"计数器.*bug", r"count.*bug",
        ]
    },
    "claim": {
        "label": "主张/内容",
        "icon": "💭",
        "auto_fixable": False,
        "regexes": [
            r"主张.*过短", r"主张.*重复", r"claim.*too.*short", r"claim.*duplicate",
            r"内容.*太短", r"content.*too.*short", r"主张完整性问题",
        ]
    },
    "dependency": {
        "label": "依赖/环境",
        "icon": "🔗",
        "auto_fixable": False,
        "regexes": [
            r"依赖.*缺失", r"module.*not.*found", r"import.*error", r"缺少.*包",
            r"package.*not.*found", r"版本.*不兼容", r"incompatible",
        ]
    },
    "arch": {
        "label": "架构/逻辑",
        "icon": "🏗️",
        "auto_fixable": False,
        "regexes": [
            r"架构", r"设计.*缺陷", r"逻辑.*错误", r"设计.*问题",
            r"业务逻辑", r"逻辑.*不一致", r"设计.*不合理",
        ]
    },
    "security": {
        "label": "安全",
        "icon": "🔒",
        "auto_fixable": False,
        "regexes": [
            r"安全", r"permission", r"unauthorized", r"token.*expired", r"认证.*失败",
        ]
    },
    "hallucination": {
        "label": "幻觉/失真",
        "icon": "👻",
        "auto_fixable": False,
        "regexes": [
            r"幻觉", r"hallucination", r"错误.*推断", r"虚假", r"fabrication",
            r"编造", r"虚假.*信息",
        ]
    },
    "loop": {
        "label": "死循环/卡死",
        "icon": "🔄",
        "auto_fixable": True,
        "regexes": [
            r"死循环", r"infinite.*loop", r"卡死", r"hang", r"timeout",
            r"响应超时", r"无响应",
        ]
    },
}

# 预编译正则（模块加载时一次编译，扫描时直接匹配）
for _cfg in ERROR_TYPES.values():
    _cfg["_compiled"] = [re.compile(r, re.IGNORECASE) for r in _cfg["regexes"]]
    del _cfg["regexes"]


# ============================================================
# 第一层：错误模式库
# ============================================================

def _load_error_store():
    if os.path.exists(ERROR_STORE):
        try:
            with open(ERROR_STORE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "patterns": [],
        "stats": {"total_errors": 0, "auto_fixed": 0, "manual_intervene": 0,
                   "fixed": 0, "total_scans": 0},
        "sessions": [],
    }


def _save_error_store(store):
    os.makedirs(os.path.dirname(ERROR_STORE) or '.', exist_ok=True)
    with open(ERROR_STORE, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def _classify_error(text):
    """根据文本内容分类错误类型，返回匹配的 ERROR_TYPE key 列表。"""
    matches = []
    for etype, cfg in ERROR_TYPES.items():
        for regex in cfg["_compiled"]:
            if regex.search(text):
                matches.append(etype)
                break
    return matches


def _scan_log_file(filepath):
    """扫描单个日志文件，提取错误条目。"""
    errors = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
    except Exception:
        return errors

    lines = text.split('\n')
    for line in lines:
        line_stripped = line.strip()
        if len(line_stripped) < 5:
            continue
        # 检测错误信号
        error_signals = ['错误', '失败', 'error', 'fail', 'bug', '异常', '问题', 'warning',
                         'failed', 'exception', 'timeout', 'missing', 'invalid', 'crash',
                         '🐛', '⚠️', '❌', '🔴']
        is_error = any(s in line_stripped for s in error_signals)
        if is_error:
            # 提取上下文（前一行 + 当前行）
            errors.append({
                "text": line_stripped[:200],
                "file": os.path.basename(filepath),
                "ts": datetime.now().isoformat(),
            })
    return errors


def scan_errors(force=False):
    """扫描所有日志源，提取错误模式。

    重要：daily log 是主观写作（描述性文字），不是客观失败记录。
    早期版本把 daily log 全文当错误来源，导致 500 条 patterns 中
    90% 是误报（比如"修复错误模式学习脚本"被当成错误发生）。
    真正的失败记录在 feedback.py 的 failure-log.json 里。
    """
    store = _load_error_store()
    all_errors = []

    # 1. ⚠️ daily log 已跳过（避免把"讨论错误"的文字当成错误发生）
    # 如需从 daily log 提取真实错误，应只扫专门段落（如 ## 错误处理 / ## Bug 修复）
    # 而非全文匹配关键词。

    # 2. 扫描训练日志
    if os.path.exists(TRAIN_LOG_DIR):
        for f in os.listdir(TRAIN_LOG_DIR):
            full = os.path.join(TRAIN_LOG_DIR, f)
            if os.path.isfile(full) and f.endswith('.json'):
                all_errors.extend(_scan_log_file(full))

    # 3. 扫描反馈层日志（唯一权威失败记录源）
    feedback_log = os.path.join(TRAIN_LOG_DIR, "failure-log.json")
    if os.path.exists(feedback_log):
        all_errors.extend(_scan_log_file(feedback_log))

    # 分类
    for err in all_errors:
        err["types"] = _classify_error(err["text"])

    # 去重：相同文本不重复记录
    seen_texts = {p["text"] for p in store.get("patterns", [])}
    new_patterns = []
    for err in all_errors:
        if err["text"] not in seen_texts:
            new_patterns.append(err)
            seen_texts.add(err["text"])

    store["patterns"].extend(new_patterns)

    # 限制总条目（保留最近500条）
    if len(store["patterns"]) > 500:
        store["patterns"] = store["patterns"][-500:]

    # 更新统计
    auto_fixable = sum(1 for p in store["patterns"]
                       if any(ERROR_TYPES[t]["auto_fixable"] for t in p.get("types", [])))
    store["stats"]["total_errors"] = len(store["patterns"])
    store["stats"]["auto_fixable"] = auto_fixable
    store["stats"]["total_scans"] = store["stats"].get("total_scans", 0) + 1

    _save_error_store(store)
    return store


# ============================================================
# 第二层：三问判断机制
# ============================================================

def three_questions(text):
    """
    三问判断：
    Q1: 修复是否只动格式？ → 是：可自动修复
    Q2: 方案是否唯一？ → 否：需人工判断
    Q3: 质量是否确定提升？ → 不确定：需人工判断
    """
    results = {}

    # Q1: 是否纯格式问题？
    format_keywords = ['格式', '拼写', 'typo', '空格', '缩进', '换行', '大小写',
                       '标点', '语法', '引号', '括号', '斜杠', '文件名', '路径',
                       'rename', 'replace', '替换', 'character']
    results["q1_format_only"] = any(kw in text.lower() for kw in format_keywords)

    # Q2: 方案是否唯一？（模糊匹配唯一性）
    # 如果文本中提到多种选择或"方案"，通常不唯一
    multi_solution_signals = ['方案', '方案', '选项', '选择', '可以.*也可以',
                               'A.*B', '要么.*要么', '或者']
    results["q2_unique_solution"] = not any(re.search(s, text, re.IGNORECASE) for s in multi_solution_signals)

    # Q3: 质量是否确定提升？（检测确定性语言）
    certain_language = ['确定', '肯定', '必然', '一定', '明确', '明显', '一定',
                        'definite', 'certain', 'surely']
    uncertain_language = ['可能', '也许', '不一定', '或许', '不确定', '有待', '需要确认',
                          '也许', 'maybe', 'perhaps', 'possibly', 'uncertain']
    certain_count = sum(1 for kw in certain_language if kw in text.lower())
    uncertain_count = sum(1 for kw in uncertain_language if kw in text.lower())
    results["q3_quality_certain"] = certain_count > uncertain_count

    # 综合判定
    if results["q1_format_only"] and results["q2_unique_solution"] and results["q3_quality_certain"]:
        results["decision"] = "auto_fix"
        results["reason"] = "Q1+Q2+Q3 全部通过 → 纯格式问题，方案唯一，质量确定提升，可自动修复"
    elif results["q1_format_only"] and results["q2_unique_solution"]:
        results["decision"] = "auto_fix"
        results["reason"] = "纯格式问题 + 方案唯一 → 可自动修复（Q3 不确定但格式类风险低）"
    elif not results["q1_format_only"] and results["q2_unique_solution"]:
        results["decision"] = "human_review"
        results["reason"] = "非格式问题 → 需人工判断方案选择"
    else:
        results["decision"] = "human_review"
        results["reason"] = "存在不确定性 → 需人工介入"

    # 自动修复分类
    if results["decision"] == "auto_fix":
        etypes = _classify_error(text)
        if "arch" in etypes or "security" in etypes or "hallucination" in etypes:
            results["decision"] = "human_review"
            results["reason"] = "涉及架构/安全/幻觉 → 强制人工介入"

    return results


def judge(text):
    """对外接口：三问判断 + 分类。"""
    result = three_questions(text)
    result["error_types"] = _classify_error(text)
    result["auto_fixable_types"] = [t for t in result["error_types"] if ERROR_TYPES[t]["auto_fixable"]]
    result["manual_review_types"] = [t for t in result["error_types"] if not ERROR_TYPES[t]["auto_fixable"]]
    return result


# ============================================================
# 第三层：自动修复执行（格式类自动修，其他人工介入）
# ============================================================

def auto_fix(text):
    """
    对格式类错误执行自动修复。
    返回 (fixed_text, changes_list)
    """
    changes = []
    fixed = text

    # 修复文件名中的危险字符
    dangerous_chars = ['/', '\\', ':']
    for ch in dangerous_chars:
        if ch in fixed:
            fixed = fixed.replace(ch, '-')
            changes.append(f"替换危险字符 '{ch}' → '-'")

    # 修复多余空格
    if '  ' in fixed:
        fixed = re.sub(r' {2,}', ' ', fixed)
        changes.append("清理多余空格")

    # 修复首尾空白
    if fixed != fixed.strip():
        fixed = fixed.strip()
        changes.append("清理首尾空白")

    return fixed, changes


# ============================================================
# 模式库查询与趋势分析
# ============================================================

def list_patterns(filter_type=None, limit=20):
    """列出已提取的错误模式。"""
    store = _load_error_store()
    patterns = store.get("patterns", [])
    if filter_type:
        patterns = [p for p in patterns if filter_type in p.get("types", [])]
    return patterns[:limit]


def get_trends(days=30):
    """分析近期错误趋势。"""
    store = _load_error_store()
    patterns = store.get("patterns", [])

    # 按类型统计
    type_counts = {}
    for p in patterns:
        for t in p.get("types", []):
            type_counts[t] = type_counts.get(t, 0) + 1

    # 按时间统计（按天）
    daily_counts = {}
    for p in patterns:
        ts = p.get("ts", "")[:10]
        if ts:
            daily_counts[ts] = daily_counts.get(ts, 0) + 1

    return {
        "total": len(patterns),
        "by_type": type_counts,
        "by_day": dict(sorted(daily_counts.items())[-7:]),  # 最近7天
        "top_issues": sorted(
            [(p["text"][:80], p.get("types", [])) for p in patterns],
            key=lambda x: x[0], reverse=True
        )[:10],
        "auto_fix_rate": round(
            store["stats"].get("auto_fixable", 0) / max(len(patterns), 1) * 100, 1
        ),
    }


# ============================================================
# 输出格式化
# ============================================================

def _print_patterns(patterns):
    print(f"\n  📋 错误模式库（共 {len(patterns)} 条）")
    print("  " + "─" * 48)
    for i, p in enumerate(patterns[:20]):
        types_str = " ".join(f"{ERROR_TYPES[t]['icon']}{t}" for t in p.get("types", [])[:3])
        text_preview = p["text"][:60].replace('\n', ' ')
        print(f"\n  [{i+1}] {types_str}")
        print(f"       {text_preview}")
        print(f"       📄 {p.get('file','?')} | {p.get('ts','?')[:16]}")
    if len(patterns) > 20:
        print(f"\n  ... 还有 {len(patterns)-20} 条")


def _print_trends(trends):
    print(f"\n  📈 错误趋势分析")
    print("  " + "─" * 48)
    print(f"\n  总错误数: {trends['total']}")
    print(f"  自动修复率: {trends['auto_fix_rate']}%")

    print("\n  按类型:")
    for t, count in sorted(trends.get("by_type", {}).items(), key=lambda x: -x[1]):
        cfg = ERROR_TYPES.get(t, {})
        icon = cfg.get("icon", "❓")
        auto = "✅" if cfg.get("auto_fixable") else "👤"
        print(f"    {icon} {t:15s}  {count:3d}  {auto}")

    print("\n  最近7天:")
    for day, count in trends.get("by_day", {}).items():
        bar = "█" * min(count, 20)
        print(f"    {day}  {bar} {count}")


# ============================================================
# 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='第二大脑错误模式学习')
    parser.add_argument('--scan', action='store_true', help='扫描日志提取错误模式')
    parser.add_argument('--judge', action='store_true', help='三问判断模式')
    parser.add_argument('--text', type=str, help='传入待判断的错误文本')
    parser.add_argument('--patterns', action='store_true', help='列出错误模式')
    parser.add_argument('--trends', action='store_true', help='分析错误趋势')
    parser.add_argument('--filter-type', type=str, help='按类型过滤错误模式')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')
    args = parser.parse_args()

    if args.scan:
        store = scan_errors()
        stats = store["stats"]
        if args.json:
            print(json.dumps({
                "stats": stats,
                "patterns_count": len(store["patterns"]),
            }, ensure_ascii=False, indent=2))
        else:
            print("=" * 50)
            print(f"  🐛 错误模式扫描完成")
            print("=" * 50)
            print(f"\n  📊 总错误: {stats['total_errors']} 条")
            print(f"  ✅ 可自动修复: {stats['auto_fixable']} 条")
            print(f"  👤 需人工介入: {stats['total_errors'] - stats['auto_fixable']} 条")
            print(f"  📋 扫描次数: {stats['total_scans']}")

    if args.judge:
        if not args.text:
            print("❌ 请通过 --text 传入错误描述")
            sys.exit(1)
        result = judge(args.text)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("=" * 50)
            print(f"  ⚖️  三问判断 — {args.text[:50]}")
            print("=" * 50)
            print(f"\n  Q1 纯格式问题?  {'✅ 是' if result['q1_format_only'] else '❌ 否'}")
            print(f"  Q2 方案唯一?    {'✅ 是' if result['q2_unique_solution'] else '❌ 否'}")
            print(f"  Q3 质量确定提升? {'✅ 是' if result['q3_quality_certain'] else '❌ 否'}")
            print(f"\n  🎯 决策: {'🤖 自动修复' if result['decision'] == 'auto_fix' else '👤 人工介入'}")
            print(f"     {result['reason']}")
            if result['error_types']:
                print(f"\n  错误类型: {' '.join(result['error_types'])}")

    if args.patterns:
        patterns = list_patterns(filter_type=args.filter_type)
        if args.json:
            print(json.dumps(patterns, ensure_ascii=False, indent=2))
        else:
            _print_patterns(patterns)

    if args.trends:
        trends = get_trends()
        if args.json:
            print(json.dumps(trends, ensure_ascii=False, indent=2))
        else:
            _print_trends(trends)

    if not any([args.scan, args.judge, args.patterns, args.trends]):
        parser.print_help()


if __name__ == "__main__":
    main()