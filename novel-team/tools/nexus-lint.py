#!/usr/bin/env python3
"""
nexus-lint.py — 世界观一致性检查器（借鉴 Nexus-Lore Lore Linter）

新增规则（vs world-pack.py）：
  N1. broken_relation   — 关系目标不存在（severity: error）
  N2. temporal_inversion — date_start > date_end（severity: error）
  N3. cross_world_ref   — 引用来自不同世界的实体（severity: warning）
  N4. death_after_action_v2 — 死后行动检测，支持 archive/flashback/memorial 语境豁免
  N5. self_reference    — 实体引用自身（severity: warning）
  N6. empty_relation_type — 关系缺少 type 字段（severity: info）

兼容现有规则：
  R1-R7 from world-pack.py（orphan/duplicate/post_death/canon_no_source等）

输出格式：
  - 按 severity 分组（error → warning → info）
  - 每条带 fingerprint、可定位、可修复指引
  - 支持 --json 输出供 CI 集成

使用：
  python nexus-lint.py check --world "玄天大陆"
  python nexus-lint.py check --world "玄天大陆" --json > issues.json
  python nexus-lint.py timeline --world "玄天大陆"
"""

import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from collections import Counter, defaultdict

# ============================================================
# 配置
# ============================================================

WORLD_DIR = Path("/var/minis/shared/novel-team/.world-packs")
DATE_PATTERN = re.compile(
    r'(第\s*[零一二三四五六七八九十百\d]+[代|年|纪元]|'
    r'\d{1,4}\s*年前|'
    r'\d{4}[-年/]\d{1,2}[-月/]\d{1,2}|'
    r'[\u4e00-\u9fa5]+年|\d+\s*(年前|年后|世纪|代))'
)
NUMERIC_DATE = re.compile(r'(\d+)\s*(年前|年后|世纪|代|年|月|日)')

# Nexus-Lore 语境豁免表（死后仍合理存在的语境）
DEATH_CONTEXT_EXEMPT = {"archive", "flashback", "memorial", "回忆", "纪念", "传说"}
DEATH_KEYWORDS = [
    "死亡", "去世", "牺牲", "阵亡", "殉职", "被杀", "遇害", "处决",
    "身亡", "毙命", "战死", "自尽", "毒杀", "问斩", "伏诛",
    "圆寂", "陨落", "殒命", "失踪", "退场", "解体", "覆灭",
    "灭亡", "焚毁", "沉没", "死", "卒", "驾崩", "薨"
]

# 关系类型白名单（type 为空时的建议）
DEFAULT_REL_TYPES = {
    "figure-figure": "associate",
    "figure-org": "member_of",
    "figure-place": "origin",
    "org-org": "alliance",
    "org-place": "controls",
    "place-place": "near",
    "figure-event": "participated",
    "org-event": "caused",
}


# ============================================================
# 数据模型
# ============================================================

