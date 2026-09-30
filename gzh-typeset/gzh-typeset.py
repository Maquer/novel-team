#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gzh-typeset.py — 公众号自适应排版引擎（融合版 v3，2026-09-24）

融合来源：
  A. 保留 shared/gzh-typeset/gzh-typeset.py 自适应引擎全部能力（09-17 落地）
       5 主题预设 + 关键词加权打分 + 5 色荧光笔 + 首尾模板 + --plain 纯文本 + 密度门控 + dst!=src 断言
  B. 吸收 shared/gzh-team/gzh-typeset.py 团队版独有能力
       --title 显式传参 / --only-body（BODY_RE 提取 `## 正文` 段）
       `### 结尾/结束/小结` 特殊跳过（不渲染标题行，内容段落照常输出）
       默认输出名规则（-正文.md → -排版稿.html）
  C. 新增修今日推送暴露的 bug
       markdown 表格 → HTML <table>（原版直接把 `| --- |` 塞进 <p>，微信渲染为裸字符）
       H1 剥离时先剥尾部 `（策略：XXX）` 标记（原版会把策略标签污染到正式标题）

输入 .md → 分类段落(结构层) + 判调性选主题(主题层) → 输出全内联样式 HTML
微信编辑器会过滤 class/<style>，故一律内联。

用法:
  python3 gzh-typeset.py IN.md [-o OUT.html] [--tone KEY] [--max-pull N]
  python3 gzh-typeset.py IN.md --title "标题" [--only-body]
  python3 gzh-typeset.py IN.md --plain
  python3 gzh-typeset.py IN.md --list-tones
  python3 gzh-typeset.py IN.md --template template.json
