#!/usr/bin/env python3
"""串行重试失败的实测任务"""
import subprocess, time, os

D = "/var/minis/shared/xhs-team/实测数据库/api-responses"

RETRIES = [
    ("DeepSeek-V4-Flash", "B", "DeepSeek_B"),
    ("Qwen3.8-Flash-Next", "C", "Qwen通义_C"),
    ("z-ai/glm-5.3-flash", "A", "GLM智谱_A"),
    ("z-ai/glm-5.3-flash", "B", "GLM智谱_B"),
    ("z-ai/glm-5.3-flash", "C", "GLM智谱_C"),
    ("z-ai/glm-5.3-flash", "D", "GLM智谱_D"),
    ("MiMo-V2.6-Flash", "A", "MiMo小米_A"),
    ("MiMo-V2.6-Flash", "C", "MiMo小米_C"),
    ("MiMo-V2.6-Flash", "D", "MiMo小米_D"),
    ("MiniCPM5-2B", "A", "MiniCPM面壁_A"),
    ("MiniCPM5-2B", "B", "MiniCPM面壁_B"),
    ("MiniCPM5-2B", "C", "MiniCPM面壁_C"),
    ("MiniCPM5-2B", "D", "MiniCPM面壁_D"),
]

PROMPTS = {
    "A": "帮我写一条小红书种草笔记,主题是「一款好用的保温杯」,要求 200 字左右,带 emoji,口语化,第一人称,结尾带互动提问。",
    "B": "写一篇公众号文章,主题「为什么年轻人开始戒掉短视频」,800 字左右,有观点有例证有结论,不要太正式。",
    "C": "甲乙丙三人,甲说乙在说谎,乙说丙在说谎,丙说甲乙都在说谎。谁在说真话?请给出推理过程。",
    "D": "把这段话润色得更自然口语化,但保持原意:「该产品在续航方面表现优异,能够满足用户全天候使用需求,值得推荐。」",
}

for mid, pkey, outfile in RETRIES:
    opath = os.path.join(D, f"{outfile}_retry.txt")
    prompt = PROMPTS[pkey]
    t0 = time.time()
    r = subprocess.run(
        ["minis-model-use", "run", "--model", mid, "--prompt", prompt,
         "--max-tokens", "4096", "--output", opath],
        capture_output=True, text=True, timeout=120
    )
    elapsed = round(time.time() - t0, 1)
    # 检查输出文件
    ok = os.path.exists(opath)
    tlen = os.path.getsize(opath) if ok else 0
    # 检查 rc 内容
    result_ok = False
    try:
        # rc 的输出可能是 stdout 的 JSON
        out_json = r.stdout or ""
        if '"ok" : true' in out_json or '"ok": true' in out_json:
            result_ok = True
    except: pass
    status = "✅" if (ok and tlen > 50) else "❌"
    print(f"  {status} {mid:30s} P{pkey} | {elapsed:>5}s | file={tlen:>5}B | ok={ok} | result_ok={result_ok}")
    time.sleep(2)  # 串行间隔

print("重试完成")
