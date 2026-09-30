#!/bin/bash
# Version: 0.1.0
set -e

OUTDIR="/var/minis/shared/duoduo-ready"
mkdir -p "$OUTDIR"

VIDEOS=(
  "https://v26-colds.douyinvod.com/9819648a0354272bed8cdae57aa63655/6a897217/video/tos/cn/tos-cn-ve-15/oEnAIfxIYg4eBzUERE9iAtBCvAQiIEILziObVC/?a=1128&br=4252&bt=4252&btag=80010e000af000&cd=0%7C0%7C0%7C0&ch=0&cquery=100y_10sH&cr=0&cs=0&cv=1&dr=0&ds=3&dy_q=1787388773&dy_va_biz_cert=&feature_id=59cb2766d89ae6284516c6a254e9fb61&ft=fL4dG0-0BN16UvjVQfqgOh7usRDJOaUaglcjp&l=20260822165253D5AF5222BA2820352939&mime_type=video_mp4&qs=0&rc=PDc5Nzg8N2ZpNTc1ZTk4ZUBpMzVrbHc5cnA1dDMzNGkzM0AvMF4tYy5jX2IxY2EvYy81YSMxZWxhMmRzYjBgLS1kLS9zcw%3D%3D"
  "https://v11-colds.douyinvod.com/cf6616ed4c25c486a068fad1fddfb180/6a89723b/video/tos/cn/tos-cn-ve-15/bb7321d4426243aaae4688f856e20cb4/?a=1128&ch=0&cr=0&dr=0&cd=0%7C0%7C0%7C0&cv=1&br=1709&bt=1709&cs=0&ds=3&ft=fL4dG0-0BN16UvjVQSUgOh7usRDJOaUaglcjp&mime_type=video_mp4&qs=0&rc=PGhnOmhnZTQ2OTRkaDs2N0Bpam05cWR4ZDk1eDMzZ2kzM0BeNDEyMzIzNjQxYC4yMDBeYSM2am9mY3FhNWVfLS0tLTBzcw%3D%3D&btag=80010e000a8000&cquery=10sH_100y&dy_q=1787388811&l=20260822165331D63815F89E6A38A8F4C8"
  "https://v5-dy-ov-experiment.zjcdn.com/74643cef030b3316d3b2f9afc0adfd07/6a8971e2/video/tos/cn/tos-cn-ve-15/o0xnTPoi0WBoIKxSgaKHg58dFqAHiEQcIPIPA/?a=1128&ch=0&cr=0&dr=0&cd=0%7C0%7C0%7C0&cv=1&br=402&bt=402&cs=0&ds=3&ft=CnkG3hFKDyjNMRVQ9wtM-SHhd.u2eS3R3-ApQX&mime_type=video_mp4&qs=0&rc=O2U2NGhpMzM8Njw8ZzM2Z0Bpam1xNWs5cjtrZDMzNGkzM0AxNjZeYjNeNjUxLjFgYy82YSM0bGdkMmQ0YTBhLS1kLS9zcw%3D%3D&btag=80010e00088000&cquery=10sH_100y&dy_q=1787388869&feature_id=f5241e7604dff1d9d6c943fd20bd51a2&l=202608221654294D879830A2939E970EA5"
)

NAMES=("bed-curtain" "storage-gadget" "backpack")
TITLES=("宿舍必备床帘选购攻略" "宿舍收纳神器大合集" "学生党书包省钱攻略")

idx=0
for CDN in "${VIDEOS[@]}"; do
  NAME="${NAMES[$idx]}"
  TITLE="${TITLES[$idx]}"
  RAW="$OUTDIR/${NAME}-raw.mp4"
  EDITED="$OUTDIR/${NAME}-edited.mp4"
  
  echo "[$((idx+1))/3] 下载: $TITLE"
  curl -L -s -o "$RAW" "$CDN" -w "  HTTP: %{http_code} | Size: %{size_download} bytes\n"
  
  DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1 "$RAW" 2>/dev/null | cut -d. -f1)
  [ -z "$DUR" ] || [ "$DUR" -lt 5 ] && { echo "  ⚠️ 无法读取时长，跳过编辑"; idx=$((idx+1)); continue; }
  NEW_DUR=$((DUR - 4))
  [ "$NEW_DUR" -lt 3 ] && NEW_DUR=3
  
  echo "  原时长: ${DUR}s → 去重后: ~$((NEW_DUR * 100 / 108))s"
  ffmpeg -y -i "$RAW" -ss 2 -t "$NEW_DUR" "/tmp/dd_s1_$NAME.mp4" 2>/dev/null
  ffmpeg -y -i "/tmp/dd_s1_$NAME.mp4" -filter_complex "[0:v]setpts=0.925*PTS[v];[0:a]atempo=1.08[a]" -map "[v]" -map "[a]" "/tmp/dd_s2_$NAME.mp4" 2>/dev/null
  ffmpeg -y -i "/tmp/dd_s2_$NAME.mp4" -vf "hflip" "/tmp/dd_s3_$NAME.mp4" 2>/dev/null
  ffmpeg -y -i "/tmp/dd_s3_$NAME.mp4" -vf "fps=12" "/tmp/dd_s4_$NAME.mp4" 2>/dev/null
  ffmpeg -y -i "/tmp/dd_s4_$NAME.mp4" -vf "format=yuv420p" "$EDITED" 2>/dev/null
  
  SIZE=$(ls -lh "$EDITED" 2>/dev/null | awk '{print $5}')
  EDUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1 "$EDITED" 2>/dev/null | cut -d. -f1)
  echo "  ✅ 成品: ${SIZE} | 时长: ${EDUR}s"
  rm -f /tmp/dd_s*.mp4
  idx=$((idx+1))
done

echo ""
echo "========== 下载完成 =========="
ls -lh "$OUTDIR"/*-edited.mp4 2>/dev/null