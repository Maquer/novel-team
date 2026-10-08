#!/usr/bin/env python3
"""
去AI味检测工具 v3 — 整合 lieflat 11条规则 + Novel-Creator 7大类检测

版本: v3.0.0
整合: lieflat-less-ai-tone (11条实测规则) + Novel-Creator-Skill (7大类检测)
特性: Tier 1A/1B分层 + 小说专用词汇库 + 两遍式润色prompt

用法:
  python3 novel-humanizer.py < 文章.txt
  python3 novel-humanizer.py --text "你的文本"
  python3 novel-humanizer.py --json < 文章.txt
  python3 novel-humanizer.py --prompt --chapter-file chapter.md
"""

import sys, re, json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ============================================================================
# lieflat 11条规则（已验证）
# ============================================================================

# 规则1 · 翻案腔
LIEFLAT_RULE1 = [
    (r'不是.{0,12}而是', '翻案腔「不是…而是」'),
    (r'并非.{0,12}而是', '翻案腔「并非…而是」'),
    (r'不在于.{0,12}而在于', '翻案腔「不在于…而在于」'),
    (r'与其说.{0,12}不如说', '翻案腔「与其说…不如说」'),
    (r'表面.{0,12}实则', '翻案腔「表面…实则」'),
    (r'看似.{0,12}实则', '翻案腔「看似…实则」'),
    (r'不是.{0,12}。而是', '翻案腔「不是。而是」'),
    (r'以为.{0,8}其实', '翻案腔「以为…其实」'),
    (r'回头才发现', '翻案腔「回头才发现」'),
    (r'说到底', '翻案腔「说到底」'),
    (r'答案恰恰相反', '翻案腔「答案恰恰相反」'),
    (r'不重要.{0,10}重要的是', '翻案腔「A不重要，重要的是B」'),
]

# 规则2 · 顿号罗列过密
LIEFLAT_RULE2 = re.compile(r'[^\n。！？；]{0,60}[、][^、\n。！？；]{1,12}[、][^、\n。！？；]{1,12}')

# 规则3 · 相邻句结构同款
# 结构签名归一化：把每段连续中文替换为 C{字数} 标记，再比对完整骨架
# 这样 Markdown 表格行（结构不同）不会被误判为同构
def _structure_sig(s: str) -> str:
    """句法骨架归一化
    '杜甫的七律对仗工整，这是汉语诗歌的传统' → 'C10，C8'
    '他写了一首三行诗，短句读起来很舒服'     → 'C10，C9'
    旧版只比逗点数+长度比例，导致表格行大量误报（实测+12~34分偏差根因）。
    """
    parts = re.split(r'([^一-鿿])', s)
    sig = []
    for p in parts:
        if p and re.match(r'[一-鿿]+', p):
            sig.append(f'C{len(p)}')
        elif p:
            sig.append(p)
    return ''.join(sig)

def _check_lieflat_rule3(text: str) -> List[Dict]:
    sents = [s.strip() for s in re.split(r'[。！？\n]', text) if s.strip()]
    hits = []
    i = 0
    while i < len(sents) - 1:
        run = [i]
        j = i + 1
        while j < len(sents):
            a, b = sents[run[-1]], sents[j]
            ca, cb = a.count('，'), b.count('，')
            # 必须同构：逗号数相同 + 结构签名完全一致 + 长度比例合理
            if (ca == cb
                    and _structure_sig(a) == _structure_sig(b)
                    and 0.5 < len(a) / max(len(b), 1) < 2.0
                    and ca >= 1):
                run.append(j)
                j += 1
            else:
                break
        if len(run) >= 2:
            hits.append({
                'rule': 'lieflat·规则3·相邻句结构同款',
                'text': ' / '.join(sents[k] for k in run[:3]),
                'score': len(run) - 1,
            })
            i = run[-1] + 1
        else:
            i += 1
    return hits

# 规则4 · 破折号滥用
LIEFLAT_RULE4_LIMIT = 1.5

# 规则4b · em dash 密度（the-last-fingerprint 借鉴，对齐 humanizer-check）
# —— 是 Markdown 结构思维泄露到散文中的最小残留单元
LIEFLAT_RULE4B_DASH_RE = re.compile(r'——')
LIEFLAT_RULE4B_WARN = 5.0    # 每千字 >5 个 em dash → 告警
LIEFLAT_RULE4B_SEVERE = 10.0 # 每千字 >10 个 → 严重

# 规则5 · 冒号滥用
LIEFLAT_RULE5A = re.compile(r'(一句话总结|核心是|关键在于|原因如下|结论|本质上|换句话说|说白了|简单来说|概括来说|总结来说)[:：]')
LIEFLAT_RULE5B = re.compile(r'^[^:：\n]{4,40}[:：]\s*$', re.M)

