#!/usr/bin/env python3
# Version: 0.1.0
"""
agent-experience.py — Agent 经验档案（借鉴 OpenOPC Self-Grown 员工经验）

OpenOPC 机制：每个"员工"有个人经验档案，记录任务成败模式、偏好、教训。
新用户入职时继承组织 Playbook，老员工则带上历史经验。

Minis 映射：每个 agent backend 是一个"员工"，执行任务时记录结果，
下次同类任务时加载相关经验作为上下文。

用法:
  # 记录一次任务执行结果
  python3 agent-experience.py record --agent coding --task "修bug" --success --quality high

  # 记录教训（含反思）
  python3 agent-experience.py lesson --agent coding --text "用grep先定位再修，别直接改"

  # 查看经验档案
  python3 agent-experience.py profile coding

  # 加载经验为 prompt（可直接附加到 system prompt）
  python3 agent-experience.py load --agent coding --task-type "写代码"

  # 统计概览
  python3 agent-experience.py stats

  # 清理旧经验（>90天）
  python3 agent-experience.py prune --days 90
"""

import argparse, json, os, re, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

EXPERIENCE_PATH = "/var/minis/shared/.agent-experience.json"

# 默认 agent 列表（与 agent-registry 对齐）
KNOWN_AGENTS = [
    "default", "coding", "writing", "xiaohongshu", "research", "decision", "explain",
]

# 任务类型关键词映射
TASK_TYPES = {
    "写代码": ["写代码", "coding", "编程", "debug", "bug", "脚本", "python", "sh"],
    "写文章": ["写文章", "写作", "writing", "公众号", "小红书", "笔记", "文案"],
    "深度分析": ["分析", "分析项目", "决策", "评估", "审计", "审计"],
    "信息收集": ["搜索", "查询", "调研", "research", "查找"],
    "知识管理": ["蒸馏", "归档", "记忆", "知识", "skill", "playbook"],
    "工具操作": ["安装", "配置", "部署", "build", "setup", "初始化"],
}


def load_experience():
    if not Path(EXPERIENCE_PATH).exists():
        return {"agents": {}, "updated_at": None}
    with open(EXPERIENCE_PATH) as f:
        return json.load(f)


