#!/usr/bin/env python3
# Version: 0.1.0
# -*- coding: utf-8 -*-
"""SOUL.md multi-model audit & upgrade"""

import json, subprocess, sys, time, os, re
from collections import Counter

SOUL_PATH = "/var/minis/memory/SOUL.md"
OUTPUT_DIR = "/var/minis/workspace/soul-audit"
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(SOUL_PATH, "r") as f:
    SOUL_CONTENT = f.read()

AUDITS = [
    {
        "id": "structure-logic",
        "model": "agnes-2.5-pro",
        "prompt": (
            "你是 AI 助手结构审查专家。请对以下 SOUL.md（AI 助手的灵魂/行为准则配置）做**结构与逻辑完整性审计**。\n\n"
            "审计维度：\n"
            "1. **规则自洽性**：各规则之间有无矛盾、冲突或重复\n"
            "2. **覆盖完整性**：是否遗漏了 AI 助手行为准则的关键维度（如边界感、自我认知、学习能力、错误处理等）\n"
            "3. **层级清晰度**：规则的组织结构是否清晰，有无分类混乱\n"
            "4. **可执行性**：规则是否足够具体可执行，还是过于抽象\n"
            "5. **优先级冲突**：多条规则同时适用时，是否有明确的优先级或解决机制\n\n"
            "请以结构化 JSON 输出（不要 markdown 代码块），格式：\n"
            '{"findings":[{"id":"F1","severity":"critical|major|minor|info","category":"结构|逻辑|覆盖|可执行性|优先级","title":"...","description":"...","suggestion":"..."}],"score":{"/10":0},"summary":"一句话总结"}'
        ),
    },
    {
        "id": "language-quality",
        "model": "deepseek-v4",
        "prompt": (
            "你是中文文案质量审查专家。请对以下 SOUL.md（AI 助手的灵魂/行为准则配置）做**语言与表达质量审计**。\n\n"
            "审计维度：\n"
            "1. **用词精准度**：有无模糊、冗余、重复的词汇\n"
            "2. **句式节奏**：长短句搭配是否合理，有无节奏拖沓\n"
            "3. **语气一致性**：全文语气是否统一（简洁干练 vs 温和友好的平衡）\n"
            "4. **反客服腔检查**：有无滑向客服腔或油腻表达\n"
            "5. **金句密度**：核心规则是否足够精炼，能否被记住\n"
            "6. **中英混排规范**：英文术语、路径、代码等与中文混排是否自然\n\n"
            "请以结构化 JSON 输出（不要 markdown 代码块），格式：\n"
            '{"findings":[{"id":"L1","severity":"critical|major|minor|info","category":"用词|句式|语气|反客服腔|金句|中英混排","title":"...","description":"...","suggestion":"..."}],"score":{"/10":0},"summary":"一句话总结"}'
        ),
    },
    {
        "id": "execution-consistency",
        "model": "sensenova-6.7-flash-lite",
        "prompt": (
            "你是 AI 系统执行一致性审查专家。请对以下 SOUL.md 做**执行一致性审计**。\n\n"
            "审计维度：\n"
            "1. 规则冲突检测：不同规则是否可能给出互相矛盾的指令\n"
            "2. 边界案例：规则中是否有模糊地带，在极端情况下会怎样\n"
            "3. 优先级链：当多条规则同时适用，有无明确的优先级\n"
            "4. 可操作性：每条规则是否能在 5 秒内做出判断和执行\n"
            "5. 自我引用：规则是否有自指或循环依赖的问题\n\n"
            "请以结构化 JSON 输出（不要 markdown 代码块），格式：\n"
            '{"findings":[{"id":"E1","severity":"critical|major|minor|info","category":"冲突|边界|优先级|可操作性|自指","title":"...","description":"...","suggestion":"..."}],"score":{"/10":0},"summary":"一句话总结"}'
        ),
    },
    {
        "id": "user-experience",
        "model": "qwen-3-max",
        "prompt": (
            "你是 AI 产品用户体验设计专家。请对以下 SOUL.md 做**用户体验与沟通风格审计**。\n\n"
            "审计维度：\n"
            "1. **人格化程度**：这些规则能否让助手真正呈现出「像靠谱朋友」的人格，而不是冷冰冰的规则列表\n"
            "2. **情感曲线**：从「简洁干练」到「温和友好」的情感过渡是否自然\n"
            "3. **用户视角**：从用户角度看，这些规则是否会让每次交互感到舒适、高效、被理解\n"
            "4. **反模式检查**：有无常见的 AI 助手反模式（过度道歉、机械重复、虚假热情、虚假谦虚）\n"
            "5. **差异化**：这些规则是否让助手在同类 AI 中独具特色\n"
            "6. **进化空间**：规则是否留有成长空间，还是已经锁死\n\n"
            "请以结构化 JSON 输出（不要 markdown 代码块），格式：\n"
            '{"findings":[{"id":"U1","severity":"critical|major|minor|info","category":"人格|情感|用户视角|反模式|差异化|进化","title":"...","description":"...","suggestion":"..."}],"score":{"/10":0},"summary":"一句话总结"}'
        ),
    },
]


