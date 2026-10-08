#!/usr/bin/env python3
"""
team-launch.py — 团队启动器

功能：
  1. 加载团队配置
  2. 初始化成员状态
  3. 分配初始任务
  4. 启动创作流程
"""

import sys
import json
from pathlib import Path
from datetime import datetime


def main():
    base_path = Path("team")
    members_file = base_path / "members.json"
    skills_file = base_path / "skills-config.json"
    
    # 加载配置
    members = json.loads(members_file.read_text())
    skills = json.loads(skills_file.read_text())
    
    # 输出团队状态
    print("=" * 60)
    print("小说团队 · 启动状态")
    print("=" * 60)
    print()
    
    print(f"团队名称：{members.get('team_name', '小说创作团队')}")
    print(f"版本：{members.get('version', '1.0.0')}")
    print(f"成员数：{len(members.get('members', []))}人")
    print(f"技能数：{len(skills.get('skill_definitions', {}))}项")
    print()
    
    # 成员状态
    print("【成员状态】")
    print("-" * 60)
    for m in members.get("members", []):
        status = "✅ 就绪" if m.get("status") == "active" else "⏸️ 暂停"
        training = m.get("training_status", "pending")
        cert = m.get("certification_level", 0)
        cert_str = ["未认证", "初级", "资深", "专家"][min(cert, 3)]
        print(f"  {m['name']:12s} | {m['role']:15s} | {status} | {cert_str}")
    print()
    
    # 部门状态
    print("【部门状态】")
    print("-" * 60)
    for dept in members.get("departments", []):
        head = next((m['name'] for m in members.get("members", []) if m["id"] == dept["head"]), "Unknown")
        print(f"  {dept['name']:12s} | 负责人：{head}")
    print()
    
    # 技能流程
    print("【核心流程】")
    print("-" * 60)
    for flow_name, flow in skills.get("skill_flows", {}).items():
        steps = len(flow.get("steps", []))
        print(f"  {flow_name}: {steps}步")
    print()
    
    # 初始任务
    print("【待执行任务】")
    print("-" * 60)
    tasks = [
        ("director", "审核项目配置", "high"),
        ("lead_writer", "创作第1章", "high"),
        ("world_builder", "完善世界包", "medium"),
        ("outline_designer", "细化大纲", "medium"),
        ("editor", "建立门禁流程", "medium"),
        ("style_optimizer", "准备去AI味工具", "low"),
        ("analyst", "创建统计模板", "low"),
    ]
    for role, task, priority in tasks:
        icon = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
        print(f"  {icon} [{priority}] {task} → {role}")
    print()
    
    print("=" * 60)
    print("✅ 团队已就绪，可以开始创作")
    print("=" * 60)


if __name__ == "__main__":
    main()