# 规则6 · 序数词当小标题
LIEFLAT_RULE6 = re.compile(r'^#{1,6}\s*(一|二|三|四|五|六|七|八|九|十|第一|第二|第三|第四|第五)\s*[、.]', re.M)
LIEFLAT_RULE6_BOLD = re.compile(r'^\*\*+\s*(一|二|三|四|五|六|七|八|九|十|第一|第二|第三|第四|第五)\s*[、.]\s*', re.M)

# 规则7 · 拟人化喻体
LIEFLAT_RULE7 = re.compile(r'(?:像|相当于|就像|好比|如同|仿佛|宛如)\s*(?:一个|一位|一名|一尊|一只|一头)\s*(导师|秘书|助手|顾问|管家|审查员|实习生|老师|教练|医生|朋友|引路人|守护者|智者|军师|操盘手|裁判|法官|导演|编剧|翻译|向导|助理|保镖|保姆)')

# 规则8 · 具体数据被概括表述盖掉
LIEFLAT_RULE8_ABSTRACT = re.compile(r'(?:显著|大幅|明显|巨大|相当|可观|巨大地|明显地|显著地)(?:地)?(?:提升|增长|改善|优化|增加|减少|降低|加快|缩短|延长|扩大|缩小|增强|减弱|提高|下降|突破|飞跃)')
LIEFLAT_RULE8_NOUNIFY = re.compile(r'(?:完成|实现|进行|开展|做了|做到)(?:了|过)?(?:对|把)?\s*[\u4e00-\u9fa5]{2,10}\s*(?:的)?\s*(?:提升|增长|改善|优化|调整|变革|改变|改造|升级|推进|迭代|重构|梳理|规范|治理|管理|设计|开发|建设|打造|塑造)')
LIEFLAT_RULE8_NUMBER = re.compile(r'\d+(?:\.\d+)?%?|[一二三四五六七八九十百千万亿]+')

# 规则9 · 禁用起手式
LIEFLAT_RULE9 = re.compile(r'^(?:说白了|说穿了|说到底|先说结论|直接说|直说|坦白讲|讲白了)[:：]?\s*', re.M)

# 规则10 · 翻译腔
LIEFLAT_RULE10A = re.compile(r'(?P<mod>[^\n。！？；，—–…]{15,})的(?P<head>[^，。！？；—–…]{2,10})(?:的|，|。|！|？|；)')
LIEFLAT_RULE10B = re.compile(r'当[^，。！？；]{2,30}时，')
LIEFLAT_RULE10C = re.compile(r'(?:对于|就|关于)\s*[^，。！？；]{2,20}(?:来说|而言|方面)|在[^，。！？；]{8,25}(?:里|中|时|下|上|之际|之间|处)')
LIEFLAT_RULE10D = re.compile(r'^(?:然而|因此|此外|与此同时|换言之|总而言之|综上所述|总的说来|概括来说|也就是说)[:：，]?\s*', re.M)
LIEFLAT_RULE10E = re.compile(r'^(?:这意味着|这表明|这说明|换句话说|也就是说)[:：，]?\s*', re.M)

# 规则11 · 段首零主语评论
LIEFLAT_RULE11 = re.compile(r'^(?:听起来|看起来|说白了|值得注意的是|更重要的是|关键在于|问题在于|意味着|不难看出|显而易见|不言而喻)[:：，]?\s*', re.M)
LIEFLAT_RULE11_BACKREF = re.compile(r'[这那其此上面下面以上以下此前]')

# ============================================================================
# Novel-Creator 7大类检测（小说专用）
# ============================================================================

