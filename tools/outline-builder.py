#!/usr/bin/env python3
"""
outline-builder.py — 大纲构建器

功能：
  1. 创建三级大纲（作品→卷→章节）
  2. 定义章节要点和情节线
  3. 管理伏笔和钩子
  4. 检查大纲一致性

使用：
  python outline-builder.py init --project "天命"
  python outline-builder.py add-volume --volume 1 --title "少年出茅庐"
  python outline-builder.py add-chapter --volume 1 --chapter 1 --title "开篇"
  python outline-builder.py add-foreshadow --chapter 1 --content "天命剑来历" --tier 1
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


class ContractViolation(Exception):
    """契约违约：前置校验失败。调用方应 exit 1 并向 stderr 输出 ERROR: 前缀。"""
    pass

@dataclass
class OutlineNode:
    """大纲节点"""
    node_id: str
    level: str           # work/volume/chapter/scene
    title: str
    parent_id: Optional[str]
    summary: str = ""
    key_points: List[str] = field(default_factory=list)
    foreshadowings: List[Dict] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    word_count_target: int = 0
    status: str = "draft"  # draft/approved/archived
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'OutlineNode':
        return cls(**data)


@dataclass
class Foreshadow:
    """伏笔"""
    id: str
    content: str
    tier: int           # 1=主线, 2=支线, 3=细节
    planted_at: str     # 埋设章节
    payoff_at: Optional[str] = None  # 回收章节
    status: str = "planted"  # planted/paid_off/abandoned
    
    def to_dict(self) -> Dict:
        return asdict(self)


class OutlineBuilder:
    """大纲构建器"""
    
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.outline_file = self.project_dir / "outline" / "outline.json"
        self.nodes: Dict[str, OutlineNode] = {}
        self.foreshadowings: Dict[str, Foreshadow] = {}
        self._load()
    
    def _load(self):
        """加载大纲"""
        if self.outline_file.exists():
            data = json.loads(self.outline_file.read_text())
            self.nodes = {k: OutlineNode.from_dict(v) for k, v in data.get("nodes", {}).items()}
            _fsh = data.get("foreshadowings", {})
            if isinstance(_fsh, list):
                self.foreshadowings = {
                    f.get("id", f"foil-{i}"): Foreshadow(**f)
                    for i, f in enumerate(_fsh)
                }
            else:
                self.foreshadowings = {
                    k: Foreshadow(**v) for k, v in _fsh.items()
                }
    
    def _next_seq(self, prefix: str) -> int:
        """生成下一个序列号（从现有同类ID扫描得出，确定性、无时间戳碰撞）。"""
        mx = 0
        for nid in self.nodes:
            m = re.match(rf"^{prefix}-(\d+)$", nid)
            if m:
                mx = max(mx, int(m.group(1)))
        for fid in self.foreshadowings:
            m = re.match(rf"^{prefix}-(\d+)$", fid)
            if m:
                mx = max(mx, int(m.group(1)))
        return mx + 1

    def _check_unique(self, node_id: str, kind: str) -> None:
        """前置校验：ID 不可重复。反模式：同名ID静默覆盖既有节点 = 无声数据丢失。"""
        if node_id in self.nodes:
            raise ContractViolation(
                f"前置校验失败: {kind} {node_id!r} 已存在，不可重复创建"
                f"（现有标题：{self.nodes[node_id].title!r}）。请改用其他编号。")

    def _check_parent(self, parent_id: str, kind: str) -> None:
        """前置校验：父节点必须已存在。失败即抛错，不静默降级。

        契约：TEAM.md 工具契约规范「前置校验」条款。
        反模式：父ID不存在时仍写入节点并返回成功 → 孤儿节点 + 同步静默失败。
        """
        if parent_id not in self.nodes:
            raise ContractViolation(
                f"前置校验失败: {kind} {parent_id!r} 不存在。"
                f"现有 {len(self.nodes)} 个节点，请先创建父节点。"
            )

    def _save(self):
        """保存大纲"""
        data = {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "foreshadowings": {k: v.to_dict() for k, v in self.foreshadowings.items()},
            "updated_at": datetime.now().isoformat(),
        }
        self.outline_file.parent.mkdir(parents=True, exist_ok=True)
        self.outline_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    def add_work(self, title: str, summary: str = "") -> str:
        """添加作品节点"""
        node_id = f"work-{self._next_seq('work'):04d}"
        self._check_unique(node_id, "作品")
        node = OutlineNode(
            node_id=node_id,
            level="work",
            title=title,
            parent_id=None,
            summary=summary,
        )
        self.nodes[node_id] = node
        self._save()
        return node_id
    
    def add_volume(self, work_id: str, volume_num: int, title: str, 
                   summary: str = "") -> str:
        """添加卷节点"""
        self._check_parent(work_id, "作品")
        node_id = f"vol-{volume_num:03d}"
        self._check_unique(node_id, "卷")
        node = OutlineNode(
            node_id=node_id,
            level="volume",
            title=title,
            parent_id=work_id,
            summary=summary,
        )
        self.nodes[node_id] = node
        
        # 层级关系由 parent_id 字段表达；children 派生自 parent_id，不单独持久化。
        # （修前此处 append 到一次性列表，实际从未落盘，见 TEAM.md v0.59 C9c）
        self._save()
        return node_id
    
    def add_chapter(self, volume_id: str, chapter_num: int, title: str,
                   summary: str = "", key_points: Optional[List[str]] = None,
                   word_count: int = 2000) -> str:
        """添加章节节点"""
        self._check_parent(volume_id, "卷")
        node_id = f"ch-{chapter_num:04d}"
        self._check_unique(node_id, "章节")
        node = OutlineNode(
            node_id=node_id,
            level="chapter",
            title=title,
            parent_id=volume_id,
            summary=summary,
            key_points=key_points or [],
            word_count_target=word_count,
        )
        self.nodes[node_id] = node
        
        # 层级关系由 parent_id 字段表达；children 派生自 parent_id，不单独持久化。
        # （修前此处 append 到一次性列表，实际从未落盘，见 TEAM.md v0.59 C9c）
        self._save()
        return node_id
    
    def add_foreshadow(self, chapter_id: str, content: str, tier: int = 1) -> str:
        """添加伏笔"""
        self._check_parent(chapter_id, "章节")
        foil_id = f"foil-{self._next_seq('foil'):04d}"
        self._check_unique(foil_id, "伏笔")
        foil = Foreshadow(
            id=foil_id,
            content=content,
            tier=tier,
            planted_at=chapter_id,
        )
        self.foreshadowings[foil_id] = foil
        
        # 伏笔归属由 foreshadowings 字典 + planted_at 字段表达，不反向写入章节节点。
        # （修前此处 append 到节点 foreshadowings 字段，但 foreshadowings 类型为 List[Dict]，
        #   写入字符串ID会造成类型不一致，见 TEAM.md v0.59 C9c）
        self._save()
        return foil_id
    
    def pay_off_foreshadow(self, foil_id: str, chapter_id: str):
        """回收伏笔。前置校验：伏笔必须存在且未回收，回收章节必须存在。"""
        if foil_id not in self.foreshadowings:
            raise ContractViolation(f"前置校验失败: 伏笔 {foil_id!r} 不存在")
        if chapter_id not in self.nodes:
            raise ContractViolation(f"前置校验失败: 回收章节 {chapter_id!r} 不存在")
        if self.foreshadowings[foil_id].status == "paid_off":
            raise ContractViolation(
                f"前置校验失败: 伏笔 {foil_id!r} 已于 "
                f"{self.foreshadowings[foil_id].payoff_at} 回收，不可重复回收")
        self.foreshadowings[foil_id].payoff_at = chapter_id
        self.foreshadowings[foil_id].status = "paid_off"
        self._save()
    
    def get_tree(self) -> List[Dict]:
        """获取树形结构"""
        tree = []
        for node in self.nodes.values():
            if node.level == "work":
                tree.append(self._build_tree_node(node))
        return tree
    
    def _build_tree_node(self, node: OutlineNode, depth: int = 0) -> Dict:
        """递归构建树节点"""
        result = {
            "id": node.node_id,
            "level": node.level,
            "title": node.title,
            "depth": depth,
            "summary": node.summary[:100] if node.summary else "",
            "word_count_target": node.word_count_target,
            "status": node.status,
            "children": [],
        }
        
        # 子节点按 parent_id 反查派生（修前读 node.children，该字段不存在 → 树恒为空）
        for other in self.nodes.values():
            if other.parent_id == node.node_id:
                result["children"].append(self._build_tree_node(other, depth + 1))
        
        return result
    
    def get_stats(self) -> Dict:
        """获取统计"""
        by_level = {}
        total_words = 0
        foreshadow_count = 0
        paid_foreshadow = 0
        
        for node in self.nodes.values():
            by_level[node.level] = by_level.get(node.level, 0) + 1
            total_words += node.word_count_target
        
        for foil in self.foreshadowings.values():
            foreshadow_count += 1
            if foil.status == "paid_off":
                paid_foreshadow += 1
        
        return {
            "total_nodes": len(self.nodes),
            "by_level": by_level,
            "total_word_count": total_words,
            "foreshadow_count": foreshadow_count,
            "foreshadow_paid": paid_foreshadow,
            "foreshadow_pending": foreshadow_count - paid_foreshadow,
        }


def _dispatch():
    parser = argparse.ArgumentParser(description="大纲构建器")
    parser.add_argument("--project", "-p", required=True, help="项目目录")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # add-work
    work_parser = subparsers.add_parser("add-work", help="添加作品")
    work_parser.add_argument("--title", "-t", required=True, help="作品标题")
    work_parser.add_argument("--summary", "-s", default="", help="作品简介")
    
    # add-volume
    vol_parser = subparsers.add_parser("add-volume", help="添加卷")
    vol_parser.add_argument("--work-id", "-w", required=True, help="作品ID")
    vol_parser.add_argument("--num", "-n", type=int, required=True, help="卷号")
    vol_parser.add_argument("--title", "-t", required=True, help="卷标题")
    vol_parser.add_argument("--summary", "-s", default="", help="卷简介")
    
    # add-chapter
    ch_parser = subparsers.add_parser("add-chapter", help="添加章节")
    ch_parser.add_argument("--volume-id", "-v", required=True, help="卷ID")
    ch_parser.add_argument("--num", "-n", type=int, required=True, help="章节号")
    ch_parser.add_argument("--title", "-t", required=True, help="章节标题")
    ch_parser.add_argument("--summary", "-s", default="", help="章节简介")
    ch_parser.add_argument("--points", "-p", nargs="*", help="要点")
    ch_parser.add_argument("--words", "-W", type=int, default=2000, help="目标字数")
    
    # add-foreshadow
    foil_parser = subparsers.add_parser("add-foreshadow", help="添加伏笔")
    foil_parser.add_argument("--chapter-id", "-c", required=True, help="章节ID")
    foil_parser.add_argument("--content", "-C", required=True, help="伏笔内容")
    foil_parser.add_argument("--tier", "-T", type=int, default=1, help="层级")
    
    # pay-off
    payoff_parser = subparsers.add_parser("pay-off", help="回收伏笔")
    payoff_parser.add_argument("--foil-id", "-f", required=True, help="伏笔ID")
    payoff_parser.add_argument("--chapter-id", "-c", required=True, help="回收章节ID")
    
    # tree
    subparsers.add_parser("tree", help="显示大纲树")
    
    # stats
    subparsers.add_parser("stats", help="统计信息")
    
    args = parser.parse_args()
    
    builder = OutlineBuilder(args.project)
    
    if args.command == "add-work":
        work_id = builder.add_work(args.title, args.summary)
        print(f"✅ 已创建作品: {work_id}")
        # 事件发射：作品创建 → 触发世界包同步扫描
        try:
            import time as _time
            novel_id = Path(args.project).name
            _events_file = Path(__file__).parent.parent / ".events" / f"{novel_id}.jsonl"
            _events_file.parent.mkdir(parents=True, exist_ok=True)
            _evt = {"event": "OUTLINE_WORK_CREATED", "work_id": work_id,
                    "title": args.title, "summary": args.summary,
                    "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S")}
            with open(_events_file, "a", encoding="utf-8") as _f:
                _f.write(json.dumps(_evt, ensure_ascii=False) + "\n")
        except Exception:
            pass
        
    elif args.command == "add-volume":
        vol_id = builder.add_volume(args.work_id, args.num, args.title, args.summary)
        print(f"✅ 已创建卷: {vol_id}")
        # 事件发射：卷创建 → 触发世界包同步扫描（高置信度）
        try:
            import time as _time
            novel_id = Path(args.project).name
            _events_file = Path(__file__).parent.parent / ".events" / f"{novel_id}.jsonl"
            _events_file.parent.mkdir(parents=True, exist_ok=True)
            _evt = {"event": "OUTLINE_VOLUME_ADDED", "volume_id": vol_id,
                    "volume_num": args.num, "title": args.title, "summary": args.summary,
                    "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S")}
            with open(_events_file, "a", encoding="utf-8") as _f:
                _f.write(json.dumps(_evt, ensure_ascii=False) + "\n")
        except Exception:
            pass
        
    elif args.command == "add-chapter":
        ch_id = builder.add_chapter(
            args.volume_id, args.num, args.title, args.summary, args.points, args.words
        )
        print(f"✅ 已创建章节: {ch_id}")
        # 事件发射：大纲章节新增 → 触发世界包同步扫描（置信度0.95）
        try:
            import time as _time
            # 从项目路径提取novel-id（取最后一级目录名）
            novel_id = Path(args.project).name
            _events_file = Path(__file__).parent.parent / ".events" / f"{novel_id}.jsonl"
            _events_file.parent.mkdir(parents=True, exist_ok=True)
            _evt = {"event": "OUTLINE_CHAPTER_ADDED",
                    "chapter": args.num,
                    "title": args.title,
                    "key_points": args.points or [],
                    "timestamp": _time.strftime("%Y-%m-%dT%H:%M:%S")}
            with open(_events_file, "a", encoding="utf-8") as _f:
                _f.write(json.dumps(_evt, ensure_ascii=False) + "\n")
        except Exception:
            pass
        
    elif args.command == "add-foreshadow":
        foil_id = builder.add_foreshadow(args.chapter_id, args.content, args.tier)
        print(f"✅ 已添加伏笔: {foil_id}")
        
    elif args.command == "pay-off":
        builder.pay_off_foreshadow(args.foil_id, args.chapter_id)
        print(f"✅ 已回收伏笔: {args.foil_id}")
        
    elif args.command == "tree":
        tree = builder.get_tree()
        print(json.dumps(tree, ensure_ascii=False, indent=2))
        
    elif args.command == "stats":
        stats = builder.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    
    else:
        parser.print_help()


def main():
    """入口。契约：前置校验失败 → exit 1 + stderr 输出 ERROR: 前缀（TEAM.md 工具契约规范）。"""
    try:
        _dispatch()
    except ContractViolation as e:
        import sys as _sys
        print(f"ERROR: {e}", file=_sys.stderr)
        _sys.exit(1)


if __name__ == "__main__":
    import argparse
    main()
