#!/usr/bin/env python3
# Version: 0.1.0
"""
memory-knowledge-link.py — 跨笔记知识关联分析器（Smart Connections 等价物）
扫描 daily logs 和 Obsidian vault，发现跨笔记的概念关联、趋势话题、
并推荐 L2→L3 晋升候选。
用法: python3 memory-knowledge-link.py [--days N] [--output PATH]
"""
import re, json
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict

MEMORY_DIR = Path("/var/minis/memory")
OBSIDIAN_DIR = Path("/var/minis/mounts/loong")

# 概念提取模式
CONCEPT_PATTERNS = [
    (r'`([^`]+)`', 'inline_code'),
    (r'#(\w[\w\-]*\w)', 'hashtag'),
    (r'\b(AI|LLM|Agent|TTS|OCR|NLP|MCP|API|CLI|GUI|SDK|RTF|DNSMOS)\b', 'tech_acronym'),
]

# L3 晋升阈值
PROMOTION_THRESHOLD_DAYS = 2  # 话题跨越 ≥2 天
PROMOTION_THRESHOLD_MENTIONS = 3  # 出现 ≥3 次

def extract_concepts(text):
    """从文本中提取概念"""
    concepts = []
    for pattern, ctype in CONCEPT_PATTERNS:
        for match in re.findall(pattern, text):
            concepts.append((match, ctype))
    return concepts

def scan_daily_logs(days=14):
    """扫描 daily logs"""
    today = datetime.now()
    logs = {}
    for i in range(days):
        date = today - timedelta(days=i)
        fname = date.strftime("%Y-%m-%d.md")
        fpath = MEMORY_DIR / fname
        if fpath.exists():
            text = fpath.read_text(encoding="utf-8")
            logs[fname[:10]] = text
    return logs

def scan_obsidian_vault():
    """扫描 Obsidian vault 中的 markdown 文件"""
    if not OBSIDIAN_DIR.exists():
        return {}
    files = {}
    for md_file in OBSIDIAN_DIR.rglob("*.md"):
        rel = md_file.relative_to(OBSIDIAN_DIR)
        files[str(rel)] = md_file.read_text(encoding="utf-8")
    return files

def find_cross_references(logs, obsidian_files):
    """发现跨笔记的交叉引用"""
    cross_refs = []
    all_text = "\n".join(logs.values())
    
    # 查找 minis:// 链接
    for match in re.findall(r'minis://([^)\s]+)', all_text):
        ref = match.split('#')[0]
        if '/' in ref and len(ref) > 3:
            cross_refs.append(("minis_link", ref))
    
    # 查找 Obsidian 文件引用
    for ref in re.findall(r'\[(.+?)\]\([^)]*\.md\)', all_text):
        cross_refs.append(("md_ref", ref))
    
    return cross_refs

def analyze_trends(logs):
    """话题趋势分析"""
    daily_topics = {}
    for date, text in logs.items():
        # 按行提取标题
        headings = re.findall(r'^##\s+(.+)$', text, re.MULTILINE)
        daily_topics[date] = headings
    
    # 统计跨天话题
    topic_days = defaultdict(set)
    topic_mentions = Counter()
    
    for date, headings in daily_topics.items():
        for h in headings:
            # 提取话题关键词
            for word in h.split():
                if len(word) >= 3:
                    topic_days[word].add(date)
                    topic_mentions[word] += 1
    
    # 过滤：跨天且频次足够
    promoted = {}
    for topic, days in topic_days.items():
        if len(days) >= PROMOTION_THRESHOLD_DAYS and topic_mentions[topic] >= PROMOTION_THRESHOLD_MENTIONS:
            promoted[topic] = {
                "days": len(days),
                "mentions": topic_mentions[topic],
                "dates": sorted(days),
            }
    
    return dict(sorted(promoted.items(), key=lambda x: -x[1]["mentions"]))

