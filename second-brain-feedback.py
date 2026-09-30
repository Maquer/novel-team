#!/usr/bin/env python3
# Version: 0.1.0
"""
second-brain-feedback.py — 第二大脑反馈层（PEV Feedback 架构）

基于 PEV（Plan-Execute-Verify）的反馈控制机制，为第二大脑系统提供：
  1. 确定性传感器（deterministic sensor）— 代码级校验，先于 LLM
  2. 失败分类（failure classifier）— 错误类型识别
  3. 根因分析（root cause analyzer）— 从失败日志提取根因
  4. 回归测试套件（regression suite）— 验证修复是否引入新问题

用法:
  # 对知识卡片做确定性校验
  python3 second-brain-feedback.py --validate-store

  # 对蒸馏管道做回归测试
  python3 second-brain-feedback.py --regression

  # 记录一次失败（来自 train.sh 等上层调用）
  python3 second-brain-feedback.py --log-failure --type distill --reason "评分异常" --detail "score=0"

  # 分类并分析最近的失败
  python3 second-brain-feedback.py --analyze

  # 生成反馈报告
  python3 second-brain-feedback.py --report

  # 健康检查：全量确定性传感器运行
  python3 second-brain-feedback.py --health

PEV 设计原则：
  - 确定性传感器优先（代码/Schema 校验），减少 LLM-as-Judge 的调用
  - 结构化反馈（分类错误），非信号稀释
  - 终止条件显式定义（防环路失控）
  - 过程可观测（Session 级+Step 级日志）
"""

import argparse
import json
import os
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

OBSIDIAN_ROOT = "/var/minis/mounts/loong"
STATE_DIR = "/var/minis/shared/.training-state"
FAIL_LOG = os.path.join(STATE_DIR, "failure-log.json")
REGRESSION_HISTORY = os.path.join(STATE_DIR, "regression-history.json")

# ============================================================
# 确定性传感器集合
# 每个传感器是一个函数，返回 (passed: bool, details: str)
# ============================================================

SENSOR_REGISTRY = {}

def sensor(name):
    def decorator(fn):
        SENSOR_REGISTRY[name] = fn
        return fn
    return decorator


@sensor("store_schema")
def check_store_schema():
    """传感器1: 知识卡片存储 Schema 校验。"""
    store_path = "/var/minis/shared/.knowledge-store.json"
    if not os.path.exists(store_path):
        return (True, "无存储文件，跳过")
    try:
        store = json.load(open(store_path, 'r', encoding='utf-8'))
    except json.JSONDecodeError as e:
        return (False, f"JSON 解析失败: {e}")

    required_fields = ["id", "title", "type", "claims", "status", "created", "score"]
    errors = []
    for i, card in enumerate(store.get("cards", [])):
        for field in required_fields:
            if field not in card:
                errors.append(f"卡片[{i}] 缺少字段: {field}")
        if "score" in card and not isinstance(card["score"], (int, float)):
            errors.append(f"卡片[{i}] score 类型错误: {type(card['score']).__name__}")
        if "status" in card and card["status"] not in ("draft", "approved", "archived", "rejected", "committed"):
            errors.append(f"卡片[{i}] 未知状态: {card['status']}")
    if errors:
        return (False, f"Schema 校验失败 ({len(errors)} 条): {'; '.join(errors[:3])}")
    return (True, f"Schema 校验通过 ({len(store.get('cards',[]))} 张卡片)")


@sensor("claim_integrity")
def check_claim_integrity():
    """传感器2: 知识主张完整性校验。"""
    store_path = "/var/minis/shared/.knowledge-store.json"
    if not os.path.exists(store_path):
        return (True, "无存储文件，跳过")
    store = json.load(open(store_path, 'r', encoding='utf-8'))
    issues = []
    seen_claims = {}
    for card in store.get("cards", []):
        claims = card.get("claims", [])
        if len(claims) == 0:
            issues.append(f"{card.get('title','?')} 零主张")
        for c in claims:
            # 短 claim 全豁免（<12 字符）：distill 抽取时会产出大量标签型 claim
            # （'核心功能'/'开源分层'/'4 个 Tools'/'8 阶段 Loop'/'规则：' 等），
            # 这些是设计使然，不是"证据被截断"。原 <5 阈值太严误报 60+，
            # <12 也误报 45 条。真正需要 fail 的只有：
            #   1. 零主张（完全没内容）
            #   2. 重复主张（同 claim 出现两次）
            #   3. 超长 claim 无终止符（>200 字符且不以 。/。\n/.!/?! 结尾）
            if len(c) > 200 and not c.rstrip().endswith(("。", ".", "！", "!", "?", "?", "\n")):
                issues.append(f"{card.get('title','?')} 超长无终止符: '{c[:40]}...'")
            claim_key = c[:20]
            if claim_key in seen_claims:
                issues.append(f"重复主张: '{c}' (also in {seen_claims[claim_key]})")
            seen_claims[claim_key] = card.get("title", "?")
    if issues:
        return (False, f"主张完整性问题 ({len(issues)} 条): {'; '.join(issues[:3])}")
    return (True, f"主张完整性校验通过")


