#!/usr/bin/env python3
"""
world-sync.py — 事件驱动的世界包同步器

触发机制：文件追加（非轮询、非常驻）
事件源：.events/<novel-id>.jsonl
  gate-check PASS    → {"event":"CHAPTER_GATE_PASSED","chapter":N}
  fact-ledger写入    → {"event":"FACT_ADDED","fact_id":"F00XX","category":"..."}
  outline新增章节    → {"event":"OUTLINE_CHAPTER_ADDED","chapter":N}

消费流程：
  1. world-sync.py scan      读取事件游标后的新事件 → 扫描实体 → 生成待确认清单
  2. world-sync.py list      查看待确认清单
  3. world-sync.py approve   人工确认后写入世界包（调用 world-pack.py 或直接写 JSON）
  4. world-sync.py reject    拒绝条目

设计原则：
  - 追加即事件，不依赖时间/cron/daemon
  - 消费是 pull 式：调用时才算处理，不调用则事件安全留存
  - 世界包写入必须经过人工确认（extracted → canon）
  - 游标持久化到 .events/<novel-id>.cursor，中断可续
"""

import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 代际项目守卫（唯一路径入口）
sys.path.insert(0, str(Path(__file__).parent))
from project_guard import resolve


BASE = Path("/var/minis/shared/novel-team")
WORLD_PACKS_DIR = BASE / ".world-packs"
EVENTS_DIR = BASE / ".events"
# 使用 pending-review.py 同一目录，文件名加 -world 后缀避免冲突
# 路径：ledger/<novel-id>/pending-world.json
# 同类任务（pending-review）归审核岗，world-sync 自动审批的由大纲岗处理
PENDING_DIR = BASE / "ledger"


# ──────────────────────────────────────────────
# 实体提取（精确版：已知词根匹配 + 通用正则兜底）
# ──────────────────────────────────────────────

# 噪声过滤：实体名第一个字不能是这些
_STOP_START = set("的了在把被将让等说想是要有来去走看到听拿叫做学教攻逃藏站坐躺飞游泳跑跳摇摆晃微轻重快慢高低大小新旧老少多少几十百千万亿第各每某谁哪怎为因所于以及和或则却但又再更最极甚较偏尤倍余远近深浅厚薄强弱刚柔坚脆回向从出进到上上下起落升降转")

# 明确的非实体词（全称匹配）
_NON_ENTITIES = {
    "外门", "内门", "开门", "敲门", "站在门", "门口", "打开门",
    "位于外门", "口打开门", "外传来敲门", "苏婉站在门",
    "挥剑", "握剑", "铁剑", "制式铁剑", "手腕上的剑",
    "大长老", "他说天命剑",
}


