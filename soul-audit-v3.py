#!/usr/bin/env python3
# Version: 0.1.0
# -*- coding: utf-8 -*-
"""SOUL.md 第三轮自我认知审计（证据驱动版）
区别于一二轮的纯静态审计：新增"运行实证"维度，用近两周真实执行证据检验规则是否失效/缺失。
"""
import json, subprocess, sys, time, re, os

OUT = "/var/minis/shared/soul-audit-v3"
os.makedirs(OUT, exist_ok=True)
FALLBACK = ["z-ai/glm-5.3-flash", "glm-5.2", "deepseek/deepseek-v4-flash"]

def get_soul():
    r = subprocess.run(["minis-config", "get", "soul.body"], capture_output=True, text=True)
    d = json.loads(r.stdout)
    return json.loads(d["value"])  # double-encoded

SOUL = get_soul()

EVIDENCE = """## 运行证据包（2026-08-24 上轮审计后的真实执行记录，摘自 daily log 与今日实测）

E1 [模型路由连败] 09-07 写一篇公众号长文：agnes-2.5-pro 403余额尽 → sensenova 4000token超时 → sensenova 重试限速 → 第4次才用 OpenRouter free 成功。SOUL 无"模型选择/时间预算/成本"守则，教训只进了 daily log 未晋升为规则。
E2 [规则执行≠规则存在] SOUL 规定"任务停滞>3天主动提醒"。"500行拆分暂缓"(09-07)、"workspace 第3次丢失未根治"(08-19)、"skill-eval 3个FAIL待修"(08-24) 均停滞超一周，从未被提醒。规则写了但从未执行。
E3 [数据腐烂] 今日实测：GLOBAL.md 标记"可用"的 minimax-m3:free 实际 404；agnes-2.5-pro 从余额耗尽恶化为 Invalid API key。GLOBAL §五 无失效日期概念。全局验证器 global-verify.py 存在且能查出问题（今天查出 2 个警告：决策超上限13>10、技能清单缺目），但没有规则强制"改 GLOBAL 必跑验证器"。
E4 [文档自身违反纪律] GLOBAL.md §三 出现整段重复行（同一技能表尾部重复3行）——GOBLAL 自己违反了"去重/边界规则"。
E5 [prompt 注入反效果] 09-07 画像"禁用闭环/赋能/生态"反而诱发 LLM 创造例外，humanizer 13分。已归因但改正方案停留在待办。
E6 [错误处理生效·正例] 09-06 reflect 首次调用 glm 系模型 output_text 恒空，按"重试1次→换模型"流程换 sensenova 成功，未卡死。
E7 [归档决策高效·正例] 09-06~09-08 五个仓库归档（Shimmy/VercelSkills/Liebin等）均"结论先行+明确不落地决策+产物落地"，SOUL 输出标准被良好执行。
E8 [工具误诊] 上轮 09-06 把"返回体字段在 data.output_text"误判为"模型返回空"，旧 soul-audit.py 因此半个多月静默产出空结果无人发现。缺"验证工具本身在工作"的意识。"""

AUDITS = [
 {"id": "E-运行实证", "model": "z-ai/glm-5.3-flash", "prompt":
  "你是 AI Agent 行为审计专家。下面是一份 AI 助手的 SOUL.md（行为准则）和它近两周的真实运行证据。你的任务：**只找规则与实际行为的落差**。\n"
  "1. 哪些规则被违反了（有证据）？为什么没执行——规则本身缺陷还是缺执行机制？\n"
  "2. 证据里暴露了哪些 SOUL 完全没有覆盖的新场景？\n"
  "3. 哪些规则写了等于没写（不可执行/无法检测违规）？\n"
  "不要泛泛挑语法毛病，只谈证据支撑的落差。\n输出纯JSON：{\"findings\":[{\"id\":\"E1\",\"severity\":\"critical|major|minor|info\",\"title\":\"...\",\"description\":\"...\",\"evidence\":\"引用证据编号\",\"suggestion\":\"...\"}],\"score\":{\"/10\":0},\"summary\":\"一句话\"}",
  "body": SOUL + "\n\n" + EVIDENCE},
 {"id": "S-结构冲突", "model": "glm-5.2", "prompt":
  "你是规则系统设计专家。审计这份 SOUL.md 的规则间冲突、优先级漏洞、循环自指。\n"
  "重点：a) 同时触发两条规则时会矛盾吗（如'直接执行'vs'需批准'、'反对是义务'vs'用户坚持'）b) 优先级链是否覆盖所有裁决场景 c) 有无规则互相引用形成循环 d) '需要批准'5项的边界是否清晰。\n"
  "输出纯JSON：{\"findings\":[{\"id\":\"S1\",\"severity\":\"critical|major|minor|info\",\"title\":\"...\",\"description\":\"...\",\"suggestion\":\"...\"}],\"score\":{\"/10\":0},\"summary\":\"一句话\"}",
  "body": SOUL},
 {"id": "L-语言质量", "model": "deepseek/deepseek-v4-flash", "prompt":
  "你是中文文案终审专家。这份 SOUL.md 将被 AI 逐条执行，语言质量=执行准确率。\n"
  "审：a) 歧义句（一条规则可读_out两种执行方式）b) 冗余重复（同一约束出现多处）c) 无法验证的模糊量词（'太泛''简短'缺判据）d) 记忆性（哪几条该做成口诀）e) 错别字。\n"
  "输出纯JSON：{\"findings\":[{\"id\":\"L1\",\"severity\":\"critical|major|minor|info\",\"title\":\"...\",\"description\":\"...\",\"suggestion\":\"...\"}],\"score\":{\"/10\":0},\"summary\":\"一句话\"}",
  "body": SOUL},
 {"id": "C-覆盖缺口", "model": "z-ai/glm-5.3-flash", "prompt":
  "你是 Agent 系统工程专家。这份 SOUL.md 服务于一个运行在 iOS iSH 终端里的个人 AI 助手，生态：21个技能、三层记忆(L1日记/L2周/L3图谱)+GLOBAL.md、多模型路由（100+模型，常失效）、Obsidian 知识库、内容创作流水线（写作→排版→发布）。\n"
  "只找**结构性缺失**：这个运行环境反复需要、但 SOUL 完全没提的行为准则。最多6条，按影响排序，宁缺毋滥。\n"
  "输出纯JSON：{\"findings\":[{\"id\":\"C1\",\"severity\":\"critical|major|minor|info\",\"title\":\"...\",\"description\":\"...\",\"suggestion\":\"...\"}],\"score\":{\"/10\":0},\"summary\":\"一句话\"}",
  "body": SOUL + "\n\n（生态背景已给，不必复述）"},
]

