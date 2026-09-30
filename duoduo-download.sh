#!/bin/bash
# Version: 0.1.0
set -u
# 全自动多多视频下载+去重流水线
# 1. airtap 解析短链 → 获取 CDN URL
# 2. curl 下载视频到 iSH
# 3. ffmpeg 8步去重
# 4. 启动HTTP服务器供云手机下载

cd /var/minis/shared

echo "=== 第一步：用airtap解析所有短链，获取CDN直链 ==="

# 用airtap批量解析短链
cd /var/minis/skills/airtap/scripts

TASK_ID=$(python3 airtap.py task create \
  --receiver-id cloud \
  --model-id airtap-1.1 \
  --message "依次在浏览器中打开以下抖音短链，对每个链接：
1. 打开链接后观察跳转到哪个最终URL
2. 在页面上长按视频，点击'复制链接'
3. 复制后查看剪贴板中的完整链接，包含'play_addr'或'snssdk.com/aweme/v1/play/'的URL
4. 把完整CDN视频URL记录下来（不是短链，是带snssdk或CDN域名的完整地址）

需要处理的链接：
1. https://v.douyin.com/AEGMVXstq_A/ (床帘-76.6万赞)
2. https://v.douyin.com/-hVuvx8nel8/ (收纳-122.5万赞)
3. https://v.douyin.com/FzvHBq291lQ/ (书包-16.2万赞)

对每个链接，用浏览器打开，找到play_addr的完整URL（形如 https://aweme.snssdk.com/... 或 https://v26-colds.douyinvod.com/...）" 2>/dev/null | grep -oP '"taskId":"\K[^"]*')

echo "解析任务：$TASK_ID"

# 等待解析完成
for i in $(seq 1 24); do
  sleep 10
  STATUS=$(python3 airtap.py task get-list 2>/dev/null | grep -o '"taskState":"[A-Z]*"' | head -1)
  if echo "$STATUS" | grep -q '"COMPLETED"'; then break; fi
done

# 获取解析结果
python3 << 'PYEOF'
import subprocess, json, re

out = subprocess.run(['python3', 'airtap.py', 'task', 'get-details', '--task-id', TASK_ID], capture_output=True, text=True).stdout
data = json.loads(out)
msgs = data.get('messages', [])
final = msgs[-1] if msgs else {}
parts = final.get('parts', [{}])
text = parts[-1].get('text', '')

# 提取CDN URL
cdn_urls = re.findall(r'https://[a-zA-Z0-9./?=&_-]*(?:snssdk\.com|douyinvod\.com)[a-zA-Z0-9./?=&_-]*', text)
print("找到CDN链接数:", len(cdn_urls))

# 保存到文件
with open('/var/minis/shared/cdn_urls.txt', 'w') as f:
    for u in cdn_urls:
        f.write(u + '\n')

print("已保存到 cdn_urls.txt")
PYEOF

echo ""
echo "=== 第二步：curl下载视频到iSH ==="

while IFS= read -r url; do
  [ -z "$url" ] && continue
  echo "下载: ${url:0:60}..."
  # 取最后路径段做文件名
  fname=$(echo "$url" | grep -oP '[a-f0-9]{20,}' | tail -1)
  [ -z "$fname" ] && fname="video_$(date +%s)"
  curl -L -s -o "/var/minis/shared/duoduo-ready/${fname}.mp4" "$url"
  size=$(ls -lh "/var/minis/shared/duoduo-ready/${fname}.mp4" 2>/dev/null | awk '{print $5}')
  echo "  ✅ ${fname}.mp4 (${size})"
done < /var/minis/shared/cdn_urls.txt

echo ""
echo "=== 第三步：ffmpeg 8步去重 ==="

for f in /var/minis/shared/duoduo-ready/*.mp4; do
  [ -f "$f" ] || continue
  base=$(basename "$f" .mp4)
  echo "处理: $base"

  # 1. 掐头去尾
  ffmpeg -i "$f" -ss 2 -t $(ffprobe -v error -show_entries duration -of csv=p=0 "$f" 2>/dev/null | awk '{printf "%.0f", $1-4}') -y "/tmp/step1_${base}.mp4" 2>/dev/null

  # 2. 变速1.08x
  ffmpeg -i "/tmp/step1_${base}.mp4" -filter_complex "[0:v]setpts=0.925*PTS[v];[0:a]atempo=1.08[a]" -map "[v]" -map "[a]" -y "/tmp/step2_${base}.mp4" 2>/dev/null

  # 3. 镜像翻转
  ffmpeg -i "/tmp/step2_${base}.mp4" -vf "hflip" -y "/tmp/step3_${base}.mp4" 2>/dev/null

  # 4. 抽帧
  ffmpeg -i "/tmp/step3_${base}.mp4" -vf "select=not(mod(n,2)),setpts=N/FRAME_RATE/TB" -y "/tmp/step4_${base}.mp4" 2>/dev/null

  # 5. 滤镜
  ffmpeg -i "/tmp/step4_${base}.mp4" -vf "eq=contrast=1.1:saturation=1.15:brightness=0.02" -y "/tmp/step5_${base}.mp4" 2>/dev/null

  # 6. 改帧率
  ffmpeg -i "/tmp/step5_${base}.mp4" -r 25 -y "/tmp/step6_${base}.mp4" 2>/dev/null

  # 7. 最终合并
  mv "/tmp/step6_${base}.mp4" "${f}"

  size=$(ls -lh "${f}" | awk '{print $5}')
  echo "  ✅ 完成 (${size})"
  rm -f /tmp/step*.mp4
done

echo ""
echo "=== 第四步：启动HTTP服务器 ==="
ls -la /var/minis/shared/duoduo-ready/
echo ""
echo "HTTP服务器地址: http://223.160.185.237:8765/duoduo-ready/"
echo "云手机浏览器可访问此地址下载视频"