"""裁出待修区域并放大，用于确认原文案"""
from PIL import Image
import os

SRC = '/var/minis/shared/xhs-team/选题库/配图素材'
OUT = '/var/minis/shared/xhs-team/选题库/crops'
os.makedirs(OUT, exist_ok=True)

# (源图, 标签, y0, y1)
JOBS = [
    ('01_3方向对比表.png', '01_title', 50, 130),
    ('01_3方向对比表.png', '01_table_top', 170, 400),
    ('01_3方向对比表.png', '01_summary', 660, 820),
    ('02_单价对比柱状图.png', '02_head', 50, 310),
    ('04_读书笔记示例.png', '04_head', 50, 200),
    ('05_情感语录示例.png', '05_head', 50, 200),
    ('06_实操步骤.png', '06_head', 50, 180),
]

for src, tag, y0, y1 in JOBS:
    im = Image.open(f'{SRC}/{src}').convert('RGB').crop((0, y0, 1080, y1))
    w, h = im.size
    im = im.resize((w * 2, h * 2), Image.LANCZOS)
    p = f'{OUT}/{tag}.png'
    im.save(p)
    print(f'{tag}.png  {im.size}  src={src} y={y0}-{y1}')