def call(model, messages):
    payload = {"messages": messages, "max_tokens": 3000}
    tried = []
    for m in [model] + [x for x in FALLBACK if x != model]:
        p = "/tmp/sa3_in.json"
        with open(p, "w") as f: json.dump(payload, f, ensure_ascii=False)
        try:
            r = subprocess.run(["minis-model-use", "run", "--model", m, "--input", p],
                               capture_output=True, text=True, timeout=240)
            d = json.loads(r.stdout)
            txt = (d.get("data") or {}).get("output_text") or ""
            if d.get("ok") and len(txt.strip()) > 50:
                return m, txt, tried
            tried.append(f"{m}:{'empty' if d.get('ok') else str(d.get('error'))[:40]}")
        except Exception as e:
            tried.append(f"{m}:{type(e).__name__}")
    return None, "", tried

results = []
for a in AUDITS:
    print(f"== {a['id']} (primary {a['model']})", flush=True)
    t0 = time.time()
    m, txt, tried = call(a["model"], [{"role": "user", "content": a["prompt"] + "\n\n===SOUL.md===\n" + a["body"]}])
    el = time.time() - t0
    parsed = None
    if txt:
        mt = re.search(r"\{.*\}", txt, re.DOTALL)
        if mt:
            try: parsed = json.loads(mt.group())
            except Exception as e: print("   parse fail:", e)
    results.append({"id": a["id"], "model_used": m, "tried": tried, "elapsed": round(el,1),
                    "parsed": parsed, "raw": txt})
    print(f"   -> {m} {el:.0f}s findings={len(parsed['findings']) if parsed else 'FAIL'}", flush=True)

with open(f"{OUT}/raw-{time.strftime('%Y%m%d%H%M')}.json", "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=1)

sev_order = {"critical":0,"major":1,"minor":2,"info":3}
all_f, scores = [], {}
for r in results:
    if r["parsed"]:
        sc = r["parsed"].get("score", {})
        scores[r["id"]] = {"model": r["model_used"], "score": sc.get("/10"),
                           "summary": r["parsed"].get("summary",""), "elapsed": r["elapsed"]}
        for fd in r["parsed"].get("findings", []):
            all_f.append({"src": r["id"], **fd})
all_f.sort(key=lambda x: sev_order.get(x.get("severity","info"), 3))

L = ["# SOUL.md 第三轮自我认知审计报告（证据驱动）\n",
     f"> 时间：{time.strftime('%Y-%m-%d %H:%M')} | 方式：4维多模型交叉审计，含运行证据包\n",
     "## 评分\n", "| 维度 | 模型 | 分 | 用时 | 总结 |", "|---|---|---|---|---|"]
for k, v in scores.items():
    L.append(f"| {k} | {v['model']} | {v['score']}/10 | {v['elapsed']}s | {v['summary']} |")
avg = round(sum(v["score"] or 0 for v in scores.values()) / max(len(scores),1), 1)
L.append(f"\n**均分 {avg}/10**（上轮 7.0）| findings {len(all_f)}\n")
L.append("## 发现（按严重度）\n")
for sev, tag in [("critical","🔴 Critical"),("major","🟠 Major"),("minor","🟡 Minor"),("info","🔵 Info")]:
    items = [f for f in all_f if f.get("severity") == sev]
    if items:
        L.append(f"### {tag}\n")
        for f in items:
            ev = f.get("evidence") or ""
            L.append(f"- **[{f['src']}] {f.get('title','')}**：{f.get('description','')}" + (f"（证据:{ev}）" if ev else ""))
            L.append(f"  - 建议：{f.get('suggestion','')}\n")
for r in results:
    if not r["parsed"]:
        L.append(f"\n⚠️ {r['id']} 审计失败，尝试链：{r['tried']}")
report = "\n".join(L)
with open(f"{OUT}/report.md", "w") as f: f.write(report)
print("\n" + report[:3000])
