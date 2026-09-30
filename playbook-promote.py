#!/usr/bin/env python3
# Version: 0.1.0
"""
playbook-promote.py — 经验晋级为 Playbook（借鉴 OpenOPC Self-Grown）

OpenOPC 核心机制：执行轨迹 → 经验蒸馏 → 重复模式识别 → 晋级为共享 Playbook
新员工入职时自动继承 Playbook，组织知识复利增长。

Minis 映射：
  knowledge-store 卡片 → 话题聚类 → 频次≥阈值 → 晋级 Playbook → 作为默认上下文

用法:
  python3 playbook-promote.py scan          # 扫描知识卡片，聚类话题
  python3 playbook-promote.py list          # 查看已有 Playbook
  python3 playbook-promote.py show <name>   # 查看 Playbook 详情
  python3 playbook-promote.py promote       # 自动晋级（基于频次阈值）
  python3 playbook-promote.py load <name>   # 加载 Playbook 为上下文
  python3 playbook-promote.py merge <n1> <n2> # 合并两个 Playbook
"""

import argparse
import logging

logger = logging.getLogger(__name__), json, os, re, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

STORE_PATH = "/var/minis/shared/.knowledge-store.json"
PLAYBOOK_PATH = "/var/minis/shared/.playbooks.json"

# 晋级阈值：同一话题在 ≥N 张卡片中出现，或跨 ≥M 天出现
PROMOTE_FREQ = 3
PROMOTE_DAYS = 2

# 话题关键词词典（覆盖 Minis 常见领域）
TOPIC_KEYWORDS = {
    "Agent 生态": ["agent", "agent-registry", "代理", "多级", "子代理", "openopc", "agent-canvas"],
    "Skill 进化": ["skill", "skill-registry", "skill-eval", "skill-router", "darwin", "蒸馏", "skillforge"],
    "知识存储": ["knowledge-store", "卡片", "蒸馏", "distill", "grounded", "okf", "tiering"],
    "记忆架构": ["记忆", "daily log", "L2", "L3", "rollup", "全局", "GLOBAL", "memory"],
    "第二大脑": ["obsidian", "第二大脑", "同步", "MCP", "search", "analytics", "graph"],
    "反馈与评估": ["反馈", "PEV", "审计", "评分", "eval", "error", "回归测试", "传感器"],
    "Auto-Learn": ["auto-learn", "自动学习", "训练", "训练管道", "pulse", "仪表盘"],
    "Content Pipeline": ["公众号", "写作", "爆款", "排版", "发布", "转化", "内容", "小红书"],
    "模型配置": ["model", "provider", "deepseek", "gpt", "sensenova", "qwen", "dots", "provider-verify"],
    "错误模式": ["错误", "bug", "修复", "踩坑", "丢失", "workspace", "失败"],
}

# 话题→中文简称映射（用于 Playbook 名称）
TOPIC_LABELS = {
    "Agent 生态": "agent-ecosystem",
    "Skill 进化": "skill-evolution",
    "知识存储": "knowledge-store",
    "记忆架构": "memory-architecture",
    "第二大脑": "second-brain",
    "反馈与评估": "feedback-eval",
    "Auto-Learn": "auto-learn",
    "Content Pipeline": "content-pipeline",
    "模型配置": "model-config",
    "错误模式": "error-patterns",
}


def load_store():
    if not Path(STORE_PATH).exists():
        return {"cards": []}
    with open(STORE_PATH) as f:
        return json.load(f)


def load_playbooks():
    if not Path(PLAYBOOK_PATH).exists():
        return {"playbooks": [], "promoted_at": None}
    with open(PLAYBOOK_PATH) as f:
        return json.load(f)