"""
import sys, re, argparse, io, json

# ── 荧光笔配色（5 色，对齐 feishu2wx；微信不支持 <mark>，一律转内联 background）──
HIGHLIGHT_COLORS = {
    'yellow': '#fff3b0',   # 经典黄（默认，最接近微信原生荧光笔）
    'green':  '#d4f1b4',
    'blue':   '#cfe3ff',
    'pink':   '#ffd6e0',
    'purple': '#e6d4ff',
}
DEFAULT_HIGHLIGHT = 'yellow'

# ── 首尾模板（对齐 feishu2wx；head 提前拼、tail 压底拼，与正文同走 _esc 内联化）──
TEMPLATE_SAMPLE = {
    'head': '**小蒋的公众号**\n\n---\n',
    'tail': '\n\n---\n\n> 本文由小蒋的公众号首发，欢迎转发到朋友圈。\n> 关注【小蒋的公众号】看更多。'
}

def _load_template(path):
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    return str(d.get('head', '') or ''), str(d.get('tail', '') or '')

def _save_template_sample(path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(TEMPLATE_SAMPLE, f, ensure_ascii=False, indent=2)
        f.write('\n')

# ── 主题预设（5 套）──
TONES = {
    'authoritative': {
        'label': '权威·合规',
        'ink':'#3F3F3F','primary':'#B03A2E','primary_dark':'#7A2E24',
        'title':'#1F1F1F','soft_bg':'#FBF5F3','gray_bg':'#F6F5F2','rule':'#B03A2E',
        'lead_text':'#5A3A34','radius':'8px'},
    'friendly': {
        'label': '亲和·教程',
        'ink':'#3D4A4D','primary':'#2E8B8B','primary_dark':'#1F5F5F',
        'title':'#20302F','soft_bg':'#F0F7F7','gray_bg':'#F4F6F6','rule':'#2E8B8B',
        'lead_text':'#2F5A5A','radius':'14px'},
    'analytical': {
        'label': '理性·深度',
        'ink':'#39393D','primary':'#2F5D8A','primary_dark':'#22456A',
        'title':'#1C1C22','soft_bg':'#EEF3F8','gray_bg':'#F3F4F6','rule':'#2F5D8A',
        'lead_text':'#2C466A','radius':'4px'},
    'urgent': {
        'label': '紧迫·热点',
        'ink':'#3D3A38','primary':'#C4551B','primary_dark':'#8A3A10',
        'title':'#241F1C','soft_bg':'#FCF2EB','gray_bg':'#F6F4F2','rule':'#C4551B',
        'lead_text':'#7A3E1A','radius':'6px'},
    'elegant': {
        'label': '克制·美学',
        'ink':'#4A4A48','primary':'#8A7B5C','primary_dark':'#5E5340',
        'title':'#2B2B29','soft_bg':'#F7F5F0','gray_bg':'#F4F3EF','rule':'#8A7B5C',
        'lead_text':'#5E5340','radius':'2px'},
}
DEFAULT_TONE = 'analytical'

# 确定性调性信号词：词→权重。稀有/领域强词高权，泛词低权。
TONE_SIGNALS = {
 'authoritative':{'办法':3,'施行':3,'法规':3,'合规':3,'政策':2,'条例':3,'规范':2,'监管':3,
                   '官方':1,'必须':1,'网信':4,'备案':2,'声明':2,'标识':2,'侵权':2},
 'friendly':{'姐妹':4,'小白':3,'新手':3,'手把手':4,'教你':2,'带你':2,'别慌':3,'轻松':1,
             '干货':2,'保姆级':4,'零门槛':3,'一看就会':4,'亲测':2},
 'analytical':{'为什么':1,'本质':2,'底层':2,'逻辑':2,'框架':2,'变量':2,'推理':2,'结论':1,
              '第一性':4,'归因':3,'因果':3,'模型':1,'系统':1,'机制':2},
 'urgent':{'截止':3,'限期':3,'最后':1,'抓紧':2,'倒计时':4,'即将':3,'别错过':3,'错过':2,
          '今天':1,'立刻':2,'赶紧':2,'最后一天':5},
 'elegant':{'美学':3,'设计':1,'品味':3,'格调':3,'留白':3,'质感':3,'审美':3,'克制':2,
           '高级感':4,'松弛':3},
}

# ── 团队版吸收的常量（09-20 融合）──
# BODY_RE：从稿件里只提取 `## 正文` 段（跳过头部 H1/备选标题/缺口判断/AI 参与/配图指导/自检）
# 09-20 17:35 修复：放宽匹配（允许 `## 正文（待负责人选后替换标题）` 这种变体），
# 终止列表加入 AI 参与程度标注 / 项目状态 / 数据来源 / 具体路径 / 结尾
BODY_RE = re.compile(
    r'(##\s*正文[^#\n]*\n)(.*?)(?=\n##\s*(?:备选标题|已选标题|缺口判断|AI 参与|AI 参与程度标注|配图指导|交付前自检|自检|发布|项目状态|数据来源|结尾)|\Z)',
    re.S)
# 尾部策略标记：`（策略：数据冲击）`、`（策略：好奇心缺口）` 等（可出现在标题任意位置，含后续冒号）
STRATEGY_TAG_RE = re.compile(r'\s*[（(]\s*策略\s*[:：]\s*[^）)]+[）)]\s*[:：]?\s*')
# markdown 表格分隔行：|---|---| 或 |:---:|---:| 等
TABLE_SEP_RE = re.compile(r'^\s*\|[\s\-:|]+\|\s*$')
# 结尾类 h2（不渲染标题行，内容照常输出）
END_H2 = {'结尾', '结束', '小结', '总结'}


# ── 主题层：确定性打分 ────────────────────────────────────────────
def detect_tone(text):
    """返回 (tone_key, scores:dict)。命中词加权求和，最高者胜，默认 DEFAULT_TONE。"""
    scores = {}
    for tone, kw in TONE_SIGNALS.items():
        s = 0
        hit = []
        for w, weight in kw.items():
            n = text.count(w)
            if n:
                s += weight * min(n, 5)   # 同词最多算5次，防堆词
                hit.append(f'{w}×{n}')
        scores[tone] = (s, hit)
    best = max(scores, key=lambda k: scores[k][0])
    if scores[best][0] == 0:
        return DEFAULT_TONE, scores
    return best, scores

# ── 结构层：段落分类 ──────────────────────────────────────────────
# 类别: h1 / table / h2 / pull / action / interact / lead / para
def _is_table(block):
    """识别 markdown 表格块：首行以 | 开头 + 第二行是分隔行。"""
    lines = block.split('\n')
    if len(lines) < 2:
        return False
    if not lines[0].lstrip().startswith('|'):
        return False
    return bool(TABLE_SEP_RE.match(lines[1]))

def _split_action_head(rest):
    """从 action 剩余文本中切出 head（标题）和 text（正文）。
    09-20 18:55 修：解决 `1. **bold**——content` 被 `。` 切分破坏 bold 标记的问题。

    分割优先级（从强到弱）：
      1. `**bold**——text`  → head=bold 内容, text=—— 之后
      2. `head：text`        → head=： 之前, text=： 之后（首个全角冒号）
      3. `head——text`       → head=—— 之前, text=—— 之后（无 bold）
      4. 回退：按首个 `。` 切分（旧逻辑）

    长 head（>18 字）截断到 12 字，剩余拼到 text 前面。
    """
    # 1. **bold**——text
    m_bold = re.match(r'^\*\*(.+?)\*\*\s*——\s*(.+)', rest, re.S)
    if m_bold:
        head = m_bold.group(1).strip()
        tail = m_bold.group(2).strip()
    else:
        # 2. head：text（全角冒号）
        m_colon = re.match(r'^([^：]{2,30})\s*[：]\s*(.+)', rest, re.S)
        if m_colon:
            head = m_colon.group(1).strip()
            tail = m_colon.group(2).strip()
        else:
            # 3. head——text（无 bold）
            m_em = re.match(r'^([^—]{2,30}?)\s*——\s*(.+)', rest, re.S)
            if m_em:
                head = m_em.group(1).strip()
                tail = m_em.group(2).strip()
            else:
                # 4. 回退：按 `。` 切分
                head, _, tail = rest.partition('。')
                tail = tail.strip()
    # 长 head 截断
    if len(head) > 18:
        head, tail = head[:12], head[12:] + '。' + tail
    return head.strip(), tail.strip()

def classify(blocks, full_text):
    """返回 [{kind, ...payload}]。第一遍粗分类，第二遍做密度门控。"""
    items = []
    seen_h2 = False
    n = len(blocks)
    in_code = False  # 代码块状态
    list_stack = []  # 嵌套列表栈 [(type, items)]
    def flush_list():
        """将所有待处理的列表项作为 <li> 输出。"""
        while list_stack:
            lst = list_stack.pop()
            tag = 'ul' if lst['type'] == 'ul' else 'ol'
            items.append({'kind': tag, 'items': lst['items']})
    for idx, raw in enumerate(blocks):
        b = raw.strip()
        # ── 代码块处理 ──────────────────────────────
        if b.startswith('```'):
            if in_code:
                # 结束代码块
                items.append({'kind': 'code', 'text': '\n'.join(list_stack[-1]['lines']), 'lang': list_stack[-1].get('lang', '')})
                list_stack.pop()
                in_code = False
            else:
                # 开始代码块：只取第一行当 lang，rest 从第一行结束处起算
                first_line = b.split('\n', 1)[0] if '\n' in b else b
                lang = first_line[3:].strip() if len(first_line) > 3 else ''
                rest = b[len(first_line):]
                close_at = rest.find('\n```')
                if close_at >= 0:
                    # 同 block 内已有闭合，直接产出 code item
                    code_body = rest[:close_at].rstrip('\n')
                    items.append({'kind': 'code', 'text': code_body, 'lang': lang})
                else:
                    # 跨 block 的 code block，进入 state-machine
                    list_stack.append({'type': 'code', 'lines': [], 'lang': lang})
                    in_code = True
            continue
        if in_code:
            list_stack[-1]['lines'].append(b)
            continue
        # ── 列表项处理 ──────────────────────────────
        # 处理多行列表块（同一块内含多行）
        if '\n' in b:
            sub_lines = [l.strip() for l in b.split('\n') if l.strip()]
            if sub_lines:
                # 检查是否都是列表行
                all_ul = all(re.match(r'^[\-\*]\s+', l) for l in sub_lines)
                all_ol = all(re.match(r'^\d+[\.、）]\s+', l) for l in sub_lines)
                if all_ul or all_ol:
                    lt = 'ul' if all_ul else 'ol'
                    items_list = []
                    for line in sub_lines:
                        m_ul = re.match(r'^[\-\*]\s+(.+)$', line)
                        m_ol = re.match(r'^(\d+)[\.、）]\s+(.+)$', line)
                        if m_ul:
                            txt = m_ul.group(1).strip()
                        elif m_ol:
                            txt = m_ol.group(2).strip()
                        else:
                            continue
                        txt_clean = re.sub(r'^\*\*(.+?)\*\*$', r'\1', txt)
                        items_list.append(txt_clean)
                    if items_list:
                        if list_stack and list_stack[-1]['type'] == lt:
                            list_stack[-1]['items'].extend(items_list)
                        else:
                            flush_list()
                            list_stack.append({'type': lt, 'items': items_list})
                        continue
        m_ul = re.match(r'^[\-\*]\s+(.+)$', b)
        m_ol = re.match(r'^(\d+)[\.、）]\s+(.+)$', b)
        if m_ul or m_ol:
            # 检查是否与当前列表类型一致
            lt = 'ul' if m_ul else 'ol'
            if m_ul:
                txt = m_ul.group(1).strip()
            elif m_ol:
                txt = m_ol.group(2).strip()
            else:
                continue
            txt_clean = re.sub(r'^\*\*(.+?)\*\*$', r'\1', txt)
            if list_stack and list_stack[-1]['type'] == lt:
                # 同类型列表，追加项
                list_stack[-1]['items'].append(txt_clean)
            else:
                # 不同类型或新列表，flush 并创建新列表
                flush_list()
                list_stack.append({'type': lt, 'items': [txt_clean]})
            continue
        # 非列表行 → flush 列表
        if list_stack:
            flush_list()
        # ── 表格块优先 ──────────────────────────────
        if _is_table(b):
            items.append({'kind':'table','block':b})
            continue
        # ── 分隔线 ──────────────────────────────────
        if re.match(r'^(-{3,}|\*{3,}|_{3,})$', b.replace(' ','').replace('\t','')):
            items.append({'kind': 'hr'})
            continue
        # ── 引用块 ──────────────────────────────────
        if b.startswith('>'):
            # 收集连续引用行
            quote_lines = [b.lstrip('>').strip()]
            j = idx + 1
            while j < n and blocks[j].strip().startswith('>'):
                quote_lines.append(blocks[j].strip().lstrip('>').strip())
                j += 1
            items.append({'kind': 'quote', 'text': '\n'.join(quote_lines)})
            continue
        # ── H1 标题 ────────────────────────────────
        m_h1 = re.match(r'^#\s+(.+)$', b)
        if m_h1:
            text = m_h1.group(1).strip()
            items.append({'kind':'h1','text':text})
            continue
        # ── H2 标题（## 级别）──────────────────────
        m_h2 = re.match(r'^##\s+(.+)$', b)
        if m_h2:
            seen_h2 = True
            text = m_h2.group(1).strip()
            if text in END_H2:
                continue
            items.append({'kind':'h2','text':text})
            continue
        # ── H3/H4/H5/H6 子标题（不带 ｜ 装饰）──────
        m_h3 = re.match(r'^#{3,6}\s+(.+)$', b)
        if m_h3:
            text = m_h3.group(1).strip()
            if text in END_H2:
                continue
            items.append({'kind':'h3','text':text})
            continue
        # ── 金句：显式标记【金句】──────────────────
        if '【金句】' in b:
            head, gold = b.split('【金句】',1)
            head=head.strip(); gold=gold.strip()
            if head:
                items.append({'kind':'para','text':head,'seen':seen_h2})
            items.append({'kind':'pull','text':gold,'seen':seen_h2})
            continue
        # ── 编号动作：第N/1./1、格式 ──────────────
        m = re.match(r'^第([一二三四五六七八九十]+)[，、](.+)', b, re.S) \
            or re.match(r'^([1-9][0-9]?)[\.、）]\s*(.+)', b, re.S)
        if m:
            cn={'一':'1','二':'2','三':'3','四':'4','五':'5','六':'6','七':'7','八':'8','九':'9','十':'10'}
            num=m.group(1); num=cn.get(num,num)
            rest=m.group(2).strip()
            head, tail = _split_action_head(rest)
            if head or tail:
                items.append({'kind':'action','num':num,'head':head,'text':tail.strip(),'seen':seen_h2})
                continue
        # ── 互动钩子（末尾问号句）──────────────────
        if idx>=n-3 and b.endswith('？') and len(b)<60:
            items.append({'kind':'interact','text':b})
            continue
        # ── lead（前 2 段，未见 h2 前）─────────────
        if not seen_h2 and idx<2:
            items.append({'kind':'lead','text':b})
            continue
        items.append({'kind':'para','text':b,'seen':seen_h2})
    # 收尾：flush 剩余代码块或列表
    if in_code and list_stack:
        code = list_stack.pop()
        items.append({'kind': 'code', 'text': '\n'.join(code['lines']), 'lang': code.get('lang','')})
    flush_list()
    return items

def density_gate(items, max_pull):
    """金句卡数量封顶 max_pull；超出的降级为加粗行内 para。"""
    seen=0
    for it in items:
        if it['kind']=='pull':
            seen+=1
            if seen>max_pull:
                it['kind']='para'; it['text']='<strong>'+it['text']+'</strong>'; it['seen']=True
    return items


# ── 渲染层：全内联样式（微信只吃内联）─────────────────────────────
FONT = "'PingFang SC','Helvetica Neue','Microsoft YaHei',sans-serif"
HL_WORDS_DEFAULT = ['4 部门','14 条','§7.4','60%']

def _esc(s, color=DEFAULT_HIGHLIGHT):
    """转义 + 内联化：==高亮== → 内联 background（微信不认 <mark> 标签）"""
    s = s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    s = _mark(s, color)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    return s.replace('\n','<br/>')

def _mark(s, color=DEFAULT_HIGHLIGHT):
    """==text== → <span style="background:COLOR">text</span>（5 色荧光笔）"""
    bg = HIGHLIGHT_COLORS.get(color, HIGHLIGHT_COLORS[DEFAULT_HIGHLIGHT])
    return re.sub(r'==(.+?)==', r'<span style="background:%s">\1</span>' % bg, s)

def _hl(s, hl_words):
    for w in hl_words:
        s = s.replace(w, f'<strong style="color:{T_["primary"]};">{w}</strong>')
    return s

def _body(s, hl_words, color=DEFAULT_HIGHLIGHT):
    return _hl(_esc(s, color), hl_words)

T_ = {}  # 当前主题变量（render 时注入）

def _parse_md_table(block_lines, color=DEFAULT_HIGHLIGHT):
    """极简 markdown 表格 → HTML <table>（内联样式，微信兼容）。
    表头用 soft_bg + primary 色，数据行用 ink 色，边框统一 #ddd。
    单元格内容走 _body 处理 **加粗** 和 ==高亮==。
    """
    def _parse_row(line):
        line = line.strip().strip('|')
        return [c.strip() for c in line.split('|')]
    if len(block_lines) < 2:
        return ''
    header = _parse_row(block_lines[0])
    rows = []
    for line in block_lines[2:]:  # 跳过分隔行
        if '|' in line:
            rows.append(_parse_row(line))
    out = ['<table style="border-collapse:collapse;margin:16px 0;width:100%%;font-size:14px;line-height:1.6;font-family:%s;">' % FONT]
    out.append('<thead><tr>')
    for cell in header:
        out.append('<th style="border:1px solid #ddd;padding:8px 10px;background:%s;text-align:left;font-weight:600;color:%s;">%s</th>' % (
            T_.get('soft_bg','#f5f5f5'), T_.get('primary','#333'), _esc(cell, color)))
    out.append('</tr></thead><tbody>')
    for row in rows:
        out.append('<tr>')
        for cell in row:
            out.append('<td style="border:1px solid #ddd;padding:8px 10px;color:%s;">%s</td>' % (
                T_.get('ink','#333'), _body(cell, [], color)))
        out.append('</tr>')
    out.append('</tbody></table>')
    return ''.join(out)

def strip_md(s):
    """剥掉 markdown 语法：加粗/斜体/高亮/行内代码/链接/行首符号
    含不闭合的 ** 处理（防 action 分类拆开后丢失闭合标记）。"""
    s = re.sub(r'\*\*', '', s)   # 所有 ** 都剥掉（含不闭合）
    s = re.sub(r'\*(?!\*)(.+?)(?<!\*)\*', r'\1', s)  # *斜体*（避开 **）
    s = re.sub(r'==(.+?)==', r'\1', s)        # ==高亮==
    s = re.sub(r'`(.+?)`', r'\1', s)          # `行内代码`
    s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)  # [文字](链接)
    s = re.sub(r'^[#>\-\*\+]\s+', '', s)             # 行首:#/>/-/*/+(markdown 语法剥净)
    return s.strip()

def render_plain(items):
    """纯文本版：零 markdown，零装饰符号，段间空行。粘进任意编辑器不炸。
    h2→【小标题】；pull→「金句」；action→编号+换行；table→原样保留；其他纯文本。"""
    o = []
    for it in items:
        k = it['kind']
        if k == 'h1':
            o.append(strip_md(it['text']))
        elif k == 'h2':
            o.append('【' + strip_md(it['text']) + '】')
        elif k == 'lead':
            o.append(strip_md(it['text']))
        elif k == 'pull':
            o.append('「' + strip_md(it['text']) + '」')
        elif k == 'action':
            o.append(f'{it["num"]}. {strip_md(it["head"])}\n   {strip_md(it["text"])}')
        elif k == 'interact':
            o.append(strip_md(it['text']))
        elif k == 'table':
            # 表格原样保留（表格本身已是结构化文本）
            o.append(it['block'])
        elif k == 'h3':
            o.append('  ' + strip_md(it['text']))
        elif k == 'quote':
            lines = [strip_md(l) for l in it['text'].split('\n')]
            o.append('│ ' + '\n│ '.join(lines))
        elif k == 'code':
            o.append('``` ' + it.get('lang',''))
            o.append(it['text'])
            o.append('```')
        elif k == 'hr':
            o.append('---')
        elif k in ('ul', 'ol'):
            prefix = '- ' if k == 'ul' else '1. '
            for i, li in enumerate(it['items']):
                o.append(f'{prefix if i==0 else "   "}{strip_md(li)}')
        else:
            o.append(strip_md(it['text']))
    return '\n\n'.join(o)

def render(items, tone, hl_words, color=DEFAULT_HIGHLIGHT):
    global T_; T_ = TONES[tone]
    o=[]
    for it in items:
        k=it['kind']
        if k=='h1':
            o.append(f'<h1 style="font-size:20px;line-height:1.5;font-weight:700;letter-spacing:.5px;'
                     f'color:{T_["title"]};font-family:{FONT};margin:0 0 24px 0;text-align:center;">'
                     f'{_esc(it["text"], color)}</h1>')
        elif k=='h2':
            o.append(f'<section style="margin:38px 0 16px 0;">'
              f'<p style="margin:0;font-size:17px;line-height:1.5;font-weight:700;letter-spacing:1.5px;'
              f'color:{T_["title"]};font-family:{FONT};">'
              f'<span style="color:{T_["primary"]};margin-right:6px;">｜</span>{_esc(it["text"], color)}</p>'
              f'<section style="height:2px;margin-top:9px;width:38px;background:{T_["rule"]};"></section></section>')
        elif k=='lead':
            o.append(f'<section style="margin:0 0 26px 0;padding:16px 18px;background:{T_["soft_bg"]};'
              f'border-left:4px solid {T_["primary"]};border-radius:0 {T_["radius"]} {T_["radius"]} 0;">'
              f'<p style="margin:0;font-size:15.5px;line-height:1.9;letter-spacing:.5px;'
              f'color:{T_["lead_text"]};font-family:{FONT};text-align:justify;">{_esc(it["text"], color)}</p></section>')
        elif k=='pull':
            o.append(f'<section style="margin:26px 0;padding:20px;background:{T_["gray_bg"]};'
              f'border-left:4px solid {T_["primary"]};border-radius:0 {T_["radius"]} {T_["radius"]} 0;">'
              f'<p style="margin:0;font-size:16px;line-height:1.95;letter-spacing:.5px;'
              f'color:{T_["primary_dark"]};font-weight:600;font-family:{FONT};text-align:center;">'
              f'{_esc(it["text"], color)}</p></section>')
        elif k=='action':
            o.append(f'<section style="margin:24px 0;padding:18px 16px;background:{T_["gray_bg"]};border-radius:{T_["radius"]};">'
              f'<section style="margin:0 0 8px 0;">'
              f'<span style="display:inline-block;width:22px;height:22px;line-height:22px;text-align:center;'
              f'background:{T_["primary"]};color:#fff;border-radius:50%;font-size:12px;font-weight:700;'
              f'margin-right:8px;vertical-align:middle;">{it["num"]}</span>'
              f'<strong style="font-size:16px;color:{T_["primary"]};letter-spacing:.5px;">{_esc(it["head"])}</strong></section>'
              f'<p style="margin:0;font-size:15px;line-height:1.9;letter-spacing:.5px;color:{T_["ink"]};'
              f'font-family:{FONT};text-align:justify;">{_body(it["text"],hl_words,color)}</p></section>')
        elif k=='interact':
            o.append(f'<section style="margin:28px 0;padding:18px;background:{T_["soft_bg"]};'
              f'border-radius:{T_["radius"]};text-align:center;">'
              f'<p style="margin:0;font-size:15px;line-height:1.9;letter-spacing:.5px;color:{T_["primary_dark"]};'
              f'font-family:{FONT};">{_esc(it["text"], color)}</p></section>')
        elif k=='table':
            o.append(_parse_md_table(it['block'].split('\n'), color))
        elif k=='h3':
            o.append(f'<p style="margin:28px 0 12px 0;font-size:16px;line-height:1.5;font-weight:700;'
              f'color:{T_["primary"]};font-family:{FONT};letter-spacing:.5px;'
              f'border-bottom:2px solid {T_["primary"]};padding-bottom:6px;">'
              f'{_esc(it["text"], color)}</p>')
        elif k=='quote':
            lines = it['text'].split('\n')
            inner = '\n'.join(
                f'<p style="margin:0 0 6px 0;font-size:15px;line-height:1.8;font-style:italic;'
                f'color:{T_["lead_text"]};font-family:{FONT};">{_esc(l, color)}</p>'
                for l in lines
            )
            o.append(f'<section style="margin:22px 0;padding:14px 18px;background:{T_["soft_bg"]};'
              f'border-left:4px solid {T_["primary"]};border-radius:0 {T_["radius"]} {T_["radius"]} 0;">'
              f'{inner}</section>')
        elif k=='code':
            code_text = _esc(it['text'], color)
            # 去除首尾多余的<br/>（代码块第一行/最后一行为空时产生）
            code_text = code_text.lstrip('<br/>').rstrip('<br/>')
            br = T_['radius']
            pp = T_['primary']
            o.append(
                f'<pre style="margin:20px 0;padding:16px;background:#1e1e1e;border-radius:{br};'
                f'font-size:13px;line-height:1.6;font-family:Consolas,Monaco,monospace;color:#d4d4d4;'
                f'overflow-x:auto;white-space:pre;">{code_text}</pre>'
            )
        elif k=='hr':
            br = T_['radius']
            pp = T_['primary']
            ink = T_['ink']
            o.append(
                f'<section style="margin:24px 0;height:1px;background:linear-gradient(to right,transparent,{pp},transparent);"></section>'
            )
        elif k=='ul':
            br = T_['radius']
            pp = T_['primary']
            ink = T_['ink']
            items_html = ''.join(
                f'<li style="margin:0 0 8px 0;padding-left:8px;font-size:15px;line-height:1.8;'
                f'color:{ink};font-family:{FONT};">• {_esc(li, color)}</li>'
                for li in it['items']
            )
            o.append(f'<ul style="margin:12px 0 22px 0;padding-left:20px;">{items_html}</ul>')
        elif k=='ol':
            br = T_['radius']
            pp = T_['primary']
            ink = T_['ink']
            items_html = ''.join(
                f'<li style="margin:0 0 8px 0;padding-left:8px;font-size:15px;line-height:1.8;'
                f'color:{ink};font-family:{FONT};">{_esc(li, color)}</li>'
                for li in it['items']
            )
            o.append(f'<ol style="margin:12px 0 22px 0;padding-left:24px;">{items_html}</ol>')
        else:  # para
            o.append(f'<p style="margin:0 0 22px 0;font-size:15px;line-height:1.9;letter-spacing:.5px;'
              f'color:{T_["ink"]};font-family:{FONT};text-align:justify;">{_body(it["text"],hl_words,color)}</p>')
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"/>'
            '<meta name="viewport" content="width=device-width,initial-scale=1"/></head>'
            '<body style="margin:0;padding:20px 16px;background:#fff;">'
            '<section style="max-width:677px;margin:0 auto;">'
            + '\n'.join(o) + '</section></body></html>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('md', nargs='?', default=None)
    ap.add_argument('-o','--out', default=None,
                    help='输出路径；不给则按源文件名推导（-正文.md → -排版稿.html，其他 → -排版稿.html）')
    ap.add_argument('--title', default=None,
                    help='显式传标题；不给则从稿件首行剥 H1（并剥尾部 `（策略：XXX）` 标记）')
    ap.add_argument('--only-body', action='store_true',
                    help='（09-20 17:40 起为 default-on）只用 BODY_RE 提取 `## 正文` 段（含变体，如 `## 正文（待负责人选后替换标题）`）')
    ap.add_argument('--whole-body', action='store_true',
                    help='强制全文渲染（不用 BODY_RE 提取，跳过头部 H1 以外的所有 ## 段落）')
    ap.add_argument('--tone', default=None)
    ap.add_argument('--max-pull', type=int, default=3)
    ap.add_argument('--hl', default=None, help='逗号分隔的高亮词；不给则用默认')
    ap.add_argument('--highlight-color', default=DEFAULT_HIGHLIGHT, choices=list(HIGHLIGHT_COLORS),
                    help='荧光笔颜色（默认 yellow；可选 green/blue/pink/purple）')
    ap.add_argument('--template', default=None,
                    help='首尾模板 JSON 文件（含 head/tail markdown）')
    ap.add_argument('--save-template', metavar='PATH', default=None,
                    help='写出示例模板 JSON 到 PATH 并退出')
    ap.add_argument('--list-tones', action='store_true')
    ap.add_argument('--plain', action='store_true',
                    help='输出纯文本版（零 markdown，段间空行；h2→【】，pull→「」，action→编号，table 原样保留）')
    a = ap.parse_args()

    if a.save_template:
        _save_template_sample(a.save_template)
        print(f'示例模板已写入 {a.save_template}（head/tail 两个 markdown 字段，改完用 --template 加载）')
        return
    if a.list_tones:
        for k,v in TONES.items(): print(f'{k:14s} {v["label"]}')
        return
    if not a.md:
        print(__doc__); sys.exit(1)

    raw = io.open(a.md, encoding='utf-8').read()
    lines = raw.split('\n')
    body = raw

    # 1. 标题处理：先剥尾部 `（策略：XXX）`，再判断是否 H1（09-20 融合）
    title_from_md = ''
    if lines:
        first = STRATEGY_TAG_RE.sub('', lines[0]).strip()
        if first.startswith('#') or (0 < len(first) < 40 and '《' in first):
            title_from_md = first.lstrip('# ').strip()
            body = '\n'.join(lines[1:])

    # 2. --only-body：自动检测（09-20 17:40 修复：从 opt-in 改为 default-on）
    #    绝大多数稿件含 `## 正文` 结构（wanganzhou/draft-ai-label/higgsfield/draft-ai-writing/draft-ai-image 5 篇全有）
    #    自动提取可避免备选标题/缺口判断/AI 参与/配图指导/自检 等段落被误渲染
    #    用 --whole-body 显式覆盖
    only_body_effective = a.only_body or (not a.whole_body and bool(BODY_RE.search(raw)))
    if only_body_effective:
        m = BODY_RE.search(raw)
        if m:
            body = m.group(2)
            print(f'  --only-body: 从 raw 提取 ## 正文 段 {len(body)} 字', file=sys.stderr)
        else:
            print(f'  --only-body: 未匹配到 `## 正文` 段，退化为全文（原 H1 已剥）', file=sys.stderr)

    # 3. 首尾模板拼接
    head, tail = '', ''
    if a.template:
        head, tail = _load_template(a.template)
        print(f'已加载模板：head {len(head)} 字 / tail {len(tail)} 字', file=sys.stderr)
    if head or tail:
        body = (head + '\n\n' + body + '\n\n' + tail)

    # 4. 分块
    blocks = [b for b in re.split(r'\n\s*\n', body) if b.strip()]

    # 5. 调性检测（用 raw 全文，不看标题）
    tone, scores = detect_tone(raw)
    if a.tone:
        if a.tone not in TONES: sys.exit('未知调性: '+a.tone)
        tone = a.tone

    # 6. 分类 + 密度门控
    items = density_gate(classify(blocks, raw), a.max_pull)
    hl_words = [w.strip() for w in a.hl.split(',')] if a.hl else HL_WORDS_DEFAULT

    # 7. 插入标题（如果有）
    final_title = a.title or title_from_md
    if final_title:
        items.insert(0, {'kind': 'h1', 'text': final_title})

    from collections import Counter
    print('  结构分布:', dict(Counter(i['kind'] for i in items)))

    # 8. 输出路径
    if a.plain:
        text = render_plain(items)
        out = a.out or re.sub(r'\.md$', '', a.md) + '.txt'
        assert out != a.md, f'输出路径与源文件相同：{out}，会用纯文本覆盖 markdown 源。改用 --out 指别处。'
        io.open(out, 'w', encoding='utf-8').write(text)
        print('  纯文本输出:', out, len(text), '字符')
        return

    # 9. HTML 渲染
    html = render(items, tone, hl_words, a.highlight_color)
    if a.out:
        out = a.out
    elif '-正文.md' in a.md:
        out = a.md.replace('-正文.md', '-排版稿.html')
    else:
        out = re.sub(r'\.md$', '', a.md) + '-排版稿.html'
    assert out != a.md, f'输出路径与源文件相同：{out}，会用 HTML 覆盖 markdown 源。改用 --out 指别处。'
    io.open(out, 'w', encoding='utf-8').write(html)

    # 10. 可解释输出
    print('选中调性:', tone, '(', TONES[tone]['label'], ')')
    print('  调性打分:', ', '.join(f'{k}={v[0]}' for k,v in sorted(scores.items(), key=lambda x:-x[1][0])))
    print('  命中词:', ', '.join(f'{k}[{",".join(v[1])}]' for k,v in scores.items() if v[1]) or '无（用默认）')
    print('  输出:', out, len(html), '字符')

if __name__ == '__main__':
    main()