def extract_entities(text: str, world_version: Optional[str] = None) -> List[Dict]:
    """
    从文本中提取候选实体。
    策略：已知专有名词词根精确匹配 + 通用正则兜底。
    world_version: "v1" / "v2" / None（None 表示无法判定，不过滤，保持原行为）。
    """
    found = []
    seen = set()

    # 已知专有名词词根（来源：世界包、角色表、大纲、功法体系）
    # FIX 2026-09-30：每个词根加版本标签（"v1"=玄天大陆 / "v2"=苍玄界 / "both"=两版共有）。
    # 此前词典 v1/v2 混用不加区分，导致 v2 实体（如血海宫）被自动同步进 v1 世界包。
    # 匹配时按项目世界版本过滤；这是部分修复——完整版需要版本感知的同步架构。
    KNOWN_ROOTS = {
        # 物品/功法
        "天剑": ("thing", "v1"), "血煞": ("thing", "v1"), "天命": ("thing", "both"),
        "寒铁": ("thing", "both"), "赤霄": ("thing", "both"),
        "天青符诀": ("thing", "v1"), "天剑诀": ("thing", "v1"),
        # 宗门/势力
        "剑心宗": ("place", "v2"), "逍遥阁": ("place", "v1"), "青云宗": ("place", "v1"),
        "东海鲛族": ("place", "v1"), "血海宫": ("place", "v2"), "赵家": ("place", "both"),
        # 地域
        "苍玄界": ("place", "v2"), "玄天大陆": ("place", "v1"),
        "中州": ("place", "both"), "北荒": ("place", "both"), "南岭": ("place", "both"),
        "东海": ("place", "both"), "西漠": ("place", "both"),
        # 秘境
        "剑冢": ("place", "both"), "寒渊": ("place", "both"), "毒瘴谷": ("place", "both"),
        "沉船墓": ("place", "both"), "藏经洞": ("place", "both"),
        # 境界
        "淬体": ("realm", "v2"), "筑基": ("realm", "v1"), "金丹": ("realm", "v1"),
        "元婴": ("realm", "v1"), "化神": ("realm", "v2"), "炼虚": ("realm", "v1"),
        "合体": ("realm", "v1"), "大乘": ("realm", "v1"), "渡劫": ("realm", "v1"),
        "炼气": ("realm", "v1"),  # FIX 2026-09-30：补 v1 境界词根（原词典缺失）
        "聚气": ("realm", "v2"), "凝元": ("realm", "v2"), "通玄": ("realm", "v2"),  # FIX 2026-09-30：补 v2 境界词根
        # 体质
        "混沌体": ("characteristic", "both"), "冰灵体": ("characteristic", "both"),
        "狂兽体": ("characteristic", "both"), "虚无体": ("characteristic", "both"),
        # 已知角色
        "林玄": ("figure", "v2"), "苏婉": ("figure", "v2"),
        "赵霸": ("figure", "v2"), "赵无咎": ("figure", "v2"),
        "萧辰": ("figure", "v1"),  # FIX 2026-09-30：补 v1 主角词根（原词典缺失）
        "李白白": ("figure", "v1"), "血姬": ("figure", "v1"), "风清扬": ("figure", "v1"),
        "逍遥子": ("figure", "v1"), "血煞老祖": ("figure", "v1"), "鲛人王": ("figure", "v1"),
        # 事件
        "身世之谜": ("event", "both"), "天裂之劫": ("event", "v1"),
    }

    # Step 1: 已知词根精确匹配
    for root, (kind, ver) in KNOWN_ROOTS.items():
        # FIX 2026-09-30：按世界版本过滤；无法判定版本（None）时不过滤，保持原行为
        if world_version and ver != "both" and ver != world_version:
            continue
        idx = 0
        while True:
            pos = text.find(root, idx)
            if pos == -1:
                break
            idx = pos + 1

            # 检查左右上下文：防止把 "大天命剑碎片" 提取为 "天命"
            left_ok = pos > 0 and not _is_prefix_continuation(text, pos - 1)
            right_ok = pos + len(root) >= len(text) or not _is_suffix_continuation(text, pos + len(root))

            if left_ok and right_ok:
                if root not in seen:
                    seen.add(root)
                    found.append({"kind": kind, "name": root, "version": ver})

    # Step 2: 通用正则兜底（发现未知实体）
    # 只在有强后缀（宗/阁/殿/城/岛/大陆/秘境）且长度≥3时匹配
    # FIX 2026-09-30：候选名若包含已被版本过滤掉的已知词根（如 v2 模式下的"天剑宗"），
    # 说明它是已知异版实体的片段，跳过，避免从兜底路径漏网
    filtered_roots = {r for r, (k, v) in KNOWN_ROOTS.items()
                      if world_version and v != "both" and v != world_version}
    generic_place_pat = r"[一-龥]{2,4}(?:宗|阁|殿|城|岛|大陆|秘境)"
    for m in re.finditer(generic_place_pat, text):
        name = m.group(0)
        if len(name) < 3 or name in seen or name in _NON_ENTITIES:
            continue
        if name[0] in _STOP_START:
            continue
        if any(r in name for r in filtered_roots):
            continue
        seen.add(name)
        found.append({"kind": "place", "name": name, "version": "unknown"})

    return found


def _is_prefix_continuation(text: str, pos: int) -> bool:
    """判断 pos 处的字符是否是前面的词的延续（即实体名前面不应该再连着这些字）"""
    # 前缀延续：如果前一个字是常见中文，可能提取了片段
    # 例："大天命" → "天命"前的"大"说明提取的不够长
    return '一' <= text[pos] <= '\u9fff' and pos > 0 and text[pos-1] not in '。，、；！？\'\'"" \n\t'


