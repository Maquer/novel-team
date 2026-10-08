#!/usr/bin/env python3
"""
模块化路由器

借鉴：Chinese-WebNovel-Skill (Tomsawyerhu/Chinese-WebNovel-Skill, 836★)
核心：主 Skill 只保留全局原则、流程约束和模块路由，
      每个高频问题拆成独立模块，不堆在一个文件里。

10 个专项模块（按链路排列）：
  前置规划链：concept_planning → opening / volume_outline
  正文执行链：plot_logic + character_consistency + transition + dialogue + chapter_ending + anti_ai_voice
  完稿收口链：consistency_review

用法：
  python3 module-router.py route --issue "开头没抓手"  # 按问题路由到模块
  python3 module-router.py list                         # 列出所有模块
  python3 module-router.py chain --phase planning       # 按阶段列出模块链
  python3 module-router.py guide --module opening       # 获取模块指南
"""

import json
import re
import sys

# 10 个专项模块定义
MODULES = {
    "concept_planning": {
        "name": "概念规划",
        "phase": "planning",
        "chain": "前置规划链",
        "position": "最上游的前置规划模块",
        "purpose": "把一句简介压成题材、消费点、hook、premise、故事引擎、长度判断和第一卷方向",
        "issue_keywords": ["值不值得写", "题材", "创意", "简介", "方向", "卖点", "premise", "概念"],
        "guide": [
            "1. 把简介拆成：题材类型 + 核心消费点 + hook",
            "2. 提炼 premise（一句话故事核心）",
            "3. 确定故事引擎（什么驱动故事持续运转）",
            "4. 判断长度（短篇/中篇/长篇连载）",
            "5. 确定第一卷方向",
        ],
        "good_practices": [
            "消费点明确（爽/虐/甜/燃/烧脑）",
            "hook 能在三句话内说清",
            "故事引擎可持续（不会写到 20 章就没料）",
        ],
        "bad_practices": [
            "概念太抽象（'讲一个人的成长'不是概念）",
            "消费点模糊（不知道读者来看什么）",
            "无故事引擎（靠灵感推进，不可持续）",
        ],
    },
    "opening": {
        "name": "开头",
        "phase": "planning",
        "chain": "前置规划链",
        "position": "承接 concept_planning，负责把骨架变成能抓人的开篇",
        "purpose": "把卖点、异常局面和主角亮相落到前 300-3000 字",
        "issue_keywords": ["开头", "开篇", "第一章", "抓人", "抓手", "前300字", "开头没抓手"],
        "guide": [
            "1. 前 50 字必须有异常/冲突/悬念",
            "2. 300 字内主角亮相",
            "3. 不要慢启动（环境描写>500字无事件）",
            "4. 开头即高潮——第一个场景必须有张力",
        ],
        "good_practices": [
            "以对话/动作开头，不以描写开头",
            "第一段就有冲突或悬念",
            "主角在前 500 字就做决定/行动",
        ],
        "bad_practices": [
            "500 字环境描写后才有第一个事件",
            "以'天气描写+起床'开头",
            "前 1000 字无冲突",
        ],
    },
    "volume_outline": {
        "name": "卷纲",
        "phase": "planning",
        "chain": "前置规划链",
        "position": "承接 concept_planning，负责中长线结构",
        "purpose": "把故事引擎展开成黄金三章、分卷设计、前 10-20 章章纲和卷末兑现",
        "issue_keywords": ["卷纲", "分卷", "章纲", "大纲", "结构", "规划", "黄金三章"],
        "guide": [
            "1. 每卷有情绪走向（爽卷/虐卷/过渡卷）",
            "2. 拆分冲突阶梯（2-4 层逐级升高）",
            "3. 定义信息差（谁知道什么）",
            "4. 每章 2-5 个场景卡",
            "5. 卷末必须兑现核心承诺",
        ],
    },
    "plot_logic": {
        "name": "剧情逻辑",
        "phase": "execution",
        "chain": "正文执行链",
        "position": "正文执行层的底层结构模块，优先级高于纯文风问题",
        "purpose": "修动机、触发、决策、后果、兑现这条因果链",
        "issue_keywords": ["逻辑", "因果", "动机", "剧情", "情节", "不合理", "穿帮", "矛盾"],
        "guide": [
            "1. 每个角色行动必须有动机",
            "2. 事件之间有因果链（因→果）",
            "3. 决策有后果（不做无后果的决定）",
            "4. 兑现之前埋的预期",
            "5. 检查：角色为什么会这么做？信息从哪来？",
        ],
    },
    "character_consistency": {
        "name": "角色一致性",
        "phase": "execution",
        "chain": "正文执行链",
        "position": "正文执行层的人物状态模块",
        "purpose": "修目标、情绪、关系、身体、声音五类人物连续性",
        "issue_keywords": ["人设崩", "OOC", "角色", "人物", "性格", "人设", "一致性"],
        "guide": [
            "1. 目标连续性：角色目标不能突然变",
            "2. 情绪连续性：不能上一秒哭下一秒笑",
            "3. 关系连续性：人际关系变化要有过程",
            "4. 身体连续性：受伤/状态要追踪",
            "5. 声音连续性：说话方式要一致",
        ],
    },
    "transition": {
        "name": "转场",
        "phase": "execution",
        "chain": "正文执行链",
        "position": "正文执行层的场景桥梁模块",
        "purpose": "处理时间跳切、空间切换、情绪承接、视角切换和章末接下章",
        "issue_keywords": ["转场", "过渡", "跳切", "切换", "生硬", "接不上"],
        "guide": [
            "1. 时间跳切要有标记（三天后/一周后）",
            "2. 空间切换要自然（不要突然换地点）",
            "3. 情绪承接：上场景的情绪要在下场景有延续",
            "4. 视角切换要明确（不要无意识切换）",
        ],
    },
    "dialogue": {
        "name": "对话",
        "phase": "execution",
        "chain": "正文执行链",
        "position": "正文执行层的表达模块",
        "purpose": "处理关系压力、人物声音、信息嵌入和对白刀口",
        "issue_keywords": ["对话", "对白", "台词", "说话", "对话假", "台词发假"],
        "guide": [
            "1. 对话要有关系压力（不只是传递信息）",
            "2. 人物声音要区分（不同角色说话方式不同）",
            "3. 信息嵌入：信息通过对话自然给出，不生硬",
            "4. 对白刀口：对话在关键处切断，留悬念",
        ],
    },
    "chapter_ending": {
        "name": "章末",
        "phase": "execution",
        "chain": "正文执行链",
        "position": "正文执行层的章节收束模块",
        "purpose": "处理章末拉力、余韵、回钩和下章承接",
        "issue_keywords": ["章末", "结尾", "钩子", "悬念", "追读", "结尾没后劲"],
        "guide": [
            "1. 章末必须有拉力（让读者想看下一章）",
            "2. 余韵：留下情感回味",
            "3. 回钩：回收之前的小预期",
            "4. 下章承接：为下一章留接口",
            "5. 13 种钩子类型：悬念/反转/危机/揭示/承诺/疑问/冲突/发现/决定/离开/到来/变化/预言",
        ],
    },
    "anti_ai_voice": {
        "name": "去AI味",
        "phase": "execution",
        "chain": "正文执行链",
        "position": "正文执行层的风格约束模块",
        "purpose": "清理空泛总结、套话氛围、说明书式对白和统一腔调",
        "issue_keywords": ["AI味", "去AI", "套话", "腔调", "发假", "说明书", "空泛"],
        "guide": [
            "1. 结构已经成立后再调用（避免把结构问题误判成文风问题）",
            "2. 清理空泛总结（'总之''归根结底'）",
            "3. 去套话氛围（'命运的齿轮''时光荏苒'）",
            "4. 去说明书式对白（对话太功能性）",
            "5. 破统一腔调（所有角色说话方式相同）",
            "6. 参见 narrative_structure_check.py 做 30 特征检测",
        ],
    },
    "consistency_review": {
        "name": "一致性复查",
        "phase": "review",
        "chain": "完稿收口链",
        "position": "最下游的收口模块，每章完稿后默认必过一遍",
        "purpose": "统一复查剧情逻辑、人物目标、情绪关系、身体信息、转场和章末承接六种一致性",
        "issue_keywords": ["复查", "收口", "一致性", "检查", "审稿", "完稿"],
        "guide": [
            "1. 剧情逻辑一致性：因果链是否通",
            "2. 人物目标一致性：角色目标是否突变",
            "3. 情绪关系一致性：关系变化是否有过程",
            "4. 身体信息一致性：受伤/状态是否追踪",
            "5. 转场一致性：场景衔接是否自然",
            "6. 章末承接一致性：上下章衔接是否通顺",
        ],
    },
}


