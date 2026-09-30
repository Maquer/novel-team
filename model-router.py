#!/usr/bin/env python3
# Version: 0.1.0
"""
model-router.py — Minis 多模型智能路由引擎 v1.0

核心功能：任务复杂度感知 + 模型健康追踪 + 自动降级路由
借鉴 Index（lmnr-ai/index）的 Flash/Pro 分层路由思路，适配 Minis 生态。

三层架构：
  1. Model Registry  — 模型注册表，按能力/成本分四档（L0-L3）
  2. Health Monitor  — 持久化健康状态，自动探测 + 错误分类
  3. Complexity Router — 文本信号 + Skill 映射 → 复杂度档位 → 路由决策

用法:
  python3 model-router.py route "写一篇小红书笔记"    # 仅做路由决策
  python3 model-router.py route --run "写一篇小红书笔记"  # 路由 + 调用模型
  python3 model-router.py status                       # 查看所有模型健康状态
  python3 model-router.py ping                        # 探测所有模型健康
  python3 model-router.py ping --model deepseek-v4-flash  # 探测单个模型
  python3 model-router.py health set deepseek-v4-flash ok  # 手动设置健康状态
  python3 model-router.py health clear               # 清除所有健康记录
  python3 model-router.py registry                   # 查看模型注册表
"""

import logging

logger = logging.getLogger(__name__)
import json, os, sys, re, subprocess, argparse, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

HEALTH_FILE = "/var/minis/shared/.model-health.json"
REGISTRY_FILE = "/var/minis/shared/.model-registry.json"


# ===== 模型注册表（四档分层） =====

# L0: Flash Tier — 简单快速任务（问候/基本问答/文件操作/简单转换）
# L1: Standard Tier — 中等复杂度（写作/代码生成/内容创作/一般分析）
# L2: Pro Tier — 复杂任务（深度分析/架构设计/多步推理/决策评估/调试优化）
# L3: Max Tier — 重负载任务（长上下文/跨领域综合/多轮规划/系统性研究）

