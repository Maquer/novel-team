#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
logic-review.py — 小说章节逻辑审查门禁
检查项：时代词汇/境界能力越界/神器感应/时间线矛盾/位置矛盾/门派设定冲突/句子重复/剑种连贯
"""
import json, re, sys, argparse
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT / "config" / "logic-rules.json"
# FIX 2026-10-04：移除天命/my-novel 写死路径（会污染所有项目）。
# 世界/角色数据由调用方按项目注入，路径改为可选参数，默认回退空结构。
WORLD_PATH = None  # 由 --world-pack 参数或项目上下文动态指定
CHARS_PATH = None  # 由 --chars 参数或项目上下文动态指定


def load_rules():
    return json.load(open(RULES_PATH, encoding="utf-8"))["rules"]


def load_world(path=None):
    """读取世界包。path 优先，回退到全局 WORLD_PATH，均无则返回空。"""
    p = Path(path) if path else (WORLD_PATH if WORLD_PATH else None)
    if not p or not Path(p).exists():
        return {"entries": {}}
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {"entries": {}}


def load_chars(path=None):
    """读取角色档案。path 优先，回退到全局 CHARS_PATH，均无则返回空。"""
    p = Path(path) if path else (CHARS_PATH if CHARS_PATH else None)
    if not p or not Path(p).exists():
        return {"characters": []}
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {"characters": []}


def strip_meta(content):
    """去掉 frontmatter 与 V/I/C/E 契约块，只留正文"""
    parts = content.split("---", 2)
    body = parts[2] if len(parts) >= 3 else content
    body = re.sub(r"^# .*\n", "", body)
    return body


def rule_era_words(text, cfg):
    issues = []
    for w in cfg["words"]:
        for m in re.finditer(re.escape(w), text):
            ctx = text[max(0, m.start()-15):m.end()+15].replace("\n", " ")
            issues.append({
                "rule": "时代词汇", "severity": cfg["severity"],
                "word": w, "context": f"...{ctx}..."
            })
    return issues


def detect_subject_realm(sentence, chars):
    """从句子中的角色名推断其境界"""
    for c in chars:
        if c["name"] in sentence:
            return c["name"], c.get("realm", "")
    return None, None


def rule_realm_capability(text, cfg, chars, world):
    """检测：淬体/炼气期不应具备筑基以上能力"""
    issues = []
    low = set(cfg["groups_low_forbidden"])
    # 按句子切
    for seg in re.split(r"[。！？\n]", text):
        if not seg.strip():
            continue
        name, realm = detect_subject_realm(seg, chars)
        if not realm:
            continue
        # 淬体期禁用：御剑飞行/神识/灵气外放/凌空/瞬移
        forbidden = low if "淬体" in realm or "炼气" in realm else set()
        for word in forbidden:
            if word in seg:
                issues.append({
                    "rule": "境界能力越界", "severity": cfg["severity"],
                    "detail": f"{name}（{realm}）出现超出境界的能力：『{word}』"
                })
    return issues


# FIX 2026-09-30：原实现中"看到/发现/感到/神色/脸色"等高频弱感知词与触发词同段即判 error，
# 误报极高（如"赵无咎看到天命剑"这类正常叙述）。
# 设计决策：强感知词（感应/察觉/听见/听到/感受到/心里发毛）保持"同段"判定；
# 弱感知词（看到/发现/感到/神色/脸色）收紧为"同句"判定——触发词、人物名、弱感知词须在同一句内。
# 行为变化：弱感知词跨句同段不再报错（误报下降，漏报可能微升）；config 新增的未知感知词默认按强处理。
_STRONG_SENSE_WORDS = {"感应", "察觉", "听见", "听到", "感受到", "心里发毛"}
_WEAK_SENSE_WORDS = {"看到", "发现", "感到", "神色", "脸色"}


def rule_divine_sense(text, cfg, chars):
    """检测：非主角人物感应/察觉天命剑/神器"""
    issues = []
    triggers = cfg["trigger_words"]
    senses = cfg.get("sense_words", [])
    strong = [s for s in senses if s not in _WEAK_SENSE_WORDS]  # 强感知词 + 未知词（默认同段口径）
    weak = [s for s in senses if s in _WEAK_SENSE_WORDS]
    # 按段切
    for para in re.split(r"\n{2,}", text):
        if not para.strip():
            continue
        has_trigger = any(t in para for t in triggers)
        if not has_trigger:
            continue
        for c in chars:
            if c.get("role") == "主角":
                continue
            if c["name"] not in para:
                continue
            # 强感知词：同段即判（旧口径）
            if any(s in para for s in strong):
                issues.append({
                    "rule": "神器感应越界", "severity": cfg["severity"],
                    "detail": f"{c['name']}（{c.get('realm','')}）不应感应/察觉神器觉醒"
                })
                continue  # 同一人同段已判，不再用弱口径重复计数
            # FIX 2026-09-30：弱感知词收紧为同句判定
            for sent in re.split(r"[。！？\n]", para):
                if not sent.strip():
                    continue
                if c["name"] in sent and any(t in sent for t in triggers) \
                        and any(s in sent for s in weak):
                    issues.append({
                        "rule": "神器感应越界", "severity": cfg["severity"],
                        "detail": f"{c['name']}（{c.get('realm','')}）不应感应/察觉神器觉醒"
                    })
                    break
    return issues


# FIX 2026-09-30：原 start_signals 硬编码"开始集合/大比开始/钟声响起"，只对第 2 章（外门大比）有效，
# 其他章节该检查名存实亡。
# 设计决策：信号词改为可配置——优先读 cfg["time_signals"]（新键），无则用通用信号词；
# 旧 cfg["start_signals"] 不再使用（行为变化：默认从"第2章专用"变为"通用"；
# 通用词"开始"经子串可覆盖"开始集合/大比开始"的大部分场景）。
# --chapter 可按章节覆盖信号词（见 _CHAPTER_TIME_SIGNAL_OVERRIDES 格式说明）。
_BUILTIN_TIME_SIGNALS = ["开始", "钟声响起", "开场", "幕启"]
# 章节覆盖表示例：{"2": ["开始集合", "大比开始", "钟声响起"]}；键为章节数字字符串
_CHAPTER_TIME_SIGNAL_OVERRIDES = {}


def _resolve_time_signals(cfg, chapter=None):
    """解析时间信号词：config time_signals > 通用内置；--chapter 命中覆盖表则用覆盖值"""
    signals = cfg.get("time_signals") or list(_BUILTIN_TIME_SIGNALS)
    if chapter:
        key = re.sub(r"\D", "", str(chapter)) or str(chapter)
        override = _CHAPTER_TIME_SIGNAL_OVERRIDES.get(key)
        if override:
            signals = list(override)
    return signals


def rule_time_contradiction(text, cfg, chapter=None):
    issues = []
    starts = [(text.find(s), s) for s in _resolve_time_signals(cfg, chapter) if s in text]
    pendings = [(text.find(s), s) for s in cfg["pending_signals"] if s in text]
    if not starts or not pendings:
        return issues
    for sp, ss in starts:
        for pp, ps in pendings:
            if abs(sp - pp) <= cfg["window"]:
                issues.append({
                    "rule": "时间线矛盾", "severity": cfg["severity"],
                    "detail": f"『{ss}』与『{ps}』相距 {abs(sp-pp)} 字，可能矛盾"
                })
    return issues


def rule_position_contradiction(text, cfg):
    issues = []
    for pair in cfg["conflict_pairs"]:
        a, b = pair
        for ma in re.finditer(re.escape(a), text):
            for mb in re.finditer(re.escape(b), text):
                if abs(ma.start() - mb.start()) < 400:
                    issues.append({
                        "rule": "位置/行为逻辑矛盾", "severity": cfg["severity"],
                        "detail": f"『{a}』与共现：『{b}』"
                    })
    return issues


# FIX 2026-09-30：原 mappings 只有 v1.0 的"天剑宗"，v2.0 正文用"剑心宗/血海宫"，
# 导致该检查对 v2.0 世界观永久失效。
# 设计决策（v1/v2 并存）：config/logic-rules.json 的 mappings 优先；
# config 未覆盖的门派回退内置表；内置表同时覆盖 v1.0（天剑宗）与 v2.0（剑心宗、血海宫）。
_BUILTIN_ORG_MAPPINGS = {
    "天剑宗": ["阔刀", "大刀", "木棍", "木棒", "棍棒", "棍", "刀法", "拳法", "拳", "掌法"],
    "剑心宗": ["阔刀", "大刀", "木棍", "木棒", "棍棒", "棍", "刀法", "拳法", "拳", "掌法"],  # v2.0 剑修门派，设定承袭天剑宗
    "血海宫": ["佛珠", "木鱼", "袈裟", "经文"],  # v2.0 血道门派，不应出现佛道器物（初版清单，可按世界包扩充）
}


def rule_modern_item_org(text, cfg, world):
    issues = []
    # FIX 2026-09-30：config 优先、内置补缺（config 未覆盖的门派仍受检）
    mappings = dict(_BUILTIN_ORG_MAPPINGS)
    mappings.update(cfg.get("mappings", {}) or {})
    # 找出章内出现的门派
    orgs = {v["name"]: v for v in world.get("entries", {}).values() if v.get("kind") == "org"}
    for org_name in orgs:
        if org_name not in text:
            continue
        forbidden = mappings.get(org_name, [])
        for word in forbidden:
            if word in text:
                issues.append({
                    "rule": "门派设定冲突", "severity": cfg["severity"],
                    "detail": f"{org_name} 中出现『{word}』"
                })
    return issues


def rule_duplicate_sentences(text, min_len=8):
    issues = []
    sents = [s.strip() for s in re.split(r"[。！？\n]", text) if len(s.strip()) >= min_len]
    cnt = Counter(sents)
    for s, c in cnt.items():
        if c > 1:
            issues.append({
                "rule": "重复句子", "severity": "warn",
                "detail": f"『{s[:30]}』重复出现 {c} 次"
            })
    return issues


def rule_constitution_valid(text, cfg, world, chars):
    """检测：角色体质是否存在 + 体质能力是否越界"""
    issues = []
    const_ids = {k for k, v in world.get("entries", {}).items() if v.get("kind") == "constitution"}
    
    # 1. 引用有效性检查
    for c in chars:
        cid = c.get("constitution", "")
        if cid and cid not in const_ids:
            issues.append({
                "rule": "体质引用无效", "severity": "error",
                "detail": f"{c['name']}引用了不存在的体质: {cid}"
            })
    
    # 2. 体质能力越界检查
    for c in chars:
        cid = c.get("constitution", "")
        if cid not in const_ids:
            continue
        realm = c.get("realm", "")
        const_entry = world["entries"].get(cid, {})
        
        # 凡体/废体不应有超境界能力
        rarity = const_entry.get("rarity", "common")
        if rarity in ("low",) and "淬体" in realm:
            issues.append({
                "rule": "体质能力矛盾", "severity": "warn",
                "detail": f"{c['name']}(废体+{realm})不应有超凡表现"
            })
    
    return issues


def rule_constitution_sword_match(text, cfg, world, chars):
    """检测：只有天命体可感知天命剑"""
    issues = []
    legend_id = "constitution_legend_0001"
    legend_chars = [c["id"] for c in chars if c.get("constitution") == legend_id]
    legend_names = [c["name"] for c in chars if c.get("constitution") == legend_id]
    
    # 检查非天命体角色是否感知天命剑
    # FIX 2026-09-30：原 sense_verbs 混装强/弱感知词且一律"同段即判"，与 rule_divine_sense
    # 修复前相同的误报模式（如"赵无咎看到天命剑"这类正常叙述）。现沿用同一强/弱分级：
    # 强感知词（感应/察觉/听见/听到/心里发毛）保持同段判定；弱感知词（看到/发现/感到/
    # 神色/脸色）收紧为同句判定（人物名、触发词、弱感知词须在同一句内）。
    for para in re.split(r"\n{2,}", text):
        if "天命剑" not in para and "神器" not in para:
            continue
        for c in chars:
            if c["id"] in legend_chars:
                continue  # 跳过天命体
            if c["name"] not in para:
                continue
            # 强感知词：同段即判（旧口径）
            if any(v in para for v in _STRONG_SENSE_WORDS):
                issues.append({
                    "rule": "体质能力越界", "severity": "error",
                    "detail": f"{c['name']}({c.get('constitution','')})不可感知天命剑"
                })
                continue  # 同一人同段已判，不再用弱口径重复计数
            # 弱感知词：同句才判
            for sent in re.split(r"[。！？\n]", para):
                if not sent.strip():
                    continue
                if c["name"] in sent and ("天命剑" in sent or "神器" in sent) \
                        and any(v in sent for v in _WEAK_SENSE_WORDS):
                    issues.append({
                        "rule": "体质能力越界", "severity": "error",
                        "detail": f"{c['name']}({c.get('constitution','')})不可感知天命剑"
                    })
                    break
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--json", action="store_true")
    # FIX 2026-09-30：--chapter 用于覆盖时间信号词（见 _CHAPTER_TIME_SIGNAL_OVERRIDES）
    ap.add_argument("--chapter", default=None, help="章节标识，用于覆盖时间信号词")
    ap.add_argument("--world-pack", default=None, help="世界包 JSON 路径（按项目动态指定，替代写死路径）")
    ap.add_argument("--chars", default=None, help="角色档案 JSON 路径（按项目动态指定，替代写死路径）")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"文件不存在: {path}")
        sys.exit(2)

    content = path.read_text(encoding="utf-8")
    text = strip_meta(content)
    rules = load_rules()
    chars = load_chars(args.chars)["characters"]
    world = load_world(args.world_pack)

    issues = []
    issues += rule_era_words(text, rules["era_words"])
    issues += rule_realm_capability(text, rules["realm_capability"], chars, world)
    issues += rule_divine_sense(text, rules["divine_sense_boundary"], chars)
    issues += rule_time_contradiction(text, rules["time_contradiction"], chapter=args.chapter)
    issues += rule_position_contradiction(text, rules["position_contradiction"])
    issues += rule_modern_item_org(text, rules["modern_item_org_conflict"], world)
    issues += rule_duplicate_sentences(text)
    issues += rule_constitution_valid(text, rules.get("constitution_valid", {}), world, chars)
    issues += rule_constitution_sword_match(text, rules.get("constitution_sword_match", {}), world, chars)

    errors = [i for i in issues if i.get("severity") == "error"]
    warns = [i for i in issues if i.get("severity") == "warn"]

    result = {"file": str(path), "status": "pass" if not errors else "fail",
              "errors": len(errors), "warnings": len(warns), "issues": issues}

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("=" * 60)
        print(f"🔍 逻辑审查: {path.name}")
        print("=" * 60)
        if not issues:
            print("  ✅ 无问题")
        for i in issues:
            tag = "❌" if i.get("severity") == "error" else "⚠️"
            print(f"  {tag} [{i['rule']}] {i.get('detail', i.get('word',''))}")
        print()
        print(f"状态: {'✅ PASS' if not errors else '❌ FAIL'} | 错误 {len(errors)} | 警告 {len(warns)}")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
