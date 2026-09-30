#!/usr/bin/env python3
# Version: 0.1.0
"""
L2 Weekly Rollup — Minis 记忆系统的 Dataview 等价物
自动扫描最近 N 天的 daily logs，聚类话题、统计频次、生成周报。
用法: python3 memory-l2-rollup.py [--days N] [--output PATH]
"""
import argparse
import logging
import re, json, os, sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

MEMORY_DIR = Path("/var/minis/memory")
OUTPUT_DEFAULT = MEMORY_DIR / "L2-weekly-summaries.md"
EXCLUDE_FILES = {"GLOBAL.md", "L2-weekly-summaries.md", "L3-knowledge-graph.md", "SOUL.md"}

# 话题关键词映射（可扩展）
TOPIC_KEYWORDS = {
    "AI工具归档": ["归档", "Stars", "开源", "GitHub", "npm", "安装"],
    "公众号/自媒体": ["公众号", "小红书", "抖音", "文案", "排版", "发布", "爆款"],
    "记忆系统": ["记忆", "L1", "L2", "L3", "L0", "daily", "rollup", "knowledge"],
    "Skill开发": ["skill", "SKILL.md", "SkillLens", "Darwin", "skill-creator"],
    "工作区治理": ["workspace", "丢失", "恢复", "共享", "shared", "backup"],
    "模型/Provider": ["模型", "Provider", "deepseek", "gpt", "sensenova", "OpenRouter"],
}

def read_daily_logs(days=7):
    """读取最近 N 天的 daily log"""
    today = datetime.now()
    logs = []
    for i in range(days):
        date = today - timedelta(days=i)
        fname = date.strftime("%Y-%m-%d.md")
        fpath = MEMORY_DIR / fname
        if fpath.exists():
            text = fpath.read_text(encoding="utf-8")
            logs.append((fname, text))
    # 按时间正序
    logs.sort(key=lambda x: x[0])
    return logs

def extract_headings(text):
    """提取 markdown 标题"""
    return re.findall(r'^##\s+(.+)$', text, re.MULTILINE)

def count_mentions(text, keywords):
    """统计关键词出现次数"""
    count = 0
    for kw in keywords:
        count += text.lower().count(kw.lower())
    return count

def extract_links(text):
    """提取 minis:// 链接"""
    return re.findall(r'minis://[^\s)]+', text)

def detect_decisions(text):
    """检测决策记录（包含'决定'/'决策'/'选择'等关键词的行）"""
    decisions = []
    for line in text.split('\n'):
        if any(w in line for w in ['决定', '决策', '选择', '定稿', '定为', '改为']):
            decisions.append(line.strip())
    return decisions[:5]  # 最多5条

def rollup(days=7):
    """生成 L2 周报"""
    logs = read_daily_logs(days)
    if not logs:
        return "没有可用的 daily log。"

    all_text = "\n".join(t for _, t in logs)
    date_range = f"{logs[0][0][:10]} ~ {logs[-1][0][:10]}"
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 话题聚类
    topic_scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = count_mentions(all_text, keywords)
        if score > 0:
            topic_scores[topic] = score

    # 按得分排序
    sorted_topics = sorted(topic_scores.items(), key=lambda x: -x[1])

    # 各天标题汇总
    daily_headings = {}
    for fname, text in logs:
        daily_headings[fname[:10]] = extract_headings(text)

    # 决策记录
    decisions = detect_decisions(all_text)

    # 统计
    total_entries = sum(len(h) for h in daily_headings.values())
    total_chars = len(all_text)
    links_found = len(extract_links(all_text))

    # 构建输出
    lines = []
    lines.append(f"## L2 周报 ({date_range})")
    lines.append(f"> 自动生成于 {today_str} | 覆盖 {len(logs)} 天")
    lines.append("")
    lines.append("### 📊 概览")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 覆盖天数 | {len(logs)} |")
    lines.append(f"| 标题条目 | {total_entries} |")
    lines.append(f"| 总字数 | {total_chars:,} |")
    lines.append(f"| 链接引用 | {links_found} |")
    lines.append("")

    lines.append("### 🔥 话题热度排行")
    lines.append("| 排名 | 话题 | 热度 |")
    lines.append("|------|------|------|")
    for i, (topic, score) in enumerate(sorted_topics, 1):
        bar = "█" * min(score, 20)
        lines.append(f"| {i} | {topic} | {bar} {score} |")
    lines.append("")

    lines.append("### 📅 每日摘要")
    for date, headings in daily_headings.items():
        lines.append(f"**{date}** ({len(headings)} 条)")
        for h in headings[:6]:
            lines.append(f"- {h}")
        if len(headings) > 6:
            lines.append(f"- ... 及其他 {len(headings)-6} 条")
        lines.append("")

    if decisions:
        lines.append("### ⚡ 关键决策")
        for d in decisions:
            lines.append(f"- {d}")
        lines.append("")

    lines.append("### 📈 趋势洞察")
    lines.append(f"本周 {len(logs)} 天内共产生 {total_entries} 个标题条目。")
    if sorted_topics:
        lines.append(f"最活跃话题：{sorted_topics[0][0]}（热度 {sorted_topics[0][1]}）。")
    if len(sorted_topics) > 1:
        lines.append(f"次活跃：{'、'.join(t[0] for t in sorted_topics[1:4])}。")
    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def append_to_l2(content):
    """追加到 L2 文件"""
    fpath = OUTPUT_DEFAULT
    if fpath.exists():
        existing = fpath.read_text(encoding="utf-8")
    else:
        existing = "# L2 Weekly Summaries\n\n> 由 memory-l2-rollup.py 自动生成\n\n"

    # 检查是否已存在同周期条目，避免重复
    if content.split("(")[1].split(")")[0] in existing:
        print(f"该周期周报已存在，跳过。")
        return

    fpath.write_text(existing + "\n" + content, encoding="utf-8")
    print(f"已追加到 {fpath}")


def query_memory(query, days=7):
    """简易记忆查询（Dataview 简化版）"""
    logs = read_daily_logs(days)
    all_text = "\n".join(t for _, t in logs)
    lines = all_text.split('\n')

    results = []
    for line in lines:
        if query.lower() in line.lower():
            results.append(line.strip())

    return results


if __name__ == "__main__":
    import argparse
import logging

logger = logging.getLogger(__name__)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minis L2 周报自动生成器")
    parser.add_argument("--days", type=int, default=7, help="扫描天数（默认7）")
    parser.add_argument("--query", type=str, help="关键词查询（查询模式）")
    parser.add_argument("--output", type=str, help="输出路径")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写入")
    args = parser.parse_args()

    if args.query:
        # 查询模式
        results = query_memory(args.query, args.days)
        if results:
            print(f"找到 {len(results)} 条匹配:")
            for r in results:
                print(f"  {r}")
        else:
            print("无匹配结果。")
    else:
        # 周报生成模式
        content = rollup(args.days)
        if args.output:
            Path(args.output).write_text(content, encoding="utf-8")
            print(f"已写入 {args.output}")
        elif args.dry_run:
            print(content)
        else:
            append_to_l2(content)