#!/usr/bin/env python3
# Version: 0.1.0
"""AI 考古学家 系列标识图 — 参数化生成 Vol.XX"""
import sys
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = "/usr/share/fonts/noto"
FONT_BOLD = f"{FONT_DIR}/NotoSansCJK-Bold.ttc"
FONT_REG = f"{FONT_DIR}/NotoSansCJK-Regular.ttc"

def load(size, weight="bold"):
    return ImageFont.truetype(FONT_BOLD if weight == "bold" else FONT_REG, size)

def gen(vol, date_label="2026", save_path=None):
    W, H = 900, 420
    img = Image.new("RGB", (W, H), (11, 20, 40))
    d = ImageDraw.Draw(img)

    # 深蓝渐变背景
    for y in range(H):
        r = int(11 + (26 - 11) * y / H)
        g = int(20 + (40 - 20) * y / H)
        b = int(40 + (71 - 40) * y / H)
        d.line([(0, y), (W, y)], fill=(r, g, b))

    # 左上：红色印章方块
    d.rounded_rectangle([(50, 50), (240, 240)], radius=8, fill=(197, 48, 48))
    # 印章内竖排"AI 考古学家"
    f_seal = load(34, "bold")
    chars = "AI\n考古\n学家"
    y0 = 74
    for i, line in enumerate(chars.split("\n")):
        w = d.textbbox((0, 0), line, font=f_seal)
        tw = w[2] - w[0]
        x = (50 + 240 - tw) / 2
        d.text((x, y0 + i * 46), line, font=f_seal, fill=(255, 235, 220))

    # 右侧标题：AI 考古学家
    f_title = load(58, "bold")
    d.text((290, 78), "AI 考古学家", font=f_title, fill=(255, 255, 255))

    # Vol 号 + 中文
    f_vol = load(28, "regular")
    d.text((290, 165), f"Vol. {vol}  ·  {date_label}", font=f_vol, fill=(212, 168, 75))

    # 金线
    d.rectangle([(290, 215), (680, 218)], fill=(212, 168, 75))

    # 副标题
    f_sub = load(24, "regular")
    d.text((290, 238), "中国制度 × AI 编排", font=f_sub, fill=(200, 200, 200))

    # 底部：小字标注
    f_tag = load(14, "regular")
    d.text((290, 310), "A SERIES BY AI ARCHAEOLOGIST", font=f_tag, fill=(150, 150, 150))

    # 右下角：编号水印
    f_water = load(160, "bold")
    wbb = d.textbbox((0, 0), vol, font=f_water)
    wx = W - (wbb[2] - wbb[0]) - 30
    wy = H - (wbb[3] - wbb[1]) - 10
    # 半透明金色水印
    watermark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(watermark)
    wd.text((wx, wy), vol, font=f_water, fill=(212, 168, 75, 55))
    img = Image.alpha_composite(img.convert("RGBA"), watermark).convert("RGB")

    if save_path:
        img.save(save_path, optimize=True, quality=95)
        print(f"saved: {save_path}")
    return img

if __name__ == "__main__":
    vol = sys.argv[1] if len(sys.argv) > 1 else "01"
    date = sys.argv[2] if len(sys.argv) > 2 else "2026"
    path = sys.argv[3] if len(sys.argv) > 3 else f"/var/minis/workspace/series-logo-vol-{vol}.png"
    gen(vol, date, path)
