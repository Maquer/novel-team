#!/usr/bin/env python3
# Version: 0.1.0
"""
Automation Template Registry — 借鉴 Agent Canvas 预置自动化模板

Agent Canvas 概念：预置自动化工作流（如 "GitHub Issue → 自动分解任务"、
"定时生成报告推送到 Slack"），用户可直接使用或自定义。

Minis 映射：每个模板 = 有序的多步操作序列（每步是 minis-cli 命令或 shell 命令），
调度器触发或手动运行。

用法:
  python3 automation-registry.py list            # 查看模板列表
  python3 automation-registry.py init            # 初始化预置模板
  python3 automation-registry.py show <name>     # 查看模板详情
  python3 automation-registry.py run <name>      # 运行模板
  python3 automation-registry.py add <name>      # 添加自定义模板
  python3 automation-registry.py remove <name>   # 删除模板
  python3 automation-registry.py run-last <name> # 查看上次运行

设计灵感: Agent Canvas (https://github.com/OpenHands/OpenHands) 自动化引擎
"""

import logging

logger = logging.getLogger(__name__)
import json, os, sys, subprocess, shlex, argparse, time
from pathlib import Path
from datetime import datetime

REGISTRY_FILE = "/var/minis/shared/.automation-registry.json"
LOG_DIR = "/var/minis/shared/.scheduler"

# ===== 预置自动化模板 =====
DEFAULT_TEMPLATES = {
    "weekly-audit": {
        "name": "weekly-audit",
        "label": "周度知识审计",
        "description": "完整的知识库健康审计：搜索+图谱+交叉验证+盲区+标签",
        "steps": [
            {"cmd": "minis graph", "label": "知识图谱构建", "timeout": 60},
            {"cmd": "minis crossq", "label": "交叉验证", "timeout": 60},
            {"cmd": "minis blindspot", "label": "认知盲区", "timeout": 30},
            {"cmd": "minis tag", "label": "标签审计", "timeout": 30},
            {"cmd": "minis analytics", "label": "搜索热度分析", "timeout": 30},
        ],
        "schedule": "weekly",
        "tags": ["maintenance", "knowledge"],
    },
    "content-pipeline": {
        "name": "content-pipeline",
        "label": "内容生产流水线",
        "description": "从选题到发布的完整内容生产流程",
        "steps": [
            {"cmd": "minis distill --review", "label": "审核待发布卡片", "timeout": 30},
            {"cmd": "minis tiering", "label": "内容分层处理", "timeout": 30},
        ],
        "schedule": "daily",
        "tags": ["content", "publish"],
    },
    "skill-health": {
        "name": "skill-health",
        "label": "Skill 健康检查",
        "description": "评估所有 Skill 的质量、一致性、过期状态",
        "steps": [
            {"cmd": "minis registry", "label": "Skill 注册表扫描", "timeout": 30},
            {"cmd": "minis eval", "label": "Skill 评测门禁", "timeout": 60},
            {"cmd": "minis lifecycle", "label": "Skill 生命周期检查", "timeout": 30},
        ],
        "schedule": "weekly",
        "tags": ["maintenance", "skill"],
    },
    "memory-compaction": {
        "name": "memory-compaction",
        "label": "记忆压缩",
        "description": "L1→L2 周报生成 + L2→L3 晋升建议",
        "steps": [
            {"cmd": "minis rollup", "label": "L1→L2 周报", "timeout": 30},
            {"cmd": "minis sync", "label": "Obsidian 双向同步", "timeout": 30},
        ],
        "schedule": "weekly",
        "tags": ["memory", "maintenance"],
    },
    "deep-train": {
        "name": "deep-train",
        "label": "深度训练",
        "description": "全量训练流水线（替代手动 train 命令）",
        "steps": [
            {"cmd": "bash /var/minis/shared/second-brain-pulse.sh", "label": "训练脉冲", "timeout": 60},
            {"cmd": "minis dashboard", "label": "健康仪表盘", "timeout": 30},
            {"cmd": "minis feedback", "label": "反馈层检查", "timeout": 30},
            {"cmd": "minis auto-learn", "label": "自动学习", "timeout": 60},
        ],
        "schedule": "daily",
        "tags": ["training", "maintenance"],
    },
    "error-pattern": {
        "name": "error-pattern",
        "label": "错误模式学习",
        "description": "检查并修复已记录的错误模式",
        "steps": [
            {"cmd": "minis error-learn", "label": "错误模式学习与修复", "timeout": 60},
        ],
        "schedule": "weekly",
        "tags": ["learning", "maintenance"],
    },
}


