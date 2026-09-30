#!/usr/bin/env python3
"""Generate 10 infographic figures for XHS note #001.
All charts: 1080x1440, dark-blue gradient background, Noto Sans CJK SC (index=2).
NO silent font fallback — will raise if font missing or glyph absent.
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFont

# ─── Constants ────────────────────────────────────────────────────────────────
W, H = 1080, 1440
BG_TOP = (6, 22, 48)      # #061630
BG_BOT = (14, 58, 108)    # #0E3A6C
WHITE = (255, 255, 255)
TEAL = (45, 212, 191)     # #2DD4BF
GRAY = (160, 180, 200)
CARD_BG = (15, 35, 65)
CARD_BORDER = (45, 212, 191)
FOOTER_TEXT = "实测 | 数据驱动 | 观点独立"

# Bar colors (matching existing charts)
BAR_COLORS = [(45, 212, 191), (99, 102, 241), (239, 68, 68), (245, 158, 11), (123, 150, 165)]

# ─── Font loading (NO fallback) ──────────────────────────────────────────────
FONT_BOLD_PATH = "/usr/share/fonts/noto/NotoSansCJK-Bold.ttc"
FONT_REG_PATH = "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc"
FONT_INDEX = 2  # SC face

def load_font(path, size):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Font not found: {path}")
    f = ImageFont.truetype(path, size, index=FONT_INDEX)
    return f

def font_bold(size):
    return load_font(FONT_BOLD_PATH, size)

def font_reg(size):
    return load_font(FONT_REG_PATH, size)

# ─── Glyph check ─────────────────────────────────────────────────────────────
# Load cmap tables once per font path. If this fails, the script dies loudly.
_CMAP_CACHE = {}

def _get_cmap(path):
    if path not in _CMAP_CACHE:
        from fontTools.ttLib import TTCollection
        tt = TTCollection(path, lazy=True)
        face = tt.fonts[FONT_INDEX]
        _CMAP_CACHE[path] = face.getBestCmap()
    return _CMAP_CACHE[path]

def assert_glyphs(text, font_obj, label=""):
    """Assert every non-ASCII character exists in the SC face cmap.
    Raises ValueError listing every missing char. Never draws tofu."""
    cmap = _get_cmap(font_obj.path)
    missing = [ch for ch in set(text) if ord(ch) > 127 and ord(ch) not in cmap]
    if missing:
        detail = ", ".join(f"'{c}'(U+{ord(c):04X})" for c in missing)
        raise ValueError(f"[{label}] Missing glyphs in SC face: {detail}")

# ─── Drawing helpers ──────────────────────────────────────────────────────────
def new_canvas():
    """Create gradient background canvas (#061630 top -> #0E3A6C bottom)."""
    strip = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        strip.putpixel((0, y), (r, g, b))
    return strip.resize((W, H), Image.NEAREST)

def draw_text_centered(draw, y, text, font, fill=WHITE):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, font=font, fill=fill)

def draw_footer(draw):
    f = font_reg(30)
    draw_text_centered(draw, H - 70, FOOTER_TEXT, f, GRAY)

def draw_accent_line(draw, y, w=200):
    x1 = (W - w) // 2
    draw.line([(x1, y), (x1 + w, y)], fill=TEAL, width=4)

def text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]

def text_height(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]

# ─── Data (from REGEN-SPEC.md) ───────────────────────────────────────────────
tools = ["豆包", "通义千问", "Claude", "Kimi", "ChatGPT"]
scores = [8.56, 7.88, 6.44, 6.36, 5.56]

scene_scores = {
    "豆包": [7.2, 7.2, 8.2],
    "Kimi": [6.2, 8.2, 6.2],
    "Claude": [8.2, 9.0, 7.7],
    "ChatGPT": [7.2, 8.5, 6.7],
    "通义千问": [6.7, 6.7, 5.7],
}
scene_names = ["场景1 小红书标题", "场景2 公众号大纲", "场景3 朋友圈文案"]

speed = {"豆包": 0.8, "Kimi": 1.1, "Claude": 1.6, "ChatGPT": 2.2, "通义千问": 0.6}

price = {
    "豆包": ("0 元", "直连"),
    "通义千问": ("0 元（按量另计）", "直连"),
    "Kimi": ("0 元基础 / Pro 99 元", "直连"),
    "Claude": ("基础免费 / Pro 145 元", "需科学上网"),
    "ChatGPT": ("基础免费 / Plus 145 元", "需科学上网"),
}

