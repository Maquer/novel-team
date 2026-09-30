from PIL import Image
import glob
from collections import Counter

for p in sorted(glob.glob('/var/minis/shared/xhs-team/选题库/配图素材/*.png')):
    im = Image.open(p).convert('RGB')
    W, H = im.size
    px = im.load()
    # 四角众数色作背景估计，避免整图众数被大片内容区带偏
    corners = [px[3, 3], px[W - 4, 3], px[3, H - 4], px[W - 4, H - 4]]
    bg = Counter(corners).most_common(1)[0][0]
    print(f"--- {p.split('/')[-1]}  {W}x{H}  bg={bg}  corners={corners}")
    xs, ys = [], []
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            r, g, b = px[x, y]
            if max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2])) > 60:
                xs.append(x)
                ys.append(y)
    if xs:
        print(f"    bbox=({min(xs)},{min(ys)})-({max(xs)},{max(ys)})  px≈{len(xs)}")
    else:
        print("    （无内容）")