HARDCODED_METADATA = {
    # L0 — Flash Tier
    "deepseek-v4-flash": {
        "tier": 0, "label": "Flash", "qualified": "deepseek/deepseek-v4-flash",
        "context": 1048576, "provider": "OpenRouter",
        "cost_tier": "low", "modalities": ["text"], "tags": ["fast", "reliable"],
        "description": "DeepSeek V4 Flash（⚠️ 偶尔限速）"
    },
    "gpt-4o-mini": {
        "tier": 0, "label": "Flash", "qualified": "gpt-4o-mini",
        "context": 128000, "provider": "OpenAI",
        "cost_tier": "low", "modalities": ["text", "image_input"], "tags": ["fast"],
        "description": "OpenAI GPT-4o Mini，轻量快速"
    },
    "sensenova-6.7-flash-lite": {
        "tier": 0, "label": "Flash", "qualified": "sensenova-6.7-flash-lite",
        "context": 128000, "provider": "sensenova",
        "cost_tier": "low", "modalities": ["text", "image_input"], "tags": ["fast"],
        "description": "Sensenova Flash Lite，轻量快速"
    },
    "agnes-2.5-flash": {
        "tier": 0, "label": "Flash", "qualified": "agnes-2.5-flash",
        "context": 128000, "provider": "OpenAI 5",
        "cost_tier": "low", "modalities": ["text"], "tags": ["fast", "reliable"],
        "description": "Agnes 2.5 Flash（OpenAI 5），快速响应"
    },
    "agnes-2.0-flash": {
        "tier": 0, "label": "Flash", "qualified": "agnes-2.0-flash",
        "context": 128000, "provider": "OpenAI 5",
        "cost_tier": "low", "modalities": ["text"], "tags": ["fast"],
        "description": "Agnes 2.0 Flash（OpenAI 5）"
    },

    # L1 — Standard Tier
    "deepseek-v4": {
        "tier": 1, "label": "Standard", "qualified": "deepseek-v4",
        "context": 128000, "provider": "OpenAI 2",
        "cost_tier": "medium", "modalities": ["text"], "tags": ["balanced"],
        "description": "DeepSeek V4 标准版（OpenAI 2 通道）"
    },
    "deepseek/deepseek-v4": {
        "tier": 1, "label": "Standard", "qualified": "deepseek/deepseek-v4",
        "context": 128000, "provider": "OpenRouter",
        "cost_tier": "medium", "modalities": ["text"], "tags": ["balanced"],
        "description": "DeepSeek V4 标准版（OpenRouter 通道）"
    },
    "qwen-3-max": {
        "tier": 1, "label": "Standard", "qualified": "qwen-3-max",
        "context": 128000, "provider": "OpenAI 2",
        "cost_tier": "medium", "modalities": ["text"], "tags": ["balanced"],
        "description": "Qwen 3 Max，中文强"
    },
    "sensenova-6.7": {
        "tier": 1, "label": "Standard", "qualified": "sensenova-6.7",
        "context": 128000, "provider": "sensenova",
        "cost_tier": "medium", "modalities": ["text"], "tags": ["balanced"],
        "description": "Sensenova 6.7 标准版"
    },

    # L2 — Pro Tier
    "anthropic/claude-sonnet-4-6": {
        "tier": 2, "label": "Pro", "qualified": "anthropic/claude-sonnet-4-6",
        "context": 1000000, "provider": "OpenRouter",
        "cost_tier": "high", "modalities": ["text", "image_input"], "tags": ["reasoning", "vision"],
        "description": "Claude Sonnet 4.6，深度推理"
    },
    "google/gemini-2.5-pro": {
        "tier": 2, "label": "Pro", "qualified": "google/gemini-2.5-pro",
        "context": 1048576, "provider": "OpenRouter",
        "cost_tier": "high", "modalities": ["text", "image_input", "pdf_input", "audio_input", "video_input"], "tags": ["reasoning", "vision", "multimodal"],
        "description": "Gemini 2.5 Pro，多模态强"
    },
    "agnes-2.5-pro": {
        "tier": 2, "label": "Pro", "qualified": "agnes-2.5-pro",
        "context": 128000, "provider": "OpenAI 5",
        "cost_tier": "medium", "modalities": ["text"], "tags": ["reasoning", "reliable"],
        "description": "Agnes 2.5 Pro（OpenAI 5），当前最强可用模型"
    },
    "glm-5.2": {
        "tier": 2, "label": "Pro", "qualified": "glm-5.2",
        "context": 256000, "provider": "OpenCode",
        "cost_tier": "medium", "modalities": ["text"], "tags": ["reasoning", "cn"],
        "description": "GLM-5.2（OpenCode），中文强"
    },

    # L3 — Max Tier
    "gpt-5.5": {
        "tier": 3, "label": "Max", "qualified": "gpt-5.5",
        "context": 1050000, "provider": "OpenAI 2",
        "cost_tier": "high", "modalities": ["text", "image_input", "pdf_input"], "tags": ["long-context", "reasoning"],
        "description": "GPT-5.5，超长上下文 1.05M"
    },
    "x-preview-f-free": {
        "tier": 3, "label": "Max", "qualified": "x-preview-f-free",
        "context": 1000000, "provider": "OpenCode-Free",
        "cost_tier": "low", "modalities": ["text", "image_input", "video_input"], "tags": ["free"],
        "description": "GLM-5 Preview，免费通道"
    },
}


# ===== 动态注册表加载 =====

_REGISTRY = {}


