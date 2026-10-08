#!/usr/bin/env python3
"""批量运行SOP质量检查，覆盖全部20章"""
import subprocess, json, os, sys

BASE = "/var/minis/shared/novel-team"
CHAPTERS_DIR = f"{BASE}/projects/my-novel/chapters"
REPORTS_DIR = f"{BASE}/reports/sop-check"
TOOLS = f"{BASE}/tools"

os.makedirs(REPORTS_DIR, exist_ok=True)

results = []

for i in range(1, 21):
    ch_file = f"{CHAPTERS_DIR}/chapter-{i:03d}.md"
    ch_num = str(i)
    print(f"\n{'='*60}")
    print(f"第 {i:02d} 章质量检查")
    print(f"{'='*60}")

    chapter_result = {"chapter": i, "file": os.path.basename(ch_file)}

    # === 1. humanizer-9d ===
    try:
        r = subprocess.run(
            ["python3", f"{TOOLS}/humanizer-9d.py",
             "--chapter-file", ch_file, "--json"],
            capture_output=True, text=True, timeout=60, cwd=BASE
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            chapter_result["humanizer"] = {
                "score": d.get("overall_score"),
                "level": d.get("level"),
                "color": d.get("color"),
                "passed": d.get("passed_dimensions"),
                "total": d.get("total_dimensions"),
                "failed": d.get("failed_dimensions"),
                "dimensions": {k: {"score": v["score"], "passed": v["passed"]}
                               for k, v in d.get("dimensions", {}).items()},
            }
            print(f"  九维评分: {d.get('overall_score')} ({d.get('level')}) {d.get('color')}")
            print(f"  通过: {d.get('passed_dimensions')}/{d.get('total_dimensions')}  "
                  f"未通过: {d.get('failed_dimensions')}")
        else:
            chapter_result["humanizer"] = {"error": r.stderr[:200]}
            print(f"  九维评分: 错误 - {r.stderr[:100]}")
    except Exception as e:
        chapter_result["humanizer"] = {"error": str(e)}
        print(f"  九维评分: 异常 - {e}")

    # === 2. gate-check ===
    try:
        r = subprocess.run(
            ["python3", f"{TOOLS}/gate-check.py", "check",
             "--chapter", ch_num, "--file", ch_file, "--mode", "write"],
            capture_output=True, text=True, timeout=60, cwd=BASE
        )
        gate_output = (r.stdout + r.stderr)[:500]
        passed = "PASS" in gate_output.upper() or "pass" in gate_output
        blocked = "BLOCK" in gate_output.upper() or "FAIL" in gate_output.upper() or "阻断" in gate_output
        chapter_result["gate_check"] = {
            "returncode": r.returncode,
            "passed": passed,
            "blocked": blocked,
            "output": gate_output[:300],
        }
        status = "✅ PASS" if passed and not blocked else ("❌ BLOCKED" if blocked else "⚠️ UNKNOWN")
        print(f"  门禁检查: {status}")
    except Exception as e:
        chapter_result["gate_check"] = {"error": str(e)}
        print(f"  门禁检查: 异常 - {e}")

    # === 3. logic-review ===
    try:
        r = subprocess.run(
            ["python3", f"{TOOLS}/logic-review.py", "--file", ch_file, "--json"],
            capture_output=True, text=True, timeout=60, cwd=BASE
        )
        if r.returncode == 0:
            d = json.loads(r.stdout)
            errors = d.get("errors", [])
            warnings = d.get("warnings", [])
            chapter_result["logic_review"] = {
                "errors": len(errors),
                "warnings": len(warnings),
                "error_list": [e.get("message", e.get("desc", str(e)))[:80] for e in errors[:5]],
                "warning_list": [w.get("message", w.get("desc", str(w)))[:80] for w in warnings[:5]],
            }
            err_str = f"❌ {len(errors)} errors" if errors else "✅ no errors"
            warn_str = f"⚠️ {len(warnings)} warnings" if warnings else "✅ no warnings"
            print(f"  逻辑审查: {err_str} / {warn_str}")
            for e in errors[:3]:
                print(f"    - {e.get('message', e.get('desc', str(e)))[:60]}")
        else:
            chapter_result["logic_review"] = {"error": r.stderr[:200]}
            print(f"  逻辑审查: 错误 - {r.stderr[:100]}")
    except Exception as e:
        chapter_result["logic_review"] = {"error": str(e)}
        print(f"  逻辑审查: 异常 - {e}")

    # === 4. 字数统计 ===
    with open(ch_file, "r", encoding="utf-8") as f:
        text = f.read()
    # 去掉frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
    import re
    cn_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    chapter_result["word_count"] = cn_chars
    word_ok = 800 <= cn_chars <= 2200
    print(f"  字数: {cn_chars} {'✅' if word_ok else '⚠️'}")

    # === 5. 英文残留检测 ===
    eng_sentences = re.findall(r'[A-Za-z]{4,}(?:\s+[A-Za-z]{3,})+', text)
    if eng_sentences:
        chapter_result["english_residue"] = eng_sentences[:3]
        print(f"  英文残留: ❌ {eng_sentences[:2]}")
    else:
        chapter_result["english_residue"] = []
        print(f"  英文残留: ✅ 无")

    # === 6. Markdown残留检测 ===
    md_bolds = re.findall(r'\*\*[^*]+\*\*', text)
    if md_bolds:
        chapter_result["markdown_residue"] = md_bolds[:3]
        print(f"  Markdown残留: ❌ {md_bolds[:2]}")
    else:
        chapter_result["markdown_residue"] = []
        print(f"  Markdown残留: ✅ 无")

    # === 汇总 ===
    passed_checks = sum(1 for k in ["humanizer","gate_check","logic_review"]
                        if chapter_result.get(k) and "error" not in chapter_result[k])
    chapter_result["checks_run"] = passed_checks
    chapter_result["checks_total"] = 3

    results.append(chapter_result)

# 保存结果
output_file = f"{REPORTS_DIR}/sop-check-all-chapters.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n\n结果已保存: {output_file}")