@sensor("file_path_safety")
def check_file_path_safety():
    """传感器3: 文件路径安全检查（防文件名含 / 崩溃）。"""
    store_path = "/var/minis/shared/.knowledge-store.json"
    if not os.path.exists(store_path):
        return (True, "无存储文件，跳过")
    store = json.load(open(store_path, 'r', encoding='utf-8'))
    dangerous = []
    # 只拦真正会破坏文件路径的字符：null byte、vertical tab、form feed
    # 历史上把 : 也列入导致日期/时间戳型标题（如 "（2026-08-24 21:00）"）大量误报，
    # 但 Obsidian 卡片 title 是数据字段不是文件名，: + 全角括号 + 空格都是合法标题字符。
    # 若需 export 到文件系统，在 export 层做 sanitize，而不是在校验层 fail。
    dangerous_chars = ["\x00", "\x0b", "\x0c"]
    for card in store.get("cards", []):
        title = card.get("title", "")
        if any(c in title for c in dangerous_chars):
            dangerous.append(title)
    if dangerous:
        return (False, f"标题含危险字符 ({len(dangerous)} 条): {'; '.join(dangerous[:3])}")
    return (True, "文件路径安全检查通过")


@sensor("graph_consistency")
def check_graph_consistency():
    """传感器4: 图谱一致性校验。"""
    store_path = "/var/minis/shared/.knowledge-store.json"
    if not os.path.exists(store_path):
        return (True, "无存储文件，跳过")
    store = json.load(open(store_path, 'r', encoding='utf-8'))
    issues = []
    seen_titles = {}
    for card in store.get("cards", []):
        title = card.get("title", "")
        if title in seen_titles:
            issues.append(f"重复标题: '{title}'")
        seen_titles[title] = card
    if issues:
        return (False, f"图谱一致性问题 ({len(issues)} 条): {'; '.join(issues[:3])}")
    return (True, f"图谱一致性校验通过 ({len(store.get('cards',[]))} 张卡片)")


@sensor("auto_learn_state")
def check_auto_learn_state():
    """传感器5: 自动学习状态一致性。"""
    state_path = "/var/minis/shared/.auto-learn-state.json"
    if not os.path.exists(state_path):
        return (True, "无 auto-learn 状态，跳过")
    state = json.load(open(state_path, 'r', encoding='utf-8'))
    issues = []
    stats = state.get("stats", {})
    total = stats.get("total", 0)
    approved = stats.get("approved", 0)
    skipped = stats.get("skipped", 0)
    if approved + skipped != total:
        issues.append(f"统计不一致: approved({approved}) + skipped({skipped}) != total({total})")
    if total == 0 and skipped > 0:
        issues.append(f"异常: total=0 但 skipped={skipped}")
    if issues:
        return (False, f"auto-learn 状态问题 ({len(issues)} 条): {'; '.join(issues[:3])}")
    return (True, f"auto-learn 状态校验通过 (处理 {total} 篇, 批准 {approved})")


@sensor("train_state")
def check_train_state():
    """传感器6: 训练状态文件一致性。"""
    stats_path = os.path.join(STATE_DIR, "stats.json")
    if not os.path.exists(stats_path):
        return (True, "无训练状态，跳过")
    try:
        stats = json.load(open(stats_path, 'r', encoding='utf-8'))
    except:
        return (False, "stats.json 解析失败")
    issues = []
    for field in ["nodes", "links"]:
        val = stats.get(field, "0")
        try:
            int(val)
        except (ValueError, TypeError):
            issues.append(f"{field} 值非数字: {val}")
    if issues:
        return (False, f"训练状态问题: {'; '.join(issues)}")
    return (True, "训练状态校验通过")


@sensor("obsidian_mount")
def check_obsidian_mount():
    """传感器7: Obsidian 挂载状态。"""
    if not os.path.isdir(OBSIDIAN_ROOT):
        return (False, f"Obsidian 未挂载: {OBSIDIAN_ROOT}")
    try:
        note_count = sum(1 for _ in os.scandir(OBSIDIAN_ROOT) if _.is_file())
    except PermissionError:
        return (False, f"Obsidian 挂载但无读取权限: {OBSIDIAN_ROOT}")
    return (True, f"Obsidian 已挂载 (根目录 {note_count} 个文件)")


