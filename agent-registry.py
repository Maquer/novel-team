#!/usr/bin/env python3
# Version: 0.1.0
"""
Agent Backend Registry — 借鉴 Agent Canvas 多后端切换

Agent Canvas 核心概念：同一控制台管理多个 Agent 后端，
用户可无缝切换本地/Docker/VM/Cloud 的后端，上下文不丢失。

Minis 映射：每个"后端" = 一组 Agent 配置（模型+技能+系统提示词+参数），
用户通过 name 切换"工作模式"，无需每次手动指定所有参数。

用法:
  python3 agent-registry.py list            # 查看后端列表
  python3 agent-registry.py add <name>      # 添加后端
  python3 agent-registry.py remove <name>   # 删除后端
  python3 agent-registry.py use <name>      # 切换到后端
  python3 agent-registry.py current         # 查看当前后端
  python3 agent-registry.py show <name>     # 查看后端详情
  python3 agent-registry.py run <name> "任务描述"  # 用指定后端执行任务
  python3 agent-registry.py run-current "任务描述" # 用当前后端执行任务
  python3 agent-registry.py init            # 初始化默认后端

设计灵感: Agent Canvas (https://github.com/OpenHands/OpenHands) 多后端架构
"""

import logging

logger = logging.getLogger(__name__)
import json, os, sys, subprocess, shlex, argparse
from pathlib import Path
from datetime import datetime

REGISTRY_FILE = "/var/minis/shared/.agent-registry.json"
STATE_FILE = "/var/minis/shared/.agent-current.json"

# ===== 默认后端模板 =====
DEFAULT_BACKENDS = {
    "default": {
        "name": "default",
        "label": "默认通用",
        "model": "agnes-2.5-pro",
        "description": "默认配置，适合一般对话与任务",
        "system_prompt": "",
        "skills": [],
        "temperature": 0.7,
        "max_tokens": 4096,
        "created_at": datetime.now().isoformat(),
    },
    "coding": {
        "name": "coding",
        "label": "编码模式",
        "model": "auto",
        "description": "代码生成/调试/重构，启用编程相关 Skill",
        "system_prompt": "你是专业的 AI 编程助手。优先使用 ponytail 极简编程原则：YAGNI → 复用 → 标准库 → 系统工具 → 已装依赖。用最少的代码解决问题。",
        "skills": ["ponytail"],
        "temperature": 0.3,
        "max_tokens": 8192,
        "created_at": datetime.now().isoformat(),
    },
    "writing": {
        "name": "writing",
        "label": "写作模式",
        "model": "auto",
        "description": "中文写作/内容创作，启用写作相关 Skill",
        "system_prompt": "你是专业的中文内容创作者。文风简洁干练，像靠谱的朋友，不油腻。适合公众号文章、小红书笔记等创作。",
        "skills": ["bao-kuai-xie-zuo", "hai-bao-she-ji", "gongzhonghao-publish"],
        "temperature": 0.8,
        "max_tokens": 8192,
        "created_at": datetime.now().isoformat(),
    },
    "xiaohongshu": {
        "name": "xiaohongshu",
        "label": "小红书模式",
        "model": "auto",
        "description": "小红书笔记创作，智能路由选择最佳模型",
        "system_prompt": "你是小红书内容创作专家。笔记要有网感、有情绪价值、有用。多用 emoji，分段清晰，标题吸引眼球。",
        "skills": ["bao-kuai-xie-zuo"],
        "temperature": 0.9,
        "max_tokens": 4096,
        "created_at": datetime.now().isoformat(),
    },
    "research": {
        "name": "research",
        "label": "研究模式",
        "model": "auto",
        "description": "深度研究/知识检索/分析，启用知识相关 Skill",
        "system_prompt": "你是研究助手。严谨、有据可依、结构化输出。回答前优先检索 Obsidian 知识库和记忆。",
        "skills": [],
        "temperature": 0.5,
        "max_tokens": 8192,
        "created_at": datetime.now().isoformat(),
    },
    "explain": {
        "name": "explain",
        "label": "解释模式",
        "model": "auto",
        "description": "复杂概念简化解释，启用 Explanation Skill",
        "system_prompt": "你是解释专家。用大白话+类比解释任何复杂概念。先判断受众，再选择合适深度的解释方式。",
        "skills": ["explanation-skill"],
        "temperature": 0.7,
        "max_tokens": 4096,
        "created_at": datetime.now().isoformat(),
    },
    "decision": {
        "name": "decision",
        "label": "决策模式",
        "model": "auto",
        "description": "复杂决策分析，启用五层决策 Skill",
        "system_prompt": "你是决策顾问。用道法术器势框架分析复杂问题，逐层拆解。提供多种方案并指出最优路径。",
        "skills": ["wu-ceng-jue-ce"],
        "temperature": 0.5,
        "max_tokens": 8192,
        "created_at": datetime.now().isoformat(),
    },
}


