#!/usr/bin/env python3
"""
九维质检评分 — ai-fiction-writer novel-humanizer 融合升级 v2

在原有 lieflat+Novel-Creator AI味检测基础上，增加 ai-fiction-writer 的九维评分体系。
九维度：逻辑性(18%) / 角色一致性(16%) / 世界观一致性(8%) / 时代适配度(14%)
        / 对话自然度(11%) / 文学性(10%) / 情感表达(10%) / 节奏感(9%) / 去系统化(4%)

v2 修复：
  - 扩展扣分模式（从~15条增至~50条）
  - 改进评分公式：固定扣分 + 长度归一化
  - 修正正则匹配逻辑（允许主语前缀）

用法：
  python3 humanizer-9d.py --text "文本" --json
  python3 humanizer-9d.py --chapter-file chapter.md --json
  python3 humanizer-9d.py --text "文本"  # 人可读报告
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ============================================================================
# 评分配置（v3：九维词句层 + 叙事结构层 — sepia/StoryScope 融合）
#
# StoryScope (arXiv:2604.03136) 证明：
#   仅用叙事结构特征（不看用词），AI 检测 macro-F1 = 93.2%
#   人类编辑改写表层风格后，检测率只从 95.5% 降到 93.9%
#   → 词句改写几乎无效，AI 破绽在叙事结构层
#
# 叙事结构层（narrative_structure）权重 0.14，独立于九维词句层；
# 九维权重相应下调，总和保持 1.00。
# ============================================================================

DIMENSIONS = {
    # --- 九维词句层（权重按 0.86 等比缩放）---
    "logic":          {"name": "逻辑性",         "weight": 0.15, "pass_line": 85, "desc": "时间线连续、设定一致、前后文无矛盾"},
    "character":      {"name": "角色一致性",     "weight": 0.14, "pass_line": 85, "desc": "言行是否符合档案、OOC检测"},
    "worldview":      {"name": "世界观一致性",   "weight": 0.07, "pass_line": 85, "desc": "地点/势力/规则/文化与世界build一致"},
    "era_adapt":      {"name": "时代适配度",     "weight": 0.12, "pass_line": 80, "desc": "禁用词、物价合理性、科技产物出现时间"},
    "dialogue":       {"name": "对话自然度",     "weight": 0.09, "pass_line": 80, "desc": "口语省略、方言痕迹、符合角色"},
    "literary":       {"name": "文学性",         "weight": 0.09, "pass_line": 75, "desc": "五感描写、比喻新鲜度、句式变化"},
    "emotion":        {"name": "情感表达",       "weight": 0.09, "pass_line": 80, "desc": "避免情感直给、动作替代、情绪曲线自然"},
    "rhythm":         {"name": "节奏感",         "weight": 0.08, "pass_line": 75, "desc": "连续对话/动作/描写的平衡、张弛有度"},
    "de_system":      {"name": "去系统化",       "weight": 0.03, "pass_line": 90, "desc": "系统面板、数据流、机械表达"},
    # --- 叙事结构层（sepia Group A-E，权重 0.14）---
    "narrative_structure": {
        "name": "叙事结构", "weight": 0.14, "pass_line": 80,
        "desc": "AI 破绽检测：主题过明/因果链过紧/情绪模式/时间线性/结尾指纹/真实锚点/读者意识"
    },
}

# ============================================================================
# 各维度扣分项（扩展版 v2：~50条模式）
# ============================================================================

# FIX 2026-09-30：时代词表统一——此前本文件的 era_adapt 现代词与
# config/logic-rules.json 的 era_words.words 各维护一份且不一致（必然漂移）。
# 设计决策：以 config/logic-rules.json 的 era_words.words 为准；config 缺失时回退内置词表；
# 为避免覆盖面倒退，内置独有的词（支付宝/WiFi/互联网/电视/高铁/高速公路/红绿灯）与 config 取并集保留。
# 行为变化：config 中的 29 个现代词（办公室/会议/老师/医院/警察/工资…）现在也会被扣分；
# 单次命中仍计 1 惩罚点（与原两条分类正则合并前一致，不重复扣）。
def _load_config_era_words() -> Optional[List[str]]:
    """从 config/logic-rules.json 读取时代词表；失败返回 None（调用方回退内置）"""
    try:
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "logic-rules.json"
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        words = data.get("rules", {}).get("era_words", {}).get("words", [])
        return list(words) if words else None
    except Exception:
        return None


# 内置时代词表（config 缺失时的回退；config 存在时作为并集补充）
_BUILTIN_ERA_WORDS = [
    "手机", "微信", "支付宝", "WiFi", "互联网", "电脑", "电视",
    "地铁", "高铁", "飞机", "高速公路", "红绿灯",
]


def _build_era_words_pattern() -> str:
    cfg_words = _load_config_era_words()
    if cfg_words is None:
        words = list(_BUILTIN_ERA_WORDS)
    else:
        words = list(cfg_words) + [w for w in _BUILTIN_ERA_WORDS if w not in cfg_words]
    # 长词优先，避免短词先吞掉长词中的子串（如"网络"吞"互联网"中的部分）
    words = sorted(set(words), key=len, reverse=True)
    return "|".join(re.escape(w) for w in words)


_ERA_WORDS_PATTERN = _build_era_words_pattern()

PUNISHMENTS = {
    "logic": [
        # 时间矛盾
        (r'刚才.*突然.*(醒来|起床|发现)', '时间跳跃可疑'),
        (r'早上.*（.*晚上|夜晚|深夜）', '时间段矛盾'),
        (r'（.*早上|上午）.*（.*晚上|夜晚|深夜）', '时间跨度矛盾'),
        # 地点瞬移
        (r'在(这里|这|此处).{0,10}(那里|那儿|彼处).{0,20}(走到|到达|赶到)', '地点瞬移可疑'),
        (r'（.*）.{0,5}(走|跑|冲|闪).{0,10}（.*）', '动作时间省略'),
    ],
    "character": [
        # OOC - 内心戏过度
        (r'(?:不禁|不由)(?:心中暗道|暗自思忖|心下思索)', '内心戏过度'),
        (r'(?:心中|心里)(?:暗道|暗想|思量)', '内心独白过多'),
        # OOC - 模板化反应
        (r'(?:脸色)(?:微微|骤然|倏地)(?:一变|苍白|惨白)', '模板化表情反应'),
        (r'(?:身形)(?:微微|骤然)(?:一顿|一滞)', '模板化动作反应'),
        (r'(?:瞳孔)(?:微微|骤然)(?:收缩|一缩)', '模板化眼神反应'),
        # OOC - 语气标签泛滥
        (r'(?:冷冷|淡淡|微微|轻轻)(?:说道|开口|说)', '语气标签泛滥'),
        (r'(?:沉声|冷声|低吼)(?:道|说)', '刻意语气标签'),
    ],
    "era_adapt": [
        # 时代错位词汇
        # FIX 2026-09-30：现代词改走统一时代词表（config/logic-rules.json era_words.words，
        # 缺失回退内置；内置独有词并入）。原"现代科技产物/现代交通工具"两条合并为一条，
        # 单次命中扣分不变；货币/时间单位两条正则保持不变。
        (_ERA_WORDS_PATTERN, '现代词汇（统一时代词表）'),
        (r'人民币|元[\s]*(?:钱|块|币)', '现代货币单位'),
        (r'秒钟|分钟|小时|天(?!(蒙蒙亮|亮|才|长|空|气|地|寒|昏|明|晚|夕|晓|黑|刚|将|机))', '现代时间单位（需上下文）'),
    ],
    "dialogue": [
        # 对话模板
        (r'"[^"]{0,30}"(?:他|她)\s*(?:说道|说|开口)', '标签式对话'),
        (r'"(?:请问|您好|谢谢|对不起|打扰|不好意思)"', '过于礼貌的对话'),
        (r'(?:道|说).{0,10}"[^"]{0,30}"', '对话位置后置'),
    ],
    "literary": [
        # 低质量比喻
        (r'仿佛.{0,5}(走在|置身于|进了)', '低质量比喻模板'),
        (r'宛如.{0,5}(一幅|一首|一曲)', '陈词滥调比喻'),
        # 滥用修辞
        (r'(?:如同|好像|仿佛|犹如).{0,10}(一般|似的)', '比喻冗余'),
    ],
    "emotion": [
        # 情感直给
        (r'(?:心中|心里)(?:涌起|泛起|充满)(?:一股|一阵|难以|无比)', '情感直给'),
        (r'(?:心中|心里)(?:一紧|一痛|一酸|一震|一跳)', '模板化情绪反应'),
        (r'不禁(?:流下|落下)(?:泪|眼泪)', '情感夸张'),
        (r'难以(?:言喻|自禁|置信)', 'AI腔形容词'),
        # 模板化情绪链
        (r'(?:心跳|呼吸)(?:加速|停滞|紊乱)', '生理反应模板'),
    ],
    "rhythm": [
        # 节奏失衡（在 check_rhythm_balance 中单独检测）
    ],
    "de_system": [
        # 系统化表达
        (r'(\[|【)\s*(?:属性|等级|HP|MP|经验|技能|状态|任务)\s*[:：]', '系统面板残留'),
        (r'(?:数值|属性|力量|速度|敏捷)(?:值|为|：?\s*\d+)', '数据流表达'),
        (r'(叮|系统提示|【系统】|机械音)(?:响起|道|提示)', '系统提示音'),
        (r'(?:系统)\s*(?:发布|提示|宣布)', '系统播报'),
    ],
}

# 额外检测（按维度聚合）
EXTRA_CHECKS = {
    "logic": [
        # 禁止开头套路
        (r'^(?:本章|本章节|这一章).{0,20}', '章末预告入侵正文'),
    ],
    "character": [
        # AI腔人物描写
        (r'(?:一双(?:眸子|眼睛))(?:闪烁着|透着|带着)(?:复杂|深邃|难以)(?:解读|捉摸)', 'AI腔眼神描写'),
        (r'(?:嘴角)(?:微微|勾起|一扬)', 'AI腔微笑模板'),
        (r'(?:眉峰|眉头)(?:微微|轻轻一)(?:皱|蹙)', 'AI腔皱眉模板'),
    ],
    "era_adapt": [
        # 逻辑连接词滥用（类翻译腔）
        (r'(?:首先|其次|再次|最后).{0,30}(?:，|。)', '序数词结构'),
        (r'(?:综上所述|总而言之|由此可见)', '结论套话'),
    ],
    "dialogue": [
        # 对话空洞化
        (r'"(?:嗯|啊|哦|呵)"(?:道|说)', '单字对话'),
    ],
    "literary": [
        # 句式单调
        (r'((?:他|她)\s+(?:走|站|坐|躺).{0,20}(?:他|她)\s+(?:走|站|坐|躺))', '连续相同句式'),
    ],
    "emotion": [
        # 情感词汇堆砌
        (r'(?:激动|兴奋|愤怒|悲伤|痛苦|恐惧)(?:难以|无比|无法)', '情感词堆砌'),
        (r'(?:心中|心里).{0,5}(?:百感交集|五味杂陈|思绪万千)', '成语堆砌'),
    ],
    "rhythm": [
        # 段落结构问题
        (r'\n{3,}', '空行过多'),
    ],
}


# ============================================================================
# 加分项（正向特征）
# ============================================================================

BONUS_PATTERNS = {
    "literary": [
        (r'(?:看|见|望|瞧|瞥|扫)(?:见|到|了)?\s*.{1,5}(?:光影|色彩|颜色|光线|黑暗|明亮|模糊|清晰)', '视觉描写'),
        (r'(?:听|闻|嗅|闻见|听见)(?:到|见|了)?\s*.{1,5}(?:声|音|响|气味|味道|气息)', '听觉/嗅觉描写'),
        (r'(?:摸|触|按|握|捏|掐)(?:到|着|住)?\s*.{1,5}(?:冷|热|凉|烫|软|硬|粗糙|光滑|锋利)', '触觉描写'),
        (r'(?:尝|吃|舔|含)(?:到|着|住)?\s*.{1,5}(?:甜|苦|辣|咸|涩|鲜|腥)', '味觉描写'),
        (r'(?:风|雨|雪|月|日|星).{0,5}(?:吹|打|照|映)', '自然环境描写'),
    ],
    "emotion": [
        (r'(?:手指|手掌|拳头|指甲)(?:微微|不自觉地|不期然|悄然)(?:握紧|收紧|颤抖|嵌入)', '以动作写情绪'),
        (r'(?:喉结|脖颈|肩背|脊背)(?:微微|不自觉地)(?:绷紧|僵硬)', '以生理反应写情绪'),
        (r'(?:呼吸|心跳|脉搏)(?:微微|不自觉地)(?:加快|放缓|停滞|漏跳)', '以生理反应写情绪'),
        (r'(?:脚步|步伐)(?:微微|不自觉地)(?:加快|放缓|停顿)', '以动作写情绪'),
    ],
    "rhythm": [
        (r'（.{1,15}）.{0,5}(?:他|她)\s+(?:走|跑|冲|闪|移|停|顿)', '动作穿插调节节奏'),
    ],
    "dialogue": [
        (r'"[^"]{2,50}"\s*(?:他|她)\s+(?:没|没有|不|却)', '有冲突的对话'),
    ],
}


# ============================================================================
# 叙事结构层检测（v3 — 基于 sepia/StoryScope 30 特征 rubric）
#
# 文献依据：
#   StoryScope (arXiv:2604.03136, Russell et al. 2026)
#     61,608 篇故事，叙事结构特征 → 93.2% macro-F1 检测率
#     人类编辑改写表层后 95.5% → 93.9%（词句层几乎无效）
#   LAMP (arXiv:2409.14509, CHI 2025) — 人类编辑改写效果测量
#   SLOPSHAPE-2026 — 187 结构特征 → 98.0% macro-F1（公司博客）
#   Sepia (Nanako0129/sepia, 2,940★, MIT) — 30 特征 5 组诊断 rubric
#
# 本模块是**正则级信号检测**（快速筛查 + 报告），不等同于 StoryScope
# 的 XGBoost 分类器。用途：gate-check 时定位"章节叙事结构是否有 AI 指纹"，
# 提示人工精审，不自动修改正文。
#
# 设计原则（对齐 sepia "Calibration" 段）：
#   - 每篇只应选 3-5 个人类向手法，不能全规则同时触发（否则是新指纹）
#   - 人类值在中间，不翻转到 AI 的对立面（过度修正 = 新破绽）
#   - 检测是"信号"非"判决"——报告引用原文，不输出概率
# ============================================================================

# 叙事结构层扣分项（对齐 sepia rubric.md Group A/B/C/E）
# Group D（缺少人类正向标记）不作为扣分——缺标记≠AI，advisory 提示
NARRATIVE_PUNISHMENTS = [
    # --- Group A: 主题过明（Thematic over-determination）---
    # 人类 ~52% 叙述者评论 vs AI 77%；主题显明度 人类3.3 AI3.9
    (r'这就是(?:人|世界|人生|社会|命运|爱|权力|真相)', 'A·主题说教句（"这就是..."定论）'),
    (r'原来.{0,15}才是(?:答案|真相|道理|关键)', 'A·说教定论（"原来...才是"）'),
    (r'(?:人|世界|社会|命运|人性)总是.{0,15}(?:如此|这样|循环|悲剧)', 'A·概括性说教（"总是如此/循环"）'),
    (r'他(?:们)?(?:终于|这才|此刻)(?:明白|懂得|理解)了', 'A·总结式顿悟（"终于明白了"）'),
    # --- Group B: 情绪模式（Sensory & embodied performativity）---
    # 人类 ~38% 身体感知 vs AI 81%；"show don't tell" 教条化
    (r'(?:心中|心里|心头)(?:一紧|一痛|一酸|一震|一跳|一滞|一暖|一沉|一松)', 'B·模板化情绪生理反应（"心中一X"高频=AI指纹）'),
    (r'(?:感到|感觉到)(?:一阵|一股|一丝)(?:(?:冷|热|疼|痛|酸|暖|麻|痒))', 'B·"感到一阵X"情绪模式'),
    (r'(?:嘴角|眼神|目光)(?:流露出|透出一丝|带着)(?:复杂|难以|说不清)', 'B·"难以捉摸"AI腔'),
    # --- Group C: 因果链过紧（Structural streamlining）---
    # 人类 ~57% 无支线 vs AI 79%；巧合触发器密集 = 单线因果
    # FIX 10-04: "命运" 在古言/玄幻语境是常用词（"命数""天意"），误伤率高；
    # 收窄到 "命运 + 决定/循环/安排" 的完整说教短语，单字"命运"不再触发
    (r'(?:恰好|正好|碰巧|巧合的是)', 'C·巧合触发器（"恰好/正巧"密集=单线因果）'),
    (r'就在(?:此时|这时|那一刻|同一(?:时刻|时间))', 'C·时间巧合压缩（"就在此时"）'),
    (r'(?:命运|天意)(?:总是|注定|安排|决定|如此)', 'C·命运决定论替代人物自主决意'),
    # --- Group E: 时间线性 & 真实锚点缺失 ---
    # 人类 ~2.4/5 时序断裂 vs AI 2.1
    # FIX 10-04: 要求"第N天"后跟标点（逗号/句号），避免误伤"word_count: 0\n第二天"（元数据粘连）；
    # 线性递进需要≥2个连续"第N天"才触发，单天不扣分（人类也正常用"第二天"）
    (r'第(?:一|二|三|四|五)天[，。]', 'E·线性天数计数（缺时序断裂）'),
]

# 叙事结构层加分项（对齐 sepia 人类正向标记）
NARRATIVE_BONUS = [
    (r'你(?:知道|见过|听过)的?(?:那种|那种样的)?', 'D·第四面墙/读者直接称呼（"你知道的那种..."）'),
    (r'(?:说|提到)的是?《[^》]+》', 'D·具名真实文本引用（非"一部小说"）'),
    (r'(?:记得|还记得)?(?:那年|当年|很多年前)', 'E·闪回/时序断裂（非线性）'),
    (r'(?:后来|多年以后|直到(?:那一天|那一刻))', 'E·时间跳切（非线性）'),
    (r'倒是.{0,10}(?:没想到|没料到)', 'C·意外转折（非必然因果）'),
]

# 叙事结构层阈值（对齐 sepia "选 3-5 个手法" 原则）
# 每章叙事层扣分封顶，防止过度惩罚（人类值在中间，不是 AI 的对立面）
NARRATIVE_MAX_PENALTY = 8   # 叙事层独立封顶 8 惩罚点（词句层是 60）
# 加分项上限（人类标记越多越好，但封顶防滥）
NARRATIVE_MAX_BONUS = 3


# ============================================================================
# 检测函数
# ============================================================================

def strip_markdown(text: str) -> str:
    """去除 Markdown 格式和 YAML frontmatter"""
    # 过滤 YAML frontmatter（--- ... --- 块 + 元数据键值对）
    lines = []
    in_frontmatter = False
    for line in text.splitlines():
        stripped = line.strip()
        # YAML frontmatter 边界
        if stripped == '---':
            if not in_frontmatter:
                in_frontmatter = True
            else:
                in_frontmatter = False
            continue
        if in_frontmatter:
            continue
        # 元数据键值行（word_count: 0 / title: xxx 等单独存在正文外的）
        if re.match(r'^(?:word_count|title|author|tags?|updated_at|created_at|status)\s*:', stripped):
            continue
        if stripped.startswith('#'):
            continue
        if stripped.startswith(('-', '*', '1.', '2.', '3.')):
            continue
        lines.append(line)
    return '\n'.join(lines)


def check_dimension(text: str, dim: str, patterns: List[Tuple[str, str]]) -> Tuple[int, List[str]]:
    """检查某个维度的扣分项"""
    issues = []
    total_penalty = 0
    for pattern, desc in patterns:
        matches = list(re.finditer(pattern, text))
        for m in matches:
            ctx = text[max(0, m.start()-10):m.end()+20].replace('\n', ' ')
            issues.append({"desc": desc, "context": ctx[:60]})
            total_penalty += 1
    return total_penalty, issues


def check_bonus(text: str, dim: str, patterns: List[Tuple[str, str]]) -> Tuple[int, List[str]]:
    """检查某个维度的加分项"""
    issues = []
    total_bonus = 0
    for pattern, desc in patterns:
        matches = list(re.finditer(pattern, text))
        if matches:
            total_bonus += 1
            issues.append({"desc": desc, "count": len(matches)})
    return total_bonus, issues


def check_rhythm_balance(text: str) -> Tuple[int, List[str]]:
    """检查节奏感——对话/动作/描写的平衡"""
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    if len(paragraphs) < 3:
        return 0, []

    dialogue_count = 0
    action_count = 0
    desc_count = 0
    mixed_count = 0

    for para in paragraphs:
        has_dialogue = bool(re.search(r'"[^"]{1,200}"', para)) and para.count('"') >= 2
        has_action = bool(re.search(r'(?:走|跑|冲|闪|移|拔|握|推|拉|抬|伸|站|坐|躺)', para))
        has_desc = bool(re.search(r'(?:看|见|望|听|闻|感觉|似乎|仿佛|如|像)', para))
        has_emotion = bool(re.search(r'(?:心中|心里|忽然|猛然|骤然)', para))

        counts = sum([has_dialogue, has_action, has_desc, has_emotion])
        if counts == 0:
            continue
        elif counts == 1:
            if has_dialogue:
                dialogue_count += 1
            elif has_action:
                action_count += 1
            elif has_desc:
                desc_count += 1
            else:
                mixed_count += 1
        else:
            mixed_count += 1

    total = max(dialogue_count + action_count + desc_count + mixed_count, 1)
    imbalance_penalty = 0
    issues = []

    if dialogue_count / total > 0.5 and len(paragraphs) >= 5:
        imbalance_penalty += 2
        issues.append(f"对话占比过高({dialogue_count}/{total})，缺乏动作和描写穿插")
    if action_count / total < 0.05 and len(paragraphs) >= 5:
        imbalance_penalty += 1
        issues.append("动作描写过少，节奏偏慢")
    if desc_count / total < 0.05 and len(paragraphs) >= 5:
        imbalance_penalty += 1
        issues.append("环境描写过少，缺少氛围营造")
    if mixed_count / total > 0.7 and len(paragraphs) >= 5:
        imbalance_penalty += 1
        issues.append("段落结构单一，缺乏变化")

    return imbalance_penalty, issues


def check_emotion_show_dont_tell(text: str) -> Tuple[int, List[str]]:
    """检查情感表达——是否展示而非告知"""
    direct_emotion_patterns = [
        r'(?:心中|心里)(?:感到|觉得|知道|明白|意识到)',
        r'(?:心中|心里)(?:一阵|一股|有些|非常|无比|难以)(?:喜悦|悲伤|愤怒|恐惧|紧张)',
    ]
    penalty = 0
    issues = []
    total_count = 0
    for pattern in direct_emotion_patterns:
        count = len(re.findall(pattern, text))
        total_count += count
    if total_count >= 3:
        penalty = total_count - 2
        issues.append(f"'心中/心里'类情感直给 {total_count} 次（≥3次开始扣分）")
    return penalty, issues


def check_narrative_structure(text: str) -> Tuple[int, int, List[str]]:
    """
    叙事结构层检测（基于 sepia/StoryScope 30 特征 rubric 的正则级信号筛查）

    返回 (penalty, bonus, issues_list)
      penalty: 命中的叙事结构扣分项数（封顶 NARRATIVE_MAX_PENALTY）
      bonus:   命中的加分项数（封顶 NARRATIVE_MAX_BONUS）
      issues:  每条命中项的描述（带原文片段）

    原理（StoryScope, arXiv:2604.03136）：
      仅用叙事结构特征（不看用词），AI 检测 macro-F1 = 93.2%
      人类编辑改写表层风格后，检测率 95.5% → 93.9%（几乎无效）
      → 词句层改写无法消除 AI 指纹，破绽在叙事结构层

    本函数是"快速筛查 + 信号定位"，不等同于 XGBoost 分类器：
      - 输出是"可疑信号列表"，供人工精审 / Agent 叙事层修复
      - 报告引用原文片段，不输出概率/判定
      - 加分项（人类正向标记）可抵消扣分，避免"全规则触发=新指纹"
    """
    issues = []
    penalty_raw = 0

    # --- 扣分项 ---
    for pattern, desc in NARRATIVE_PUNISHMENTS:
        matches = list(re.finditer(pattern, text))
        if not matches:
            continue
        # 高频命中（≥3 处）= 强烈信号，权重加倍
        hit_count = len(matches)
        if hit_count >= 3:
            weight = 2
        elif hit_count >= 2:
            weight = 1
        else:
            weight = 1  # 单次命中仍是信号，不忽略
        penalty_raw += weight
        # 截取第一个匹配的原文片段（前后各 15 字，避免整段重复）
        first = matches[0]
        start = max(0, first.start() - 15)
        end = min(len(text), first.end() + 15)
        snippet = text[start:end].replace('\n', ' ')
        issues.append({
            "type": "narrative_penalty",
            "group": desc.split("·")[0] if "·" in desc else "?",
            "desc": desc,
            "count": hit_count,
            "context": snippet,
        })

    # 封顶
    penalty = min(penalty_raw, NARRATIVE_MAX_PENALTY)

    # --- 加分项（人类正向标记）---
    bonus_raw = 0
    for pattern, desc in NARRATIVE_BONUS:
        matches = list(re.finditer(pattern, text))
        if matches:
            bonus_raw += 1
            first = matches[0]
            start = max(0, first.start() - 15)
            end = min(len(text), first.end() + 15)
            snippet = text[start:end].replace('\n', ' ')
            issues.append({
                "type": "narrative_bonus",
                "desc": desc,
                "context": snippet,
            })

    bonus = min(bonus_raw, NARRATIVE_MAX_BONUS)

    return penalty, bonus, issues


def calculate_dimension_score(penalty: int, bonus: int, char_count: int) -> float:
    """计算单维度得分（0-100）

    v3 评分公式（更敏感）：
      - 每条惩罚扣 8 分（固定值，不受长度影响）
      - 短文本额外加权：≤100字 ×2.5，≤200字 ×2.0，≤500字 ×1.5
      - 加分每条 +1 分，最多 +3 分
      - 封顶惩罚：最多扣 60 分（得分不低于 40）
    """
    # 基础扣分：每条固定 -8 分
    base_penalty = penalty * 8
    # 短文本加权
    if char_count <= 100:
        weight = 2.5
    elif char_count <= 200:
        weight = 2.0
    elif char_count <= 500:
        weight = 1.5
    else:
        weight = 1.0
    # 有效惩罚（封顶60分）
    effective_penalty = min(base_penalty * weight, 60)
    # 加分（封顶3分）
    bonus_points = min(bonus, 3)
    raw = max(0, 100 - effective_penalty + bonus_points)
    return round(min(100.0, float(raw)), 1)


def humanizer_9d(text: str) -> Dict:
    """执行九维质检评分"""
    body = strip_markdown(text)
    pure = re.sub(r'\s+', '', body)
    char_count = max(len(pure), 1)

    results = {}
    total_weighted = 0.0
    total_weight = 0.0
    all_issues = []

    for dim_key, dim_config in DIMENSIONS.items():
        weight = dim_config["weight"]
        pass_line = dim_config["pass_line"]
        name = dim_config["name"]

        # 主扣分检测
        penalty, issues = check_dimension(body, dim_key, PUNISHMENTS.get(dim_key, []))
        # 加分检测
        bonus, bonuses = check_bonus(body, dim_key, BONUS_PATTERNS.get(dim_key, []))
        # 额外检测
        extra_penalty = 0
        extra_issues = []
        if dim_key in EXTRA_CHECKS:
            ep, ei = check_dimension(body, dim_key, EXTRA_CHECKS[dim_key])
            extra_penalty += ep
            extra_issues.extend(ei)
        if dim_key == "rhythm":
            ep, ei = check_rhythm_balance(body)
            extra_penalty += ep
            extra_issues.extend(ei)
        elif dim_key == "emotion":
            ep, ei = check_emotion_show_dont_tell(body)
            extra_penalty += ep
            extra_issues.extend(ei)
        elif dim_key == "narrative_structure":
            # 叙事结构层独立检测（sepia/StoryScope 信号）
            n_penalty, n_bonus, n_issues = check_narrative_structure(body)
            extra_penalty += n_penalty
            extra_issues.extend(n_issues)
            # 叙事层加分（人类正向标记）抵消部分扣分
            bonus += n_bonus
            for ni in n_issues:
                if ni.get("type") == "narrative_bonus":
                    # 加分项也记录到 all_issues
                    bonuses.append({
                        "desc": ni["desc"],
                        "context": ni.get("context", ""),
                    })

        penalty += extra_penalty
        score = calculate_dimension_score(penalty, bonus, char_count)

        results[dim_key] = {
            "name": name,
            "weight": weight,
            "score": score,
            "pass_line": pass_line,
            "passed": score >= pass_line,
            "penalty": penalty,
            "bonus": bonus,
            "issues": issues,
            "bonuses": bonuses,
        }
        total_weighted += score * weight
        total_weight += weight

        for issue in issues:
            all_issues.append({"dimension": dim_key, **issue})
        for bonus_item in bonuses:
            all_issues.append({"dimension": dim_key, "type": "bonus", **bonus_item})
        # 叙事层特殊：extra_issues 里有 narrative_penalty/bonus 两种类型
        if dim_key == "narrative_structure":
            for ei in extra_issues:
                all_issues.append({"dimension": dim_key, **ei})

    overall = round(total_weighted / total_weight, 1) if total_weight > 0 else 0

    if overall >= 90:
        level, color = "S", "🟢"
    elif overall >= 80:
        level, color = "A", "🟢"
    elif overall >= 70:
        level, color = "B", "🟡"
    elif overall >= 60:
        level, color = "C", "🟠"
    else:
        level, color = "D", "🔴"

    passed_count = sum(1 for r in results.values() if r["passed"])
    failed_dims = [r["name"] for r in results.values() if not r["passed"]]

    return {
        "overall_score": overall,
        "level": level,
        "color": color,
        "passed_dimensions": passed_count,
        "total_dimensions": len(results),
        "failed_dimensions": failed_dims,
        "dimensions": results,
        "issues": all_issues,
        "char_count": char_count,
    }


def build_report(result: Dict, chapter_name: str = "") -> str:
    """生成人类可读报告（v3：含叙事结构层）"""
    lines = [
        "=" * 60,
        "📝 九维质检报告 v3（含叙事结构层）",
        "=" * 60,
        "",
        f"📄 章节: {chapter_name or '未命名'}",
        f"📏 字符数: {result['char_count']:,}",
        "",
        f"📊 综合评分: {result['overall_score']} 分  {result['color']} 等级 {result['level']}",
        f"   通过维度: {result['passed_dimensions']}/{result['total_dimensions']}",
    ]
    if result['failed_dimensions']:
        lines.append(f"   未通过: {', '.join(result['failed_dimensions'])}")
    lines.append("")

    # 分组：词句层 + 叙事结构层
    lines.append("📚 词句层（九维）")
    lines.append("┌─────────────────┬──────┬───────┬────────────────────────┐")
    lines.append("│ 维度            │ 权重 │ 得分  │ 状态                   │")
    lines.append("├─────────────────┼──────┼───────┼────────────────────────┤")
    for dim_key, dim in DIMENSIONS.items():
        if dim_key == "narrative_structure":
            continue  # 单独处理
        r = result['dimensions'][dim_key]
        status = "✅" if r['passed'] else "❌"
        fail_note = f"≤{r['pass_line']}" if not r['passed'] else ""
        lines.append(f"│ {dim['name']:<11} │ {int(dim['weight']*100):>4}% │ {r['score']:>5.1f}  │ {status} {fail_note} │")
    lines.append("└─────────────────┴──────┴───────┴────────────────────────┘")

    # 叙事结构层
    lines.append("")
    lines.append("🏛  叙事结构层（sepia/StoryScope 信号）")
    lines.append("┌─────────────────┬──────┬───────┬────────────────────────┐")
    ns = result['dimensions'].get('narrative_structure', {})
    if ns:
        status = "✅" if ns.get('passed') else "❌"
        fail_note = f"≤{ns.get('pass_line', 80)}" if not ns.get('passed') else ""
        lines.append(f"│ {'叙事结构':<11} │  14% │ {ns.get('score', 0):>5.1f}  │ {status} {fail_note} │")
        # 显示叙事层问题
        ns_issues = [i for i in result['issues'] if i.get('dimension') == 'narrative_structure']
        ns_penalty = [i for i in ns_issues if i.get('type') == 'narrative_penalty']
        ns_bonus   = [i for i in ns_issues if i.get('type') == 'narrative_bonus']
        if ns_penalty:
            lines.append(f"│ 扣分信号: {len(ns_penalty)} 处                    │")
            for i in ns_penalty[:6]:
                lines.append(f"│   ⚠️  {i.get('desc', i.get('context', ''))[:50]}")
        if ns_bonus:
            lines.append(f"│ 人类标记: {len(ns_bonus)} 处（加分）              │")
            for b in ns_bonus[:3]:
                lines.append(f"│   ✨  {b.get('desc', '')[:50]}")
    lines.append("└─────────────────┴──────┴───────┴────────────────────────┘")
    lines.append("")

    # 各维度问题明细
    dim_issues = {}
    dim_bonuses = {}
    for issue in result['issues']:
        dim_key = issue['dimension']
        if issue.get('type') in ('bonus', 'narrative_bonus'):
            dim_bonuses.setdefault(dim_key, []).append(issue)
        else:
            dim_issues.setdefault(dim_key, []).append(issue)

    for dim_key, dim in DIMENSIONS.items():
        if dim_key == "narrative_structure":
            continue  # 已在上方单独展示
        if dim_key not in dim_issues or not dim_issues[dim_key]:
            continue
        name = dim['name']
        issues = dim_issues[dim_key]
        lines.append(f"【{name}】{'✅' if result['dimensions'][dim_key]['passed'] else '❌'} {len(issues)} 个问题")
        for i in issues[:5]:
            lines.append(f"  ⚠️  {i.get('desc', i.get('context', ''))[:70]}")
            ctx = i.get('context', '')
            if ctx and 'desc' in i:
                lines.append(f"     📄 {ctx[:70]}")
        if len(issues) > 5:
            lines.append(f"  … 另 {len(issues)-5} 处")
        lines.append("")

    for dim_key in dim_bonuses:
        name = DIMENSIONS.get(dim_key, {}).get('name', dim_key)
        bonuses = dim_bonuses[dim_key]
        if dim_key == 'narrative_structure':
            continue  # 已展示
        lines.append(f"【{name}】✨ {len(bonuses)} 个正向特征")
        for b in bonuses[:3]:
            lines.append(f"  ✨ {b.get('desc', b.get('context', ''))[:70]}")
        lines.append("")

    lines.append("=" * 60)

    failed = [result['dimensions'][k] for k, v in DIMENSIONS.items() if not result['dimensions'][k]['passed']]
    if failed:
        lines.append("🔧 改进建议（按优先级排序）：")
        for f in sorted(failed, key=lambda x: x['score']):
            desc = f['issues'][0].get('desc', f['issues'][0].get('context', '')) if f['issues'] else '提升此项维度得分'
            lines.append(f"  {f['name']}({f['score']:.1f}分 ≤ {f['pass_line']}): {str(desc)[:60]}")
        lines.append("")

    return '\n'.join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description='九维质检评分工具 v2')
    parser.add_argument('--text', help='直接提供文本')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    parser.add_argument('--chapter-file', help='章节文件路径')
    args = parser.parse_args()

    if args.text:
        text = args.text
    elif args.chapter_file:
        text = Path(args.chapter_file).read_text(encoding='utf-8')
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("用法:")
        print("  python3 humanizer-9d.py --text \"文本\"")
        print("  python3 humanizer-9d.py --json --text \"文本\"")
        print("  python3 humanizer-9d.py --chapter-file chapter.md")
        sys.exit(1)

    if not text.strip():
        print("输入为空")
        sys.exit(1)

    result = humanizer_9d(text)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        chapter_name = Path(args.chapter_file).stem if args.chapter_file else '未命名'
        print(build_report(result, chapter_name))


if __name__ == "__main__":
    main()