@sensor("disk_space")
def check_disk_space():
    """传感器8: 磁盘空间检查。"""
    import shutil
    try:
        total, used, free = shutil.disk_usage("/var/minis")
        free_mb = free / (1024 * 1024)
        if free_mb < 100:
            return (False, f"磁盘空间不足: 仅剩 {free_mb:.0f}MB")
        return (True, f"磁盘空间: {free_mb:.0f}MB 可用")
    except Exception as e:
        return (False, f"磁盘检查失败: {e}")


# ============================================================
# 失败分类器
# ============================================================

FAILURE_TYPES = {
    "distill": "蒸馏失败",
    "graph": "图谱构建失败",
    "crossq": "交叉验证失败",
    "blindspot": "认知盲区扫描失败",
    "analytics": "搜索热度统计失败",
    "tag": "标签审计失败",
    "auto_learn": "自动学习失败",
    "dashboard": "仪表盘生成失败",
    "sync": "同步失败",
    "schema": "Schema 校验失败",
    "claim": "主张完整性失败",
    "path": "文件路径安全失败",
    "state": "状态一致性失败",
    "mount": "挂载状态失败",
    "disk": "磁盘空间失败",
}


def classify_failure(error_text, context=""):
    """将错误文本分类到 failure_type。"""
    err_lower = (error_text + " " + context).lower()
    type_scores = {t: 0 for t in FAILURE_TYPES}

    # 关键词映射
    type_keywords = {
        "distill": ["蒸馏", "claim", "extract", "score_card", "classify_type"],
        "graph": ["图谱", "graph", "node", "edge", "wiki_link", "孤立"],
        "crossq": ["交叉", "crossq", "contradict", "矛盾"],
        "blindspot": ["盲区", "blindspot", "shallow", "浅涉"],
        "analytics": ["搜索", "analytics", "hit_rate", "click_rate"],
        "tag": ["标签", "tag", "audit", "命名"],
        "auto_learn": ["auto_learn", "自动学习", "批准", "归档"],
        "dashboard": ["dashboard", "仪表盘", "health"],
        "sync": ["sync", "同步", "minis-to-obsidian"],
        "schema": ["schema", "字段", "missing", "缺少字段", "type error"],
        "claim": ["claim", "主张", "integrity", "重复主张", "过短"],
        "path": ["path", "安全", "危险字符", "崩溃", "filename"],
        "state": ["state", "一致性", "统计不一致", "json 解析"],
        "mount": ["mount", "挂载", "权限", "permission"],
        "disk": ["disk", "磁盘", "空间不足"],
    }
    for ft, keywords in type_keywords.items():
        for kw in keywords:
            if kw.lower() in err_lower:
                type_scores[ft] += 2

    # 兜底：traceback 中的文件名
    for ft in FAILURE_TYPES:
        if ft in err_lower:
            type_scores[ft] += 1

    best_type = max(type_scores, key=type_scores.get)
    if type_scores[best_type] == 0:
        return "unknown"
    return best_type


# ============================================================
# 失败日志管理
# ============================================================

def _load_fail_log():
    if os.path.exists(FAIL_LOG):
        try:
            return json.load(open(FAIL_LOG, 'r', encoding='utf-8'))
        except:
            return []
    return []