# Category 1 - AI 高频词汇
NC_AI_VOCAB = [
    ("不禁", "情感反应套话，角色常失去主动性"),
    ("仿佛", "过度比喻词"),
    ("宛如", "过度比喻词"),
    ("宛若", "过度比喻词"),
    ("恍若", "过度比喻词"),
    ("仿若", "过度比喻词"),
    ("好似", "过度比喻词"),
    ("映入眼帘", "陈词滥调视觉过渡"),
    ("涌入眼帘", "陈词滥调视觉过渡"),
    ("跃入眼帘", "陈词滥调视觉过渡"),
    ("此时此刻", "时间强调膨胀"),
    ("就在此时", "时间强调膨胀"),
    ("恰在此时", "时间强调膨胀"),
    ("在这一刻", "时间强调膨胀"),
    ("心中暗道", "内心独白滥用"),
    ("心中暗想", "内心独白滥用"),
    ("暗自思忖", "内心独白滥用"),
    ("心中一动", "内心独白滥用"),
    ("心中一凛", "内心独白滥用"),
    ("心念一动", "内心独白滥用"),
    ("沉声道", "对话标签套话"),
    ("淡淡地说", "对话标签套话"),
    ("轻声道", "对话标签套话"),
    ("缓缓说道", "对话标签套话"),
    ("淡然道", "对话标签套话"),
    ("漠然道", "对话标签套话"),
    ("脸色一变", "反应套话"),
    ("神情一凛", "反应套话"),
    ("眉头微皱", "反应套话"),
    ("身形一顿", "动作套话"),
    ("脚步一顿", "动作套话"),
    ("身子微微一颤", "动作套话"),
    ("目光如炬", "眼睛描写套话"),
    ("目光深邃", "眼睛描写套话"),
    ("深邃的眸子", "眼睛描写套话"),
    ("嘴角微扬", "微笑描写套话（AI特征极强）"),
    ("勾起一抹弧度", "微笑描写套话（AI特征极强）"),
    ("嘴角勾起", "微笑描写套话"),
    ("只见", "场景过渡套话"),
    ("但见", "场景过渡套话"),
    ("感慨良多", "情感套话"),
    ("百感交集", "情感套话"),
    ("不禁感叹", "情感套话"),
    ("不由自主", "主体性剥夺词"),
    ("不由得", "主体性剥夺词"),
    ("情不自禁", "主体性剥夺词"),
]

# Category 2 - 弱化副词泛滥
NC_WEAK_ADVERBS = [
    "微微", "淡淡", "缓缓", "轻轻", "悄悄", "悄然",
    "深深", "静静", "慢慢", "默默", "暗暗", "隐隐",
    "渐渐", "徐徐", "徐徐地",
]
NC_ADVERB_THRESHOLD = 3  # 每千字阈值

# Category 3 - 意义膨胀
NC_SIGNIFICANCE = [
    ("意义深远", "意义膨胀"),
    ("影响深远", "意义膨胀"),
    ("意义非凡", "意义膨胀"),
    ("令人叹为观止", "意义膨胀"),
    ("叹为观止", "意义膨胀"),
    ("前所未有", "意义膨胀"),
    ("史无前例", "意义膨胀"),
    ("意味深长", "意义膨胀"),
    ("深入人心", "意义膨胀"),
    ("可谓", "意义膨胀：用繁替简"),
    ("堪称", "意义膨胀：用繁替简"),
    ("不得不说", "评论性插入"),
    ("值得一提的是", "评论性插入"),
    ("不容忽视", "评论性插入"),
    ("毋庸置疑", "评论性插入"),
    ("不容置疑", "评论性插入"),
]

# Category 4 - 通用结论套话
NC_CONCLUSION = [
    "展望未来", "未来可期", "前途无量",
    "前景广阔", "大有可为", "方兴未艾",
    "相信未来", "充满希望", "充满期待",
    "前程似锦", "大展宏图",
]

# Category 5 - 段落首句总结模式
NC_PARA_STARTERS = [
    "总的来说", "总而言之", "综上所述",
    "由此可见", "不难看出", "显而易见",
    "值得注意的是", "不容忽视的是",
    "更重要的是", "尤其值得一提",
    "事实上", "实际上", "说到底",
    "换句话说", "简而言之",
]

# Category 6 - 翻译腔/正式语体入侵
NC_FORMAL = [
    ("于是乎", "翻译腔正式语体"),
    ("然而事实上", "正式论述语体入侵"),
    ("然而实际上", "正式论述语体入侵"),
    ("理所当然", "正式论述语体入侵"),
    ("一方面", "论文结构词入侵小说"),
    ("另一方面", "论文结构词入侵小说"),
    ("与此同时", "正式新闻语体"),
    ("从而", "正式逻辑连接词"),
    ("因而", "正式逻辑连接词"),
    ("诚然", "正式让步连词"),
]

# Category 7 - 排比三连
NC_TRIO_PATTERN = re.compile(r'[\u4e00-\u9fff]{2,8}[、，][^\n、，。！？]{2,8}[、，][^\n、，。！？]{2,8}[。，！]')

# ============================================================================
# Tier分类（对齐 avoid-ai-writing）
# ============================================================================