def route_by_issue(issue: str) -> dict:
    """按问题描述路由到模块"""
    scores = {}
    for mod_id, mod in MODULES.items():
        score = 0
        for kw in mod.get("issue_keywords", []):
            if kw in issue:
                score += len(kw)  # 长关键词权重高
        if score > 0:
            scores[mod_id] = score

    if not scores:
        return {
            "match": None,
            "desc": "未匹配到模块，建议先走 concept_planning 或 consistency_review",
        }

    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return {
        "match": top[0][0],
        "module": MODULES[top[0][0]],
        "alternatives": [{"id": mid, "score": s} for mid, s in top[1:3]],
    }


def list_modules():
    """列出所有模块"""
    return {
        mod_id: {
            "name": mod["name"],
            "phase": mod["phase"],
            "chain": mod["chain"],
            "position": mod["position"],
            "purpose": mod["purpose"],
        }
        for mod_id, mod in MODULES.items()
    }


def get_chain(phase: str) -> dict:
    """按阶段列出模块链"""
    chains = {}
    for mod_id, mod in MODULES.items():
        if mod["phase"] == phase:
            chain = mod["chain"]
            if chain not in chains:
                chains[chain] = []
            chains[chain].append({
                "id": mod_id,
                "name": mod["name"],
                "position": mod["position"],
            })
    return chains