def save_playbooks(data):
    with open(PLAYBOOK_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_date(card):
    """从卡片标题或时间字段提取日期"""
    title = card.get("title", "")
    # 尝试从标题提取 YYYY-MM-DD 或 YYYY-MM-DD HH
    m = re.search(r'(\d{4}-\d{2}-\d{2})', title)
    if m:
        return m.group(1)
    # 尝试从 updated_at
    ua = card.get("updated_at", "")
    m = re.search(r'(\d{4}-\d{2}-\d{2})', ua)
    if m:
        return m.group(1)
    return "unknown"


def match_topics(card):
    """匹配卡片所属话题"""
    text = json.dumps(card, ensure_ascii=False).lower()
    matched = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                matched.append(topic)
                break
    return matched


def scan_cards():
    """扫描所有知识卡片，按话题聚类"""
    store = load_store()
    cards = store.get("cards", [])

    # 话题→卡片列表
    topic_cards = defaultdict(list)
    topic_days = defaultdict(set)  # 话题→出现的日期集合
    unmatched = []

    for card in cards:
        topics = match_topics(card)
        if not topics:
            unmatched.append(card.get("title", "?"))
            continue
        day = extract_date(card)
        for t in topics:
            topic_cards[t].append(card)
            topic_days[t].add(day)

    return topic_cards, topic_days, unmatched


def list_playbooks():
    data = load_playbooks()
    print("\n📚 Playbook 库")
    print("=" * 70)
    if not data.get("playbooks"):
        print("  （空 — 运行 scan + promote 来生成 Playbook）")
        return
    for pb in data["playbooks"]:
        topics = pb.get("topics", [])
        days = pb.get("spanning_days", 0)
        cards_n = len(pb.get("card_ids", []))
        score = pb.get("score", 0)
        auto = "🤖自动" if pb.get("auto_promoted") else "👤手动"
        print(f"  {pb['name']:<20} | {auto} | {score:>4}分 | {days}天 | {cards_n}卡片 | {', '.join(topics)}")
    print(f"\n  最后晋级: {data.get('promoted_at', '从未')}")
    print()


def show_playbook(name):
    data = load_playbooks()
    store = load_store()
    cards = store.get("cards", [])

    pb = next((p for p in data["playbooks"] if p["name"] == name), None)
    if not pb:
        print(f"❌ 未找到 Playbook: {name}")
        return

    print(f"\n📖 Playbook: {pb['name']}")
    print(f"   描述: {pb.get('description', '')}")
    print(f"   来源话题: {', '.join(pb.get('topics', []))}")
    print(f"   时间跨度: {pb.get('spanning_days', 0)} 天")
    print(f"   评分: {pb.get('score', 0)}")
    print(f"   晋级方式: {'自动' if pb.get('auto_promoted') else '手动'}")
    print(f"   创建时间: {pb.get('created_at', '?')[:19]}")
    print(f"   最后更新: {pb.get('updated_at', '?')[:19]}")
    print(f"\n   核心经验 ({len(pb.get('lessons', []))} 条):")
    for i, lesson in enumerate(pb.get("lessons", []), 1):
        print(f"     {i}. {lesson[:100]}")

    # 关联的原始卡片
    card_ids = pb.get("card_ids", [])
    if card_ids:
        print(f"\n   关联知识卡片 ({len(card_ids)} 张):")
        for cid in card_ids[:10]:
            match = next((c for c in cards if c.get("id") == cid or c.get("title") == cid), None)
            title = match.get("title", cid) if match else cid
            print(f"     - {title[:80]}")
        if len(card_ids) > 10:
            print(f"     ... 还有 {len(card_ids)-10} 张")
    print()


def promote():
    """自动晋级：扫描卡片→话题聚类→达到阈值则晋级"""
    data = load_playbooks()
    existing = {p["name"] for p in data.get("playbooks", [])}
    topic_cards, topic_days, unmatched = scan_cards()

    promoted = []
    skipped = []

    for topic, cards in sorted(topic_cards.items()):
        if len(cards) < PROMOTE_FREQ:
            skipped.append((topic, len(cards), f"频次不足(需{PROMOTE_FREQ})"))
            continue
        days = len(topic_days.get(topic, set()))
        if days < PROMOTE_DAYS:
            skipped.append((topic, len(cards), f"时间跨度不足(需{PROMOTE_DAYS}天)"))
            continue

        name = TOPIC_LABELS.get(topic, topic.replace(" ", "-").lower())
        if name in existing:
            skipped.append((topic, len(cards), "已存在"))
            continue

        # 提取核心经验（卡片标题/摘要去重）
        lessons = []
        seen = set()
        for c in sorted(cards, key=lambda x: extract_date(x)):
            title = c.get("title", "")[:100]
            # 去除时间戳后缀
            title_clean = re.sub(r'\s*[（(]\d{4}-\d{2}-\d{2}[T\d:\-]*[）)]', '', title).strip()
            if title_clean and title_clean not in seen:
                seen.add(title_clean)
                lessons.append(title_clean)

        # 评分：基于卡片数×时间跨度
        score = min(len(cards) * 20 + days * 10, 100)

        pb = {
            "name": name,
            "description": f"从 {len(cards)} 张卡片、{days} 天数据自动晋级的经验总结：{topic}",
            "topics": [topic],
            "lessons": lessons,
            "card_ids": [c.get("id", c.get("title", "")) for c in cards],
            "spanning_days": days,
            "score": score,
            "auto_promoted": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        data["playbooks"].append(pb)
        promoted.append((topic, len(cards), days, score))

    data["promoted_at"] = datetime.now().isoformat()
    save_playbooks(data)

    print("\n📈 Playbook 晋级报告")
    print("=" * 70)
    if promoted:
        print(f"\n  ✅ 晋级 {len(promoted)} 个 Playbook:")
        for topic, cnt, days, score in promoted:
            name = TOPIC_LABELS.get(topic, topic)
            print(f"    {name:<20} | {cnt}卡片 × {days}天 → {score}分")
    else:
        print("\n  ⚪ 无新晋级")

    if skipped:
        print(f"\n  ⏭️ 跳过 {len(skipped)} 个话题:")
        for topic, cnt, reason in skipped:
            print(f"    {topic:<20} | {cnt}卡片 | {reason}")

    if unmatched:
        print(f"\n  🔍 未匹配话题的卡片 ({len(unmatched)} 张):")
        for t in unmatched[:5]:
            print(f"    - {t[:70]}")
        if len(unmatched) > 5:
            print(f"    ... 还有 {len(unmatched)-5} 张")
    print()

    return len(promoted)


def load_playbook(name):
    """加载 Playbook，输出可直接作为系统提示词的上下文"""
    data = load_playbooks()
    pb = next((p for p in data["playbooks"] if p["name"] == name), None)
    if not pb:
        print(f"❌ 未找到 Playbook: {name}")
        return

    output = {
        "playbook": pb["name"],
        "description": pb.get("description", ""),
        "topics": pb.get("topics", []),
        "lessons": pb.get("lessons", []),
        "score": pb.get("score", 0),
        "prompt_snippet": build_prompt(pb),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def build_prompt(pb):
    """将 Playbook 转为可作为 system prompt 附加的文本"""
    lessons = pb.get("lessons", [])
    if not lessons:
        return ""
    lines = [f"## 经验 Playbook: {pb['name']}"]
    lines.append(f"来源: {', '.join(pb.get('topics', []))} | 评分: {pb.get('score', 0)} | 跨度: {pb.get('spanning_days', 0)}天")
    lines.append(f"核心经验 ({len(lessons)} 条):")
    for i, lesson in enumerate(lessons[:15], 1):
        lines.append(f"  {i}. {lesson}")
    if len(lessons) > 15:
        lines.append(f"  ... 还有 {len(lessons)-15} 条")
    return "\n".join(lines)


def merge(name1, name2, merged_name=None):
    """合并两个 Playbook"""
    data = load_playbooks()
    pbs = data.get("playbooks", [])

    pb1 = next((p for p in pbs if p["name"] == name1), None)
    pb2 = next((p for p in pbs if p["name"] == name2), None)
    if not pb1 or not pb2:
        print(f"❌ 未找到 Playbook: {name1} 或 {name2}")
        return

    merged_name = merged_name or (name1 + "+" + name2)
    merged = {
        "name": merged_name,
        "description": f"合并 {name1} + {name2}: {pb1.get('description','')} / {pb2.get('description','')}",
        "topics": list(set(pb1.get("topics", []) + pb2.get("topics", []))),
        "lessons": list(dict.fromkeys(pb1.get("lessons", []) + pb2.get("lessons", []))),
        "card_ids": list(dict.fromkeys(pb1.get("card_ids", []) + pb2.get("card_ids", []))),
        "spanning_days": max(pb1.get("spanning_days", 0), pb2.get("spanning_days", 0)),
        "score": max(pb1.get("score", 0), pb2.get("score", 0)),
        "auto_promoted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "merged_from": [name1, name2],
    }

    pbs.append(merged)
    data["promoted_at"] = datetime.now().isoformat()
    save_playbooks(data)
    print(f"✅ 合并完成: {name1} + {name2} → {merged_name}")
    print(f"   话题: {', '.join(merged['topics'])}")
    print(f"   经验条数: {len(merged['lessons'])}")
    print(f"   评分: {merged['score']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Playbook 晋级引擎")
    parser.add_argument("action", choices=["scan", "list", "show", "promote", "load", "merge"],
                        help="操作类型")
    parser.add_argument("name", nargs="?", help="Playbook 名称（show/load 使用）")
    parser.add_argument("name2", nargs="?", help="第二个 Playbook 名称（merge 使用）")
    parser.add_argument("--out-name", help="合并后的名称（merge 使用）")
    args = parser.parse_args()

    if args.action == "scan":
        topic_cards, topic_days, unmatched = scan_cards()
        print("\n🔍 话题聚类扫描")
        print("=" * 70)
        total = sum(len(c) for c in topic_cards.values())
        print(f"  总卡片: {total} | 匹配话题: {len(topic_cards)} | 未匹配: {len(unmatched)}")
        print()
        for topic in sorted(topic_cards.keys()):
            cards = topic_cards[topic]
            days = len(topic_days.get(topic, set()))
            name = TOPIC_LABELS.get(topic, topic)
            freq_bar = "█" * min(len(cards), 20)
            print(f"  {name:<20} | {freq_bar:<20} {len(cards):>3}卡片 | {days}天 | {'✅ 可晋级' if len(cards)>=PROMOTE_FREQ and days>=PROMOTE_DAYS else '⏳ 未达标'}")
        print()
    elif args.action == "list":
        list_playbooks()
    elif args.action == "show":
        if not args.name:
            print("❌ 请指定 Playbook 名称")
            sys.exit(1)
        show_playbook(args.name)
    elif args.action == "promote":
        promote()
    elif args.action == "load":
        if not args.name:
            print("❌ 请指定 Playbook 名称")
            sys.exit(1)
        load_playbook(args.name)
    elif args.action == "merge":
        if not args.name or not args.name2:
            print("❌ 请指定两个 Playbook 名称")
            sys.exit(1)
        merge(args.name, args.name2, args.out_name)


if __name__ == "__main__":
    main()