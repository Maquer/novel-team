#!/usr/bin/env python3
# Version: 0.1.0
"""
obsidian-explain.py — 受众自适应解释工具 v1.1

从 Explanation Skill 读取方法论，调用模型生成易懂解释。
v1.1 变更（审计后修复）：
- P0: audience_display 变量定义修复
- P0: /tmp 文件并发安全（PID+timestamp）
- P1: --text 模式语义修复
- P1: load_skill_prompt() 改用标题段落匹配
- P2: 移除闲置 MODEL_DEFAULT
- 新增：受众四轴调参映射

用法:
    python3 obsidian-explain.py --topic "什么是 MCP"
    python3 obsidian-explain.py --topic "什么是 Git 分支" --audience 老板
    python3 obsidian-explain.py --text "MCP 是协议接口规范" --audience 5岁
    python3 obsidian-explain.py --topic "区块链" --model deepseek-v4
"""

import argparse
import json
import os
import sys
import re
import time

SKILL_PATH = "/var/minis/skills/explanation-skill/SKILL.md"
MODEL_FAST = "agnes-2.5-flash"

AUDIENCES = {
    "5岁": "5岁小孩。超简单词汇，用玩具/动物/食物/游戏类比，短句。一个核心点。",
    "10岁": "10岁小孩。简单词汇，用学校/游戏/运动类比。可引入基础术语+定义。",
    "外行": "外行成年人。尊重但不居高临下，结论先行，日常事物类比。",
    "老板": "公司高管。专业简洁，讲影响/成本/风险/时间线/决策点。不讲技术细节。",
    "父母": "父母或家人。温暖耐心，用他们熟悉的事物类比，少术语。",
    "朋友": "朋友。随意轻松，流行文化/共同兴趣类比。",
    "工程师": "工程师/技术同事。直接精确，讲架构/接口/性能/权衡。可跳过背景。",
    "客户": "客户/非技术合作方。结论先行+商业价值，避免技术术语，突出'对你意味着什么'。",
}

# 受众四轴调参映射（词汇/类比/语气/深度，各 1-5）
AUDIENCE_AXES = {
    "5岁":     {"vocab": 1, "analogy": 1, "tone": "活泼", "depth": 1},
    "10岁":    {"vocab": 2, "analogy": 2, "tone": "轻松", "depth": 2},
    "外行":    {"vocab": 3, "analogy": 2, "tone": "尊重", "depth": 2},
    "老板":    {"vocab": 4, "analogy": 3, "tone": "专业", "depth": 3},
    "父母":    {"vocab": 2, "analogy": 2, "tone": "温暖", "depth": 2},
    "朋友":    {"vocab": 3, "analogy": 3, "tone": "随意", "depth": 3},
    "工程师":  {"vocab": 5, "analogy": 4, "tone": "精确", "depth": 5},
    "客户":    {"vocab": 3, "analogy": 2, "tone": "专业", "depth": 3},
}

OUTPUT_FORMATS = {
    "对话": "对话式解释（默认）。一句话核心→类比→三步理解→对比→总结。",
    "卡片": "卡片式输出。适合发人/存档。每段一个观点，带 emoji。",
    "极简": "一句话核心+一个类比。砍掉一切多余。",
}


def _extract_section(text, heading):
    """从 Markdown 文本提取指定标题下的段落内容。"""
    pattern = re.compile(r'^##+\s+' + re.escape(heading) + r'\s*\n(.*?)(?=^##+\s+|\Z)', re.MULTILINE | re.DOTALL)
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def load_skill_prompt():
    """从 Explanation Skill 提取方法论 prompt。用标题段落匹配，非固定偏移。"""
    if not os.path.exists(SKILL_PATH):
        return "使用类比+单点+视觉+对比四原则，把概念讲清楚。"
    text = open(SKILL_PATH, 'r', encoding='utf-8').read()
    parts = []
    parts.append(_extract_section(text, "Step 2：四原则执行"))
    parts.append(_extract_section(text, "检查清单"))
    parts.append(_extract_section(text, "失败模式"))
    return "\n\n".join(p for p in parts if p) or "使用类比+单点+视觉+对比四原则。"


