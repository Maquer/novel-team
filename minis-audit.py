#!/usr/bin/env python3
# Version: 0.1.0
"""
Minis 全量量化评分引擎 v1.0
评分维度：Skills / Shared Tools / Architecture / Second Brain / Loss Resilience / Integration
每个维度 0-100 分，最终综合分 + 升级迭代建议
"""

import logging

logger = logging.getLogger(__name__)
import os, json, re, subprocess, datetime, sys
from pathlib import Path

BASE = Path("/var/minis")
SHARED = BASE / "shared"
SKILLS = BASE / "skills"
OBSIDIAN = BASE / "mounts/loong"
MEMORY = BASE / "memory"

SB_MODULES = {
    "obsidian-search.py": "检索引擎",
    "obsidian-sync.sh": "双向同步",
    "obsidian-distill.py": "知识蒸馏",
    "obsidian-graph.py": "知识图谱",
    "obsidian-crossq.py": "交叉验证",
    "obsidian-blindspot.py": "盲区发现",
    "obsidian-tag.py": "标签提取",
    "obsidian-analytics.py": "搜索分析",
    "obsidian-learn.py": "学习轨迹",
    "obsidian-skill-lifecycle.py": "Skill 生命周期",
    "obsidian-error-learn.py": "错误模式学习",
    "second-brain-feedback.py": "反馈层(PEV)",
    "second-brain-dashboard.py": "健康仪表盘",
    "second-brain-train.sh": "训练流水线",
    "second-brain-pulse.sh": "训练脉冲",
    "session-commit.py": "Session 记忆提交",
    "friction-score.py": "摩擦度评分",
    "obsidian-auto-learn.py": "自动学习管道",
    "ctx2skill-duel.py": "红蓝军/回放",
    "tiering.py": "分层内容处理",
    "second-brain-mcp/server.py": "MCP 接口",
    "nuwa-distill.py": "女娲蒸馏集成",
    "skill-registry.py": "Skill 注册表",
    "skill-eval-gate.py": "Skill 评测门禁",
    "skill-migrate.py": "Skill 迁移工具",
}

results = {}
upgrade_plan = []

def score_skill(skills_data):
    """维度1: Skills 质量 (权重 20%)"""
    scores = []
    issues = []
    for skill_name, meta in skills_data.items():
        sk_dir = SKILLS / skill_name
        s = 0
        # 1. Eval Gate 评分 (30pt)
        gate = meta.get("eval_gate", 0)
        s += gate * 0.30

        # 2. 成熟度等级 (20pt)
        maturity_map = {"L0": 0, "L1": 15, "L2": 20, "L3": 30, "L4": 45, "L5": 60}
        mat = meta.get("maturity", "L0")
        s += maturity_map.get(mat, 0)

        # 3. 测试覆盖 (20pt)
        has_tests = meta.get("has_tests", False)
        s += 20 if has_tests else 0

        # 4. 文档完整度 (20pt)
        has_meta = meta.get("has_meta", False)
        has_changelog = meta.get("has_changelog", False)
        has_examples = False
        examples_dir = sk_dir / "examples"
        if examples_dir.exists() and list(examples_dir.iterdir()):
            has_examples = True
        doc_score = (20 if has_meta else 0) + (15 if has_changelog else 0) + (15 if has_examples else 0)
        s += min(20, doc_score)

        # 5. 集成度 (10pt) - 是否被其他工具引用
        integration = 0
        if meta.get("maturity", "L0") in ("L2", "L3", "L4", "L5"):
            integration = 10
        s += integration

        scores.append(s)
        if s < 60:
            issues.append(f"{skill_name}: {s:.0f}分 (Gate={gate}, 成熟度={mat}, 测试={has_tests})")

    total = sum(scores) / len(scores) if scores else 0
    return {
        "score": round(total, 1),
        "skills_scored": len(scores),
        "avg_gate": round(sum(meta.get("eval_gate", 0) for meta in skills_data.values()) / len(skills_data), 1) if skills_data else 0,
        "avg_maturity": sum(maturity_map.get(meta.get("maturity","L0"),0) for meta in skills_data.values()) / len(skills_data) / 60 * 100 if skills_data else 0,
        "issues": issues[:5]
    }