def _is_suffix_continuation(text: str, pos: int) -> bool:
    """判断 pos 处是否还有后续字说明实体名提取不完整"""
    if pos >= len(text):
        return False
    ch = text[pos]
    # 如果后面紧跟"的/了/地/得"等，说明前面的完整词已被提取
    if ch in "的了吗呢吧啊哦嗯啊呀哈嘿喂吗哪几谁这那每各":
        return False
    # 如果后面紧跟更多中文字，可能是实体名更长
    # 但我们无法判断，暂时返回False（宁可多提，由人工过滤）
    return False

def _events_path(novel_id: str) -> Path:
    d = EVENTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{novel_id}.jsonl"


def _cursor_path(novel_id: str) -> Path:
    d = EVENTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{novel_id}.cursor"


def emit_event(novel_id: str, event_type: str, payload: Dict = None) -> str:
    """追加一条事件到事件文件（事件源调用此函数）"""
    p = _events_path(novel_id)
    event = {
        "event": event_type,
        "timestamp": datetime.now().isoformat(),
        **(payload or {}),
    }
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event["timestamp"]


def _read_events_since(novel_id: str, cursor: int = 0) -> List[Dict]:
    """读取游标之后的事件（行号 = 行序）"""
    p = _events_path(novel_id)
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    events = []
    for i, line in enumerate(lines[cursor:], cursor):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _get_cursor(novel_id: str) -> int:
    cp = _cursor_path(novel_id)
    if cp.exists():
        try:
            return int(cp.read_text().strip())
        except ValueError:
            pass
    return 0


def _set_cursor(novel_id: str, value: int):
    _cursor_path(novel_id).write_text(str(value))


# ──────────────────────────────────────────────
# 世界包比对
# ──────────────────────────────────────────────

def _detect_world_version(novel_id: str) -> Optional[str]:
    # FIX 2026-09-30：判定项目世界版本，用于 KNOWN_ROOTS 版本过滤。
    # 玄天大陆 → v1，苍玄界 → v2；无法判定返回 None（调用方不过滤，保持原行为）。
    # 这是部分修复：完整版需要版本感知的同步架构（world-pack 的 retired 状态 + 迁移函数）。
    try:
        for p in WORLD_PACKS_DIR.glob("*.json"):
            try:
                name = str(json.loads(p.read_text(encoding="utf-8")).get("name", ""))
            except Exception:
                continue
            if "苍玄界" in name:
                return "v2"
            if "玄天大陆" in name:
                return "v1"
    except Exception:
        pass
    try:
        cfg = resolve(novel_id).root_dir / "project-config.json"
        if cfg.exists():
            world = str(json.loads(cfg.read_text(encoding="utf-8")).get("world", ""))
            if "苍玄界" in world:
                return "v2"
            if "玄天大陆" in world:
                return "v1"
    except Exception:
        pass
    return None


def _load_world_pack(novel_id: str) -> Dict:
    """加载世界包条目名称集合"""
    # FIX 2026-09-30：此前无条件取第一个 json；现优先选文件名/内容与项目世界名匹配的包，
    # 无匹配才回退第一个并打 warning 日志。
    wp_files = list(WORLD_PACKS_DIR.glob("*.json"))
    if not wp_files:
        return {"names": set(), "path": None}
    wp_path = wp_files[0]
    if len(wp_files) > 1:
        world_version = _detect_world_version(novel_id)
        scored = []
        for p in wp_files:
            score = 0
            try:
                pname = str(json.loads(p.read_text(encoding="utf-8")).get("name", ""))
                if world_version == "v1" and "玄天大陆" in pname:
                    score = 2
                elif world_version == "v2" and "苍玄界" in pname:
                    score = 2
                elif novel_id in p.stem:
                    score = 1
            except Exception:
                pass
            scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        wp_path = scored[0][1]
        if scored[0][0] == 0:
            print(f"⚠️ [world-sync] 找到 {len(wp_files)} 个世界包，均无法匹配项目世界版本，"
                  f"已回退第一个：{wp_path.name}", file=sys.stderr)
    data = json.loads(wp_path.read_text(encoding="utf-8"))
    names = set()
    for entry in data.get("entries", {}).values():
        names.add(entry.get("name", ""))
        for alias in entry.get("aliases", []):
            names.add(alias)
    return {"names": names, "path": wp_path}


