#!/usr/bin/env python3
"""
test-abilitykit-tools.py — AbilityKit借鉴工具回归测试

测试内容（P0+P1+P2，共9个工具，44项）：
  P0: plot-pipeline.py / plot-trigger.py / plot-trace.py
  P1: state-modifier.py / continuous-state.py
  P2: plot-tag.py / character-hfsman.py / narrative-flow.py / plot-explain.py

运行：
  python test-abilitykit-tools.py
"""

import sys
import json
import subprocess
from pathlib import Path

# 工具目录绝对路径
TOOLS_DIR = Path(__file__).parent.resolve()
PYTHON = sys.executable


def run_cmd(args):
    """运行命令并返回结果（用绝对路径确保subprocess能找到脚本）"""
    script = str(TOOLS_DIR / args[0])
    cmd = [PYTHON, script] + args[1:]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def test_plot_pipeline():
    """测试剧情流水线引擎"""
    print("\n" + "=" * 60)
    print("🎬 测试 PlotPipeline（剧情流水线）")
    print("=" * 60)
    
    tests = [
        ("build", ["plot-pipeline.py", "build", "-p", "test-pipe", "--phases", "hook,rise,conflict,climax,resolution"]),
        ("status", ["plot-pipeline.py", "status", "-p", "test-pipe"]),
        ("run_hook", ["plot-pipeline.py", "run", "-p", "test-pipe", "--phase", "hook", "--context-json", '{"chapter":1}']),
        ("status_after", ["plot-pipeline.py", "status", "-p", "test-pipe", "--phase", "hook"]),
    ]
    
    passed = 0
    for name, args in tests:
        rc, stdout, stderr = run_cmd(args)
        if rc == 0:
            print(f"  ✅ {name}: PASS")
            passed += 1
        else:
            print(f"  ❌ {name}: FAIL - {stderr[:80]}")
    
    return passed == len(tests)


def test_plot_trigger():
    """测试剧情触发器"""
    print("\n" + "=" * 60)
    print("⚡ 测试 PlotTrigger（剧情触发器）")
    print("=" * 60)
    
    tests = [
        ("register", ["plot-trigger.py", "-p", "test-trigger-x", "register", "--event-type", "chapter_start", "--action", "write_fact", "--priority", "5"]),
        ("fire", ["plot-trigger.py", "-p", "test-trigger-x", "fire", "--event-type", "chapter_start", "--payload", '{"chapter":1}']),
        ("list", ["plot-trigger.py", "-p", "test-trigger-x", "list"]),
        ("history", ["plot-trigger.py", "-p", "test-trigger-x", "history", "--limit", "5"]),
    ]
    
    passed = 0
    for name, args in tests:
        rc, stdout, stderr = run_cmd(args)
        if rc == 0:
            print(f"  ✅ {name}: PASS")
            passed += 1
        else:
            print(f"  ❌ {name}: FAIL - {stderr[:80]}")
    
    return passed == len(tests)


def test_plot_trace():
    """测试剧情溯源链"""
    print("\n" + "=" * 60)
    print("🔗 测试 PlotTrace（剧情溯源链）")
    print("=" * 60)
    
    tests = [
        ("add1", ["plot-trace.py", "-p", "test-trace-x", "add", "--chapter", "1", "--event", "天命剑现世", "--event-type", "world_event", "--tags", "天命剑,上古"]),
        ("add2", ["plot-trace.py", "-p", "test-trace-x", "add", "--chapter", "5", "--event", "萧辰得剑", "--event-type", "foreshadow_recall", "--parents", "E0001", "--tags", "天命剑,觉醒"]),
        ("back", ["plot-trace.py", "-p", "test-trace-x", "trace-back", "--node-id", "E0002", "--depth", "3"]),
        ("fwd", ["plot-trace.py", "-p", "test-trace-x", "trace-forward", "--node-id", "E0001", "--depth", "2"]),
        ("consist", ["plot-trace.py", "-p", "test-trace-x", "check-consistency"]),
        ("graph", ["plot-trace.py", "-p", "test-trace-x", "graph"]),
    ]
    
    passed = 0
    for name, args in tests:
        rc, stdout, stderr = run_cmd(args)
        if rc == 0:
            print(f"  ✅ {name}: PASS")
            passed += 1
        else:
            print(f"  ❌ {name}: FAIL - {stderr[:80]}")
    
    return passed == len(tests)