def score_shared_tools():
    """维度2: Shared Tools 质量 (权重 20%)"""
    py_files = list(SHARED.glob("*.py"))
    sh_files = list(SHARED.glob("*.sh"))
    js_files = list(SHARED.glob("*.js"))
    all_scripts = py_files + sh_files + js_files

    scores = []
    issues = []

    for f in all_scripts:
        if f.name.startswith("."):
            continue
        s = 0
        content = f.read_text(errors="ignore")
        lines = len(content.splitlines())

        # 1. 代码规模 (15pt) - 太短可能不完整，太长可能臃肿
        if lines >= 200:
            s += 15
        elif lines >= 100:
            s += 12
        elif lines >= 50:
            s += 8
        else:
            s += 5

        # 2. 文档/docstring (15pt)
        doc_ratio = content.count('"""') / max(lines, 1)
        if doc_ratio > 0.02:
            s += 15
        elif doc_ratio > 0.01:
            s += 10
        elif "#" in content[:500]:
            s += 5
        else:
            s += 0

        # 3. 错误处理 (15pt)
        try_count = content.count("try:")
        if try_count >= 3:
            s += 15
        elif try_count >= 1:
            s += 10
        else:
            s += 0

        # 4. 模块化/可配置 (15pt)
        if "argparse" in content or "click" in content or "--help" in content:
            s += 10
        if "config" in content.lower() or "CONFIG" in content:
            s += 5
        if "def " in content:
            s += min(10, content.count("def ") * 0.5)

        # 5. 集成度 (20pt) - 是否被其他工具调用
        integrated = False
        for other in all_scripts:
            if other == f:
                continue
            other_content = other.read_text(errors="ignore")
            if f.name in other_content or f.stem in other_content:
                integrated = True
                break
        s += 20 if integrated else 0

        # 6. 生产就绪 (20pt)
        has_main = ("if __name__" in content) or ("#!/bin/bash" in content)
        has_exit = ("sys.exit" in content) or "exit 0" in content
        has_logging = ("logging" in content) or ("log" in content and "print" in content)
        prod = (10 if has_main else 0) + (5 if has_exit else 0) + (5 if has_logging else 0)
        s += min(20, prod)

        scores.append(min(100, s))
        if s < 60:
            issues.append(f"{f.name}: {s:.0f}分 (L={lines})")

    return {
        "score": round(sum(scores)/len(scores), 1) if scores else 0,
        "tools_count": len(scores),
        "avg_lines": round(sum(len(f.read_text(errors="ignore").splitlines()) for f in all_scripts if not f.name.startswith(".")) / max(len(scores),1), 0),
        "issues": issues[:5]
    }