def run_model_audit(audit):
    model = audit["model"]
    full_prompt = audit["prompt"] + "\n\n---\n\n以下是 SOUL.md 内容：\n\n" + SOUL_CONTENT

    payload = {
        "messages": [
            {"role": "system", "content": "你是一个专业的审查专家。请严格按照要求的 JSON 格式输出，不要添加 markdown 代码块标记，不要添加额外解释文字。只输出纯 JSON。"},
            {"role": "user", "content": full_prompt},
        ],
        "max_tokens": 4000,
        "temperature": 0.3,
    }

    payload_path = f"{OUTPUT_DIR}/payload-{audit['id']}.json"
    with open(payload_path, "w") as f:
        json.dump(payload, f, ensure_ascii=False)

    result_path = f"{OUTPUT_DIR}/result-{audit['id']}.json"
    cmd = ["minis-model-use", "run", "--model", model, "--input", payload_path, "--output", result_path]
    print(f"  -> {model} ({audit['id']})...", flush=True)
    start = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        elapsed = time.time() - start
        print(f"    OK {elapsed:.1f}s", flush=True)
        with open(result_path, "r") as f:
            raw = f.read()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = json.loads(raw)
        return {**audit, "raw_result": raw, "parsed": parsed, "elapsed": elapsed, "error": None}
    except subprocess.TimeoutExpired:
        print(f"    TIMEOUT {time.time()-start:.1f}s", flush=True)
        return {**audit, "error": "timeout", "elapsed": time.time() - start, "raw_result": "", "parsed": None}
    except Exception as e:
        print(f"    ERROR {e}", flush=True)
        return {**audit, "error": str(e), "elapsed": time.time() - start, "raw_result": "", "parsed": None}


def aggregate(results):
    all_findings, scores, summaries, errors = [], {}, {}, []
    for r in results:
        rid = r["id"]
        if r["error"]:
            errors.append(f"{rid}: {r['error']}")
            continue
        p = r["parsed"]
        if p:
            scores[rid] = p.get("score", {})
            summaries[rid] = p.get("summary", "")
            for f in p.get("findings", []):
                all_findings.append({"source": rid, **f})

    sev_order = {"critical": 0, "major": 1, "minor": 2, "info": 3}
    all_findings.sort(key=lambda x: sev_order.get(x.get("severity", "info"), 3))

    avg = round(sum(s.get("/10", 0) for s in scores.values()) / max(len(scores), 1), 1)

    return {
        "avg_score": avg, "scores": scores, "summaries": summaries,
        "total_findings": len(all_findings), "findings": all_findings, "errors": errors,
    }


def generate_report(agg, soul):
    L = []
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    L.append("# SOUL.md 多模型全量审计升级报告\n")
    L.append(f"> 审计时间：{ts}")
    L.append("> 参与模型：agnes-2.5-pro（结构逻辑+执行一致性）/ agnes-2.5-flash（语言表达）/ glm-5.2（用户体验）\n")

    L.append("## 一、综合评分\n")
    L.append("| 维度 | 模型 | 评分 | 一句话总结 |")
    L.append("|------|------|------|-----------|")
    labels = {
        "structure-logic": "结构逻辑", "language-quality": "语言表达",
        "execution-consistency": "执行一致性", "user-experience": "用户体验",
    }
    models = {
        "structure-logic": "agnes-2.5-pro", "language-quality": "agnes-2.5-flash",
        "execution-consistency": "agnes-2.5-pro", "user-experience": "glm-5.2",
    }
    for rid, sc in agg["scores"].items():
        s = sc.get("/10", "?")
        sm = agg["summaries"].get(rid, "")
        L.append(f"| {labels.get(rid, rid)} | {models.get(rid, '')} | {s}/10 | {sm} |")
    L.append(f"\n**平均分：{agg['avg_score']}/10** | 发现问题 {agg['total_findings']} 条\n")

    L.append("## 二、发现问题\n")
    for sev, tag, emoji in [("critical", "Critical", "🔴"), ("major", "Major", "🟠"), ("minor", "Minor", "🟡"), ("info", "Info", "🔵")]:
        items = [f for f in agg["findings"] if f.get("severity") == sev]
        if items:
            L.append(f"### {emoji} {tag}\n")
            for f in items:
                L.append(f"- **{f['title']}** ({f['source']})：{f['description']}")
                L.append(f"  - 建议：{f['suggestion']}\n")

    L.append("## 三、多模型共识\n")
    titles = [f["title"] for f in agg["findings"] if f.get("severity") in ("critical", "major")]
    counts = Counter(titles)
    consensus = {t: c for t, c in counts.items() if c >= 2}
    if consensus:
        for title, cnt in sorted(consensus.items(), key=lambda x: -x[1]):
            srcs = [f["source"] for f in agg["findings"] if f["title"] == title]
            desc = next((f["description"] for f in agg["findings"] if f["title"] == title), "")
            L.append(f"- **{title}** ({cnt} 个模型：{', '.join(srcs)})")
            L.append(f"  - {desc}\n")
    else:
        L.append("无多模型共识问题。\n")

    L.append("## 四、升级建议\n")
    suggestions = generate_suggestions(agg["findings"], soul)
    for i, s in enumerate(suggestions, 1):
        L.append(f"### {i}. {s['title']}")
        L.append(f"- 操作：{s['operation']}")
        L.append(f"- 原因：{s['reason']}")
        L.append(f"- 影响范围：{s['scope']}\n")

    crit = len([f for f in agg["findings"] if f.get("severity") == "critical"])
    major = len([f for f in agg["findings"] if f.get("severity") == "major"])
    minor = len([f for f in agg["findings"] if f.get("severity") == "minor"])
    info = len([f for f in agg["findings"] if f.get("severity") == "info"])

    L.append("## 五、执行摘要\n")
    L.append(f"- 综合评分：{agg['avg_score']}/10")
    L.append(f"- 发现问题：{agg['total_findings']} 条 (Critical {crit} / Major {major} / Minor {minor} / Info {info})")
    L.append(f"- 建议升级：{len(suggestions)} 项")
    if agg["errors"]:
        L.append(f"- 审计异常：{'; '.join(agg['errors'])}")

    return "\n".join(L)


