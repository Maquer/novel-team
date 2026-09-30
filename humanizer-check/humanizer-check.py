#!/usr/bin/env python3
"""
去AI味检测工具 v2 — 基于 lieflat-less-ai-tone 11条实测规则

语料：300 篇 AI 样本 / 117.9 万汉字 / 5 模型
每条规则带 AI/Human 频率比 + 覆盖率。白名单式改写：只处理命中规则处，
未命中规则的句子逐字保留，不润色、不改语气、不调结构。

用法：
  python3 humanizer-check.py < 文章.txt
  python3 humanizer-check.py --text "你的文本"
  python3 humanizer-check.py --json < 文章.txt
"""

import sys, re, json

# ── 规则 1 · 翻案腔 ──────────────────────────────────────────────
RULE1_PATTERNS = [
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

# ── 规则 2 · 顿号罗列过密 ──────────────────────────────────────
# 一个分句内出现两个以上顿号，连起三项以上并列
RULE2_RE = re.compile(r'[^\n。！？；]{0,60}[、][^、\n。！？；]{1,12}[、][^、\n。！？；]{1,12}')

# ── 规则 3 · 相邻句结构同款 ────────────────────────────────────
# 相邻两句以上，逗号数量相同、成分顺序相同、长度接近
def _sentences(text):
    return [s.strip() for s in re.split(r'[。！？\n]', text) if s.strip()]

def _comma_count(s):
    return s.count('，')

def _structure_sig(s):
    """句法骨架：把每段连续中文替换为其字数标记，保留标点位置。
    '杜甫的七律对仗工整，这是汉语诗歌的传统' → 'C10，C8'
    '他写了一首三行诗，短句读起来很舒服' → 'C10，C9'
    旧版把整段中文压成一个 'N'，导致任意一句带逗号的话都判同构。"""
    parts = re.split(r'([^一-鿿])', s)
    sig = []
    for p in parts:
        if p and re.match(r'[一-鿿]+', p):
            sig.append(f'C{len(p)}')
        elif p:
            sig.append(p)
    return ''.join(sig)

def _check_rule3(text):
    sents = _sentences(text)
    hits = []
    i = 0
    while i < len(sents) - 1:
        run = [i]
        j = i + 1
        while j < len(sents):
            a, b = sents[run[-1]], sents[j]
            if (_comma_count(a) == _comma_count(b)
                    and _structure_sig(a) == _structure_sig(b)
                    and 0.5 < len(a) / max(len(b), 1) < 2.0
                    and _comma_count(a) >= 1):
                run.append(j)
                j += 1
            else:
                break
        if len(run) >= 2:
            hits.append({
                'rule': '规则3·相邻句结构同款',
                'text': ' / '.join(sents[k] for k in run[:3]),
                'score': len(run) - 1,
            })
            i = run[-1] + 1
        else:
            i += 1
    return hits

# ── 规则 4 · 破折号滥用 ─────────────────────────────────────────
# 每千字破折号数 > 1.5（人类 0.80，AI 2.38）
RULE4_LIMIT = 1.5

# ── 规则 4b · em dash 密度（The Last Fingerprint 借鉴）────────────
# 核心发现：em dash（——）是 Markdown 结构思维泄露的最小残留单元
# 阈值：>5‰ 告警，>10‰ 严重（GPT-4.1 无抑制 10.62‰，禁止后仍 3.86‰，Llama=0）
RULE4B_DASH_RE = re.compile(r'——')
RULE4B_WARN = 5.0    # 每千字 >5 个 em dash → 告警
RULE4B_SEVERE = 10.0 # 每千字 >10 个 → 严重

# ── 规则 5 · 冒号滥用 ───────────────────────────────────────────
RULE5A_HINT = re.compile(r'(一句话总结|核心是|关键在于|原因如下|结论|本质上|换句话说|说白了|简单来说|概括来说|总结来说)[:：]')
RULE5B_EMPTY = re.compile(r'^[^:：\n]{4,40}[:：]\s*$', re.M)

# ── 规则 6 · 序数词当小标题 ─────────────────────────────────────
RULE6_RE = re.compile(r'^#{1,6}\s*(一|二|三|四|五|六|七|八|九|十|第一|第二|第三|第四|第五)\s*[、.]', re.M)
RULE6_BOLD_RE = re.compile(r'^\*\*+\s*(一|二|三|四|五|六|七|八|九|十|第一|第二|第三|第四|第五)\s*[、.]\s*', re.M)

# ── 规则 7 · 拟人化喻体 ─────────────────────────────────────────
RULE7_RE = re.compile(r'(?:像|相当于|就像|好比|如同|仿佛|宛如)\s*(?:一个|一位|一名|一尊|一只|一头)\s*(导师|秘书|助手|顾问|管家|审查员|实习生|老师|教练|医生|朋友|引路人|守护者|智者|军师|操盘手|操盘手|裁判|法官|导演|编剧|翻译|向导|教练|助理|保镖|保姆|管家)')

# ── 规则 8 · 把已有的具体数据写回概括表述 ──────────────────────
RULE8_ABSTRACT = re.compile(r'(?:显著|大幅|明显|巨大|相当|可观|巨大地|明显地|显著地)(?:地)?(?:提升|增长|改善|优化|增加|减少|降低|加快|缩短|延长|扩大|缩小|增强|减弱|提高|下降|突破|飞跃)')
RULE8_NOUNIFY = re.compile(r'(?:完成|实现|进行|开展|做了|做到)(?:了|过)?(?:对|把)?\s*[\u4e00-\u9fa5]{2,10}\s*(?:的)?\s*(?:提升|增长|改善|优化|调整|变革|改变|改造|升级|推进|推进|迭代|重构|梳理|规范|治理|管理|设计|开发|建设|打造|打造|塑造|塑造)')
RULE8_NUMBER = re.compile(r'\d+(?:\.\d+)?%?|[一二三四五六七八九十百千万亿]+')

# ── 规则 9 · 禁用起手式 ────────────────────────────────────────
RULE9_RE = re.compile(r'^(?:说白了|说穿了|说到底|先说结论|直接说|直说|坦白讲|讲白了)[:：]?\s*', re.M)

# ── 规则 10 · 翻译腔（五种） ────────────────────────────────────
RULE10A = re.compile(
    r'(?P<mod>[^\n。！？；，—–…]{15,})的(?P<head>[^，。！？；—–…]{2,10})(?:的|，|。|！|？|；)')
# 2026-09-19 修：旧版 mod 类只排除 ，。！？；，破折号/省略号未排除 →
# 跨分句的长 span 被当成一个修饰语，实测 skill-ecosystem 正文 14 处命中中 5 处虚增
# （其中一处 63 字横跨两个分句），排除后 14→10。与规则自述"mod 是纯文字"一致。  # 过长前置定语
RULE10B = re.compile(r'当[^，。！？；]{2,30}时，')  # "当…时"前置时间从句
RULE10C = re.compile(r'(?:对于|就|关于)\s*[^，。！？；]{2,20}(?:来说|而言|方面)|在[^，。！？；]{8,25}(?:里|中|时|下|上|之际|之间|处)')  # 前置话题壳
RULE10D = re.compile(r'^(?:然而|因此|此外|与此同时|换言之|总而言之|综上所述|总的说来|概括来说|也就是说|也就是说|也就是说)[:：，]?\s*', re.M)  # 句首连接词
RULE10E = re.compile(r'^(?:这意味着|这表明|这说明|换句话说|也就是说|也就是说|换言之)[:：，]?\s*', re.M)  # "这意味着"式复述

# ── 规则 11 · 段首零主语评论 ────────────────────────────────────
RULE11_RE = re.compile(r'^(?:听起来|看起来|说白了|值得注意的是|更重要的是|关键在于|问题在于|意味着|不难看出|显而易见|不言而喻|显而易见|说到底)[:：，]?\s*', re.M)
RULE11_BACKREF = re.compile(r'[这那其此上面下面以上以下此前 latter]')

# ─── 09-20 新：Tier 1A/1B 拆分（对齐 avoid-ai-writing） ───
# 1A = AI 频率标记（权重高，人很少用）
# 1B = 清晰化编辑（权重低，人也会用；不计入 AI 判定主权重）
# 依据：avoid-ai-writing patterns.md "清晰化修正永不把文档推向 AI 判定"
RULE_TIER = {
    '规则1·翻案腔': '1A',              # 翻案腔是 AI 特有
    '规则2·顿号罗列过密': '1A',         # 顿号罗列 4.21x，最强 AI 信号
    '规则3·相邻句结构同款': '1A',       # 排比是 AI 特有
    '规则4·破折号滥用': '1A',           # 破折号密度 2.38x，AI 特有
    '规则4b·em dash 密度过高': '1A',    # em dash 是 Markdown 结构残留，Llama=0
    '规则5·冒号滥用': '1A',             # 提示语/空转句是 AI 特有
    '规则6·序数词当小标题': '1A',       # 结构是 AI 特有
    '规则7·拟人化喻体': '1A',           # 比喻是 AI 特有
    '规则8·具体数据被概括表述盖掉': '1B', # 抽象化，人也会用
    '规则8·名词化结构': '1B',           # 名词化，人也会用
    '规则9·禁用起手式': '1A',           # 起手式是 AI 特有
    '规则10A·过长前置定语': '1A',       # 翻译腔是 AI 特有
    '规则10·翻译腔': '1A',              # 翻译腔是 AI 特有
    '规则11·段首零主语评论': '1A',      # 评论语是 AI 特有
}
# 1B 权重系数（不计入 AI 判定主分，只作清晰化提示）
TIER1B_WEIGHT = 0.3

# ── 保留的 v1 规则（未在 lieflat 语料中验证，标注证据状态） ──
V1_KEEP = [
    (r'在当今社会|在当今时代|在这个快速发展的时代|在当今快节奏|在这个.*?的时代', 'A5', '在当今社会/时代 宏大开场（v1 实战总结，未在 lieflat 语料中验证）'),
    (r'这不仅仅.{0,12}更是|这不仅是.{0,12}更是|这不仅.{0,12}而且', 'A8', '这不仅仅是…更是 递进套话（v1 实战总结，未在 lieflat 语料中验证）'),
    (r'一方面.{0,20}另一方面', 'A14', '一方面…另一方面 辩证模板（v1 实战总结，未在 lieflat 语料中验证）'),
]


def score_content(text):
    text = text.replace('\r', '\n')
    hits = []
    total = 0

    # 规则 1 · 翻案腔
    for pat, desc in RULE1_PATTERNS:
        for m in re.finditer(pat, text):
            ctx = text[max(0, m.start() - 20):m.end() + 30].replace('\n', ' ')
            hits.append({'rule': '规则1·翻案腔', 'desc': desc, 'text': ctx, 'score': 2})
            total += 2

    # 规则 2 · 顿号罗列过密
    for m in RULE2_RE.finditer(text):
        ctx = text[max(0, m.start() - 15):m.end() + 15].replace('\n', ' ')
        hits.append({'rule': '规则2·顿号罗列过密', 'desc': '一个分句内两个以上顿号', 'text': ctx, 'score': 1})
        total += 1

    # 规则 3 · 相邻句结构同款
    for h in _check_rule3(text):
        hits.append({'rule': '规则3·相邻句结构同款', 'desc': f"连续{h['score']+1}句同一句法骨架", 'text': h['text'], 'score': h['score']})
        total += h['score']

    # 规则 4 · 破折号滥用（中文破折号 ——，非英文 em dash）
    # 按连续段计数，避免 "——" 被 count('—') 和 count('——') 重复计 3 次
    dash_runs = re.findall(r'—+', text)
    total_dashes = len(dash_runs)
    if len(text) > 0:
        per_k = total_dashes / (len(text) / 1000)
        if per_k > RULE4_LIMIT:
            hits.append({'rule': '规则4·破折号滥用', 'desc': f'破折号 {per_k:.2f}/千字（人类 0.80，AI 2.38）', 'text': f'全文共 {total_dashes} 处', 'score': 3})
            total += 3

    # 规则 4b · em dash 密度（The Last Fingerprint 借鉴）
    # —— 是 Markdown 结构思维泄露到散文中的最小残留单元
    em_dash_runs = RULE4B_DASH_RE.findall(text)
    em_dash_count = len(em_dash_runs)
    if len(text) > 0:
        em_per_k = em_dash_count / (len(text) / 1000)
        if em_per_k >= RULE4B_WARN:
            severity = '严重' if em_per_k >= RULE4B_SEVERE else '告警'
            hits.append({
                'rule': '规则4b·em dash 密度过高',
                'desc': f'em dash {em_per_k:.2f}/千字（{severity}；GPT-4.1 抑制后 3.86‰，Llama=0）',
                'text': f'全文共 {em_dash_count} 处 em dash',
                'score': 3 if em_per_k >= RULE4B_SEVERE else 2,
            })
            total += 3 if em_per_k >= RULE4B_SEVERE else 2

    # 规则 5a · 提示语引出的冒号
    for m in RULE5A_HINT.finditer(text):
        ctx = text[max(0, m.start() - 10):m.end() + 30].replace('\n', ' ')
        hits.append({'rule': '规则5·冒号滥用', 'desc': '提示语引出内容', 'text': ctx, 'score': 1})
        total += 1

    # 规则 5b · 空转句引出列表
    for m in RULE5B_EMPTY.finditer(text):
        hits.append({'rule': '规则5·冒号滥用', 'desc': '空转句引出列表', 'text': m.group(0), 'score': 2})
        total += 2

    # 规则 6 · 序数词当小标题
    headers = RULE6_RE.findall(text) + RULE6_BOLD_RE.findall(text)
    if len(headers) >= 3:
        hits.append({'rule': '规则6·序数词当小标题', 'desc': f'小标题以序数词编号，共 {len(headers)} 个', 'text': ' / '.join(headers[:5]), 'score': 3})
        total += 3

    # 规则 7 · 拟人化喻体
    for m in RULE7_RE.finditer(text):
        ctx = text[max(0, m.start() - 10):m.end() + 30].replace('\n', ' ')
        hits.append({'rule': '规则7·拟人化喻体', 'desc': '把工具比作理想化的人', 'text': ctx, 'score': 2})
        total += 2

    # 规则 8 · 具体数据被概括表述盖掉
    paragraphs = text.split('\n')
    for pi, para in enumerate(paragraphs):
        has_number = bool(RULE8_NUMBER.search(para))
        if not has_number:
            continue
        for m in RULE8_ABSTRACT.finditer(para):
            ctx = para[max(0, m.start() - 15):m.end() + 15]
            hits.append({'rule': '规则8·具体数据被概括表述盖掉', 'desc': '同段已有具体数值，却被概括说法盖住', 'text': ctx, 'score': 2})
            total += 2
        for m in RULE8_NOUNIFY.finditer(para):
            ctx = para[max(0, m.start() - 10):m.end() + 25]
            hits.append({'rule': '规则8·名词化结构', 'desc': '可恢复动词的名词化表达', 'text': ctx, 'score': 1})
            total += 1

    # 规则 9 · 禁用起手式
    for m in RULE9_RE.finditer(text):
        ctx = text[max(0, m.start() - 5):m.end() + 25].replace('\n', ' ')
        hits.append({'rule': '规则9·禁用起手式', 'desc': '禁用起手式', 'text': ctx, 'score': 1})
        total += 1

    # 规则 10 · 翻译腔（五种）
    # 10A 过长前置定语：修饰语长于被修饰语
    for m in RULE10A.finditer(text):
        mod, head = m.group('mod'), m.group('head')
        if len(mod) > len(head):
            ctx = text[max(0, m.start() - 10):m.end() + 25].replace('\n', ' ')
            hits.append({'rule': '规则10A·过长前置定语', 'desc': f'修饰语({len(mod)}字)长于被修饰语({len(head)}字)', 'text': ctx, 'score': 1})
            total += 1
    for m in RULE10B.finditer(text):
        ctx = text[max(0, m.start() - 5):m.end() + 20].replace('\n', ' ')
        hits.append({'rule': '规则10·翻译腔', 'desc': '"当…时"前置时间从句', 'text': ctx, 'score': 1})
        total += 1
    for m in RULE10C.finditer(text):
        ctx = text[max(0, m.start() - 5):m.end() + 25].replace('\n', ' ')
        hits.append({'rule': '规则10·翻译腔', 'desc': '前置话题壳', 'text': ctx, 'score': 1})
        total += 1
    for m in RULE10D.finditer(text):
        ctx = text[max(0, m.start() - 5):m.end() + 25].replace('\n', ' ')
        hits.append({'rule': '规则10·翻译腔', 'desc': '句首连接词当路标', 'text': ctx, 'score': 1})
        total += 1
    for m in RULE10E.finditer(text):
        ctx = text[max(0, m.start() - 5):m.end() + 25].replace('\n', ' ')
        hits.append({'rule': '规则10·翻译腔', 'desc': '"这意味着"式复述句', 'text': ctx, 'score': 1})
        total += 1

    # 规则 11 · 段首零主语评论
    paras = [p.strip() for p in text.split('\n') if p.strip()]
    for pi, para in enumerate(paras):
        if pi == 0:
            continue
        m = RULE11_RE.match(para)
        if m and not RULE11_BACKREF.search(para[:m.end() + 15]):
            hits.append({'rule': '规则11·段首零主语评论', 'desc': '非首段以评论语开头且无回指成分', 'text': para[:m.end() + 20], 'score': 2})
            total += 2

    # v1 保留规则（标注证据状态）
    for pat, code, desc in V1_KEEP:
        if re.search(pat, text):
            hits.append({'rule': f'{code}（v1保留，未在 lieflat 语料中验证）', 'desc': desc, 'text': '命中', 'score': 1})
            total += 1

    # 分级
    if total == 0:
        level, color = '✅ 很干净', '🟢'
    elif total <= 5:
        level, color = '🟡 轻微AI味', '🟡'
    elif total <= 15:
        level, color = '🟠 中等AI味', '🟠'
    elif total <= 25:
        level, color = '🔴 明显AI味', '🔴'
    else:
        level, color = '🚨 严重AI味，建议重写', '🚨'

    # 09-20 新：Tier 1A/1B 分层（对齐 avoid-ai-writing）
    # 1A = AI 频率标记（权重高），1B = 清晰化编辑（权重低，不计入 AI 判定主分）
    total_a = 0
    total_b = 0
    for h in hits:
        tier = RULE_TIER.get(h['rule'], '1A')
        h['tier'] = tier  # 给每条 hit 标 tier 字段
        if tier == '1A':
            total_a += h['score']
        else:
            total_b += h['score']

    # 重新计算 total：1A 全权重 + 1B 只算 30%
    # 依据：avoid-ai-writing "清晰化修正永不把文档推向 AI 判定"
    total_weighted = total_a + int(total_b * TIER1B_WEIGHT)
    # 用加权后的 total 重新分级
    if total_weighted == 0:
        level, color = '✅ 干净', '🟢'
    elif total_weighted <= 5:
        level, color = '🟢 极轻', '🟢'
    elif total_weighted <= 15:
        level, color = '🟡 轻微AI味', '🟡'
    elif total_weighted <= 25:
        level, color = '🔴 明显AI味', '🔴'
    else:
        level, color = '🚨 严重AI味，建议重写', '🚨'

    return total, total_weighted, total_a, total_b, level, color, hits


def main():
    if '--text' in sys.argv:
        idx = sys.argv.index('--text')
        text = ' '.join(sys.argv[idx + 1:])
    elif len(sys.argv) > 1 and sys.argv[1].endswith('.txt'):
        text = open(sys.argv[1]).read()
    else:
        if not sys.stdin.isatty():
            text = sys.stdin.read()
        else:
            print("用法: python3 humanizer-check.py < 文章.txt")
            print("     python3 humanizer-check.py --text \"你的文本\"")
            sys.exit(1)

    if not text.strip():
        print("输入为空")
        sys.exit(1)

    total, weighted, total_a, total_b, level, color, hits = score_content(text)

    if '--json' not in sys.argv and '--review' not in sys.argv:
        print(f"{'='*50}")
        print(f"📝 AI味检测报告 v2（lieflat 11条实测规则 · Tier 1A/1B 分层）")
        print(f"{'='*50}")
        print(f"📊 综合评分: {weighted} 分  {color} {level}")
        print(f"   ├─ Tier 1A（AI 频率标记，权重高）: {total_a} 分")
        print(f"   └─ Tier 1B（清晰化编辑，权重低）: {total_b} 分 × 0.3 = {int(total_b * 0.3)} 分")
        print(f"   ────────────────────────────────")
        print(f"   原始命中分（未分层）: {total} 分")
        print()

        if not hits:
            print("🎉 未命中任何规则。按白名单原则，逐字保留原文。")
            print()
            print("⚠️  未命中 ≠ 确定是人写的。本清单只覆盖 lieflat 语料验证过的")
            print("   11 类触发标记，不覆盖的区域不做判断。")
        else:
            by_rule = {}
            for h in hits:
                by_rule.setdefault(h['rule'], []).append(h)
            for rule, items in by_rule.items():
                print(f"🔍 {rule}（{len(items)} 处）:")
                for h in items[:5]:
                    print(f"   ⚠️  {h['desc']}")
                    print(f"      📄 {h['text'][:80]}")
                if len(items) > 5:
                    print(f"   … 另 {len(items)-5} 处")
                print()

        print(f"{'='*50}")
        print("🔧 改写原则（白名单式）:")
        print("  1. 只改命中规则处，未命中句子逐字保留")
        print("  2. 每处改动对应明确规则编号，无对应规则的改动必须撤销")
        print("  3. 不润色、不改语气、不调结构、不重组观点")
        print("  4. 每个改后的实词必须能在原文指出出处")
        print("  5. 不补虚词、不换代词、不调句长、不拆段落")
        print("  6. 正文里的'首先…其次'、句内同构排比、比喻——不改")
        print()
        print("📖 完整规则与负面用例表见:")
        print("   /var/minis/shared/humanizer-check/checklist.md")
        print(f"{'='*50}")

    if '--json' in sys.argv:
        print(json.dumps({
            'score': weighted, 'level': level,
            'hits': hits, 'rules_checked': 14
        }, ensure_ascii=False, indent=2))
    
    if '--review' in sys.argv:
        # 结构化审稿报告
        print("\n" + "=" * 60)
        print("📋 结构化审稿报告")
        print("=" * 60)
        
        # 1. 场景描写检查
        print("\n【一、场景描写检查】")
        scene_checks = [
            ("环境描写", "是否有具体的环境描写？"),
            ("画面感", "是否能让读者产生画面感？"),
            ("感官细节", "是否有视觉/听觉/嗅觉等感官细节？")
        ]
        for title, question in scene_checks:
            print(f"  □ {title}: {question}")
        
        # 2. 人物刻画检查
        print("\n【二、人物刻画检查】")
        char_checks = [
            ("外貌描写", "是否有具体的外貌描写？"),
            ("动作描写", "是否有细致的动作描写？"),
            ("心理描写", "是否有内心活动描写？"),
            ("语言描写", "对话是否贴合人物性格？")
        ]
        for title, question in char_checks:
            print(f"  □ {title}: {question}")
        
        # 3. 对话检查
        print("\n【三、对话检查】")
        dialogue_checks = [
            ("自然度", "对话是否自然？"),
            ("个性", "是否符合人物性格？"),
            ("信息量", "是否推进剧情或揭示性格？")
        ]
        for title, question in dialogue_checks:
            print(f"  □ {title}: {question}")
        
        # 4. 节奏检查
        print("\n【四、节奏检查】")
        pacing_checks = [
            ("拖沓", "是否有不必要的拖沓？"),
            ("仓促", "是否有过于仓促的地方？"),
            ("张力", "是否有足够的张力？")
        ]
        for title, question in pacing_checks:
            print(f"  □ {title}: {question}")
        
        # 5. AI痕迹检查（集成humanizer）
        print("\n【五、AI痕迹检查】")
        if total > 0:
            print(f"  ⚠️  发现{total}处AI痕迹")
            for h in hits[:5]:
                print(f"     - {h['rule']}: {h['desc']}")
        else:
            print("  ✅ 未发现明显AI痕迹")
        
        print("\n" + "=" * 60)
        print("审稿结论")
        print("=" * 60)
        print(f"综合评分: {weighted} 分  {color} {level}")
        print(f"建议操作: {'通过' if weighted <= 15 else '需要修改'}")
        print("=" * 60)


if __name__ == '__main__':
    main()