TIERclassification = {
    # 规则4b·em dash 密度过高（新增：对齐 humanizer-check）
    'lieflat·规则4b·em dash 密度过高': '1A',
    # lieflat 规则
    'lieflat·规则1·翻案腔': '1A',
    'lieflat·规则2·顿号罗列过密': '1A',
    'lieflat·规则3·相邻句结构同款': '1A',
    'lieflat·规则4·破折号滥用': '1A',
    'lieflat·规则5·冒号滥用': '1A',
    'lieflat·规则6·序数词当小标题': '1A',
    'lieflat·规则7·拟人化喻体': '1A',
    'lieflat·规则8·具体数据被概括表述盖掉': '1B',
    'lieflat·规则8·名词化结构': '1B',
    'lieflat·规则9·禁用起手式': '1A',
    'lieflat·规则10·翻译腔': '1A',
    'lieflat·规则11·段首零主语评论': '1A',
    # Novel-Creator 规则
    'nc·Category1·AI高频词汇': '1A',
    'nc·Category2·弱化副词泛滥': '1A',
    'nc·Category3·意义膨胀': '1A',
    'nc·Category4·通用结论套话': '1A',
    'nc·Category5·论文式段落结构': '1A',
    'nc·Category6·正式语体入侵': '1A',
    'nc·Category7·排比三连': '1A',
}

TIER1B_WEIGHT = 0.3

# ============================================================================
# 检测核心
# ============================================================================

def _strip_markdown(text: str) -> str:
    """去除Markdown标记"""
    # FIX 2026-09-30：先剥离文件开头的 frontmatter（---...--- 元数据块）。
    # 行为变化：此前标题/作者/标签等元数据会被计入 AI 味扫描，现在不再计入。
    lines = text.splitlines()
    if lines and lines[0].strip() == '---':
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                lines = lines[i + 1:]
                break
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        if stripped.startswith(('- ', '* ', '1.', '2.', '3.')):
            continue
        out.append(line)
    return '\n'.join(out)

def _extract_context(text: str, pos: int, window: int = 40) -> str:
    """截取上下文"""
    start = max(0, pos - window)
    end = min(len(text), pos + window)
    snippet = text[start:end].replace('\n', ' ')
    if start > 0:
        snippet = '…' + snippet
    if end < len(text):
        snippet = snippet + '…'
    return snippet