def _load_characters(novel_id: str) -> set:
    """加载角色表名称集合"""
    # FIX 2026-09-30：此前硬编码 projects/my-novel，忽略传入的 novel_id；
    # 现经 project_guard.resolve(novel_id) 解析。
    try:
        char_file = resolve(novel_id).root_dir / "characters" / "characters.json"
    except Exception:
        char_file = BASE / "projects" / novel_id / "characters" / "characters.json"
    if not char_file.exists():
        return set()
    data = json.loads(char_file.read_text(encoding="utf-8"))
    names = set()
    chars = data.get("characters", {})
    if isinstance(chars, dict):
        for c in chars.values():
            if isinstance(c, dict):
                names.add(c.get("name", ""))
            else:
                names.add(str(c))
    elif isinstance(chars, list):
        for c in chars:
            if isinstance(c, dict):
                names.add(c.get("name", ""))
            else:
                names.add(str(c))
    return names


def _load_facts(novel_id: str) -> Dict:
    """加载事实账本"""
    fp = BASE / "ledger" / novel_id / "facts.json"
    if not fp.exists():
        return {}
    return json.loads(fp.read_text(encoding="utf-8"))


def _find_missing(entities: List[Dict], world_names: set, char_names: set) -> List[Dict]:
    """找出尚未在世界包/角色表中定义的实体"""
    missing = []
    for ent in entities:
        name = ent["name"]
        kind = ent["kind"]
        # 角色查字符表，其他查世界包
        if kind == "figure":
            if name not in char_names and name not in world_names:
                missing.append(ent)
        else:
            if name not in world_names:
                missing.append(ent)
    return missing


# ──────────────────────────────────────────────
# 待确认清单
# ──────────────────────────────────────────────

def _pending_path(novel_id: str) -> Path:
    return PENDING_DIR / novel_id / "pending-world.json"


def _load_pending(novel_id: str) -> List[Dict]:
    p = _pending_path(novel_id)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return []


def _save_pending(novel_id: str, items: List[Dict]):
    _pending_path(novel_id).write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_wid(items: List[Dict]) -> str:
    nums = [int(w["id"][1:]) for w in items if w.get("id", "").startswith("W")]
    return f"W{max(nums, default=0)+1:03d}"


# ──────────────────────────────────────────────
# 核心扫描逻辑
# ──────────────────────────────────────────────

