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
# 九维评分配置
# ============================================================================

DIMENSIONS = {
    "logic":          {"name": "逻辑性",         "weight": 0.18, "pass_line": 85, "desc": "时间线连续、设定一致、前后文无矛盾"},
    "character":      {"name": "角色一致性",     "weight": 0.16, "pass_line": 85, "desc": "言行是否符合档案、OOC检测"},
    "worldview":      {"name": "世界观一致性",   "weight": 0.08, "pass_line": 85, "desc": "地点/势力/规则/文化与世界build一致"},
    "era_adapt":      {"name": "时代适配度",     "weight": 0.14, "pass_line": 80, "desc": "禁用词、物价合理性、科技产物出现时间"},
    "dialogue":       {"name": "对话自然度",     "weight": 0.11, "pass_line": 80, "desc": "口语省略、方言痕迹、符合角色"},
    "literary":       {"name": "文学性",         "weight": 0.10, "pass_line": 75, "desc": "五感描写、比喻新鲜度、句式变化"},
    "emotion":        {"name": "情感表达",       "weight": 0.10, "pass_line": 80, "desc": "避免情感直给、动作替代、情绪曲线自然"},
    "rhythm":         {"name": "节奏感",         "weight": 0.09, "pass_line": 75, "desc": "连续对话/动作/描写的平衡、张弛有度"},
    "de_system":      {"name": "去系统化",       "weight": 0.04, "pass_line": 90, "desc": "系统面板、数据流、机械表达"},
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
        (r'秒钟|分钟|小时|天(?!(蒙蒙亮|亮|才|长|空|气|地|寒|昏|明|晚|夕|晓|黑|刚|将))', '现代时间单位（需上下文）'),
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
# 检测函数
# ============================================================================

def strip_markdown(text: str) -> str:
    """去除 Markdown 格式"""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
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
    """生成人类可读报告"""
    lines = [
        "=" * 60,
        "📝 九维质检报告 v2",
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
    lines.append("┌─────────────────┬──────┬───────┬────────────────────────┐")
    lines.append("│ 维度            │ 权重 │ 得分  │ 状态                   │")
    lines.append("├─────────────────┼──────┼───────┼────────────────────────┤")

    for dim_key, dim in DIMENSIONS.items():
        r = result['dimensions'][dim_key]
        status = "✅" if r['passed'] else "❌"
        fail_note = f"≤{r['pass_line']}" if not r['passed'] else ""
        lines.append(f"│ {dim['name']:<11} │ {int(dim['weight']*100):>4}% │ {r['score']:>5.1f}  │ {status} {fail_note} │")

    lines.append("└─────────────────┴──────┴───────┴────────────────────────┘")
    lines.append("")

    dim_issues = {}
    dim_bonuses = {}
    for issue in result['issues']:
        dim_key = issue['dimension']
        if issue.get('type') == 'bonus':
            dim_bonuses.setdefault(dim_key, []).append(issue)
        else:
            dim_issues.setdefault(dim_key, []).append(issue)

    for dim_key, dim in DIMENSIONS.items():
        if dim_key not in dim_issues or not dim_issues[dim_key]:
            continue
        name = dim['name']
        issues = dim_issues[dim_key]
        lines.append(f"【{name}】{'✅' if result['dimensions'][dim_key]['passed'] else '❌'} {len(issues)} 个问题")
        for i in issues[:5]:
            lines.append(f"  ⚠️  {i['desc']}")
            if i.get('context'):
                lines.append(f"     📄 {i['context'][:70]}")
        if len(issues) > 5:
            lines.append(f"  … 另 {len(issues)-5} 处")
        lines.append("")

    for dim_key in dim_bonuses:
        name = DIMENSIONS[dim_key]['name']
        bonuses = dim_bonuses[dim_key]
        lines.append(f"【{name}】✨ {len(bonuses)} 个正向特征")
        for b in bonuses[:3]:
            lines.append(f"  ✨ {b['desc']}")
        lines.append("")

    lines.append("=" * 60)

    failed = [result['dimensions'][k] for k, v in DIMENSIONS.items() if not result['dimensions'][k]['passed']]
    if failed:
        lines.append("🔧 改进建议（按优先级排序）：")
        for f in sorted(failed, key=lambda x: x['score']):
            desc = f['issues'][0]['desc'] if f['issues'] else '提升此项维度得分'
            lines.append(f"  {f['name']}({f['score']:.1f}分 ≤ {f['pass_line']}): {desc}")
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