def score_architecture():
    """维度3: 架构治理 (权重 15%)"""
    s = 0
    issues = []

    # 1. PARA 结构完整性 (25pt)
    para_dirs = ["00-Inbox", "01-Projects", "02-Areas", "03-Resources", "04-Archives"]
    para_count = sum(1 for d in para_dirs if (OBSIDIAN / d).exists())
    s += para_count / 5 * 25
    if para_count < 5:
        missing = [d for d in para_dirs if not (OBSIDIAN / d).exists()]
        issues.append(f"PARA 缺失: {missing}")

    # 2. MOC 中枢 (10pt)
    if (OBSIDIAN / "MOC.md").exists():
        s += 10
    else:
        issues.append("缺少 MOC.md 中枢")

    # 3. GLOBAL.md 质量 (20pt)
    gm_path = MEMORY / "GLOBAL.md"
    if gm_path.exists():
        content = gm_path.read_text(errors="ignore")
        lines = len(content.splitlines())
        has_sections = content.count("##")
        has_tables = content.count("|")
        s += min(20, (lines/200)*10 + has_sections*1 + has_tables*0.2)
    else:
        issues.append("缺少 GLOBAL.md")

    # 4. SOUL.md 存在 (5pt)
    if (MEMORY / "SOUL.md").exists():
        s += 5

    # 5. 决策记录 (15pt)
    if gm_path.exists():
        content = gm_path.read_text(errors="ignore")
        decisions = content.count("决策记录") + content.count("| 2026-")
        s += min(15, decisions * 2)

    # 6. 项目看板 (15pt)
    if gm_path.exists():
        content = gm_path.read_text(errors="ignore")
        project_rows = content.count("| ") - 20  # rough count
        s += min(15, project_rows * 0.5)

    # 7. 工具链文档 (10pt)
    readme = SHARED / "memory-tools-README.md"
    if readme.exists():
        s += min(10, len(readme.read_text(errors="ignore").splitlines()) / 100 * 10)

    return {
        "score": min(100, round(s, 1)),
        "para_dirs": para_count,
        "global_lines": len(gm_path.read_text(errors="ignore").splitlines()) if gm_path.exists() else 0,
        "issues": issues[:5]
    }

def score_memory_system():
    """维度4: 记忆体系 (权重 10%)"""
    s = 0
    issues = []

    # 1. Daily logs 数量
    logs = sorted(MEMORY.glob("*.md"))
    daily_logs = [l for l in logs if re.match(r"\d{4}-\d{2}-\d{2}\.md", l.name)]
    s += min(20, len(daily_logs) * 1.5)

    # 2. L2 周报
    l2 = MEMORY / "L2-weekly-summaries.md"
    if l2.exists() and l2.stat().st_size > 500:
        s += 15
    else:
        issues.append("L2 周报缺失或过小")

    # 3. L3 知识图谱
    l3 = MEMORY / "L3-knowledge-graph.md"
    if l3.exists():
        content = l3.read_text(errors="ignore")
        s += min(20, len(content.splitlines()) / 50 * 20)
        if len(content.splitlines()) < 30:
            issues.append("L3 知识图谱内容过少")
    else:
        issues.append("缺少 L3 知识图谱")
        s -= 5

    # 4. GLOBAL.md 存在
    if (MEMORY / "GLOBAL.md").exists():
        s += 10
    else:
        issues.append("缺少 GLOBAL.md")
        s -= 5

    # 5. SOUL.md
    if (MEMORY / "SOUL.md").exists():
        s += 5

    # 6. 记忆工具链
    mem_tools = ["memory-l2-rollup.py", "memory-knowledge-link.py", "minis-capture.sh", "minis-dashboard.sh"]
    for t in mem_tools:
        if (SHARED / t).exists():
            s += 3

    return {
        "score": min(100, max(0, round(s, 1))),
        "daily_logs": len(daily_logs),
        "issues": issues[:5]
    }

def score_second_brain():
    """维度5: 第二大脑 (权重 15%)"""
    s = 0
    issues = []

    present = 0
    for f, desc in SB_MODULES.items():
        path = SHARED / f
        if path.exists():
            present += 1
            content = path.read_text(errors="ignore")
            lines = len(content.splitlines())
            if lines > 100:
                s += 3.5
            elif lines > 50:
                s += 2.5
            else:
                s += 1.5
        else:
            issues.append(f"缺失: {f} ({desc})")

    # 知识存储
    ks = SHARED / ".knowledge-store.json"
    if ks.exists():
        data = json.loads(ks.read_text())
        cards = data.get("cards", [])
        s += min(10, len(cards) * 0.3)
    else:
        issues.append("知识存储缺失")

    # MCP server 注册
    try:
        r = subprocess.run(["minis-mcp-cli", "ping", "second-brain"], capture_output=True, text=True, timeout=5)
        if "ok" in r.stdout:
            s += 5
    except:
        pass

    total_possible = len(SB_MODULES)
    coverage = present / total_possible * 100
    return {
        "score": min(100, round(s, 1)),
        "modules_present": present,
        "modules_total": total_possible,
        "coverage": round(coverage, 1),
        "issues": issues[:5]
    }