def scan(novel_id: str, auto_commit: bool = False) -> Dict:
    """
    处理游标后的所有新事件 → 生成待确认清单

    事件类型处理：
    - CHAPTER_GATE_PASSED: 扫描章节正文 + 新增事实，找未定义实体
    - FACT_ADDED: 检查新事实内容中的实体是否在世界上
    """
    cursor = _get_cursor(novel_id)
    total_lines = len(_events_path(novel_id).read_text(encoding="utf-8").strip().splitlines()) \
        if _events_path(novel_id).exists() else 0

    new_events = _read_events_since(novel_id, cursor)
    pending = _load_pending(novel_id)
    world_info = _load_world_pack(novel_id)
    # FIX 2026-09-30：判定世界版本，实体提取时按版本过滤词典（v1/v2 混用曾致串味）
    world_version = _detect_world_version(novel_id)
    world_names = world_info["names"]
    char_names = _load_characters(novel_id)
    facts = _load_facts(novel_id)

    added_items = []

    for event in new_events:
        etype = event.get("event", "")
        ch_num = event.get("chapter", 0)

        if etype == "CHAPTER_GATE_PASSED":
            # 扫描章节正文
            ch_file = resolve(novel_id).chapters() / f"chapter-{ch_num:03d}.md"
            text = ""
            if ch_file.exists():
                text = ch_file.read_text(encoding="utf-8")
            elif ch_num:
                # 兼容不同路径
                alt = resolve(novel_id).chapters() / f"chapter-{ch_num:03d}.md"
                if alt.exists():
                    text = alt.read_text(encoding="utf-8")

            if text:
                entities = extract_entities(text, world_version)
                missing = _find_missing(entities, world_names, char_names)
                for ent in missing:
                    confidence = 0.7  # 正文提取，置信度中等
                    item = {
                        "id": _next_wid(pending + added_items),
                        "kind": ent["kind"],
                        "name": ent["name"],
                        "source_event": f"CHAPTER_GATE_PASSED ch{ch_num}",
                        "status": "pending",
                        "created_at": datetime.now().isoformat(),
                        "confidence": confidence,
                        "note": f"从第{ch_num}章正文提取，未在世界包/角色表中找到",
                    }
                    # 高置信度规则类实体自动入库（不需要人工确认）
                    if confidence >= 0.9 and ent["kind"] in ("place", "event", "thing"):
                        _auto_approve_to_world(novel_id, item, world_info)
                        item["status"] = "auto_approved"
                    added_items.append(item)

            # 同时扫描该章节相关的新事实
            new_facts = [f for fid, f in facts.items()
                         if f.get("source", "").startswith(f"第{ch_num}章")]
            fact_text = " ".join(f.get("content", "") for f in new_facts)
            if fact_text:
                fact_entities = extract_entities(fact_text, world_version)
                fact_missing = _find_missing(fact_entities, world_names, char_names)
                for ent in fact_missing:
                    confidence = 0.8  # 事实账本提取，置信度较高
                    item = {
                        "id": _next_wid(pending + added_items),
                        "kind": ent["kind"],
                        "name": ent["name"],
                        "source_event": f"FACT_FROM_CH{ch_num}",
                        "status": "pending",
                        "created_at": datetime.now().isoformat(),
                        "confidence": confidence,
                        "note": f"事实账本第{ch_num}章事实中提取，建议核验后入库",
                    }
                    # 高置信度规则类实体自动入库
                    if confidence >= 0.9 and ent["kind"] in ("place", "event", "thing"):
                        _auto_approve_to_world(novel_id, item, world_info)
                        item["status"] = "auto_approved"
                    added_items.append(item)

        elif etype == "OUTLINE_CHAPTER_ADDED":
            # 大纲章节关键要点提取实体（高置信度）
            key_points = event.get("key_points", [])
            if not key_points:
                continue
            key_text = " ".join(key_points)
            entities = extract_entities(key_text, world_version)
            missing = _find_missing(entities, world_names, char_names)
            for ent in missing:
                confidence = 0.95  # 大纲规划阶段，置信度最高
                item = {
                    "id": _next_wid(pending + added_items),
                    "kind": ent["kind"],
                    "name": ent["name"],
                    "source_event": f"OUTLINE_CHAPTER_ADDED ch{ch_num}",
                    "status": "pending",
                    "created_at": datetime.now().isoformat(),
                    "confidence": confidence,
                    "note": f"大纲第{ch_num}章关键要点中提取，规划阶段实体",
                }
                _auto_approve_to_world(novel_id, item, world_info)
                item["status"] = "auto_approved"
                added_items.append(item)
            fact_content = event.get("content", "")
        elif etype == "FACT_ADDED":
            # 事实添加：检查新事实内容中的实体是否在世界上
            fact_content = event.get("content", "")
            if fact_content:
                entities = extract_entities(fact_content, world_version)
                missing = _find_missing(entities, world_names, char_names)
                for ent in missing:
                    confidence = 0.85  # 事实账本事件，置信度较高
                    item = {
                        "id": _next_wid(pending + added_items),
                        "kind": ent["kind"],
                        "name": ent["name"],
                        "source_event": f"FACT_ADDED {event.get('fact_id','')}",
                        "status": "pending",
                        "created_at": datetime.now().isoformat(),
                        "confidence": confidence,
                        "note": f"新增事实{event.get('fact_id','?')}中提取，建议核验",
                    }
                    if confidence >= 0.9 and ent["kind"] in ("place", "event", "thing"):
                        _auto_approve_to_world(novel_id, item, world_info)
                        item["status"] = "auto_approved"
                    added_items.append(item)


        elif etype == "OUTLINE_VOLUME_ADDED":
            # 大纲卷创建：提取卷标题/简介中的实体（高置信度，自动入库）
            title = event.get("title", "")
            summary = event.get("summary", "")
            vol_num = event.get("volume_num", "")
            text = f"{title} {summary}"
            entities = extract_entities(text, world_version)
            missing = _find_missing(entities, world_names, char_names)
            for ent in missing:
                item = {
                    "id": _next_wid(pending + added_items),
                    "kind": ent["kind"],
                    "name": ent["name"],
                    "source_event": f"OUTLINE_VOLUME_ADDED vol{vol_num}",
                    "status": "auto_approved",
                    "created_at": datetime.now().isoformat(),
                    "confidence": 0.95,
                    "note": f"大纲卷{vol_num}创建时提取，规划阶段实体，自动入库",
                }
                _auto_approve_to_world(novel_id, item, world_info)
                added_items.append(item)

        elif etype == "OUTLINE_WORK_CREATED":
            # 作品创建：提取作品标题/简介中的实体（高置信度，自动入库）
            title = event.get("title", "")
            summary = event.get("summary", "")
            text = f"{title} {summary}"
            entities = extract_entities(text, world_version)
            missing = _find_missing(entities, world_names, char_names)
            for ent in missing:
                item = {
                    "id": _next_wid(pending + added_items),
                    "kind": ent["kind"],
                    "name": ent["name"],
                    "source_event": "OUTLINE_WORK_CREATED",
                    "status": "auto_approved",
                    "created_at": datetime.now().isoformat(),
                    "confidence": 0.95,
                    "note": "作品创建时从标题/简介提取，自动入库",
                }
                _auto_approve_to_world(novel_id, item, world_info)
                added_items.append(item)

    pending.extend(added_items)
    _save_pending(novel_id, pending)

    # 更新游标
    _set_cursor(novel_id, total_lines)

    return {
        "scanned_events": len(new_events),
        "new_pending_items": len(added_items),
        "total_pending": len(pending),
        "items": [i for i in added_items],
        "world_pack_entries": len(world_names),
        "character_entries": len(char_names),
    }


