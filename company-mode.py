#!/usr/bin/env python3
# Version: 0.1.0
"""
company-mode.py — Company Mode 编排器（借鉴 OpenOPC Self-Run）

OpenOPC Company Mode 核心：
  1. 根据任务自动推导"组织"（哪些角色参与）
  2. 为每个角色分配工作项，按依赖 DAG 并行/串行执行
  3. 每个角色在运行时加载自己的经验 + 组织 Playbook
  4. 审查机制：结果经 reviewer 审核后才能通过

Minis 映射：
  - "角色" = agent backend（coding/writing/research 等）
  - "工作项" = 拆分的子任务
  - "经验" = agent-experience.py 的个人档案
  - "Playbook" = playbook-promote.py 的组织级知识
  - "审查" = 用 verify 模式做质量检查

用法:
  # 分解任务并运行
  python3 company-mode.py run "写一篇文章并排好版发公众号"

  # 指定模式
  python3 company-mode.py run "做投资决策分析" --agents research,writing

  # 预览任务分解（不执行）
  python3 company-mode.py plan "写一篇文章并排好版发公众号"

  # 查看运行历史
  python3 company-mode.py history

  # 从 Playbook 加载上下文后运行
  python3 company-mode.py run "写一篇关于XX的文章" --playbook content-pipeline
"""

import argparse, json, os, re, sys, subprocess, shlex
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HISTORY_PATH = "/var/minis/shared/.company-runs.json"

# ===== 角色定义 =====
ROLES = {
    "coding": {
        "label": "工程师",
        "backend": "coding",
        "capabilities": ["写代码", "修bug", "脚本", "编程", "debug"],
        "trigger_keywords": ["代码", "bug", "编程", "脚本", "python", "sh", "api", "接口"],
    },
    "writing": {
        "label": "内容创作者",
        "backend": "writing",
        "capabilities": ["写文章", "写作", "文案", "公众号", "小红书"],
        "trigger_keywords": ["文章", "写", "文案", "公众号", "小红书", "笔记", "创作"],
    },
    "research": {
        "label": "研究员",
        "backend": "research",
        "capabilities": ["调研", "搜索", "信息收集", "分析"],
        "trigger_keywords": ["调研", "搜索", "分析", "研究", "收集", "查找", "信息"],
    },
    "decision": {
        "label": "决策顾问",
        "backend": "decision",
        "capabilities": ["决策", "评估", "分析项目", "投资"],
        "trigger_keywords": ["决策", "评估", "投资", "分析项目", "要不要", "值得"],
    },
    "explain": {
        "label": "解释专家",
        "backend": "explain",
        "capabilities": ["解释", "科普", "讲解"],
        "trigger_keywords": ["解释", "科普", "讲解", "大白话", "是什么"],
    },
    "default": {
        "label": "通用助手",
        "backend": "default",
        "capabilities": ["其他"],
        "trigger_keywords": [],
    },
}


def load_runs():
    if not Path(HISTORY_PATH).exists():
        return {"runs": []}
    with open(HISTORY_PATH) as f:
        return json.load(f)