def build_prompt(topic, audience, fmt, skill_method, is_text_mode=False):
    audience_desc = AUDIENCES.get(audience, audience)
    fmt_desc = OUTPUT_FORMATS.get(fmt, fmt)
    axes = AUDIENCE_AXES.get(audience, {"vocab": 3, "analogy": 2, "tone": "适中", "depth": 3})

    if is_text_mode:
        task = f"润色以下文本，让它对{audience}（{audience_desc}）更容易理解：\n\n{topic}"
        instruction = "请保留原文核心信息，只做语言上的通俗化改写。不要改变原意。"
    else:
        task = f"解释「{topic}」给{audience}（{audience_desc}）"
        instruction = "请直接输出解释，不要加元注释。"

    prompt = f"""你是解释大师。你的任务：{task}。

输出格式：{fmt}（{fmt_desc}）

受众四轴调参：
- 词汇难度: {axes['vocab']}/5
- 类比复杂度: {axes['analogy']}/5
- 语气风格: {axes['tone']}
- 解释深度: {axes['depth']}/5

方法论要点：
{skill_method}

受众 = {audience} | 格式 = {fmt}

要求：
1. 用生活类比（受众熟悉的场景）
2. 一次只讲一件事
3. 用 emoji 做视觉标记
4. 有前后对比
5. 不写空话尾巴
6. 输出不超过 800 字

{instruction}"""
    return prompt


def _safe_tmp(prefix):
    """生成并发安全的临时文件路径。"""
    pid = os.getpid()
    ts = int(time.time() * 1000000)
    return f"/tmp/minis_{prefix}_{pid}_{ts}"


def call_model(prompt, model=None):
    """调用 minis-model-use 生成解释。"""
    model = model or MODEL_FAST
    prompt_path = _safe_tmp("explain_prompt") + ".json"
    result_path = _safe_tmp("explain_result") + ".json"

    with open(prompt_path, 'w', encoding='utf-8') as f:
        json.dump({"messages": [{"role": "user", "content": prompt}]}, f, ensure_ascii=False)

    try:
        cmd = (
            f"minis-model-use run --model {model} "
            f"--input {prompt_path} "
            f"--output {result_path}"
        )
        ret = os.system(cmd)
        if ret != 0:
            return None

        if not os.path.exists(result_path):
            return None

        data = json.load(open(result_path, 'r', encoding='utf-8'))
        content = ""
        if isinstance(data, dict):
            if "choices" in data and data["choices"]:
                msg = data["choices"][0].get("message", {})
                content = msg.get("content", "")
            elif "content" in data:
                content = data["content"]
            elif "output" in data:
                content = data["output"]
            elif "text" in data:
                content = data["text"]
        elif isinstance(data, list) and len(data) > 0:
            item = data[0]
            if isinstance(item, dict) and "content" in item:
                content = item["content"]
            elif isinstance(item, str):
                content = item
        return content if content else None
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️ 解析模型输出失败: {e}", file=sys.stderr)
        return None
    finally:
        for p in (prompt_path, result_path):
            try:
                os.remove(p)
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description='受众自适应解释工具 v1.1')
    parser.add_argument('--topic', '-t', help='要解释的主题')
    parser.add_argument('--text', help='要润色的已有文本')
    parser.add_argument('--audience', '-a', default='5岁',
                        help=f'目标受众: {", ".join(AUDIENCES.keys())}')
    parser.add_argument('--format', '-f', default='对话',
                        choices=list(OUTPUT_FORMATS.keys()),
                        help='输出格式')
    parser.add_argument('--model', '-m', help='使用的模型')
    parser.add_argument('--list', action='store_true', help='列出支持受众')
    args = parser.parse_args()

    if args.list:
        print("支持的受众：")
        for k, v in AUDIENCES.items():
            axes = AUDIENCE_AXES.get(k, {})
            ax_str = f" V{axes.get('vocab','?')}/A{axes.get('analogy','?')}/D{axes.get('depth','?')}/{axes.get('tone','?')}"
            print(f"  {k:8} — {v[:60]}...{ax_str}")
        print("\n输出格式：")
        for k, v in OUTPUT_FORMATS.items():
            print(f"  {k:4} — {v[:60]}...")
        return

    if not args.topic and not args.text:
        parser.print_help()
        print("\n⚠️ 请提供 --topic 或 --text")
        sys.exit(1)

    is_text_mode = bool(args.text) and not args.topic
    audience = args.audience
    audience_display = audience if audience in AUDIENCES else audience
    if audience not in AUDIENCES:
        print(f"⚠️ 未知受众 '{audience}'，使用自定义描述")

    topic = args.topic or f"润色以下文本：{args.text}"
    skill_method = load_skill_prompt()
    prompt = build_prompt(topic, audience, args.format, skill_method, is_text_mode=is_text_mode)

    mode_label = "润色" if is_text_mode else "解释"
    print(f"📖 {mode_label} [{audience_display}] 视角: {topic[:50]}...")
    print(f"   模型: {args.model or MODEL_FAST}")
    print(f"   {'='*50}")
    result = call_model(prompt, args.model)

    if result:
        print(result)
    else:
        print("❌ 解释生成失败（模型调用超时或失败）")
        sys.exit(1)


if __name__ == '__main__':
    main()