#!/usr/bin/env python3
# Version: 0.1.0
"""
model-watchdog.py — 模型健康看门狗 v1.0

核心功能：定期检测所有已配置模型的健康状态，对比上次记录，输出变更报告。
解决两个痛点：
  1. 模型状态是"死"的，坏了没人知道 → 主动 ping + 变更检测
  2. 模型分组没有检测机制 → 分组级别的存活率 + 变更摘要

用法:
  python3 model-watchdog.py check              # 执行一次检测
  python3 model-watchdog.py check --json       # JSON 输出（供 Apple Shortcuts 消费）
  python3 model-watchdog.py check --quiet      # 仅在有变更时输出
  python3 model-watchdog.py report             # 显示上次检测结果
  python3 model-watchdog.py report --json      # JSON 输出
  python3 model-watchdog.py status             # 简要状态摘要
"""

import logging

logger = logging.getLogger(__name__)
import json, os, sys, subprocess, time, re
from pathlib import Path
from datetime import datetime, timezone

STATE_DIR = "/var/minis/shared/.watchdog"
STATE_FILE = f"{STATE_DIR}/model-watchdog-state.json"
HEALTH_FILE = "/var/minis/shared/.model-health.json"
REGISTRY_FILE = "/var/minis/shared/.model-registry.json"
ALERT_LOG = f"{STATE_DIR}/alert-history.jsonl"
MINIS_CLI = "minis-cli"

