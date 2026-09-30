#!/usr/bin/env python3
"""5 款 AI 模型 × 4 prompt 并行实测脚本"""
import subprocess, json, time, os, concurrent.futures

MODELS = [
    {"id": "DeepSeek-V4-Flash", "label": "Radeon Cloud", "name": "DeepSeek"},
    {"id": "Qwen3.8-Flash-Next", "label": "Radeon Cloud", "name": "Qwen通义"},
    {"id": "z-ai/glm-5.3-flash", "label": "OpenRouter", "name": "GLM智谱"},
    {"id": "MiMo-V2.6-Flash", "label": "Radeon Cloud", "name": "MiMo小米"},
    {"id": "MiniCPM5-2B", "label": "Radeon Cloud", "name": "MiniCPM面壁"},
]

PROMPTS = {
    "A": "帮我写一条小红书种草笔记,主题是「一款好用的保温杯」,要求 200 字左右,带 emoji,口语化,第一人称,结尾带互动提问。",
    "B": "写一篇公众号文章,主题「为什么年轻人开始戒掉短视频」,800 字左右,有观点有例证有结论,不要太正式。",
    "C": "甲乙丙三人,甲说乙在说谎,乙说丙在说谎,丙说甲乙都在说谎。谁在说真话?请给出推理过程。",
    "D": "把这段话润色得更自然口语化,但保持原意:「该产品在续航方面表现优异,能够满足用户全天候使用需求,值得推荐。」",
}

OUTDIR = "/var/minis/shared/xhs-team/实测数据库/api-responses"
os.makedirs(OUTDIR, exist_ok=True)

def run_one(model, prompt_key):
    mid = model["id"]
    mname = model["name"]
    prompt = PROMPTS[prompt_key]
    outfile = os.path.join(OUTDIR, f"{mname}_{prompt_key}.txt")
    t0 = time.time()
    try:
        r = subprocess.run(
            ["minis-model-use", "run", "--model", mid, "--prompt", prompt,
             "--max-tokens", "4096", "--output", outfile],
            capture_output=True, text=True, timeout=120
        )
        elapsed = round(time.time() - t0, 1)
        # 读取输出文件
        text = ""
        if os.path.exists(outfile):
            with open(outfile, "r") as f:
                text = f.read()
        else:
            text = r.stdout or r.stderr or "(empty)"
        return {
            "model": mname, "prompt": prompt_key,
            "elapsed": elapsed, "rc": r.returncode,
            "text_len": len(text), "text_preview": text[:200],
            "text_full_file": outfile,
        }
    except subprocess.TimeoutExpired:
        return {"model": mname, "prompt": prompt_key, "elapsed": 120,
                "rc": -1, "error": "timeout 120s"}
    except Exception as e:
        return {"model": mname, "prompt": prompt_key,
                "elapsed": round(time.time()-t0,1), "rc": -2, "error": str(e)}

# 构建 20 个任务
tasks = [(m, p) for m in MODELS for p in PROMPTS]
print(f"共 {len(tasks)} 个任务,并行执行(max_workers=10)...")

results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
    futures = {pool.submit(run_one, m, p): (m["name"], p) for m, p in tasks}
    for i, fut in enumerate(concurrent.futures.as_completed(futures)):
        r = fut.result()
        results.append(r)
        print(f"  [{i+1}/{len(tasks)}] {r['model']}-{r['prompt']} | {r['elapsed']}s | len={r.get('text_len','?')} | rc={r['rc']}")

# 汇总写入
summary_path = os.path.join(OUTDIR, "_summary.json")
with open(summary_path, "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n汇总写入 {summary_path}")
print(f"响应文本在 {OUTDIR}/")
