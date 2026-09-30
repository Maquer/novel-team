#!/usr/bin/env python3
# Version: 0.1.0
"""
摩擦度评分模块 — 借鉴 TeamAI 的 Session Friction 设计。

TeamAI 原文逻辑：
  会话结束后按"摩擦度"评分——用户打断次数、AI 重试次数、拒绝工具调用次数等信号。
  长但常规的会话（大量工具调用但无摩擦）不触发分享；真正有问题的会话才触发。

移植到 Minis：
  分析 daily log / 笔记内容，识别"这段内容是否有学习价值"。
  - 高摩擦：创造了新认知（新建/归档/落地/迁移/修复/补齐）→ 应完整蒸馏
  - 中摩擦：有反思改进（分析/优化/总结/决策/设计）→ 可蒸馏但降阈值
  - 低摩擦：日常例行（运行/状态检查/无变化）→ 轻量处理
  - 零摩擦：无实质内容（纯状态报告/空操作）→ 跳过

用法:
  python3 friction-score.py --score "文本内容"
  python3 friction-score.py --score-file "/path/to/file.md"
  python3 friction-score.py --json
"""
import argparse
import logging

logger = logging.getLogger(__name__)

import json, os, re, sys
from datetime import datetime

# 摩擦信号词库（权重越高=信号越强）
HIGH_FRICTION = {
    # 认知创造：新建、归档、迁移、修复——这些都是"产生新知识"的动作
    "新建": 3, "创建": 3, "归档": 3, "落地": 3, "部署": 3, "补齐": 3,
    "迁移": 3, "重构": 3, "修复": 3, "Bug": 3, "bug": 3, "bug修复": 3,
    "打通": 3, "构建": 3, "升级": 3, "升级至": 3,
    # 学习发现：发现新东西或踩坑
    "发现": 3, "学习": 3, "踩坑": 3, "新认知": 3, "突破": 3,
    # 知识生产：蒸馏、知识卡片
    "蒸馏": 3, "知识卡片": 3, "Skill": 3, "skill": 3,
    # 决策
    "决策": 3, "关键决策": 3,
}

MEDIUM_FRICTION = {
    # 分析反思：有思考但不一定是新知识
    "分析": 2, "总结": 2, "优化": 2, "改进": 2, "对比": 2,
    "设计": 2, "评估": 2, "评估对比": 2,
    # 读文/阅读：输入阶段，不一定产出
    "读文": 2, "阅读": 2, "读到": 2,
    # 发现差异/缺口
    "缺口": 2, "缺失": 2, "差距": 2, "不足": 2,
}

LOW_FRICTION = {
    # 例行操作：运行、检查、状态报告
    "运行": -1, "状态检查": -1, "无新": -1, "无待": -1, "无需": -1,
    "跳过": -1, "查看": -1, "确认": -1, "无变化": -1,
    "执行": -1, "完成": -1, "成功": -1,
    # 纯元操作：更新配置、清理等
    "清理": -1, "格式": -1,
}

# 低摩擦阈值词（高摩擦词被稀释的情况）
DILUTION_MARKER = re.compile(
    r'(?:运行|执行|状态检查|无新|无待|跳过|查看|确认|无变化|成功|完成)'
)

# 空内容检测
EMPTY_PATTERN = re.compile(r'^[\s\-:>\[\](){}]*$')