# ─── Fig2: Comparison Table ──────────────────────────────────────────────────
def gen_fig2_comparison():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title_f = font_bold(64)
    header_f = font_bold(36)
    cell_f = font_reg(36)
    small_f = font_reg(32)

    title = "5款AI写作工具对比"
    assert_glyphs(title, title_f, "fig2")
    draw_text_centered(d, 80, title, title_f, WHITE)
    draw_accent_line(d, 165, 280)

    # Table columns: tool | monthly_price | access | score | verdict
    headers = ["工具", "月费", "国内访问", "综合得分", "结论"]
    rows = [
        ("豆包", "0 元", "直连", "8.56", "留下"),
        ("通义千问", "0 元", "直连", "7.88", "放弃"),
        ("Claude", "Pro 145 元", "需科学上网", "6.44", "放弃"),
        ("Kimi", "Pro 99 元", "直连", "6.36", "放弃"),
        ("ChatGPT", "Plus 145 元", "需科学上网", "5.56", "放弃"),
    ]

    # Layout: 5 columns evenly spaced
    col_x = [60, 270, 500, 710, 890]
    col_w = [200, 220, 200, 170, 140]
    start_y = 230
    row_h = 130
    hdr_h = 90

    # Header background
    d.rounded_rectangle([40, start_y, W - 40, start_y + hdr_h], radius=12, fill=(20, 50, 90))
    for i, h in enumerate(headers):
        assert_glyphs(h, header_f, "fig2-hdr")
        tw = text_width(d, h, header_f)
        cx = col_x[i] + col_w[i] // 2
        d.text((cx - tw // 2, start_y + 25), h, font=header_f, fill=TEAL)

    # Rows
    for ri, row in enumerate(rows):
        ry = start_y + hdr_h + 20 + ri * row_h
        bg_c = (15, 35, 70) if ri % 2 == 0 else (10, 28, 55)
        d.rounded_rectangle([40, ry, W - 40, ry + row_h - 10], radius=10, fill=bg_c)
        for ci, val in enumerate(row):
            assert_glyphs(val, cell_f, f"fig2-r{ri}c{ci}")
            tw = text_width(d, val, cell_f)
            cx = col_x[ci] + col_w[ci] // 2
            color = WHITE
            if ci == 4:  # verdict column
                color = TEAL if val == "留下" else (239, 100, 100)
            if ci == 3:  # score column
                color = TEAL if ri == 0 else WHITE
            d.text((cx - tw // 2, ry + 40), val, font=cell_f, fill=color)

    # Bottom note
    note = "排名按综合得分降序"
    assert_glyphs(note, small_f, "fig2-note")
    draw_text_centered(d, start_y + hdr_h + 20 + 5 * row_h + 30, note, small_f, GRAY)
    draw_footer(d)
    img.save(os.path.join(OUT, "fig2-comparison.png"))

# ─── Fig2b: Score Bar Chart ──────────────────────────────────────────────────
def gen_fig2_score_chart():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title_f = font_bold(56)
    label_f = font_reg(36)
    val_f = font_bold(40)

    title = "综合得分排名"
    assert_glyphs(title, title_f, "fig2b")
    draw_text_centered(d, 80, title, title_f, WHITE)
    draw_accent_line(d, 160, 240)

    # Vertical bar chart
    chart_top, chart_bot = 280, 1050
    chart_left, chart_right = 120, W - 120
    bar_w = 120
    gap = (chart_right - chart_left - 5 * bar_w) // 4

    for i, (tool, score) in enumerate(zip(tools, scores)):
        assert_glyphs(tool, label_f, f"fig2b-{tool}")
        x = chart_left + i * (bar_w + gap)
        bar_h = int((score / 10.0) * (chart_bot - chart_top))
        y1 = chart_bot - bar_h
        color = TEAL if i == 0 else BAR_COLORS[i % len(BAR_COLORS)]
        d.rounded_rectangle([x, y1, x + bar_w, chart_bot], radius=8, fill=color)
        # Value on top
        sv = f"{score:.2f}"
        tw = text_width(d, sv, val_f)
        d.text((x + bar_w // 2 - tw // 2, y1 - 50), sv, font=val_f, fill=WHITE)
        # Label below
        lw = text_width(d, tool, label_f)
        d.text((x + bar_w // 2 - lw // 2, chart_bot + 20), tool, font=label_f, fill=WHITE)

    # Baseline
    d.line([(chart_left - 20, chart_bot), (chart_right + 20, chart_bot)], fill=GRAY, width=2)

    note = "满分10分 | 3次测试去首取中位数"
    assert_glyphs(note, label_f, "fig2b-note")
    draw_text_centered(d, chart_bot + 90, note, label_f, GRAY)
    draw_footer(d)
    img.save(os.path.join(OUT, "fig2-score-chart.png"))

# ─── Fig3: Grouped Horizontal Bar Chart ──────────────────────────────────────
def gen_fig3_scene_charts():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title_f = font_bold(56)
    label_f = font_reg(34)
    val_f = font_bold(32)
    scene_f = font_bold(38)

    title = "各场景质量分对比"
    assert_glyphs(title, title_f, "fig3")
    draw_text_centered(d, 60, title, title_f, WHITE)
    draw_accent_line(d, 140, 240)

    # Legend
    legend_tools = ["豆包", "Kimi", "Claude", "ChatGPT", "通义千问"]
    legend_colors = BAR_COLORS  # teal, purple, red, orange, gray
    lx = 80
    ly = 190
    for i, name in enumerate(legend_tools):
        assert_glyphs(name, label_f, f"fig3-leg-{name}")
        d.rounded_rectangle([lx, ly, lx + 30, ly + 30], radius=4, fill=legend_colors[i])
        d.text((lx + 38, ly - 2), name, font=label_f, fill=WHITE)
        lx += text_width(d, name, label_f) + 70

    # 3 scene groups, each with 5 horizontal bars
    tool_order = ["豆包", "Kimi", "Claude", "ChatGPT", "通义千问"]
    bar_h = 50
    bar_gap = 12
    group_gap = 60
    max_score = 10.0
    bar_area_x = 100
    bar_area_w = 750
    y_cursor = 280

    for si, scene in enumerate(scene_names):
        assert_glyphs(scene, scene_f, f"fig3-s{si}")
        d.text((80, y_cursor), scene, font=scene_f, fill=TEAL)
        y_cursor += 55
        for ti, tool in enumerate(tool_order):
            sc = scene_scores[tool][si]
            bw = int((sc / max_score) * bar_area_w)
            bx = bar_area_x
            by = y_cursor + ti * (bar_h + bar_gap)
            d.rounded_rectangle([bx, by, bx + bw, by + bar_h], radius=6, fill=legend_colors[ti])
            # Value label to the right of bar
            sv = f"{sc:.1f}"
            d.text((bx + bw + 12, by + 8), sv, font=val_f, fill=WHITE)
            # Tool name to the left of bar (small)
            tw = text_width(d, tool, label_f)
            assert_glyphs(tool, label_f, f"fig3-t{ti}")
            d.text((bx - tw - 15, by + 8), tool, font=label_f, fill=GRAY)
        y_cursor += 5 * (bar_h + bar_gap) + group_gap

    draw_footer(d)
    img.save(os.path.join(OUT, "fig3-scene-charts.png"))

# ─── Fig4: Conclusion Card ───────────────────────────────────────────────────
def gen_fig4_conclusion():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title_f = font_bold(64)
    body_f = font_reg(42)
    num_f = font_bold(42)

    title = "为什么留下豆包"
    assert_glyphs(title, title_f, "fig4")
    draw_text_centered(d, 120, title, title_f, TEAL)
    draw_accent_line(d, 210, 300)

    reasons = [
        ("理由一", "完全免费，零成本使用"),
        ("理由二", "首 token 响应仅 0.8 秒，体验流畅"),
        ("理由三", "朋友圈文案质量 8.2 分，全场最高"),
    ]
    y = 320
    for i, (tag, text) in enumerate(reasons):
        assert_glyphs(tag, num_f, f"fig4-tag{i}")
        assert_glyphs(text, body_f, f"fig4-txt{i}")
        # Card background
        cy = y + i * 220
        d.rounded_rectangle([80, cy, W - 80, cy + 170], radius=16, fill=CARD_BG, outline=CARD_BORDER, width=2)
        # Tag
        d.text((120, cy + 25), tag, font=num_f, fill=TEAL)
        # Body text (may need 2 lines)
        max_w = W - 260
        tx, ty = 120, cy + 85
        words = text
        if text_width(d, words, body_f) > max_w:
            # Split at midpoint
            mid = len(words) // 2
            # Find a good split point
            for sp in range(mid, min(mid + 10, len(words))):
                if words[sp] in "，。、 ":
                    mid = sp + 1
                    break
            d.text((tx, ty), words[:mid], font=body_f, fill=WHITE)
            d.text((tx, ty + 55), words[mid:], font=body_f, fill=WHITE)
        else:
            d.text((tx, ty), words, font=body_f, fill=WHITE)

    draw_footer(d)
    img.save(os.path.join(OUT, "fig4-conclusion.png"))

# ─── Fig5: Price Comparison ──────────────────────────────────────────────────
def gen_fig5_price():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title_f = font_bold(56)
    tool_f = font_bold(40)
    price_f = font_reg(38)
    small_f = font_reg(32)

    title = "月费对比"
    assert_glyphs(title, title_f, "fig5")
    draw_text_centered(d, 80, title, title_f, WHITE)
    draw_accent_line(d, 160, 200)

    price_data = [
        ("豆包", "0 元", True),
        ("通义千问", "0 元（按量另计）", True),
        ("Kimi", "0 元基础 / Pro 99 元", True),
        ("Claude", "基础免费 / Pro 145 元", False),
        ("ChatGPT", "基础免费 / Plus 145 元", False),
    ]

    y_start = 240
    card_h = 160
    gap = 30

    for i, (tool, pr, free) in enumerate(price_data):
        assert_glyphs(tool, tool_f, f"fig5-t{i}")
        assert_glyphs(pr, price_f, f"fig5-p{i}")
        cy = y_start + i * (card_h + gap)
        # Card bg
        bg = (15, 50, 55) if free else (50, 20, 20)
        border = TEAL if free else (239, 100, 100)
        d.rounded_rectangle([60, cy, W - 60, cy + card_h], radius=14, fill=bg, outline=border, width=2)
        # Tool name
        d.text((100, cy + 20), tool, font=tool_f, fill=WHITE)
        # Price
        price_color = TEAL if free else (255, 180, 80)
        d.text((100, cy + 80), pr, font=price_f, fill=price_color)
        # Badge on right
        badge = "免费" if free else "付费"
        assert_glyphs(badge, small_f, f"fig5-b{i}")
        bw = text_width(d, badge, small_f) + 30
        bx = W - 100 - bw
        by = cy + 55
        bc = TEAL if free else (239, 100, 100)
        d.rounded_rectangle([bx, by, bx + bw, by + 46], radius=23, fill=bc)
        d.text((bx + 15, by + 4), badge, font=small_f, fill=(6, 22, 48))

    note = "免费 > 低成本 > 高成本"
    assert_glyphs(note, small_f, "fig5-note")
    draw_text_centered(d, y_start + 5 * (card_h + gap) + 40, note, small_f, GRAY)
    draw_footer(d)
    img.save(os.path.join(OUT, "fig5-price.png"))

# ─── Fig6: Speed Bar Chart ───────────────────────────────────────────────────
def gen_fig6_speed():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title_f = font_bold(56)
    label_f = font_reg(36)
    val_f = font_bold(40)
    note_f = font_reg(34)

    title = "首 token 响应时间"
    assert_glyphs(title, title_f, "fig6")
    draw_text_centered(d, 80, title, title_f, WHITE)
    draw_accent_line(d, 160, 240)

    # Sort by speed ascending (lower = faster = better)
    speed_sorted = sorted(speed.items(), key=lambda x: x[1])
    chart_top, chart_bot = 300, 1020
    chart_left, chart_right = 120, W - 120
    bar_w = 120
    n = len(speed_sorted)
    gap = (chart_right - chart_left - n * bar_w) // (n - 1)
    max_val = 2.5

    for i, (tool, sec) in enumerate(speed_sorted):
        assert_glyphs(tool, label_f, f"fig6-{tool}")
        x = chart_left + i * (bar_w + gap)
        bar_h = int((sec / max_val) * (chart_bot - chart_top))
        y1 = chart_bot - bar_h
        color = BAR_COLORS[i % len(BAR_COLORS)]
        d.rounded_rectangle([x, y1, x + bar_w, chart_bot], radius=8, fill=color)
        sv = f"{sec:.1f}s"
        tw = text_width(d, sv, val_f)
        d.text((x + bar_w // 2 - tw // 2, y1 - 50), sv, font=val_f, fill=WHITE)
        lw = text_width(d, tool, label_f)
        d.text((x + bar_w // 2 - lw // 2, chart_bot + 20), tool, font=label_f, fill=WHITE)

    d.line([(chart_left - 20, chart_bot), (chart_right + 20, chart_bot)], fill=GRAY, width=2)

    note = "越矮越快 | 最快：通义千问 0.6s"
    assert_glyphs(note, note_f, "fig6-note")
    draw_text_centered(d, chart_bot + 100, note, note_f, GRAY)
    draw_footer(d)
    img.save(os.path.join(OUT, "fig6-speed.png"))

# ─── Fig7: Access Comparison Cards ──────────────────────────────────────────
def gen_fig7_access():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title_f = font_bold(56)
    group_f = font_bold(44)
    item_f = font_reg(40)
    tag_f = font_bold(32)
    small_f = font_reg(32)

    title = "国内访问门槛"
    assert_glyphs(title, title_f, "fig7")
    draw_text_centered(d, 80, title, title_f, WHITE)
    draw_accent_line(d, 160, 220)

    direct = ["豆包", "通义千问", "Kimi"]
    blocked = ["Claude", "ChatGPT"]

    # Group 1: direct
    gy = 230
    assert_glyphs("直连可用", group_f, "fig7-g1")
    d.rounded_rectangle([60, gy, W - 60, gy + 56], radius=12, fill=(15, 50, 55))
    d.text((90, gy + 6), "直连可用", font=group_f, fill=TEAL)
    gy += 80
    for tool in direct:
        assert_glyphs(tool, item_f, f"fig7-d-{tool}")
        d.rounded_rectangle([80, gy, W - 80, gy + 110], radius=12, fill=CARD_BG)
        d.text((120, gy + 30), tool, font=item_f, fill=WHITE)
        # Badge
        badge = "无需翻墙"
        assert_glyphs(badge, tag_f, "fig7-badge-d")
        bw = text_width(d, badge, tag_f) + 24
        bx = W - 120 - bw
        d.rounded_rectangle([bx, gy + 36, bx + bw, gy + 74], radius=19, fill=TEAL)
        d.text((bx + 12, gy + 38), badge, font=tag_f, fill=(6, 22, 48))
        gy += 130

    # Group 2: blocked
    gy += 50
    assert_glyphs("需科学上网", group_f, "fig7-g2")
    d.rounded_rectangle([60, gy, W - 60, gy + 56], radius=12, fill=(50, 20, 20))
    d.text((90, gy + 6), "需科学上网", font=group_f, fill=(239, 100, 100))
    gy += 80
    for tool in blocked:
        assert_glyphs(tool, item_f, f"fig7-b-{tool}")
        d.rounded_rectangle([80, gy, W - 80, gy + 110], radius=12, fill=CARD_BG)
        d.text((120, gy + 30), tool, font=item_f, fill=WHITE)
        badge = "门槛较高"
        assert_glyphs(badge, tag_f, "fig7-badge-b")
        bw = text_width(d, badge, tag_f) + 24
        bx = W - 120 - bw
        d.rounded_rectangle([bx, gy + 36, bx + bw, gy + 74], radius=19, fill=(239, 100, 100))
        d.text((bx + 12, gy + 38), badge, font=tag_f, fill=(255, 255, 255))
        gy += 130

    note = "直连 = 无需任何额外工具即可使用"
    assert_glyphs(note, small_f, "fig7-note")
    draw_text_centered(d, gy + 30, note, small_f, GRAY)
    draw_footer(d)
    img.save(os.path.join(OUT, "fig7-access.png"))

# ─── Fig8: Summary Recommendation ───────────────────────────────────────────
def gen_fig8_summary():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title_f = font_bold(52)
    big_f = font_bold(72)
    score_f = font_bold(56)
    body_f = font_reg(40)
    small_f = font_reg(32)

    # Header
    assert_glyphs("最终推荐", title_f, "fig8-hdr")
    draw_text_centered(d, 100, "最终推荐", title_f, GRAY)

    # Big name
    assert_glyphs("豆包", big_f, "fig8-name")
    draw_text_centered(d, 210, "豆包", big_f, TEAL)
    draw_accent_line(d, 320, 260)

    # Score
    score_text = "综合得分 8.56 / 10"
    assert_glyphs(score_text, score_f, "fig8-score")
    draw_text_centered(d, 380, score_text, score_f, WHITE)

    # Divider
    d.line([(200, 490), (W - 200, 490)], fill=(60, 90, 130), width=2)

    # Applicable people
    assert_glyphs("适合以下人群：", body_f, "fig8-sub")
    d.text((120, 530), "适合以下人群：", font=body_f, fill=GRAY)

    people = [
        "零预算但有日常写作需求的学生和自媒体人",
        "需要快速出稿、不想折腾网络环境的上班族",
        "追求响应速度、不想等待的效率控",
    ]
    y = 610
    for i, p in enumerate(people):
        assert_glyphs(p, body_f, f"fig8-p{i}")
        # Bullet
        d.ellipse([120, y + 18, 136, y + 34], fill=TEAL)
        # Text - check if needs wrapping
        max_w = W - 280
        if text_width(d, p, body_f) > max_w:
            # Simple split
            mid = len(p) // 2
            for sp in range(mid, min(mid + 15, len(p))):
                if p[sp] in "、，。 ":
                    mid = sp + 1
                    break
            d.text((160, y), p[:mid], font=body_f, fill=WHITE)
            d.text((160, y + 52), p[mid:], font=body_f, fill=WHITE)
            y += 130
        else:
            d.text((160, y), p, font=body_f, fill=WHITE)
            y += 80

    draw_footer(d)
    img.save(os.path.join(OUT, "fig8-summary.png"))

# ─── Fig9: Method Explanation ────────────────────────────────────────────────
def gen_fig9_method():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title_f = font_bold(56)
    num_f = font_bold(44)
    body_f = font_reg(38)
    small_f = font_reg(32)

    title = "测试方法"
    assert_glyphs(title, title_f, "fig9")
    draw_text_centered(d, 80, title, title_f, WHITE)
    draw_accent_line(d, 160, 200)

    steps = [
        ("01", "3 场景 x 5 工具 = 15 组测试"),
        ("02", "每组 3 次取中位数，去除首测异常"),
        ("03", "盲评：遮住工具名称，消除品牌偏见"),
        ("04", "价格数据截至 2026-09-24"),
    ]
    y_start = 250
    card_h = 210
    gap = 40

    for i, (num, text) in enumerate(steps):
        assert_glyphs(text, body_f, f"fig9-{i}")
        cy = y_start + i * (card_h + gap)
        d.rounded_rectangle([60, cy, W - 60, cy + card_h], radius=14, fill=CARD_BG, outline=CARD_BORDER, width=2)
        # Number
        d.text((100, cy + 20), num, font=num_f, fill=TEAL)
        # Text - may wrap
        tx = 100
        ty = cy + 90
        max_w = W - 220
        if text_width(d, text, body_f) > max_w:
            mid = len(text) // 2
            for sp in range(mid, min(mid + 15, len(text))):
                if text[sp] in "，。 　=×":
                    mid = sp + 1
                    break
            d.text((tx, ty), text[:mid], font=body_f, fill=WHITE)
            d.text((tx, ty + 50), text[mid:], font=body_f, fill=WHITE)
        else:
            d.text((tx, ty), text, font=body_f, fill=WHITE)

    draw_footer(d)
    img.save(os.path.join(OUT, "fig9-method.png"))

# ─── Fig10: Suitability Two-Column ──────────────────────────────────────────
def gen_fig10_suitability():
    img = new_canvas()
    d = ImageDraw.Draw(img)
    title_f = font_bold(56)
    col_title_f = font_bold(44)
    item_f = font_reg(36)
    small_f = font_reg(32)

    title = "适合谁 / 不适合谁"
    assert_glyphs(title, title_f, "fig10")
    draw_text_centered(d, 80, title, title_f, WHITE)
    draw_accent_line(d, 160, 240)

    # Two columns
    col_w_half = (W - 160) // 2
    lx = 60
    rx = 60 + col_w_half + 40
    cy = 220

    # Left column: suitable
    assert_glyphs("适合", col_title_f, "fig10-lt")
    d.rounded_rectangle([lx, cy, lx + col_w_half, cy + 60], radius=10, fill=(15, 60, 55))
    d.text((lx + 20, cy + 8), "适合", font=col_title_f, fill=TEAL)

    items_yes = [
        "预算为零的学生党",
        "日更自媒体作者",
        "追求速度的效率党",
        "不想折腾网络的人",
    ]
    iy = cy + 80
    for item in items_yes:
        assert_glyphs(item, item_f, f"fig10-y-{item}")
        d.ellipse([lx + 20, iy + 14, lx + 36, iy + 30], fill=TEAL)
        d.text((lx + 50, iy), item, font=item_f, fill=WHITE)
        iy += 70

    # Right column: not suitable
    assert_glyphs("不适合", col_title_f, "fig10-rt")
    d.rounded_rectangle([rx, cy, rx + col_w_half, cy + 60], radius=10, fill=(60, 20, 20))
    d.text((rx + 20, cy + 8), "不适合", font=col_title_f, fill=(239, 100, 100))

    items_no = [
        "需要专业级长文写作",
        "对文笔有极高要求",
        "需要复杂逻辑推理",
        "需要多模态输入输出",
    ]
    ny = cy + 80
    for item in items_no:
        assert_glyphs(item, item_f, f"fig10-n-{item}")
        d.ellipse([rx + 20, ny + 14, rx + 36, ny + 30], fill=(239, 100, 100))
        d.text((rx + 50, ny), item, font=item_f, fill=WHITE)
        ny += 70

    # Separator line
    mid_x = (lx + col_w_half + rx) // 2
    d.line([(mid_x, cy + 60), (mid_x, max(iy, ny) + 20)], fill=(60, 90, 130), width=2)

    draw_footer(d)
    img.save(os.path.join(OUT, "fig10-suitability.png"))

# ─── Main ────────────────────────────────────────────────────────────────────
OUT = "/var/minis/shared/xhs-team/assets"

def verify_face_is_sc():
    """Confirm ttc index=2 really is the SC face, else abort."""
    from fontTools.ttLib import TTCollection
    for path in (FONT_BOLD_PATH, FONT_REG_PATH):
        tt = TTCollection(path, lazy=True)
        name = tt.fonts[FONT_INDEX]["name"]
        fam = None
        for rec in name.names:
            if rec.nameID == 1 and rec.toUnicode():
                fam = rec.toUnicode()
                break
        if "SC" not in (fam or ""):
            raise RuntimeError(f"{path} index={FONT_INDEX} is face '{fam}', expected SC")
        print(f"  face ok: {os.path.basename(path)} index={FONT_INDEX} -> {fam}")

if __name__ == "__main__":
    print("Generating 10 figures...")
    verify_face_is_sc()
    gen_fig2_comparison()
    print("  fig2-comparison.png done")
    gen_fig2_score_chart()
    print("  fig2-score-chart.png done")
    gen_fig3_scene_charts()
    print("  fig3-scene-charts.png done")
    gen_fig4_conclusion()
    print("  fig4-conclusion.png done")
    gen_fig5_price()
    print("  fig5-price.png done")
    gen_fig6_speed()
    print("  fig6-speed.png done")
    gen_fig7_access()
    print("  fig7-access.png done")
    gen_fig8_summary()
    print("  fig8-summary.png done")
    gen_fig9_method()
    print("  fig9-method.png done")
    gen_fig10_suitability()
    print("  fig10-suitability.png done")

    # ─── Verification ────────────────────────────────────────────────────────
    print("\n=== Verification ===")
    files = [
        "fig2-comparison.png", "fig2-score-chart.png", "fig3-scene-charts.png",
        "fig4-conclusion.png", "fig5-price.png", "fig6-speed.png",
        "fig7-access.png", "fig8-summary.png", "fig9-method.png",
        "fig10-suitability.png",
    ]
    all_ok = True
    for fname in files:
        path = os.path.join(OUT, fname)
        if not os.path.exists(path):
            print(f"  FAIL {fname}: not found")
            all_ok = False
            continue
        sz = os.path.getsize(path)
        img = Image.open(path)
        dims = img.size
        ok = sz > 8192 and dims == (1080, 1440)
        status = "OK" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  {status} {fname}: {sz} bytes, {dims[0]}x{dims[1]}")

    if all_ok:
        print("\nAll 10 figures generated successfully.")
    else:
        print("\nSOME FIGURES FAILED.")
        sys.exit(1)
