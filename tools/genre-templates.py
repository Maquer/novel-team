#!/usr/bin/env python3
"""
题材模板库

借鉴：webnovel-writer 37 题材模板 + awesome-novel-agent 24 题材画像
提供题材风格基线和写作参数预设

用法：
  python3 genre-templates.py list                    # 列出所有题材
  python3 genre-templates.py get --genre <name>      # 获取题材模板
  python3 genre-templates.py match --desc "<简介>"   # 匹配题材
"""

import json
import re
import sys

# 37 题材模板（合并 webnovel-writer 37 + awesome-novel-agent 24 去重）
GENRE_TEMPLATES = {
    # ═══ 玄幻修仙类 ═══
    "修仙": {
        "category": "玄幻修仙",
        "core_conflict": "逆天改命",
        "power_progression": "境界突破",
        "emotion_arc": "压抑→突破→爽快",
        "hook_type": "实力展示/逆转打脸",
        "chapter_length": [3000, 5000],
        "dialogue_ratio": 0.25,
        "action_density": "high",
        "world_rules": ["灵根/天赋体系", "境界分明", "宗门势力"],
        "taboos": ["现代词汇", "科技元素"],
    },
    "系统流": {
        "category": "玄幻修仙",
        "core_conflict": "任务驱动成长",
        "power_progression": "系统升级",
        "emotion_arc": "任务→奖励→满足",
        "hook_type": "系统提示/任务完成",
        "chapter_length": [3000, 4500],
        "dialogue_ratio": 0.20,
        "action_density": "medium",
        "world_rules": ["系统面板", "任务体系", "数值化"],
        "taboos": ["无系统解释", "面板不一致"],
    },
    "高武": {
        "category": "玄幻修仙",
        "core_conflict": "武道争锋",
        "power_progression": "武道境界",
        "emotion_arc": "挑战→突破→超越",
        "hook_type": "战斗高潮",
        "chapter_length": [3500, 5500],
        "dialogue_ratio": 0.22,
        "action_density": "high",
        "world_rules": ["武道体系", "气/内力", "门派"],
        "taboos": ["修仙元素混入", "现代武器"],
    },
    "西幻": {
        "category": "玄幻修仙",
        "core_conflict": "命运抗争",
        "power_progression": "职业/技能树",
        "emotion_arc": "冒险→成长→英雄",
        "hook_type": "冒险发现/战斗",
        "chapter_length": [3000, 5000],
        "dialogue_ratio": 0.30,
        "action_density": "medium",
        "world_rules": ["魔法体系", "种族", "公会/王国"],
        "taboos": ["东方修仙", "系统面板"],
    },
    "无限流": {
        "category": "玄幻修仙",
        "core_conflict": "副本生存",
        "power_progression": "副本奖励积累",
        "emotion_arc": "危险→智慧→通关",
        "hook_type": "副本开始/通关",
        "chapter_length": [3500, 6000],
        "dialogue_ratio": 0.25,
        "action_density": "high",
        "world_rules": ["副本机制", "主神空间", "团队/单人"],
        "taboos": ["副本外长篇", "无规则"],
    },
    "末世": {
        "category": "玄幻修仙",
        "core_conflict": "生存竞争",
        "power_progression": "异能进化",
        "emotion_arc": "绝望→希望→重建",
        "hook_type": "危机/物资/变异",
        "chapter_length": [3000, 5000],
        "dialogue_ratio": 0.20,
        "action_density": "high",
        "world_rules": ["丧尸/变异", "物资稀缺", "基地建设"],
        "taboos": ["轻松日常", "物资充足"],
    },
    "科幻": {
        "category": "玄幻修仙",
        "core_conflict": "文明冲突",
        "power_progression": "科技解锁",
        "emotion_arc": "探索→发现→抉择",
        "hook_type": "科技突破/外星接触",
        "chapter_length": [3000, 5500],
        "dialogue_ratio": 0.28,
        "action_density": "medium",
        "world_rules": ["科技树", "星际/未来", "物理规律"],
        "taboos": ["魔法混入", "修仙体系"],
    },

    # ═══ 都市现代类 ═══
    "都市异能": {
        "category": "都市现代",
        "core_conflict": "隐秘世界争斗",
        "power_progression": "异能觉醒/升级",
        "emotion_arc": "日常→异能介入→解决",
        "hook_type": "异能展示/危机",
        "chapter_length": [3000, 4500],
        "dialogue_ratio": 0.30,
        "action_density": "medium",
        "world_rules": ["异能体系", "隐秘组织", "现代都市"],
        "taboos": ["修仙境界", "系统面板"],
    },
    "都市日常": {
        "category": "都市现代",
        "core_conflict": "生活矛盾",
        "power_progression": "事业/感情发展",
        "emotion_arc": "平淡→冲突→解决",
        "hook_type": "生活反转/情感冲突",
        "chapter_length": [2500, 4000],
        "dialogue_ratio": 0.35,
        "action_density": "low",
        "world_rules": ["现代都市", "职场/校园", "社会关系"],
        "taboos": ["异能/修仙", "科幻元素"],
    },
    "都市脑洞": {
        "category": "都市现代",
        "core_conflict": "规则异常",
        "power_progression": "规则理解/利用",
        "emotion_arc": "发现→试探→掌握",
        "hook_type": "规则发现/异常事件",
        "chapter_length": [2500, 4500],
        "dialogue_ratio": 0.28,
        "action_density": "low",
        "world_rules": ["异常规则", "现代背景", "解谜导向"],
        "taboos": ["战斗为主", "异能升级"],
    },
    "现实题材": {
        "category": "都市现代",
        "core_conflict": "社会矛盾",
        "power_progression": "认知成长",
        "emotion_arc": "困境→挣扎→突破",
        "hook_type": "社会冲突/人物反转",
        "chapter_length": [3000, 5000],
        "dialogue_ratio": 0.32,
        "action_density": "low",
        "world_rules": ["现实世界", "无超自然", "社会逻辑"],
        "taboos": ["异能/科幻", "系统面板"],
    },
    "电竞": {
        "category": "都市现代",
        "core_conflict": "竞技对抗",
        "power_progression": "技术/团队提升",
        "emotion_arc": "训练→比赛→胜利",
        "hook_type": "比赛高潮/逆转",
        "chapter_length": [3000, 5000],
        "dialogue_ratio": 0.35,
        "action_density": "medium",
        "world_rules": ["游戏机制", "电竞圈", "团队合作"],
        "taboos": ["异能", "修仙"],
    },
    "直播文": {
        "category": "都市现代",
        "core_conflict": "内容创作竞争",
        "power_progression": "粉丝/影响力增长",
        "emotion_arc": "直播→互动→涨粉",
        "hook_type": "直播名场面/弹幕反应",
        "chapter_length": [2500, 4000],
        "dialogue_ratio": 0.40,
        "action_density": "low",
        "world_rules": ["直播平台", "弹幕文化", "粉丝经济"],
        "taboos": ["脱离直播", "无互动"],
    },

    # ═══ 言情类 ═══
    "古言": {
        "category": "言情",
        "core_conflict": "身份/权力阻碍",
        "power_progression": "感情深化",
        "emotion_arc": "相遇→心动→阻碍→在一起",
        "hook_type": "误会/身份揭示/虐心",
        "chapter_length": [3000, 4500],
        "dialogue_ratio": 0.35,
        "action_density": "low",
        "world_rules": ["古代背景", "礼教约束", "权谋"],
        "taboos": ["现代词汇", "科技元素"],
    },
    "宫斗宅斗": {
        "category": "言情",
        "core_conflict": "后宫/家族权力",
        "power_progression": "地位提升",
        "emotion_arc": "隐忍→布局→反击",
        "hook_type": "阴谋揭露/反击成功",
        "chapter_length": [3000, 5000],
        "dialogue_ratio": 0.38,
        "action_density": "low",
        "world_rules": ["后宫/世家", "等级制度", "权谋计策"],
        "taboos": ["武力解决", "现代思维"],
    },
    "青春甜宠": {
        "category": "言情",
        "core_conflict": "感情障碍",
        "power_progression": "感情升温",
        "emotion_arc": "相遇→心动→甜蜜→在一起",
        "hook_type": "甜蜜瞬间/吃醋/告白",
        "chapter_length": [2500, 4000],
        "dialogue_ratio": 0.40,
        "action_density": "low",
        "world_rules": ["校园/都市", "无虐或轻虐", "甜度导向"],
        "taboos": ["重虐", "复杂权谋"],
    },
    "豪门总裁": {
        "category": "言情",
        "core_conflict": "身份差距/误会",
        "power_progression": "感情突破障碍",
        "emotion_arc": "相遇→冲突→心动→在一起",
        "hook_type": "霸道/吃醋/身份揭示",
        "chapter_length": [3000, 4500],
        "dialogue_ratio": 0.35,
        "action_density": "low",
        "world_rules": ["豪门背景", "商业元素", "身份差距"],
        "taboos": ["奇幻元素", "武力为主"],
    },
    "狗血言情": {
        "category": "言情",
        "core_conflict": "多重误会/三角关系",
        "power_progression": "虐→和好→再虐",
        "emotion_arc": "甜蜜→虐心→反转→在一起",
        "hook_type": "虐心/误会/反转",
        "chapter_length": [3000, 5000],
        "dialogue_ratio": 0.35,
        "action_density": "low",
        "world_rules": ["多重矛盾", "误会驱动", "情感过山车"],
        "taboos": ["过于平淡", "快速解决"],
    },
    "替身文": {
        "category": "言情",
        "core_conflict": "替身→真爱",
        "power_progression": "身份认知转变",
        "emotion_arc": "替身→心动→揭示→真爱",
        "hook_type": "替身揭示/吃醋/告白",
        "chapter_length": [3000, 4500],
        "dialogue_ratio": 0.33,
        "action_density": "low",
        "world_rules": ["替身设定", "原配对比", "身份焦虑"],
        "taboos": ["无替身矛盾", "快速揭示"],
    },
    "种田": {
        "category": "言情",
        "core_conflict": "生活改善",
        "power_progression": "家境殷实",
        "emotion_arc": "贫困→努力→改善→幸福",
        "hook_type": "丰收/小日子/邻里",
        "chapter_length": [2500, 4000],
        "dialogue_ratio": 0.35,
        "action_density": "low",
        "world_rules": ["乡村/古代", "日常为主", "无超自然"],
        "taboos": ["异能/修仙", "都市元素"],
    },

    # ═══ 特殊题材 ═══
    "规则怪谈": {
        "category": "特殊",
        "core_conflict": "规则生存",
        "power_progression": "规则理解",
        "emotion_arc": "发现→试探→掌握→逃离",
        "hook_type": "规则触发/异常发现",
        "chapter_length": [2500, 4500],
        "dialogue_ratio": 0.20,
        "action_density": "low",
        "world_rules": ["异常规则", "违反后果", "解谜导向"],
        "taboos": ["武力解决", "规则不一致"],
    },
    "悬疑脑洞": {
        "category": "特殊",
        "core_conflict": "谜题解答",
        "power_progression": "线索积累",
        "emotion_arc": "疑惑→发现→推理→揭示",
        "hook_type": "线索发现/反转",
        "chapter_length": [3000, 5000],
        "dialogue_ratio": 0.30,
        "action_density": "low",
        "world_rules": ["逻辑严密", "线索公平", "推理导向"],
        "taboos": ["超自然解释", "线索不公"],
    },
    "悬疑灵异": {
        "category": "特殊",
        "core_conflict": "灵异事件调查",
        "power_progression": "灵异知识积累",
        "emotion_arc": "遇鬼→调查→真相→超度",
        "hook_type": "灵异事件/恐怖发现",
        "chapter_length": [3000, 5000],
        "dialogue_ratio": 0.25,
        "action_density": "medium",
        "world_rules": ["灵异体系", "民俗传说", "恐怖氛围"],
        "taboos": ["科学解释一切", "轻松基调"],
    },
    "历史架空": {
        "category": "特殊",
        "core_conflict": "权力争霸",
        "power_progression": "势力扩张",
        "emotion_arc": "布局→争斗→胜利",
        "hook_type": "战争/政变/谋略",
        "chapter_length": [3500, 5500],
        "dialogue_ratio": 0.30,
        "action_density": "medium",
        "world_rules": ["历史背景", "权谋体系", "军事战略"],
        "taboos": ["现代科技", "超自然"],
    },
    "抗战谍战": {
        "category": "特殊",
        "core_conflict": "民族存亡",
        "power_progression": "情报/行动升级",
        "emotion_arc": "潜伏→危机→行动→胜利",
        "hook_type": "身份暴露/行动成功",
        "chapter_length": [3000, 5000],
        "dialogue_ratio": 0.32,
        "action_density": "medium",
        "world_rules": ["抗战背景", "谍战逻辑", "历史事件"],
        "taboos": ["超自然", "脱离历史"],
    },
    "知乎短篇": {
        "category": "特殊",
        "core_conflict": "概念反转",
        "power_progression": "N/A（短篇）",
        "emotion_arc": "引入→铺垫→反转",
        "hook_type": "概念/反转/结局",
        "chapter_length": [1000, 3000],
        "dialogue_ratio": 0.25,
        "action_density": "low",
        "world_rules": ["概念驱动", "反转核心", "短小精悍"],
        "taboos": ["冗长铺垫", "无反转"],
    },
    "克苏鲁": {
        "category": "特殊",
        "core_conflict": "未知恐惧",
        "power_progression": "禁忌知识积累",
        "emotion_arc": "好奇→不安→恐惧→疯狂",
        "hook_type": "异常发现/理智检定",
        "chapter_length": [3000, 5000],
        "dialogue_ratio": 0.22,
        "action_density": "low",
        "world_rules": ["克苏鲁神话", "理智值", "不可名状"],
        "taboos": ["轻松基调", "武力解决古神"],
    },
}