def score_loss_resilience():
    """维度6: 丢失韧性 (权重 10%)"""
    s = 0
    issues = []

    # 1. 核心工具是否在 shared/ (不依赖 workspace)
    critical_in_shared = [
        "obsidian-search.py", "obsidian-sync.sh", "obsidian-distill.py",
        "second-brain-train.sh", "second-brain-dashboard.py",
        "skill-registry.py", "skill-eval-gate.py",
        "friction-score.py", "obsidian-auto-learn.py",
    ]
    present = sum(1 for f in critical_in_shared if (SHARED / f).exists())
    s += present / len(critical_in_shared) * 30
    if present < len(critical_in_shared):
        missing = [f for f in critical_in_shared if not (SHARED / f).exists()]
        issues.append(f"核心工具未迁移到 shared/: {missing}")

    # 2. workspace 备份脚本
    if (SHARED / "workspace-backup.sh").exists():
        s += 10
    else:
        issues.append("缺少 workspace 备份脚本")

    # 3. 全局配置 (GLOBAL.md 在 memory/ 不受 workspace 丢失影响)
    if (MEMORY / "GLOBAL.md").exists():
        s += 10

    # 4. knowledge-store 持久化
    if (SHARED / ".knowledge-store.json").exists():
        s += 10

    # 5. 决策记录在 GLOBAL.md (不受丢失影响)
    gm = MEMORY / "GLOBAL.md"
    if gm.exists():
        content = gm.read_text(errors="ignore")
        if "决策记录" in content:
            s += 10

    # 6. Obsidian 归档作为备份层
    obsidian_backup = OBSIDIAN / "04-Archives"
    if obsidian_backup.exists():
        files = list(obsidian_backup.rglob("*.md"))
        s += min(10, len(files) * 0.1)

    # 7. 项目看板记录丢失历史
    if gm.exists():
        content = gm.read_text(errors="ignore")
        if "丢失" in content or "workspace" in content.lower():
            s += 10

    return {
        "score": min(100, round(s, 1)),
        "critical_in_shared": present,
        "critical_total": len(critical_in_shared),
        "issues": issues[:5]
    }

def score_integration():
    """维度7: 工具间集成度 (权重 10%)"""
    s = 0

    # 1. 脚本间相互引用
    py_files = list(SHARED.glob("*.py")) + list(SHARED.glob("*.sh"))
    refs = 0
    total = 0
    for f in py_files:
        if f.name.startswith("."):
            continue
        total += 1
        content = f.read_text(errors="ignore")
        for other in py_files:
            if other == f or other.name.startswith("."):
                continue
            if other.name in content or other.stem in content:
                refs += 1
                break

    if total > 0:
        s += min(25, (refs / total) * 25)

    # 2. 训练流水线是否集成所有模块
    train = SHARED / "second-brain-train.sh"
    if train.exists():
        content = train.read_text(errors="ignore")
        modules_found = sum(1 for m in ["distill", "graph", "crossq", "blindspot", "tag",
                                          "analytics", "learn", "auto-learn", "dashboard",
                                          "feedback", "error-learn", "skill-lifecycle",
                                          "pulse", "session-commit"] if m in content)
        s += min(25, modules_found * 2)
    else:
        s -= 5

    # 3. MCP 接口
    mcp = SHARED / "second-brain-mcp"
    if mcp.exists():
        s += 15

    # 4. 知识存储通用格式
    ks = SHARED / ".knowledge-store.json"
    if ks.exists():
        data = json.loads(ks.read_text())
        cards = data.get("cards", [])
        types = set()
        for card in cards:
            if isinstance(card, dict):
                types.add(card.get("type","?"))
        s += min(15, len(types) * 3)

    # 5. 统一 CLI 入口
    aliases = SHARED / "minis-aliases.sh"
    if aliases.exists():
        s += 10

    # 6. 记忆工具 README
    readme = SHARED / "memory-tools-README.md"
    if readme.exists():
        s += 10

    return {
        "score": min(100, round(s, 1)),
        "tool_refs": refs,
        "tools": total,
        "issues": []
    }

