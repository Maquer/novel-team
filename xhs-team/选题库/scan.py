"""逐行文本扫描：找出每条文字行的 y 区间与 x 范围"""
from PIL import Image
import glob

BG = (255, 248, 240)

def lines_info(p):
    im = Image.open(p).convert('RGB')
    W, H = im.size
    px = im.load()
    row_hits = []
    for y in range(H):
        c = 0
        for x in range(0, W, 3):
            r, g, b = px[x, y]
            if max(abs(r - BG[0]), abs(g - BG[1]), abs(b - BG[2])) > 50:
                c += 1
        row_hits.append(c)
    # 合并连续行成文本行
    res = []
    y = 0
    while y < H:
        if row_hits[y] > 2:
            y0 = y
            while y < H and row_hits[y] > 2:
                y += 1
            res.append((y0, y - 1, sum(row_hits[y0:y])))
        else:
            y += 1
    return W, H, res

for p in sorted(glob.glob('/var/minis/shared/xhs-team/选题库/配图素材/*.png')):
    name = p.split('/')[-1]
    W, H, rows = lines_info(p)
    print(f"\n=== {name} ({W}x{H}) 共 {len(rows)} 个内容行 ===")
    for (y0, y1, hits) in rows:
        print(f"  y={y0:>4}-{y1:<4} h={y1-y0+1:>3} ink={hits:>6}")