def refresh_registry():
    """
    从 .model-registry.json 动态加载模型注册表。
    JSON 文件由 model-registry-sync.py 从 minis-model-use list 实时生成。
    硬编码元数据（tags/description）作为补充合并。
    注册表文件不存在时，降级为最小可用集。
    """
    global _REGISTRY
    if os.path.exists(REGISTRY_FILE):
        try:
            raw = json.loads(Path(REGISTRY_FILE).read_text())
        except (json.JSONDecodeError, IOError):
            raw = {}

        if raw:
            registry = {}
            for mid, entry in raw.items():
                meta = HARDCODED_METADATA.get(mid, {})
                tier = entry.get("tier", 1)
                registry[mid] = {
                    "model_id": mid,
                    "qualified": entry.get("qualified", mid),
                    "tier": tier,
                    "label": entry.get("label", "Standard"),
                    "provider": entry.get("provider", "?"),
                    "cost_tier": entry.get("cost_tier", "medium"),
                    "context": entry.get("context", 128000),
                    "modalities": entry.get("modalities", ["text"]),
                    "tags": meta.get("tags", (["fast"] if tier <= 0 else ["balanced"] if tier == 1 else ["reasoning"] if tier == 2 else ["long-context"])),
                    "description": meta.get("description", f"{entry.get('display_name', mid)}（{entry.get('provider', '?')}，{entry.get('label', 'Standard')}）"),
                }
            _REGISTRY = registry
            return _REGISTRY

    # 兜底：注册表文件不存在/空时
    _REGISTRY = {
        "agnes-2.5-pro": {
            "model_id": "agnes-2.5-pro",
            "qualified": "agnes-2.5-pro",
            "tier": 2, "label": "Pro", "provider": "OpenAI 5",
            "cost_tier": "medium", "context": 128000,
            "modalities": ["text"], "tags": ["reasoning", "reliable"],
            "description": "Agnes 2.5 Pro（OpenAI 5），当前最强可用模型"
        }
    }
    return _REGISTRY


def get_registry():
    """获取当前注册表（首次调用时自动加载）"""
    global _REGISTRY
    if not _REGISTRY:
        return refresh_registry()
    return _REGISTRY


# 模块加载时初始化
refresh_registry()


# ===== 任务复杂度信号 =====

COMPLEXITY_SIGNALS = {
    # L0 信号（简单任务）
    0: {
        "keywords": ["简单", "就行", "快点", "随便", "就行", "简要", "一句话", "简短",
                     "问候", "打招呼", "确认", "列出", "看看", "查一下",
                     "打开", "关闭", "删除", "重命名", "移动"],
        "patterns": [
            r'^(你好|hi|hello|早上好|晚上好)',
            r'^(列出|列出所有|list|ls)\b',
            r'^(是|对|好|嗯|ok|好的)$',
        ],
    },
    # L1 信号（中等复杂度）
    1: {
        "keywords": ["写", "生成", "总结", "改写", "翻译", "转换", "提取", "整理",
                     "创建", "新建", "添加", "修改", "更新", "归档",
                     "写文章", "写笔记", "写代码", "写脚本",
                     "分析", "对比", "比较",
                     "小红书", "公众号", "抖音", "文案"],
        "patterns": [
            r'^[写生创总译]\w{1,6}\s',
        ],
    },
    # L2 信号（复杂任务）
    2: {
        "keywords": ["分析", "设计", "架构", "评估", "对比", "选择", "决策",
                     "bug", "fix", "debug", "调试", "优化", "重构",
                     "方案", "策略", "路线", "规划", "计划",
                     "深度分析", "详细分析", "全面", "综合"],
        "patterns": [],
    },
    # L3 信号（重负载任务）
    3: {
        "keywords": ["深度", "全面", "详细", "系统", "跨领域", "综合",
                     "长期", "战略", "路线", "路线图", "roadmap",
                     "五层", "道法术器势", "框架", "体系"],
        "patterns": [
            r'(深度|全面|系统(性)?|长期|战略|跨领域)',
        ],
    },
}

# Skill → 复杂度档位映射
SKILL_TIER_MAP = {
    "karpathy-claude": 1,
    "ponytail": 1,
    "explanation-skill": 1,
    "hai-bao-she-ji": 1,
    "gongzhonghao-publish": 2,
    "nuwa-skill": 2,
    "bao-kuai-xie-zuo": 1,
    "nei-rong-zhuan-hua": 1,
    "wu-ceng-jue-ce": 3,
    "grill-me": 1,
    "airtap": 0,
    "skill-creator": 2,
    "darwin-skill": 2,
}


# ===== 健康状态管理 =====

