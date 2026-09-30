#!/usr/bin/env python3
"""探测配图待修文本区域的精确边界框"""
from PIL import Image
import numpy as np

D = "/var/minis/shared/xhs-team/选题库/配图素材/"

def probe(name, y_lo, y_hi, label, x_lo=0, x_hi=1080):
    im = Image.open(D + name).convert("RGB")
    a = np.array(im)
    region = a[y_lo:y_hi, x_lo:x_hi]
    # 用区域内众数色作为背景
    flat = region.reshape(-1, 3)
    bg = np.bincount(flat.ravel(), minlength=256).argmax()
    bgc = flat[0]  # simplified; complex alternative was dead code (if False)
    # 简单法：统计每个颜色出现次数
    from collections import Counter
    cnt = Counter(map(tuple, flat))
    bgc = np.array(cnt.most_common(1)[0][0])
    mask = np.any(region != bgc, axis=2)
    ys, xs = np.where(mask)
    if len(ys) == 0:
        print(f"{label}: 区域内无文本 (bg={bgc})")
        return
    print(f"{label}: bbox=({xs.min()+x_lo},{ys.min()+y_lo})-({xs.max()+x_lo},{ys.max()+y_lo}) "
          f"bg={bgc.tolist()} ink={np.median(region[mask].reshape(-1,3),axis=0).astype(int).tolist()} "
          f"rows={len(ys)}")

print("=== 01_3方向对比表 ===")
probe("01_3方向对比表.png", 560, 720, "单价最高行")
probe("01_3方向对比表.png", 300, 460, "可持续性行")
print("=== 02_单价对比柱状图 ===")
probe("02_单价对比柱状图.png", 90, 190, "副标题")
print("=== 04_读书笔记示例 ===")
probe("04_读书笔记示例.png", 130, 200, "副标题真实内容")
print("=== 05_情感语录示例 ===")
probe("05_情感语录示例.png", 130, 200, "副标题真实内容")
print("=== 06_实操步骤 ===")
probe("06_实操步骤.png", 130, 190, "副标题")