def approve(novel_id: str, wid: str, note: str = "") -> Dict:
    """确认条目，写入世界包"""
    pending = _load_pending(novel_id)
    for item in pending:
        if item["id"] == wid:
            if item["status"] != "pending":
                return {"ok": False, "error": f"{wid} 已处理（状态：{item['status']}）"}

            # 写入世界包
            wp = _load_world_pack(novel_id)
            if not wp["path"]:
                return {"ok": False, "error": "世界包文件不存在，请先初始化"}

            data = json.loads(wp["path"].read_text(encoding="utf-8"))
            kind = item.get("kind", "note")
            name = item["name"]
            eid = f"{kind[:1]}_{name[:3]}_{len(data.get('entries',{}))+1:04d}"

            # 避免重复
            existing_names = {e.get("name","") for e in data.get("entries",{}).values()}
            if name in existing_names:
                item["status"] = "skipped"
                item["decision_note"] = f"已存在，跳过（{note}）"
                _save_pending(novel_id, pending)
                return {"ok": True, "msg": f"{wid} 跳过：'{name}' 已存在于世界包", "action": "skipped"}

            data.setdefault("entries", {})[eid] = {
                "id": eid,
                "kind": kind,
                "name": name,
                "status": "draft",  # 入库为 draft，人工提升为 canon
                "aliases": [],
                "folder": "",
                "tags": [f"synced:{wid}"],
                "tagline": item.get("note", ""),
                "when": {},
                "relations": [],
                "fields": [],
                "evidence": [{"source": item["source_event"], "at": item["created_at"]}],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "content": "",
            }

            tmp = wp["path"].with_suffix('.tmp')
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(wp["path"])

            item["status"] = "approved"
            item["decided_at"] = datetime.now().isoformat()
            item["decision_note"] = note or "人工确认"
            _save_pending(novel_id, pending)
            return {"ok": True, "msg": f"✅ {wid} '{name}' 已写入世界包（draft）", "entry_id": eid}

    return {"ok": False, "error": f"未找到 {wid}"}


def reject(novel_id: str, wid: str, reason: str = "") -> Dict:
    pending = _load_pending(novel_id)
    for item in pending:
        if item["id"] == wid:
            item["status"] = "rejected"
            item["decided_at"] = datetime.now().isoformat()
            item["decision_note"] = reason
            _save_pending(novel_id, pending)
            return {"ok": True, "msg": f"❌ {wid} 已拒绝：{reason}"}
    return {"ok": False, "error": f"未找到 {wid}"}


