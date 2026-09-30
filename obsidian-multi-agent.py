#!/usr/bin/env python3
# Version: 0.1.0
"""
Minis 多 Agent Bot 群聊编排器（借鉴 Hermes Bot Mode）

核心设计：
- 每个 Bot 有名字/角色/模型/persona，独立模型调用
- @ 协议：@阿策 只发给阿策，@所有人 广播
- 三轮/十条硬上限防跑飞
- 判断不了的事输出 [需人类拍板] 标记
- 群聊记录输出到 daily log

用法：
  python3 obsidian-multi-agent.py --topic "帮我策划一篇公众号文章"
  python3 obsidian-multi-agent.py --topic "XXX" --bots "阿策,阿笔"
  python3 obsidian-multi-agent.py --list                    # 查看所有 Bot
  python3 obsidian-multi-agent.py --chat "先@阿查调研一下XX"  # 精确控制
"""

import argparse
import json
import os
import yaml
from datetime import datetime

BOTS_PATH = os.path.join(os.path.dirname(__file__), "multi-agent-bots.yaml")

def load_bots(path=BOTS_PATH):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    bots = cfg.get("bots", [])
    # P2: 启动时校验 Bot 配置
    required_fields = ["name", "model", "persona"]
    seen_names = set()
    valid_bots = []
    for bot in bots:
        missing = [f for f in required_fields if not bot.get(f)]
        if missing:
            print(f"⚠️ 跳过 Bot '{bot.get('name', '?')}'：缺少必填字段 {missing}")
            continue
        name = bot["name"]
        if name in seen_names:
            print(f"⚠️ 跳过重复 Bot name: {name}")
            continue
        seen_names.add(name)
        valid_bots.append(bot)
    if not valid_bots:
        print("❌ 没有可用的 Bot 配置")
    return valid_bots

def call_model(model, prompt, max_tokens=2000, fallback="deepseek/deepseek-v4-flash"):
    """调用 minis-model-use 执行一次对话，支持 fallback
    返回 dict: {"text": ..., "meta": {}} — text 用于 context，meta 用于展示
    """
    import subprocess
    result = subprocess.run(
        ["minis-model-use", "run", "--model", model, "--prompt", prompt, "--max-tokens", str(max_tokens)],
        capture_output=True, text=True, timeout=120
    )
    output = result.stdout
    if result.returncode == 0 and output:
        txt = _parse_output(output)
        if txt:
            return {"text": txt, "meta": {}}
    # 主模型失败 → fallback
    if fallback and fallback != model:
        err_hint = ""
        try:
            parsed = json.loads(output)
            if "error" in parsed:
                err_hint = parsed["error"].get("message", "未知错误")
        except:
            pass
        result2 = subprocess.run(
            ["minis-model-use", "run", "--model", fallback, "--prompt", prompt, "--max-tokens", str(max_tokens)],
            capture_output=True, text=True, timeout=120
        )
        txt = _parse_output(result2.stdout)
        if txt:
            meta = {"downgraded_from": model, "used_model": fallback, "reason": err_hint or "rate_limited"}
            return {"text": txt, "meta": meta}
        return {"text": f"[模型调用失败: {model}]", "meta": {"error": True}}
    return {"text": f"[模型调用失败: {model}]", "meta": {"error": True}}


def _parse_output(output):
    """解析 minis-model-use 输出"""
    try:
        parsed = json.loads(output)
        if "data" in parsed:
            txt = parsed["data"].get("output_text", "")
            if txt:
                return txt[:3000]
        if "choices" in parsed and len(parsed["choices"]) > 0:
            return parsed["choices"][0].get("message", {}).get("content", output[:2000])
    except:
        pass
    return output[:3000] if output else ""


