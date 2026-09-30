#!/usr/bin/env python3
# Version: 0.1.0
"""
obsidian-skill-lifecycle.py — Skill 生命周期管理

管理 knowledge card 从 draft → approved → deprecated 的完整生命周期。
与 obsidian-distill.py 审核流程打通，补充 distill 缺失的 deprecated 机制。

用法:
  # 概览所有卡片状态
  python3 obsidian-skill-lifecycle.py --overview

  # 列出 draft 状态的卡片（待审核）
  python3 obsidian-skill-lifecycle.py --list draft

  # 列出 approved 状态的卡片
  python3 obsidian-skill-lifecycle.py --list approved

  # 自动检测应标记 deprecated 的卡片
  python3 obsidian-skill-lifecycle.py --detect-deprecated

  # 将某卡片标记为 deprecated
  python3 obsidian-skill-lifecycle.py --deprecate "卡片标题"

  # 将某卡片从 draft 批准为 approved
  python3 obsidian-skill-lifecycle.py --approve "卡片标题"

  # 生命周期统计
  python3 obsidian-skill-lifecycle.py --stats

  # JSON 输出
  python3 obsidian-skill-lifecycle.py --overview --json
"""

import argparse
import json
import os
from datetime import datetime

KNOWLEDGE_STORE = "/var/minis/shared/.knowledge-store.json"
STATE_FILE = "/var/minis/shared/.skill-lifecycle-state.json"

# 生命周期状态
STATUSES = {
    "draft": {"label": "草稿", "icon": "📝", "color": "yellow"},
    "approved": {"label": "已批准", "icon": "✅", "color": "green"},
    "archived": {"label": "已归档", "icon": "📦", "color": "blue"},
    "rejected": {"label": "已拒绝", "icon": "❌", "color": "red"},
    "deprecated": {"label": "已弃用", "icon": "🗑️", "color": "gray"},
}

# 弃用检测规则
DEPRECATION_RULES = [
    {
        "name": "长期未更新",
        "desc": "approved 卡片超过 180 天未被修改或引用",
        "days_threshold": 180,
        "action": "deprecated",
    },
    {
        "name": "零主张卡片",
        "desc": "approved 卡片主张数为零（蒸馏质量差）",
        "min_claims": 0,
        "action": "deprecated",
    },
    {
        "name": "低分卡片",
        "desc": "approved 卡片评分 < 30（内容质量低）",
        "max_score": 30,
        "action": "deprecated",
    },
    {
        "name": "重复标题",
        "desc": "标题与其他卡片重复或高度相似",
        "action": "deprecated",
    },
]


def _load_store():
    if not os.path.exists(KNOWLEDGE_STORE):
        return {"cards": []}
    try:
        with open(KNOWLEDGE_STORE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"cards": []}