# 24 题材画像（awesome-novel-agent 预置，简化版）
GENRE_PROFILES_24 = {
    "仙侠": {"base": "修仙", "style": "古典飘逸", "rhythm": "慢热递进"},
    "武侠": {"base": "高武", "style": "侠义豪迈", "rhythm": "快节奏战斗"},
    "都市重生": {"base": "都市异能", "style": "先知先觉", "rhythm": "爽快打脸"},
    "都市修仙": {"base": "都市异能", "style": "隐秘修仙", "rhythm": "日常+战斗交替"},
    "医道": {"base": "都市日常", "style": "专业+仁心", "rhythm": "病例驱动"},
    "商战": {"base": "现实题材", "style": "冷静精明", "rhythm": "布局→收网"},
    "官场": {"base": "现实题材", "style": "沉稳圆滑", "rhythm": "升迁线"},
    "军旅": {"base": "现实题材", "style": "热血铁血", "rhythm": "任务驱动"},
    "二次元": {"base": "都市日常", "style": "轻小说风", "rhythm": "轻松日常"},
    "同人": {"base": "西幻", "style": "原作还原", "rhythm": "事件驱动"},
    "网游": {"base": "电竞", "style": "数据化", "rhythm": "升级+PK"},
    "穿越": {"base": "历史架空", "style": "现代思维碰撞", "rhythm": "适应→改变"},
    "玄幻": {"base": "修仙", "style": "宏大世界观", "rhythm": "升级打怪"},
    "灵异": {"base": "悬疑灵异", "style": "恐怖氛围", "rhythm": "案件驱动"},
    "甜文": {"base": "青春甜宠", "style": "轻松甜蜜", "rhythm": "糖分密集"},
    "虐文": {"base": "狗血言情", "style": "虐心催泪", "rhythm": "虐→糖→虐"},
    "爽文": {"base": "系统流", "style": "快速满足", "rhythm": "高频爽点"},
    "种田文": {"base": "种田", "style": "温馨日常", "rhythm": "慢节奏生活"},
    "悬疑": {"base": "悬疑脑洞", "style": "逻辑严密", "rhythm": "线索→揭示"},
    "科幻未来": {"base": "科幻", "style": "硬核/软科幻", "rhythm": "探索驱动"},
    "历史": {"base": "历史架空", "style": "考据严谨", "rhythm": "事件驱动"},
    "谍战": {"base": "抗战谍战", "style": "紧张悬疑", "rhythm": "情报→行动"},
    "末世生存": {"base": "末世", "style": "残酷求生", "rhythm": "危机驱动"},
    "无限副本": {"base": "无限流", "style": "规则解谜", "rhythm": "副本循环"},
}


