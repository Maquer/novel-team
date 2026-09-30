#!/usr/bin/env python3
# Version: 0.1.0
"""
学习轨迹追踪 — 记录学习进度、能力评估、复习提醒。

用法:
    # 记录学习事件
    python3 obsidian-learn.py --add "水果采购" "已掌握产地行情基础"

    # 更新等级
    python3 obsidian-learn.py --update "水果采购" --level 4

    # 查看学习状态
    python3 obsidian-learn.py --status

    # 查看能力雷达
    python3 obsidian-learn.py --radar

    # 复习提醒
    python3 obsidian-learn.py --review

    # 学习统计
    python3 obsidian-learn.py --stats
"""
import argparse, os, json, sys
from datetime import datetime, timedelta

LEARN_STORE = "/var/minis/shared/.learning-store.json"

STAGES = {
    "1": {"label": "初识", "color": "🌱", "desc": "刚接触，知道基本概念"},
    "2": {"label": "入门", "color": "🌿", "desc": "能基本使用，理解主要原理"},
    "3": {"label": "熟悉", "color": "🌳", "desc": "能熟练应用，理解细节"},
    "4": {"label": "精通", "color": "🏔️", "desc": "能教授他人，有深度理解"},
    "5": {"label": "专家", "color": "💎", "desc": "有独特见解，能创新改进"},
}


def _get_cats():
    """动态获取能力域：已有学习记录 + 预定义兜底。"""
    store = _load()
    existing = list({e["topic"] for e in store.get("entries", []) if e.get("topic")})
    default = ["AI编程", "公众号运营", "Agent框架", "AI工具",
               "内容创作", "数据分析", "项目管理", "Python", "Obsidian"]
    return existing + [c for c in default if c not in existing]


def _load():
    if os.path.exists(LEARN_STORE):
        try:
            return json.load(open(LEARN_STORE, 'r', encoding='utf-8'))
        except:
            return {"entries": [], "sessions": []}
    return {"entries": [], "sessions": []}


def _save(store):
    os.makedirs(os.path.dirname(LEARN_STORE) or '.', exist_ok=True)
    json.dump(store, open(LEARN_STORE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def add_learning(topic, note, level=None, source=None):
    store = _load()
    # 找现有条目
    entry = None
    for e in store["entries"]:
        if e["topic"] == topic:
            entry = e
            break

    if entry:
        entry["level"] = int(level) if level else entry["level"]
        entry["last_updated"] = datetime.now().isoformat()
        entry["notes"].append({"ts": datetime.now().isoformat(), "note": note, "source": source})
        entry["sessions"] = entry.get("sessions", 0) + 1
    else:
        entry = {
            "topic": topic, "level": int(level) if level else 1,
            "notes": [{"ts": datetime.now().isoformat(), "note": note, "source": source}],
            "sessions": 1, "created": datetime.now().isoformat(), "last_updated": datetime.now().isoformat()
        }
        store["entries"].append(entry)

    store["sessions"].append({"ts": datetime.now().isoformat(), "topic": topic, "note": note})
    _save(store)
    return entry


def get_status():
    store = _load()
    entries = store.get("entries", [])
    return sorted(entries, key=lambda x: x["level"], reverse=True)


def get_radar():
    store = _load()
    entries = store.get("entries", [])
    cats = _get_cats()
    result = []
    for cat in cats:
        entry = next((e for e in entries if e["topic"] == cat), None)
        level = entry["level"] if entry else 0
        info = STAGES.get(str(level), STAGES["1"])
        bar = "█" * level + "░" * (5 - level)
        result.append({"topic": cat, "level": level, "icon": info["color"], "bar": bar, "label": info["label"]})
    return result


def get_review_suggestions():
    store = _load()
    now = datetime.now()
    suggestions = []
    for e in store.get("entries", []):
        last = datetime.fromisoformat(e.get("last_updated", now.isoformat()))
        days_since = (now - last).days
        if days_since > 7:
            suggestions.append({"topic": e["topic"], "days_since": days_since, "level": e["level"]})
    return suggestions


def get_stats():
    store = _load()
    entries = store.get("entries", [])
    sessions = store.get("sessions", [])
    level_dist = {}
    for e in entries:
        l = str(e["level"])
        level_dist[l] = level_dist.get(l, 0) + 1
    topics = set(e["topic"] for e in sessions)
    return {
        "total_topics": len(entries), "total_sessions": len(sessions),
        "topics_covered": len(topics), "level_distribution": level_dist,
        "recent_30d": len([s for s in sessions if (datetime.now() - datetime.fromisoformat(s["ts"])).days <= 30]),
    }


def main():
    parser = argparse.ArgumentParser(description='学习轨迹追踪')
    parser.add_argument('--add', '-a', nargs=2, metavar=('TOPIC', 'NOTE'), help='记录学习')
    parser.add_argument('--update', metavar='TOPIC', help='更新等级')
    parser.add_argument('--level', type=int, default=2, help='更新等级（1-5）')
    parser.add_argument('--status', '-s', action='store_true', help='查看状态')
    parser.add_argument('--radar', '-r', action='store_true', help='能力雷达')
    parser.add_argument('--review', '-v', action='store_true', help='复习提醒')
    parser.add_argument('--stats', action='store_true', help='学习统计')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')

    args = parser.parse_args()

    if args.add:
        entry = add_learning(args.add[0], args.add[1])
        info = STAGES.get(str(entry["level"]), STAGES["1"])
        print(f"{info['color']} {args.add[0]} → {info['label']} (Lv.{entry['level']})")
        sys.exit(0)

    if args.update:
        entry = add_learning(args.update, f"等级更新 → Lv.{args.level}", level=args.level)
        info = STAGES.get(str(entry["level"]), STAGES["1"])
        print(f"{info['color']} {args.update} → {info['label']} (Lv.{entry['level']})")
        sys.exit(0)

    if args.status:
        entries = get_status()
        if not entries:
            print("📝 暂无学习记录")
            sys.exit(0)
        print(f"📊 学习状态 ({len(entries)} 个话题)\n")
        for e in entries:
            info = STAGES.get(str(e["level"]), STAGES["1"])
            last = e.get("last_updated", "?")[:10]
            print(f"  {info['color']} {e['topic']:20s} Lv.{e['level']} {info['label']:4s} | {e['sessions']}次 | {last}")
        sys.exit(0)

    if args.radar:
        radar = get_radar()
        print("🎯 能力雷达\n")
        for r in radar:
            print(f"  {r['icon']} {r['topic']:12s} {r['bar']} Lv.{r['level']} {r['label']}")
        sys.exit(0)

    if args.review:
        suggestions = get_review_suggestions()
        if suggestions:
            print(f"📋 需复习话题 ({len(suggestions)} 个)\n")
            for s in suggestions:
                info = STAGES.get(str(s["level"]), STAGES["1"])
                print(f"  {info['color']} {s['topic']:20s} 已 {s['days_since']} 天未学习")
        else:
            print("✅ 暂无需要复习的话题")
        sys.exit(0)

    if args.stats:
        stats = get_stats()
        print(f"📈 学习统计\n")
        print(f"  总话题: {stats['total_topics']}")
        print(f"  总学习次数: {stats['total_sessions']}")
        print(f"  近30天: {stats['recent_30d']} 次")
        print(f"  等级分布:")
        for lv, cnt in sorted(stats['level_distribution'].items()):
            info = STAGES.get(lv, STAGES["1"])
            print(f"    {info['color']} Lv.{lv} {info['label']:4s}: {cnt} 个话题")
        sys.exit(0)

    parser.print_help()


if __name__ == '__main__':
    main()