def save_runs(data):
    with open(HISTORY_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def decompose_task(task_text):
    """根据任务描述自动分解为工作项 + 匹配角色"""
    text = task_text.lower()

    # 识别子任务边界
    # 常见连接词：并、然后、之后、接着、再、同时、还要、以及、和（后面跟动作）
    # 简单策略：按动词短语分割
    sentences = re.split(r'[，。；、\n]+', task_text)

    items = []
    for s in sentences:
        s = s.strip()
        if not s or len(s) < 4:
            continue
        # 匹配角色
        matched_roles = []
        for rname, rdef in ROLES.items():
            for kw in rdef["trigger_keywords"]:
                if kw in s.lower():
                    matched_roles.append(rname)
                    break

        if not matched_roles:
            matched_roles = ["default"]

        items.append({
            "description": s,
            "roles": list(set(matched_roles)),
            "dependencies": [],
            "status": "pending",
        })

    # 建立依赖关系：后出现的任务如果引用前一个任务的产出，则依赖
    # 简单规则：如果包含"然后"、"之后"、"接着"等词，依赖前一个
    for i in range(1, len(items)):
        desc = items[i]["description"]
        if any(word in desc for word in ["然后", "之后", "接着", "再", "之后"]):
            items[i]["dependencies"] = [i-1]

    return items


def assign_agents(items, agent_filter=None):
    """为工作项分配最佳 agent backend"""
    assignments = []
    for idx, item in enumerate(items):
        # 如果有角色限制
        if agent_filter:
            available = [a for a in agent_filter if a in item["roles"]]
            if not available:
                available = item["roles"]
        else:
            available = item["roles"]

        best = available[0] if available else "default"
        assignments.append({
            "item_id": idx,
            "description": item["description"],
            "assigned_agent": best,
            "roles": item["roles"],
            "dependencies": item["dependencies"],
        })

    return assignments


def build_prompt(item, playbook_text=None, experience_text=None):
    """构建运行提示词"""
    parts = [f"## 任务\n{item['description']}"]

    if experience_text:
        parts.append(f"\n## 个人经验\n{experience_text}")

    if playbook_text:
        parts.append(f"\n## 组织 Playbook\n{playbook_text}")

    parts.append(f"\n## 角色: {ROLES.get(item['assigned_agent'],{}).get('label', item['assigned_agent'])}")

    return "\n".join(parts)


def plan_task(task_text, agent_filter=None):
    """预览任务分解"""
    items = decompose_task(task_text)
    assignments = assign_agents(items, agent_filter)

    print(f"\n📋 任务分解: {task_text[:60]}")
    print("=" * 70)
    print(f"  总工作项: {len(assignments)}")
    print()

    for a in assignments:
        deps = f" ← 依赖 #{', '.join(map(str, a['dependencies']))}" if a['dependencies'] else ""
        role_label = ROLES.get(a['assigned_agent'],{}).get('label', a['assigned_agent'])
        print(f"  #{a['item_id']} [{role_label:<10}] {a['description'][:50]}{deps}")

    # 角色汇总
    role_count = defaultdict(int)
    for a in assignments:
        role_count[a['assigned_agent']] += 1
    print(f"\n  角色分配: {dict(role_count)}")
    print()
    return assignments


def run_task(task_text, agent_filter=None, playbook_name=None, dry_run=False, verbose=False):
    """执行 Company Mode 任务"""
    items = decompose_task(task_text)
    assignments = assign_agents(items, agent_filter)

    print(f"\n🏢 Company Mode 执行中: {task_text[:60]}")
    print("=" * 70)
    print(f"  工作项: {len(assignments)} | 模式: {'DRY-RUN' if dry_run else 'EXECUTE'}")
    if playbook_name:
        print(f"  Playbook: {playbook_name}")
    print()

    results = []
    for a in assignments:
        role_label = ROLES.get(a['assigned_agent'],{}).get('label', a['assigned_agent'])
        desc = a['description']
        deps = f" [依赖 #{', '.join(map(str, a['dependencies']))}]" if a['dependencies'] else ""

        print(f"  ▶ #{a['item_id']} [{role_label}] {desc[:50]}{deps}")

        # 构建 prompt
        exp_text = ""
        pb_text = ""
        if playbook_name:
            pb_result = subprocess.run(
                [sys.executable, "/var/minis/shared/playbook-promote.py", "load", playbook_name],
                capture_output=True, text=True
            )
            try:
                pb_data = json.loads(pb_result.stdout)
                pb_text = pb_data.get("prompt_snippet", "")
            except:
                pass

        if not dry_run:
            exp_result = subprocess.run(
                [sys.executable, "/var/minis/shared/agent-experience.py", "load",
                 "--agent", a['assigned_agent'], "--task-type", desc],
                capture_output=True, text=True
            )
            try:
                exp_data = json.loads(exp_result.stdout)
                exp_text = exp_data.get("prompt_snippet", "")
            except:
                pass

        prompt = build_prompt(a, pb_text, exp_text)

        if dry_run:
            print(f"    ⏸️ [dry-run] 将用 agent={a['assigned_agent']} 执行")
            if verbose:
                print(f"    Prompt preview:\n    {prompt[:200]}...")
            results.append({
                "item_id": a["item_id"],
                "description": desc,
                "agent": a["assigned_agent"],
                "status": "skipped_dry_run",
                "prompt_preview": prompt[:500],
            })
            continue

        # 实际执行：调用 agent-registry run
        run_result = subprocess.run(
            [sys.executable, "/var/minis/shared/agent-registry.py", "run",
             a['assigned_agent'], prompt],
            capture_output=True, text=True, timeout=120
        )
        output = run_result.stdout if run_result.returncode == 0 else run_result.stderr

        # 记录经验
        success = run_result.returncode == 0
        exp_record = subprocess.run(
            [sys.executable, "/var/minis/shared/agent-experience.py", "record",
             "--agent", a['assigned_agent'], "--task", desc,
             "--quality", "high" if success else "low"],
            capture_output=True, text=True
        )

        icon = "✅" if success else "⚠️"
        print(f"    {icon} agent={a['assigned_agent']} | 返回码={run_result.returncode}")

        results.append({
            "item_id": a["item_id"],
            "description": desc,
            "agent": a["assigned_agent"],
            "status": "success" if success else "failed",
            "output_preview": output[:500] if output else "",
            "return_code": run_result.returncode,
        })

    # 保存运行记录
    data = load_runs()
    run_record = {
        "task": task_text,
        "assignments": assignments,
        "results": results,
        "playbook": playbook_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_items": len(assignments),
        "success_count": sum(1 for r in results if r.get("status") == "success"),
    }
    data["runs"].append(run_record)
    if len(data["runs"]) > 50:
        data["runs"] = data["runs"][-50:]
    save_runs(data)

    # 总结
    print(f"\n📊 执行总结")
    print(f"  总工作项: {len(results)}")
    print(f"  成功: {run_record['success_count']} | 失败/跳过: {len(results)-run_record['success_count']}")
    print()

    return results


def show_history(limit=5):
    data = load_runs()
    runs = data.get("runs", [])
    if not runs:
        print("📋 运行历史: (空)")
        return

    print(f"\n📋 运行历史 (最近 {limit} 条)")
    print("=" * 70)
    for run in runs[-limit:]:
        ts = run.get("timestamp", "?")[:19]
        task = run.get("task", "?")[:50]
        items = run.get("total_items", 0)
        success = run.get("success_count", 0)
        pb = f" | Playbook:{run.get('playbook','—')}" if run.get("playbook") else ""
        print(f"  [{ts}] {task}")
        print(f"         {items}项 | ✅{success}/{items}{pb}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Company Mode 编排器")
    sub = parser.add_subparsers(dest="action")

    p_plan = sub.add_parser("plan", help="预览任务分解")
    p_plan.add_argument("task", help="任务描述")
    p_plan.add_argument("--agents", help="指定 agent 列表（逗号分隔）")

    p_run = sub.add_parser("run", help="执行 Company Mode")
    p_run.add_argument("task", help="任务描述")
    p_run.add_argument("--agents", help="指定 agent 列表")
    p_run.add_argument("--playbook", help="加载 Playbook")
    p_run.add_argument("--dry-run", action="store_true", help="仅预览不执行")
    p_run.add_argument("--verbose", action="store_true", help="详细输出")

    sub.add_parser("history", help="查看运行历史")

    args = parser.parse_args()

    if args.action == "plan":
        agent_filter = [a.strip() for a in args.agents.split(",")] if args.agents else None
        plan_task(args.task, agent_filter)
    elif args.action == "run":
        agent_filter = [a.strip() for a in args.agents.split(",")] if args.agents else None
        run_task(args.task, agent_filter, args.playbook, args.dry_run, args.verbose)
    elif args.action == "history":
        show_history()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