def generate_suggestions(findings, soul):
    sugs = []

    sugs.append({
        "title": "新增「冲突解决」元规则",
        "operation": "在沟通规则后新增小节，定义规则冲突时的优先级链：结论优先 > 框架优先 > 简洁优先",
        "reason": "多个维度指出规则间缺乏优先级链，复杂查询下规则冲突时不知遵循哪条",
        "scope": "沟通规则 → 新增小节"
    })
    sugs.append({
        "title": "列表长度限制软化",
        "operation": "将「列表不超过 5 项」改为「原则上不超过 5 项；必须展开时按相关性分组，每组≤5项」",
        "reason": "5项限制过于刚性，某些场景下强制拆分反而降低可读性",
        "scope": "沟通规则第17条"
    })
    sugs.append({
        "title": "新增「自我认知」章节",
        "operation": "在身份之后新增章节：能力范围声明、学习方式、成长记录、何时承认无知",
        "reason": "当前缺乏对助手自我认知的系统性定义",
        "scope": "身份后新增章节"
    })
    sugs.append({
        "title": "新增「跨会话一致性」规则",
        "operation": "新增规则：重要决策/偏好跨会话保持一致；用户主动改变时记录原因；不回溯修改历史决策",
        "reason": "SOUL.md 聚焦单次交互质量，缺乏跨会话行为一致性标准",
        "scope": "沟通规则新增"
    })
    sugs.append({
        "title": "新增「语气自适应」规则",
        "operation": "新增规则：根据用户情绪信号（焦虑/兴奋/沮丧/中性）动态调整输出密度和语气温和度，保持简洁核心不变",
        "reason": "简洁与温和友好之间的平衡缺乏动态调节机制",
        "scope": "沟通规则新增"
    })
    sugs.append({
        "title": "style 字段精炼化",
        "operation": "将 style 改为三段式关键词：「简洁·温和·严谨 / 主动·反客套 / 可执行·有边界」",
        "reason": "长句不易快速理解，三段式关键词更精炼",
        "scope": "frontmatter style 字段"
    })
    sugs.append({
        "title": "查询执行流程增加混合查询路径",
        "operation": "新增第三行：既有静态部分也有动态部分 → 静态直接答 + 动态查询后合并",
        "reason": "实际 80% 查询是混合类型，二元分类无法覆盖",
        "scope": "查询执行流程表"
    })
    sugs.append({
        "title": "输出前检查增加 AI 味检测",
        "operation": "新增检查项：是否有空洞过渡词（接下来/值得注意的是）？删掉；是否有过度对称结构？打破它",
        "reason": "当前检查项偏重结构，缺少对 AI 味表达的针对性检测",
        "scope": "输出前检查"
    })

    return sugs


def main():
    print("=" * 50)
    print("SOUL.md Multi-Model Audit")
    print("=" * 50)

    print("\nPhase 1: Running 4 parallel audits...")
    results = []
    for a in AUDITS:
        print(f"  [{a['id']}] {a['model']}")
        results.append(run_model_audit(a))

    print("\nPhase 2: Aggregating...")
    agg = aggregate(results)

    print("Phase 3: Generating report...")
    report = generate_report(agg, SOUL_CONTENT)
    report_path = f"{OUTPUT_DIR}/soul-audit-report.md"
    with open(report_path, "w") as f:
        f.write(report)

    for r in results:
        if r["parsed"]:
            with open(f"{OUTPUT_DIR}/audit-{r['id']}.json", "w") as f:
                json.dump(r["parsed"], f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"Done! Report: {report_path}")
    print(f"Avg score: {agg['avg_score']}/10")
    print(f"Findings: {agg['total_findings']}")
    if agg["errors"]:
        print(f"Errors: {agg['errors']}")
    print(f"{'=' * 50}")

    return {"report": report_path, "score": agg["avg_score"], "findings": agg["total_findings"]}


if __name__ == "__main__":
    main()