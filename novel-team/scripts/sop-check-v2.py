#!/usr/bin/env python3
"""SOP质量检查 - 正确解析JSON版本"""
import subprocess, json, os, re

BASE = "/var/minis/shared/novel-team"
CHAPTERS_DIR = f"{BASE}/projects/my-novel/chapters"
TOOLS = f"{BASE}/tools"

results = []

for i in range(1, 21):
    ch_file = f"{CHAPTERS_DIR}/chapter-{i:03d}.md"
    r = {"chapter": i}

    # 1. humanizer-9d
    try:
        out = subprocess.run(
            ["python3", f"{TOOLS}/humanizer-9d.py", "--chapter-file", ch_file, "--json"],
            capture_output=True, text=True, timeout=60, cwd=BASE
        ).stdout
        d = json.loads(out)
        r["humanizer"] = {
            "score": d.get("overall_score"),
            "level": d.get("level"),
            "failed": d.get("failed_dimensions", []),
            "dialogue": d.get("dimensions", {}).get("dialogue", {}).get("score"),
            "era": d.get("dimensions", {}).get("era_adapt", {}).get("score"),
        }
    except: r["humanizer"] = None

    # 2. gate-check
    try:
        out = subprocess.run(
            ["python3", f"{TOOLS}/gate-check.py", "check",
             "--chapter", str(i), "--file", ch_file, "--mode", "write"],
            capture_output=True, text=True, timeout=60, cwd=BASE
        ).stdout
        d = json.loads(out)
        r["gate"] = {
            "passed": d.get("passed"),
            "p0": d["summary"]["p0_blockers"],
            "p1": d["summary"]["p1_warnings"],
            "p2": d["summary"]["p2_suggestions"],
            "ai_tone": d["checks"].get("ai_tone", {}).get("tier_1a"),
            "hook": d["checks"].get("hook", {}).get("has_hook"),
            "consistency": d["checks"].get("consistency", {}).get("status"),
            "hook_details": d["checks"].get("hook", {}).get("details", []),
        }
    except: r["gate"] = None

    # 3. logic-review
    try:
        out = subprocess.run(
            ["python3", f"{TOOLS}/logic-review.py", "--file", ch_file, "--json"],
            capture_output=True, text=True, timeout=60, cwd=BASE
        ).stdout
        d = json.loads(out)
        r["logic"] = {"errors": d.get("errors", 0), "warnings": d.get("warnings", 0)}
    except: r["logic"] = None

    # 4. 字数 + 英文/MD残留
    with open(ch_file) as f: text = f.read()
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3: text = parts[2]
    cn = len(re.findall(r'[\u4e00-\u9fff]', text))
    r["word_count"] = cn
    r["eng"] = re.findall(r'[A-Za-z]{4,}(?:\s+[A-Za-z]{3,})+', text)
    r["md"] = re.findall(r'\*\*[^*]+\*\*', text)

    results.append(r)

# 保存
with open(f"{BASE}/reports/sop-check/sop-check-all-chapters.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# 打印
print(f"{'章':>3} {'九维':>5} {'等级':>3} {'门禁':>4} {'P0':>2} {'P1':>2} {'P2':>2} {'AI味':>4} {'钩子':>4} {'字数':>5} {'英文':>3} {'MD':>3}")
print(f"{'-'*70}")
for r in results:
    h = r.get("humanizer") or {}
    g = r.get("gate") or {}
    lc = r.get("logic") or {}
    hs = h.get("score", "?")
    hl = h.get("level", "?")
    gp = "PASS" if g.get("passed") else "FAIL"
    p0 = g.get("p0", "?")
    p1 = g.get("p1", "?")
    p2 = g.get("p2", "?")
    ai = g.get("ai_tone", "?")
    hk = "✅" if g.get("hook") else "❌"
    ws = r.get("word_count", 0)
    eng = "❌" if r.get("eng") else "✅"
    md = "❌" if r.get("md") else "✅"
    le = lc.get("errors", "?")
    lw = lc.get("warnings", "?")
    print(f"{r['chapter']:>3} {hs:>5} {hl:>3} {gp:>4} {p0:>2} {p1:>2} {p2:>2} {ai:>4} {hk:>4} {ws:>5} {eng:>3} {md:>3}")

print(f"\n总计: {len(results)}章")
print(f"平均九维: {sum(r['humanizer']['score'] for r in results if r.get('humanizer'))/sum(1 for r in results if r.get('humanizer')):.1f}")
print(f"门禁通过: {sum(1 for r in results if r.get('gate',{}).get('passed'))}/20")
print(f"P0阻断: {sum(r['gate']['p0'] for r in results if r.get('gate'))}")
print(f"P1警告: {sum(r['gate']['p1'] for r in results if r.get('gate'))}")
print(f"P2建议: {sum(r['gate']['p2'] for r in results if r.get('gate'))}")
print(f"字数不足2000: {sum(1 for r in results if r.get('word_count',0) < 2000)}")
print(f"英文残留: {sum(1 for r in results if r.get('eng'))}")
print(f"MD残留: {sum(1 for r in results if r.get('md'))}")