def detect_all(text: str, threshold: float = 15.0) -> Dict:
    """执行完整检测

    FIX 2026-09-30：--threshold 参数此前只解析、从未使用（死参数），现正式接入。
    设计决策：文字分级阈值按 threshold/15.0 等比缩放；threshold=15.0（默认）时与旧行为完全一致。
    注意：门禁（gate-check.py）判定用的是 tier_1a 原始分，不受本分级阈值影响。
    """
    body = _strip_markdown(text)
    pure = re.sub(r'\s+', '', body)
    char_count = max(len(pure), 1)
    per_thousand = char_count / 1000
    
    hits = []
    
    # ==================== lieflat 规则检测 ====================
    
    # 规则1 · 翻案腔
    for pat, desc in LIEFLAT_RULE1:
        for m in re.finditer(pat, body):
            ctx = body[max(0, m.start() - 20):m.end() + 30].replace('\n', ' ')
            hits.append({'rule': 'lieflat·规则1·翻案腔', 'desc': desc, 'text': ctx, 'score': 2})
    
    # 规则2 · 顿号罗列过密
    for m in LIEFLAT_RULE2.finditer(body):
        ctx = body[max(0, m.start() - 15):m.end() + 15].replace('\n', ' ')
        hits.append({'rule': 'lieflat·规则2·顿号罗列过密', 'desc': '一个分句内两个以上顿号', 'text': ctx, 'score': 1})
    
    # 规则3 · 相邻句结构同款
    for h in _check_lieflat_rule3(body):
        hits.append(h)
    
    # 规则4 · 破折号滥用（中文破折号 ——，非英文 em dash）
    # 按连续段计数，避免 "——" 被 count('—') 和 count('——') 重复计 3 次
    dash_runs = re.findall(r'—+', body)
    total_dashes = len(dash_runs)
    if char_count > 0:
        per_k = total_dashes / (char_count / 1000)
        if per_k > LIEFLAT_RULE4_LIMIT:
            hits.append({'rule': 'lieflat·规则4·破折号滥用', 'desc': f'破折号 {per_k:.2f}/千字（人类0.80，AI 2.38）', 'text': f'全文共{total_dashes}处', 'score': 3})
    
    # 规则4b · em dash 密度（Markdown 结构残留）
    em_dash_runs = LIEFLAT_RULE4B_DASH_RE.findall(body)
    em_dash_count = len(em_dash_runs)
    if char_count > 0:
        em_per_k = em_dash_count / (char_count / 1000)
        if em_per_k >= LIEFLAT_RULE4B_WARN:
            severity = '严重' if em_per_k >= LIEFLAT_RULE4B_SEVERE else '告警'
            hits.append({
                'rule': 'lieflat·规则4b·em dash 密度过高',
                'desc': f'em dash {em_per_k:.2f}/千字（{severity}；GPT-4.1 抑制后 3.86‰，Llama=0）',
                'text': f'全文共 {em_dash_count} 处 em dash',
                'score': 3 if em_per_k >= LIEFLAT_RULE4B_SEVERE else 2,
            })
    
    # 规则5 · 冒号滥用
    for m in LIEFLAT_RULE5A.finditer(body):
        ctx = body[max(0, m.start() - 10):m.end() + 30].replace('\n', ' ')
        hits.append({'rule': 'lieflat·规则5·冒号滥用', 'desc': '提示语引出内容', 'text': ctx, 'score': 1})
    for m in LIEFLAT_RULE5B.finditer(body):
        hits.append({'rule': 'lieflat·规则5·冒号滥用', 'desc': '空转句引出列表', 'text': m.group(0), 'score': 2})
    
    # 规则6 · 序数词当小标题
    headers = LIEFLAT_RULE6.findall(body) + LIEFLAT_RULE6_BOLD.findall(body)
    if len(headers) >= 3:
        hits.append({'rule': 'lieflat·规则6·序数词当小标题', 'desc': f'小标题以序数词编号，共{len(headers)}个', 'text': ' / '.join(headers[:5]), 'score': 3})
    
    # 规则7 · 拟人化喻体
    for m in LIEFLAT_RULE7.finditer(body):
        ctx = body[max(0, m.start() - 10):m.end() + 30].replace('\n', ' ')
        hits.append({'rule': 'lieflat·规则7·拟人化喻体', 'desc': '把工具比作理想化的人', 'text': ctx, 'score': 2})
    
    # 规则8 · 具体数据被概括表述盖掉
    paragraphs = body.split('\n')
    for pi, para in enumerate(paragraphs):
        has_number = bool(LIEFLAT_RULE8_NUMBER.search(para))
        if not has_number:
            continue
        for m in LIEFLAT_RULE8_ABSTRACT.finditer(para):
            ctx = para[max(0, m.start() - 15):m.end() + 15]
            hits.append({'rule': 'lieflat·规则8·具体数据被概括表述盖掉', 'desc': '同段已有具体数值，却被概括说法盖住', 'text': ctx, 'score': 2})
        for m in LIEFLAT_RULE8_NOUNIFY.finditer(para):
            ctx = para[max(0, m.start() - 10):m.end() + 25]
            hits.append({'rule': 'lieflat·规则8·名词化结构', 'desc': '可恢复动词的名词化表达', 'text': ctx, 'score': 1})
    
    # 规则9 · 禁用起手式
    for m in LIEFLAT_RULE9.finditer(body):
        ctx = body[max(0, m.start() - 5):m.end() + 25].replace('\n', ' ')
        hits.append({'rule': 'lieflat·规则9·禁用起手式', 'desc': '禁用起手式', 'text': ctx, 'score': 1})
    
    # 规则10 · 翻译腔
    for m in LIEFLAT_RULE10A.finditer(body):
        mod, head = m.group('mod'), m.group('head')
        if len(mod) > len(head):
            ctx = body[max(0, m.start() - 10):m.end() + 25].replace('\n', ' ')
            hits.append({'rule': 'lieflat·规则10·翻译腔', 'desc': f'修饰语({len(mod)}字)长于被修饰语({len(head)}字)', 'text': ctx, 'score': 1})
    for m in LIEFLAT_RULE10B.finditer(body):
        ctx = body[max(0, m.start() - 5):m.end() + 20].replace('\n', ' ')
        hits.append({'rule': 'lieflat·规则10·翻译腔', 'desc': '"当…时"前置时间从句', 'text': ctx, 'score': 1})
    for m in LIEFLAT_RULE10C.finditer(body):
        ctx = body[max(0, m.start() - 5):m.end() + 25].replace('\n', ' ')
        hits.append({'rule': 'lieflat·规则10·翻译腔', 'desc': '前置话题壳', 'text': ctx, 'score': 1})
    for m in LIEFLAT_RULE10D.finditer(body):
        ctx = body[max(0, m.start() - 5):m.end() + 25].replace('\n', ' ')
        hits.append({'rule': 'lieflat·规则10·翻译腔', 'desc': '句首连接词当路标', 'text': ctx, 'score': 1})
    for m in LIEFLAT_RULE10E.finditer(body):
        ctx = body[max(0, m.start() - 5):m.end() + 25].replace('\n', ' ')
        hits.append({'rule': 'lieflat·规则10·翻译腔', 'desc': '"这意味着"式复述句', 'text': ctx, 'score': 1})
    
    # 规则11 · 段首零主语评论
    paras = [p.strip() for p in body.split('\n') if p.strip()]
    for pi, para in enumerate(paras):
        if pi == 0:
            continue
        m = LIEFLAT_RULE11.match(para)
        if m and not LIEFLAT_RULE11_BACKREF.search(para[:m.end() + 15]):
            hits.append({'rule': 'lieflat·规则11·段首零主语评论', 'desc': '非首段以评论语开头且无回指成分', 'text': para[:m.end() + 20], 'score': 2})
    
    # ==================== Novel-Creator 7大类检测 ====================
    
    # Category 1 · AI高频词汇
    total_vocab_count = 0
    vocab_hits = []
    for phrase, reason in NC_AI_VOCAB:
        positions = [m.start() for m in re.finditer(re.escape(phrase), body)]
        if positions:
            count = len(positions)
            total_vocab_count += count
            examples = [_extract_context(body, p) for p in positions[:2]]
            vocab_hits.append({'phrase': phrase, 'count': count, 'reason': reason, 'examples': examples})
    if vocab_hits:
        top_phrases = sorted(vocab_hits, key=lambda x: x['count'], reverse=True)[:5]
        top_names = ', '.join(f'{h["phrase"]}(×{h["count"]})' for h in top_phrases)
        hits.append({
            'rule': 'nc·Category1·AI高频词汇',
            'desc': f'发现{total_vocab_count}处AI高频词，Top5: {top_names}',
            'text': '见详情',
            'score': min(total_vocab_count, 10),
            'details': vocab_hits
        })
    
    # Category 2 · 弱化副词泛滥
    total_adverb_count = 0
    adverb_hits = []
    for adv in NC_WEAK_ADVERBS:
        positions = [m.start() for m in re.finditer(re.escape(adv), body)]
        if positions:
            count = len(positions)
            total_adverb_count += count
            adverb_hits.append({'adverb': adv, 'count': count})
    adverb_density = total_adverb_count / per_thousand if per_thousand else 0
    if adverb_density > NC_ADVERB_THRESHOLD:
        hits.append({
            'rule': 'nc·Category2·弱化副词泛滥',
            'desc': f'密度{adverb_density:.1f}/千字（阈值{NC_ADVERB_THRESHOLD}）',
            'text': f'共{total_adverb_count}处',
            'score': 3,
            'details': adverb_hits
        })
    
    # Category 3 · 意义膨胀
    significance_hits = []
    for phrase, reason in NC_SIGNIFICANCE:
        positions = [m.start() for m in re.finditer(re.escape(phrase), body)]
        if positions:
            significance_hits.append({'phrase': phrase, 'count': len(positions), 'reason': reason})
    if significance_hits:
        hits.append({
            'rule': 'nc·Category3·意义膨胀',
            'desc': f'发现{len(significance_hits)}类意义膨胀词',
            'text': ', '.join(h['phrase'] for h in significance_hits[:4]),
            'score': len(significance_hits),
            'details': significance_hits
        })
    
    # Category 4 · 通用结论套话
    conclusion_hits = [p for p in NC_CONCLUSION if p in body]
    if conclusion_hits:
        hits.append({
            'rule': 'nc·Category4·通用结论套话',
            'desc': f'发现{len(conclusion_hits)}处结论套话',
            'text': ', '.join(conclusion_hits),
            'score': len(conclusion_hits),
        })
    
    # Category 5 · 论文式段落结构
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]
    summary_para_count = 0
    summary_examples = []
    for para in paragraphs:
        first_sentence = re.split(r'[，。！？]', para)[0]
        for starter in NC_PARA_STARTERS:
            if first_sentence.startswith(starter):
                summary_para_count += 1
                summary_examples.append(first_sentence[:60])
                break
    essay_ratio = summary_para_count / max(len(paragraphs), 1)
    if essay_ratio > 0.25:
        hits.append({
            'rule': 'nc·Category5·论文式段落结构',
            'desc': f'{summary_para_count}/{len(paragraphs)}段以总结句开头',
            'text': '论文写法入侵小说',
            'score': 3,
            'examples': summary_examples[:3]
        })
    
    # Category 6 · 正式语体入侵
    formal_hits = []
    for phrase, reason in NC_FORMAL:
        positions = [m.start() for m in re.finditer(re.escape(phrase), body)]
        if positions:
            formal_hits.append({'phrase': phrase, 'count': len(positions), 'reason': reason})
    if formal_hits:
        hits.append({
            'rule': 'nc·Category6·正式语体入侵',
            'desc': f'发现{len(formal_hits)}类正式语体词',
            'text': ', '.join(h['phrase'] for h in formal_hits[:3]),
            'score': len(formal_hits),
            'details': formal_hits
        })
    
    # Category 7 · 排比三连
    trio_matches = NC_TRIO_PATTERN.findall(body)
    trio_count = len(trio_matches)
    if trio_count > 3:
        hits.append({
            'rule': 'nc·Category7·排比三连',
            'desc': f'发现{trio_count}处三元排比',
            'text': '句式结构雷同',
            'score': min(trio_count, 5),
            'examples': trio_matches[:3]
        })
    
    # ==================== 综合评分 ====================
    
    total_score = sum(h['score'] for h in hits)
    
    # 分层计分
    total_1A = 0
    total_1B = 0
    for h in hits:
        tier = TIERclassification.get(h['rule'], '1A')
        h['tier'] = tier
        if tier == '1A':
            total_1A += h['score']
        else:
            total_1B += h['score']
    
    weighted_score = total_1A + int(total_1B * TIER1B_WEIGHT)
    
    # 分级
    # FIX 2026-09-30：分级阈值接入 threshold，按 threshold/15.0 等比缩放；
    # 默认 15.0 时为 5/15/25，与旧行为完全一致。
    _scale = (threshold / 15.0) if threshold else 1.0
    _lv1, _lv2, _lv3 = 5 * _scale, 15 * _scale, 25 * _scale
    if weighted_score == 0:
        level, color = '✅ 干净', '🟢'
    elif weighted_score <= _lv1:
        level, color = '🟢 极轻AI味', '🟢'
    elif weighted_score <= _lv2:
        level, color = '🟡 轻微AI味', '🟡'
    elif weighted_score <= _lv3:
        level, color = '🔴 明显AI味', '🔴'
    else:
        level, color = '🚨 严重AI味，建议重写', '🚨'
    
    return {
        'char_count': char_count,
        'paragraph_count': len(paragraphs),
        'total_score': total_score,
        'weighted_score': weighted_score,
        'tier_1a': total_1A,
        'tier_1b': total_1B,
        'level': level,
        'color': color,
        'threshold': threshold,  # FIX 2026-09-30：输出生效阈值，便于门禁侧对账（新增键，旧键不变）
        'hits': hits,
        'source': 'lieflat 11条 + Novel-Creator 7大类'
    }