def load_registry():
    if Path(REGISTRY_FILE).exists():
        with open(REGISTRY_FILE) as f:
            return json.load(f)
    return {}


def save_registry(data):
    with open(REGISTRY_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def init_default():
    """初始化默认后端"""
    reg = load_registry()
    changed = False
    for name, backend in DEFAULT_BACKENDS.items():
        if name not in reg:
            reg[name] = backend
            changed = True
    if changed:
        save_registry(reg)
        # 设置 default 为当前
        with open(STATE_FILE, "w") as f:
            json.dump({"current": "default", "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
        print("✅ 默认后端初始化完成，当前: default")
    else:
        print("ℹ️  后端已存在，未变更")


def cmd_list():
    reg = load_registry()
    current = load_current()
    print("\n📋 Agent 后端列表")
    print("=" * 60)
    if not reg:
        print("  (空) — 运行 `agent-registry.py init` 初始化默认后端")
        return
    for name, b in sorted(reg.items()):
        marker = " ◀" if name == current else ""
        skills_str = f"  [{', '.join(b.get('skills', []))}]" if b.get("skills") else ""
        print(f"  {name:20s} | {b.get('label', name):12s} | {b.get('model', 'N/A'):30s}{marker}{skills_str}")
    print(f"\n  当前活跃: {current or '无'}")


def cmd_show(name):
    reg = load_registry()
    b = reg.get(name)
    if not b:
        print(f"❌ 后端 '{name}' 不存在")
        return
    print(f"\n{'='*50}")
    print(f"  后端详情: {name}")
    print(f"{'='*50}")
    print(f"  标签:      {b.get('label', name)}")
    print(f"  描述:      {b.get('description', '')}")
    print(f"  模型:      {b.get('model', '')}")
    print(f"  系统提示:  {b.get('system_prompt', '(无)')[:100]}...")
    print(f"  技能:      {', '.join(b.get('skills', [])) or '(无)'}")
    print(f"  温度:      {b.get('temperature', 0.7)}")
    print(f"  最大Token: {b.get('max_tokens', 4096)}")
    print(f"  创建时间:  {b.get('created_at', 'N/A')}")


def cmd_add(args):
    """添加后端: --name <name> --label <label> --model <model> [--description <desc>] [--skills <s1,s2>] [--prompt <prompt>]"""
    name = args.name
    reg = load_registry()
    if name in reg:
        print(f"⚠️  后端 '{name}' 已存在，使用 update 或 remove+add")
        return
    backend = {
        "name": name,
        "label": args.label or name,
        "model": args.model,
        "description": args.description or "",
        "system_prompt": args.prompt or "",
        "skills": [s.strip() for s in (args.skills or "").split(",") if s.strip()],
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "created_at": datetime.now().isoformat(),
    }
    reg[name] = backend
    save_registry(reg)
    print(f"✅ 后端 '{name}' 已添加")


def cmd_remove(name):
    reg = load_registry()
    if name not in reg:
        print(f"❌ 后端 '{name}' 不存在")
        return
    current = load_current()
    if current == name:
        print(f"⚠️  '{name}' 是当前活跃后端，已切换到 default")
        with open(STATE_FILE, "w") as f:
            json.dump({"current": "default", "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    del reg[name]
    save_registry(reg)
    print(f"✅ 后端 '{name}' 已删除")


def cmd_use(name):
    reg = load_registry()
    if name not in reg:
        print(f"❌ 后端 '{name}' 不存在")
        print(f"   可用: {', '.join(reg.keys())}")
        return
    with open(STATE_FILE, "w") as f:
        json.dump({"current": name, "updated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    b = reg[name]
    print(f"✅ 已切换到: {name} ({b.get('label', name)})")
    print(f"   模型: {b.get('model', 'N/A')}")
    print(f"   技能: {', '.join(b.get('skills', [])) or '(无)'}")


def cmd_current():
    cur = load_current()
    if not cur:
        print("无活跃后端")
        return
    reg = load_registry()
    b = reg.get(cur, {})
    print(f"🔄 当前后端: {cur} ({b.get('label', cur)})")
    print(f"   模型: {b.get('model', 'N/A')}")
    print(f"   技能: {', '.join(b.get('skills', [])) or '(无)'}")
    print(f"   提示: {b.get('system_prompt', '(无)')[:80]}")


def load_current():
    if Path(STATE_FILE).exists():
        with open(STATE_FILE) as f:
            return json.load(f).get("current", "")
    return ""


def cmd_run(backend_name, query, smart_model=False):
    """用指定后端执行任务"""
    reg = load_registry()
    if backend_name not in reg:
        print(f"❌ 后端 '{backend_name}' 不存在")
        return
    b = reg[backend_name]
    model = b.get("model", "agnes-2.5-pro")
    prompt = b.get("system_prompt", "")
    skills = b.get("skills", [])
    temperature = b.get("temperature", 0.7)
    max_tokens = b.get("max_tokens", 4096)

    # 智能路由：model="auto" 或 --smart-model 时，委托 model-router 选模型
    if model == "auto" or smart_model:
        router_cmd = ["python3", "/var/minis/shared/model-router.py", "route"]
        if skills:
            router_cmd += ["--skill", skills[0]]
        router_cmd.append(query)
        router_proc = subprocess.run(
            router_cmd,
            capture_output=True, text=True, timeout=10
        )
        # 找到根 JSON 的起始 {（跳过前面的路由摘要文本）
        lines = router_proc.stdout.split("\n")
        json_start = -1
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "{":
                json_start = i
                break
        if json_start >= 0:
            json_text = "\n".join(lines[json_start:])
            try:
                route_result = json.loads(json_text)
                selected = route_result["selected_model"]
                model = selected["qualified"]
                print(f"  [路由] L{route_result['estimated_tier']} → {selected['model_id']} ({selected['provider']})")
            except (json.JSONDecodeError, KeyError):
                pass  # 解析失败则用默认模型

    # 构建完整 user message
    user_msg = query
    if skills:
        user_msg = f"[Skill 上下文: {', '.join(skills)}]\n\n{user_msg}"

    # 构建 messages
    messages = []
    if prompt:
        messages.append({"role": "system", "content": prompt})
    messages.append({"role": "user", "content": user_msg})

    # 写入输入文件
    input_file = f"/tmp/agent-run-{os.getpid()}-{__import__('time').time():.6f}.json"
    payload = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    with open(input_file, "w") as f:
        json.dump(payload, f, ensure_ascii=False)

    print(f"{'='*50}")
    print(f"  后端: {backend_name} | 模型: {model}")
    print(f"{'='*50}")

    result = subprocess.run(
        ["minis-model-use", "run", "--model", model, "--input", input_file],
        capture_output=True, text=True, timeout=180
    )
    os.remove(input_file)
    if result.returncode != 0:
        print(f"❌ 执行失败: {result.stderr[:200]}")
        return
    # 解析 minis-model-use JSON 输出，只显示 output_text
    try:
        resp = json.loads(result.stdout)
        output = resp.get("data", {}).get("output_text", result.stdout)
        usage = resp.get("data", {}).get("usage", {})
        print(output)
        if usage:
            print(f"\n  [用量: {usage.get('input_tokens', '?')} in / {usage.get('output_tokens', '?')} out]")
    except (json.JSONDecodeError, KeyError):
        print(result.stdout)


def cmd_run_current(query, smart_model=False):
    cur = load_current()
    if not cur:
        print("❌ 无当前后端，先用 `use <name>` 切换")
        return
    cmd_run(cur, query, smart_model=smart_model)


def main():
    parser = argparse.ArgumentParser(description="Agent Backend Registry")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="查看后端列表")
    sub.add_parser("init", help="初始化默认后端")

    p_show = sub.add_parser("show", help="查看后端详情")
    p_show.add_argument("name")

    p_add = sub.add_parser("add", help="添加后端")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--label", default="")
    p_add.add_argument("--model", required=True)
    p_add.add_argument("--description", default="")
    p_add.add_argument("--skills", default="")
    p_add.add_argument("--prompt", default="")
    p_add.add_argument("--temperature", type=float, default=0.7)
    p_add.add_argument("--max_tokens", type=int, default=4096)

    sub.add_parser("use", aliases=["switch"]).add_argument("name")
    sub.add_parser("remove", aliases=["rm"]).add_argument("name")
    sub.add_parser("current")

    p_run = sub.add_parser("run", help="用指定后端执行任务")
    p_run.add_argument("name")
    p_run.add_argument("query")
    p_run.add_argument("--smart-model", action="store_true",
                       help="使用智能路由选择模型（需 model-router.py）")

    p_run_cur = sub.add_parser("run-current", help="用当前后端执行任务")
    p_run_cur.add_argument("query")
    p_run_cur.add_argument("--smart-model", action="store_true",
                           help="使用智能路由选择模型（需 model-router.py）")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmds = {
        "list": cmd_list,
        "init": init_default,
        "show": lambda: cmd_show(args.name),
        "add": lambda: cmd_add(args),
        "use": lambda: cmd_use(args.name),
        "switch": lambda: cmd_use(args.name),
        "remove": lambda: cmd_remove(args.name),
        "rm": lambda: cmd_remove(args.name),
        "current": cmd_current,
        "run": lambda: cmd_run(args.name, args.query, smart_model=args.smart_model),
        "run-current": lambda: cmd_run_current(args.query, smart_model=args.smart_model),
    }
    cmds.get(args.command, lambda: print(f"未知命令: {args.command}"))()


if __name__ == "__main__":
    main()