def _save_fail_log(entries):
    os.makedirs(os.path.dirname(FAIL_LOG) or '.', exist_ok=True)
    json.dump(entries, open(FAIL_LOG, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def log_failure(failure_type, reason, detail="", step=""):
    """记录一次失败事件。"""
    entries = _load_fail_log()
    entry = {
        "ts": datetime.now().isoformat(),
        "type": failure_type,
        "type_label": FAILURE_TYPES.get(failure_type, failure_type),
        "reason": reason,
        "detail": detail[:500],  # 截断
        "step": step,
        "resolved": False,
    }
    entries.append(entry)
    _save_fail_log(entries)
    return entry


def _resolve_past_failures(step=""):
    """某 step 现在通过了，把之前同 step 未 resolved 的失败记录标记为已解决。

    没有这个机制的话，历史失败会永远堆在 failure-log.json 里，
    每次训练都把它们重复提取到 error-patterns，制造"466 条需人工"的假象。
    """
    if not step:
        return
    entries = _load_fail_log()
    changed = False
    for e in entries:
        if e.get("step") == step and not e.get("resolved"):
            e["resolved"] = True
            e["resolved_at"] = datetime.now().isoformat()
            changed = True
    if changed:
        _save_fail_log(entries)


# ============================================================
# 根因分析
# ============================================================

def analyze_failures(limit=30):
    """分析最近的失败，找出根因模式。"""
    entries = _load_fail_log()[-limit:]
    if not entries:
        return {"summary": "无失败记录", "type_counts": {}, "recent": [], "patterns": []}

    # 按类型分组
    type_counts = {}
    for e in entries:
        t = e.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # 按根因分组（reason 前 20 字归一）
    reason_groups = {}
    for e in entries:
        r = e.get("reason", "unknown")[:30]
        reason_groups.setdefault(r, {"count": 0, "types": set(), "entries": []})
        reason_groups[r]["count"] += 1
        reason_groups[r]["types"].add(e.get("type", "unknown"))
        reason_groups[r]["entries"].append(e)

    # 按次数排序
    sorted_reasons = sorted(reason_groups.items(), key=lambda x: x[1]["count"], reverse=True)

    # 发现模式
    patterns = []
    for reason, data in sorted_reasons:
        if data["count"] >= 3:
            patterns.append({
                "pattern": reason,
                "count": data["count"],
                "types": sorted(data["types"]),
                "first_seen": data["entries"][0].get("ts", ""),
                "last_seen": data["entries"][-1].get("ts", ""),
            })

    return {
        "summary": f"{len(entries)} 条失败，{len(type_counts)} 种类型",
        "type_counts": type_counts,
        "recent": entries[-10:],
        "patterns": patterns[:5],
        "total_unresolved": sum(1 for e in entries if not e.get("resolved")),
    }


# ============================================================
# 回归测试套件
# ============================================================

def run_regression_tests(json_output=False):
    """运行确定性传感器的回归测试套件。"""
    results = []
    passed = 0
    failed = 0
    skipped = 0

    if not json_output:
        print("\n" + "═" * 50)
        print("  🔬 回归测试套件 — 确定性传感器")
        print("═" * 50 + "\n")

    for sensor_name, sensor_fn in sorted(SENSOR_REGISTRY.items()):
        start_ts = datetime.now()
        try:
            ok, detail = sensor_fn()
            elapsed = (datetime.now() - start_ts).total_seconds()
            status = "✅" if ok else "❌"
            results.append({
                "sensor": sensor_name,
                "passed": ok,
                "detail": detail,
                "elapsed_ms": round(elapsed * 1000),
            })
            if not json_output:
                print(f"  {status} [{sensor_name}] {detail}")
            if ok:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            elapsed = (datetime.now() - start_ts).total_seconds()
            results.append({
                "sensor": sensor_name,
                "passed": False,
                "detail": f"异常: {str(e)[:100]}",
                "elapsed_ms": round(elapsed * 1000),
            })
            if not json_output:
                print(f"  💥 [{sensor_name}] 异常: {str(e)[:100]}")
            failed += 1

    if not json_output:
        print("\n" + "─" * 50)
        print(f"  总计: {len(results)} 个传感器 | ✅ {passed} 通过 | ❌ {failed} 失败")
        if failed == 0:
            print("  🟢 所有确定性传感器通过 — 系统结构健康")
        else:
            print(f"  🔴 {failed} 个传感器失败 — 需关注")
            for r in results:
                if not r["passed"]:
                    log_failure("schema" if "store" in r["sensor"] else "state",
                               r["detail"], step=r["sensor"])
        # 通过 → 把之前该 step 未 resolved 的失败标记为 resolved
        # 否则历史失败会永远堆在 failure-log.json 里，每次训练都被重复提取
        for r in results:
            if r["passed"]:
                _resolve_past_failures(step=r["sensor"])
        print()
    return results


# ============================================================
# 健康检查（全量）
# ============================================================

def health_check(json_output=False):
    """全量健康检查：运行所有确定性传感器。"""
    if not json_output:
        print(f"\n{'═'*50}")
        print(f"  🏥 反馈层健康检查 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'═'*50}\n")

    results = run_regression_tests(json_output=json_output)

    # 分析历史失败
    print("─" * 50)
    analysis = analyze_failures()
    if analysis.get("total_unresolved", 0) > 0:
        print(f"\n  ⚠️ 未解决失败: {analysis['total_unresolved']} 条")
        for p in analysis.get("patterns", [])[:3]:
            print(f"     🔁 {p['pattern']} (出现 {p['count']} 次, 类型: {', '.join(p['types'])})")

    # 类型分布
    print(f"\n  📊 失败类型分布:")
    for t, c in sorted(analysis.get("type_counts", {}).items(), key=lambda x: x[1], reverse=True):
        bar = "█" * min(c, 20)
        print(f"     {FAILURE_TYPES.get(t, t):20s} {c:>3} {bar}")

    return results


# ============================================================
# 报告生成
# ============================================================

def generate_report(json_output=False):
    """生成反馈层报告。"""
    results = run_regression_tests(json_output=json_output)
    analysis = analyze_failures()

    # 计算反馈健康分
    sensor_pass = sum(1 for r in results if r["passed"])
    sensor_total = len(results)
    sensor_rate = sensor_pass / sensor_total if sensor_total > 0 else 0

    # 历史失败趋势
    unresolved = analysis.get("total_unresolved", 0)
    recent_count = len(analysis.get("recent", []))

    report = {
        "ts": datetime.now().isoformat(),
        "feedback_health": round(sensor_rate * 100),
        "sensor_summary": {
            "total": sensor_total,
            "passed": sensor_pass,
            "failed": sensor_total - sensor_pass,
            "rate": round(sensor_rate, 2),
        },
        "failure_summary": {
            "total": recent_count,
            "unresolved": unresolved,
            "type_counts": analysis.get("type_counts", {}),
            "patterns": analysis.get("patterns", []),
        },
        "sensors": results,
    }

    print(f"\n{'═'*50}")
    print(f"  📋 反馈层报告 — {report['ts']}")
    print(f"{'═'*50}\n")
    print(f"  反馈健康分: {report['feedback_health']}/100")
    print(f"  传感器: {sensor_pass}/{sensor_total} 通过")
    print(f"  未解决失败: {unresolved} 条")
    if analysis.get("patterns"):
        print(f"\n  🔄 失败模式:")
        for p in analysis["patterns"][:3]:
            print(f"    🔁 {p['pattern'][:40]} (出现{p['count']}次, {', '.join(p['types'])})")
    print()
    return report


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='第二大脑反馈层 (PEV Feedback)')
    parser.add_argument('--validate-store', action='store_true', help='校验知识卡片存储')
    parser.add_argument('--regression', action='store_true', help='运行回归测试套件')
    parser.add_argument('--health', action='store_true', help='全量健康检查')
    parser.add_argument('--log-failure', action='store_true', help='记录一次失败')
    parser.add_argument('--type', help='失败类型 (--log-failure 时用)')
    parser.add_argument('--reason', help='失败原因 (--log-failure 时用)')
    parser.add_argument('--detail', help='失败详情 (--log-failure 时用)')
    parser.add_argument('--step', help='失败步骤 (--log-failure 时用)')
    parser.add_argument('--analyze', action='store_true', help='分析失败')
    parser.add_argument('--report', action='store_true', help='生成反馈报告')
    parser.add_argument('--list-sensors', action='store_true', help='列出所有传感器')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')
    parser.add_argument('--classify', help='将文本分类为失败类型')
    args = parser.parse_args()

    if args.list_sensors:
        print("确定性传感器列表:")
        for name in sorted(SENSOR_REGISTRY.keys()):
            print(f"  📡 {name}")
        return

    if args.validate_store:
        ok, detail = SENSOR_REGISTRY["store_schema"]()
        if args.json:
            print(json.dumps({"passed": ok, "detail": detail}, ensure_ascii=False))
        else:
            print(f"{'✅' if ok else '❌'} {detail}")
        return

    if args.regression:
        results = run_regression_tests(json_output=args.json)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    if args.health:
        results = health_check(json_output=args.json)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    if args.log_failure:
        if not args.type or not args.reason:
            print("❌ --log-failure 需要 --type 和 --reason")
            return
        entry = log_failure(args.type, args.reason, args.detail or "", args.step or "")
        if args.json:
            print(json.dumps(entry, ensure_ascii=False, indent=2))
        else:
            print(f"✅ 失败已记录: [{entry['type_label']}] {entry['reason']}")
        return

    if args.analyze:
        analysis = analyze_failures()
        if args.json:
            print(json.dumps(analysis, ensure_ascii=False, indent=2))
        else:
            print(analysis["summary"])
            if analysis.get("patterns"):
                print("\n失败模式:")
                for p in analysis["patterns"]:
                    print(f"  🔁 {p['pattern'][:40]} (出现{p['count']}次, 类型: {', '.join(p['types'])})")
            print(f"\n未解决: {analysis.get('total_unresolved', 0)} 条")
        return

    if args.report:
        report = generate_report(json_output=args.json)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    if args.classify:
        result = classify_failure(args.classify)
        print(result)
        return

    # 默认：健康检查
    health_check()


if __name__ == "__main__":
    main()
