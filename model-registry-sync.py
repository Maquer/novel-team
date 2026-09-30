#!/usr/bin/env python3
# Version: 0.1.0
"""
model-registry-sync.py — 模型注册表自动同步 v1.0

核心功能：从 minis-model-use list 获取实时模型列表，与已知元数据合并，
自动补齐缺失模型的档位/成本/模态等属性，输出统一的 .model-registry.json。

用法:
  python3 model-registry-sync.py sync              # 执行同步
  python3 model-registry-sync.py drift             # 显示差异报告
  python3 model-registry-sync.py show              # 显示当前注册表
  python3 model-registry-sync.py --json            # JSON 输出
"""

import json, sys, subprocess, os, re
from pathlib import Path
from datetime import datetime, timezone

REGISTRY_FILE = "/var/minis/shared/.model-registry.json"

# 已知模型元数据（seed）—— 手动维护的档位/成本信息
# 新模型自动推断，已知模型用此覆盖
KNOWN_METADATA = {
    "deepseek/deepseek-v4-flash": {"tier": 0, "label": "Flash",  "cost_tier": "low"},
    "agnes-2.5-pro": {"tier": 2, "label": "Pro",  "cost_tier": "medium"},
    "agnes-2.5-flash": {"tier": 0, "label": "Flash",  "cost_tier": "low"},
    "agnes-2.0-flash": {"tier": 0, "label": "Flash",  "cost_tier": "low"},
    "glm-5.2": {"tier": 2, "label": "Pro",  "cost_tier": "medium"},
    "mimo-v2.5": {"tier": 1, "label": "Standard",  "cost_tier": "low"},
    "cohere-north-mini-code": {"tier": 1, "label": "Standard",  "cost_tier": "low"},
    "dots3-note-prev": {"tier": 1, "label": "Standard",  "cost_tier": "low"},
    "gpt-4o-mini":                {"tier": 0, "label": "Flash",  "cost_tier": "low"},
    "sensenova-6.7-flash-lite":   {"tier": 0, "label": "Flash",  "cost_tier": "low"},
    "deepseek-v4":                {"tier": 1, "label": "Standard", "cost_tier": "medium"},
    "deepseek/deepseek-v4":       {"tier": 1, "label": "Standard", "cost_tier": "medium"},
    "qwen-3-max":                 {"tier": 1, "label": "Standard", "cost_tier": "medium"},
    "sensenova-6.7":              {"tier": 1, "label": "Standard", "cost_tier": "medium"},
    "anthropic/claude-sonnet-4-6": {"tier": 2, "label": "Pro",   "cost_tier": "high"},
    "google/gemini-2.5-pro":      {"tier": 2, "label": "Pro",    "cost_tier": "high"},
    "gpt-5.5":                    {"tier": 3, "label": "Max",    "cost_tier": "high"},
    "x-preview-f-free":           {"tier": 3, "label": "Max",    "cost_tier": "low"},
}

# 从 model_id 推断档位/成本/模态的规则
INFERENCE_RULES = [
    # 命名模式 → 档位
    (r'flash|lite|mini', 0, "Flash", "low"),
    (r'claude|gemini.*pro|gpt-5\.5|sonnet', 2, "Pro", "high"),
    (r'gpt-5\.5|glm-5|x-preview', 3, "Max", "high"),
    (r'gpt-4o|qwen.*max|deepseek-v4$', 1, "Standard", "medium"),
    (r'gpt-4o.*mini|sensenova.*flash', 0, "Flash", "low"),
]

IMAGE_ONLY_PATTERNS = [r'image.*output|gpt-image', r'image_output']