def _auto_approve_to_world(novel_id: str, item: Dict, world_info: Dict) -> None:
    """自动将高置信度实体写入世界包（无需人工确认）"""
    wp = world_info
    if not wp.get("path"):
        return
    data = json.loads(wp["path"].read_text(encoding="utf-8"))
    name = item["name"]
    kind = item["kind"]
    # 避免重复
    existing_names = {e.get("name", "") for e in data.get("entries", {}).values()}
    if name in existing_names:
        item["status"] = "skipped"
        return
    eid = f"{kind[:1]}_{name[:3]}_{len(data.get('entries',{}))+1:04d}"
    data.setdefault("entries", {})[eid] = {
        "id": eid,
        "kind": kind,
        "name": name,
        "status": "draft",
        "aliases": [],
        "folder": "",
        "tags": [f"auto-sync:{item['source_event']}"],
        "tagline": item.get("note", ""),
        "when": {},
        "relations": [],
        "fields": [],
        "evidence": [{"source": item["source_event"], "at": item["created_at"]}],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "content": "",
    }
    tmp = wp["path"].with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(wp["path"])
    item["world_entry_id"] = eid
    item["decision_note"] = "自动批准（高置信度规则类实体）"


def list_pending(novel_id: str, status: str = "all") -> List[Dict]:
    items = _load_pending(novel_id)
    if status == "all":
        return items
    return [i for i in items if i.get("status") == status]


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="事件驱动的世界包同步器")
    parser.add_argument("--novel-id", "-p", default=None, help="项目ID")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="消费新事件，生成待确认清单")
    p_list = sub.add_parser("list", help="查看待确认清单")
    p_list.add_argument("--status", default="pending",
                       choices=["pending", "approved", "rejected", "skipped", "all"])
    p_ap = sub.add_parser("approve", help="确认条目，写入世界包")
    p_ap.add_argument("--id", required=True)
    p_ap.add_argument("--note", default="")
    p_rej = sub.add_parser("reject", help="拒绝条目")
    p_rej.add_argument("--id", required=True)
    p_rej.add_argument("--reason", default="")
    p_emit = sub.add_parser("emit", help="手动发射事件（测试用）")
    p_emit.add_argument("--event-type", "-e", required=True,
                       choices=["CHAPTER_GATE_PASSED", "FACT_ADDED", "OUTLINE_CHAPTER_ADDED"])
    p_emit.add_argument("--chapter", "-c", type=int, default=0)
    p_emit.add_argument("--payload", help="额外载荷JSON")

    args = parser.parse_args()

    if args.cmd == "scan":
        r = scan(args.novel_id)
        # 统计各状态
        all_items = list_pending(args.novel_id, "all")
        auto_count = sum(1 for i in all_items if i.get("status") == "auto_approved")
        pending_count = sum(1 for i in all_items if i.get("status") == "pending")
        result = {
            "scanned_events": r["scanned_events"],
            "new_pending_items": r["new_pending_items"],
            "total_pending": r["total_pending"],
            "auto_approved": auto_count,
            "needs_human": pending_count,
        }
        print(json.dumps(result, ensure_ascii=False))

    elif args.cmd == "list":
        items = list_pending(args.novel_id, args.status)
        icons = {"pending": "⏳", "approved": "✅", "rejected": "❌", "skipped": "⏭️"}
        print(f"共 {len(items)} 条（{args.status}）\n")
        for item in items:
            icon = icons.get(item.get("status", "pending"), "?")
            print(f"  {icon} [{item['id']}] {item['kind']}：{item['name']}")
            print(f"     来源：{item.get('source_event','')} | 置信度：{item.get('confidence','?')}")
            if item.get("status") in ("approved", "rejected", "skipped"):
                print(f"     → {item['status']}：{item.get('decision_note','')}")

    elif args.cmd == "approve":
        r = approve(args.novel_id, args.id, args.note)
        print(("✅ " if r.get("ok") else "❌ ") + r.get("msg", r.get("error", "")))

    elif args.cmd == "reject":
        r = reject(args.novel_id, args.id, args.reason)
        print(("✅ " if r.get("ok") else "❌ ") + r.get("msg", r.get("error", "")))

    elif args.cmd == "emit":
        payload = json.loads(args.payload) if args.payload else {}
        payload["chapter"] = args.chapter
        ts = emit_event(args.novel_id, args.event_type, payload)
        print(f"✅ 事件已发射：{args.event_type} ch{args.chapter} @ {ts}")
        print("   运行 world-sync.py scan 消费")


if __name__ == "__main__":
    main()