# ============================================================================
# 报告生成
# ============================================================================

def build_report(result: Dict, chapter_name: str = '') -> str:
    """生成人类可读报告"""
    lines = [
        '=' * 60,
        '📝 去AI味检测报告 v3（lieflat 11条 + Novel-Creator 7大类）',
        '=' * 60,
        '',
        f'📊 综合评分: {result["weighted_score"]} 分  {result["color"]} {result["level"]}',
        f'   ├─ Tier 1A（AI 频率标记，权重高）: {result["tier_1a"]} 分',
        f'   └─ Tier 1B（清晰化编辑，权重低）: {result["tier_1b"]} 分 × 0.3 = {int(result["tier_1b"] * 0.3)} 分',
        f'   ────────────────────────────────',
        f'   原始命中分（未分层）: {result["total_score"]} 分',
        '',
        f'📄 章节: {chapter_name or "未命名"}',
        f'📏 字符数: {result["char_count"]:,}',
        f'📑 段落数: {result["paragraph_count"]}',
        ''
    ]
    
    if not result['hits']:
        lines.append('🎉 未命中任何规则。按白名单原则，逐字保留原文。')
        lines.append('')
        lines.append('⚠️  未命中 ≠ 确定是人写的。本清单只覆盖 lieflat+Novel-Creator 语料验证过的')
        lines.append('   18 类触发标记，不覆盖的区域不做判断。')
    else:
        by_rule = {}
        for h in result['hits']:
            by_rule.setdefault(h['rule'], []).append(h)
        
        lines.append('🔍 发现的问题：')
        lines.append('')
        for rule, items in by_rule.items():
            lines.append(f'【{rule}】（{len(items)} 处）:')
            for h in items[:3]:
                desc = h.get('desc', '未知')
                lines.append(f'   ⚠️  {desc}')
                text = h.get('text', '')
                if text and text != '见详情':
                    lines.append(f'      📄 {text[:80]}')
            if len(items) > 3:
                lines.append(f'   … 另 {len(items)-3} 处')
            lines.append('')
        
        lines.append('')
        lines.append('=' * 60)
        lines.append('🔧 改写原则（白名单式）:')
        lines.append('  1. 只改命中规则处，未命中句子逐字保留')
        lines.append('  2. 每处改动对应明确规则编号，无对应规则的改动必须撤销')
        lines.append('  3. 不润色、不改语气、不调结构、不重组观点')
        lines.append('  4. 每个改后的实词必须能在原文指出出处')
        lines.append('  5. 不补虚词、不换代词、不调句长、不拆段落')
        lines.append('  6. 正文里的"首先…其次"、句内同构排比、比喻——不改')
        lines.append('')
        lines.append('=' * 60)
    
    return '\n'.join(lines)


