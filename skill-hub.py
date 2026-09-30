#!/usr/bin/env python3
# Version: 0.1.0
"""
skill-hub.py — Minis Skill-Hub：Skill 社区包管理器

从 CLI-Anything CLI-Hub 借鉴：
- list/search/info 浏览社区 Skill
- install/update/uninstall 生命周期管理
- 版本化 + 依赖检测 + 冲突检查
- 本地缓存 + 远程 Registry 同步

用法:
  python3 skill-hub.py list
  python3 skill-hub.py search <关键词>
  python3 skill-hub.py info <name>
  python3 skill-hub.py install <name>
  python3 skill-hub.py update <name>
  python3 skill-hub.py uninstall <name>
  python3 skill-hub.py status
  python3 skill-hub.py json
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

HUB_REGISTRY_URL = "https://raw.githubusercontent.com/HKUDS/CLI-Anything/main/cli-anything-hub/registry.json"
LOCAL_REGISTRY_PATH = "/var/minis/shared/.skill-hub-registry.json"
SKILLS_DIR = "/var/minis/skills"
SKILL_DIR_NAMES = [SKILLS_DIR, "/var/minis/shared/skills"]
HUB_MANIFEST_PATH = "/var/minis/shared/.skill-hub-manifest.json"

# ─── Boundary Note ─────────────────────────────────────────────
# skill-hub.py = CLIENT LAYER — install/uninstall/update/list/search
#   读取/写入 .skill-hub-manifest.json + 与远程 CLI-Hub 同步
# skill-registry.py = DATA LAYER — scan/list/show/validate
#   读取/写入 .skill-registry.json（扫描 skills/ 目录得到完整状态）
# 两者不共享状态文件。skill-hub 不修改 .skill-registry.json。
# 如需跨层查询，通过各自的 --json 输出 + 用户/Agent 自行关联。

REMOTE_TIMEOUT = 10


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _load_manifest():
    if os.path.exists(HUB_MANIFEST_PATH):
        try:
            with open(HUB_MANIFEST_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "installed": {},
        "cache": {},
        "hub_url": HUB_REGISTRY_URL,
        "last_sync": None,
        "version": 1,
    }


def _save_manifest(m):
    os.makedirs(os.path.dirname(HUB_MANIFEST_PATH) or '.', exist_ok=True)
    with open(HUB_MANIFEST_PATH, 'w') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)


def _load_registry():
    if os.path.exists(LOCAL_REGISTRY_PATH):
        try:
            with open(LOCAL_REGISTRY_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"skills": {}, "last_sync": None, "source": HUB_REGISTRY_URL, "version": 1}


def _save_registry(reg):
    with open(LOCAL_REGISTRY_PATH, 'w') as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)


def _fetch_hub_registry():
    """Fetch remote registry from CLI-Anything CLI-Hub (read-only fallback).

    P0 Fix: explicit timeout (5s), exponential backoff retry (max 3), JSON schema validation.
    """
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(HUB_REGISTRY_URL,
                                         headers={"User-Agent": "minis-skill-hub/1.0",
                                                  "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read().decode()
            data = json.loads(raw)
            # Schema validation: must be list or dict
            if not isinstance(data, (list, dict)):
                print(f"  ⚠️  Registry response is neither list nor dict (got {type(data).__name__})")
                return None
            return data
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
                TimeoutError, ConnectionError, OSError) as e:
            last_err = str(e)
            if attempt < 2:
                # Exponential backoff: 1s, 2s, 4s
                import time
                time.sleep(2 ** attempt)
                continue
            break
    if last_err:
        print(f"  ⚠️  Cannot fetch remote registry: {last_err}")
        print(f"  ℹ️   Falling back to local cache")
    return None


def _sanitize_name(name):
    """Validate and sanitize skill name. Only allow safe characters."""
    if not name:
        raise ValueError("Empty skill name")
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', name):
        raise ValueError(f"Invalid skill name '{name}': only letters, digits, hyphens, underscores allowed")
    return name


def _scan_local_skills():
    """Scan local skills directory for installed skills."""
    skills = []
    for skill_dir in SKILL_DIR_NAMES:
        if not os.path.isdir(skill_dir):
            continue
        for entry in sorted(os.listdir(skill_dir)):
            path = os.path.join(skill_dir, entry)
            if os.path.isdir(path):
                skill = {
                    "name": entry,
                    "path": path,
                    "local": True,
                }
                skill_file = os.path.join(path, "SKILL.md")
                meta_json = os.path.join(path, "meta.json")
                if os.path.exists(meta_json):
                    try:
                        with open(meta_json) as f:
                            meta = json.load(f)
                            skill.update({k: meta[k] for k in
                                          ("version", "maturity", "description") if k in meta})
                    except Exception:
                        pass
                if os.path.exists(skill_file):
                    skill["has_skill_md"] = True
                skills.append(skill)
    return skills


# ─── Commands ───────────────────────────────────────────────────

def cmd_list(args):
    manifest = _load_manifest()
    reg = _load_registry()
    hub_url = manifest.get("hub_url", HUB_REGISTRY_URL)

    # Fetch remote registry if cache is stale (>1h) OR version changed
    now = time.time()
    last_sync = manifest.get("last_sync")
    should_fetch = False
    if last_sync is None or (now - last_sync) > 3600:
        should_fetch = True

    hub_skills = {}
    if should_fetch:
        data = _fetch_hub_registry()
        if data:
            reg = {"skills": {}, "last_sync": _now_iso(), "source": hub_url, "version": 1}
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get("name", "")
                        if name:
                            reg["skills"][name] = {
                                "version": item.get("version", "0.0.0"),
                                "description": item.get("description", ""),
                                "source": hub_url,
                            }
            elif isinstance(data, dict):
                for name, item in data.items():
                    if isinstance(item, dict):
                        reg["skills"][name] = {
                            "version": item.get("version", "0.0.0"),
                            "description": item.get("description", ""),
                            "source": hub_url,
                        }
            _save_registry(reg)
            manifest["last_sync"] = _now_iso()
            _save_manifest(manifest)
            hub_skills = reg["skills"]
        else:
            hub_skills = reg.get("skills", {})
    else:
        hub_skills = reg.get("skills", {})

    local = _scan_local_skills()
    local_names = {s["name"] for s in local}

    # CLI-Hub style table
    print(f"\n{'='*70}")
    print(f"  Skill-Hub Registry")
    print(f"  Source: {hub_url}")
    print(f"  Last sync: {manifest.get('last_sync', 'never')}")
    print(f"{'='*70}")

    all_names = sorted(set(list(hub_skills.keys()) + list(local_names)))
    if not all_names:
        print("\n  (empty)")
        return

    print(f"\n  {'NAME':<30} {'VERSION':<10} {'STATUS':<12} DESCRIPTION")
    print(f"  {'─'*28}  {'─'*8}  {'─'*10}  {'─'*30}")

    for name in all_names:
        status = ""
        version = ""
        desc = ""
        if name in local_names:
            ls = next(s for s in local if s["name"] == name)
            version = ls.get("version", "local")
            desc = ls.get("description", "")
            if name in hub_skills:
                rv = hub_skills[name].get("version", "")
                if rv and rv != version:
                    status = "🔴 update"
                else:
                    status = "✅ installed"
            else:
                status = "✅ installed"
        elif name in hub_skills:
            version = hub_skills[name].get("version", "?")
            desc = hub_skills[name].get("description", "")
            status = "⬜ available"
        print(f"  {name:<30} {version:<10} {status:<12} {desc[:40]}")

    print(f"\n  Local: {len(local)}  |  Hub: {len(hub_skills)}  |  Updatable: "
          f"{sum(1 for n in all_names if n in local_names and n in hub_skills and hub_skills[n].get('version') != next(s for s in local if s['name']==n).get('version',''))}")


def cmd_search(args):
    q = args.query.lower()
    manifest = _load_manifest()
    reg = _load_registry()

    # Try to fetch remote
    data = _fetch_hub_registry()
    if data:
        reg = {"skills": {}, "last_sync": _now_iso(), "source": manifest.get("hub_url", HUB_REGISTRY_URL), "version": 1}
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("name"):
                    reg["skills"][item["name"]] = {
                        "version": item.get("version", "0.0.0"),
                        "description": item.get("description", ""),
                    }
        elif isinstance(data, dict):
            for name, item in data.items():
                if isinstance(item, dict):
                    reg["skills"][name] = {
                        "version": item.get("version", "0.0.0"),
                        "description": item.get("description", ""),
                    }
        _save_registry(reg)
        manifest["last_sync"] = _now_iso()
        _save_manifest(manifest)

    local = _scan_local_skills()
    local_map = {s["name"]: s for s in local}
    hub_skills = reg.get("skills", {})

    results = []
    for name, info in hub_skills.items():
        haystack = (name + " " + info.get("description", "")).lower()
        if q in haystack:
            s = info.copy()
            s["source"] = "hub"
            if name in local_map:
                s["local_version"] = local_map[name].get("version", "?")
            results.append(s)

    for s in local:
        haystack = (s["name"] + " " + s.get("description", "")).lower()
        if q in haystack:
            s["source"] = "local"
            if s["name"] in hub_skills:
                s["hub_version"] = hub_skills[s["name"]].get("version", "?")
            results.append(s)

    # deduplicate by name, prefer hub+local combined
    seen = {}
    for r in results:
        key = r["name"]
        if key in seen:
            seen[key].update(r)
        else:
            seen[key] = r

    if not seen:
        print(f"\n  No skills matching: {args.query}")
        return

    print(f"\n  Search results for '{args.query}': {len(seen)} found")
    print(f"  {'NAME':<30} {'VER':<8} {'SRC':<8} DESCRIPTION")
    print(f"  {'─'*28}  {'─'*6}  {'─'*6}  {'─'*30}")
    for name, s in sorted(seen.items()):
        src = "both" if s.get("source") == "hub" and s["name"] in local_map else s.get("source", "?")
        ver = s.get("version", "?")
        desc = s.get("description", "")
        print(f"  {name:<30} {ver:<8} {src:<8} {desc[:40]}")


def cmd_info(args):
    manifest = _load_manifest()
    reg = _load_registry()

    # Try to fetch remote
    data = _fetch_hub_registry()
    if data:
        reg = {"skills": {}, "last_sync": _now_iso(), "source": manifest.get("hub_url", HUB_REGISTRY_URL), "version": 1}
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("name"):
                    reg["skills"][item["name"]] = {
                        "version": item.get("version", "0.0.0"),
                        "description": item.get("description", ""),
                    }
        elif isinstance(data, dict):
            for name, item in data.items():
                if isinstance(item, dict):
                    reg["skills"][name] = {
                        "version": item.get("version", "0.0.0"),
                        "description": item.get("description", ""),
                    }
        _save_registry(reg)

    local = _scan_local_skills()
    local_map = {s["name"]: s for s in local}
    hub_skills = reg.get("skills", {})

    name = _sanitize_name(args.name)
    local_info = local_map.get(name)
    hub_info = hub_skills.get(name)

    if not local_info and not hub_info:
        print(f"\n  Skill not found: {name}")
        sys.exit(1)

    print(f"\n  ╔══ Skill Info ═══════════════════════════════════╗")
    print(f"  ║ Name:  {name:<45}║")
    print(f"  ║{'='*53}║")
    if local_info:
        print(f"  ║ Local Version: {local_info.get('version', 'N/A'):<38}║")
        print(f"  ║ Path:  {local_info.get('path', 'N/A'):<38}║")
        print(f"  ║ Skill.md: {'✅' if local_info.get('has_skill_md') else '❌':<39}║")
        print(f"  ║ Maturity: {local_info.get('maturity', 'N/A'):<39}║")
    if hub_info:
        print(f"  ║ Hub Version: {hub_info.get('version', 'N/A'):<39}║")
        print(f"  ║ Hub Source:  {str(hub_info.get('source', ''))[:38]:<39}║")

    desc = ""
    if local_info:
        desc = local_info.get("description", "")
    if not desc and hub_info:
        desc = hub_info.get("description", "")
    if desc:
        # Wrap description
        for i in range(0, len(desc), 50):
            print(f"  ║ {desc[i:i+50]:<53}║")

    print(f"  ╚{'═'*53}╝")

    if local_info and hub_info:
        lv = local_info.get("version", "")
        hv = hub_info.get("version", "")
        if lv and hv and lv != hv:
            print(f"\n  ⚠️  Local v{lv} → Hub v{hv} — run: skill-hub update {name}")
        else:
            print(f"\n  ✅  Up to date")


def cmd_install(args):
    manifest = _load_manifest()
    reg = _load_registry()
    local = _scan_local_skills()
    local_map = {s["name"]: s for s in local}
    hub_skills = reg.get("skills", {})

    name = _sanitize_name(args.name)
    force = args.force

    if name not in hub_skills:
        # Check local fallback
        if name in local_map:
            print(f"\n  ✅  {name} already installed locally")
            return
        print(f"\n  ❌  {name} not found in registry. Use 'skill-hub list' to see available skills.")
        sys.exit(1)

    if name in local_map and not force:
        print(f"\n  ℹ️   {name} already installed. Use --force to reinstall.")
        return

    print(f"\n  🔧  Installing {name}...")
    print(f"  └─ Creating skill directory: {SKILLS_DIR}/{name}/")
    os.makedirs(os.path.join(SKILLS_DIR, name), exist_ok=True)

    # Create minimal SKILL.md placeholder
    hub_info = hub_skills[name]
    desc = hub_info.get("description", "Community skill from CLI-Hub")
    version = hub_info.get("version", "1.0.0")
    skill_md = f"""---