def load_registry():
    if Path(REGISTRY_FILE).exists():
        with open(REGISTRY_FILE) as f:
            return json.load(f)
    return {"templates": {}, "run_log": {}}


def save_registry(data):
    with open(REGISTRY_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def init_default():
    reg = load_registry()
    templates = reg.get("templates", {})
    changed = False
    for name, tpl in DEFAULT_TEMPLATES.items():
        if name not in templates:
            templates[name] = tpl
            changed = True
    if changed:
        reg["templates"] = templates
        save_registry(reg)
        print(f"✅ 预置模板初始化完成，共 {len(templates)} 个")
    else:
        print(f"ℹ️  模板已存在，共 {len(templates)} 个")


def cmd_list():
    reg = load_registry()
    templates = reg.get("templates", {})
    print("\n📋 自动化模板列表")
    print("=" * 60)
    if not templates:
        print("  (空) — 运行 `automation-registry.py init` 初始化预置模板")
        return
    for name, tpl in sorted(templates.items()):
        steps_str = f"{len(tpl.get('steps', []))}步"
        last_run = reg.get("run_log", {}).get(name, {}).get("last_run", "从未")
        status = "✅" if last_run != "从未" else "⬜"
        print(f"  {status} {name:20s} | {tpl.get('label', name):16s} | {steps_str:>4s} | 上次: {last_run[:16]}")
    print(f"\n  共 {len(templates)} 个模板")


def cmd_show(name):
    reg = load_registry()
    tpl = reg.get("templates", {}).get(name)
    if not tpl:
        print(f"❌ 模板 '{name}' 不存在")
        return
    run_info = reg.get("run_log", {}).get(name, {})
    print(f"\n{'='*50}")
    print(f"  模板: {name} ({tpl.get('label', name)})")
    print(f"{'='*50}")
    print(f"  描述: {tpl.get('description', '')}")
    print(f"  计划: {tpl.get('schedule', 'manual')}")
    print(f"  标签: {', '.join(tpl.get('tags', [])) or '(无)'}")
    print(f"\n  步骤:")
    for i, step in enumerate(tpl.get("steps", []), 1):
        print(f"    {i}. [{step.get('label', step['cmd'])[:40]}]")
        print(f"       命令: {step['cmd']}")
        print(f"       超时: {step.get('timeout', 30)}s")
    if run_info:
        print(f"\n  运行状态: 上次={run_info.get('last_run', '从未')}, 结果={run_info.get('status', 'N/A')}")


def cmd_add(args):
    reg = load_registry()
    templates = reg.get("templates", {})
    name = args.name
    if name in templates:
        print(f"⚠️  模板 '{name}' 已存在")
        return
    # 解析 steps
    steps = []
    if args.steps:
        for s in args.steps.split(";"):
            s = s.strip()
            if not s:
                continue
            parts = s.split("|", 1)
            cmd = parts[0].strip()
            label = parts[1].strip() if len(parts) > 1 else cmd[:30]
            timeout = int(parts[2].strip()) if len(parts) > 2 else 30
            steps.append({"cmd": cmd, "label": label, "timeout": timeout})
    tpl = {
        "name": name,
        "label": args.label or name,
        "description": args.description or "",
        "steps": steps,
        "schedule": args.schedule or "manual",
        "tags": [t.strip() for t in (args.tags or "").split(",") if t.strip()],
    }
    templates[name] = tpl
    reg["templates"] = templates
    save_registry(reg)
    print(f"✅ 模板 '{name}' 已添加 ({len(steps)} 步)")


def cmd_remove(name):
    reg = load_registry()
    templates = reg.get("templates", {})
    if name not in templates:
        print(f"❌ 模板 '{name}' 不存在")
        return
    del templates[name]
    reg["templates"] = templates
    save_registry(reg)
    print(f"✅ 模板 '{name}' 已删除")


def cmd_run(name):
    reg = load_registry()
    tpl = reg.get("templates", {}).get(name)
    if not tpl:
        print(f"❌ 模板 '{name}' 不存在")
        return
    print(f"\n{'='*50}")
    print(f"  运行模板: {name} ({tpl.get('label', name)})")
    print(f"{'='*50}")
    steps = tpl.get("steps", [])
    results = []
    all_ok = True
    for i, step in enumerate(steps, 1):
        cmd = step["cmd"]
        label = step.get("label", cmd[:40])
        timeout = step.get("timeout", 30)
        print(f"\n  [{i}/{len(steps)}] {label}...")
        t0 = time.time()
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            elapsed = time.time() - t0
            ok = r.returncode == 0
            status = "✅" if ok else "❌"
            print(f"     {status} {elapsed:.1f}s | {r.stdout.strip()[:80] or '(无输出)'}")
            if not ok:
                print(f"     stderr: {r.stderr.strip()[:100]}")
                all_ok = False
            results.append({"step": label, "ok": ok, "elapsed": round(elapsed, 1)})
        except subprocess.TimeoutExpired:
            elapsed = time.time() - t0
            print(f"     ⏰ 超时 ({timeout}s)")
            all_ok = False
            results.append({"step": label, "ok": False, "elapsed": timeout, "error": "timeout"})
        except Exception as e:
            print(f"     ❌ {str(e)[:80]}")
            all_ok = False
            results.append({"step": label, "ok": False, "error": str(e)})

    # 记录运行日志
    run_log = reg.get("run_log", {})
    run_log[name] = {
        "last_run": datetime.now().isoformat(),
        "status": "success" if all_ok else "partial",
        "steps": results,
    }
    reg["run_log"] = run_log
    save_registry(reg)

    print(f"\n{'='*50}")
    ok_count = sum(1 for r in results if r.get("ok"))
    print(f"  完成: {ok_count}/{len(results)} 步 {'✅' if all_ok else '⚠️'}")
    print(f"  详情: {json.dumps(results, ensure_ascii=False)}")


def cmd_run_last(name):
    reg = load_registry()
    info = reg.get("run_log", {}).get(name, {})
    if not info:
        print(f"ℹ️  模板 '{name}' 从未运行过")
        return
    print(f"\n📊 模板 '{name}' 上次运行")
    print(f"  时间: {info.get('last_run', 'N/A')}")
    print(f"  状态: {info.get('status', 'N/A')}")
    for s in info.get("steps", []):
        icon = "✅" if s.get("ok") else "❌"
        print(f"    {icon} {s.get('step', 'N/A')} ({s.get('elapsed', 0)}s)")


def main():
    parser = argparse.ArgumentParser(description="Automation Template Registry")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="查看模板列表")
    sub.add_parser("init", help="初始化预置模板")

    p_show = sub.add_parser("show", help="查看模板详情")
    p_show.add_argument("name")

    p_add = sub.add_parser("add", help="添加自定义模板")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--label", default="")
    p_add.add_argument("--description", default="")
    p_add.add_argument("--steps", required=True, help="步骤序列，格式: cmd|label|timeout;cmd2|label2|timeout2")
    p_add.add_argument("--schedule", default="manual")
    p_add.add_argument("--tags", default="")

    sub.add_parser("remove", aliases=["rm"]).add_argument("name")

    sub.add_parser("run").add_argument("name")
    sub.add_parser("run-last").add_argument("name")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmds = {
        "list": cmd_list,
        "init": init_default,
        "show": lambda: cmd_show(args.name),
        "add": lambda: cmd_add(args),
        "remove": lambda: cmd_remove(args.name),
        "rm": lambda: cmd_remove(args.name),
        "run": lambda: cmd_run(args.name),
        "run-last": lambda: cmd_run_last(args.name),
    }
    cmds.get(args.command, lambda: print(f"未知命令: {args.command}"))()


if __name__ == "__main__":
    main()