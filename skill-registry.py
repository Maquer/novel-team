#!/usr/bin/env python3
# Version: 0.1.0
"""
skill-registry.py — Minis Skill 版本化注册表 v2

v2 变更：
- 成熟度从"文件存在"改为"流程能力"模型（对齐 SOTA AI 文章五级定义）
- 评分改门禁式（error 一票否决，warning/info 参考）
- 增加 trace 基础设施需求检测

对齐 SOTA AI 文章定义：
  L1 = 手工技能（有 SKILL.md + frontmatter）
  L2 = Eval-gated（有触发边界测试 + 失败模式编码 + 反例 + 检查点）
  L3 = Trace-mined（连接 Trace Lake，从真实运行中生成候选）
  L4 = Skill Foundry（外部资源挖掘 + 自动生成 + 版本化）
  L5 = Self-modifying（agent 自改代码 + benchmark 验证）

用法:
  python3 skill-registry.py scan
  python3 skill-registry.py list
  python3 skill-registry.py show <name>
  python3 skill-registry.py status
  python3 skill-registry.py validate
  python3 skill-registry.py json
  python3 skill-registry.py export
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REGISTRY_PATH = "/var/minis/shared/.skill-registry.json"
SKILLS_DIR = "/var/minis/skills"

MATURITY_LABELS = {
    "L1": "手工技能 — 有 SKILL.md + frontmatter",
    "L2": "Eval-gated — 有触发边界测试 + 失败模式 + 反例 + 检查点",
    "L3": "Trace-mined — 连接 Trace Lake，从真实运行中生成候选",
    "L4": "Skill Foundry — 外部资源挖掘 + 自动生成 + 版本化",
    "L5": "Self-modifying — agent 自改代码 + benchmark 验证",
}

# 当前 Minis 基础设施状态（决定最高可达成熟度）
INFRA_CAPABILITY = {
    "trace_lake": False,       # 无 Trace Lake 基础设施
    "sandbox_execution": False, # 无沙箱执行环境
    "candidate_generator": False, # 无候选生成器
    "skill_foundry": False,     # 无外部资源挖掘
    "self_modifying": False,    # 无自改代码机制
}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


REGISTRY_STALE_HOURS = 24  # 缓存超过此时长视为陈旧，读时警告


def _warn_if_stale(reg):
    """读缓存时提示陈旧度：过期报告会让治理决策基于不存在的 Skill。"""
    try:
        ls = reg.get("last_scan")
        if not ls:
            return
        dt = datetime.fromisoformat(str(ls).replace("Z", "+00:00"))
        age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        if age_h > REGISTRY_STALE_HOURS:
            print(f"⚠️  注册表缓存已 {age_h/24:.1f} 天未刷新（最后扫描 {str(ls)[:19]}），"
                  f"可能与磁盘不符 → python3 skill-registry.py scan", file=sys.stderr)
    except Exception:
        pass


def _load_registry(warn=True):
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
                reg = json.load(f)
            if warn:
                _warn_if_stale(reg)
            return reg
        except Exception:
            pass
    return {"skills": {}, "last_scan": None, "version": 2}


SNAPSHOT_PATH = "/var/minis/shared/.skill-snapshot.json"
HISTORY_PATH = "/var/minis/shared/.skill-history.jsonl"
MAX_SNAPSHOT_FILES = 10  # 只保留最近 10 份快照文件

# ===== Snapshot + History =====

def _load_snapshot():
    if os.path.exists(SNAPSHOT_PATH):
        try:
            with open(SNAPSHOT_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _compute_snapshot():
    """Compute current snapshot: per-skill hashes + component inventory."""
    snapshot = {
        "timestamp": _now_iso(),
        "skills": {},
    }
    if not os.path.isdir(SKILLS_DIR):
        return snapshot
    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if not os.path.isdir(skill_dir):
            continue
        skill_snap = {"path": skill_dir, "components": {}}
        for f in os.listdir(skill_dir):
            fp = os.path.join(skill_dir, f)
            if os.path.isfile(fp):
                h = _compute_hash(fp)
                skill_snap["components"][f] = {"type": "file", "hash": h, "size": os.path.getsize(fp)}
            elif os.path.isdir(fp):
                skill_snap["components"][f] = {"type": "dir"}
        # SKILL.md 独立追踪
        skill_md = os.path.join(skill_dir, "SKILL.md")
        if os.path.exists(skill_md):
            skill_snap["skill_md_hash"] = _compute_hash(skill_md)
            skill_snap["skill_md_size"] = os.path.getsize(skill_md)
            mtime = os.path.getmtime(skill_md)
            skill_snap["skill_md_mtime"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
        snapshot["skills"][entry] = skill_snap
    snapshot["skill_count"] = len(snapshot["skills"])
    return snapshot


def _save_snapshot(snap):
    """Save snapshot file with rotation: keep MAX_SNAPSHOT_FILES latest."""
    os.makedirs(os.path.dirname(SNAPSHOT_PATH) or '.', exist_ok=True)
    # Rotate old snapshots
    if os.path.exists(SNAPSHOT_PATH):
        base = os.path.join(os.path.dirname(SNAPSHOT_PATH) or '.', ".skill-snapshot")
        existing = sorted([f for f in os.listdir(os.path.dirname(SNAPSHOT_PATH) or '.') if f.startswith(".skill-snapshot-") and f.endswith(".json")])
        for old in existing[:-MAX_SNAPSHOT_FILES + 1]:
            try:
                os.remove(os.path.join(os.path.dirname(SNAPSHOT_PATH) or '.', old))
            except OSError:
                pass
        # Archive current snapshot before overwriting
        archive_name = f".skill-snapshot-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
        archive_path = os.path.join(os.path.dirname(SNAPSHOT_PATH) or '.', archive_name)
        try:
            with open(SNAPSHOT_PATH, 'r', encoding='utf-8') as src:
                with open(archive_path, 'w', encoding='utf-8') as dst:
                    dst.write(src.read())
        except Exception:
            pass
    with open(SNAPSHOT_PATH, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)


def _diff_snapshots(old, new):
    """Compare two snapshots, return list of change events."""
    events = []
    if old is None:
        # First-ever snapshot: no changes to compare
        return events
    old_skills = old.get("skills", {})
    new_skills = new.get("skills", {})
    old_names = set(old_skills.keys())
    new_names = set(new_skills.keys())

    for name in sorted(new_names - old_names):
        events.append({"event": "skill_added", "name": name, "timestamp": new["timestamp"]})
    for name in sorted(old_names - new_names):
        events.append({"event": "skill_removed", "name": name, "timestamp": new["timestamp"]})
    for name in sorted(old_names & new_names):
        old_s = old_skills[name]
        new_s = new_skills[name]
        # SKILL.md content changed?
        if old_s.get("skill_md_hash") != new_s.get("skill_md_hash"):
            events.append({
                "event": "skill_modified",
                "name": name,
                "field": "SKILL.md",
                "old_hash": old_s.get("skill_md_hash"),
                "new_hash": new_s.get("skill_md_hash"),
                "timestamp": new["timestamp"],
            })
        # Component inventory changed?
        old_comps = set(old_s.get("components", {}).keys())
        new_comps = set(new_s.get("components", {}).keys())
        for comp in sorted(new_comps - old_comps):
            events.append({
                "event": "component_added",
                "name": name,
                "component": comp,
                "timestamp": new["timestamp"],
            })
        for comp in sorted(old_comps - new_comps):
            events.append({
                "event": "component_removed",
                "name": name,
                "component": comp,
                "timestamp": new["timestamp"],
            })

    return events


def _log_history(events):
    """Append change events to JSONL history."""
    if not events:
        return
    os.makedirs(os.path.dirname(HISTORY_PATH) or '.', exist_ok=True)
    with open(HISTORY_PATH, 'a', encoding='utf-8') as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def snapshot_cmd():
    snap = _load_snapshot()
    if snap is None:
        return {"error": "No snapshot available. Run 'scan' first."}
    summary = {
        "timestamp": snap["timestamp"],
        "skill_count": snap["skill_count"],
        "skills": {},
    }
    for name, s in snap.get("skills", {}).items():
        summary["skills"][name] = {
            "skill_md_hash": s.get("skill_md_hash"),
            "skill_md_size": s.get("skill_md_size"),
            "components": list(s.get("components", {}).keys()),
        }
    return summary


def history_cmd(limit=20):
    if not os.path.exists(HISTORY_PATH):
        return []
    with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    events = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events[-limit:] if len(events) > limit else events


# ===== 注册表读写 =====

def _save_registry(reg):
    os.makedirs(os.path.dirname(REGISTRY_PATH) or '.', exist_ok=True)
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def _parse_frontmatter(text):
    """解析 YAML frontmatter，支持块标量 | > 及 - / + 折叠变体。

    旧版逐行 split(':')，把 `description: >-` 当成值 ">$-$"、正文全部丢弃：
    实测 23 个 Skill 里 10 个 description 解析长度 ≤2，
    连带 desc_length 门禁与 skill-router 的 TF-IDF 检索输入全部失真。
    """
    meta = {}
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?', text, re.DOTALL)
    if not m:
        return meta
    lines = m.group(1).split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        if ':' not in line or line[:1].isspace():
            i += 1
            continue
        key, val = line.split(':', 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if val and val[0] in ('|', '>') and val[1:].strip() in ('', '-', '+'):
            fold = val[0] == '>'
            parts = []
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and not nxt[:1].isspace():
                    break
                parts.append(nxt.strip())
                i += 1
            while parts and not parts[-1]:
                parts.pop()
            val = (' ' if fold else '\n').join(
                p for p in parts if p) if fold else '\n'.join(parts)
            meta[key] = val.strip()
            continue
        meta[key] = val
        i += 1
    return meta


def _compute_hash(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except Exception:
        return None


# tests 目录里被视为"真实用例"的字段名。只有目录没有这些 = 空壳。
TEST_CASE_KEYS = ("explicit_triggers", "implicit_triggers", "negative_triggers",
                  "regression", "trigger_queries", "tests", "cases", "queries")


def _count_test_cases(skill_dir):
    """统计 tests/ 下的真实用例数。

    背景：skill-migrate.py 会生成 tests/README.json，四类 triggers 全为空数组。
    旧逻辑只判断目录存在就加分，导致"有测试"的 14 个 Skill 里 13 个实为零用例空壳。
    """
    tests_dir = os.path.join(skill_dir, "tests")
    if not os.path.isdir(tests_dir):
        return None  # 无 tests 目录
    cases = 0
    for root, _dirs, files in os.walk(tests_dir):
        for fn in files:
            fp = os.path.join(root, fn)
            if fn.endswith(".py"):
                cases += 1
                continue
            if not fn.endswith((".json", ".yaml", ".yml")):
                continue
            try:
                data = json.loads(Path(fp).read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, list):
                cases += len(data)
            elif isinstance(data, dict):
                for key in TEST_CASE_KEYS:
                    val = data.get(key)
                    if isinstance(val, list):
                        cases += len(val)
    return cases


def _scan_single_skill(skill_dir):
    name = os.path.basename(skill_dir)
    skill_path = os.path.join(skill_dir, "SKILL.md")
    entry = {"name": name, "path": skill_dir, "exists": os.path.isdir(skill_dir)}

    if not entry["exists"]:
        return entry

    try:
        mtime = os.path.getmtime(skill_dir)
        entry["last_modified"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except Exception:
        pass

    entry["components"] = {}
    for f in os.listdir(skill_dir):
        fp = os.path.join(skill_dir, f)
        if os.path.isfile(fp):
            entry["components"][f] = {"type": "file", "size": os.path.getsize(fp)}
        elif os.path.isdir(fp):
            entry["components"][f] = {"type": "dir"}

    # 真实测试用例数（区分"有 tests 目录"与"有测试内容"）
    entry["test_cases"] = _count_test_cases(skill_dir)

    entry["skill_md"] = {}
    if os.path.exists(skill_path):
        try:
            text = Path(skill_path).read_text(encoding='utf-8')
            lines = text.split('\n')
            entry["size_bytes"] = os.path.getsize(skill_path)
            entry["lines"] = len(lines)
            entry["char_count"] = len(text)

            meta = _parse_frontmatter(text)
            entry["name_frontmatter"] = meta.get("name", "")
            entry["description"] = meta.get("description", "")
            entry["frontmatter_keys"] = list(meta.keys())
            entry["desc_length"] = len(meta.get("description", ""))

            # 信号检测
            desc = meta.get("description", "")
            entry["has_triggers"] = bool(re.search(r'(触发|trigger|当|when|use when|提到|say|说)', desc, re.IGNORECASE))
            entry["has_failure_modes"] = bool(re.search(r'(失败|error|错误|fallback|异常|如果.*失败|if.*fail)', text, re.IGNORECASE))
            entry["has_anti_examples"] = bool(re.search(r'(不要|反例|黑名单|do not|never|avoid|不应|禁止)', text, re.IGNORECASE))
            entry["has_checkpoints"] = bool(re.search(r'(CHECKPOINT|检查点|STOP|🛑|暂停|确认)', text, re.IGNORECASE))
            entry["has_steps"] = bool(re.search(r'Phase|Step|阶段|步骤|Phase \d|Step \d', text))
            entry["has_progressive_disclosure"] = bool(re.search(r'(progressive|渐进|按需|metadata|元数据)', text, re.IGNORECASE))
            entry["has_fluff"] = _count_fluff(text) >= 3
            entry["has_ending_fluff"] = _has_ending_fluff(text)
            entry["has_concrete_examples"] = _has_concrete_examples(text)
            entry["content_hash"] = _compute_hash(skill_path)

            # 正/负触发测试检测
            tests_dir = os.path.join(skill_dir, "tests")
            entry["has_explicit_triggers"] = os.path.exists(os.path.join(tests_dir, "explicit-trigger.jsonl"))
            entry["has_negative_triggers"] = os.path.exists(os.path.join(tests_dir, "negative-trigger.jsonl"))
            entry["has_golden_tasks"] = os.path.exists(os.path.join(tests_dir, "golden-task.jsonl"))
            entry["has_regression_tests"] = os.path.exists(os.path.join(tests_dir, "regression.jsonl"))

        except Exception as e:
            entry["parse_error"] = str(e)

    return entry


def _count_fluff(text):
    patterns = [r'\b建议\b', r'可以考虑', r'灵活把握', r'视情况而定', r'根据情况',
                r'灵活应用', r'灵活处理', r'酌情', r'适当.*考虑', r'酌情考虑']
    count = 0
    for p in patterns:
        count += len(re.findall(p, text))
    return count


def _has_ending_fluff(text):
    endings = [r'灵活应用', r'根据情况判断', r'灵活处理', r'灵活变通',
               r'适当调整', r'根据实际需要', r'视具体情况', r'灵活运用']
    for p in endings:
        if re.search(p + r'[。．，,]?\s*$', text):
            return True
    return False


def _has_concrete_examples(text):
    patterns = [r'`[^`]+`', r'\b\d+px\b', r'\b\d+em\b', r'\b\d+%?\b',
                r'```', r'path=', r'`--', r'\bhttps?://']
    for p in patterns:
        if re.search(p, text):
            return True
    return False


# ===== v2 成熟度估算 =====

def _estimate_maturity(data):
    """
    基于流程能力的成熟度模型。
    核心原则：成熟度反映 skill 在自演化闭环中的流程能力，而非文件数量。
    """
    infra = INFRA_CAPABILITY

    # L1: 基础结构 — SKILL.md + frontmatter 完整
    has_md = os.path.exists(os.path.join(data.get("path", ""), "SKILL.md"))
    has_name = "name" in data.get("frontmatter_keys", [])
    has_desc = "description" in data.get("frontmatter_keys", [])
    has_desc_nonempty = data.get("desc_length", 0) > 0

    if has_md and has_name and has_desc and has_desc_nonempty:
        # L2: Eval-gated — 需要触发条件 + 失败模式 + 反例 + 检查点
        quality_signals = sum([
            data.get("has_triggers", False),
            data.get("has_failure_modes", False),
            data.get("has_anti_examples", False),
            data.get("has_checkpoints", False),
        ])
        # 需要至少 3/4 个质量信号 + tests/ 目录存在
        has_tests_dir = "tests" in data.get("components", {})
        if quality_signals >= 3 and has_tests_dir:
            # L3: Trace-mined — 需要 Trace Lake 基础设施
            if infra["trace_lake"]:
                if "skill.meta.json" in data.get("components", {}):
                    # L4: Skill Foundry
                    if infra["skill_foundry"]:
                        return "L4"
                    if data.get("has_explicit_triggers") and data.get("has_negative_triggers"):
                        return "L4"
                    return "L3"
                return "L3"
            return "L2"
        elif quality_signals >= 2:
            return "L2"
        else:
            return "L1"
    return "L0"


# ===== v2 门禁式评分 =====

def _gate_score(data):
    """
    门禁式评分（v2）：
    - error: 一票否决（任何 error → 不通过）
    - warning: 每个扣 10 分
    - info: 每个扣 3 分
    - 满分 100
    """
    errors = 0
    warnings = 0
    infos = 0

    # error 级别：阻塞项
    if not os.path.exists(os.path.join(data.get("path", ""), "SKILL.md")):
        errors += 1
    meta_keys = data.get("frontmatter_keys", [])
    if "name" not in meta_keys:
        errors += 1
    if "description" not in meta_keys:
        errors += 1
    elif data.get("desc_length", 0) == 0:
        errors += 1
    if data.get("desc_length", 0) > 1024:
        warnings += 1

    # warning 级别：建议项
    if not data.get("has_triggers", False):
        warnings += 1
    if not data.get("has_failure_modes", False):
        warnings += 1
    if not data.get("has_anti_examples", False):
        warnings += 1
    if not data.get("has_checkpoints", False):
        warnings += 1
    if not data.get("has_steps", False):
        warnings += 1
    if data.get("has_fluff", False):
        warnings += 1
    if data.get("has_ending_fluff", False):
        warnings += 1

    # info 级别：参考项
    if not data.get("has_progressive_disclosure", False):
        infos += 1
    if not data.get("has_concrete_examples", False):
        infos += 1
    # tests 空壳（目录在但零用例）视同缺失：否则 migrate 生成的空 README.json 就能白拿分
    if "tests" not in data.get("components", {}) or data.get("test_cases") == 0:
        infos += 1
    if "skill.meta.json" not in data.get("components", {}):
        infos += 1
    if "CHANGELOG.md" not in data.get("components", {}):
        infos += 1

    passed = errors == 0
    score = max(0, 100 - warnings * 10 - infos * 3)

    return {
        "passed": passed,
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
    }


def scan():
    if not os.path.isdir(SKILLS_DIR):
        return {"error": f"Skills directory not found: {SKILLS_DIR}"}
    reg = _load_registry(warn=False)  # 本次就要刷新，无需陈旧度警告
    found = []
    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if os.path.isdir(skill_dir):
            data = _scan_single_skill(skill_dir)
            reg["skills"][data["name"]] = data
            found.append(data["name"])
    # 剔除磁盘上已不存在的条目：否则删除的 Skill 会永久留在缓存里污染统计
    removed = sorted(set(reg.get("skills", {}).keys()) - set(found))
    for name in removed:
        del reg["skills"][name]
    reg["last_scan"] = _now_iso()
    reg["skill_count"] = len(found)
    reg["version"] = 2
    _save_registry(reg)

    # Snapshot + history
    old_snap = _load_snapshot()
    new_snap = _compute_snapshot()
    events = _diff_snapshots(old_snap, new_snap)
    _save_snapshot(new_snap)
    _log_history(events)

    return {
        "scanned": len(found),
        "names": found,
        "removed": removed,
        "timestamp": reg["last_scan"],
        "version": 2,
        "changes": len(events),
        "change_types": list(set(e["event"] for e in events)) if events else [],
    }


def list_skills():
    reg = _load_registry()
    skills = reg.get("skills", {})
    result = []
    for name, data in skills.items():
        g = _gate_score(data)
        result.append({
            "name": name,
            "maturity": _estimate_maturity(data),
            "lines": data.get("lines", 0),
            "score": g["score"],
            "passed": g["passed"],
            "errors": g["errors"],
            "warnings": g["warnings"],
            "has_tests": "tests" in data.get("components", {}),
            "has_meta": "skill.meta.json" in data.get("components", {}),
            "has_changelog": "CHANGELOG.md" in data.get("components", {}),
        })
    return sorted(result, key=lambda x: (not x["passed"], x["score"]))


def show(name):
    reg = _load_registry()
    if name not in reg.get("skills", {}):
        return {"error": f"Skill '{name}' not found"}
    data = reg["skills"][name]
    data["maturity"] = _estimate_maturity(data)
    data["gate_score"] = _gate_score(data)
    return data


def status():
    reg = _load_registry()
    skills = reg.get("skills", {})
    stats = {
        "total": len(skills),
        "last_scan": reg.get("last_scan"),
        "version": reg.get("version", 1),
        "maturity_distribution": {"L0": 0, "L1": 0, "L2": 0, "L3": 0, "L4": 0, "L5": 0},
        "passed": 0, "failed": 0,
        "total_errors": 0, "total_warnings": 0,
        "scores": [],
        "has_tests": 0, "has_meta": 0, "has_changelog": 0,
        "tests_with_cases": 0, "shell_tests": 0, "total_test_cases": 0,
    }
    for name, data in skills.items():
        m = _estimate_maturity(data)
        stats["maturity_distribution"][m] = stats["maturity_distribution"].get(m, 0) + 1
        g = _gate_score(data)
        if g["passed"]:
            stats["passed"] += 1
        else:
            stats["failed"] += 1
        stats["total_errors"] += g["errors"]
        stats["total_warnings"] += g["warnings"]
        stats["scores"].append(g["score"])
        if "tests" in data.get("components", {}): stats["has_tests"] += 1
        if "skill.meta.json" in data.get("components", {}): stats["has_meta"] += 1
        if "CHANGELOG.md" in data.get("components", {}): stats["has_changelog"] += 1
        tc = data.get("test_cases")
        if tc:
            stats["tests_with_cases"] += 1
            stats["total_test_cases"] += tc
        elif tc == 0:
            stats["shell_tests"] += 1

    scores = stats["scores"]
    stats["avg_score"] = round(sum(scores) / len(scores), 1) if scores else 0
    stats["min_score"] = min(scores) if scores else 0
    stats["max_score"] = max(scores) if scores else 0
    stats["infra_capability"] = INFRA_CAPABILITY
    return stats


def validate():
    reg = _load_registry()
    results = []
    for name, data in sorted(reg.get("skills", {}).items()):
        g = _gate_score(data)
        issues = []
        if not os.path.exists(os.path.join(data.get("path", ""), "SKILL.md")):
            issues.append("🔴 SKILL.md 不存在")
        meta_keys = data.get("frontmatter_keys", [])
        if "name" not in meta_keys:
            issues.append("🔴 frontmatter 缺少 name")
        if "description" not in meta_keys:
            issues.append("🔴 frontmatter 缺少 description")
        elif data.get("desc_length", 0) == 0:
            issues.append("🔴 description 为空")

        warnings = []
        if data.get("desc_length", 0) > 1024:
            warnings.append("⚠️ description 过长")
        if not data.get("has_triggers", False):
            warnings.append("⚠️ 缺少明确触发条件")
        if not data.get("has_failure_modes", False):
            warnings.append("⚠️ 缺少失败模式编码")
        if not data.get("has_anti_examples", False):
            warnings.append("⚠️ 缺少反例/黑名单")
        if not data.get("has_checkpoints", False):
            warnings.append("⚠️ 缺少检查点")
        if not data.get("has_steps", False):
            warnings.append("⚠️ 缺少步骤结构")
        if data.get("has_fluff", False):
            warnings.append("⚠️ AI 腔软化措辞 ≥3 处")
        if data.get("has_ending_fluff", False):
            warnings.append("⚠️ 结尾有空话")
        for comp in ["tests", "skill.meta.json", "CHANGELOG.md"]:
            if comp not in data.get("components", {}):
                warnings.append(f"ℹ️ 缺少 {comp}")

        results.append({
            "name": name,
            "maturity": _estimate_maturity(data),
            "passed": g["passed"],
            "score": g["score"],
            "errors": g["errors"],
            "warnings": g["warnings"],
            "issues": issues,
            "warnings_detail": warnings,
        })
    return results


def export_markdown():
    reg = _load_registry()
    skills = reg.get("skills", {})
    st = status()
    lines = ["# Minis Skill Registry v2", f"> 最后扫描: {st.get('last_scan', 'N/A')}", f"> 门禁式评分（error 一票否决）", ""]
    lines.append(f"**总览**: {st['passed']}/{st['total']} 通过, Avg {st['avg_score']}, "
                 f"成熟度 {st['maturity_distribution']}")
    lines.append("")
    lines.append("| Skill | 成熟度 | 评分 | 状态 | 错误 | 警告 | tests | meta | changelog |")
    lines.append("|-------|--------|------|------|------|------|-------|------|-----------|")
    for name in sorted(skills.keys()):
        d = skills[name]
        g = _gate_score(d)
        m = _estimate_maturity(d)
        icon = "✅" if g["passed"] else "🔴"
        lines.append(
            f"| {name} | {m} | {g['score']} | {icon} | {g['errors']} | {g['warnings']} | "
            f"{'✅' if 'tests' in d.get('components', {}) else '❌'} | "
            f"{'✅' if 'skill.meta.json' in d.get('components', {}) else '❌'} | "
            f"{'✅' if 'CHANGELOG.md' in d.get('components', {}) else '❌'} |"
        )
    lines.append("")
    lines.append("## 基础设施状态")
    lines.append("| 能力 | 状态 |")
    lines.append("|------|------|")
    for k, v in INFRA_CAPABILITY.items():
        lines.append(f"| {k} | {'✅' if v else '❌'} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Minis Skill Registry v2")
    parser.add_argument("command", choices=["scan", "list", "show", "status", "validate", "json", "export", "snapshot", "history"], nargs="?", default="list")
    parser.add_argument("name", nargs="?")
    parser.add_argument("--json", action="store_true", dest="json_out")
    parser.add_argument("--limit", type=int, default=20, help="History: max events to show (default 20)")
    args = parser.parse_args()

    if args.command == "scan":
        result = scan()
    elif args.command == "list":
        result = list_skills()
    elif args.command == "show":
        if not args.name:
            print("Error: 'show' requires a skill name"); sys.exit(1)
        result = show(args.name)
    elif args.command == "status":
        result = status()
    elif args.command == "validate":
        result = validate()
    elif args.command == "export":
        print(export_markdown()); return
    elif args.command == "json":
        result = _load_registry()
    elif args.command == "snapshot":
        result = snapshot_cmd()
    elif args.command == "history":
        result = history_cmd(args.limit)

    if args.command == "list":
        if not result:
            print("No skills registered. Run 'scan' first."); return
        print(f"{'Skill':<24} {'成熟度':<6} {'评分':>4} {'状态':<4} {'错':>2} {'警':>2} {'tests':<5} {'meta':<5} {'changelog':<8}")
        print("-" * 70)
        for s in result:
            icon = "✅" if s["passed"] else "🔴"
            print(f"{s['name']:<24} {s['maturity']:<6} {s['score']:>4} {icon:<4} {s['errors']:>2} {s['warnings']:>2} "
                  f"{'✅' if s['has_tests'] else '❌':<5} {'✅' if s['has_meta'] else '❌':<5} "
                  f"{'✅' if s['has_changelog'] else '❌':<8}")
    elif args.command == "status":
        print(f"注册表 v{result.get('version',1)} (最后扫描: {result.get('last_scan', 'N/A')}):")
        print(f"  总 Skill 数: {result['total']}  ✅ 通过: {result['passed']}  🔴 未通过: {result['failed']}")
        print(f"  评分: Avg {result['avg_score']} (min {result['min_score']}, max {result['max_score']})")
        print(f"  错误: {result['total_errors']}  警告: {result['total_warnings']}")
        print(f"  成熟度: {result['maturity_distribution']}")
        print(f"  tests: {result['has_tests']}/{result['total']}  meta.json: {result['has_meta']}/{result['total']}  changelog: {result['has_changelog']}/{result['total']}")
        print(f"  ⚠ tests 真实内容: 有用例 {result.get('tests_with_cases', 0)}/{result['total']}"
              f"  空壳(0 用例) {result.get('shell_tests', 0)}  用例总数 {result.get('total_test_cases', 0)}")
        print(f"  基础设施: {result.get('infra_capability', {})}")
    elif args.command == "validate":
        fail = sum(1 for r in result if not r["passed"])
        print(f"Skill 门禁校验 ({result.__len__()} 个, {fail} 个未通过):")
        print()
        for r in result:
            icon = "✅" if r["passed"] else "🔴"
            print(f"  {icon} {r['name']} ({r['maturity']}, {r['score']}/100)")
            if r["issues"]:
                for i in r["issues"]:
                    print(f"    {i}")
            if r["warnings_detail"]:
                for w in r["warnings_detail"][:4]:
                    print(f"    {w}")
                if len(r["warnings_detail"]) > 4:
                    print(f"    ... 还有 {len(r['warnings_detail']) - 4} 项")
            print()
    elif args.command == "snapshot":
        if "error" in result:
            print(result["error"]); return
        if args.json_out:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Skill 快照 (时间: {result['timestamp']}, 共 {result['skill_count']} 个):")
            print()
            for name, s in sorted(result["skills"].items()):
                h = s.get("skill_md_hash", "N/A")
                sz = s.get("skill_md_size", "?")
                comps = ", ".join(s.get("components", []))
                print(f"  {name}")
                print(f"    SKILL.md: {sz}B  hash={h}")
                if comps:
                    print(f"    组件: {comps}")
    elif args.command == "history":
        if not result:
            print("暂无变更记录。")
            return
        if args.json_out:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Skill 变更历史 (最近 {len(result)} 条):")
            print()
            for ev in result:
                ts = ev.get("timestamp", "N/A")[:19]
                if ev["event"] == "skill_added":
                    print(f"  ➕ [{ts}] Skill 新增: {ev['name']}")
                elif ev["event"] == "skill_removed":
                    print(f"  ➖ [{ts}] Skill 移除: {ev['name']}")
                elif ev["event"] == "skill_modified":
                    old = (ev.get("old_hash") or "?")[:8]
                    new = (ev.get("new_hash") or "?")[:8]
                    print(f"  ✏️ [{ts}] Skill 内容变更: {ev['name']}/{ev.get('field','')}  {old}→{new}")
                elif ev["event"] == "component_added":
                    print(f"  📄 [{ts}] 组件新增: {ev['name']}/{ev['component']}")
                elif ev["event"] == "component_removed":
                    print(f"  🗑️ [{ts}] 组件移除: {ev['name']}/{ev['component']}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()