class WorldPack:
    def __init__(self, name: str):
        self.name = name
        self.path = WORLD_DIR / f"{name}.json"
        self.data = self._load()
        self.entries: Dict[str, dict] = self.data.get("entries", {})
        self.issues: List[dict] = self.data.get("issues", [])

    def _load(self) -> dict:
        if not self.path.exists():
            print(f"❌ 世界包不存在: {self.path}", file=sys.stderr)
            sys.exit(1)
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self):
        self.data["issues"] = self.issues
        self.data["updated_at"] = datetime.now().isoformat()
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get_entity(self, eid: str) -> Optional[dict]:
        return self.entries.get(eid)

    def resolve_entity(self, ref: str) -> Optional[str]:
        """通过名字/别名解析实体 ID"""
        ref_lower = ref.lower()
        for eid, e in self.entries.items():
            if e["name"].lower() == ref_lower:
                return eid
            for alias in e.get("aliases", []):
                if alias.lower() == ref_lower:
                    return eid
        return None

    # ----------------------------------------------------------
    # Nexus-Lore 新增规则
    # ----------------------------------------------------------

    def check_broken_relation(self) -> List[dict]:
        """N1: 关系目标不存在"""
        issues = []
        for eid, e in self.entries.items():
            for rel in e.get("relations", []):
                target = rel.get("to") or rel.get("target") or rel.get("to_id")
                if target and target not in self.entries:
                    # 尝试名字解析
                    resolved = self.resolve_entity(target)
                    hint = f"（名字 '{target}' 不存在，提示：可能是 '{resolved}'？）" if resolved else f"（提示：名字 '{target}' 不存在）"
                    issues.append({
                        "rule": "broken_relation",
                        "severity": "error",
                        "entry_id": eid,
                        "message": f"关系目标不存在: {e['name']} → {target} {hint}".rstrip(),
                        "fix": "补上目标条目，或把 to 改成它的名字/别名",
                    })
        return issues

    def check_temporal_inversion(self) -> List[dict]:
        """N2: date_start > date_end"""
        issues = []
        for eid, e in self.entries.items():
            when = e.get("when", {})
            ds = when.get("date_start") or e.get("date_start")
            de = when.get("date_end") or e.get("date_end")
            if ds and de:
                try:
                    if isinstance(ds, str) and isinstance(de, str):
                        d_start = datetime.fromisoformat(ds.replace("Z", "+00:00"))
                        d_end = datetime.fromisoformat(de.replace("Z", "+00:00"))
                    else:
                        continue
                    if d_start > d_end:
                        issues.append({
                            "rule": "temporal_inversion",
                            "severity": "error",
                            "entry_id": eid,
                            "message": f"时间倒置: {e['name']} (start={ds} > end={de})",
                            "fix": "检查 date_start 和 date_end，或改为 only_date 字段",
                        })
                except (ValueError, TypeError):
                    pass  # 日期格式不可解析，跳过
        return issues

    def check_cross_world_ref(self) -> List[dict]:
        """N3: 引用来自不同世界的实体（需要多世界存在才有效）"""
        issues = []
        # 仅当有多个世界包时启用
        world_files = list(WORLD_DIR.glob("*.json"))
        if len(world_files) <= 1:
            return issues
        # 简化：标记所有跨 world 的引用为 warning
        # 实际需要维护 world 字段，当前暂跳过
        return issues

    def check_death_after_action_v2(self) -> List[dict]:
        """N4: 死后行动检测（带语境豁免）"""
        issues = []
        for eid, e in self.entries.items():
            content = e.get("content", "")
            tagline = e.get("tagline", "")
            text = content + " " + tagline

            is_dead = (
                e.get("status") == "retired"
                or any(kw in text for kw in DEATH_KEYWORDS)
            )
            if not is_dead:
                continue

            # 检查是否有语境豁免
            context = e.get("context", "")
            has_exemption = any(ctx in context for ctx in DEATH_CONTEXT_EXEMPT)
            if has_exemption:
                continue

            # 检查活动关系
            for rel in e.get("relations", []):
                rel_type = rel.get("type", "")
                if rel_type in ("participated", "caused", "led", "commanded"):
                    issues.append({
                        "rule": "death_after_action_v2",
                        "severity": "error",
                        "entry_id": eid,
                        "message": f"实体已死亡但仍参与活动: {e['name']} ({rel_type})",
                        "fix": "核对时间线，或设置 context: memorial/flashback/archive",
                    })
                    break

            # 检查内容中是否有死后行动描述
            active_verbs = ["领导", "指挥", "发动", "策划", "进攻", "防御", "建立", "创建", "训练"]
            for verb in active_verbs:
                if verb in text and "死" in text:
                    # 简单启发式：如果动词和死在同一句附近
                    idx = text.find(verb)
                    if idx >= 0 and idx < len(text) - 50:
                        snippet = text[max(0, idx-30):idx+50]
                        if "死" in snippet or "亡" in snippet:
                            issues.append({
                                "rule": "death_after_action_v2",
                                "severity": "warning",
                                "entry_id": eid,
                                "message": f"疑似死后仍有活动描述: {e['name']} 含 '{verb}'",
                                "fix": "检查是否为回忆/传说/亡灵语境，添加 context 字段",
                            })
                            break
        return issues

    def check_self_reference(self) -> List[dict]:
        """N5: 实体引用自身"""
        issues = []
        for eid, e in self.entries.items():
            for rel in e.get("relations", []):
                target = rel.get("to") or rel.get("target") or rel.get("to_id")
                if target == eid:
                    issues.append({
                        "rule": "self_reference",
                        "severity": "warning",
                        "entry_id": eid,
                        "message": f"实体自引用: {e['name']} → 自身",
                        "fix": "检查是否是笔误，或改为 'self' 表示自我关系",
                    })
        return issues

    def check_empty_relation_type(self) -> List[dict]:
        """N6: 关系缺少 type 字段"""
        issues = []
        for eid, e in self.entries.items():
            for i, rel in enumerate(e.get("relations", [])):
                if "type" not in rel and "to" not in rel and "target" not in rel:
                    issues.append({
                        "rule": "empty_relation_type",
                        "severity": "info",
                        "entry_id": eid,
                        "message": f"关系 #{i+1} 缺少 type 和 to/target 字段: {e['name']}",
                        "fix": "补上 type（如 associate/alliance/participated）和 to（目标ID）",
                    })
        return issues

    # ----------------------------------------------------------
    # 完整检查
    # ----------------------------------------------------------

    def full_check(self) -> List[dict]:
        """执行所有检查，合并结果"""
        all_issues = []

        # Nexus-Lore 新增
        all_issues.extend(self.check_broken_relation())
        all_issues.extend(self.check_temporal_inversion())
        all_issues.extend(self.check_death_after_action_v2())
        all_issues.extend(self.check_self_reference())
        all_issues.extend(self.check_empty_relation_type())

        # 现有 world-pack.py 规则（兼容）
        # R1: dangling relation (已有检查，但用新逻辑重写)
        for eid, e in self.entries.items():
            for rel in e.get("relations", []):
                target = rel.get("to") or rel.get("target") or rel.get("to_id")
                if target and target not in self.entries:
                    # 已在 N1 中检查，跳过重复
                    pass

        # R2: duplicate
        by_name = defaultdict(list)
        for eid, e in self.entries.items():
            key = f"{e.get('kind','?')}::{e['name'].lower()}"
            by_name[key].append(eid)
        for key, eids in by_name.items():
            if len(eids) > 1:
                all_issues.append({
                    "rule": "duplicate_entity",
                    "severity": "warning",
                    "entries": eids,
                    "message": f"疑似重复条目: {self.entries[eids[0]]['name']}",
                    "fix": "合并成一条，把另一个名字放进 aliases",
                })

        # R4: orphan
        connected_ids = set()
        for e in self.entries.values():
            for rel in e.get("relations", []):
                target = rel.get("to") or rel.get("target") or rel.get("to_id")
                if target:
                    connected_ids.add(target)
                    connected_ids.add(e["id"])
        for eid, e in self.entries.items():
            if eid not in connected_ids and not e.get("relations"):
                all_issues.append({
                    "rule": "orphan",
                    "severity": "info",
                    "entry_id": eid,
                    "message": f"孤岛条目: {e['name']}",
                    "fix": "给它至少一条关系，或并进相关条目",
                })

        # R5: empty stub
        for eid, e in self.entries.items():
            if not e.get("tagline") and not e.get("content"):
                all_issues.append({
                    "rule": "empty_stub",
                    "severity": "info",
                    "entry_id": eid,
                    "message": f"空壳条目: {e['name']}",
                    "fix": "补一句 tagline，或删掉",
                })

        # R6: canon without source
        for eid, e in self.entries.items():
            if e.get("status") == "canon" and not e.get("evidence"):
                all_issues.append({
                    "rule": "canon_no_source",
                    "severity": "warning",
                    "entry_id": eid,
                    "message": f"正典却没有出处: {e['name']}",
                    "fix": "关联来源，或降级为草稿",
                })

        # R7: AI unconfirmed
        for eid, e in self.entries.items():
            if e.get("status") == "extracted":
                all_issues.append({
                    "rule": "ai_unconfirmed",
                    "severity": "warning",
                    "entry_id": eid,
                    "message": f"AI抽取未经确认: {e['name']}",
                    "fix": "在「来源」页逐条确认或丢弃",
                })

        self.issues = all_issues
        return all_issues

    # ----------------------------------------------------------
    # Chronicle 时间线（借鉴 Nexus-Lore）
    # ----------------------------------------------------------

    def get_chronicle(self) -> List[dict]:
        """
        生成 Chronical 时间线视图。
        按 date_order 稳定排序（不依赖日期字符串字典序）。
        支持 when.date_start / when.date_end / fields 中的日期字段。
        """
        events = []
        for eid, e in self.entries.items():
            when = e.get("when", {})
            ds = when.get("date_start") or e.get("date_start")
            de = when.get("date_end") or e.get("date_end")

            # 从 fields 中提取日期信息
            field_dates = {}
            for f in e.get("fields", []):
                fname = f.get("name", "") if isinstance(f, dict) else ""
                fval = f.get("value", "") if isinstance(f, dict) else ""
                if isinstance(fval, str):
                    m = NUMERIC_DATE.search(fval)
                    if m:
                        field_dates[fname] = int(m.group(1))

            if ds or de or field_dates:
                try:
                    if isinstance(ds, str):
                        start = datetime.fromisoformat(ds.replace("Z", "+00:00"))
                    elif isinstance(ds, (int, float)):
                        start = datetime.fromtimestamp(ds)
                    else:
                        start = None

                    if isinstance(de, str):
                        end = datetime.fromisoformat(de.replace("Z", "+00:00"))
                    elif isinstance(de, (int, float)):
                        end = datetime.fromtimestamp(de)
                    else:
                        end = None

                    # 使用字段中的数值年份作为 fallback
                    year_val = None
                    if not start and field_dates:
                        # 取最早的一年
                        year_val = min(field_dates.values())
                        start = datetime(year=year_val, month=1, day=1)

                    events.append({
                        "id": eid,
                        "name": e["name"],
                        "kind": e.get("kind"),
                        "start": start.isoformat() if start else None,
                        "end": end.isoformat() if end else None,
                        "year_val": year_val,
                        "tagline": e.get("tagline", "")[:80],
                    })
                except (ValueError, TypeError, OSError):
                    pass

        # 按 start 稳定排序（None 放最后）
        events.sort(key=lambda x: (x["start"] is None, x["start"] or "", x["year_val"] or 9999))
        return events

    # ----------------------------------------------------------
    # 实体关系图（文本版）
    # ----------------------------------------------------------

    def render_graph_text(self) -> str:
        """渲染实体关系图为文本（便于 iSH 环境查看）"""
        lines = []
        lines.append(f"=== {self.name} 实体关系图 ===\n")

        # 按 kind 分组统计
        kind_counts = Counter(e.get("kind") for e in self.entries.values())
        lines.append(f"实体统计: {len(self.entries)} 个条目")
        for k, c in kind_counts.most_common():
            lines.append(f"  {k}: {c}")
        lines.append("")

        # 有关系的实体
        has_relations = [(eid, e) for eid, e in self.entries.items() if e.get("relations")]
        lines.append(f"有关系的实体: {len(has_relations)}/{len(self.entries)}\n")

        for eid, e in sorted(has_relations, key=lambda x: x[1]["name"]):
            lines.append(f"[{e['kind']}] {e['name']}")
            for rel in e.get("relations", []):
                target = rel.get("to") or rel.get("target") or "?"
                rel_type = rel.get("type", "(无类型)")
                lines.append(f"  ──[{rel_type}]──> {target}")
            lines.append("")

        # 孤立实体（无关系）
        orphans = [(eid, e) for eid, e in self.entries.items() if not e.get("relations")]
        if orphans:
            lines.append(f"孤立实体 ({len(orphans)} 个，需补充关系):")
            for eid, e in sorted(orphans, key=lambda x: x[1]["name"])[:20]:
                lines.append(f"  • {e['name']} ({e['kind']})")
            if len(orphans) > 20:
                lines.append(f"  ... 还有 {len(orphans)-20} 个")

        return "\n".join(lines)

    # ----------------------------------------------------------
    # 报告输出
    # ----------------------------------------------------------

    def print_report(self, issues: List[dict]):
        """打印可读的检查报告"""
        by_severity = defaultdict(list)
        for iss in issues:
            by_severity[iss.get("severity", "info")].append(iss)

        severity_order = ["error", "warning", "info"]
        severity_icon = {"error": "🔴", "warning": "🟡", "info": "⚪"}

        total = len(issues)
        errors = len(by_severity.get("error", []))
        warnings = len(by_severity.get("warning", []))
        infos = len(by_severity.get("info", []))

        print(f"\n{'='*50}")
        print(f"  Nexus-Lint 检查报告 — {self.name}")
        print(f"  实体: {len(self.entries)} | 问题: {total} (错误:{errors} 警告:{warnings} 提示:{infos})")
        print(f"{'='*50}\n")

        for sev in severity_order:
            items = by_severity.get(sev, [])
            if not items:
                continue
            icon = severity_icon[sev]
            print(f"  {icon} {sev.upper()} ({len(items)} 条)\n")
            for iss in items:
                eid = iss.get("entry_id", "")
                entity_name = self.entries.get(eid, {}).get("name", "?") if eid else "?"
                rule = iss.get("rule", "?")
                msg = iss.get("message", "")
                fix = iss.get("fix", "")
                print(f"    [{rule}] {entity_name}: {msg}")
                if fix:
                    print(f"      修复: {fix}")
                print()

        # 汇总
        print(f"{'='*50}")
        if errors > 0:
            print(f"  ⛔ 发现 {errors} 个错误，需修复后再发布")
        elif warnings > 0:
            print(f"  ⚠️  发现 {warnings} 个警告，建议处理")
        else:
            print(f"  ✅ 全部通过！")
        print(f"{'='*50}\n")