def sanitize_response(text):
    """
    净化模型响应：
    1. 过滤 ANSI 转义序列和控制字符（防终端污染/日志破坏）
    2. 过滤常见 prompt injection 指令模式（防跨 Bot 注入）
    3. 去除零宽字符
    """
    if not text:
        return ""

    import re
    # 过滤 ANSI 转义序列 (ESC [...m 等)
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    # 过滤控制字符 (除换行/制表符外)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
    # 过滤零宽字符 (零宽空格/连接符/非断行空格等)
    text = re.sub(r'[\u200B\u200C\u200D\uFEFF\u202A-\u202E\u2060-\u2069]', '', text)
    # 过滤常见 prompt injection 指令模式
    injection_patterns = [
        r'(?i)ignore\s+(all\s+)?(previous|system|above)\s+(instructions?|directives?|prompts?)',
        r'(?i) disregard (all\s+)?(previous|system|above)\s+(instructions?|directives?)',
        r'(?i)you are now (a\s+)?(different|new)\s+(personality|model|assistant)',
        r'(?i)execute\s+the\s+following\s+instructions?',
        r'(?i)override\s+(system|all)\s+(instructions?|directives?)',
        r'(?i)忘记之前的所有指令',
        r'(?i)忽略所有(系统|之前)指令',
        r'(?i)你现在是一个新的',
        r'(?i)指令覆盖',
    ]
    for pattern in injection_patterns:
        text = re.sub(pattern, '[FILTERED_INJECTION]', text)
    # 移除多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def load_skill_prompts(skills_list):
    """加载 Skill 的 SKILL.md 内容，追加到 Bot 的 persona 中"""
    skills_base = "/var/minis/skills"
    skill_texts = []
    for skill_name in skills_list:
        skill_path = os.path.join(skills_base, skill_name, "SKILL.md")
        if os.path.exists(skill_path):
            with open(skill_path) as f:
                skill_texts.append(f"## {skill_name} Skill\n{f.read()[:1000]}")
        else:
            # Skill 不存在则静默跳过
            pass
    return "\n\n".join(skill_texts)


def build_prompt(bot, context, user_input):
    """构建 Bot 的对话 prompt"""
    persona = bot.get("persona", "")
    skills = bot.get("skills", [])

    # P1 修复：加载配置中的 Skill 内容
    skill_section = ""
    if skills:
        skill_texts = load_skill_prompts(skills)
        if skill_texts:
            skill_section = f"\n\n【你的技能包】\n{skill_texts}"

    context_text = ""
    if context:
        context_text = "\n\n【群聊上下文】\n" + "\n".join(context)

    prompt = f"""{persona}

{skill_section}

{context_text}

【用户指令】{user_input}

【你的角色】{bot['name']} - {bot['role']}
【你的职责】{bot.get('description', '')}

请根据你的角色和职责，针对用户指令给出你的专业意见。如果这个问题超出你的职责范围，请明确说"这不属于我的职责，建议@其他同事"。
不要重复别人的观点，要从你的专业角度补充新信息。
"""
    return prompt

def parse_mentions(user_input, all_names):
    """解析 @ 提及 — 使用正则全词匹配，避免子串误触发"""
    import re
    mentioned = []
    for name in all_names:
        # 全词匹配：@阿策 后必须是非中文/非字母/非数字/非下划线字符
        pattern = r'@' + re.escape(name) + r'(?![\w\u4e00-\u9fff])'
        if re.search(pattern, user_input):
            mentioned.append(name)
    return mentioned

def run_chat(bots, user_input, max_rounds=3, max_messages=10):
    """执行一轮多 Agent 群聊"""
    bot_map = {b["name"]: b for b in bots}
    all_names = [b["name"] for b in bots]

    print(f"\n{'='*50}")
    print(f"🤖 多 Agent 群聊开始")
    print(f"{'='*50}")
    print(f"👥 在线 Bot: {', '.join(all_names)}")
    print(f"📝 用户: {user_input}")
    print()

    context = []
    message_count = 0
    results = []

    for round_num in range(1, max_rounds + 1):
        print(f"--- Round {round_num} ---")

        # 解析 @ 提及
        mentioned = parse_mentions(user_input, all_names)
        if len(mentioned) > 0:
            active_bots = [bot_map[n] for n in mentioned]
        elif f"@所有人" in user_input or f"@all" in user_input:
            active_bots = bots
        else:
            # 广播模式：所有 Bot 都参与
            active_bots = bots

        round_results = []
        for bot in active_bots:
            if message_count >= max_messages:
                print(f"  ⚠️ 消息数已达上限 ({max_messages})，剩余 Bot 跳过")
                break

            prompt = build_prompt(bot, context, user_input)
            print(f"  🤖 @{bot['name']}({bot['role']}) 思考中...", end=" ", flush=True)
            result = call_model(bot["model"], prompt)
            raw_response = result["text"]
            meta = result.get("meta", {})

            # 检查响应是否为错误标记
            if raw_response.startswith("[") and raw_response.endswith("]"):
                print(f"⚠️ {raw_response}")
                continue

            # P0: 净化响应 — 过滤控制字符 + prompt injection
            response = sanitize_response(raw_response)

            # P1: 空响应跳过，不污染 context
            if not response:
                print(f"⚠️ @{bot['name']} 返回空内容，跳过")
                continue

            # 清理响应
            response = response.strip()[:1500]
            display_suffix = ""
            if "downgraded_from" in meta:
                used = meta.get("used_model", bot["model"])
                display_suffix = f" [⚠️ 降级: {meta['downgraded_from']}→{used}]"
            display = f"  📝 @{bot['name']}: {response[:200]}{'...' if len(response) > 200 else ''}{display_suffix}"
            print(display)

            round_results.append({"name": bot["name"], "role": bot["role"], "response": response})
            context.append(f"@{bot['name']}({bot['role']}): {response}")
            message_count += 1

        if not round_results:
            print("  本轮无人回应")
            break

        results.extend(round_results)

        # 如果只有一个 Bot 回应且是广播模式，下一轮可能产生循环
        if len(mentioned) > 0:
            break  # 精确 @ 只跑一轮

    # 检查是否需要人类拍板
    needs_human = any("待验证" in r["response"] or "不确定" in r["response"] for r in results)
    if needs_human:
        print(f"\n  ⚠️ [需人类拍板] 有 Bot 报告了不确定信息，建议核实")

    print(f"\n{'='*50}")
    print(f"📊 群聊结束：共 {message_count} 条消息，{len(set(r['name'] for r in results))} 位 Bot 参与")
    print(f"{'='*50}")

    return results