def test_state_modifier():
    """测试状态修正器"""
    print("\n" + "=" * 60)
    print("🎯 测试 StateModifier（状态修正器）")
    print("=" * 60)
    
    tests = [
        ("base", ["state-modifier.py", "-p", "test-mod-x", "base", "--target", "萧辰", "--stat", "combat_power", "--set-val", "100"]),
        ("buff", ["state-modifier.py", "-p", "test-mod-x", "add", "--target", "萧辰", "--name", "愤怒_buff", "--value", "20", "--mtype", "buff", "--reason", "战意高涨"]),
        ("debuff", ["state-modifier.py", "-p", "test-mod-x", "add", "--target", "萧辰", "--name", "受伤_debuff", "--value", "-30", "--mtype", "debuff", "--reason", "擂台战受伤"]),
        ("apply", ["state-modifier.py", "-p", "test-mod-x", "apply", "--target", "萧辰", "--stat", "combat_power", "--chapter", "5"]),
        ("list", ["state-modifier.py", "-p", "test-mod-x", "list", "--target", "萧辰"]),
        ("summary", ["state-modifier.py", "-p", "test-mod-x", "summary"]),
    ]
    
    passed = 0
    for name, args in tests:
        rc, stdout, stderr = run_cmd(args)
        if rc == 0:
            print(f"  ✅ {name}: PASS")
            passed += 1
        else:
            print(f"  ❌ {name}: FAIL")
            print(f"     stderr: {stderr[:200]}")
            print(f"     stdout: {stdout[:200]}")
    
    return passed == len(tests)


def test_continuous_state():
    """测试持续状态系统"""
    print("\n" + "=" * 60)
    print("⏳ 测试 ContinuousState（持续状态）")
    print("=" * 60)
    tests = [
        ("add", ["continuous-state.py", "-p", "test-cs-x", "add", "--name", "追杀中", "--tags", "追杀,威胁", "--chapter", "5", "--trigger", "萧辰发现父亲遗言"]),
        ("tick", ["continuous-state.py", "-p", "test-cs-x", "tick", "--chapter", "6"]),
        ("list", ["continuous-state.py", "-p", "test-cs-x", "list"]),
        ("summary", ["continuous-state.py", "-p", "test-cs-x", "summary"]),
    ]
    passed = 0
    for name, args in tests:
        rc, _, stderr = run_cmd(args)
        if rc == 0: print(f"  ✅ {name}: PASS"); passed += 1
        else: print(f"  ❌ {name}: FAIL - {stderr[:80]}")
    return passed == len(tests)


def test_plot_tag():
    """测试剧情标签系统"""
    print("\n" + "=" * 60)
    print("🏷️ 测试 PlotTag（剧情标签）")
    print("=" * 60)
    tests = [
        ("add", ["plot-tag.py", "-p", "test-pt-x", "add", "--name", "复仇线", "--desc", "萧辰复仇主线"]),
        ("add_sub", ["plot-tag.py", "-p", "test-pt-x", "add", "--name", "天命剑", "--parent", "TG0001"]),
        ("search", ["plot-tag.py", "-p", "test-pt-x", "search", "--keyword", "复仇"]),
        ("tree", ["plot-tag.py", "-p", "test-pt-x", "tree"]),
        ("summary", ["plot-tag.py", "-p", "test-pt-x", "summary"]),
    ]
    passed = 0
    for name, args in tests:
        rc, _, stderr = run_cmd(args)
        if rc == 0: print(f"  ✅ {name}: PASS"); passed += 1
        else: print(f"  ❌ {name}: FAIL - {stderr[:80]}")
    return passed == len(tests)