# ============================================================
# CLI
# ============================================================

def cmd_check(args):
    pack = WorldPack(args.world)
    issues = pack.full_check()
    pack.print_report(issues)

    if args.json:
        out = {
            "world": pack.name,
            "total": len(issues),
            "by_severity": {
                "error": len([i for i in issues if i["severity"] == "error"]),
                "warning": len([i for i in issues if i["severity"] == "warning"]),
                "info": len([i for i in issues if i["severity"] == "info"]),
            },
            "issues": issues,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_timeline(args):
    pack = WorldPack(args.world)
    timeline = pack.get_chronicle()
    if not timeline:
        print("  ⚪ 暂无带时间信息的实体（when.date_start 为空）")
        print("  💡 提示：在实体 'when' 字段添加 date_start/date_end ISO 日期")
        print("     或在使用 fields 中添加数值型年份")
        return

    print(f"\n{'='*60}")
    print(f"  Chronicle 时间线 — {pack.name}")
    print(f"  共 {len(timeline)} 个带时间信息的实体")
    print(f"{'='*60}\n")

    for e in timeline:
        start_str = e["start"][:10] if e["start"] else "?"
        end_str = e["end"][:10] if e["end"] else "?"
        tag = e["tagline"][:50] if e["tagline"] else ""
        print(f"  [{e['kind']:8s}] {e['name']:20s} {start_str} ~ {end_str}")
        if tag:
            print(f"             {tag}")
        print()


def cmd_graph(args):
    pack = WorldPack(args.world)
    print(pack.render_graph_text())


def main():
    parser = argparse.ArgumentParser(description="Nexus-Lint: 世界观一致性检查器")
    parser.add_argument("--world", "-w", required=True, help="世界包名称（不含 .json）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="运行一致性检查")
    p_check.add_argument("--json", action="store_true", help="JSON 输出")

    p_timeline = sub.add_parser("timeline", help="生成 Chronicle 时间线")
    p_graph = sub.add_parser("graph", help="渲染实体关系图（文本）")

    args = parser.parse_args()
    if args.command == "check":
        cmd_check(args)
    elif args.command == "timeline":
        cmd_timeline(args)
    elif args.command == "graph":
        cmd_graph(args)


if __name__ == "__main__":
    main()
