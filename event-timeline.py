#!/usr/bin/env python3
# Version: 0.1.0
"""Event Timeline"""
import os, re, argparse, json
from pathlib import Path
MEMORY_DIR = "/var/minis/memory"
EVENT_PATTERNS = re.compile(r'(归档|落地|部署|升级|创建|完成|修复|新增|迁移|重构|上线|发布|验证|落地)')

def extract_events(date_str, content):
    """从 daily log 提取事件行"""
    events = []
    for line in content.splitlines():
        line = line.strip()
        if not line or len(line) < 5:
            continue
        if line.startswith('#'):
            continue
        if EVENT_PATTERNS.search(line):
            clean = re.sub(r'^[-•*]\s*', '', line)
            clean = re.sub(r'\*\*(.+?)\*\*', r'\1', clean)
            clean = re.sub(r'`([^`]+)`', r'\1', clean)
            if len(clean) > 4:
                events.append(clean)
    return events


def parse_daily_log(filename):
    """解析 daily log 文件，提取事件"""
    path = Path(MEMORY_DIR) / filename
    if not path.exists():
        return None
    date_str = filename[:-3]
    with open(path) as f:
        content = f.read()
    events = extract_events(date_str, content)
    return {"date": date_str, "events": events}


def list_daily_dates():
    """列出所有 daily log 日期，按时间序"""
    dates = []
    for f in os.listdir(MEMORY_DIR):
        if f.endswith(".md") and re.match(r"\d{4}-\d{2}-\d{2}\.md$", f):
            dates.append(f[:-3])
    return sorted(dates)


def search_timeline(topic=None, date_from=None, date_to=None, limit=50):
    """搜索事件时间线"""
    dates = list_daily_dates()
    if date_from:
        dates = [d for d in dates if d >= date_from]
    if date_to:
        dates = [d for d in dates if d <= date_to]

    timeline = []
    for date_str in dates:
        data = parse_daily_log(date_str + ".md")
        if not data:
            continue
        events = data["events"]
        if topic:
            topic_lower = topic.lower()
            events = [e for e in events if topic_lower in e.lower()]
        if events:
            for event in events:
                timeline.append({"date": date_str, "event": event})

    return timeline

def main():
    parser = argparse.ArgumentParser(description="Minis 事件时间线（BEAM EO 修复）")
    parser.add_argument("--topic", "-t", help="按主题关键词过滤")
    parser.add_argument("--from", "-f", dest="date_from", help="起始日期 YYYY-MM-DD")
    parser.add_argument("--to", "-t2", dest="date_to", help="结束日期 YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=0, help="最近 N 天")
    parser.add_argument("--query", "-q", help="搜索关键词（命中事件）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--limit", "-n", type=int, default=0, help="最多显示 N 条")
    args = parser.parse_args()

    days = 0
    from_date = args.date_from
    to_date = args.date_to
    if args.days > 0:
        from datetime import datetime, timedelta
        to_date = datetime.now().strftime("%Y-%m-%d")
        from_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    events = search_timeline(topic=args.topic,
                             date_from=from_date, date_to=to_date)
    if args.limit > 0:
        events = events[:args.limit]

    if args.json:
        print(json.dumps([{"date": e["date"], "event": e["event"]} for e in events],
                         ensure_ascii=False, indent=2))
    else:
        if not events:
            print("未找到事件。")
            return
        print(f"事件时间线（{len(events)} 条，严格时间序）")
        print("=" * 60)
        for e in events:
            print(f"  {e['date']}  {e['event']}")
        print("=" * 60)

if __name__ == "__main__":
    main()