# ============ MAIN ============
print("=" * 60)
print("  Minis 全量量化评分报告")
print(f"  时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("=" * 60)

# --- 维度1: Skills ---
# Load eval gate scores from cached JSON
eval_scores = {}
eval_file = SHARED / ".eval-gate-scores.json"
if eval_file.exists():
    eval_scores = json.loads(eval_file.read_text())

skills_data = {}
for d in sorted(SKILLS.iterdir()):
    if d.is_dir():
        name = d.name
        meta = {"eval_gate": 0, "maturity": "L0", "has_tests": False, "has_meta": False, "has_changelog": False}
        for f in d.iterdir():
            if f.name == "skill.meta.json":
                meta["has_meta"] = True
                try:
                    mj = json.loads(f.read_text())
                    if mj.get("last_eval") and mj["last_eval"].get("score"):
                        meta["eval_gate"] = int(mj["last_eval"]["score"])
                    if mj.get("maturity"):
                        meta["maturity"] = mj["maturity"]
                except:
                    pass
            elif f.name == "CHANGELOG.md":
                meta["has_changelog"] = True
            elif f.name == "tests":
                meta["has_tests"] = len(list(f.iterdir())) > 0 if f.is_dir() else False
        # Priority 1: eval gate scores from .eval-gate-scores.json
        if name in eval_scores:
            es = eval_scores[name]
            meta["eval_gate"] = es.get("score", meta["eval_gate"])
        # Priority 2: skill-registry scores
        if meta["eval_gate"] == 0:
            try:
                reg = json.loads((SHARED / ".skill-registry.json").read_text())
                sk_reg = reg.get("skills", {}).get(name, {})
                # Registry computes score inline
                components = sk_reg.get("components", {})
                has_all = all(k in components for k in ["SKILL.md", "skill.meta.json", "CHANGELOG.md"])
                has_tests_dir = "tests" in components
                has_examples = "examples" in components
                registry_score = 0
                if has_all: registry_score += 40
                if has_tests_dir: registry_score += 20
                if has_examples: registry_score += 15
                registry_score += 25  # base
                meta["eval_gate"] = min(100, registry_score)
                # maturity from registry
                mat = sk_reg.get("maturity", "L1")
                if mat:
                    meta["maturity"] = mat
            except:
                pass
        # Priority 2: SKILL.md frontmatter
        sk = d / "SKILL.md"
        if sk.exists():
            content = sk.read_text(errors="ignore")
            if meta["eval_gate"] == 0 and "eval_gate" in content:
                m = re.search(r'eval_gate:\s*(\d+)', content)
                if m:
                    meta["eval_gate"] = int(m.group(1))
            if meta["maturity"] == "L0" and "maturity" in content:
                m = re.search(r'maturity:\s*(L\d+)', content)
                if m:
                    meta["maturity"] = m.group(1)
        skills_data[name] = meta

r1 = score_skill(skills_data)
results["skills"] = r1
print(f"\n📦 维度1: Skills 质量 (权重 20%) → {r1['score']}/100")
print(f"   评分数: {r1['skills_scored']}, 平均 Gate: {r1['avg_gate']}")
for sk, meta in sorted(skills_data.items()):
    bar = "█" * int(meta.get("eval_gate", 0) / 10) + "░" * (10 - int(meta.get("eval_gate", 0) / 10))
    print(f"   {sk:25s}  Gate={meta.get('eval_gate', 0):3d} 成熟度={meta.get('maturity','?'):3s} [{bar}]")
if r1["issues"]:
    for i in r1["issues"][:3]:
        print(f"   ⚠️  {i}")

# --- 维度2: Shared Tools ---
r2 = score_shared_tools()
results["shared_tools"] = r2
print(f"\n🔧 维度2: Shared Tools (权重 20%) → {r2['score']}/100")
print(f"   工具数: {r2['tools_count']}, 平均行数: {r2['avg_lines']}")

# --- 维度3: Architecture ---
r3 = score_architecture()
results["architecture"] = r3
print(f"\n🏗️  维度3: 架构治理 (权重 15%) → {r3['score']}/100")
print(f"   PARA 目录: {r3['para_dirs']}/5, GLOBAL.md: {r3['global_lines']} 行")
if r3["issues"]:
    for i in r3["issues"][:3]:
        print(f"   ⚠️  {i}")

# --- 维度4: Memory ---
r4 = score_memory_system()
results["memory"] = r4
print(f"\n🧠 维度4: 记忆体系 (权重 10%) → {r4['score']}/100")
print(f"   日志: {r4['daily_logs']} 篇")
if r4["issues"]:
    for i in r4["issues"][:3]:
        print(f"   ⚠️  {i}")

# --- 维度5: Second Brain ---
r5 = score_second_brain()
results["second_brain"] = r5
print(f"\n🤖 维度5: 第二大脑 (权重 15%) → {r5['score']}/100")
print(f"   模块: {r5['modules_present']}/{r5['modules_total']} ({r5['coverage']}%)")
if r5["issues"]:
    for i in r5["issues"][:3]:
        print(f"   ⚠️  {i}")

# --- 维度6: Loss Resilience ---
r6 = score_loss_resilience()
results["loss_resilience"] = r6
print(f"\n🛡️  维度6: 丢失韧性 (权重 10%) → {r6['score']}/100")
print(f"   核心工具在 shared/: {r6['critical_in_shared']}/{r6['critical_total']}")
if r6["issues"]:
    for i in r6["issues"][:3]:
        print(f"   ⚠️  {i}")

# --- 维度7: Integration ---
r7 = score_integration()
results["integration"] = r7
print(f"\n🔗 维度7: 工具集成度 (权重 10%) → {r7['score']}/100")

# === 综合分 ===
weights = {
    "skills": 0.20,
    "shared_tools": 0.20,
    "architecture": 0.15,
    "memory": 0.10,
    "second_brain": 0.15,
    "loss_resilience": 0.10,
    "integration": 0.10,
}
total_score = sum(results[k]["score"] * weights[k] for k in weights)

print(f"\n{'='*60}")
print(f"  📊 综合评分: {total_score:.1f}/100")
grade = "S" if total_score >= 90 else "A" if total_score >= 80 else "B" if total_score >= 70 else "C" if total_score >= 60 else "D"
print(f"  等级: {grade}")
print(f"{'='*60}")

# === 维度雷达 ===
print(f"\n  维度详情:")
print(f"  {'维度':15s} {'分数':>6s} {'权重':>6s} {'加权':>6s} {'评级':>5s}")
print(f"  {'-'*40}")
for k, w in weights.items():
    s = results[k]["score"]
    weighted = s * w
    g = "S" if s >= 90 else "A" if s >= 80 else "B" if s >= 70 else "C" if s >= 60 else "D"
    bar_len = int(s / 10)
    bar = "█" * bar_len + "░" * (10 - bar_len)
    print(f"  {k:15s} {s:5.1f}  {w*100:4.0f}%  {weighted:5.1f}  {g:4s} [{bar}]")

# === 升级迭代建议 ===
print(f"\n{'='*60}")
print(f"  🔧 量化升级迭代方案")
print(f"{'='*60}")

priority = []

for k, w in weights.items():
    r = results[k]
    gap = 100 - r["score"]
    priority_score = gap * w
    priority.append((k, r["score"], gap, w, priority_score, r.get("issues", [])))

priority.sort(key=lambda x: -x[4])

rank = 1
for k, score, gap, w, ps, issues in priority:
    dim_name = {"skills":"Skills", "shared_tools":"Shared Tools", "architecture":"架构治理",
                "memory":"记忆体系", "second_brain":"第二大脑", "loss_resilience":"丢失韧性",
                "integration":"工具集成"}[k]
    print(f"\n  #{rank} {dim_name} (当前 {score:.0f}/100, 缺口 {gap:.0f}pt × 权重{w*100:.0f}% = 优先级 {ps:.1f})")
    if score >= 80:
        print(f"     ✅ 已达到 A 级以上，维护性迭代")
    elif score >= 60:
        print(f"     🟡 中等水平，有明确提升空间")
    else:
        print(f"     🔴 薄弱维度，需重点投入")

    # 具体建议
    if k == "skills":
        low_skills = [n for n,m in skills_data.items() if m.get("eval_gate",0) < 80]
        if low_skills:
            print(f"     → 优先提升: {', '.join(low_skills)} (Gate < 80)")
        maturity_low = [n for n,m in skills_data.items() if m.get("maturity","L0") in ("L0","L1")]
        if maturity_low:
            print(f"     → 成熟度升级: {', '.join(maturity_low)} (L0/L1 → L2+)")
        print(f"     → 所有 Skill 补全 examples/ 目录")
        print(f"     → 对 L2 以下 Skill 运行 Eval Gate 逐条修复")

    elif k == "shared_tools":
        print(f"     → 对 < 60 分的工具运行自动化代码质量修复")
        print(f"     → 统一 CLI 入口：所有工具支持 --help / --version")
        print(f"     → 增加 logging 模块替代 print")
        print(f"     → 增加 argparse 参数解析")

    elif k == "architecture":
        if issues:
            for i in issues:
                print(f"     → 修复: {i}")
        print(f"     → 补齐 PARA 缺失目录")
        print(f"     → GLOBAL.md 结构化升级：添加 L2/L3 交叉引用")
        print(f"     → 项目看板超过 20 项时拆到独立文件")

    elif k == "memory":
        print(f"     → 日志从 {r4['daily_logs']} 篇增长，保持每日写入")
        print(f"     → L3 知识图谱扩展：跨话题关联 ≥5 条")
        print(f"     → L2 周报自动化：memory-l2-rollup.py 定期运行")

    elif k == "second_brain":
        missing = [f for f,_ in SB_MODULES.items() if not (SHARED / f).exists()]
        if missing:
            print(f"     → 补齐缺失模块: {missing}")
        print(f"     → 模块间集成度提升：训练流水线覆盖所有模块")
        cards = json.loads((SHARED/'.knowledge-store.json').read_text()).get("cards", [])
        print(f"     → 知识存储类型扩展：当前 {len(cards)} 条 → 目标 100+ 条")

    elif k == "loss_resilience":
        print(f"     → 核心工具迁移完成度: {r6['critical_in_shared']}/{r6['critical_total']}")
        if r6['critical_in_shared'] < r6['critical_total']:
            print(f"     → 剩余工具迁移到 shared/: {[f for f in critical_in_shared if not (SHARED/f).exists()]}")
        print(f"     → 建立自动化备份：Apple Shortcuts 每日备份 shared/ + memory/")
        print(f"     → 关键文件双写：shared/ + Obsidian 04-Archives/")

    elif k == "integration":
        print(f"     → 工具引用率: {r7['tool_refs']}/{r7['tools']}")
        print(f"     → 建立统一 CLI 入口 minis-cli (bash wrapper)")
        print(f"     → 增加 minis-aliases.sh 覆盖所有工具")
        print(f"     → 知识存储格式标准化：统一 card schema")

    rank += 1

# === 输出 JSON ===
output = {
    "timestamp": datetime.datetime.now().isoformat(),
    "total_score": round(total_score, 1),
    "grade": grade,
    "dimensions": {k: {"score": results[k]["score"], "weight": weights[k], "weighted": round(results[k]["score"] * weights[k], 1)} for k in weights},
    "priorities": [(k, round(ps, 1)) for k, _, _, _, ps, _ in priority],
}
out_path = SHARED / ".minis-audit-report.json"
out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
print(f"\n📁 详细报告已保存: {out_path}")
