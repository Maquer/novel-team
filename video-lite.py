#!/usr/bin/env python3
# Version: 0.1.0
"""
video-lite.py — 小红书视频剪辑 P0 版

场景：图片序列 → 竖屏 mp4 + 封面（可选 BGM / PIL 水印）

⚠️ iSH 环境说明：ffmpeg 6.1.2 无 drawtext / subtitles filter
   → 水印由 PIL 预处理烧入图片（阶段 0），ffmpeg 只负责视频编码
   → 字幕请用 PIL 预先叠加到图片，或用独立 SRT 字幕轨（mov_text）

用法：
  python3 video-lite.py --images imgs/ --out out.mp4
  python3 video-lite.py --images a.png b.png --out out.mp4 --duration 2.5 --watermark @handle
  python3 video-lite.py --images imgs/ --out out.mp4 --subtitle subs.srt   # mov_text 软字幕轨

依赖：ffmpeg 6.1.2（iSH 已装），PIL（iSH 已装 py3-pillow）
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def run(cmd, timeout=600):
    """执行 ffmpeg 命令，打印命令用于调试，返回 CompletedProcess"""
    print(f"[ffmpeg] {' '.join(cmd)}")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        print(f"[ERROR] ffmpeg exit {r.returncode}")
        print(r.stderr[-3000:])
        sys.exit(1)
    return r


def collect_images(paths):
    """收集图片路径（支持单个文件/目录/多个）"""
    exts = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'}
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.iterdir()):
                if f.suffix.lower() in exts:
                    out.append(str(f))
        elif p.is_file() and p.suffix.lower() in exts:
            out.append(str(p))
        else:
            print(f"[WARN] skip {p} (not image or missing)")
    if not out:
        sys.exit("[ERROR] 未找到任何图片")
    return out


def build_filterchains(images, w, h, dur_per_img, transition, fps=30):
    """
    返回 (filterchains_list, out_label)
    filterchains 之间由调用方用 ; 拼接
    """
    n = len(images)
    # -loop 1 -i <img> 已让图片无限循环，直接 trim 截片段
    streams = []
    for i in range(n):
        streams.append(
            f"[{i}:v]trim=duration={dur_per_img},"
            f"setpts=PTS-STARTPTS,"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},"
            f"fps={fps}[v{i}]"
        )

    if transition == "none" or n == 1:
        # 简单 concat，无转场
        concat_in = "".join(f"[v{i}]" for i in range(n))
        streams.append(f"{concat_in}concat=n={n}:v=1:a=0[vout]")
        return streams, "vout"

    # xfade 链式
    xfade_dur = min(0.5, dur_per_img * 0.2)
    last_label = "v0"
    for i in range(1, n):
        prev_total = i * dur_per_img - (i - 1) * xfade_dur
        offset = max(0, prev_total - xfade_dur)
        new_label = f"x{i}"
        streams.append(
            f"[{last_label}][v{i}]xfade=transition=fade:duration={xfade_dur}:offset={offset}[{new_label}]"
        )
        last_label = new_label
    return streams, last_label


def add_watermark_to_images(images, watermark, pos, font_path, out_dir):
    """PIL 阶段 0：给每张图烧入水印（iSH ffmpeg 无 drawtext filter）"""
    os.makedirs(out_dir, exist_ok=True)
    out_paths = []
    for i, img in enumerate(images):
        try:
            im = Image.open(img).convert("RGBA")
        except Exception as e:
            print(f"[WARN] skip {img}: {e}")
            continue

        W, H = im.size
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 字号按画面宽度比例（1080x1920 下 ≈ 48px）
        font_size = max(32, min(W, H) // 20)
        try:
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), watermark, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        padding = max(20, W // 30)
        pos_map = {
            "bottom-right": (W - tw - padding, H - th - padding),
            "bottom-left": (padding, H - th - padding),
            "top-right": (W - tw - padding, padding),
            "top-left": (padding, padding),
        }
        xy = pos_map.get(pos, pos_map["bottom-right"])

        # 描边（黑色）+ 文字（白色半透明）
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            draw.text((xy[0] + dx, xy[1] + dy), watermark, font=font, fill=(0, 0, 0, 180))
        draw.text(xy, watermark, font=font, fill=(255, 255, 255, 217))

        composited = Image.alpha_composite(im, overlay).convert("RGB")
        out_path = os.path.join(out_dir, f"wm_{i:03d}_{os.path.basename(img)}")
        composited.save(out_path, "JPEG", quality=92)
        out_paths.append(out_path)

    return out_paths


def main():
    ap = argparse.ArgumentParser(description="小红书视频剪辑 P0：图片序列→竖屏mp4")
    ap.add_argument("--images", nargs="+", required=True, help="图片文件或目录")
    ap.add_argument("--out", required=True, help="输出 mp4 路径")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920, help="小红书竖屏默认 1080x1920")
    ap.add_argument("--duration", type=float, default=3.0, help="每张图停留秒数")
    ap.add_argument("--transition", default="fade", choices=["fade", "none"])
    ap.add_argument("--bgm", help="背景音乐 mp3（可选，会按视频长度截断+淡出）")
    ap.add_argument("--subtitle", help="字幕文件 srt（可选，烧录到画面上）")
    ap.add_argument("--watermark", help="右下角水印文字（可选，如 @handle）")
    ap.add_argument("--watermark-pos", default="bottom-right",
                    choices=["bottom-right", "bottom-left", "top-right", "top-left"])
    ap.add_argument("--cover", help="封面 jpg（可选，自动生成中间帧）")
    ap.add_argument("--font", default="/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
                    help="中文字体路径（默认 iSH 内 Noto Sans CJK）")
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    images = collect_images(args.images)
    print(f"[INFO] {len(images)} 张图 → {args.out} ({args.width}x{args.height}, "
          f"每张 {args.duration}s, transition={args.transition})")

    # 阶段 0：PIL 水印（iSH ffmpeg 无 drawtext filter）
    stage0_dir = "/tmp/video-lite-stage0"
    os.makedirs(stage0_dir, exist_ok=True)
    if args.watermark:
        print(f"[INFO] 阶段 0: PIL 烧入水印 '{args.watermark}' @ {args.watermark_pos}")
        images = add_watermark_to_images(
            images, args.watermark, args.watermark_pos, args.font, stage0_dir
        )
        if not images:
            sys.exit("[ERROR] 水印处理失败，无有效图片")

    # 阶段 1：合成画面（不带音频/字幕/水印）
    tmp_video = "/tmp/video-lite-stage1.mp4"
    stage2_out = "/tmp/video-lite-stage2.mp4"
    total_dur = len(images) * args.duration
    if args.transition == "fade":
        xfade_dur = min(0.5, args.duration * 0.2)
        total_dur -= (len(images) - 1) * xfade_dur

    # filterchain 之间用 ; 分隔
    streams, out_label = build_filterchains(
        images, args.width, args.height, args.duration, args.transition, args.fps
    )
    fc_string = ";".join(streams)

    cmd = ["ffmpeg", "-y", "-hide_banner"]
    for img in images:
        cmd += ["-loop", "1", "-i", img]
    cmd += ["-filter_complex", fc_string, "-map", f"[{out_label}]"]

    # 音频处理
    if args.bgm and os.path.exists(args.bgm):
        cmd += ["-i", args.bgm, "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-af", f"afade=t=out:st={max(0, total_dur-1.5)}:d=1.5"]

    # 视频编码（小红书 H.264，high 兼容性）
    cmd += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.0",
        "-t", str(total_dur), tmp_video,
    ]
    run(cmd)

    # 阶段 2：字幕作为 mov_text 软字幕轨（iSH ffmpeg 无 subtitles filter，不烧画面）
    stage2_out = "/tmp/video-lite-stage2.mp4"
    final_cmd = ["ffmpeg", "-y", "-hide_banner", "-i", tmp_video]

    if args.subtitle and os.path.exists(args.subtitle):
        # SRT 作为独立字幕流 → 编码为 mov_text
        print(f"[INFO] 阶段 2: 加 SRT 软字幕轨 (mov_text)")
        final_cmd += ["-i", args.subtitle,
                      "-map", "0:v", "-map", "0:a?", "-map", "1:0",
                      "-c:v", "copy", "-c:a", "copy",
                      "-c:s", "mov_text", stage2_out]
        run(final_cmd)
        subprocess.run(["cp", stage2_out, args.out], check=True)
    else:
        subprocess.run(["cp", tmp_video, args.out], check=True)

    # 生成封面
    if args.cover:
        # 截取中间帧
        cover_time = total_dur / 2
        run(["ffmpeg", "-y", "-hide_banner", "-ss", str(cover_time),
             "-i", args.out, "-frames:v", "1", args.cover])

    # 清理临时文件
    import shutil
    for tmp in [tmp_video, stage2_out]:
        if os.path.exists(tmp):
            os.remove(tmp)
    if os.path.isdir(stage0_dir):
        shutil.rmtree(stage0_dir, ignore_errors=True)

    # 汇总
    size_mb = os.path.getsize(args.out) / (1024 * 1024)
    print(f"[OK] {args.out} ({size_mb:.2f} MB, {total_dur:.1f}s, "
          f"{args.width}x{args.height})")
    if args.cover and os.path.exists(args.cover):
        print(f"[OK] cover: {args.cover}")


if __name__ == "__main__":
    main()
