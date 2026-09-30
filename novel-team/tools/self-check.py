#!/usr/bin/env python3
"""
小说团队自检脚本 — v0.60
检查：工具可用性、数据完整性、质量债务、待确认区、角色深度
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path("/var/minis/shared/novel-team")
PROJECTS_DIR = BASE_DIR / "projects" / "my-novel"

def check_tools():
    """检查工具可用性"""
    tools = [
        "gate-check.py",
        "quality-debt.py",
        "pending-review.py",
        "character-depth.py",
        "char-context-filter.py",
        "quality-gate.py",
        "fact-ledger.py",
        "guard-v6.py",
        "novel-humanizer.py",
        "context-manager.py",
        "outline-precheck.py",
        "chapter-contract.py",
        "plot-pipeline.py",
        "plot-trigger.py",
        "plot-trace.py",
        "state-modifier.py",
        "continuous-state.py",
        "plot-tag.py",
        "character-hfsman.py",
        "narrative-flow.py",
        "plot-explain.py",
    ]
    results = {}
    for t in tools:
        p = BASE_DIR / "tools" / t
        results[t] = p.exists()
    return results

def check_data():
    """检查数据完整性"""
    results = {}
    
    # 章节
    chap_dir = PROJECTS_DIR / "chapters"
    chapters = list(chap_dir.glob("chapter-*.md")) if chap_dir.exists() else []
    results["chapters"] = len(chapters)
    
    # 角色
    chars_file = PROJECTS_DIR / "characters" / "characters.json"
    if chars_file.exists():
        chars = json.loads(chars_file.read_text(encoding="utf-8"))
        results["characters"] = len(chars.get("characters", []))
    else:
        results["characters"] = 0
    
    # 事实账本
    facts_file = BASE_DIR / "ledger" / "my-novel" / "facts.json"
    if facts_file.exists():
        facts = json.loads(facts_file.read_text(encoding="utf-8"))
        # 兼容两种格式：dict {F0001: {...}} 直接取键数；envelope {"facts": [...]} 取数组长度
        if isinstance(facts, dict):
            results["facts"] = len(facts) if any(k.startswith("F") for k in facts) else len(facts.get("facts", []))
        elif isinstance(facts, list):
            results["facts"] = len(facts)
        else:
            results["facts"] = 0
    else:
        results["facts"] = 0
    
    # 质量债务
    debt_file = BASE_DIR / "ledger" / "my-novel" / "quality-debt.json"
    if debt_file.exists():
        debts = json.loads(debt_file.read_text(encoding="utf-8"))
        results["debts_open"] = debts.get("total_open", 0)
        results["debts_resolved"] = debts.get("total_resolved", 0)
    else:
        results["debts_open"] = 0
        results["debts_resolved"] = 0
    
    # 待确认区
    pending_file = BASE_DIR / "ledger" / "my-novel" / "pending.json"
    if pending_file.exists():
        pendings = json.loads(pending_file.read_text(encoding="utf-8"))
        results["pending"] = len([p for p in pendings if p.get("status") == "pending"])
    else:
        results["pending"] = 0
    
    return results

def check_character_depth():
    """检查角色深度"""
    chars_file = PROJECTS_DIR / "characters" / "characters.json"
    if not chars_file.exists():
        return []
    
    chars = json.loads(chars_file.read_text(encoding="utf-8"))
    thresholds = {"简要": 100, "标准": 300, "深入": 800, "完整": 1500}
    
    results = []
    for c in chars.get("characters", []):
        content = json.dumps(c, ensure_ascii=False)
        length = len(content)
        level = "简要"
        for lvl, t in thresholds.items():
            if length >= t:
                level = lvl
        results.append({
            "id": c["id"],
            "name": c["name"],
            "length": length,
            "level": level,
        })
    return results

def main():
    print("=" * 60)
    # 版本号与 TEAM.md 保持同步；变更脚本时必同步此处
    print("📚 小说团队自检报告 — v0.60")
    print("=" * 60)
    
    # 1. 工具检查
    print("\n[1/4] 工具可用性")
    tools = check_tools()
    ok_tools = sum(1 for v in tools.values() if v)
    total_tools = len(tools)
    print(f"  可用: {ok_tools}/{total_tools}")
    missing = [t for t, v in tools.items() if not v]
    if missing:
        print(f"  ⚠️ 缺失: {', '.join(missing)}")
    else:
        print("  ✅ 全部工具可用")
    
    # 2. 数据完整性
    print("\n[2/4] 数据完整性")
    data = check_data()
    print(f"  章节: {data['chapters']} 篇")
    print(f"  角色: {data['characters']} 个")
    print(f"  事实账本: {data['facts']} 条")
    print(f"  质量债务(未解决): {data['debts_open']} 条")
    print(f"  质量债务(已解决): {data['debts_resolved']} 条")
    print(f"  待确认提案: {data['pending']} 条")
    
    if data['chapters'] == 0:
        print("  ⚠️ 无章节文件")
    if data['characters'] == 0:
        print("  ⚠️ 无角色档案")
    if data['facts'] == 0:
        print("  ⚠️ 事实账本为空")
    
    # 3. 角色深度
    print("\n[3/4] 角色深度评级")
    depths = check_character_depth()
    if depths:
        for d in depths:
            icons = {"简要": "📝", "标准": "📄", "深入": "📚", "完整": "✨"}
            print(f"  {icons.get(d['level'], '?')} [{d['id']}] {d['name']}: {d['level']} ({d['length']}字符)")
    else:
        print("  ⚠️ 无角色数据")
    
    # 4. 健康度评估
    print("\n[4/4] 健康度评估")
    score = 0
    max_score = 100
    
    # 工具完整性 (30分)
    tool_score = int(ok_tools / total_tools * 30) if total_tools > 0 else 0
    score += tool_score
    
    # 数据完整性 (30分)
    if data['chapters'] > 0:
        score += 10
    if data['characters'] > 0:
        score += 10
    if data['facts'] > 0:
        score += 10
    
    # 流程健康 (20分)
    if data['debts_open'] <= 5:
        score += 10
    if data['pending'] <= 3:
        score += 10
    
    # 角色深度 (20分)
    deep_chars = sum(1 for d in depths if d['level'] in ['深入', '完整'])
    score += min(20, deep_chars * 10)
    
    # 评级
    if score >= 80:
        grade = "🟢 优秀"
    elif score >= 60:
        grade = "🟡 良好"
    elif score >= 40:
        grade = "🟠 一般"
    else:
        grade = "🔴 需修复"
    
    print(f"  综合评分: {score}/{max_score} ({grade})")
    
    # 问题清单
    issues = []
    if data['chapters'] < 3:
        issues.append("章节不足（建议≥3篇）")
    if data['pending'] > 0:
        issues.append(f"有待确认提案 {data['pending']} 条需人工处理")
    if data['debts_open'] > 10:
        issues.append(f"质量债务过多（{data['debts_open']}条，建议≤10）")
    shallow = [d for d in depths if d['level'] == '简要']
    if shallow:
        issues.append(f"角色深度不足（{len(shallow)}个简要档）")
    
    if issues:
        print("\n  ⚠️ 待处理事项：")
        for i in issues:
            print(f"    • {i}")
    else:
        print("\n  ✅ 无待处理事项")
    
    print("\n" + "=" * 60)
    print("✅ 自检完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