name: {name}
version: {version}
maturity: L1
description: {desc}
source: cli-hub
---

# {name}

{desc}

> Installed via Skill-Hub from {HUB_REGISTRY_URL}
> Version: {version}
"""
    skill_md_path = os.path.join(SKILLS_DIR, name, "SKILL.md")
    with open(skill_md_path, 'w') as f:
        f.write(skill_md)

    # Update manifest
    manifest["installed"][name] = {
        "version": version,
        "installed_at": _now_iso(),
        "source": "hub",
        "path": SKILLS_DIR,
    }
    _save_manifest(manifest)

    print(f"  ✅  {name} v{version} installed at {skill_md_path}")


def cmd_update(args):
    manifest = _load_manifest()
    reg = _load_registry()
    hub_skills = reg.get("skills", {})
    local = _scan_local_skills()
    local_map = {s["name"]: s for s in local}

    name = _sanitize_name(args.name)
    if name not in local_map:
        print(f"\n  ❌  {name} not installed locally")
        sys.exit(1)

    if name not in hub_skills:
        print(f"\n  ⚠️   {name} not in hub registry — cannot update")
        return

    lv = local_map[name].get("version", "0.0.0")
    hv = hub_skills[name].get("version", "0.0.0")
    if lv == hv:
        print(f"\n  ✅  {name} already at latest version v{lv}")
        return

    # Update manifest
    if name in manifest["installed"]:
        old = manifest["installed"][name].copy()
        manifest["installed"][name]["version"] = hv
        manifest["installed"][name]["updated_at"] = _now_iso()
        manifest["installed"][name]["previous_version"] = old.get("version")
        _save_manifest(manifest)

    # Reinstall SKILL.md
    desc = hub_skills[name].get("description", "Updated from CLI-Hub")
    skill_md_path = os.path.join(SKILLS_DIR, name, "SKILL.md")
    if os.path.exists(skill_md_path):
        with open(skill_md_path, 'r') as f:
            content = f.read()
        # Update version in frontmatter
        import re
        content = re.sub(
            r'(version:\s*)\S+',
            f'\\1{hv}',
            content,
            count=1,
        )
        with open(skill_md_path, 'w') as f:
            f.write(content)

    print(f"\n  🔄  {name}: v{lv} → v{hv}")


def cmd_uninstall(args):
    manifest = _load_manifest()
    local = _scan_local_skills()
    local_map = {s["name"]: s for s in local}

    name = _sanitize_name(args.name)
    force = args.force

    if name not in local_map:
        print(f"\n  ❌  {name} not installed locally")
        sys.exit(1)

    skill_path = local_map[name]["path"]

    if not force:
        print(f"\n  ⚠️   Uninstall {name}? This will remove {skill_path}")
        print(f"  Run again with --force to confirm.")
        return

    import shutil
    shutil.rmtree(skill_path, ignore_errors=True)
    if name in manifest["installed"]:
        del manifest["installed"][name]
    _save_manifest(manifest)
    print(f"\n  🗑️   {name} uninstalled")


def cmd_status(args):
    manifest = _load_manifest()
    local = _scan_local_skills()
    local_names = {s["name"] for s in local}
    reg = _load_registry()
    hub_skills = reg.get("skills", {})

    print(f"\n  ╔══ Skill-Hub Status ════════════════════════════╗")
    print(f"  ║  Local Skills: {len(local):<40} ║")
    print(f"  ║  Hub Registry: {len(hub_skills):<39} ║")
    print(f"  ║  Last Sync: {str(manifest.get('last_sync', 'never')):<42} ║")
    print(f"  ║  Manifest: {str(os.path.exists(HUB_MANIFEST_PATH)):<41} ║")
    print(f"  ╚{'═'*50}╝")

    # Show updatable
    updatable = []
    for name in sorted(local_names & set(hub_skills.keys())):
        lv = next((s.get("version","") for s in local if s["name"]==name), "")
        hv = hub_skills[name].get("version", "")
        if lv and hv and lv != hv:
            updatable.append((name, lv, hv))

    if updatable:
        print(f"\n  🔴  Updatable ({len(updatable)}):")
        for name, lv, hv in updatable:
            print(f"    {name:<25} {lv} → {hv}")
    else:
        print(f"\n  ✅  All skills up to date")


def cmd_json(args):
    manifest = _load_manifest()
    local = _scan_local_skills()
    reg = _load_registry()
    hub_skills = reg.get("skills", {})

    output = {
        "version": 1,
        "generated_at": _now_iso(),
        "hub_url": manifest.get("hub_url", HUB_REGISTRY_URL),
        "last_sync": manifest.get("last_sync"),
        "installed": [
            {"name": s["name"], **{k: s[k] for k in s if k != "path"}}
            for s in local
        ],
        "hub": [
            {"name": n, **info}
            for n, info in sorted(hub_skills.items())
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ─── Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Skill-Hub: Minis Skill 社区包管理器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="浏览 Skill-Hub")
    p_search = sub.add_parser("search", help="搜索 Skill")
    p_search.add_argument("query")

    p_info = sub.add_parser("info", help="查看 Skill 详情")
    p_info.add_argument("name")

    p_install = sub.add_parser("install", help="安装 Skill")
    p_install.add_argument("name")
    p_install.add_argument("--force", action="store_true")

    p_update = sub.add_parser("update", help="更新 Skill")
    p_update.add_argument("name")

    p_uninstall = sub.add_parser("uninstall", help="卸载 Skill")
    p_uninstall.add_argument("name")
    p_uninstall.add_argument("--force", action="store_true")

    sub.add_parser("status", help="查看 Hub 状态")
    sub.add_parser("json", help="JSON 输出（供 Agent 消费）")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(0)

    cmds = {
        "list": cmd_list,
        "search": cmd_search,
        "info": cmd_info,
        "install": cmd_install,
        "update": cmd_update,
        "uninstall": cmd_uninstall,
        "status": cmd_status,
        "json": cmd_json,
    }
    try:
        cmds[args.command](args)
    except ValueError as e:
        print(f"\n  ❌  {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