# 打印汇总表
print(f"\n{'='*70}")
print(f"SOP质量检查汇总（20章）")
print(f"{'='*70}")
print(f"{'章':>3} {'九维':>6} {'等级':>4} {'门禁':>8} {'逻辑':>8} {'字数':>6} {'英文':>4} {'MD':>4}")
print(f"{'-'*70}")
for r in results:
    h = r.get("humanizer", {})
    g = r.get("gate_check", {})
    l = r.get("logic_review", {})
    hs = h.get("score", "?")
    hl = h.get("level", "?")
    gs = "PASS" if g.get("passed") else ("BLOCK" if g.get("blocked") else "ERR")
    le = f"{l.get('errors',0)}E" if l.get("errors") else "0E"
    lw = f"{l.get('warnings',0)}W" if l.get("warnings") else "0W"
    ws = r.get("word_count", 0)
    eng = "❌" if r.get("english_residue") else "✅"
    md = "❌" if r.get("markdown_residue") else "✅"
    print(f"{r['chapter']:>3} {hs:>6} {hl:>4} {gs:>8} {le:>4} {lw:>4} {ws:>6} {eng:>4} {md:>4}")

print(f"\n总计: {len(results)} 章")
avg_score = sum(r["humanizer"].get("score", 0) or 0 for r in results) / len(results)
print(f"平均九维评分: {avg_score:.1f}")
total_words = sum(r.get("word_count", 0) for r in results)
print(f"总字数: {total_words}")
under_word = sum(1 for r in results if r.get("word_count", 0) < 800)
print(f"字数不足800: {under_word} 章")
eng_issues = sum(1 for r in results if r.get("english_residue"))
print(f"英文残留: {eng_issues} 章")
md_issues = sum(1 for r in results if r.get("markdown_residue"))
print(f"Markdown残留: {md_issues} 章")