def friction_score(text):
    """
    计算摩擦度评分。

    返回:
        (score: int, level: str, breakdown: dict)
    - score: 原始分（可正可负），范围约 -20 ~ +50
    - level: 'high' / 'medium' / 'low' / 'empty'
    - breakdown: 各维度信号计数
    """
    if not text or len(text.strip()) < 20:
        return (0, "empty", {"high_hits": 0, "medium_hits": 0, "low_hits": 0, "entry_count": 0, "total_chars": 0})

    total_chars = len(text)

    # 计数
    high_hits = 0
    medium_hits = 0
    low_hits = 0

    # 高摩擦信号（精确词匹配）
    for kw, weight in HIGH_FRICTION.items():
        count = text.count(kw)
        high_hits += count * weight

    # 中摩擦信号
    for kw, weight in MEDIUM_FRICTION.items():
        count = text.count(kw)
        medium_hits += count * weight

    # 低摩擦信号（负分）
    for kw, weight in LOW_FRICTION.items():
        count = text.count(kw)
        low_hits += count * weight

    # 内容结构信号（加分项）
    # 条目数（## 标题行）
    entry_count = text.count('\n## ')
    high_hits += min(entry_count * 1, 5)  # 最多 +5

    # 有列表项（- * 等）
    list_count = len(re.findall(r'^\s*[-*+]\s+', text, re.MULTILINE))
    if list_count >= 3:
        high_hits += min(list_count // 3, 3)

    # 有代码块
    code_count = text.count('```')
    if code_count >= 2:
        high_hits += 2

    # 有链接（http/https）
    link_count = len(re.findall(r'https?://', text))
    if link_count >= 3:
        high_hits += 2

    # 有表格（管道符 | 出现较多）
    pipe_lines = len(re.findall(r'^[^\n]*\|', text, re.MULTILINE))
    if pipe_lines >= 5:
        high_hits += 2

    # 汇总
    raw_score = high_hits + medium_hits + low_hits

    # 低摩擦稀释：如果例行词太多，压制分数
    low_content_lines = len(re.findall(r'^[\s]*[\-*>:\[\](){}|/]', text, re.MULTILINE))
    total_lines = len(text.split('\n'))
    if total_lines > 0 and low_content_lines / total_lines > 0.4:
        raw_score = max(0, raw_score - 5)

    # 等级判定
    if raw_score >= 15:
        level = "high"
    elif raw_score >= 6:
        level = "medium"
    elif raw_score >= 0:
        level = "low"
    else:
        level = "empty"

    breakdown = {
        "high_hits": high_hits,
        "medium_hits": medium_hits,
        "low_hits": low_hits,
        "entry_count": entry_count,
        "total_chars": total_chars,
        "raw_score": raw_score,
    }

    return (raw_score, level, breakdown)


def get_action(level, auto_score=0):
    """
    根据摩擦等级决定处理方式。

    返回: (action, reason)
    - "distill": 完整蒸馏+归档
    - "distill_light": 蒸馏但降低自动批准阈值
    - "summarize": 仅记录摘要，不蒸馏
    - "skip": 完全跳过
    """
    if level == "high":
        return ("distill", "高摩擦：创造了新认知，完整蒸馏+归档")
    elif level == "medium":
        if auto_score >= 50:
            return ("distill", "中摩擦+高质量：完整蒸馏+归档")
        else:
            return ("distill_light", "中摩擦：蒸馏，降低自动批准阈值")
    elif level == "low":
        return ("summarize", "低摩擦：日常例行，仅记录摘要")
    else:
        return ("skip", "零摩擦：无实质内容，跳过")


def main():
    import argparse
import logging

logger = logging.getLogger(__name__)
parser = argparse.ArgumentParser(description='摩擦度评分')
parser.add_argument('--score', help='直接评分文本')
parser.add_argument('--score-file', help='评分文件')
parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')
args = parser.parse_args()

if args.score:
    text = args.score
    source = "inline"
elif args.score_file:
    try:
        text = open(args.score_file, 'r', encoding='utf-8', errors='replace').read()
        source = args.score_file
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)
else:
    # 从 stdin 读取
    text = sys.stdin.read()
    source = "stdin"

    score, level, breakdown = friction_score(text)
    action, reason = get_action(level)

    result = {
        "score": score,
        "level": level,
        "action": action,
        "reason": reason,
        "breakdown": breakdown,
        "source": source,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        level_icons = {"high": "🔴", "medium": "🟡", "low": "🟢", "empty": "⚪"}
        action_icons = {"distill": "🧠", "distill_light": "📝", "summarize": "📋", "skip": "⏭️"}
        print(f"{level_icons.get(level, '?')} 摩擦度: {score:+d} ({level})")
        print(f"{action_icons.get(action, '?')} 建议动作: {action}")
        print(f"   {reason}")
        print(f"   高摩擦信号: {breakdown['high_hits']} | 中摩擦: {breakdown['medium_hits']} | 低摩擦: {breakdown['low_hits']}")
        print(f"   条目: {breakdown['entry_count']} | 字符: {breakdown['total_chars']}")

    # 非 JSON 模式打印一个分隔线方便管道使用
    if not args.json:
        print(f"  SCORE={score}  LEVEL={level}  ACTION={action}")


if __name__ == "__main__":
    main()