def get_guide(module_id: str) -> dict:
    """获取模块指南"""
    mod = MODULES.get(module_id)
    if not mod:
        return {"error": f"未找到模块: {module_id}"}
    return {
        "id": module_id,
        "name": mod["name"],
        "phase": mod["phase"],
        "purpose": mod["purpose"],
        "guide": mod.get("guide", []),
        "good_practices": mod.get("good_practices", []),
        "bad_practices": mod.get("bad_practices", []),
    }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="模块化路由器")
    sub = parser.add_subparsers(dest="cmd")

    p_route = sub.add_parser("route", help="按问题路由")
    p_route.add_argument("--issue", required=True)

    sub.add_parser("list", help="列出所有模块")

    p_chain = sub.add_parser("chain", help="按阶段列出模块链")
    p_chain.add_argument("--phase", required=True, choices=["planning", "execution", "review"])

    p_guide = sub.add_parser("guide", help="获取模块指南")
    p_guide.add_argument("--module", required=True)

    args = parser.parse_args()
    if args.cmd == "route":
        print(json.dumps(route_by_issue(args.issue), ensure_ascii=False, indent=2))
    elif args.cmd == "list":
        print(json.dumps(list_modules(), ensure_ascii=False, indent=2))
    elif args.cmd == "chain":
        print(json.dumps(get_chain(args.phase), ensure_ascii=False, indent=2))
    elif args.cmd == "guide":
        print(json.dumps(get_guide(args.module), ensure_ascii=False, indent=2))
    else:
        parser.print_help()
