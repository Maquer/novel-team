#!/usr/bin/env python3
"""test-degradation.py — D2 并发故障降级策略测试（TEAM.md v0.60）

v0.57 登记了本文件但实际不存在（纸面完成）。本测试覆盖 generate_fix_order() 的
完整声明，包括此前从未被验证过的「同级别次级排序」。

用法：python3 test-degradation.py
退出：全过 exit 0；任一失败 exit 1
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(TOOLS, "gate-check.py")

spec = importlib.util.spec_from_file_location("gc", GATE)
gc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gc)
checker = gc.GateChecker("_test_reg")

fails = []


def check(cond, msg):
    print(f"  {'✅' if cond else '❌'} {msg}")
    if not cond:
        fails.append(msg)


def gates(order):
    return [f["gate"] for f in order]


def level_gate_line(level, label, detail):
    return f"[{level}] {label}：{detail}"


print("\n1. 跨级别排序（P0 > P1 > P2）")
res = {
    "errors": {"p2": [], "p1": [level_gate_line("P1", "字数不足", "1800字")],
               "p0": [level_gate_line("P0", "设定矛盾", "境界不符")]},
    "warnings": {"p2": [level_gate_line("P2", "细节建议", "环境描写")], "p1": []},
}
order = checker.generate_fix_order(res)
check([f["priority"] for f in order] == sorted(f["priority"] for f in order),
      "输出按 priority 升序排列")
check(gates(order)[0] == "fact_consistency", "P0 的 设定矛盾 在最前")
check(order[-1]["level"] == "P2", "P2 在最后")

print("\n2. 同级别次级排序（D2a 修前从未生效）")
# 故意按声明顺序的反向输入
res = {"errors": {"p0": [
    level_gate_line("P0", "AI味超标", "tier_1a=32"),
    level_gate_line("P0", "角色掉线", "林玄在第5段消失"),
    level_gate_line("P0", "设定矛盾", "主角境界与功法不符"),
]}, "warnings": {}}
got = gates(checker.generate_fix_order(res))
doc = ["fact_consistency", "character_consistency", "ai_tone"]
check(got == doc, f"声明链 设定矛盾>角色掉线>AI味 实际 {got}")

res = {"warnings": {"p1": [
    level_gate_line("P1", "钩子缺失", "章末无钩子"),
    level_gate_line("P1", "字数不足", "1900字"),
    level_gate_line("P1", "禁用词", "最后"),
]}, "errors": {}}
got = gates(checker.generate_fix_order(res))
doc = ["word_count", "forbidden_words", "hook"]
check(got == doc, f"声明链 字数>禁用词>钩子 实际 {got}")

print("\n3. 同 gate 多问题不丢失（D2b 修前静默丢弃）")
res = {"errors": {"p0": [
    level_gate_line("P0", "设定矛盾", "主角境界与功法不符"),
    level_gate_line("P0", "设定矛盾", "功法品阶与武库记录冲突"),
]}, "warnings": {}}
got = checker.generate_fix_order(res)
check(len(got) == 2, f"同 gate 两条不同问题均保留，实际 {len(got)} 条")

res = {"errors": {"p0": [
    level_gate_line("P0", "设定矛盾", "主角境界与功法不符"),
    level_gate_line("P0", "设定矛盾", "主角境界与功法不符"),
]}, "warnings": {}}
got = checker.generate_fix_order(res)
check(len(got) == 1, f"完全重复的行仍被去重，实际 {len(got)} 条")

print("\n4. 未识别 gate 不破坏排序")
res = {"errors": {"p0": [level_gate_line("P0", "全新未识别门禁", "某问题")]}, "warnings": {}}
got = checker.generate_fix_order(res)
check(len(got) == 1 and got[0]["sub_priority"] == 99,
      f"未知 gate 落到 SUB_FALLBACK=99，实际 {got[0]['sub_priority'] if got else 'N/A'}")

print("\n5. 真实章节 --fix-order 可运行")
ch = os.path.join(TOOLS, "..", "projects", "_test_reg", "chapters", "ch009.md")
if os.path.exists(ch):
    r = subprocess.run([sys.executable, GATE, "--file", ch, "--fix-order"],
                       capture_output=True, text=True, timeout=120)  # FIX 2026-09-30: 加 timeout
    # 退出码语义变更（门禁阻断修复后）：0 = 通过，1 = 被 P0 阻断。
    # 修前阻断是死代码，恒为 0；现两种都是合法结果，只排除崩溃码（>=2 / -9 等）
    check(r.returncode in (0, 1),
          f"exit ∈ {{0,1}}（实际 {r.returncode}）")
    check("Traceback" not in r.stderr, "stderr 无 Traceback（未崩溃）")
    check("ERROR:" not in r.stderr, "stderr 无 ERROR: 前缀")
    # D2c：stdout 必须是纯 JSON（修前被 📡 事件行污染）
    stdout = r.stdout.strip()
    check(not stdout.startswith("📡"), "stdout 未被事件行污染")
    try:
        json.loads(stdout)
        check(True, "stdout 是合法 JSON")
    except Exception as e:
        check(False, f"stdout 非合法 JSON：{e}")
else:
    print(f"  ⏭️ 跳过（无 {ch}）")

print("\n6. ai_tone 失败真实阻断（FIX 2026-09-30 新增）")
# 回归 09-28 门禁阻断层 0% 生效：构造 tier_1a>=16 的章节（novel-humanizer 实测
# tier_1a=39），跑 gate-check CLI，断言 passed == False 且 p0_failures 含 ai_tone。
# 注意：当前代码 p0_failures 承载的是各门禁的 details 文案（非 gate 名），
# 故匹配 "AI味"/"ai_tone" 关键字。若断言失败，测试整体 exit 非零。
_ai_vocab = ["仿佛", "不禁", "心中一凛", "嘴角微扬", "目光如炬", "只见", "此时此刻"]
_ai_lines = []
for _i in range(30):
    _w = _ai_vocab[_i % len(_ai_vocab)]
    _ai_lines.append(f"第{_i+1}段：林玄{_w}看着远方{_w}，{_w}天地灵气翻涌{_w}。")
for _i in range(10):
    _ai_lines.append("他出剑快，出剑准，出剑狠。")  # 排比三连（Category7）
for _i in range(8):
    _ai_lines.append("说白了，这一剑无人能挡。")  # 禁用起手式（规则9）
_ai_text = "\n".join(_ai_lines)

with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                 encoding="utf-8") as _tf:
    _tf.write(_ai_text)
    _ai_chapter = _tf.name
try:
    r = subprocess.run([sys.executable, GATE, "--file", _ai_chapter],
                       capture_output=True, text=True, timeout=120)  # FIX 2026-09-30: 加 timeout
    try:
        _data = json.loads(r.stdout)
    except Exception:
        _data = None
        check(False,
              f"gate-check 未输出合法 JSON（疑似崩溃），stderr 摘要：{r.stderr.strip()[:300]}")
    if _data is not None:
        check(_data.get("passed") is False,
              f"高AI味章节 passed == False（实际 passed={_data.get('passed')}）")
        _p0 = _data.get("p0_failures", []) or []
        check(any("AI味" in str(d) or "ai_tone" in str(d) for d in _p0),
              f"p0_failures 含 ai_tone 条目（实际 {len(_p0)} 条）")
finally:
    os.unlink(_ai_chapter)

print("\n" + "=" * 56)
if fails:
    for f in fails:
        print(f"  ❌ {f}")
    print(f"{len(fails)} 项失败")
    sys.exit(1)
print("  ✅ 全部通过")
