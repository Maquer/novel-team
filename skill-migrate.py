#!/usr/bin/env python3
# Version: 0.1.0
"""
skill-migrate.py — Skill 批量迁移 v2

v2 变更（审计后修复）：
- 权限推断正则收紧：加 \b 边界，补 subprocess/os.system/requests 检测
- 迁移时诊断 frontmatter 缺失，自动修复或明确警告
- 依赖推断排除自身名称

用法:
  python3 skill-migrate.py                    # 迁移所有
  python3 skill-migrate.py --skill <name>     # 单个
  python3 skill-migrate.py --dry-run          # 预览
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILLS_DIR = "/var/minis/skills"

KNOWN_SKILLS = ["skill-creator", "darwin-skill", "grill-me", "airtap",
                "bao-kuai-xie-zuo", "hai-bao-she-ji", "gongzhonghao-publish",
                "nei-rong-zhuan-hua", "ponytail", "wu-ceng-jue-ce"]

PERMISSION_PATTERNS = {
    "filesystem": [r'\b(read|write|open|pathlib|os\.(path|remove|mkdir|listdir))\b', r'\b(目录|文件夹|路径|文件系统)\b'],
    "network": [r'\b(requests|urllib|aiohttp|http\.client)\b', r'\b(curl|wget|fetch|axios)\b', r'\b(网络|url|endpoint)\b'],
    "shell": [r'\b(subprocess|os\.system|os\.popen|shell\s*=\s*true)\b', r'\b(exec|eval)\b', r'\b(终端|命令行)\b'],
    "ios-frameworks": [r'\bapple-(alarm|bluetooth|calendar|healthkit|maps|phone)\b', r'\b(iOS|iPhone|iPad|iSH|device)\b'],
    "secrets": [r'\b(api[_-]?key|token|secret|credential|password)\b', r'\b(AZURE_|GOOGLE_|OPENAI_)\w*\b'],
}


def _parse_frontmatter(text):
    meta = {}
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?', text, re.DOTALL)
    if not m:
        return meta
    for line in m.group(1).split('\n'):
        if ':' in line:
            k, v = line.split(':', 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta


def _detect_permissions(text):
    perms = set()
    for perm, patterns in PERMISSION_PATTERNS.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                perms.add(perm)
                break
    if not perms:
        perms.add("none")
    return sorted(perms)


def _detect_dependencies(text, own_name):
    deps = set()
    for sk in KNOWN_SKILLS:
        if sk == own_name:
            continue
        if re.search(r'\b' + re.escape(sk) + r'\b', text):
            deps.add(sk)
    return sorted(deps)


def _diagnose_frontmatter(text, name):
    meta = _parse_frontmatter(text)
    missing = []
    issues = []
    if "name" not in meta:
        missing.append("name")
        issues.append("🔴 frontmatter 缺少 name 字段")
    if "description" not in meta:
        missing.append("description")
        issues.append("🔴 frontmatter 缺少 description 字段")
    elif meta.get("description", "") == "":
        issues.append("🔴 description 为空")

    auto_fix = _auto_fix_frontmatter(text, name, missing) if missing else None
    return missing, issues, auto_fix


def _auto_fix_frontmatter(text, name, missing):
    lines = text.split('\n')
    # 找 frontmatter 结束行
    fm_end = None
    for i in range(1, min(10, len(lines))):
        if lines[i].strip() == '---':
            fm_end = i
            break
    if fm_end is None:
        return None

    fixed = False

    remaining = missing.copy()
    if "name" in remaining and not any(l.startswith('  name:') for l in lines):
        lines.insert(fm_end, f'  name: "{name}"')
        fm_end += 1
        remaining.remove("name")
        fixed = True

    if "description" in remaining:
        body = re.sub(r'---\s*\n.*?\n---\s*\n?', '', text, count=1, flags=re.DOTALL)
        first_para = re.match(r'^[^\n.。]+[.。]?\s*\n?([^\n.。]*[.。])', body)
        if first_para:
            desc = first_para.group(0).strip()
            if len(desc) > 10 and len(desc) < 200:
                lines.insert(fm_end, f'  description: "{desc}"')
                remaining.remove("description")
                fixed = True

    return '\n'.join(lines) if fixed else None


def migrate_skill(name, dry_run=False):
    skill_dir = os.path.join(SKILLS_DIR, name)
    skill_path = os.path.join(skill_dir, "SKILL.md")
    changes = []
    diagnoses = []

    if not os.path.isdir(skill_dir):
        return {"name": name, "status": "skip", "reason": "directory not found"}
    if not os.path.exists(skill_path):
        return {"name": name, "status": "skip", "reason": "no SKILL.md"}

    text = Path(skill_path).read_text(encoding='utf-8')

    # 诊断 frontmatter
    missing, issues, auto_fix = _diagnose_frontmatter(text, name)
    for issue in issues:
        diagnoses.append(issue)

    if auto_fix and missing:
        if dry_run:
            diagnoses.append(f"💡 可自动修复: {', '.join(missing)}")
        else:
            Path(skill_path).write_text(auto_fix, encoding='utf-8')
            changes.append(f"🔧 自动修复 frontmatter: {', '.join(missing)}")

    text = auto_fix or text
    meta = _parse_frontmatter(text)

    # 生成 meta.json
    meta_path = os.path.join(skill_dir, "skill.meta.json")
    meta_json = {
        "name": meta.get("name", name),
        "version": "1.0.0",
        "status": "approved",
        "author": "human",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provenance": {"source": "manual", "source_trace_ids": [], "external_refs": []},
        "permissions": _detect_permissions(text),
        "dependencies": _detect_dependencies(text, name),
        "last_eval": {"score": None, "passed": None, "date": None, "eval_mode": None},
        "review_history": [],
        "maturity": "L1",
        "lines": len(text.split('\n')),
        "char_count": len(text),
        "frontmatter_issues": missing,
    }
    if not dry_run and not os.path.exists(meta_path):
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta_json, f, ensure_ascii=False, indent=2)
        changes.append(f"skill.meta.json (perms={meta_json['permissions']}, deps={meta_json['dependencies']})")

    # 创建 tests/
    tests_dir = os.path.join(skill_dir, "tests")
    if not os.path.exists(tests_dir) and not dry_run:
        os.makedirs(tests_dir, exist_ok=True)
        with open(os.path.join(tests_dir, "README.json"), 'w', encoding='utf-8') as f:
            json.dump({"description": f"Trigger boundary tests for '{name}'",
                       "generated_at": datetime.now(timezone.utc).isoformat(),
                       "explicit_triggers": [], "implicit_triggers": [],
                       "negative_triggers": [], "regression": []}, f, ensure_ascii=False, indent=2)
        changes.append("tests/ + README.json")

    # 创建 CHANGELOG.md
    changelog_path = os.path.join(skill_dir, "CHANGELOG.md")
    if not os.path.exists(changelog_path) and not dry_run:
        with open(changelog_path, 'w', encoding='utf-8') as f:
            f.write(f"# CHANGELOG — {name}\n\n> Skill evolution audit trail.\n\n")
            f.write(f"## v1.0.0\n\n- **Date:** {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write("- **Change:** Initial migration\n- **Source:** skill-migrate.py\n")
            f.write("- **Status:** approved\n- **Eval:** pending\n\n---\n\n")
        changes.append("CHANGELOG.md")

    return {"name": name, "status": "migrated", "changes": changes,
            "diagnoses": diagnoses, "permissions": meta_json["permissions"],
            "dependencies": meta_json["dependencies"]}


def migrate_all(dry_run=False):
    if not os.path.isdir(SKILLS_DIR):
        sys.exit(1)
    results = []
    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if os.path.isdir(skill_dir):
            r = migrate_skill(entry, dry_run)
            results.append(r)
            icon = "✅" if r["status"] == "migrated" else "⏭️"
            chg = ", ".join(r.get("changes", []))
            diag = " | ".join(r.get("diagnoses", [])) if r.get("diagnoses") else ""
            print(f"  {icon} {entry:<24} {r['status']:<10} {chg} {diag}")
    print(f"\n  Migrated: {sum(1 for r in results if r['status']=='migrated')}, "
          f"Skipped: {sum(1 for r in results if r['status']=='skip')}, "
          f"Dry run: {dry_run}")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", help="单个 Skill")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.skill:
        migrate_skill(args.skill, args.dry_run)
    else:
        migrate_all(args.dry_run)


if __name__ == "__main__":
    main()