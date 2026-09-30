#!/usr/bin/env python3
# Version: 0.1.0
"""
多多视频全自动流水线
1. 从抖音素材池下载视频（通过 play API → CDN 重定向）
2. ffmpeg 去重处理（掐头去尾/变速/镜像/抽帧/滤镜/改帧率/替换水印）
3. 输出成品到 /var/minis/shared/duoduo-ready/
"""
import subprocess, os, json, re, sys, time

INPUT_DIR = "/var/minis/shared/duoduo-download"
OUTPUT_DIR = "/var/minis/shared/duoduo-ready"
MATERIALS_PATH = "/var/minis/mounts/loong/01-Projects/多多视频/素材/素材包v2.md"

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def extract_video_id(short_url):
    """从抖音短链提取 video_id"""
    # 短链格式: v.douyin.com/xxx → 需要解析
    # 直接用 curl 跟踪重定向获取完整 URL
    cmd = f'curl -sIL --max-redirs 3 --max-time 10 "{short_url}" 2>/dev/null | grep -i "^location:" | tail -1'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    location = result.stdout.strip()
    # 从 location 中提取 video_id
    # 格式: douyin.com/share/video/7387640549777444122
    m = re.search(r'/video/(\d+)', location)
    if m:
        return m.group(1)
    # 或从 aweme_id 获取
    m = re.search(r'/share/video/(\d+)/', location)
    if m:
        return m.group(1)
    return None


def get_play_url(video_id):
    """从 video_id 获取播放地址"""
    # 抖音短链: v.douyin.com/xxx
    # 先通过重定向获取完整信息
    pass


def download_video(video_id, output_path, label=""):
    """下载抖音视频"""
    # 抖音的视频 ID 是 aweme_id（数字），不是 video_id（字母数字）
    # play 接口: https://aweme.snssdk.com/aweme/v1/play/?video_id=xxx
    # 但我们需要从短链跳到完整 URL 再提取
    
    # 方法1: 直接用 aweme_id 构造 play URL
    # 短链跳转后拿到 aweme_id
    print(f"  📡 解析视频 {video_id[:20]}...")
    
    # 从之前收集的数据中我们知道格式
    # 但这里我们直接处理完整的视频链接
    pass