def save_experience(data):
    with open(EXPERIENCE_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def classify_task(task_text):
    """根据任务描述分类"""
    text = task_text.lower()
    scores = {}
    for ttype, keywords in TASK_TYPES.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[ttype] = score
    if scores:
        return max(scores, key=scores.get)
    return "其他"


def get_or_create_agent(data, agent_name):
    if agent_name not in data["agents"]:
        data["agents"][agent_name] = {
            "name": agent_name,
            "total_tasks": 0,
            "success_count": 0,
            "failure_count": 0,
            "quality_distribution": {"high": 0, "medium": 0, "low": 0},
            "task_type_history": Counter(),
            "lessons": [],
            "records": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    return data["agents"][agent_name]


def record_task(args):
    data = load_experience()
    agent = get_or_create_agent(data, args.agent)

    task_type = classify_task(args.task)

    record = {
        "task": args.task,
        "task_type": task_type,
        "success": args.success,
        "quality": args.quality or "medium",
        "duration_sec": args.duration if hasattr(args, 'duration') else None,
        "notes": args.notes or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    agent["total_tasks"] += 1
    if args.success:
        agent["success_count"] += 1
    else:
        agent["failure_count"] += 1
    agent["quality_distribution"][args.quality or "medium"] = \
        agent["quality_distribution"].get(args.quality or "medium", 0) + 1
    agent["task_type_history"][task_type] = agent["task_type_history"].get(task_type, 0) + 1
    agent["records"].append(record)
    # 只保留最近 50 条
    if len(agent["records"]) > 50:
        agent["records"] = agent["records"][-50:]
    agent["updated_at"] = datetime.now(timezone.utc).isoformat()

    save_experience(data)
    print(f"✅ 已记录: [{agent['name']}] {args.task[:50]} | 成功={args.success} | 质量={args.quality}")
    print(f"   总计: {agent['total_tasks']}次 | 成功率: {agent['success_count']/max(agent['total_tasks'],1)*100:.0f}%")


def add_lesson(args):
    data = load_experience()
    agent = get_or_create_agent(data, args.agent)

    lesson = {
        "text": args.text,
        "task_type": classify_task(args.task_type or ""),
        "category": args.category or "general",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    agent["lessons"].append(lesson)
    # 只保留最近 30 条
    if len(agent["lessons"]) > 30:
        agent["lessons"] = agent["lessons"][-30:]
    agent["updated_at"] = datetime.now(timezone.utc).isoformat()

    save_experience(data)
    print(f"✅ 已添加经验教训: [{agent['name']}] {args.text[:60]}...")


def show_profile(args):
    data = load_experience()
    agent_name = args.agent or "all"

    if agent_name == "all":
        print("\n📊 Agent 经验档案总览")
        print("=" * 70)
        for aname, adata in data["agents"].items():
            total = adata["total_tasks"]
            if total == 0:
                continue
            success_rate = adata["success_count"] / total * 100
            lessons = len(adata["lessons"])
            top_type = max(adata["task_type_history"].items(), key=lambda x: x[1])[0] if adata["task_type_history"] else "—"
            qd = adata.get("quality_distribution", {})
            print(f"  {aname:<15} | {total:>3}次 | 成功率{success_rate:>5.0f}% | {lessons:>2}条教训 | 主攻:{top_type} | Q:{qd.get('high',0)}H/{qd.get('medium',0)}M/{qd.get('low',0)}L")
        print()
        return

    agent = data["agents"].get(agent_name)
    if not agent:
        print(f"❌ 未找到: {agent_name}")
        return

    total = agent["total_tasks"]
    success_rate = agent["success_count"] / max(total, 1) * 100

    print(f"\n👤 Agent: {agent_name}")
    print("=" * 70)
    print(f"  总任务: {total} | 成功: {agent['success_count']} | 失败: {agent['failure_count']} | 成功率: {success_rate:.0f}%")
    qd = agent.get("quality_distribution", {})
    print(f"  质量分布: 高{qd.get('high',0)} 中{qd.get('medium',0)} 低{qd.get('low',0)}")
    if agent["task_type_history"]:
        print(f"  任务类型: {dict(agent['task_type_history'])}")
    print(f"  创建: {agent['created_at'][:19]} | 最后更新: {agent['updated_at'][:19]}")

    if agent["lessons"]:
        print(f"\n  📝 经验教训 ({len(agent['lessons'])} 条):")
        for l in agent["lessons"][-10:]:
            cat = f"[{l.get('category','')}]" if l.get('category') else ""
            print(f"    - {cat} {l['text'][:80]}")

    if agent["records"]:
        print(f"\n  📋 最近任务 ({len(agent['records'])} 条):")
        for r in agent["records"][-5:]:
            icon = "✅" if r["success"] else "❌"
            print(f"    {icon} [{r['task_type']}] {r['task'][:60]} (质量:{r['quality']})")
    print()


def load_context(args):
    """加载经验为可直接附加到 system prompt 的文本"""
    data = load_experience()
    agent = data["agents"].get(args.agent)
    if not agent:
        print(f"❌ 未找到: {args.agent}")
        return

    task_type = classify_task(args.task_type or "")

    # 1. 匹配该任务类型的历史成功记录
    relevant_records = [
        r for r in agent.get("records", [])
        if r.get("success") and (r.get("task_type") == task_type or not task_type)
    ][:5]

    # 2. 匹配该任务类型的教训
    relevant_lessons = [
        l for l in agent.get("lessons", [])
        if l.get("task_type") == task_type or not task_type
    ][:5]

    # 3. 全局教训
    general_lessons = [
        l for l in agent.get("lessons", [])
        if l.get("category") == "general"
    ][:3]

    lines = []
    lines.append(f"## Agent 经验: {args.agent}")
    lines.append(f"总任务: {agent['total_tasks']} | 成功率: {agent['success_count']/max(agent['total_tasks'],1)*100:.0f}%")

    if relevant_lessons:
        lines.append(f"\n### 相关教训 ({task_type}):")
        for l in relevant_lessons:
            lines.append(f"- {l['text']}")

    if general_lessons:
        lines.append(f"\n### 通用经验:")
        for l in general_lessons:
            lines.append(f"- {l['text']}")

    if relevant_records:
        lines.append(f"\n### 成功模式 (最近 {len(relevant_records)} 次):")
        for r in relevant_records:
            lines.append(f"- {r['task'][:60]}")

    if not relevant_lessons and not general_lessons and not relevant_records:
        lines.append("（暂无相关经验）")

    output = {
        "agent": args.agent,
        "task_type": task_type,
        "prompt_snippet": "\n".join(lines),
        "lesson_count": len(relevant_lessons) + len(general_lessons),
        "success_rate": f"{agent['success_count']/max(agent['total_tasks'],1)*100:.0f}%",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def show_stats():
    data = load_experience()
    total_agents = len(data["agents"])
    total_tasks = sum(a["total_tasks"] for a in data["agents"].values())
    total_success = sum(a["success_count"] for a in data["agents"].values())
    total_lessons = sum(len(a["lessons"]) for a in data["agents"].values())

    print("\n📈 全局经验统计")
    print("=" * 70)
    print(f"  Agent 数: {total_agents}")
    print(f"  总任务: {total_tasks}")
    print(f"  总成功: {total_success} ({total_success/max(total_tasks,1)*100:.0f}%)")
    print(f"  总教训: {total_lessons}")
    if total_tasks > 0:
        # 最活跃 agent
        top = max(data["agents"].items(), key=lambda x: x[1]["total_tasks"])
        print(f"  最活跃: {top[0]} ({top[1]['total_tasks']}次)")
    print()


def prune(days):
    data = load_experience()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    pruned = 0
    for aname, adata in data["agents"].items():
        before = len(adata["records"])
        adata["records"] = [r for r in adata["records"] if r.get("timestamp", "") > cutoff_iso]
        before_l = len(adata["lessons"])
        adata["lessons"] = [l for l in adata["lessons"] if l.get("timestamp", "") > cutoff_iso]
        pruned += (before - len(adata["records"])) + (before_l - len(adata["lessons"]))

    save_experience(data)
    print(f"🧹 已清理 {pruned} 条旧记录（>{days}天）")
    print()


def main():
    parser = argparse.ArgumentParser(description="Agent 经验档案")
    sub = parser.add_subparsers(dest="action")

    # record
    p_record = sub.add_parser("record", help="记录任务结果")
    p_record.add_argument("--agent", required=True)
    p_record.add_argument("--task", required=True)
    p_record.add_argument("--success", action="store_true", default=True)
    p_record.add_argument("--fail", action="store_false", dest="success")
    p_record.add_argument("--quality", choices=["high", "medium", "low"], default="medium")
    p_record.add_argument("--notes", default="")
    p_record.add_argument("--duration", type=int, default=None)

    # lesson
    p_lesson = sub.add_parser("lesson", help="添加经验教训")
    p_lesson.add_argument("--agent", required=True)
    p_lesson.add_argument("--text", required=True)
    p_lesson.add_argument("--task-type", default="")
    p_lesson.add_argument("--category", default="general")

    # profile
    p_profile = sub.add_parser("profile", help="查看经验档案")
    p_profile.add_argument("--agent", default="all")

    # load
    p_load = sub.add_parser("load", help="加载经验为 prompt 上下文")
    p_load.add_argument("--agent", required=True)
    p_load.add_argument("--task-type", default="")

    # stats
    sub.add_parser("stats", help="全局统计")

    # prune
    p_prune = sub.add_parser("prune", help="清理旧经验")
    p_prune.add_argument("--days", type=int, default=90)

    args = parser.parse_args()

    if args.action == "record":
        record_task(args)
    elif args.action == "lesson":
        add_lesson(args)
    elif args.action == "profile":
        show_profile(args)
    elif args.action == "load":
        load_context(args)
    elif args.action == "stats":
        show_stats()
    elif args.action == "prune":
        prune(args.days)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()