def build_prompt(result: Dict, chapter_text: str) -> str:
    """生成两遍式润色prompt"""
    if not result['hits']:
        return """## 校稿任务：精细润色

本章经自动检测，未发现显著AI写作痕迹，整体质量良好。

执行精细润色：
1. **节奏检查**：阅读每段，找出连续三句以上等长的段落并调整节奏
2. **具体化检查**：把任何模糊的情感/状态描述替换为具体行动或细节
3. **结尾钩子**：末段是否留有足够的悬念或行动张力
4. **个人风格**：全篇是否有独特的叙事声音，还是过于"中性标准"

完成后输出修改版本（变化量建议控制在5%以内）。"""
    
    issue_summary = '\n'.join(f'- {h.get("desc", "未知问题")}' for h in result['hits'][:10])
    
    return f"""## 校稿任务：去除 AI 写作痕迹

本章已通过自动检测，发现以下 AI 写作特征：

{issue_summary}

---

### 执行方式：两遍式润色

**第一遍：清除 AI 模式**

针对以下类型逐段修改，用具体细节替代抽象套话：

**A. AI高频词替换原则**
- "不禁" → 直接写角色的行动
- "仿佛/宛如/宛若" → 用具体感知描写替代
- "映入眼帘" → 直接写看到了什么
- "心中暗道/暗自思忖" → 删除或改为行动
- "沉声道/淡淡地说" → 统一用"说"或删标签
- "脸色一变/身形一顿" → 写具体的生理反应
- "嘴角微扬/勾起一抹弧度" → "他笑了"或删掉
- "不由自主/情不自禁" → 改为角色主动行动

**B. 弱化副词瘦身**
删除"微微/淡淡/缓缓/轻轻/悄悄/悄然"等，每千字不超过3个。

**C. 意义膨胀处理**
把"意义深远/可谓/前所未有"等改为具体事实描述。
例：~~"这次交谈意义深远"~~ → "那天之后，他改变了用兵的节奏"

**D. 段落结构调整**
消除以总结句开头的段落，改为以行动/感知/对话开头。
例：~~"不难看出，他已下定决心"~~ → 直接写他做了什么。

**E. 通用结论改写**
末尾不用"未来可期"类结语，改为具体的悬念或行动钩子。

---

**第二遍：审查剩余 AI 味**

完成第一遍后，问自己：
> "这段文字哪些地方还是明显AI生成的感觉？"

列出3-5条具体问题，然后针对它们再次修改。

判断标准（有以下任一即需修改）：
- 每句话节奏相同、长度相近
- 情感表达依赖套话而非具体细节
- 角色反应都是被动的（"不禁"、"不由"）
- 段落间过渡依赖"此时"、"与此同时"

---

### 输出要求

1. 给出润色后的完整章节正文
2. 不改变剧情内容，只改写表达方式
3. 保留所有章节结构（标题等）
4. 修改量建议：字数变化控制在±10%以内
"""