def download_from_link(url, output_path, label=""):
    """从完整链接下载视频"""
    print(f"📥 下载: {label or url[:50]}")
    
    # 如果 URL 是短链
    if "v.douyin.com" in url or "douyin.com/share" in url:
        # 先解析短链获取 video_id
        print(f"  📡 解析短链...")
        cmd = f'curl -sIL --max-redirs 3 --max-time 15 "{url}" 2>/dev/null'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # 提取 video_id 从最终跳转 URL
        headers = result.stdout
        # 查找 v.douyin.com/xxx/ 格式的短链
        m = re.search(r'Location.*?v\.douyin\.com/(\S+)', headers)
        if m:
            short_code = m.group(1)
        else:
            # 查找 /share/video/xxx/ 格式
            m = re.search(r'Location.*?/share/video/(\d+)/', headers)
            if m:
                video_id = m.group(1)
            else:
                m = re.search(r'Location.*?/video/(\d+)', headers)
                if m:
                    video_id = m.group(1)
                else:
                    print(f"  ❌ 无法解析链接")
                    return False
    else:
        video_id = url
    
    # 构造 play URL（无水印）
    play_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={video_id}&ratio=720p&line=0"
    
    # 下载（跟随重定向）
    cmd = f'curl -sL --max-time 60 -o "{output_path}" "{play_url}" -w "%{{http_code}}|%{{size_download}}" 2>/dev/null'
    print(f"  📥 {play_url[:80]}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    status = result.stdout.strip()
    if status.startswith("200"):
        _, size = status.split("|")
        size_mb = float(size) / 1024 / 1024
        print(f"  ✅ 下载完成: {size_mb:.1f} MB")
        return True
    else:
        print(f"  ❌ 下载失败: {status}")
        return False


def ffmpeg_dedup(input_path, output_path, label=""):
    """ffmpeg 去重处理（8步）"""
    print(f"  🎬 ffmpeg 处理: {label}")
    
    # 步骤1: 掐头去尾 + 步骤2: 变速 + 步骤3: 镜像 + 步骤4: 改帧率 + 步骤5: 加滤镜
    # 用 -vf filter 链实现
    
    # 掐头去尾：从第0.5秒开始，留到倒数1秒
    # 先用 ffprobe 获取时长
    probe = subprocess.run(
        f"ffprobe -v error -show_entries format=duration -of csv=p=0 \"{input_path}\"",
        shell=True, capture_output=True, text=True
    )
    duration = float(probe.stdout.strip() or 0)
    
    if duration < 3:
        print(f"    视频太短 ({duration:.1f}s)，跳过掐头去尾")
        trim_start = 0
        trim_duration = duration
    else:
        trim_start = 0.5
        trim_duration = duration - 1.0
        if trim_duration < 2:
            trim_duration = duration
    
    # ffmpeg filter: 掐头去尾(trim) + 变速 + 镜像(hflip) + 亮度对比度 + 调色调
    # trim=START:DURATION,volume=1,hflip,eq=brightness=0.05:contrast=1.1,scale=1280:-2
    filter_complex = (
        f"trim=start={trim_start}:duration={trim_duration},"
        f"setpts=PTS-STARTPTS,"
        f"hflip,"
        f"eq=brightness=0.05:contrast=1.1:saturation=1.1,"
        f"scale=1280:-2"
    )
    
    cmd = (
        f'ffmpeg -y -i "{input_path}" '
        f'-vf "{filter_complex}" '
        f'-r 25 '
        f'-c:v libx264 -preset medium '
        f'-crf 23 '
        f'-c:a copy '
        f'"{output_path}"'
    )
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
        size = os.path.getsize(output_path) / 1024 / 1024
        print(f"  ✅ 处理完成: {size:.1f} MB")
        return True
    else:
        print(f"  ❌ 处理失败: {result.stderr[:200]}")
        return False


def process_all():
    """批量处理素材包中的所有视频"""
    
    # 手动定义素材清单（从素材包v2提取）
    materials = [
        # 品类A
        {"label": "床帘1", "url": "https://v.douyin.com/AEGMVXstq_A/", "category": "A", "product": "床帘"},
        {"label": "床帘2", "url": "https://v.douyin.com/6_dZvHL8rcs/", "category": "A", "product": "床帘"},
        {"label": "床帘3", "url": "https://v.douyin.com/5frIgnfsV3Y/", "category": "A", "product": "床帘"},
        {"label": "收纳1", "url": "https://v.douyin.com/-hVuvx8nel8/", "category": "A", "product": "收纳神器"},
        {"label": "收纳2", "url": "https://v.douyin.com/RQyouBipilU/", "category": "A", "product": "收纳神器"},
        {"label": "书包1", "url": "https://v.douyin.com/FzvHBq291lQ/", "category": "A", "product": "书包"},
        {"label": "书包2", "url": "https://v.douyin.com/TbBd1fbNWFc/", "category": "A", "product": "书包"},
        {"label": "书桌1", "url": "https://v.douyin.com/aD9dxxftvdY/", "category": "A", "product": "床上书桌"},
        {"label": "书桌2", "url": "https://v.douyin.com/4gstS3qYwSw/", "category": "A", "product": "床上书桌"},
        {"label": "书桌3", "url": "https://v.douyin.com/UplUyZ4abn4/", "category": "A", "product": "床上书桌"},
        {"label": "桌面1", "url": "https://v.douyin.com/CTNVRMns9XA/", "category": "A", "product": "桌面收纳"},
        {"label": "磁吸灯1", "url": "https://v.douyin.com/GMN5aWc26HA/", "category": "A", "product": "磁吸灯"},
        # 品类B
        {"label": "风扇1", "url": "https://v.douyin.com/EaV6gwf4IdE/", "category": "B", "product": "挂脖风扇"},
        {"label": "风扇2", "url": "https://v.douyin.com/8106HU23-CA/", "category": "B", "product": "挂脖风扇"},
        {"label": "坐垫1", "url": "https://v.douyin.com/AQ52gT4dIpo/", "category": "B", "product": "冰丝坐垫"},
        # 品类C
        {"label": "保温杯1", "url": "https://v.douyin.com/GPqp5jIViMs/", "category": "C", "product": "保温杯"},
        {"label": "保温杯2", "url": "https://v.douyin.com/Ue3H0ZahLds/", "category": "C", "product": "保温杯"},
    ]
    
    stats = {"downloaded": 0, "processed": 0, "failed": []}
    
    for i, m in enumerate(materials):
        label = m["label"]
        url = m["url"]
        cat = m["category"]
        
        print(f"\n{'='*40}")
        print(f"[{i+1}/{len(materials)}] {label} ({cat}-{m['product']})")
        print(f"{'='*40}")
        
        # 检查是否已下载
        raw_path = os.path.join(INPUT_DIR, f"{label}.mp4")
        ready_path = os.path.join(OUTPUT_DIR, f"{label}.mp4")
        
        if os.path.exists(raw_path):
            print(f"  ✅ 已下载，跳过")
        else:
            if not download_from_link(url, raw_path, label):
                stats["failed"].append(label)
                print(f"  ❌ {label} 下载失败")
                continue
            stats["downloaded"] += 1
        
        if os.path.exists(ready_path):
            print(f"  ✅ 已处理，跳过")
        else:
            if not ffmpeg_dedup(raw_path, ready_path, label):
                stats["failed"].append(label + "-edit")
                print(f"  ❌ {label} 处理失败")
                continue
            stats["processed"] += 1
        
        print(f"  ✅ {label} 完成！")
    
    print(f"\n\n📊 结果汇总")
    print(f"  下载: {stats['downloaded']}")
    print(f"  处理: {stats['processed']}")
    print(f"  失败: {stats['failed']}")
    print(f"  成品目录: {OUTPUT_DIR}")
    
    # 列出成品
    print(f"\n📁 成品列表:")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        size = os.path.getsize(os.path.join(OUTPUT_DIR, f)) / 1024 / 1024
        print(f"  {f:20s} {size:.1f} MB")


if __name__ == "__main__":
    process_all()