def fetch_live_models():
    """从 minis-model-use list --all 获取全部分组的模型列表

    必须带 --all：默认只返回 agent loop 分组内的模型。
    agent loop 分组为空时默认返回 0 个模型，会把已有注册表清空成 {}。
    """
    result = subprocess.run(
        ["minis-model-use", "list", "--all"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None, result.stderr.strip()
    try:
        data = json.loads(result.stdout)
        return data["data"]["models"], None
    except (json.JSONDecodeError, KeyError) as e:
        return None, str(e)


def infer_metadata(model_id, modalities, provider):
    """根据命名模式推断档位、成本、标签"""
    for pattern, tier, label, cost in INFERENCE_RULES:
        if re.search(pattern, model_id, re.IGNORECASE):
            return {"tier": tier, "label": label, "cost_tier": cost}

    # 默认
    return {"tier": 1, "label": "Standard", "cost_tier": "medium"}


def infer_description(model_id, display_name, provider, modalities):
    """生成描述"""
    parts = [display_name or model_id]
    if provider:
        parts.append(f"({provider})")
    # 标注特殊模态
    has_image = "image_output" in modalities
    if has_image:
        parts.append("[图生图]")
    has_audio = "audio_input" in modalities or "audio_output" in modalities
    if has_audio:
        parts.append("[音频]")
    return " ".join(parts)


def sync_registry(force=False):
    """
    执行同步。返回 (result_dict, drift_list)。
    drift_list: 每项含 {model_id, type: "added"|"updated"|"unchanged"|"removed", detail}
    """
    live_models, err = fetch_live_models()
    if err:
        return {"error": err}, []

    # 加载现有注册表
    existing = {}
    if os.path.exists(REGISTRY_FILE):
        try:
            existing = json.loads(Path(REGISTRY_FILE).read_text())
        except (json.JSONDecodeError, IOError):
            existing = {}

    # 保护：live 返回空但注册表非空 → 说明模型分组被清空或接口异常，
    # 绝不能用空列表覆盖已有注册表（会造成 60 个模型注册表被清空成 {}）
    if not live_models and existing:
        return {
            "error": "live model list returned 0 models while existing registry has "
                     f"{len(existing)} models — aborting sync to protect registry. "
                     "Check Settings > Model Groups.",
            "total": len(existing),
            "added": 0, "updated": 0, "removed": 0, "unchanged": len(existing),
            "registry_file": REGISTRY_FILE,
            "protected": True,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }, []

    live_ids = {m["model_id"] for m in live_models}
    existing_ids = set(existing.keys())

    # 已存在但不在 live 列表中的 → removed
    removed_ids = existing_ids - live_ids
    # live 中有但注册表中没有的 → added
    added_ids = live_ids - existing_ids
    # 共有的 → 检查是否需要更新
    common_ids = live_ids & existing_ids

    new_registry = {}
    drift = []

    now = datetime.now(timezone.utc).isoformat()

    for model in live_models:
        mid = model["model_id"]
        provider = model["instance_label"]
        display = model["display_name"]
        ctx = model["context_window"]
        modalities = model.get("modalities", [])

        if mid in removed_ids:
            continue  # removed 不在注册表里

        # 合并元数据
        known = KNOWN_METADATA.get(mid, {})
        inferred = infer_metadata(mid, modalities, provider)

        tier = known.get("tier", inferred["tier"])
        label = known.get("label", inferred["label"])
        cost_tier = known.get("cost_tier", inferred["cost_tier"])

        entry = {
            "model_id": mid,
            "qualified": mid,
            "display_name": display,
            "provider": provider,
            "tier": tier,
            "label": label,
            "cost_tier": cost_tier,
            "context": ctx,
            "modalities": modalities,
            "description": infer_description(mid, display, provider, modalities),
            "last_seen": now,
            "source": "live" if mid in added_ids else "sync",
        }
        new_registry[mid] = entry

        if mid in added_ids:
            drift.append({
                "model_id": mid,
                "type": "added",
                "detail": f"新模型自动加入: {display} ({provider})",
            })
        elif mid in common_ids:
            # 检查是否有字段变化
            old = existing.get(mid, {})
            changes = []
            for field in ["provider", "context", "modalities"]:
                if old.get(field) != entry.get(field):
                    changes.append(f"{field}: {old.get(field)} → {entry.get(field)}")
            if changes:
                drift.append({
                    "model_id": mid,
                    "type": "updated",
                    "detail": "; ".join(changes),
                })
            else:
                drift.append({
                    "model_id": mid,
                    "type": "unchanged",
                    "detail": None,
                })

    # 记录 removed
    for mid in removed_ids:
        old = existing.get(mid, {})
        drift.append({
            "model_id": mid,
            "type": "removed",
            "detail": f"已从提供商移除: {old.get('display_name', mid)} ({old.get('provider', '?')})",
        })

    # 写盘
    Path(REGISTRY_FILE).write_text(json.dumps(new_registry, indent=2, ensure_ascii=False))

    result = {
        "total": len(new_registry),
        "added": len(added_ids),
        "updated": sum(1 for d in drift if d["type"] == "updated"),
        "unchanged": sum(1 for d in drift if d["type"] == "unchanged"),
        "removed": len(removed_ids),
        "registry_file": REGISTRY_FILE,
        "synced_at": now,
    }
    return result, drift


def load_registry():
    """读取 .model-registry.json"""
    if os.path.exists(REGISTRY_FILE):
        try:
            return json.loads(Path(REGISTRY_FILE).read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def show_registry(args_json=False):
    """显示当前注册表"""
    reg = load_registry()
    if not reg:
        print("❌ 注册表为空，请先运行 sync")
        return

    if args_json:
        print(json.dumps(reg, indent=2, ensure_ascii=False))
        return

    print(f"📋 模型注册表 ({len(reg)} 个模型)")
    print(f"   最后同步: {reg[list(reg.keys())[0]].get('last_seen', '?')[:16]}")
    print(f"")
    print(f"   {'档位':5s} {'成本':8s} {'模态':25s} {'模型ID':35s} {'显示名':35s} {'服务商'}")
    print(f"   {'─'*5} {'─'*8} {'─'*25} {'─'*35} {'─'*35} {'─'*12}")
    for mid in sorted(reg.keys(), key=lambda x: (reg[x]["tier"], reg[x]["cost_tier"])):
        e = reg[mid]
        modal = ','.join(e.get("modalities", []))
        print(f"   L{e['tier']:<4d} {e['cost_tier']:8s} {modal:25s} {mid:35s} {e.get('display_name','?'):35s} {e.get('provider','?')}")


def show_drift(args_json=False):
    """显示同步差异报告"""
    reg = load_registry()
    if not reg:
        print("❌ 注册表为空，请先运行 sync")
        return

    result, drift = sync_registry()
    if "error" in result:
        print(f"❌ 同步失败: {result['error']}")
        return

    # 汇总
    added = [d for d in drift if d["type"] == "added"]
    updated = [d for d in drift if d["type"] == "updated"]
    removed = [d for d in drift if d["type"] == "removed"]
    unchanged = [d for d in drift if d["type"] == "unchanged"]

    if args_json:
        print(json.dumps({
            "summary": result,
            "drift": drift,
        }, indent=2, ensure_ascii=False))
        return

    print(f"🔄 模型注册表同步报告")
    print(f"   总计: {result['total']} | 新增: {result['added']} | 更新: {result['updated']} | 移除: {result['removed']} | 不变: {result['unchanged']}")
    print()

    if added:
        print(f"🆕 新增模型 ({len(added)}):")
        for d in added:
            print(f"   ✅ {d['model_id']:35s} {d['detail']}")
        print()

    if updated:
        print(f"📝 更新模型 ({len(updated)}):")
        for d in updated:
            print(f"   📌 {d['model_id']:35s} {d['detail']}")
        print()

    if removed:
        print(f"🗑️ 移除模型 ({len(removed)}):")
        for d in removed:
            print(f"   ❌ {d['model_id']:35s} {d['detail']}")
        print()

    if not added and not updated and not removed:
        print(f"✅ 注册表已是最新，无变更")
    else:
        print(f"📁 注册表已更新至: {REGISTRY_FILE}")


def main():
    parser = __import__("argparse").ArgumentParser(
        description="Model Registry Sync — 模型注册表自动同步"
    )
    sub = parser.add_subparsers(dest="command")

    p_sync = sub.add_parser("sync", help="执行同步")
    p_sync.add_argument("--json", action="store_true")

    p_drift = sub.add_parser("drift", help="显示差异报告")
    p_drift.add_argument("--json", action="store_true")

    p_show = sub.add_parser("show", help="显示当前注册表")
    p_show.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "sync":
        result, drift = sync_registry()
        if args.json:
            print(json.dumps({"result": result, "drift": drift}, indent=2, ensure_ascii=False))
        else:
            # 显示结果
            print(f"🔄 模型注册表同步报告")
            print(f"   总计: {result['total']} | 新增: {result['added']} | 更新: {result['updated']} | 移除: {result['removed']} | 不变: {result['unchanged']}")
            print()
            added = [d for d in drift if d["type"] == "added"]
            updated = [d for d in drift if d["type"] == "updated"]
            removed = [d for d in drift if d["type"] == "removed"]
            if added:
                print(f"🆕 新增模型 ({len(added)}):")
                for d in added:
                    print(f"   ✅ {d['model_id']:35s} {d['detail']}")
                print()
            if updated:
                print(f"📝 更新模型 ({len(updated)}):")
                for d in updated:
                    print(f"   📌 {d['model_id']:35s} {d['detail']}")
                print()
            if removed:
                print(f"🗑️ 移除模型 ({len(removed)}):")
                for d in removed:
                    print(f"   ❌ {d['model_id']:35s} {d['detail']}")
                print()
            if not added and not updated and not removed:
                print(f"✅ 注册表已是最新，无变更")
            else:
                print(f"📁 注册表已更新至: {REGISTRY_FILE}")
    elif args.command == "drift":
        show_drift(args_json=args.json)
    elif args.command == "show":
        show_registry(args_json=args.json)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()