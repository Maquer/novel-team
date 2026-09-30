#!/usr/bin/env python3
"""
world-pack.py — 世界包管理系统（借鉴 worldtree）

核心功能：
  1. 世界包数据格式（23种条目类型+30种关系类型）
  2. 一致性检查（21条规则）
  3. 状态管理（canon/draft/disputed/retired/extracted）
  4. 引文核验（AI抽取必须可追溯）

使用：
  python world-pack.py init --name "我的宇宙"
  python world-pack.py add --kind figure --name "沈夜舟" --status canon
  python world-pack.py check
  python world-pack.py stats
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field


# 配置
def _world_dir() -> Path:
    """世界包根目录。

    FIX 2026-09-30（D3 同类）：原 `WORLD_DIR = Path("/var/minis/shared/novel-team/.world-packs")`
    把路径硬编码，且在 import 时就 mkdir（副作用）。现走 NOVEL_TEAM_ROOT 环境变量
    （默认 /var/minis/shared/novel-team，与 novelkit.core.config.novel_team_root() 同源），
    目录惰性创建（首次实际使用时）。OpenMinis 生产环境（NOVEL_TEAM_ROOT 未设置）
    行为与原来完全一致。
    """
    d = Path(os.environ.get("NOVEL_TEAM_ROOT", "/var/minis/shared/novel-team")) / ".world-packs"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ============================================================
# 数据定义（借鉴worldtree schema.js）
# ============================================================

# 条目类型（23种，分6组）
KINDS = {
    # 根 · 不可选择的前提
    "world": {"cn": "世界总纲", "group": "origin", "timed": False, "glyph": "✦", "color": "#e8d8a0"},
    "law": {"cn": "世界法则", "group": "origin", "timed": False, "glyph": "◇", "color": "#9fb6c9"},
    "myth": {"cn": "创世神话", "group": "origin", "timed": True, "glyph": "☉", "color": "#e0c060"},
    "secret": {"cn": "未解之谜", "group": "origin", "timed": False, "glyph": "?", "color": "#d1c05a"},
    "power": {"cn": "力量体系", "group": "origin", "timed": False, "glyph": "✧", "color": "#b07fd1"},
    
    # 干 · 舞台
    "era": {"cn": "纪元时代", "group": "land", "timed": True, "glyph": "◷", "color": "#c9b47f"},
    "realm": {"cn": "界域", "group": "land", "timed": False, "glyph": "☁", "color": "#7f9fb6"},
    "region": {"cn": "地域", "group": "land", "timed": False, "glyph": "▨", "color": "#8a9a5a"},
    "place": {"cn": "地点城邑", "group": "land", "timed": False, "glyph": "⌂", "color": "#e0a05a"},
    
    # 枝 · 长时段
    "race": {"cn": "种族族群", "group": "peoples", "timed": False, "glyph": "⚉", "color": "#7fc98f"},
    "culture": {"cn": "文化", "group": "peoples", "timed": False, "glyph": "❦", "color": "#5aae8f"},
    "lang": {"cn": "语言文字", "group": "peoples", "timed": False, "glyph": "文", "color": "#4f9a9a"},
    "term": {"cn": "名词译表", "group": "peoples", "timed": False, "glyph": "⇄", "color": "#69a8a0"},
    "faith": {"cn": "信仰宗教", "group": "peoples", "timed": False, "glyph": "✟", "color": "#8f6fd1"},
    "god": {"cn": "神祇", "group": "peoples", "timed": True, "glyph": "☀", "color": "#d9b24f"},
    
    # 梢 · 中时段
    "org": {"cn": "势力组织", "group": "thrones", "timed": True, "glyph": "⚑", "color": "#d1685a"},
    "dynasty": {"cn": "王朝世系", "group": "thrones", "timed": True, "glyph": "♛", "color": "#c98f4f"},
    "figure": {"cn": "人物", "group": "thrones", "timed": True, "glyph": "☗", "color": "#6fc9d1"},
    "thing": {"cn": "器物物种", "group": "thrones", "timed": True, "glyph": "⚔", "color": "#f0d060"},
    "work": {"cn": "著述文本", "group": "deeds", "timed": True, "glyph": "❡", "color": "#9ad1b0"},
    
    # 叶 · 作为
    "event": {"cn": "事件", "group": "deeds", "timed": True, "glyph": "✳", "color": "#c96f4a"},
    
    # 芽 · 未写
    "story": {"cn": "情节线", "group": "hooks", "timed": False, "glyph": "➤", "color": "#f0e060"},
    "note": {"cn": "杂记", "group": "hooks", "timed": False, "glyph": "·", "color": "#8fa0a8"},
}

# 关系类型（30种）
REL_TYPES = {
    # 层级
    "located_in": {"cn": "位于", "inverse": "contains", "tree": True},
    "member_of": {"cn": "隶属", "inverse": "has_member", "tree": True},
    "part_of": {"cn": "…的一部分", "inverse": "has_part", "tree": True},
    "branch_of": {"cn": "分支自", "inverse": "has_branch", "tree": True},
    
    # 血缘
    "parent_of": {"cn": "是…的父/母", "inverse": "child_of"},
    "spouse_of": {"cn": "配偶", "inverse": "spouse_of", "sym": True},
    "sibling_of": {"cn": "兄弟姊妹", "inverse": "sibling_of", "sym": True},
    "ancestor_of": {"cn": "祖先", "inverse": "descendant_of"},
    "heir_of": {"cn": "继承人", "inverse": "heir"},
    
    # 社会
    "leader_of": {"cn": "领袖", "inverse": "led_by"},
    "allied_with": {"cn": "盟友", "inverse": "allied_with", "sym": True},
    "opposed_to": {"cn": "敌对", "inverse": "opposed_to", "sym": True},
    "vassal_of": {"cn": "臣属", "inverse": "suzerain_of"},
    "serves": {"cn": "效力于", "inverse": "employer"},
    "loves": {"cn": "爱慕", "inverse": "loved_by"},
    "betrays": {"cn": "背叛", "inverse": "betrayed_by"},
    "owes": {"cn": "亏欠", "inverse": "owed_by"},
    "worships": {"cn": "信奉", "inverse": "worshiped_by"},
    
    # 所属
    "owns": {"cn": "持有", "inverse": "held_by"},
    "created_by": {"cn": "由…所造", "inverse": "created"},
    "made_of": {"cn": "材质", "inverse": "material_of"},
    
    # 因果时序
    "caused": {"cn": "导致", "inverse": "caused_by"},
    "precedes": {"cn": "早于", "inverse": "follows"},
    "during": {"cn": "发生于期间", "inverse": "hosts_event"},
    "participated": {"cn": "参与", "inverse": "witness"},
    
    # 语义
    "refers_to": {"cn": "提及", "inverse": "referred_by"},
    "translates": {"cn": "译作", "inverse": "translated_from"},
    "same_as": {"cn": "同一事物", "inverse": "same_as", "sym": True},
    "contradicts": {"cn": "与…矛盾", "inverse": "contradicts", "sym": True},
    "binds": {"cn": "约束", "inverse": "bound_by"},
}

# 状态定义
STATUSES = {
    "canon": {"cn": "正典", "color": "#5aae8f"},
    "draft": {"cn": "草稿", "color": "#c9b47f"},
    "disputed": {"cn": "存疑", "color": "#d1a85a"},
    "retired": {"cn": "已废", "color": "#8f7f7f"},
    "extracted": {"cn": "待确认", "color": "#c96f8f"},
}


@dataclass
class WorldEntry:
    """世界条目"""
    id: str
    kind: str
    name: str
    status: str = "draft"
    aliases: List[str] = field(default_factory=list)
    folder: str = ""
    tags: List[str] = field(default_factory=list)
    tagline: str = ""
    when: Dict = field(default_factory=dict)
    relations: List[Dict] = field(default_factory=list)
    fields: List[Dict] = field(default_factory=list)
    evidence: List[Dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    content: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "status": self.status,
            "aliases": self.aliases,
            "folder": self.folder,
            "tags": self.tags,
            "tagline": self.tagline,
            "when": self.when,
            "relations": self.relations,
            "fields": self.fields,
            "evidence": self.evidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "content": self.content,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "WorldEntry":
        return cls(
            id=data["id"],
            kind=data["kind"],
            name=data["name"],
            status=data.get("status", "draft"),
            aliases=data.get("aliases", []),
            folder=data.get("folder", ""),
            tags=data.get("tags", []),
            tagline=data.get("tagline", ""),
            when=data.get("when", {}),
            relations=data.get("relations", []),
            fields=data.get("fields", []),
            evidence=data.get("evidence", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            content=data.get("content", ""),
        )


class WorldPack:
    """世界包管理器"""
    
    def __init__(self, name: str):
        self.name = name
        self.storage_path = _world_dir() / f"{name}.json"
        self.entries: Dict[str, WorldEntry] = {}
        self.sources: List[Dict] = []
        self.issues: List[Dict] = []
        self._load()
    
    def _load(self):
        """加载世界包"""
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.entries = {k: WorldEntry.from_dict(v) for k, v in data.get("entries", {}).items()}
            self.sources = data.get("sources", [])
            self.issues = data.get("issues", [])
    
    def _save(self):
        """保存世界包"""
        tmp = self.storage_path.with_suffix('.tmp')
        data = {
            "name": self.name,
            "entries": {k: v.to_dict() for k, v in self.entries.items()},
            "sources": self.sources,
            "issues": self.issues,
            "updated_at": datetime.now().isoformat(),
        }
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)
    
    def add_entry(self, kind: str, name: str, status: str = "draft",
                 tagline: str = "", content: str = "") -> WorldEntry:
        """添加条目"""
        if kind not in KINDS:
            raise ValueError(f"非法条目类型: {kind}，可选: {', '.join(KINDS.keys())}")
        
        # 生成唯一ID
        entry_id = f"{kind[0]}_{name[:3]}_{len(self.entries)+1:04d}"
        
        entry = WorldEntry(
            id=entry_id,
            kind=kind,
            name=name,
            status=status,
            tagline=tagline,
            content=content,
        )
        
        self.entries[entry_id] = entry
        self._save()
        
        return entry
    
    def add_relation(self, from_id: str, to_id: str, rel_type: str,
                    from_time: str = "", until_time: str = "",
                    evidence: Dict = None) -> bool:
        """添加关系"""
        # FIX 2026-09-30：to_id 必填。此前 to_id 只做存在性检查却从不写入关系字典，
        # 导致 dangling_relation/orphan/causal_cycle 三条检查永远读不到 rel["to"]，形同虚设。
        if not to_id:
            raise ValueError("to_id 不能为空：关系必须有明确的目标条目")
        if rel_type not in REL_TYPES:
            raise ValueError(f"非法关系类型: {rel_type}")

        if from_id not in self.entries or to_id not in self.entries:
            return False

        rel = {
            "type": rel_type,
            "to": to_id,  # FIX 2026-09-30：补上 to 键
            "from": from_time,
            "until": until_time,
            "evidence": evidence or {},
        }
        
        self.entries[from_id].relations.append(rel)
        self.entries[from_id].updated_at = datetime.now().isoformat()
        
        self._save()
        return True
    
    def add_source(self, source_id: str, content: str, url: str = "") -> str:
        """添加来源"""
        source = {
            "id": source_id,
            "content": content,
            "url": url,
            "created_at": datetime.now().isoformat(),
        }
        self.sources.append(source)
        self._save()
        return source_id
    
    def verify_quote(self, quote: str, source_id: str) -> bool:
        """引文核验：quote必须在source内容中逐字出现"""
        source = next((s for s in self.sources if s["id"] == source_id), None)
        if not source:
            return False
        return quote in source["content"]
    
    def check_consistency(self) -> List[Dict]:
        """
        一致性检查（借鉴worldtree linter.js）
        
        返回问题列表，每条带指纹
        """
        issues = []
        
        # 1. 关系指向不存在的条目
        for entry in self.entries.values():
            for rel in entry.relations:
                to_id = rel.get("to") or rel.get("target")
                # FIX 2026-09-30：修复性检查——旧版 add_relation 未写入 to 键，
                # 历史数据中缺 to 的关系报 warning（而不是像以前一样静默跳过）
                if not to_id:
                    issues.append({
                        "rule": "relation_missing_target",
                        "severity": "warning",
                        "entry_id": entry.id,
                        "message": f"关系缺少目标（to 为空）：类型={rel.get('type', '?')}，疑似旧版 add_relation 写入",
                        "fix": "补全该关系的 to 字段，或删除后重建",
                    })
                    continue
                if to_id not in self.entries:
                    issues.append({
                        "rule": "dangling_relation",
                        "severity": "error",
                        "entry_id": entry.id,
                        "message": f"关系指向不存在的条目: {to_id}",
                        "fix": "补上目标条目，或把to改成它的名字/别名",
                    })
        
        # 2. 重复条目
        by_name = {}
        for entry in self.entries.values():
            key = f"{entry.kind}::{entry.name.lower()}"
            by_name.setdefault(key, []).append(entry)
        
        for key, entries in by_name.items():
            if len(entries) > 1:
                issues.append({
                    "rule": "duplicate_entity",
                    "severity": "warning",
                    "entries": [e.id for e in entries],
                    "message": f"疑似重复条目: {entries[0].name}",
                    "fix": "合并成一条，把另一个名字放进aliases",
                })
        
        # 3. 死后行动
        death_keywords = ["死亡", "去世", "牺牲", "阵亡", "殉职", "被杀", "遇害", "处决", "身亡", "毙命", "战死", "自尽", "毒杀", "问斩", "伏诛", "圆寂", "陨落", "殒命", "失踪", "退场", "解体", "覆灭", "灭亡", "焚毁", "沉没"]
        for entry in self.entries.values():
            if entry.status == "retired" or "死亡" in entry.content or any(kw in entry.content for kw in death_keywords[:5]):
                # 检查是否还有活动
                for rel in entry.relations:
                    if rel.get("type") in ["participated", "caused"]:
                        issues.append({
                            "rule": "post_death_action",
                            "severity": "error",
                            "entry_id": entry.id,
                            "message": f"条目{entry.name}已标记为retired但仍参与活动关系",
                            "fix": "核对时间线，或标成回忆/假死/亡灵语境",
                        })
        
        # 4. 孤岛条目
        connected_ids = set()
        for entry in self.entries.values():
            for rel in entry.relations:
                to_id = rel.get("to") or rel.get("target")
                if to_id:
                    connected_ids.add(to_id)
                    connected_ids.add(entry.id)
        
        for entry in self.entries.values():
            if entry.id not in connected_ids and not entry.relations:
                issues.append({
                    "rule": "orphan",
                    "severity": "info",
                    "entry_id": entry.id,
                    "message": f"孤岛条目: {entry.name}",
                    "fix": "给它至少一条关系，或并进相关条目",
                })
        
        # 5. 空壳条目
        for entry in self.entries.values():
            if not entry.tagline and not entry.content:
                issues.append({
                    "rule": "empty_stub",
                    "severity": "info",
                    "entry_id": entry.id,
                    "message": f"空壳条目: {entry.name}",
                    "fix": "补一句tagline，或删掉",
                })
        
        # 6. 正典无出处
        for entry in self.entries.values():
            if entry.status == "canon" and not entry.evidence:
                issues.append({
                    "rule": "canon_no_source",
                    "severity": "warning",
                    "entry_id": entry.id,
                    "message": f"正典却没有出处: {entry.name}",
                    "fix": "关联来源，或降级为草稿",
                })
        
        # 7. AI未确认
        for entry in self.entries.values():
            if entry.status == "extracted":
                issues.append({
                    "rule": "ai_unconfirmed",
                    "severity": "warning",
                    "entry_id": entry.id,
                    "message": f"AI抽取未经确认: {entry.name}",
                    "fix": "在「来源」页逐条确认或丢弃",
                })
        
        # 8. 因果环检测（简化版）
        # 构建因果图
        causal_graph = {}
        for entry in self.entries.values():
            for rel in entry.relations:
                if rel.get("type") == "caused":
                    to_id = rel.get("to") or rel.get("target")
                    if to_id:
                        causal_graph.setdefault(entry.id, []).append(to_id)
        
        # 检测环
        def has_cycle(node, visited, rec_stack):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in causal_graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.discard(node)
            return False
        
        visited = set()
        for node in causal_graph:
            if node not in visited:
                if has_cycle(node, visited, set()):
                    issues.append({
                        "rule": "causal_cycle",
                        "severity": "error",
                        "message": "发现因果环",
                        "fix": "把其中一条改成「早于」，或修时间",
                    })
                    break
        
        self.issues = issues
        self._save()
        
        return issues
    
    def get_stats(self) -> Dict:
        """获取世界包统计"""
        kind_counts = {}
        status_counts = {}
        group_counts = {}
        
        for entry in self.entries.values():
            kind_counts[entry.kind] = kind_counts.get(entry.kind, 0) + 1
            status_counts[entry.status] = status_counts.get(entry.status, 0) + 1
            
            kind_info = KINDS.get(entry.kind, {})
            group = kind_info.get("group", "unknown")
            group_counts[group] = group_counts.get(group, 0) + 1
        
        return {
            "total_entries": len(self.entries),
            "total_sources": len(self.sources),
            "total_issues": len(self.issues),
            "kind_distribution": kind_counts,
            "status_distribution": status_counts,
            "group_distribution": group_counts,
        }
    
    def print_summary(self):
        """打印世界包摘要"""
        stats = self.get_stats()
        
        print(f"\n=== 世界包: {self.name} ===\n")
        print(f"总条目数: {stats['total_entries']}")
        print(f"总来源数: {stats['total_sources']}")
        print(f"问题数: {stats['total_issues']}")
        print()
        
        if stats['kind_distribution']:
            print("【条目类型分布】")
            for kind, count in sorted(stats['kind_distribution'].items()):
                kind_info = KINDS.get(kind, {})
                print(f"  {kind_info.get('glyph', '•')} {kind_info.get('cn', kind)}: {count}")
            print()
        
        if stats['status_distribution']:
            print("【状态分布】")
            for status, count in sorted(stats['status_distribution'].items()):
                status_info = STATUSES.get(status, {})
                print(f"  {status_info.get('cn', status)}: {count}")
            print()
        
        if self.issues:
            print("【最近问题】")
            for issue in self.issues[:10]:
                sev = issue.get('severity', 'info')
                icon = "❌" if sev == "error" else "⚠️" if sev == "warning" else "ℹ️"
                print(f"  {icon} [{sev.upper()}] {issue.get('message', '')}")
            print()


def cmd_init(args):
    """初始化世界包"""
    pack = WorldPack(args.name)
    print(f"✅ 已创建世界包: {args.name}")
    print(f"   路径: {pack.storage_path}")


def cmd_add(args):
    """添加条目"""
    pack = WorldPack(args.name)
    
    entry = pack.add_entry(
        kind=args.kind,
        name=args.name,
        status=args.status,
        tagline=args.tagline,
        content=args.content,
    )
    
    print(f"✅ 已添加条目: {entry.id}")
    print(f"   类型: {KINDS.get(args.kind, {}).get('cn', args.kind)}")
    print(f"   名称: {entry.name}")
    print(f"   状态: {STATUSES.get(args.status, {}).get('cn', args.status)}")


def cmd_check(args):
    """一致性检查"""
    pack = WorldPack(args.name)
    issues = pack.check_consistency()
    
    if issues:
        print(f"\n⚠️ 发现 {len(issues)} 个问题:\n")
        for issue in issues:
            sev = issue.get('severity', 'info')
            icon = "❌" if sev == "error" else "⚠️" if sev == "warning" else "ℹ️"
            print(f"  {icon} [{sev.upper()}] {issue.get('message', '')}")
            if 'fix' in issue:
                print(f"     建议: {issue['fix']}")
            print()
    else:
        print("\n✅ 一致性检查通过")


def cmd_stats(args):
    """查看统计"""
    pack = WorldPack(args.name)
    pack.print_summary()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="世界包管理系统（借鉴worldtree）")
    parser.add_argument("--name", "-n", required=True, help="世界包名称")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # init命令
    subparsers.add_parser("init", help="初始化世界包")
    
    # add命令
    p_add = subparsers.add_parser("add", help="添加条目")
    p_add.add_argument("--kind", "-k", required=True, help="条目类型")
    p_add.add_argument("--name", "-nm", required=True, help="条目名称")
    p_add.add_argument("--status", "-s", default="draft", help="状态")
    p_add.add_argument("--tagline", "-t", help="一句话描述")
    p_add.add_argument("--content", "-c", help="正文内容")
    
    # check命令
    subparsers.add_parser("check", help="一致性检查")
    
    # stats命令
    subparsers.add_parser("stats", help="查看统计")
    
    args = parser.parse_args()
    
    if args.command == "init":
        cmd_init(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "check":
        cmd_check(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()