# 已知模型元数据（seed）—— 手动维护的档位/成本信息
# 新模型自动推断，已知模型用此覆盖
KNOWN_METADATA = {
    "deepseek/deepseek-v4-flash": {"tier": 0, "label": "Flash",  "cost_tier": "low"},
    "deepseek-v4-flash":          {"tier": 0, "label": "Flash",  "cost_tier": "low"},
    "agnes-2.5-pro":              {"tier": 2, "label": "Pro",    "cost_tier": "medium"},
    "agnes-2.5-flash":            {"tier": 0, "label": "Flash",  "cost_tier": "low"},
    "agnes-2.0-flash":            {"tier": 0, "label": "Flash",  "cost_tier": "low"},
    "glm-5.2":                    {"tier": 2, "label": "Pro",    "cost_tier": "medium"},
    "mimo-v2.5":                  {"tier": 1, "label": "Standard", "cost_tier": "low"},
    "cohere-north-mini-code":     {"tier": 1, "label": "Standard", "cost_tier": "low"},
    "dots3-note-prev":            {"tier": 1, "label": "Standard", "cost_tier": "low"},
    "sensenova-u1-fast":          {"tier": 1, "label": "Standard", "cost_tier": "low"},
    "sensenova-u1.5-lite":        {"tier": 1, "label": "Standard", "cost_tier": "low"},
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

PERMANENT_FAILURE = {"not_found", "not_enabled", "invalid_key", "insufficient_balance", "not_logged_in"}
TRANSIENT_FAILURE = {"rate_limited", "timeout", "error", "down"}

# 健康状态优先级（越低越严重）
STATUS_SEVERITY = {
    "ok": 0, "available": 0,
    "unknown": 1,
    "rate_limited": 2, "timeout": 3, "error": 3, "down": 3,
    "not_found": 4, "not_enabled": 4, "invalid_key": 4, "insufficient_balance": 4, "not_logged_in": 4,
    "special_endpoint": 5,  # 图像/视频模型需专用端点，chat 探测必然失败，不算不可用
}

# 图像/视频模型端点识别（从报错消息判断）
SPECIAL_ENDPOINT_PATTERNS = [
    (r"is an image model|Use /v1/images/generations", "image"),
    (r"is a video model|Use /v1/videos", "video"),
]

# 推断档位/成本规则
INFERENCE_RULES = [
    (r'flash|lite|mini', 0, "Flash", "low"),
    (r'claude|gemini.*pro|gpt-5\.5|sonnet', 2, "Pro", "high"),
    (r'gpt-5\.5|glm-5|x-preview', 3, "Max", "high"),
    (r'gpt-4o|qwen.*max|deepseek-v4$', 1, "Standard", "medium"),
]


def load_model_registry():
    """从 .model-registry.json 加载注册表，不存在则从 minis-model-use list 生成"""
    registry = {}
    if os.path.exists(REGISTRY_FILE):
        try:
            raw = json.loads(Path(REGISTRY_FILE).read_text())
            for mid, info in raw.items():
                registry[mid] = {
                    "model_id": mid,
                    "tier": info.get("tier", 1),
                    "label": info.get("label", "Standard"),
                    "provider": info.get("provider", "?"),
                    "cost_tier": info.get("cost_tier", "medium"),
                    "context": info.get("context", 128000),
                    "modalities": info.get("modalities", ["text"]),
                    "description": info.get("description", mid),
                }
            if registry:
                return registry
        except (json.JSONDecodeError, IOError):
            pass

    # 兜底：从 minis-model-use list 实时获取
    # --all 必须：默认只返回 agent loop 分组模型，分组为空时返回 0 个
    try:
        result = subprocess.run(
            ["minis-model-use", "list", "--all"],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        for m in data["data"]["models"]:
            mid = m["model_id"]
            known = KNOWN_METADATA.get(mid, {})
            inferred = _infer_metadata(mid, m.get("modalities", []))
            tier = known.get("tier", inferred["tier"])
            label = known.get("label", inferred["label"])
            cost_tier = known.get("cost_tier", inferred["cost_tier"])
            registry[mid] = {
                "model_id": mid,
                "tier": tier,
                "label": label,
                "provider": m["instance_label"],
                "cost_tier": cost_tier,
                "context": m.get("context_window", 128000),
                "modalities": m.get("modalities", ["text"]),
                "description": m.get("display_name", mid),
            }
        return registry
    except Exception:
        return registry


def _infer_metadata(model_id, modalities):
    for pattern, tier, label, cost in INFERENCE_RULES:
        if re.search(pattern, model_id, re.IGNORECASE):
            return {"tier": tier, "label": label, "cost_tier": cost}
    return {"tier": 1, "label": "Standard", "cost_tier": "medium"}


def ensure_dirs():
    Path(STATE_DIR).mkdir(parents=True, exist_ok=True)


def load_state():
    """返回完整状态（含 last_check / current / changes）"""
    if os.path.exists(STATE_FILE):
        try:
            return json.loads(Path(STATE_FILE).read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def load_current():
    """返回 current 数据（用于变更检测）"""
    state = load_state()
    return state.get("current", {})


def save_state(data):
    Path(STATE_FILE).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def append_alert(alert):
    Path(ALERT_LOG).parent.mkdir(parents=True, exist_ok=True)
    with open(ALERT_LOG, "a") as f:
        f.write(json.dumps(alert, ensure_ascii=False) + "\n")


def load_alerts():
    if not os.path.exists(ALERT_LOG):
        return []
    alerts = []
    with open(ALERT_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    alerts.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return alerts


# ===== 探测 =====

def ping_model(model_id):
    """对单个模型做最小调用探测。解析 minis-model-use 的 JSON stdout。"""
    try:
        result = subprocess.run(
            ["minis-model-use", "run",
             "--model", model_id,
             "--prompt", "ping",
             "--max-tokens", "4",
             "--temperature", "0"],
            capture_output=True, text=True, timeout=30
        )
        # 优先解析 JSON stdout
        try:
            output = json.loads(result.stdout)
            if output.get("ok"):
                return {"status": "ok", "error": None}
            err_msg = output.get("error", {}).get("message", "")
        except json.JSONDecodeError:
            err_msg = result.stderr.strip()[:200]

        # 错误分类
        err_lower = err_msg.lower()
        # 图像/视频模型用 chat 端点探测必然失败，不算不可用
        for pat, etype in SPECIAL_ENDPOINT_PATTERNS:
            if re.search(pat, err_msg, re.IGNORECASE):
                return {"status": "special_endpoint", "error": err_msg[:200],
                        "special_endpoint": etype}
        if "rate limit" in err_lower or "429" in err_msg:
            return {"status": "rate_limited", "error": err_msg[:200]}
        if "not found" in err_lower or "404" in err_msg or "not a valid model" in err_lower:
            return {"status": "not_found", "error": err_msg[:200]}
        if "not enabled" in err_lower:
            return {"status": "not_enabled", "error": err_msg[:200]}
        if "invalid api key" in err_lower or "invalid api" in err_lower:
            return {"status": "invalid_key", "error": err_msg[:200]}
        if "out of credits" in err_lower or "402" in err_msg:
            return {"status": "insufficient_balance", "error": err_msg[:200]}
        if "401" in err_msg or "unauthorized" in err_lower:
            return {"status": "not_logged_in", "error": err_msg[:200]}
        return {"status": "error", "error": err_msg[:200]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": "timeout 30s"}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


FORCE_REPROBE_DAYS = 30  # 月度强制复测：跳过时长超过此值一律重新探测，防永久盲区


def _decide_skip(mid, prev, skip_days):
    """
    True = 本轮跳过该模型。三个条件必须同时成立，缺一个就探测：
      1. 上次状态属于 PERMANENT_FAILURE（invalid_key/not_found/not_logged_in/...，非人工换 key 不会自愈）
      2. 该状态已持续 >= skip_days 天（避免刚失效就跳过，掩盖瞬时抖动误判成永久）
      3. 距上次真实探测 < FORCE_REPROBE_DAYS（月度强制复测，杜绝永久盲区）
    新模型（无历史）永不跳过。
    """
    if skip_days <= 0:
        return False
    p = prev.get(mid)
    if not p:
        return False
    # 上轮被跳过的条目：按其真实旧状态判定，否则 skipped 会每轮反复触发重探
    eff = p.get("prev_status") if p.get("status") == "skipped" else p.get("status")
    if eff not in PERMANENT_FAILURE:
        return False
    probed = p.get("probed_at") or p.get("changed_at")
    if not probed:
        return False
    try:
        dt = datetime.fromisoformat(probed)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    age = (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
    if age >= FORCE_REPROBE_DAYS:
        return False
    return age >= skip_days


def ping_all(skip_days=0, prev=None):
    """
    探测模型，返回 {model_id: {status, error, info}}。
    skip_days>0 时跳过「已知永久失效且持续 skip_days 天」的模型（见 _decide_skip）。
    """
    registry = load_model_registry()
    prev = prev or {}
    results = {}
    skipped = []
    for mid in registry:
        info = registry[mid]
        if _decide_skip(mid, prev, skip_days):
            old = prev[mid]
            skipped.append(mid)
            results[mid] = {
                "status": "skipped",
                "prev_status": old.get("status"),
                "error": old.get("error", ""),
                "tier": info["tier"],
                "label": info["label"],
                "provider": info["provider"],
                "cost_tier": info["cost_tier"],
                "probed_at": old.get("probed_at"),
                "changed_at": old.get("changed_at"),
            }
            continue
        check = ping_model(mid)
        prev_status = (prev.get(mid) or {}).get("status")
        now_iso = datetime.now(timezone.utc).isoformat()
        # changed_at 只在状态真发生变化时重置，否则跳过判定永远算不出「已持续 N 天」
        if prev_status == check["status"]:
            changed_at = (prev.get(mid) or {}).get("changed_at") or now_iso
        else:
            changed_at = now_iso
        results[mid] = {
            "status": check["status"],
            "error": check["error"],
            "tier": info["tier"],
            "label": info["label"],
            "provider": info["provider"],
            "cost_tier": info["cost_tier"],
            "probed_at": now_iso,
            "changed_at": changed_at,
        }
        if check.get("special_endpoint"):
            results[mid]["special_endpoint"] = check["special_endpoint"]
        time.sleep(0.3)
    if skipped:
        print(f"⏭️  跳过 {len(skipped)} 个已知永久失效模型（--skip-dead {skip_days}；"
              f"{FORCE_REPROBE_DAYS} 天后强制复测）", file=sys.stderr)
    return results


# ===== 变更检测 =====

def detect_changes(current, previous):
    """
    对比当前状态和上次记录，返回变更列表。
    每条变更: {model_id, old_status, new_status, change_type, severity}
    change_type: "degraded" | "recovered" | "worsened" | "unchanged"
    """
    changes = []
    all_models = set(list(current.keys()) + list(previous.keys()))

    for mid in sorted(all_models):
        curr = current.get(mid, {})
        prev = previous.get(mid, {})
        old_status = prev.get("status", "unknown")
        new_status = curr.get("status", "unknown")

        old_sev = STATUS_SEVERITY.get(old_status, 99)
        new_sev = STATUS_SEVERITY.get(new_status, 99)

        if new_status == "skipped" or old_status == new_status:
            # skipped = 本轮未探测（沿用上次结论），不构成任何状态变更
            change_type = "unchanged"
            new_status = old_status
        elif new_sev > old_sev:
            change_type = "degraded"
        elif new_sev < old_sev:
            change_type = "recovered"
        elif old_status == "unknown":
            change_type = "first_check"
        else:
            change_type = "unchanged"

        changes.append({
            "model_id": mid,
            "provider": curr.get("provider", "?"),
            "label": curr.get("label", "?"),
            "tier": curr.get("tier", -1),
            "old_status": old_status,
            "new_status": new_status,
            "change_type": change_type,
            "old_severity": old_sev,
            "new_severity": new_sev,
        })

    return changes


# ===== 汇总统计 =====

def summarize(current):
    """按档位和分组生成摘要统计"""
    summary = {
        "total": len(current),
        "by_tier": {},
        "by_provider": {},
        "by_status": {},
        "available_count": 0,
        "unavailable_count": 0,
        "skipped_count": 0,
    }

    for mid, info in current.items():
        status = info.get("status", "unknown")
        tier = info.get("tier", -1)
        provider = info.get("provider", "?")

        # 档位统计
        tier_key = f"L{tier}"
        if tier_key not in summary["by_tier"]:
            summary["by_tier"][tier_key] = {"total": 0, "ok": 0, "issues": []}
        summary["by_tier"][tier_key]["total"] += 1
        if status == "ok":
            summary["by_tier"][tier_key]["ok"] += 1
        else:
            summary["by_tier"][tier_key]["issues"].append({"model": mid, "status": status})

        # Provider 统计
        if provider not in summary["by_provider"]:
            summary["by_provider"][provider] = {"total": 0, "ok": 0, "models": []}
        summary["by_provider"][provider]["total"] += 1
        if status == "ok":
            summary["by_provider"][provider]["ok"] += 1
        summary["by_provider"][provider]["models"].append({"model": mid, "status": status})

        # 状态统计
        if status not in summary["by_status"]:
            summary["by_status"][status] = 0
        summary["by_status"][status] += 1

        # 存活计数
        # special_endpoint 不算不可用——图像/视频模型需要专用端点探测，chat 端点必然失败
        if status == "ok":
            summary["available_count"] += 1
        elif status == "special_endpoint":
            summary["special_endpoint_count"] = summary.get("special_endpoint_count", 0) + 1
        elif status == "skipped":
            # 本轮未探测，不计入异常（否则每轮都虚报几十个「死」模型）
            summary["skipped_count"] = summary.get("skipped_count", 0) + 1
        else:
            summary["unavailable_count"] += 1

    return summary


# ===== 输出格式化 =====

def format_report(changes, summary, quiet=False):
    """生成人类可读的变更报告"""
    lines = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"🐕 Model Watchdog 检测报告 — {now}")
    lines.append(f"")

    # 存活摘要
    alive = summary["available_count"]
    dead = summary["unavailable_count"]
    total = summary["total"]
    skipped = summary.get("skipped_count", 0)
    probe_note = f" | 跳过未探: {skipped}" if skipped else ""
    lines.append(f"📊 存活: {alive}/{total} | 异常: {dead}/{total}{probe_note}")
    lines.append(f"")

    # 档位存活率
    lines.append("🏷️ 各档位存活率:")
    for tier_key in sorted(summary["by_tier"].keys()):
        tier_data = summary["by_tier"][tier_key]
        rate = f"{tier_data['ok']}/{tier_data['total']}"
        bar_len = 10
        filled = int(tier_data["ok"] / max(tier_data["total"], 1) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        lines.append(f"  {tier_key}: {rate} {bar}")
    lines.append(f"")

    # Provider 存活率
    lines.append("🏢 各服务商存活率:")
    for prov in sorted(summary["by_provider"].keys()):
        prov_data = summary["by_provider"][prov]
        rate = f"{prov_data['ok']}/{prov_data['total']}"
        lines.append(f"  {prov:20s}: {rate}")
    lines.append(f"")

    # 变更详情
    active_changes = [c for c in changes if c["change_type"] != "unchanged"]
    if not active_changes and quiet:
        lines.append("✅ 无变更，一切正常")
        return "\n".join(lines)

    if active_changes:
        lines.append("⚠️ 状态变更:")
        for c in active_changes:
            icon = {"degraded": "🔴", "recovered": "🟢", "worsened": "🟠", "first_check": "🆕"}.get(c["change_type"], "⚪")
            arrow = {"degraded": "↓", "recovered": "↑", "worsened": "↓", "first_check": "→"}.get(c["change_type"], "=")
            lines.append(
                f"  {icon} {c['model_id']:35s} "
                f"{c['old_status']:18s} {arrow} {c['new_status']:18s}  [{c['change_type']:10s}]"
            )
    else:
        lines.append("✅ 全部未变更")

    return "\n".join(lines)


def format_report_json(changes, summary):
    """生成 JSON 格式报告（供 Apple Shortcuts 消费）"""
    return json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "changes": changes,
    }, indent=2, ensure_ascii=False)


# ===== CLI =====

def cmd_check(args):
    """执行一次完整检测"""
    ensure_dirs()
    # 先自动同步注册表（从 minis-model-use list 获取最新模型）
    try:
        result = subprocess.run(
            ["python3", "/var/minis/shared/model-registry-sync.py", "sync", "--json"],
            capture_output=True, text=True, timeout=15
        )
    except Exception:
        pass  # 同步失败不影响检测

    print(f"🔍 正在探测模型（skip_dead={getattr(args, 'skip_dead', 0)}天）...", file=sys.stderr)
    prev_state = load_current()
    current = ping_all(skip_days=getattr(args, "skip_dead", 0), prev=prev_state)

    changes = detect_changes(current, prev_state)

    # 更新状态文件
    state = {
        "last_check": datetime.now(timezone.utc).isoformat(),
        "current": current,
        "changes": changes,
    }
    save_state(state)

    summary = summarize(current)

    # 记录告警
    active_changes = [c for c in changes if c["change_type"] in ("degraded", "recovered", "worsened")]
    for c in active_changes:
        alert = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": c["model_id"],
            "provider": c["provider"],
            "change_type": c["change_type"],
            "old_status": c["old_status"],
            "new_status": c["new_status"],
        }
        append_alert(alert)

    if args.json:
        print(format_report_json(changes, summary))
    else:
        print(format_report(changes, summary, quiet=args.quiet))


def cmd_report(args):
    """显示上次检测结果"""
    state = load_state()
    if not state:
        print("❌ 尚无检测记录，请先运行 check")
        return

    current = state.get("current", {})
    changes = state.get("changes", [])
    summary = summarize(current)

    if args.json:
        print(format_report_json(changes, summary))
    else:
        print(format_report(changes, summary))


def cmd_status(args):
    """简要状态摘要"""
    state = load_state()
    if not state:
        print("❌ 尚无检测记录，请先运行 check")
        return

    current = state.get("current", {})
    last = state.get("last_check", "unknown")

    alive = sum(1 for v in current.values() if v.get("status") == "ok")
    total = len(current)
    print(f"🐕 Model Watchdog")
    print(f"   最后检测: {last}")
    print(f"   存活率:   {alive}/{total} ({int(alive/max(total,1)*100)}%)")
    print(f"")
    print(f"   {'模型':35s} {'状态':18s} {'服务商'}")
    print(f"   {'─'*35} {'─'*18} {'─'*12}")
    for mid in sorted(current.keys()):
        info = current[mid]
        status = info.get("status", "?")
        provider = info.get("provider", "?")
        icon = "✅" if status == "ok" else "❌"
        print(f"   {icon} {mid:33s} {status:18s} {provider}")

    # 告警历史
    alerts = load_alerts()
    recent = [a for a in alerts if a.get("change_type") in ("degraded", "worsened")]
    if recent:
        print(f"\n📢 最近告警:")
        for a in recent[-5:]:
            ts = a.get("timestamp", "?")[:16]
            print(f"   🔴 {ts} {a.get('model','?')} {a.get('old_status','?')} → {a.get('new_status','?')} [{a.get('change_type','?')}]")


def cmd_sync(args):
    """手动同步注册表"""
    result = subprocess.run(
        ["python3", "/var/minis/shared/model-registry-sync.py", "sync"] + (["--json"] if args.json else []),
        capture_output=True, text=True, timeout=15
    )
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")


def cmd_registry(args):
    """显示当前注册表"""
    registry = load_model_registry()
    if args.json:
        print(json.dumps({mid: {k: v for k, v in info.items() if k != "description"}
                          for mid, info in sorted(registry.items())},
                         indent=2, ensure_ascii=False))
        return
    print(f"📋 模型注册表 ({len(registry)} 个模型)")
    print(f"")
    print(f"   {'档位':5s} {'成本':8s} {'上下文':>8s} {'模型ID':35s} {'服务商'}")
    print(f"   {'─'*5} {'─'*8} {'─'*8} {'─'*35} {'─'*15}")
    for mid in sorted(registry.keys(), key=lambda x: (registry[x]["tier"], registry[x]["cost_tier"])):
        e = registry[mid]
        print(f"   L{e['tier']:<4d} {e['cost_tier']:8s} {e['context']:>8d} {mid:35s} {e['provider']}")


# 错误码归因透明化：每个 status 对应 语义 / 判定依据 / 应对建议
# 每个 status 对应：语义 / 判定依据（触发关键词）/ 应对建议（人工干预 or 自愈）
STATUS_REASON = {
    "ok":                 ("✅ 完全可用",               "ping 成功返回内容",                 "无需处理"),
    "available":          ("✅ 完全可用（别名）",       "ping 成功返回内容",                 "无需处理"),
    "unknown":            ("❓ 未知状态",              "首次探测或未记录",                 "下轮探测自动判定"),
    "rate_limited":       ("⏳ 短期限流，会自愈",        "响应含 'rate limit' / 429",        "分钟级自愈；批量脚本需 30-60s 间隔"),
    "timeout":            ("⏳ 网络抖动/上游慢",        "请求 30s 超时",                    "重试即可；连续 timeout 才考虑下线"),
    "error":              ("⚠️  未分类错误",           "HTTP 200 但 body 报非预期错",       "看 error 字段定位；可能是 5xx/SSL"),
    "down":               ("⚠️  服务整体不可用",       "连接失败/DNS/服务宕机",             "小时级自愈；跨时段看是否恢复"),
    "not_found":          ("❌ 模型 ID 不存在/已下线",  "'not found' / 404 / not a valid model", "永久失效；从 GLOBAL §五「已下线」加名单"),
    "not_enabled":        ("🔒 Key 有效但模型未开通",   "'not enabled' / 400 Model not enabled", "该 Key 全线可用但此模型未开通；Key 本身不废"),
    "invalid_key":        ("❌ Key 已失效或被吊销",     "'Invalid API key' / 401",          "永久失效；需换 key 或删除；GLOBAL §五「API Key 失效」"),
    "insufficient_balance":("💰 余额不足（免费档耗尽）", "'out of credits' / 402",           "永久失效；等额度重置或换 key；GLOBAL §五「限速中」"),
    "not_logged_in":      ("🔐 需 OAuth/登录（非 API Key）", "'not logged in' / auth required",  "永久失效；不是 Key 问题，是登录方式不对"),
    "special_endpoint":   ("🖼️  需专用端点（非 chat）", "'is an image/video model'",         "非故障：图像/视频模型不能走 /v1/chat，需专用端点"),
    "skipped":            ("⏭️  本轮跳过",            "已知永久失效 >= N 天",             "按 skip-dead 逻辑跳过；每 30 天强制复测"),
}


def cmd_explain(args):
    """显示错误码归因表（人类可读）。借鉴 trae-signin README 明说服务端 API 缺陷。"""
    if args.json:
        print(json.dumps({k: {"label": v[0], "evidence": v[1], "action": v[2]} for k, v in STATUS_REASON.items()},
                         indent=2, ensure_ascii=False))
        return
    print("📖 错误码归因表（模型状态 → 语义 / 判定依据 / 应对建议）")
    print("")
    print("  ⚠️  注意：错误码是「分类」不是「真相」。")
    print("     例如 rate_limited 可能是短时流控、账号池打满、或 key 被限流三种情况，看具体 error 字段定位。")
    print("")
    print(f"  {'状态':<20s} {'语义':<28s} {'判定依据':<35s} 应对建议")
    print(f"  {'─'*20} {'─'*28} {'─'*35} {'─'*30}")
    for status, (label, evidence, action) in STATUS_REASON.items():
        print(f"  {status:<20s} {label:<28s} {evidence:<35s} {action}")
    print("")
    print("📌 说明：错误码是分类不是真相——内部 code 已归一化为人类可读状态。")


def main():
    parser = __import__("argparse").ArgumentParser(
        description="Model Watchdog — 模型健康看门狗"
    )
    sub = parser.add_subparsers(dest="command")

    p_check = sub.add_parser("check", help="执行一次检测")
    p_check.add_argument("--json", action="store_true", help="JSON 输出")
    p_check.add_argument("--quiet", action="store_true", help="仅在有变更时输出")
    p_check.add_argument("--skip-dead", type=int, default=0, metavar="DAYS",
                         help=f"跳过已连续失效>=DAYS天的永久失效模型（invalid_key/not_found 等）；"
                              f"每 {FORCE_REPROBE_DAYS} 天强制复测。定时任务建议 3")

    p_report = sub.add_parser("report", help="显示上次检测结果")
    p_report.add_argument("--json", action="store_true")

    sub.add_parser("status", help="简要状态")

    p_sync = sub.add_parser("sync", help="同步模型注册表")
    p_sync.add_argument("--json", action="store_true")

    p_reg = sub.add_parser("registry", help="显示当前注册表")
    p_reg.add_argument("--json", action="store_true")

    p_explain = sub.add_parser("explain", help="显示错误码归因表（14 种状态的语义/依据/建议）")
    p_explain.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.command == "check":
        cmd_check(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "registry":
        cmd_registry(args)
    elif args.command == "explain":
        cmd_explain(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()