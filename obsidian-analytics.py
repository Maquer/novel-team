#!/usr/bin/env python3
# Version: 0.1.0
"""
搜索热度追踪 — 记录每次 Obsidian 搜索行为，分析搜索模式，调优搜索权重。

用法:
    # 记录一次搜索
    python3 obsidian-analytics.py --log "水果采购" --folder "01-Projects"

    # 查看搜索统计
    python3 obsidian-analytics.py --stats

    # 查看热门笔记（最常被搜到的）
    python3 obsidian-analytics.py --trending

    # 查看冷门关键词（搜了但没结果的）
    python3 obsidian-analytics.py --dead-ends

    # 分析搜索质量（搜索次数 vs 结果相关性）
    python3 obsidian-analytics.py --quality

    # 生成调优建议
    python3 obsidian-analytics.py --suggest
"""

import argparse
import os
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

# 日志文件
SEARCH_LOG = os.path.expanduser("~/.obsidian-search-log.json")

# 如果搜索日志有旧数据但结构不对，用备用路径
if not os.path.exists(SEARCH_LOG):
    SEARCH_LOG = "/var/minis/shared/.obsidian-search-log.json"

# ═══════════════════════════════════════════════════

def _load_log() -> list:
    if os.path.exists(SEARCH_LOG):
        try:
            return json.load(open(SEARCH_LOG, 'r', encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            # JSON 损坏时尝试从行缓存恢复
            try:
                with open(SEARCH_LOG, 'r', encoding='utf-8') as f:
                    lines = [l for l in f.readlines() if l.strip().startswith('{')]
                recovered = []
                for line in lines:
                    try:
                        recovered.append(json.loads(line))
                    except:
                        pass
                if recovered:
                    _save_log(recovered)
                    print(f"⚠️ 搜索日志 JSON 损坏，已恢复 {len(recovered)} 条记录")
                    return recovered
            except:
                pass
            return []
    return []


def _save_log(log: list):
    os.makedirs(os.path.dirname(SEARCH_LOG) or '.', exist_ok=True)
    json.dump(log, open(SEARCH_LOG, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def log_search(query: str, folder: str = None, top: int = 10,
               result_count: int = 0, clicked_path: str = None):
    """记录一次搜索行为。"""
    log = _load_log()
    entry = {
        "ts": datetime.now().isoformat(),
        "query": query,
        "folder": folder,
        "top": top,
        "result_count": result_count,
        "clicked": clicked_path,
    }
    log.append(entry)
    # 保留最近 500 条
    log = log[-500:]
    _save_log(log)


def get_stats(days: int = 30) -> dict:
    """获取搜索统计。"""
    log = _load_log()
    now = datetime.now()
    cutoff = now - timedelta(days=days)

    recent = [e for e in log if datetime.fromisoformat(e["ts"]) >= cutoff]

    # 搜索次数
    total_searches = len(recent)

    # 搜索关键词频次
    query_counter = Counter(e["query"] for e in recent)

    # 有结果的搜索比例
    with_results = sum(1 for e in recent if e.get("result_count", 0) > 0)
    hit_rate = (with_results / total_searches * 100) if total_searches > 0 else 0

    # 点击了结果的搜索
    with_click = sum(1 for e in recent if e.get("clicked"))

    return {
        "total_searches": total_searches,
        "hit_rate": round(hit_rate, 1),
        "click_rate": round(with_click / total_searches * 100, 1) if total_searches > 0 else 0,
        "top_queries": query_counter.most_common(10),
        "dead_end_queries": [e["query"] for e in recent if e.get("result_count", 0) == 0],
    }


def get_trending(days: int = 30) -> list:
    """获取最常被搜到的笔记（按被点击次数排序）。"""
    log = _load_log()
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    recent = [e for e in log if datetime.fromisoformat(e["ts"]) >= cutoff and e.get("clicked")]

    path_counter = Counter(e["clicked"] for e in recent)
    return [{"path": p, "views": c} for p, c in path_counter.most_common(10)]


def get_dead_ends(days: int = 30) -> list:
    """获取搜了但没结果的关键词。"""
    log = _load_log()
    now = datetime.now()
    cutoff = now - timedelta(days=days)
    recent = [e for e in log if datetime.fromisoformat(e["ts"]) >= cutoff]

    dead = [e["query"] for e in recent if e.get("result_count", 0) == 0]
    return list(Counter(dead).most_common(10))


def suggest() -> str:
    """基于搜索数据生成调优建议。"""
    stats = get_stats()
    trending = get_trending()
    dead = get_dead_ends()

    suggestions = []

    if stats["hit_rate"] < 50 and stats["total_searches"] > 5:
        suggestions.append(f"⚠️ 搜索命中率仅 {stats['hit_rate']}%。建议：扩大搜索范围或检查笔记命名是否包含常用关键词。")

    if dead:
        suggestions.append(f"🚫 以下关键词常搜不到结果（可能是笔记缺少相关标签/关键词）：")
        for kw, cnt in dead[:5]:
            suggestions.append(f"    - 「{kw}」出现 {cnt} 次")

    if stats["click_rate"] < 30 and stats["total_searches"] > 10:
        suggestions.append(f"📉 结果点击率仅 {stats['click_rate']}%。建议：摘要提取逻辑可能不够精准，或搜索结果排序需要优化。")

    if trending:
        suggestions.append(f"🔥 最常访问的笔记：")
        for item in trending[:3]:
            suggestions.append(f"    - {item['path']} ({item['views']} 次)")

    if not suggestions:
        suggestions.append("✅ 搜索质量正常，暂无需要优化的地方。")

    return "\n".join(suggestions)


def main():
    parser = argparse.ArgumentParser(description='Obsidian 搜索热度追踪')
    parser.add_argument('--log', '-l', help='记录一次搜索（格式: "query"）')
    parser.add_argument('--folder', '-f', help='搜索所在的文件夹（配合 --log 使用）')
    parser.add_argument('--stats', '-s', action='store_true', help='查看搜索统计')
    parser.add_argument('--trending', '-t', action='store_true', help='查看热门笔记')
    parser.add_argument('--dead-ends', '-d', action='store_true', help='查看零结果关键词')
    parser.add_argument('--quality', '-q', action='store_true', help='分析搜索质量')
    parser.add_argument('--suggest', '-g', action='store_true', help='生成调优建议')
    parser.add_argument('--days', type=int, default=30, help='统计天数')
    parser.add_argument('--result-count', '-c', type=int, default=0, help='搜索结果数量（配合 --log）')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')

    args = parser.parse_args()

    # 记录搜索
    if args.log:
        log_search(args.log, folder=args.folder,
                   result_count=args.result_count or 0)
        print(f"✅ 已记录搜索: {args.log}")
        sys.exit(0)

    # 统计
    if args.stats:
        stats = get_stats(args.days)
        if args.json:
            print(json.dumps(stats, ensure_ascii=False, indent=2))
        else:
            print(f"📊 搜索统计（{args.days} 天）\n")
            print(f"  总搜索: {stats['total_searches']} 次")
            print(f"  命中率: {stats['hit_rate']}%")
            print(f"  点击率: {stats['click_rate']}%")
            print(f"\n  🔝 高频关键词:")
            for kw, cnt in stats['top_queries']:
                print(f"    {cnt:3d}x  {kw}")
        sys.exit(0)

    if args.trending:
        trending = get_trending(args.days)
        if args.json:
            print(json.dumps(trending, ensure_ascii=False, indent=2))
        else:
            print(f"🔥 热门笔记（{args.days} 天）\n")
            for item in trending:
                print(f"  {item['views']:3d}x  {item['path']}")
        sys.exit(0)

    if args.dead_ends:
        dead = get_dead_ends(args.days)
        if args.json:
            print(json.dumps(dead, ensure_ascii=False, indent=2))
        else:
            print(f"🚫 零结果关键词（{args.days} 天）\n")
            for kw, cnt in dead:
                print(f"  {cnt:3d}x  {kw}")
        sys.exit(0)

    if args.quality or args.suggest:
        print(suggest())
        sys.exit(0)

    parser.print_help()


if __name__ == '__main__':
    main()