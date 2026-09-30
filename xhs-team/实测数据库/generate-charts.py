#!/usr/bin/env python3
"""明镜(配图官) — 用 PIL 生成 xhs #001 全部配图（CJK 友好）"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = '/var/minis/attachments'
os.makedirs(OUT, exist_ok=True)

# ── 字体 ────────────────────────────────────────────────
F_BOLD   = '/usr/share/fonts/noto/NotoSansCJK-Bold.ttc'
F_REG    = '/usr/share/fonts/noto/NotoSansCJK-Regular.ttc'
F_MONO   = '/usr/share/fonts/noto/NotoSansMonoCJK-Regular.ttc'  # 备用

def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

f_title  = lambda s: load_font(F_BOLD, s)
f_body   = lambda s: load_font(F_REG,  s)
f_mono   = lambda s: load_font(F_MONO, s)

# ── 颜色 ────────────────────────────────────────────────
C_BG       = '#0f0f1a'
C_CARD     = '#1c1c2e'
C_BORDER   = '#2d2d44'
C_WHITE    = '#f0f0f0'
C_GRAY     = '#888899'
C_YELLOW   = '#f5c542'
C_RED      = '#e94560'
C_GREEN    = '#0f9b8e'
C_BLUE     = '#4a90d9'
C_PURPLE   = '#a855f7'
C_ORANGE   = '#f97316'

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# ── 绘制矩形背景 ─────────────────────────────────────────
def draw_rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x0,y0,x1,y1 = xy
    r = radius
    draw.rectangle([x0+r, y0, x1-r, y1], fill=fill)
    draw.rectangle([x0, y0+r, x1, y1-r], fill=fill)
    draw.pieslice([x0, y0, x0+2*r, y0+2*r], 180, 270, fill=fill)
    draw.pieslice([x1-2*r, y0, x1, y0+2*r], 270, 360, fill=fill)
    draw.pieslice([x0, y1-2*r, x0+2*r, y1], 90, 180, fill=fill)
    draw.pieslice([x1-2*r, y1-2*r, x1, y1], 0, 90, fill=fill)
    if outline:
        draw.arc([x0, y0, x0+2*r, y0+2*r], 180, 270, fill=outline, width=width)
        draw.arc([x1-2*r, y0, x1, y0+2*r], 270, 360, fill=outline, width=width)
        draw.arc([x0, y1-2*r, x0+2*r, y1], 90, 180, fill=outline, width=width)
        draw.arc([x1-2*r, y1-2*r, x1, y1], 0, 90, fill=outline, width=width)
        draw.line([x0+r,y0,x1-r,y0], fill=outline, width=width)
        draw.line([x0+r,y1,x1-r,y1], fill=outline, width=width)
        draw.line([x0,y0+r,x0,y1-r], fill=outline, width=width)
        draw.line([x1,y0+r,x1,y1-r], fill=outline, width=width)

def draw_rect(draw, xy, fill, outline=None, width=1):
    x0,y0,x1,y1 = xy
    draw.rectangle([x0,y0,x1,y1], fill=fill)
    if outline:
        draw.rectangle(xy, outline=outline, width=width)

def draw_text_centered(draw, x, y, text, font, color):
    bbox = draw.textbbox((0,0), text, font=font)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    draw.text((x - tw//2, y), text, fill=color, font=font)

def draw_text_left(draw, x, y, text, font, color):
    draw.text((x, y), text, fill=color, font=font)

def draw_multiline_centered(draw, x, y, lines, font, color, line_h=1.3):
    for i, line in enumerate(lines):
        draw_text_centered(draw, x, y + i * int(font.size * line_h), line, font, color)

def draw_multiline_left(draw, x, y, lines, font, color, line_h=1.35):
    for i, line in enumerate(lines):
        draw_text_left(draw, x, y + i * int(font.size * line_h), line, font, color)

def make_canvas(w, h):
    return Image.new('RGB', (w, h), hex_to_rgb(C_BG))

def save(img, name):
    path = os.path.join(OUT, name)
    img.save(path, 'PNG')
    sz = os.path.getsize(path)
    print(f'✅ {name}  ({sz//1024}KB)')

# ══════════════════════════════════════════════════════════
# 图1: MiniCPM CoT 暴露 — 核心证据
# ══════════════════════════════════════════════════════════
def chart1_mincpm_cot():
    W, H = 1200, 1000
    img = make_canvas(W, H)
    d = ImageDraw.Draw(img)
    ft = f_title; fb = f_body; fm = f_mono

    # 标题
    draw_text_centered(d, W//2, 50, '截图 2：MiniCPM CoT 暴露（核心证据）', ft(32), C_RED)

    # 代码块背景
    draw_rounded_rect(d, (60, 140, 1140, 280), 12, '#0d1117', '#388bfd44', 2)
    draw_multiline_left(d, 80, 155,
        ['User是商家,语气要活泼热情',
         '我需要先确定文章结构',
         '用户之前让我写过行李牌的内容，现在需要的是保温杯的推荐。',
         '用户是商家，所以语气要活泼热情，突出产品特点。'],
        fm(20), C_BLUE)
    draw_text_left(d, 80, 290, '⚠️ 上方为模型 chain-of-thought 原始输出，API 直接返回给用户', fb(18), C_YELLOW)

    # 对比卡片
    cards = [
        ('❌ MiniCPM5-2B', '暴露推理过程', '用户看到"思考过程"而非可直接发布成品', C_RED),
        ('✅ DeepSeek / Qwen / MiMo', '推理过程被抑制', '直接返回可用成品，无 CoT 噪音', C_GREEN),
    ]
    for i, (t, t2, t3, c) in enumerate(cards):
        y = 340 + i * 170
        draw_rounded_rect(d, (60, y, 1140, y+150), 12, C_CARD, hex_to_rgb(c), 2)
        draw_text_left(d, 90, y+15, t, ft(26), hex_to_rgb(c))
        draw_text_left(d, 90, y+55, t2, fb(22), C_WHITE)
        draw_text_left(d, 90, y+90, t3, fb(18), C_GRAY)

    # 底部
    draw_text_centered(d, W//2, H-60, '数据来源：API 调用  |  时间：2026-09-24  |  模型：MiniCPM5-2B via Radeon Cloud',
                       fb(14), C_GRAY)
    save(img, 'chart01-mincpm-cot.png')

# ══════════════════════════════════════════════════════════
# 图2: 评分总览表格
# ══════════════════════════════════════════════════════════
def chart2_score_table():
    W, H = 1200, 750
    img = make_canvas(W, H)
    d = ImageDraw.Draw(img)
    ft = f_title; fb = f_body

    draw_text_centered(d, W//2, 40, '评分总览（4维度×4任务，满分80）', ft(28), C_WHITE)

    # 表头
    headers = ['模型', '准确性', '自然度', '完整度', '实用性', '总分', '结论']
    col_x = [80, 250, 420, 590, 760, 930, 1060]
    for x, h in zip(col_x, headers):
        draw_text_centered(d, x, 100, h, ft(18), C_YELLOW)

    rows = [
        ('Qwen 通义',    ['18','19','18','16'], '72', '✅ 推荐', C_GREEN),
        ('MiMo 小米',    ['18','19','18','16'], '72', '✅ 推荐', C_GREEN),
        ('DeepSeek',     ['17','18','17','16'], '69', '✅ 推荐', C_BLUE),
        ('MiniCPM 面壁', ['13','13','14','11'], '51', '❌ 放弃', C_RED),
        ('GLM 智谱',     ['—','—','—','—'],     '—',  '⬜ 未测', C_GRAY),
    ]
    score_xs = col_x[1:5]  # 准确性,自然度,完整度,实用性
    total_x  = col_x[5]
    verdict_x = col_x[6]
    for i, (name, scores, total, verdict, color) in enumerate(rows):
        y = 155 + i * 95
        draw_rounded_rect(d, (60, y, 1140, y+82), 8, C_CARD if i % 2 == 0 else '#16162a',
                          C_BORDER, 1)
        draw_text_left(d, 90, y+28, name, fb(18), C_WHITE)
        for j, (x, val) in enumerate(zip(score_xs, scores)):
            draw_text_centered(d, x, y+28, val, fb(18), C_WHITE)
        draw_text_centered(d, total_x, y+28, total, ft(20), color)
        draw_text_centered(d, verdict_x, y+28, verdict, ft(18), color)

    # 均值行
    draw_text_centered(d, W//2, H-80,
        '均值：66 分  |  MiniCPM 差距：−15 分  |  放弃线：总分 < 均值 且 某任务实用性 ≤ 2',
        fb(16), C_GRAY)
    draw_text_centered(d, W//2, H-50, '数据来源：api-responses/  |  时间：2026-09-24',
                       fb(14), C_GRAY)
    save(img, 'chart02-score-table.png')

# ══════════════════════════════════════════════════════════
# 图3: 4款 Prompt A 对比（种草）
# ══════════════════════════════════════════════════════════
def chart3_a_compare():
    W, H = 1300, 1100
    img = make_canvas(W, H)
    d = ImageDraw.Draw(img)
    ft = f_title; fb = f_body; fm = f_mono

    draw_text_centered(d, W//2, 35, '截图 3：Prompt A（种草）4 款输出对比', ft(26), C_WHITE)

    prompts = [
        ('DeepSeek\n⭐19分\n612B',
         ['用了三个月的保温杯，真心想安利给全世界！🌍',
          '早上倒的热水，下午喝还是烫嘴的程度，',
          '保温效果真的绝了！杯身磨砂质感，',
          '握着超舒服，而且完全不沾指纹。',
          '最戳我的是它的杯盖，一键弹开+安全锁，',
          '单手操作超方便，通勤路上喝水不用手忙脚乱。',
          '容量400ml刚好够我半天，放包里也不重，',
          '颜值还高，奶茶色越看越喜欢～💕',
          '现在每天喝水频率都变高了，连同事都被种草问链接。',
          '姐妹们，你们选保温杯最看重啥？评论区聊聊～👇'],
         C_BLUE),
        ('Qwen 通义\n⭐19分\n589B',
         ['姐妹们，我真的被这个保温杯拿捏了🥹',
          '以前冬天喝热水，没一会儿就凉了，',
          '后来随手入手了这个保温杯，结果直接爱上！',
          '保温效果很惊喜，早上倒的热水到下午还是温温的，',
          '泡咖啡、泡茶也很合适☕',
          '杯子颜值也很能打，简单干净，放办公桌上看着都舒服✨',
          '密封性也OK，放包里不怕漏水。',
          '最关键是一点不显重，随手带出门很方便👌',
          '冬天真的不能没有它，感觉随时都有热乎乎的水喝～',
          '你们平时买保温杯最看重保温、颜值还是便携呀？🤔'],
         C_GREEN),
        ('MiMo 小米\n⭐19分\n529B',
         ['☕️冬天的命真的是保温杯给的！',
          '之前随便买个杯子，一小时就凉透，',
          '直到换了这款保温杯，直接真香✨',
          '早上倒的热水，下午打开还烫嘴，',
          '保温力我愿称之为「卷王」🔥',
          '颜值也戳我，奶fufu的颜色，',
          '拿在手里像个配饰，拍照超上镜📸',
          '杯口大好清洗，装咖啡不串味，',
          '单手开盖开车党狂喜🚗',
          '姐妹们冬天都用什么保温杯呀？评论区一起抄作业呗～👇'],
         C_GREEN),
        ('MiniCPM 面壁\n⭐13分\n1267B',
         ['[CoT 推理过程] ← 🔴 暴露区',
          '用户是商家,语气要活泼热情',
          '我需要先确定文章结构',
          '用户之前让我写过行李牌的内容...',
          '[正文]',
          '✨保温杯私藏秘诀✨',
          '姐妹们！这个保温杯真的绝了😭',
          '保温性能超绝，饭团、咖啡都能喝上班喝水不凉！',
          '外壳软糯得像握个毛绒球🧸',
          '真正确的好杯子还得自己得熟用哦❤️',
          '你们最喜欢哪个款式呀？💬',
          '#保温杯推荐 #我的好物 #生活小确幸'],
         C_RED),
    ]

    col_w = W // 4
    for i, (title, lines, color) in enumerate(prompts):
        x0 = i * col_w + 15
        # 标题
        draw_rounded_rect(d, (x0, 65, x0 + col_w - 30, 145), 8, C_CARD, color, 2)
        title_lines = title.split('\n')
        for li, tl in enumerate(title_lines):
            c = color
            draw_text_centered(d, x0 + (col_w-30)//2, 75 + li * 28, tl, ft(18) if '分' in tl or 'B' in tl else fb(16), c)
        # 内容框
        box_h = max(320, len(lines) * 26 + 30)
        draw_rounded_rect(d, (x0, 155, x0 + col_w - 30, 155 + box_h), 8, '#0d1117', color, 1)
        for li, line in enumerate(lines):
            c = C_YELLOW if 'CoT' in line or '用户是' in line or '我需要' in line or '推理' in line else C_WHITE
            draw_text_left(d, x0 + 15, 165 + li * 26, line, fm(15) if 'CoT' in line else fb(15), c)
        if 'CoT' in str(lines):
            draw_text_centered(d, x0 + (col_w-30)//2, 155 + box_h + 10, '🔴 CoT 暴露区（非正文）', fb(14), C_RED)

    draw_text_centered(d, W//2, H-30,
        '共 4 款，MiniCPM 输出 1267B（远超其他 3 款的 ~550B），因大量 CoT 推理过程占据篇幅',
        fb(14), C_GRAY)
    save(img, 'chart03-a-compare.png')

# ══════════════════════════════════════════════════════════
# 图4: Prompt C 逻辑推理对比
# ══════════════════════════════════════════════════════════
def chart4_c_compare():
    W, H = 1200, 800
    img = make_canvas(W, H)
    d = ImageDraw.Draw(img)
    ft = f_title; fb = f_body

    draw_text_centered(d, W//2, 35, '截图 4：Prompt C（逻辑推理）对比 — "谁在说真话？"', ft(26), C_WHITE)

    # 问题框
    draw_rounded_rect(d, (60, 75, 1140, 130), 10, '#1e3a5f', C_BLUE, 2)
    draw_text_centered(d, W//2, 95,
        '甲：乙在说谎  |  乙：丙在说谎  |  丙：甲乙都在说谎  →  谁在说真话？',
        fb(20), C_WHITE)

    results = [
        ('DeepSeek（943B）', '✅ 乙说真话', '推理链清晰，逐步排除矛盾', C_BLUE),
        ('Qwen 通义（1106B）', '✅ 乙说真话', '反证法穷举，验证完整', C_GREEN),
        ('MiMo 小米（936B）', '✅ 乙说真话', '三种假设逐一验证，格式最清晰', C_GREEN),
        ('MiniCPM（4019B）', '✅ 乙说真话', '但输出含大量 CoT，结论淹没在冗长推理中', C_RED),
    ]
    for i, (name, result, note, color) in enumerate(results):
        y = 160 + i * 150
        draw_rounded_rect(d, (60, y, 1140, y+135), 10, C_CARD, color, 2)
        draw_text_left(d, 90, y+15, name, ft(22), hex_to_rgb(color))
        draw_text_left(d, 90, y+50, result, fb(20), C_GREEN if '✅' in result else C_RED)
        draw_text_left(d, 90, y+80, note, fb(16), C_GRAY)

    draw_text_centered(d, W//2, H-40,
        '4 款均得出正确结论"乙说真话"，但 MiniCPM 输出长度是其他 3 款的 4-5 倍（CoT 膨胀）',
        fb(14), C_GRAY)
    save(img, 'chart04-c-compare.png')

# ══════════════════════════════════════════════════════════
# 图5: Prompt D 润色对比
# ══════════════════════════════════════════════════════════
def chart5_d_compare():
    W, H = 1200, 850
    img = make_canvas(W, H)
    d = ImageDraw.Draw(img)
    ft = f_title; fb = f_body

    draw_text_centered(d, W//2, 35, '截图 5：Prompt D（润色）对比 — 全模型共同短板', ft(26), C_WHITE)

    # 原始输入
    draw_rounded_rect(d, (60, 75, 1140, 130), 10, '#3d2c00', C_YELLOW, 2)
    draw_text_left(d, 90, 95, '原始输入（27字）：「该产品在续航方面表现优异，能够满足用户全天候使用需求，值得推荐。」',
                   fb(18), C_YELLOW)

    d_results = [
        ('DeepSeek（102B）', '这产品续航真的顶，充一次电能用一整天，完全不耽误事儿，挺值得入手的。',
         '信息损失：「全天候」→「一整天」，但口语化自然', C_BLUE),
        ('Qwen 通义（83B）', '\n\n这款产品的续航挺给力的，从早用到晚基本没问题，很推荐。',
         '过度简化，丢失"值得推荐"力度', C_BLUE),
        ('MiMo 小米（90B）', '这款产品续航真的很给力，从早用到晚完全没问题，挺值得推荐的。',
         '几乎无损，但仍偏简', C_BLUE),
        ('MiniCPM（926B）', '需要润色...\n我们需要将这段话润色得更自然口语化...\n可以考虑这样的改写：\n"这款产品在续航上真的很不错，差不多能撑一整天用来用，确实值得推荐。"',
         'CoT 膨胀，输出 10 倍于原始，内容仍淹没在推理过程中', C_RED),
    ]
    for i, (name, output, note, color) in enumerate(d_results):
        y = 170 + i * 155
        draw_rounded_rect(d, (60, y, 1140, y+140), 10, C_CARD, color, 2)
        draw_text_left(d, 90, y+12, name, ft(20), hex_to_rgb(color))
        # 输出文本（截断显示）
        out_lines = output.split('\n')
        display_lines = [l for l in out_lines if l.strip()]
        for li, ol in enumerate(display_lines[:3]):
            c = C_YELLOW if 'CoT' in ol or '需要' in ol or '可以考虑' in ol else C_WHITE
            draw_text_left(d, 90, y+45 + li*24, ol[:70], fb(15), c)
        draw_text_left(d, 90, y+115, f'⚠️ {note}', fb(14), C_YELLOW)

    draw_text_centered(d, W//2, H-40,
        '结论：4 款润色均丢失细节或过度简化，共性短板；MiniCPM 因 CoT 膨胀最严重',
        fb(14), C_GRAY)
    save(img, 'chart05-d-compare.png')

# ══════════════════════════════════════════════════════════
# 图6: 评分柱状图
# ══════════════════════════════════════════════════════════
def chart6_bar():
    W, H = 1000, 600
    img = make_canvas(W, H)
    d = ImageDraw.Draw(img)
    ft = f_title; fb = f_body

    draw_text_centered(d, W//2, 30, '总分对比（满分80）', ft(24), C_WHITE)

    models = [('Qwen 通义', 72, C_GREEN), ('MiMo 小米', 72, C_GREEN),
              ('DeepSeek', 69, C_BLUE), ('MiniCPM', 51, C_RED)]
    bar_w = 120; gap = 60; start_x = 100
    max_y = H - 120; base_y = H - 80
    scale = (max_y - 80) / 80

    # 均值线
    mean_y = base_y - 66 * scale
    d.line([(60, mean_y), (W-60, mean_y)], fill=hex_to_rgb(C_YELLOW), width=2)
    draw_text_left(d, W-200, mean_y - 15, '均值 66 分', fb(14), C_YELLOW)

    # 放弃线
    drop_y = base_y - 55 * scale
    d.line([(60, drop_y), (W-60, drop_y)], fill=hex_to_rgb(C_RED), width=1)
    draw_text_left(d, W-200, drop_y - 15, '放弃线 55 分', fb(14), C_RED)

    for i, (name, score, color) in enumerate(models):
        x = start_x + i * (bar_w + gap)
        bar_h = score * scale
        # 柱子
        draw_rounded_rect(d, (x, base_y - bar_h, x + bar_w, base_y), 6, color)
        # 分数标签
        draw_text_centered(d, x + bar_w//2, base_y - bar_h - 25, str(score), ft(22), color)
        # 模型名
        draw_text_centered(d, x + bar_w//2, base_y + 15, name, fb(16), C_WHITE)

    draw_text_centered(d, W//2, H-40,
        '数据：api-responses/  |  MiniCPM 因 CoT 膨胀拖累各维度评分（均值 66，差距 −15）',
        fb(14), C_GRAY)
    save(img, 'chart06-bar-chart.png')

# ══════════════════════════════════════════════════════════
# 图7: GLM 402 错误
# ══════════════════════════════════════════════════════════
def chart7_glm_error():
    W, H = 1000, 500
    img = make_canvas(W, H)
    d = ImageDraw.Draw(img)
    ft = f_title; fb = f_body; fm = f_mono

    draw_text_centered(d, W//2, 40, '截图 7：GLM-5.3-Flash 失败记录（未测）', ft(24), C_RED)

    error_lines = [
        '{"action": "run",',
        ' "error": {',
        '   "code": "internal_error",',
        '   "message": "Provider error: [402] This request requires more credits,',
        '     or fewer max_tokens. You requested up to 4096 tokens, but ..."},',
        ' "ok": false,',
        ' "timestamp": "2026-09-24T09:10:11+08:00",',
        ' "tool": "minis-model-use"}',
    ]
    draw_rounded_rect(d, (60, 90, 940, 310), 10, '#0d1117', C_RED, 2)
    for i, line in enumerate(error_lines):
        draw_text_left(d, 80, 105 + i * 28, line, fm(16), C_RED)

    draw_text_left(d, 80, 340,
        '说明：OpenRouter free tier credits 不足，max_tokens=4096 触发 402 限流。降低到 500 仍间歇失败，本轮 GLM 未测。',
        fb(16), C_GRAY)
    draw_text_centered(d, W//2, H-40, '本轮 GLM 未测，不纳入评分对比', fb(14), C_GRAY)
    save(img, 'chart07-glm-error.png')

# ══════════════════════════════════════════════════════════
# 图8: 耗时对比（可选）
# ══════════════════════════════════════════════════════════
def chart8_timing():
    W, H = 1100, 650
    img = make_canvas(W, H)
    d = ImageDraw.Draw(img)
    ft = f_title; fb = f_body

    draw_text_centered(d, W//2, 30, '截图 6（可选）：API 调用耗时对比', ft(24), C_WHITE)

    tasks = ['A 种草', 'B 长文', 'C 逻辑', 'D 润色']
    data = {
        'DeepSeek': [9.2, None, 13.8, 2.7],
        'Qwen 通义': [13.3, 36.8, None, 9.4],
        'MiMo 小米': [9.1, 37.7, 50.8, 3.2],
        'MiniCPM':  [2.8, 8.0, 37.0, 20.4],
    }
    colors_map = {'DeepSeek': C_BLUE, 'Qwen 通义': C_GREEN, 'MiMo 小米': C_PURPLE, 'MiniCPM': C_RED}

    bar_group_w = 200; group_gap = 80; start_x = 100
    max_h = H - 180; base_y = H - 80; max_val = 55
    scale = max_h / max_val
    n_models = len(data)
    bw = bar_group_w // n_models

    for ti, task in enumerate(tasks):
        gx = start_x + ti * (bar_group_w + group_gap)
        # 任务名
        draw_text_centered(d, gx + bar_group_w//2, 70, task, ft(18), C_WHITE)
        # 均值线
        valid = [v for v in data['DeepSeek'][:ti+1] if v]  # not right way
        for mi, (name, vals) in enumerate(data.items()):
            if ti >= len(vals): continue
            v = vals[ti]
            if v is None:
                draw_text_centered(d, gx + mi*bw + bw//2, base_y - 10, '—', fb(14), C_GRAY)
                continue
            bh = v * scale
            x = gx + mi * bw + 5
            draw_rounded_rect(d, (x, base_y - bh, x + bw - 10, base_y), 4, colors_map[name])
            draw_text_centered(d, x + (bw-10)//2, base_y - bh - 18, f'{v:.1f}s', fb(12), colors_map[name])

    # 图例
    legend_y = H - 60
    lx = 100
    for name, col in colors_map.items():
        draw_rounded_rect(d, (lx, legend_y-10, lx+20, legend_y+10), 4, col)
        draw_text_left(d, lx+28, legend_y-5, name, fb(14), C_WHITE)
        lx += 130

    draw_text_centered(d, W//2, H-95,
        'B 长文任务 DeepSeek/Qwen 超时（60s）标记为 None；MiniCPM 整体最快但输出质量最低',
        fb(13), C_GRAY)
    save(img, 'chart08-timing.png')

# ══════════════════════════════════════════════════════════
# 图9: 封面图
# ══════════════════════════════════════════════════════════
def chart9_cover():
    W, H = 750, 1000  # 3:4 比例
    img = make_canvas(W, H)
    d = ImageDraw.Draw(img)
    ft = f_title; fb = f_body

    # 渐变标题区
    draw_rounded_rect(d, (30, 30, W-30, 350), 16, '#1a1a3e', C_BORDER, 2)
    draw_text_centered(d, W//2, 70, 'AI 写小红书笔记', ft(42), C_WHITE)
    draw_text_centered(d, W//2, 130, '4 款国产模型 1 款淘汰', ft(36), C_RED)
    draw_text_centered(d, W//2, 190, 'MiniCPM 的 CoT 泄露踩坑实录', ft(24), C_YELLOW)
    d.line([(80, 240), (W-80, 240)], fill=hex_to_rgb(C_BORDER), width=2)

    # 评分
    scores = [('Qwen 通义', 72, C_GREEN), ('MiMo 小米', 72, C_GREEN),
              ('DeepSeek', 69, C_BLUE), ('MiniCPM', 51, C_RED)]
    for i, (name, score, color) in enumerate(scores):
        y = 280 + i * 75
        draw_rounded_rect(d, (60, y, W-60, y+62), 8, C_CARD, color, 1)
        draw_text_left(d, 90, y+15, name, ft(24), C_WHITE)
        draw_text_centered(d, W-90, y+15, f'{score}分', ft(24), color)

    draw_text_centered(d, W//2, H-120, '#AI写作 #AI工具 #国产大模型 #API实测 #踩坑',
                       fb(16), C_GRAY)
    draw_text_centered(d, W//2, H-80, '2026.09.24 · 自费评测 · 无品牌合作',
                       fb(14), C_GRAY)
    save(img, 'chart09-cover.png')


if __name__ == '__main__':
    chart1_mincpm_cot()
    chart2_score_table()
    chart3_a_compare()
    chart4_c_compare()
    chart5_d_compare()
    chart6_bar()
    chart7_glm_error()
    chart8_timing()
    chart9_cover()
    print('\n🎉 全部 9 张配图生成完成！')