def list_bots(bots):
    """列出所有 Bot"""
    print(f"\n{'='*50}")
    print(f"🤖 多 Agent Bot 列表 ({len(bots)} 个)")
    print(f"{'='*50}")
    for i, bot in enumerate(bots, 1):
        print(f"\n  {i}. {bot['name']} — {bot['role']}")
        print(f"     📋 {bot.get('description', '')}")
        print(f"     🧠 模型: {bot.get('model', '默认')}")
        print(f"     💬 风格: {bot.get('persona', '')[:60]}...")
        skills = bot.get('skills', [])
        if skills:
            print(f"     🛠 技能: {', '.join(skills)}")
    print(f"\n{'='*50}")

def main():
    parser = argparse.ArgumentParser(description="Minis 多 Agent Bot 群聊（借鉴 Hermes Bot Mode）")
    parser.add_argument("--topic", "-t", help="群聊主题")
    parser.add_argument("--chat", "-c", help="精确群聊指令（支持 @Bot名）")
    parser.add_argument("--bots", "-b", help="指定参与的 Bot（逗号分隔）")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有 Bot")
    parser.add_argument("--rounds", "-r", type=int, default=3, help="最大轮数（默认3）")
    parser.add_argument("--max-msgs", "-m", type=int, default=10, help="最大消息数（默认10）")
    args = parser.parse_args()

    bots = load_bots()

    if args.list:
        list_bots(bots)
        return

    if not args.topic and not args.chat:
        parser.print_help()
        return

    user_input = args.chat or args.topic

    # 过滤 Bot
    if args.bots:
        selected = [b for b in bots if b["name"] in [x.strip() for x in args.bots.split(",")]]
        if not selected:
            print(f"❌ 未找到匹配的 Bot: {args.bots}")
            list_bots(bots)
            return
        bots = selected

    results = run_chat(bots, user_input, max_rounds=args.rounds, max_messages=args.max_msgs)

    # 保存到 daily log
    log_file = os.path.join(os.path.dirname(__file__), f"..", "memory", f"{datetime.now().strftime('%Y-%m-%d')}.md")
    log_file = os.path.normpath(log_file)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if results:
        log_entry = f"\n<!-- {timestamp} -->\n"
        log_entry += f"## 多 Agent 群聊记录（{timestamp.split()[0]}）\n\n"
        log_entry += f"- 用户: {user_input}\n"
        log_entry += f"- 参与 Bot: {', '.join(r['name'] for r in results)}\n"
        log_entry += f"- 消息数: {len(results)}\n\n"
        for r in results:
            log_entry += f"### @{r['name']} ({r['role']})\n{r['response'][:500]}\n\n"

        if os.path.exists(log_file):
            with open(log_file, "a") as f:
                f.write(log_entry)
            print(f"\n💾 群聊记录已追加到 daily log")

if __name__ == "__main__":
    main()