def suggest_l3_promotions(logs):
    """推荐 L2→L3 晋升"""
    # 收集每日日志中的"项目"关键词
    project_keywords = defaultdict(list)
    project_pattern = re.compile(r'(?<!\w)([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-]+)*|[\u4e00-\u9fff]{2,}(?:项目|系列|系统|框架|架构|工具|平台|库))')
    
    for date, text in logs.items():
        for match in project_pattern.finditer(text):
            keyword = match.group().strip()
            if keyword not in {"日期", "状态", "指标", "数值", "内容", "说明"}:
                project_keywords[keyword].append(date)
    
    promotions = []
    for keyword, dates in project_keywords.items():
        unique_dates = set(dates)
        if len(unique_dates) >= PROMOTION_THRESHOLD_DAYS and len(dates) >= PROMOTION_THRESHOLD_MENTIONS:
            promotions.append({
                "topic": keyword,
                "day_span": len(unique_dates),
                "total_mentions": len(dates),
                "dates": sorted(unique_dates),
                "reason": f"跨{len(unique_dates)}天, {len(dates)}次提及"
            })
    
    promotions.sort(key=lambda x: -x["total_mentions"])
    return promotions[:8]  # 最多推荐8个

def find_obsidian_patterns(obsidian_files):
    """分析 Obsidian 笔记模式"""
    if not obsidian_files:
        return {}
    
    ai_tools = {k: v for k, v in obsidian_files.items() if "AI工具" in k}
    
    patterns = {
        "AI工具归档数": len(ai_tools),
        "按语言分布": Counter(),
    }
    
    for _, content in ai_tools.items():
        lang_match = re.search(r'(?<=语言：)[^\n,，]+', content)
        if lang_match:
            patterns["按语言分布"][lang_match.group().strip()] += 1
    
    return patterns

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Minis 知识关联分析器")
    parser.add_argument("--days", type=int, default=14, help="扫描天数（默认14）")
    parser.add_argument("--obsidian", action="store_true", help="同时扫描 Obsidian vault")
    args = parser.parse_args()

    logs = scan_daily_logs(args.days)
    
    print("=" * 50)
    print(f"  🧠 Minis 知识关联分析")
    print(f"  📅 覆盖 {args.days} 天 ({len(logs)} 篇日志)")
    print("=" * 50)
    
    # 1. 话题趋势
    print("\n📈 跨天话题趋势（L3 晋升候选）")
    print("-" * 40)
    promotions = suggest_l3_promotions(logs)
    if promotions:
        print(f"{'话题':<16} {'天':>4} {'频次':>4} {'日期'}")
        print(f"{'-'*16} {'-'*4} {'-'*4} {'-'*30}")
        for p in promotions:
            dates_str = "、".join(p["dates"])
            print(f"{p['topic']:<16} {p['day_span']:>4} {p['total_mentions']:>4}  {dates_str}")
    else:
        print("  暂无符合晋升条件的跨天话题。")
    
    # 2. 概念云
    print("\n🏷️  高频概念")
    print("-" * 40)
    all_concepts = []
    for _, text in logs.items():
        all_concepts.extend(extract_concepts(text))
    concept_counter = Counter(c[0] for c in all_concepts)
    for concept, count in concept_counter.most_common(10):
        bar = "█" * min(count, 12)
        print(f"  {concept:<20} {bar} {count}")
    
    # 3. 交叉引用
    obsidian_files = {}
    if args.obsidian:
        obsidian_files = scan_obsidian_vault()
    cross_refs = find_cross_references(logs, obsidian_files)
    print(f"\n🔗 交叉引用 ({len(cross_refs)} 个)")
    print("-" * 40)
    ref_counter = Counter(r[1] for r in cross_refs)
    for ref, count in ref_counter.most_common(5):
        print(f"  {ref} (×{count})")
    
    # 4. Obsidian 统计
    if obsidian_files:
        obs_patterns = find_obsidian_patterns(obsidian_files)
        print(f"\n📚 Obsidian 知识库")
        print("-" * 40)
        print(f"  AI工具归档: {obs_patterns.get('AI工具归档数', 0)} 篇")
        if obs_patterns.get("按语言分布"):
            print(f"  按语言: {dict(obs_patterns['按语言分布'])}")
    
    # 5. L3 建议
    print("\n📋 L3 晋升建议")
    print("-" * 40)
    if promotions:
        for i, p in enumerate(promotions[:5], 1):
            print(f"  {i}. **{p['topic']}** — {p['reason']}")
            print(f"     → 建议：写入 L3-knowledge-graph.md 作为新节点")
    else:
        print("  本期暂无晋升建议。")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()