def load_health():
    if os.path.exists(HEALTH_FILE):
        try:
            return json.loads(Path(HEALTH_FILE).read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_health(data):
    Path(HEALTH_FILE).write_text(json.dumps(data, indent=2, ensure_ascii=False))

def get_health(model_id):
    h = load_health()
    return h.get(model_id, {"status": "unknown", "last_check": None})

def set_health(model_id, status, error_msg=None):
    h = load_health()
    now = datetime.now(timezone.utc).isoformat()
    h[model_id] = {
        "status": status,
        "last_check": now,
        "error": error_msg or None,
    }
    save_health(h)

def clear_health():
    save_health({})

# 永久性问题状态（不会自动恢复，陈旧数据也不重新纳入）
PERMANENT_FAILURE = {"not_found", "not_enabled", "invalid_key", "insufficient_balance", "not_logged_in"}
# 可能恢复的问题（超时可能恢复，限速可能解除）
TRANSIENT_FAILURE = {"rate_limited", "timeout", "error", "down"}

def is_model_available(model_id):
    h = get_health(model_id)
    status = h.get("status", "unknown")
    if status in ("ok", "available"):
        return True
    if status in PERMANENT_FAILURE:
        # 永久性问题不随时间自动恢复，直接排除
        return False
    if status in TRANSIENT_FAILURE:
        last_check = h.get("last_check")
        if last_check:
            try:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(last_check)
                if age > timedelta(hours=2):
                    return None  # 超时2h以上，尝试重新检测
            except ValueError:
                pass
        return False
    return None  # unknown, need check

def get_available_models(tier=None):
    available = []
    for mid, info in get_registry().items():
        if tier is not None and info["tier"] != tier:
            continue
        avail = is_model_available(mid)
        if avail:
            available.append(mid)
        elif avail is None:
            # Unknown/stale — include with warning, the router will try first
            available.append(mid)
    return available


# ===== 复杂度评估 =====

def estimate_complexity(text, skill=None, user_tier=None):
    """
    估算任务复杂度档位 (0-3)。
    返回 (tier, score, signals)。
    """
    if user_tier is not None:
        return (user_tier, 100, ["user_override"])

    score = 0
    signals = []
    text_lower = text.lower()

    # Skill 映射优先
    if skill and skill in SKILL_TIER_MAP:
        base = SKILL_TIER_MAP[skill]
        signals.append(f"skill:{skill}→L{base}")

    # 关键词匹配（从 L3 到 L0 倒序，高优先级信号覆盖低优先级）
    tier_scores = []
    for tier in sorted(COMPLEXITY_SIGNALS.keys(), reverse=True):
        rules = COMPLEXITY_SIGNALS[tier]
        matched_keywords = []
        matched_patterns = []

        for kw in rules["keywords"]:
            if kw.lower() in text_lower:
                matched_keywords.append(kw)

        for pat in rules["patterns"]:
            if re.search(pat, text_lower):
                matched_patterns.append(pat)

        if matched_keywords or matched_patterns:
            weight = (tier + 1) * 10  # L3=40, L2=30, L1=20, L0=10
            count = len(matched_keywords) + len(matched_patterns)
            tier_scores.append((tier, weight * min(count, 3),
                               matched_keywords, matched_patterns))

    if tier_scores:
        # 取最高档位的分数作为基准
        best_tier = tier_scores[0][0]
        best_score = tier_scores[0][1]
        for tier, sc, kws, pats in tier_scores:
            signals.append(f"L{tier}:{','.join(kws[:3])}")
        # Skill 作为最低基线：关键词只能升高，不能降低
        if skill and skill in SKILL_TIER_MAP:
            best_tier = max(best_tier, SKILL_TIER_MAP[skill])
        return (best_tier, int(best_score), signals)

    # 无匹配信号 → 使用 Skill 基线或默认 L1
    if skill and skill in SKILL_TIER_MAP:
        return (SKILL_TIER_MAP[skill], 20, signals + ["skill_baseline"])
    return (1, 10, ["default_L1"])


# ===== 路由决策 =====

def route(task_text, skill=None, user_tier=None, system_prompt=None, messages=None):
    """
    路由决策。返回路由结果 dict。
    """
    tier, score, signals = estimate_complexity(task_text, skill, user_tier)

    # 确定 fallback chain：从目标档位开始，向下降级
    candidates = []
    for t in range(tier, -1, -1):
        for mid, info in get_registry().items():
            if info["tier"] != t:
                continue
            avail = is_model_available(mid)
            if avail is False:
                continue
            candidates.append({
                "model_id": mid,
                "qualified": info["qualified"],
                "tier": t,
                "label": info["label"],
                "provider": info["provider"],
                "context": info["context"],
                "modalities": info["modalities"],
                "cost_tier": info["cost_tier"],
                "health": "ok" if avail else "unknown",
                "description": info["description"],
            })

    # 排序：健康优先（ok > unknown > 其他），同健康按成本（low > medium > high）
    HEALTH_PRIORITY = {"ok": 0, "available": 0, "unknown": 1, "fallback": 2}
    COST_PRIORITY = {"low": 0, "medium": 1, "high": 2}
    candidates.sort(key=lambda c: (
        HEALTH_PRIORITY.get(c["health"], 3),
        COST_PRIORITY.get(c["cost_tier"], 1),
        c["model_id"]
    ))

    if not candidates:
        # 最终兜底：强行用 agnes-2.5-pro
        fallback = get_registry()["agnes-2.5-pro"]
        candidates.append({
            "model_id": "agnes-2.5-pro",
            "qualified": fallback["qualified"],
            "tier": 2, "label": "Pro",
            "provider": fallback["provider"],
            "context": fallback["context"],
            "modalities": fallback["modalities"],
            "cost_tier": fallback["cost_tier"],
            "health": "fallback",
            "description": fallback["description"],
        })

    selected = candidates[0]
    result = {
        "selected_model": selected,
        "estimated_tier": tier,
        "complexity_score": score,
        "signals": signals,
        "candidates": candidates,
        "fallback_chain": [c["model_id"] for c in candidates],
        "routed_at": datetime.now(timezone.utc).isoformat(),
    }
    return result


# ===== 模型探测 =====

def ping_model(model_id):
    """对单个模型做最小调用探测健康状态"""
    try:
        result = subprocess.run(
            ["minis-model-use", "run",
             "--model", model_id,
             "--prompt", "ping",
             "--max-tokens", "4",
             "--temperature", "0"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            set_health(model_id, "ok")
            return {"model_id": model_id, "status": "ok"}
        else:
            stderr = result.stderr.strip()
            # 分类错误
            if "rate limit" in stderr.lower() or "429" in stderr:
                status = "rate_limited"
            elif "not found" in stderr.lower() or "404" in stderr or "not a valid model" in stderr.lower():
                status = "not_found"
            elif "not enabled" in stderr.lower() or "model not enabled" in stderr.lower():
                status = "not_enabled"
            elif "invalid api key" in stderr.lower() or "invalid api" in stderr.lower():
                status = "invalid_key"
            elif "out of credits" in stderr.lower() or "402" in stderr:
                status = "insufficient_balance"
            elif "401" in stderr or "unauthorized" in stderr.lower():
                status = "not_logged_in"
            else:
                status = "error"
            set_health(model_id, status, stderr[:200])
            return {"model_id": model_id, "status": status, "error": stderr[:200]}
    except subprocess.TimeoutExpired:
        set_health(model_id, "timeout")
        return {"model_id": model_id, "status": "timeout"}
    except Exception as e:
        set_health(model_id, "error", str(e)[:200])
        return {"model_id": model_id, "status": "error", "error": str(e)[:200]}


def ping_all():
    results = []
    for mid in get_registry():
        results.append(ping_model(mid))
        time.sleep(0.5)  # 避免速率限制
    return results


# ===== CLI =====

def print_status():
    h = load_health()
    print(f"{'模型':35s} {'档位':6s} {'状态':18s} {'最后检查':25s} {'错误信息'}")
    print("-" * 120)
    for mid, info in sorted(get_registry().items(), key=lambda x: (x[1]["tier"], x[1]["cost_tier"])):
        health = h.get(mid, {})
        status = health.get("status", "unknown")
        last = health.get("last_check", "never")[:19] if health.get("last_check") else "never"
        err = health.get("error", "") or ""
        label = f"L{info['tier']} {info['label']}"
        status_display = status if status != "unknown" else "?"
        print(f"{mid:35s} {label:6s} {status_display:18s} {last:25s} {err[:30]}")


def print_registry():
    print(f"{'模型':35s} {'档位':8s} {'上下文':12s} {'成本':8s} {'模态':20s} 描述")
    print("-" * 120)
    for mid, info in sorted(get_registry().items(), key=lambda x: (x[1]["tier"], x[1]["cost_tier"])):
        modalities_str = "+".join(info["modalities"][:3])
        ctx_str = f"{info['context']/1000:.0f}K" if info['context'] < 1000000 else f"{info['context']/1000000:.1f}M"
        print(f"{mid:35s} L{info['tier']} {info['label']:5s} {ctx_str:12s} {info['cost_tier']:8s} {modalities_str:20s} {info['description'][:50]}")


def cmd_route(args):
    text = args.text or sys.stdin.read().strip()

    # --model 覆盖路由：直接用指定模型
    if getattr(args, "model", None) and getattr(args, "tools", None):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tool_emulation", "/var/minis/shared/tool-emulation.py")
        te = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(te)
        try:
            tools = json.loads(args.tools)
        except json.JSONDecodeError as e:
            print(f"[错误] --tools JSON 解析失败: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[Tool] {args.model} (指定) | {len(tools)} 工具", file=sys.stderr)
        resp = te.run_with_tools(prompt=text, tools=tools, model=args.model, verbose=True)
        print(json.dumps(resp, indent=2, ensure_ascii=False))
        return

    result = route(
        task_text=text,
        skill=args.skill,
        user_tier=args.tier,
    )

    # --tools: 走 tool-emulation 多轮循环
    if getattr(args, 'tools', None):
        try:
            tools = json.loads(args.tools)
        except json.JSONDecodeError as e:
            print(f"[错误] --tools JSON__: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(tools, list) or not tools:
            print("[错误] --tools 非空 JSON 数组", file=sys.stderr)
            sys.exit(1)

        import importlib.util
        spec = importlib.util.spec_from_file_location("tool_emulation", "/var/minis/shared/tool-emulation.py")
        te = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(te)

        sel = result["selected_model"] if args.run else (result["candidates"][0] if result["candidates"] else None)
        if not sel:
            print("[错误] 无可用模型", file=sys.stderr)
            sys.exit(1)

        print(f"[Tool] {sel['model_id']} | {len(tools)} __", file=sys.stderr)
        resp = te.run_with_tools(prompt=text, tools=tools, model=sel["qualified"], verbose=True)
        print(json.dumps(resp, indent=2, ensure_ascii=False))
        return

    if not args.run:
        # 仅路由决策，打印结果
        sel = result["selected_model"]
        print(f"路由结果:")
        print(f"  任务文本: {text[:80]}")
        print(f"  估算档位: L{result['estimated_tier']} (score={result['complexity_score']})")
        print(f"  信号: {', '.join(result['signals'])}")
        print(f"  选中模型: {sel['model_id']} (L{sel['tier']} {sel['label']}, {sel['provider']})")
        print(f"  健康状态: {sel['health']}")
        print(f"  Fallback链: {' → '.join(result['fallback_chain'])}")
        print(f"\n完整 JSON:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # --run 模式：调用选中的模型
    sel = result["selected_model"]
    print(f"[路由] L{result['estimated_tier']} → {sel['model_id']} ({sel['provider']})", file=sys.stderr)

    input_path = Path(f"/tmp/model-router-input-{int(time.time())}.json")
    input_data = {
        "messages": [{"role": "user", "content": text}],
    }
    input_path.write_text(json.dumps(input_data))

    cmd = [
        "minis-model-use", "run",
        "--model", sel["qualified"],
        "--input", str(input_path),
        "--temperature", "0.7",
    ]

    result_proc = subprocess.run(cmd, capture_output=True, text=True)
    input_path.unlink(missing_ok=True)

    if result_proc.returncode != 0:
        stderr = result_proc.stderr.strip()
        # 更新健康状态
        set_health(sel["model_id"], "error", stderr[:200])
        # 尝试 fallback
        if len(result["candidates"]) > 1:
            print(f"[模型调用失败] {sel['model_id']}: {stderr[:100]}", file=sys.stderr)
            print(f"[尝试 fallback]", file=sys.stderr)
            for candidate in result["candidates"][1:]:
                cmd2 = [
                    "minis-model-use", "run",
                    "--model", candidate["qualified"],
                    "--input", str(input_path),
                    "--temperature", "0.7",
                ]
                result_proc2 = subprocess.run(cmd2, capture_output=True, text=True)
                if result_proc2.returncode == 0:
                    print(result_proc2.stdout, end="")
                    set_health(candidate["model_id"], "ok")
                    return
                else:
                    set_health(candidate["model_id"], "error", result_proc2.stderr[:200])
                    print(f"[fallback 失败] {candidate['model_id']}: {result_proc2.stderr[:100]}", file=sys.stderr)
            print(f"[所有模型均调用失败]", file=sys.stderr)
        print(stderr, file=sys.stderr)
        sys.exit(1)
    else:
        print(result_proc.stdout, end="")
        set_health(sel["model_id"], "ok")


def cmd_status(_args):
    refresh_registry()
    print_status()

def cmd_ping(args):
    if args.model:
        r = ping_model(args.model)
        print(json.dumps(r, indent=2, ensure_ascii=False))
    else:
        print("正在探测所有模型（约需 30-60 秒）...")
        results = ping_all()
        for r in results:
            print(f"  {r['model_id']:35s} → {r['status']}")
        print(f"\n完整结果:")
        print(json.dumps(results, indent=2, ensure_ascii=False))

def cmd_health(args):
    if args.subcommand == "set":
        set_health(args.model, args.status, args.error)
        print(f"已设置 {args.model} 状态为 {args.status}")
    elif args.subcommand == "clear":
        clear_health()
        print("已清除所有健康记录")

def cmd_registry(_args):
    print_registry()


def cmd_sync(_args):
    """强制刷新注册表：先调用 model-registry-sync.py 同步，再重新加载"""
    print("🔄 正在同步模型注册表...")
    result = subprocess.run(
        ["python3", "/var/minis/shared/model-registry-sync.py", "sync"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(result.stderr, file=sys.stderr)
    refresh_registry()
    print(f"✅ 注册表已刷新，当前 {len(get_registry())} 个模型")


def main():
    parser = argparse.ArgumentParser(description="Minis 多模型智能路由引擎")
    subparsers = parser.add_subparsers(dest="command")

    # route
    p_route = subparsers.add_parser("route", help="路由决策")
    p_route.add_argument("text", nargs="?", help="任务文本")
    p_route.add_argument("--skill", help="关联的 Skill 名称")
    p_route.add_argument("--tier", type=int, choices=[0, 1, 2, 3], help="用户手动指定档位")
    p_route.add_argument("--run", action="store_true", help="路由后直接调用模型")
    p_route.add_argument("--tools", help="OpenAI tools JSON（走 tool-emulation 多轮循环）")
    p_route.add_argument("--model", help="跳过路由，直接指定模型")
    p_route.set_defaults(func=cmd_route)

    # status
    p_status = subparsers.add_parser("status", help="查看模型健康状态")
    p_status.set_defaults(func=cmd_status)

    # ping
    p_ping = subparsers.add_parser("ping", help="探测模型健康")
    p_ping.add_argument("--model", help="指定单个模型（默认全部）")
    p_ping.set_defaults(func=cmd_ping)

    # health
    p_health = subparsers.add_parser("health", help="健康状态管理")
    p_health_sub = p_health.add_subparsers(dest="subcommand")
    ph_set = p_health_sub.add_parser("set", help="手动设置模型状态")
    ph_set.add_argument("model", help="模型 ID")
    ph_set.add_argument("status", help="状态值")
    ph_set.add_argument("--error", help="错误信息")
    ph_set.set_defaults(func=cmd_health)
    ph_clear = p_health_sub.add_parser("clear", help="清除所有记录")
    ph_clear.set_defaults(func=cmd_health)

    # registry
    p_reg = subparsers.add_parser("registry", help="查看模型注册表")
    p_reg.set_defaults(func=cmd_registry)

    # sync
    p_sync = subparsers.add_parser("sync", help="同步模型注册表（从 minis-model-use list）")
    p_sync.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)
    args.func(args)


if __name__ == "__main__":
    main()