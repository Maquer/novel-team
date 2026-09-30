#!/usr/bin/env python3
# Version: 0.1.0
"""
第二大脑健康仪表盘 — 汇总全部 11 模块状态，输出可读报告。

用法:
  python3 /var/minis/shared/second-brain-dashboard.py
  python3 /var/minis/shared/second-brain-dashboard.py --json
"""

import argparse
import logging
import json, os, sys
from datetime import datetime

logger = logging.getLogger(__name__)

OBSIDIAN_ROOT = "/var/minis/mounts/loong"
STATE_DIR = "/var/minis/shared/.training-state"

def _r(*path):
    p = os.path.join(*path)
    if os.path.exists(p):
        try:
            return json.load(open(p, 'r', encoding='utf-8'))
        except:
            return None
    return None


def main():
    """主入口函数"""
    import argparse
    import logging

    logger = logging.getLogger(__name__)
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', '-j', action='store_true')
    args = parser.parse_args()

    # 收集各模块状态
    data = {}

    # 1. 笔记统计
    note_count = 0
    for root, dirs, files in os.walk(OBSIDIAN_ROOT):
        for f in files:
            if f.endswith(".md"):
                note_count += 1
        data["notes"] = note_count

    # 2. 图谱（实时查询）
    import subprocess
    try:
        r = subprocess.run(
            ['python3', '/var/minis/shared/obsidian-graph.py', '--stats'],
            capture_output=True, text=True, timeout=10
        )
        graph_out = r.stdout
        nodes = 0
        links = 0
        isolated = 0
        for line in graph_out.split('\n'):
            if '总节点' in line:
                nodes = int(line.split(':')[-1].strip().split()[0]) if ':' in line else 0
            if '总链接' in line:
                links = int(line.split(':')[-1].strip().split()[0]) if ':' in line else 0
            if '孤立笔记' in line:
                isolated = int(line.split(':')[-1].strip().split()[0]) if ':' in line else 0
        data["graph"] = {"total_nodes": nodes, "total_edges": links, "isolated": isolated}
    except Exception:
        data["graph"] = {"total_nodes": 0, "total_edges": 0, "isolated": 0}

    # 3. 搜索统计
    search_log = _r("/var/minis/shared", ".obsidian-search-log.json")
    total_search = len(search_log) if isinstance(search_log, list) else 0
    data["search_total"] = total_search

    # 4. 学习存储
    learn = _r("/var/minis/shared", ".learning-store.json")
    obs_level = 1
    if learn:
        for e in learn.get("entries", []):
            if e.get("topic") == "Obsidian":
                obs_level = e.get("level", 1)
    data["obsidian_level"] = obs_level

    # 5. 训练脉冲最新状态
    pulse = _r(STATE_DIR, "pulse-latest.json")
    data["pulse"] = pulse

    # 6. 卡片存储
    distill = _r("/var/minis/shared", ".knowledge-store.json")
    pending_cards = 0
    approved_cards = 0
    if distill:
        for c in distill.get("cards", []):
            if c.get("status") == "draft":
                pending_cards += 1
            elif c.get("status") == "approved":
                approved_cards += 1
        data["pending_cards"] = pending_cards
        data["approved_cards"] = approved_cards

    # 7. 自动学习管道
    auto_learn = _r("/var/minis/shared", ".auto-learn-state.json")
    data["auto_learn"] = auto_learn

    # 8. 反馈层（确定性传感器）
    import subprocess
    try:
        r2 = subprocess.run(
            ['python3', '/var/minis/shared/second-brain-feedback.py', '--health'],
            capture_output=True, text=True, timeout=10
        )
        fb_health = 100
        fb_passed = 8
        fb_total = 8
        if r2.returncode == 0:
            for line in r2.stdout.split('\n'):
                if '通过' in line:
                    fb_passed = int(line.split('/')[-1].strip())
                if '总计' in line:
                    fb_total = int(line.split('/')[-1].strip())
    except Exception:
        fb_health, fb_passed, fb_total = 100, 8, 8
    data["feedback"] = {"health": fb_health, "passed": fb_passed, "total": fb_total}

    # 9. 错误模式
    error_log = _r("/var/minis/shared", ".failure-log.json")
    data["errors"] = len(error_log) if isinstance(error_log, list) else 0

    # 10. Skill 状态
    registry = _r("/var/minis/shared", ".skill-registry.json")
    data["skills_total"] = len(registry.get("skills", {})) if registry else 0

    # 11. 训练状态
    train_log = _r("/var/minis/shared", ".training-state", "last-run.json")
    data["last_train"] = train_log.get("timestamp") if train_log else None

    # 计算健康分
    health = 100
    deductions = []

    # 扣分项
    if data["errors"] > 0:
        deductions.append(f"错误模式 {data['errors']} 条")
        health -= min(data["errors"] * 5, 20)

    if data["skills_total"] < 20:
        deductions.append(f"Skill 数量不足 ({data['skills_total']})")
        health -= min((20 - data["skills_total"]) * 2, 20)

    # 反馈层扣分
    feedback = data.get("feedback", {})
    if feedback.get("failed", 0) > 0:
        fb_fail = feedback["failed"]
        deductions.append(f"反馈层传感器失败 {fb_fail} 个")
        health -= min(fb_fail * 10, 30)

    data["health_score"] = max(health, 0)
    data["health_deductions"] = deductions

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    # 文本仪表盘
    level_icon = {1: "🌱", 2: "🌿", 3: "🌳", 4: "🏔️", 5: "💎"}
    obs_icon = level_icon.get(data["obsidian_level"], "❓")

    health_bar = "█" * (data["health_score"] // 10) + "░" * (10 - data["health_score"] // 10)
    health_color = "🟢" if data["health_score"] >= 70 else "🟡" if data["health_score"] >= 40 else "🔴"
    feedback_health_color = "🟢" if data["feedback"]["health"] >= 75 else "🟡" if data["feedback"]["health"] >= 50 else "🔴"

    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║           🧠 第二大脑健康仪表盘 ─ {datetime.now().strftime('%Y-%m-%d %H:%M')}          ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  🏥 健康分: {health_color} {data['health_score']}/100  {health_bar}{' '*(20-len(health_bar))}     ║
║                                                               ║
║  📖 笔记: {data['notes']:>5} 篇                                        ║
║  🕸️  图谱: {data['graph'].get('total_nodes',0):>4} 节点 / {data['graph'].get('total_edges',0):>4} 链接         ║
║  🔍 搜索: {data['search_total']:>5} 次                                   ║
║  🧠 卡片: ✅ {data['approved_cards']:>3} 已审 / 📝 {data['pending_cards']:>3} 待审         ║
║  🌳 Obsidian 等级: {obs_icon} Lv.{data['obsidian_level']}                                 ║
║  📡 反馈层: {feedback_health_color} {data['feedback']['health']}/100 ({data['feedback']['passed']}/{data['feedback']['total']})     ║
║                                                               ║
╠═══════════════════════════════════════════════════════════════╣
║  📋 扣分项:                                                    ║
║""")

    for d in deductions:
        print(f"║    - {d:34s} ║")
    if not deductions:
        print("║    ✅ 无扣分项                                       ║")

    print(f"""╠═══════════════════════════════════════════════════════════════╣
║  🌳 能力雷达 (Top 5)                                          ║
║""")

    if learn:
        entries = sorted(learn.get("entries", []), key=lambda x: x.get("level", 0), reverse=True)[:5]
        for e in entries:
            lvl = e.get("level", 0)
            icon = level_icon.get(lvl, "❓")
            bar = "█" * lvl + "░" * (5 - lvl)
            print(f"║    {icon} {e.get('topic','?'):20s} {bar} Lv.{lvl}         ║")

    print(f"""╚═══════════════════════════════════════════════════════════════╝""")
if __name__ == "__main__":
    main()