# ============================================================================
# 主入口
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='去AI味检测工具 v3（lieflat + Novel-Creator）')
    parser.add_argument('--text', help='直接提供文本')
    parser.add_argument('--json', action='store_true', help='输出JSON格式')
    parser.add_argument('--prompt', action='store_true', help='生成润色prompt')
    parser.add_argument('--chapter-file', help='章节文件路径')
    parser.add_argument('--max-fixes', '-m', type=int, default=3, help='最大修复处数（默认3处/章）')
    parser.add_argument('--threshold', type=float, default=15.0, help='AI味阈值（默认15）')
    
    args = parser.parse_args()
    
    # 获取文本
    if args.text:
        text = args.text
    elif args.chapter_file:
        text = Path(args.chapter_file).read_text(encoding='utf-8')
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("用法:")
        print("  python3 novel-humanizer.py < 文章.txt")
        print("  python3 novel-humanizer.py --text \"你的文本\"")
        print("  python3 novel-humanizer.py --json < 文章.txt")
        print("  python3 novel-humanizer.py --prompt --chapter-file chapter.md")
        sys.exit(1)
    
    if not text.strip():
        print("输入为空")
        sys.exit(1)
    
    # 执行检测
    # FIX 2026-09-30：--threshold 正式传入 detect_all（此前解析后被丢弃）
    result = detect_all(text, threshold=args.threshold)
    
    # 输出结果
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.prompt:
        chapter_name = Path(args.chapter_file).stem if args.chapter_file else '未知章节'
        print(build_prompt(result, text))
    else:
        chapter_name = Path(args.chapter_file).stem if args.chapter_file else '未命名'
        print(build_report(result, chapter_name))


if __name__ == '__main__':
    main()
