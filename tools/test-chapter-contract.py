#!/usr/bin/env python3
"""
章节契约回归测试（反向断言优先）

用法：python3 tools/test-chapter-contract.py
退出码：0=全部通过；1=有回归

断言设计：
  G1 正确契约（全匹配）          → passed=True
  B1 缺 V 段                   → passed=False
  B2 缺 E 段                   → passed=False
  B3 E hook 过短(<5字)          → passed=False
  G2 L4 双高潮（≤2，正常）      → passed=True
  B4 L4 三高中超（≥3，超标）    → passed=False
  G3 无 frontmatter 但有 VICE   → passed=True
  B5 tension_in 越界            → passed=False
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
TOOL = HERE / "chapter-contract.py"

PASS, FAIL = 0, []


def run_test(label, content, expect_passed=None):
    global PASS
    d = tempfile.mkdtemp()
    p = Path(d) / "test.md"
    p.write_text(content, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(TOOL), "validate", "--chapter-file", str(p)],
        capture_output=True, text=True, timeout=30, cwd=str(HERE.parent)
    )
    try:
        result = json.loads(r.stdout)
        ok = result.get("passed", False)
    except Exception:
        ok = False
    status = "✅" if (expect_passed is None or ok == expect_passed) else "❌"
    if expect_passed is not None and ok == expect_passed:
        PASS += 1
    print(f"  {status} {label}: passed={ok}")
    if not ok and expect_passed == True:
        for e in result.get("errors", []):
            print(f"     ERR: {e[:90]}")
    if ok and expect_passed == False:
        print(f"     UNEXPECTED PASS")


# 基础模板（与 characters.json 中 char-001 淬体三重一致）
TMPL = """---
title: 第1章 开篇
charm_level: L1
---
# 第1章 开篇

## [V] 前提状态
realm: 淬体三重
anchors: [F0003]

## [I] 铺垫/信息释放
tension_in: 0.5
new_info: [王大首战挑衅]

## [C] 高潮结算
climax: L2
outcome: 萧辰迎战

## [E] 收尾钩子+状态变更
hook: 王大冷笑：你首战是我。
changes: []
"""
run_test("G1 正确契约", TMPL, expect_passed=True)
run_test("B1 缺 V 段", TMPL.split("## [V]")[1], expect_passed=False)
run_test("B2 缺 E 段", TMPL.split("## [E]")[0] + "## [E]\nhook: 短\nchanges: []", expect_passed=False)
run_test("B3 E hook 过短(<5字)", TMPL.replace("王大冷笑：你首战是我。", "短"), expect_passed=False)
run_test("G2 L4 双高潮（上限内）",
         TMPL.replace("climax: L2\noutcome: 萧辰迎战",
                      "climax: L4\noutcome: a\nc climax: L4\noutcome: b"),
         expect_passed=True)
run_test("B4 L4 三高中超",
         TMPL.replace("climax: L2\noutcome: 萧辰迎战",
                      "climax: L4\noutcome: a\nc climax: L4\noutcome: b\nc climax: L4\noutcome: c"),
         expect_passed=False)
run_test("G3 无 frontmatter 有 VICE", """# 第1章\n## [V]\nrealm: 淬体三重\n## [I]\ntension_in: 0.5\n## [C]\nclimax: L1\n## [E]\nhook: 明日再来战。\nchanges: []\n""", expect_passed=True)
run_test("B5 tension_in 越界", TMPL.replace("tension_in: 0.5", "tension_in: 1.5"), expect_passed=False)

print(f"\n结果: {PASS} 通过 / {len(FAIL)} 失败")
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
