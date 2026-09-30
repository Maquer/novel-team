#!/usr/bin/env python3
# Version: 0.1.0
"""
Schema Learning — 自动学习高频记忆模式，发现 schema 漂移
=========================================================

借鉴 MindMemOS (mindscale-noah) 的 schema learning pipeline：自动识别
高频记忆模式，而非用固定模板。obsidian-distill.py 用固定 KNOWLEDGE_TYPES
（concept/tool/method/principle/example/framework）+ scope（global/local），
但实际数据中 70/72 卡片是 type=memory（不存在的类型），说明分类器对
session-commit 输入失效。

本工具分析现有卡片，发现：
1. 字段覆盖率：哪些字段总是/从不填充
2. 类型分布异常：哪些类型被错用（如 memory 不在 schema 里）
3. 标签熵：标签冗余度，哪些标签应升级为字段
4. Claim 模式：claim 前缀/长度分布，发现可结构化的重复模式
5. Schema 漂移：卡片有 schema 外字段
6. 改进建议：基于数据提出 schema 修订

用法:
    # 全量分析（默认）
    python3 obsidian-schema-learn.py

    # 只分析某维度
    python3 obsidian-schema-learn.py --fields
    python3 obsidian-schema-learn.py --types
    python3 obsidian-schema-learn.py --tags
    python3 obsidian-schema-learn.py --claims
    python3 obsidian-schema-learn.py --drift

    # JSON 输出
    python3 obsidian-schema-learn.py --json

    # 应用修复（给 memory 卡片重新分类，清理元数据标签）
    python3 obsidian-schema-learn.py --apply

    # 干跑（打印会做什么，不落盘）
    python3 obsidian-schema-learn.py --apply --dry-run
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

KNOWLEDGE_STORE = "/var/minis/shared/.knowledge-store.json"
SCHEMA_LOG = "/var/minis/shared/.schema-learn-log.jsonl"

# distill.py 的固定 schema（硬编码，用于对比）
KNOWN_TYPES = {"concept", "tool", "method", "principle", "example", "framework", "memory"}
KNOWN_FIELDS = {
    "id", "title", "type", "type_label", "icon", "claims", "tags", "source",
    "created", "status", "score", "content_preview", "l0_abstract", "l1_overview",
    "l0_tokens", "l1_tokens", "evidence", "scope", "scope_label", "scope_icon",
    "tier_tokens", "content_md", "merged_into", "merged_at", "merge_reason",
    "archived_at", "archived_reason", "dream_linked_at",
}

# session-commit 卡片的 claim 前缀模式（用于发现可结构化的模式）
CLAIM_PREFIX_PATTERNS = {
    "action": re.compile(r'^(修复|新增|删除|升级|迁移|归档|落地|集成|部署|重构|优化|完成|测试|验证|修复)'),
    "metric": re.compile(r'^(\d+[/\.]?\d*\s*[分%]|score[:：]\s*\d|PASS|FAIL)'),
    "evidence": re.compile(r'^(✅|❌|⚠️|🔴|🟢|🟡)'),
    "timestamp": re.compile(r'\d{4}-\d{2}-\d{2}'),
    "negation": re.compile(r'^(未|无|缺|没有|不|无法|不能|失败)'),
    "reference": re.compile(r'^(借鉴|参考|来源|引|see|ref)'),
    "quote": re.compile(r'^[>\-•]'),
    "code": re.compile(r'^[a-zA-Z_]+\.[a-zA-Z_]+'),  # file.py 风格
}


def load_store():
    if not os.path.exists(KNOWLEDGE_STORE):
        return {"cards": [], "audit_log": []}
    try:
        with open(KNOWLEDGE_STORE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"cards": [], "audit_log": []}


def save_store(store):
    with open(KNOWLEDGE_STORE, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def log_event(event_type, details):
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event_type,
        **details,
    }
    with open(SCHEMA_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


# ─────────────────────────────────────────────
# 分析维度
# ─────────────────────────────────────────────
def analyze_fields(cards):
    """字段覆盖率：每个字段在多少卡片中出现"""
    field_count = Counter()
    field_examples = defaultdict(list)
    for c in cards:
        for k in c.keys():
            field_count[k] += 1
            if len(field_examples[k]) < 2:
                val = c[k]
                if isinstance(val, str):
                    field_examples[k].append(val[:80])
                elif isinstance(val, list):
                    field_examples[k].append(f"[{len(val)} items]")
                else:
                    field_examples[k].append(str(val)[:80])

    total = len(cards) if cards else 1
    coverage = []
    for field, count in field_count.most_common():
        coverage.append({
            "field": field,
            "count": count,
            "coverage": round(count / total, 3),
            "in_schema": field in KNOWN_FIELDS,
            "examples": field_examples[field],
        })
    return {
        "total_cards": len(cards),
        "total_fields": len(field_count),
        "coverage": coverage,
        "schema_fields_missing_data": [
            f for f in KNOWN_FIELDS if field_count.get(f, 0) == 0
        ],
        "non_schema_fields": [
            {"field": c["field"], "count": c["count"]}
            for c in coverage if not c["in_schema"]
        ],
    }


def analyze_types(cards):
    """类型分布：发现无效类型 + 类型失衡"""
    type_dist = Counter(c.get("type", "(none)") for c in cards)
    invalid_types = {t: n for t, n in type_dist.items() if t not in KNOWN_TYPES}

    # 按类型看 scope 分布
    type_scope = defaultdict(lambda: Counter())
    for c in cards:
        t = c.get("type", "(none)")
        s = c.get("scope", "(none)")
        type_scope[t][s] += 1

    return {
        "distribution": dict(type_dist),
        "invalid_types": invalid_types,
        "type_scope_matrix": {t: dict(s) for t, s in type_scope.items()},
        "recommendations": _type_recommendations(type_dist, invalid_types),
    }


def _type_recommendations(type_dist, invalid_types):
    """基于类型分布给出建议"""
    recs = []
    total = sum(type_dist.values()) or 1
    if invalid_types:
        recs.append({
            "issue": "invalid-type",
            "detail": f"{sum(invalid_types.values())} 张卡片用了不存在的类型: {list(invalid_types.keys())}",
            "action": "重新运行 classify_type() 或手动修正",
            "severity": "high",
        })
    # memory 类型占主导 → 分类器对 session-commit 输入失效
    if type_dist.get("memory", 0) / total > 0.5:
        recs.append({
            "issue": "classifier-failure",
            "detail": f"memory 类型占 {type_dist['memory']}/{total} ({type_dist['memory']/total*100:.0f}%)，分类器对 session-commit 输入失效",
            "action": "给 session-commit 卡片加 'subtype' 字段（decision/insight/discovery/preference/error），替代通用 memory 类型",
            "severity": "high",
        })
    # 单一类型主导
    for t, n in type_dist.most_common(1):
        if n / total > 0.8 and t != "memory":
            recs.append({
                "issue": "type-dominance",
                "detail": f"{t} 类型占 {n/total*100:.0f}%，分类缺乏多样性",
                "action": "检查 classify_type() 的关键词权重",
                "severity": "medium",
            })
    if not recs:
        recs.append({"issue": "none", "detail": "类型分布正常", "severity": "low"})
    return recs


def analyze_tags(cards):
    """标签熵：冗余度 + 高频标签 + 候选字段"""
    tag_counter = Counter()
    card_tag_sets = []
    for c in cards:
        tags = c.get("tags", [])
        card_tag_sets.append(set(tags))
        for t in tags:
            tag_counter[t] += 1

    total_tags = sum(tag_counter.values())
    unique_tags = len(tag_counter)
    redundancy = 1 - (unique_tags / total_tags) if total_tags else 0

    # 高频标签（应升级为字段）
    high_freq = []
    for tag, count in tag_counter.most_common():
        if count / len(cards) > 0.3 if cards else False:
            is_metadata = bool(re.match(r'\d{4}-\d{2}-\d{2}', tag)) or tag in ('session-commit',)
            high_freq.append({
                "tag": tag,
                "count": count,
                "ratio": round(count / len(cards), 3) if cards else 0,
                "suggest_as_field": is_metadata,
                "field_name": "date" if re.match(r'\d{4}-\d{2}-\d{2}', tag) else ("source_type" if tag == "session-commit" else None),
                "note": "元数据标签，应转为字段" if is_metadata else "高频内容标签，可考虑作为主分类",
            })

    # 只用一次的标签（长尾，可能噪音）
    long_tail = [{"tag": t, "count": 1} for t, n in tag_counter.most_common() if n == 1]

    return {
        "total_tags": total_tags,
        "unique_tags": unique_tags,
        "redundancy_ratio": round(redundancy, 3),
        "high_frequency": high_freq,
        "long_tail_count": len(long_tail),
        "long_tail_sample": long_tail[:10],
        "recommendations": [
            {
                "issue": "metadata-as-tag",
                "detail": f"session-commit/日期类标签 {sum(h['count'] for h in high_freq if h['suggest_as_field'])} 次出现，应转为字段",
                "action": "清理 tags 中 session-commit 和日期，迁移到 source_type/date 字段",
                "severity": "high",
            }
        ] if any(h["suggest_as_field"] for h in high_freq) else [],
    }


def analyze_claims(cards):
    """Claim 模式：前缀分类 + 长度分布 + 可结构化模式"""
    all_claims = []
    for c in cards:
        for claim in c.get("claims", []):
            all_claims.append(claim)

    if not all_claims:
        return {"total_claims": 0}

    # 前缀模式分类
    pattern_count = Counter()
    unmatched = []
    for claim in all_claims:
        matched = False
        for pname, pregex in CLAIM_PREFIX_PATTERNS.items():
            if pregex.search(claim):
                pattern_count[pname] += 1
                matched = True
                break
        if not matched:
            unmatched.append(claim[:60])

    # 长度分布
    lengths = [len(c) for c in all_claims]
    avg_len = sum(lengths) / len(lengths)

    return {
        "total_claims": len(all_claims),
        "avg_claims_per_card": round(len(all_claims) / len(cards), 2) if cards else 0,
        "pattern_distribution": dict(pattern_count),
        "unmatched_count": len(unmatched),
        "unmatched_sample": unmatched[:10],
        "length": {
            "avg": round(avg_len, 1),
            "min": min(lengths),
            "max": max(lengths),
            "median": sorted(lengths)[len(lengths)//2],
        },
        "recommendations": _claim_recommendations(pattern_count, len(all_claims)),
    }


def _claim_recommendations(pattern_count, total):
    recs = []
    if not total:
        return recs
    # action 类占主导 → 可结构化为 {action, target, result}
    if pattern_count.get("action", 0) / total > 0.3:
        recs.append({
            "issue": "action-dominant",
            "detail": f"action 类 claim 占 {pattern_count['action']/total*100:.0f}%，可结构化为 {{action, target, result}} 三元组",
            "action": "考虑在 schema 加 action/target/result 子字段，替代自由文本 claim",
            "severity": "medium",
        })
    # metric 类 → 可提取为 score 字段
    if pattern_count.get("metric", 0) / total > 0.15:
        recs.append({
            "issue": "metric-extractable",
            "detail": f"metric 类 claim 占 {pattern_count['metric']/total*100:.0f}%，含分数/百分比，可提取为结构化 metric 字段",
            "action": "加 metric 字段 {name, value, unit}，从 claim 中自动提取",
            "severity": "medium",
        })
    # evidence 类 → 可提取为 status 字段
    if pattern_count.get("evidence", 0) / total > 0.15:
        recs.append({
            "issue": "evidence-extractable",
            "detail": f"evidence 类 claim（✅/❌/⚠️ 前缀）占 {pattern_count['evidence']/total*100:.0f}%，可提取为 verification 字段",
            "action": "加 verification 字段 {status: pass/fail/warn, detail}",
            "severity": "low",
        })
    return recs


def analyze_drift(cards):
    """Schema 漂移：卡片有 schema 外字段"""
    drift_fields = Counter()
    drift_examples = defaultdict(list)
    for c in cards:
        for k in c.keys():
            if k not in KNOWN_FIELDS:
                drift_fields[k] += 1
                if len(drift_examples[k]) < 3:
                    val = c[k]
                    drift_examples[k].append(str(val)[:80] if not isinstance(val, (list, dict)) else f"[{type(val).__name__}]")

    return {
        "drift_fields": [
            {"field": f, "count": n, "examples": drift_examples[f]}
            for f, n in drift_fields.most_common()
        ],
        "drift_count": len(drift_fields),
    }


def analyze_scope(cards):
    """Scope 分布：global/local 缺失率"""
    scope_dist = Counter(c.get("scope", "(none)") for c in cards)
    total = len(cards) or 1
    missing = scope_dist.get("(none)", 0)
    return {
        "distribution": dict(scope_dist),
        "missing_rate": round(missing / total, 3),
        "recommendations": [
            {
                "issue": "scope-missing",
                "detail": f"{missing}/{total} ({missing/total*100:.0f}%) 卡片无 scope",
                "action": "回填 scope（基于 source 关键词或 title 分类）",
                "severity": "high" if missing / total > 0.3 else "medium",
            }
        ] if missing / total > 0.1 else [],
    }


# ─────────────────────────────────────────────
# 修复动作
# ─────────────────────────────────────────────
def _reclassify_memory(card):
    """给 memory 类型卡片推断 subtype"""
    text = ' '.join([
        card.get("title", ""),
        ' '.join(card.get("claims", [])),
        card.get("l1_overview", ""),
        card.get("content_preview", ""),
    ]).lower()

    # 按关键词推断 subtype
    if any(w in text for w in ["修复", "bug", "错误", "失败", "踩坑", "问题"]):
        return "error"
    if any(w in text for w in ["决策", "决定", "选择", "批准", "审批"]):
        return "decision"
    if any(w in text for w in ["偏好", "喜欢", "习惯", "约定", "偏好"]):
        return "preference"
    if any(w in text for w in ["归档", "记录", "档案", "工具", "项目"]):
        return "discovery"
    if any(w in text for w in ["洞察", "发现", "意识到", "启发", "借鉴"]):
        return "insight"
    return "log"  # 默认


def _clean_metadata_tags(card):
    """清理 session-commit 和日期标签，迁移到字段"""
    tags = card.get("tags", [])
    cleaned = []
    extracted_date = None
    extracted_source_type = None
    for t in tags:
        if re.match(r'\d{4}-\d{2}-\d{2}', t):
            extracted_date = t
        elif t == "session-commit":
            extracted_source_type = "session-commit"
        else:
            cleaned.append(t)
    return cleaned, extracted_date, extracted_source_type


def apply_fixes(store, dry_run=False):
    """应用 schema 修复：重分类 memory + 清理元数据标签 + 回填 scope"""
    cards = store.get("cards", [])
    changes = {
        "reclassified": 0,
        "tags_cleaned": 0,
        "scope_backfilled": 0,
        "details": [],
    }
    for c in cards:
        changed = False
        detail = {"id": c.get("id", ""), "title": c.get("title", "")[:50]}

        # 1. 重分类 memory 类型
        if c.get("type") == "memory":
            subtype = _reclassify_memory(c)
            if not dry_run:
                c["type"] = "memory"
                c["subtype"] = subtype
                c["type_label"] = f"记忆·{subtype}"
            detail["subtype"] = subtype
            changes["reclassified"] += 1
            changed = True

        # 2. 清理元数据标签
        cleaned, date, source_type = _clean_metadata_tags(c)
        if len(cleaned) != len(c.get("tags", [])):
            if not dry_run:
                c["tags"] = cleaned
                if date:
                    c["memory_date"] = date
                if source_type:
                    c["source_type"] = source_type
            detail["removed_tags"] = len(c.get("tags", [])) - len(cleaned)
            detail["date_extracted"] = date
            detail["source_type_extracted"] = source_type
            changes["tags_cleaned"] += 1
            changed = True

        # 3. 回填缺失 scope
        if not c.get("scope"):
            text = (c.get("title", "") + " " + c.get("content_preview", "")).lower()
            source = c.get("source", "").lower()
            if "daily-log" in source or "session" in source:
                scope = "local"
            elif any(w in text for w in ["原理", "原则", "方法", "通用", "框架"]):
                scope = "global"
            else:
                scope = "local"  # session-commit 默认 local
            if not dry_run:
                c["scope"] = scope
                c["scope_label"] = "全局诊断" if scope == "global" else "局部干预"
                c["scope_icon"] = "🌐" if scope == "global" else "📍"
            detail["scope_backfilled"] = scope
            changes["scope_backfilled"] += 1
            changed = True

        if changed:
            changes["details"].append(detail)

    if not dry_run and changes["details"]:
        save_store(store)
        log_event("apply-fixes", {
            "reclassified": changes["reclassified"],
            "tags_cleaned": changes["tags_cleaned"],
            "scope_backfilled": changes["scope_backfilled"],
        })
    return changes


# ─────────────────────────────────────────────
# 报告
# ─────────────────────────────────────────────
def build_report(store, args):
    cards = store.get("cards", [])
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_cards": len(cards),
    }
    if args.fields or args.all:
        report["fields"] = analyze_fields(cards)
    if args.types or args.all:
        report["types"] = analyze_types(cards)
    if args.tags or args.all:
        report["tags"] = analyze_tags(cards)
    if args.claims or args.all:
        report["claims"] = analyze_claims(cards)
    if args.drift or args.all:
        report["drift"] = analyze_drift(cards)
    if args.scope or args.all:
        report["scope"] = analyze_scope(cards)
    return report


def print_report(report, as_json=False):
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(f"\n🧠 Schema Learning 报告 — {report['generated_at']}")
    print(f"   总卡片: {report['total_cards']}")
    print()

    if 'fields' in report:
        f = report['fields']
        print(f"📊 字段覆盖率: {f['total_fields']} 个字段")
        for c in f['coverage'][:15]:
            flag = "" if c['in_schema'] else " ⚠️非schema"
            print(f"   {c['coverage']*100:5.1f}%  {c['field']:20s}{flag}")
        if f['schema_fields_missing_data']:
            print(f"   schema 内但无数据: {f['schema_fields_missing_data']}")
        if f['non_schema_fields']:
            print(f"   非 schema 字段: {[x['field'] for x in f['non_schema_fields']]}")
        print()

    if 'types' in report:
        t = report['types']
        print(f"🏷️  类型分布: {t['distribution']}")
        if t['invalid_types']:
            print(f"   ❌ 无效类型: {t['invalid_types']}")
        print(f"   类型×Scope: {t['type_scope_matrix']}")
        for r in t['recommendations']:
            print(f"   → [{r['severity']}] {r['issue']}: {r['detail']}")
            print(f"     action: {r['action']}")
        print()

    if 'tags' in report:
        tg = report['tags']
        print(f"🏷️  标签熵: {tg['total_tags']} tags → {tg['unique_tags']} unique (冗余 {tg['redundancy_ratio']*100:.0f}%)")
        for h in tg['high_frequency']:
            tag = h['tag']
            extra = f" → 升级为字段 {h['field_name']}" if h['suggest_as_field'] and h.get('field_name') else ""
            print(f"   [{h['ratio']*100:.0f}%] {tag} × {h['count']}{extra}")
        if tg['long_tail_count']:
            print(f"   长尾标签（仅1次）: {tg['long_tail_count']} 个")
        for r in tg.get('recommendations', []):
            print(f"   → [{r['severity']}] {r['issue']}: {r['detail']}")
            print(f"     action: {r['action']}")
        print()

    if 'claims' in report:
        cl = report['claims']
        if cl.get('total_claims', 0) > 0:
            print(f"📝 Claim 模式: {cl['total_claims']} 条 (avg {cl['avg_claims_per_card']}/card)")
            print(f"   长度: avg={cl['length']['avg']} min={cl['length']['min']} max={cl['length']['max']}")
            print(f"   模式分布: {cl['pattern_distribution']}")
            if cl['unmatched_count']:
                print(f"   未匹配: {cl['unmatched_count']} 条")
                for u in cl['unmatched_sample'][:5]:
                    print(f"     - {u}")
            for r in cl.get('recommendations', []):
                print(f"   → [{r['severity']}] {r['issue']}: {r['detail']}")
                print(f"     action: {r['action']}")
        print()

    if 'drift' in report:
        dr = report['drift']
        print(f"🔀 Schema 漂移: {dr['drift_count']} 个非 schema 字段")
        for d in dr['drift_fields'][:10]:
            print(f"   {d['field']} × {d['count']}  例: {d['examples'][0] if d['examples'] else ''}")
        print()

    if 'scope' in report:
        sc = report['scope']
        print(f"🎯 Scope 分布: {sc['distribution']}")
        print(f"   缺失率: {sc['missing_rate']*100:.0f}%")
        for r in sc.get('recommendations', []):
            print(f"   → [{r['severity']}] {r['issue']}: {r['detail']}")
            print(f"     action: {r['action']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="MindMemOS 借鉴：Schema Learning — 自动发现高频记忆模式")
    parser.add_argument("--all", action="store_true", help="全量分析（默认）")
    parser.add_argument("--fields", action="store_true")
    parser.add_argument("--types", action="store_true")
    parser.add_argument("--tags", action="store_true")
    parser.add_argument("--claims", action="store_true")
    parser.add_argument("--drift", action="store_true")
    parser.add_argument("--scope", action="store_true")
    parser.add_argument("--apply", action="store_true", help="应用修复（重分类+清理标签+回填scope）")
    parser.add_argument("--dry-run", action="store_true", help="干跑，不落盘")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    store = load_store()

    # 默认 = all
    if not (args.fields or args.types or args.tags or args.claims
            or args.drift or args.scope or args.all or args.apply):
        args.all = True

    if args.apply:
        changes = apply_fixes(store, dry_run=args.dry_run)
        print(f"\n🔧 Schema 修复" + (" (dry-run)" if args.dry_run else ""))
        print(f"   重分类 memory: {changes['reclassified']} 张")
        print(f"   清理元数据标签: {changes['tags_cleaned']} 张")
        print(f"   回填 scope: {changes['scope_backfilled']} 张")
        for d in changes['details'][:10]:
            extra = []
            if 'subtype' in d:
                extra.append(f"→{d['subtype']}")
            if 'removed_tags' in d:
                extra.append(f"-{d['removed_tags']}tags")
            if 'scope_backfilled' in d:
                extra.append(f"scope={d['scope_backfilled']}")
            print(f"   {d['title'][:45]}  {' '.join(extra)}")
        return

    report = build_report(store, args)
    print_report(report, args.json)


if __name__ == "__main__":
    main()