def _save_store(store):
    os.makedirs(os.path.dirname(KNOWLEDGE_STORE) or '.', exist_ok=True)
    with open(KNOWLEDGE_STORE, 'w', encoding='utf-8') as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"actions": [], "stats": {"total": 0, "draft": 0, "approved": 0,
                                       "deprecated": 0, "archived": 0, "rejected": 0}}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE) or '.', exist_ok=True)
    json.dump(state, open(STATE_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def _update_stats(store):
    state = _load_state()
    cards = store.get("cards", [])
    state["stats"] = {
        "total": len(cards),
        "draft": sum(1 for c in cards if c.get("status") == "draft"),
        "approved": sum(1 for c in cards if c.get("status") == "approved"),
        "deprecated": sum(1 for c in cards if c.get("status") == "deprecated"),
        "archived": sum(1 for c in cards if c.get("status") == "archived"),
        "rejected": sum(1 for c in cards if c.get("status") == "rejected"),
    }
    _save_state(state)
    return state["stats"]


def overview():
    """概览所有卡片生命周期状态。"""
    store = _load_store()
    cards = store.get("cards", [])
    stats = _update_stats(store)

    by_status = {}
    for s in STATUSES:
        by_status[s] = [c for c in cards if c.get("status") == s]

    return {
        "stats": stats,
        "by_status": {s: len(v) for s, v in by_status.items()},
        "recent_drafts": [
            {"id": c.get("id"), "title": c.get("title"), "score": c.get("score"),
             "created": c.get("created", "")[:16]}
            for c in sorted(by_status.get("draft", []),
                            key=lambda x: x.get("created", ""), reverse=True)[:10]
        ],
        "recent_deprecated": [
            {"id": c.get("id"), "title": c.get("title"),
             "created": c.get("created", "")[:16],
             "deprecated_at": c.get("deprecated_at", "")[:16]}
            for c in sorted(by_status.get("deprecated", []),
                            key=lambda x: x.get("deprecated_at", ""), reverse=True)[:10]
        ],
    }


def list_by_status(status):
    """列出指定状态的卡片。"""
    store = _load_store()
    cards = [c for c in store.get("cards", []) if c.get("status") == status]
    return [
        {"id": c.get("id"), "title": c.get("title"),
         "score": c.get("score"), "claims": len(c.get("claims", [])),
         "created": c.get("created", "")[:16],
         "tags": c.get("tags", [])[:5]}
        for c in cards[-30:]
    ]


def detect_deprecated():
    """检测应标记为 deprecated 的卡片。"""
    store = _load_store()
    cards = [c for c in store.get("cards", []) if c.get("status") == "approved"]
    candidates = []

    now = datetime.now()

    for card in cards:
        reasons = []

        # 规则1: 长期未更新
        created = card.get("created", "")
        if created:
            try:
                created_dt = datetime.fromisoformat(created[:19])
                days_since = (now - created_dt).days
                if days_since > 180:
                    reasons.append(f"长期未更新 ({days_since} 天)")
            except Exception:
                pass

        # 规则2: 零主张
        if len(card.get("claims", [])) == 0:
            reasons.append("零主张（内容缺失）")

        # 规则3: 低分
        score = card.get("score", 100)
        if score < 30:
            reasons.append(f"评分过低 ({score})")

        # 规则4: 重复标题
        title = card.get("title", "")
        if title:
            dupes = [c for c in cards if c.get("title") == title and c.get("id") != card.get("id")]
            if dupes:
                reasons.append(f"标题重复 ({len(dupes)} 条)")

        if reasons:
            candidates.append({
                "id": card.get("id"),
                "title": card.get("title"),
                "score": score,
                "claims": len(card.get("claims", [])),
                "created": created[:16] if created else "",
                "reasons": reasons,
            })

    return candidates


def deprecate(title_or_id):
    """将指定卡片标记为 deprecated。"""
    store = _load_store()
    changed = False

    for card in store.get("cards", []):
        if card.get("title") == title_or_id or card.get("id") == title_or_id:
            card["status"] = "deprecated"
            card["deprecated_at"] = datetime.now().isoformat()
            card["deprecated_reason"] = "手动标记"
            changed = True
            break

    if changed:
        _save_store(store)
        _update_stats(store)
        return {"deprecated": title_or_id, "success": True}
    return {"deprecated": title_or_id, "success": False, "reason": "未找到匹配的卡片"}


def approve(title_or_id):
    """将 draft 卡片批准为 approved。"""
    store = _load_store()
    changed = False

    for card in store.get("cards", []):
        if card.get("title") == title_or_id or card.get("id") == title_or_id:
            if card.get("status") != "draft":
                return {"title": title_or_id, "success": False,
                        "reason": f"当前状态 {card.get('status')}，非 draft"}
            card["status"] = "approved"
            card["approved_at"] = datetime.now().isoformat()
            changed = True
            break

    if changed:
        _save_store(store)
        _update_stats(store)
        return {"approved": title_or_id, "success": True}
    return {"approved": title_or_id, "success": False, "reason": "未找到匹配的 draft 卡片"}


def get_stats():
    """获取生命周期统计。"""
    store = _load_store()
    cards = store.get("cards", [])
    total = len(cards)

    # 按知识类型统计
    type_dist = {}
    for c in cards:
        ktype = c.get("type", "unknown")
        type_dist[ktype] = type_dist.get(ktype, 0) + 1

    # 状态分布
    status_dist = {}
    for c in cards:
        s = c.get("status", "unknown")
        status_dist[s] = status_dist.get(s, 0) + 1

    return {
        "total": total,
        "status_dist": status_dist,
        "type_dist": type_dist,
        "avg_score": round(sum(c.get("score", 0) for c in cards) / max(total, 1), 1),
    }


def print_overview(data):
    stats = data["stats"]
    print("=" * 50)
    print(f"  🔄 Skill 生命周期概览")
    print("=" * 50)
    print(f"\n  📊 总计: {stats['total']} 张卡片")
    print(f"    📝 Draft:     {stats['draft']}")
    print(f"    ✅ Approved:  {stats['approved']}")
    print(f"    📦 Archived:  {stats['archived']}")
    print(f"    🗑️  Deprecated: {stats['deprecated']}")
    print(f"    ❌ Rejected:  {stats['rejected']}")

    if data["recent_drafts"]:
        print(f"\n  📝 最近 Draft 卡片:")
        for c in data["recent_drafts"][:5]:
            print(f"    {c['title'][:40]:40s}  评分:{c['score']}")

    if data["recent_deprecated"]:
        print(f"\n  🗑️  最近弃用:")
        for c in data["recent_deprecated"][:5]:
            print(f"    {c['title'][:40]:40s}  {c.get('deprecated_at','')[:10]}")


def main():
    parser = argparse.ArgumentParser(description='Skill 生命周期管理')
    parser.add_argument('--overview', action='store_true', help='生命周期概览')
    parser.add_argument('--list', type=str, metavar='STATUS', help='列出指定状态的卡片')
    parser.add_argument('--detect-deprecated', action='store_true', help='检测应弃用的卡片')
    parser.add_argument('--deprecate', type=str, metavar='TITLE', help='标记卡片为 deprecated')
    parser.add_argument('--approve', type=str, metavar='TITLE', help='批准 draft 卡片')
    parser.add_argument('--stats', action='store_true', help='统计信息')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')
    args = parser.parse_args()

    if args.overview:
        data = overview()
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print_overview(data)

    if args.list:
        items = list_by_status(args.list)
        if args.json:
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            print(f"\n  {'📝' if args.list == 'draft' else '✅'} 状态 [{args.list.upper()}] 共 {len(items)} 条")
            print("  " + "─" * 48)
            for c in items:
                print(f"    {c['title'][:45]:45s}  评分:{c['score']}  主张:{c['claims']}")

    if args.detect_deprecated:
        candidates = detect_deprecated()
        if args.json:
            print(json.dumps({"candidates": candidates, "count": len(candidates)},
                             ensure_ascii=False, indent=2))
        else:
            print("=" * 50)
            print(f"  🗑️  弃用候选检测 — {len(candidates)} 张卡片")
            print("=" * 50)
            for c in candidates[:20]:
                reasons_str = "; ".join(c["reasons"])
                print(f"\n  🗑️  {c['title'][:40]}")
                print(f"      评分:{c['score']}  主张:{c['claims']}  创建:{c['created'][:10]}")
                print(f"      原因: {reasons_str}")
            if len(candidates) > 20:
                print(f"\n  ... 还有 {len(candidates)-20} 条")

    if args.deprecate:
        result = deprecate(args.deprecate)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result["success"]:
                print(f"  ✅ 已标记为 deprecated: {result['deprecated']}")
            else:
                print(f"  ❌ 失败: {result.get('reason')}")

    if args.approve:
        result = approve(args.approve)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if result["success"]:
                print(f"  ✅ 已批准: {result['approved']}")
            else:
                print(f"  ❌ 失败: {result.get('reason')}")

    if args.stats:
        stats = get_stats()
        if args.json:
            print(json.dumps(stats, ensure_ascii=False, indent=2))
        else:
            print("=" * 50)
            print(f"  📊 Skill 生命周期统计")
            print("=" * 50)
            print(f"\n  总计: {stats['total']} 张")
            print(f"  平均评分: {stats['avg_score']}")
            print(f"\n  按状态:")
            for s, count in stats["status_dist"].items():
                cfg = STATUSES.get(s, {"icon": "❓", "label": s})
                print(f"    {cfg['icon']} {s:12s}  {count}")
            print(f"\n  按类型:")
            for t, count in stats["type_dist"].items():
                print(f"    {t:12s}  {count}")

    if not any([args.overview, args.list, args.detect_deprecated,
                args.deprecate, args.approve, args.stats]):
        parser.print_help()


if __name__ == "__main__":
    main()