def test_hfsman():
    """测试角色心理状态机"""
    print("\n" + "=" * 60)
    print("🧠 测试 CharacterHFSM（角色心理状态机）")
    print("=" * 60)
    tests = [
        ("create", ["character-hfsman.py", "-p", "test-hm-x", "create", "--char", "萧辰", "--initial", "calm", "--subs", "angry,collapsed,awakened"]),
        ("trans", ["character-hfsman.py", "-p", "test-hm-x", "transition", "--char", "萧辰", "--from-state", "calm", "--event", "attacked", "--to-state", "angry"]),
        ("fire", ["character-hfsman.py", "-p", "test-hm-x", "fire", "--char", "萧辰", "--event", "attacked", "--chapter", "3"]),
        ("status", ["character-hfsman.py", "-p", "test-hm-x", "status", "--char", "萧辰"]),
        ("history", ["character-hfsman.py", "-p", "test-hm-x", "history", "--char", "萧辰", "--limit", "5"]),
    ]
    passed = 0
    for name, args in tests:
        rc, _, stderr = run_cmd(args)
        if rc == 0: print(f"  ✅ {name}: PASS"); passed += 1
        else: print(f"  ❌ {name}: FAIL - {stderr[:80]}")
    return passed == len(tests)


def test_narrative_flow():
    """测试多线叙事流程"""
    print("\n" + "=" * 60)
    print("📖 测试 NarrativeFlow（多线叙事）")
    print("=" * 60)
    tests = [
        ("add", ["narrative-flow.py", "-p", "test-nf-x", "add", "--name", "三线并行", "--type", "parallel", "--lines", "hero,side,villain"]),
        ("adv", ["narrative-flow.py", "-p", "test-nf-x", "advance", "--node-id", "FN0001", "--line", "hero", "--chapter", "5"]),
        ("check", ["narrative-flow.py", "-p", "test-nf-x", "check", "--node-id", "FN0001"]),
        ("summary", ["narrative-flow.py", "-p", "test-nf-x", "summary"]),
    ]
    passed = 0
    for name, args in tests:
        rc, _, stderr = run_cmd(args)
        if rc == 0: print(f"  ✅ {name}: PASS"); passed += 1
        else: print(f"  ❌ {name}: FAIL - {stderr[:80]}")
    return passed == len(tests)


def test_plot_explain():
    """测试剧情解释器"""
    print("\n" + "=" * 60)
    print("🔍 测试 PlotExplain（剧情解释器）")
    print("=" * 60)
    tests = [
        ("add", ["plot-explain.py", "-p", "test-pe-x", "add", "--chapter", "5", "--event", "萧辰觉醒", "--explanation", "天命剑触发血祭", "--source", "trace"]),
        ("explain", ["plot-explain.py", "-p", "test-pe-x", "explain", "--chapter", "5"]),
        ("chain", ["plot-explain.py", "-p", "test-pe-x", "chain", "--node-id", "EX0001", "--depth", "2"]),
        ("summary", ["plot-explain.py", "-p", "test-pe-x", "summary"]),
    ]
    passed = 0
    for name, args in tests:
        rc, _, stderr = run_cmd(args)
        if rc == 0: print(f"  ✅ {name}: PASS"); passed += 1
        else: print(f"  ❌ {name}: FAIL - {stderr[:80]}")
    return passed == len(tests)


def main():
    print("\n" + "=" * 60)
    print("🧪 AbilityKit 借鉴工具回归测试")
    print("=" * 60)
    
    results = []
    results.append(("PlotPipeline", test_plot_pipeline()))
    results.append(("PlotTrigger", test_plot_trigger()))
    results.append(("PlotTrace", test_plot_trace()))
    results.append(("StateModifier", test_state_modifier()))
    results.append(("ContinuousState", test_continuous_state()))
    results.append(("PlotTag", test_plot_tag()))
    results.append(("CharacterHFSM", test_hfsman()))
    results.append(("NarrativeFlow", test_narrative_flow()))
    results.append(("PlotExplain", test_plot_explain()))
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 全部测试通过！")
        return 0
    else:
        print(f"\n⚠️ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