def list_genres():
    """列出所有题材"""
    result = {}
    for name, template in GENRE_TEMPLATES.items():
        cat = template["category"]
        if cat not in result:
            result[cat] = []
        result[cat].append(name)
    return result


def get_genre(name: str):
    """获取题材模板"""
    if name in GENRE_TEMPLATES:
        return GENRE_TEMPLATES[name]
    # 尝试 24 画像
    if name in GENRE_PROFILES_24:
        profile = GENRE_PROFILES_24[name]
        base = GENRE_TEMPLATES.get(profile["base"], {})
        return {**base, "profile_name": name, "style": profile["style"], "rhythm": profile["rhythm"]}
    return None


def match_genre(desc: str):
    """从简介匹配题材"""
    scores = {}
    for name, template in GENRE_TEMPLATES.items():
        score = 0
        # 检查关键词
        for keyword in [template["core_conflict"], template["category"]]:
            if keyword in desc:
                score += 2
        # 检查世界规则关键词
        for rule in template.get("world_rules", []):
            for r in rule.split("/"):
                if r in desc:
                    score += 1
        if score > 0:
            scores[name] = score

    if not scores:
        return {"match": None, "desc": "未匹配到题材"}

    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
    return {
        "match": top[0][0],
        "score": top[0][1],
        "alternatives": [{"name": n, "score": s} for n, s in top[1:]],
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="题材模板库")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("list", help="列出所有题材")
    p_get = sub.add_parser("get", help="获取题材模板")
    p_get.add_argument("--genre", required=True)
    p_match = sub.add_parser("match", help="匹配题材")
    p_match.add_argument("--desc", required=True)

    args = parser.parse_args()
    if args.cmd == "list":
        print(json.dumps(list_genres(), ensure_ascii=False, indent=2))
    elif args.cmd == "get":
        result = get_genre(args.genre)
        print(json.dumps(result, ensure_ascii=False, indent=2) if result else "未找到")
    elif args.cmd == "match":
        print(json.dumps(match_genre(args.desc), ensure_ascii=False, indent=2))
    else:
        parser.print_help()
