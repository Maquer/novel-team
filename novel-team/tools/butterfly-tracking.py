#!/usr/bin/env python3
"""
蝴蝶效应分叉追踪 — 大纲编排增强

借鉴 ai-fiction-writer novel-outline Skill 的蝴蝶效应分叉追踪机制。
支持在大纲节拍中标记「分叉点」，记录原历史/新历史/触发条件/影响章节，
并在后续写作中自动提醒分叉影响。

使用：
  python3 butterfly-tracking.py init --novel-id my-novel
  python3 butterfly-tracking.py add-branch --chapter 5 --beat 3 \
      --description "萧辰决定不使用天命剑" \
      --original "使用天命剑获胜" \
      --trigger "萧辰认为天命剑会暴露身份"
  python3 butterfly-tracking.py impact --chapter 8
  python3 butterfly-tracking.py list
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

TRACKING_DIR = Path("/var/minis/shared/novel-team/.butterfly")


@dataclass
class BranchPoint:
    """分叉点"""
    id: str
    chapter: int
    beat: int           # 在章节内的节拍编号
    description: str    # 当前历史（实际发生的）
    original: str       # 原历史（未受干预的走向）
    trigger: str        # 触发条件
    triggered_at: str   # 触发章节
    affected_chapters: List[int]  # 影响章节
    status: str = "active"  # active/paid_off/abandoned

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "chapter": self.chapter,
            "beat": self.beat,
            "description": self.description,
            "original": self.original,
            "trigger": self.trigger,
            "triggered_at": self.triggered_at,
            "affected_chapters": self.affected_chapters,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'BranchPoint':
        return cls(**data)


class ButterflyTracker:
    """蝴蝶效应分叉追踪器"""

    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.tracking_dir = TRACKING_DIR / novel_id
        self.tracking_dir.mkdir(parents=True, exist_ok=True)
        self.branches_path = self.tracking_dir / "branches.json"
        self.branches: List[BranchPoint] = []
        self._load()

    def _load(self):
        if self.branches_path.exists():
            data = json.loads(self.branches_path.read_text(encoding='utf-8'))
            self.branches = [BranchPoint.from_dict(b) for b in data.get("branches", [])]
        else:
            self.branches = []

    def _save(self):
        data = {"branches": [b.to_dict() for b in self.branches]}
        tmp = self.branches_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.branches_path)

    def add_branch(
        self,
        chapter: int,
        beat: int,
        description: str,
        original: str,
        trigger: str,
        affected_chapters: Optional[List[int]] = None,
    ) -> BranchPoint:
        """添加分叉点"""
        bid = f"branch-{len(self.branches)+1:03d}"
        branch = BranchPoint(
            id=bid,
            chapter=chapter,
            beat=beat,
            description=description,
            original=original,
            trigger=trigger,
            triggered_at=datetime.now().isoformat(),
            affected_chapters=affected_chapters or [],
            status="active",
        )
        self.branches.append(branch)
        self._save()
        return branch

    def mark_paid_off(self, branch_id: str, chapter: int):
        """标记分叉已回收"""
        for b in self.branches:
            if b.id == branch_id:
                b.status = "paid_off"
                if chapter not in b.affected_chapters:
                    b.affected_chapters.append(chapter)
                b._save()
                return b
        return None

    def mark_abandoned(self, branch_id: str):
        """标记分叉已废弃"""
        for b in self.branches:
            if b.id == branch_id:
                b.status = "abandoned"
                b._save()
                return b
        return None

    def get_active_branches(self) -> List[BranchPoint]:
        """获取所有活跃分叉"""
        return [b for b in self.branches if b.status == "active"]

    def get_branches_for_chapter(self, chapter: int) -> List[BranchPoint]:
        """获取影响某章节的分叉"""
        result = []
        for b in self.branches:
            if b.status == "active" and chapter in b.affected_chapters:
                result.append(b)
            # 也包含触发章节本身
            if b.chapter == chapter and b.status == "active":
                if b not in result:
                    result.append(b)
        return result

    def check_impact(self, chapter: int) -> Dict:
        """检查某章节受哪些分叉影响"""
        branches = self.get_branches_for_chapter(chapter)
        return {
            "chapter": chapter,
            "active_branches": len(branches),
            "branches": [b.to_dict() for b in branches],
            "warnings": [],
        }

    def get_summary(self) -> Dict:
        """获取分叉统计"""
        active = sum(1 for b in self.branches if b.status == "active")
        paid_off = sum(1 for b in self.branches if b.status == "paid_off")
        abandoned = sum(1 for b in self.branches if b.status == "abandoned")
        return {
            "total": len(self.branches),
            "active": active,
            "paid_off": paid_off,
            "abandoned": abandoned,
            "branches": [b.to_dict() for b in self.branches],
        }

    def export_md(self) -> str:
        """导出为 Markdown"""
        lines = ["# 蝴蝶效应分叉追踪\n"]
        summary = self.get_summary()
        lines.append(f"总计: {summary['total']} 个分叉点\n")
        lines.append(f"- 活跃: {summary['active']}")
        lines.append(f"- 已回收: {summary['paid_off']}")
        lines.append(f"- 已废弃: {summary['abandoned']}\n")
        lines.append("---\n")

        for b in self.branches:
            status_icon = {"active": "🟡", "paid_off": "✅", "abandoned": "⬜"}.get(b.status, "?")
            lines.append(f"## {status_icon} {b.id} (第{b.chapter}章 节拍{b.beat})\n")
            lines.append(f"- **触发条件**: {b.trigger}")
            lines.append(f"- **原历史**: {b.original}")
            lines.append(f"- **新历史**: {b.description}")
            lines.append(f"- **影响章节**: {b.affected_chapters or '待确认'}")
            lines.append(f"- **状态**: {b.status}")
            lines.append("")
        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="蝴蝶效应分叉追踪")
    subparsers = parser.add_subparsers(dest="command")

    # init
    p_init = subparsers.add_parser("init", help="初始化分叉追踪")
    p_init.add_argument("--novel-id", required=True)

    # add-branch
    p_add = subparsers.add_parser("add-branch", help="添加分叉点")
    p_add.add_argument("--novel-id", required=True)
    p_add.add_argument("--chapter", required=True, type=int, help="触发章节")
    p_add.add_argument("--beat", required=True, type=int, help="节拍编号")
    p_add.add_argument("--description", "-d", required=True, help="新历史描述")
    p_add.add_argument("--original", "-o", required=True, help="原历史描述")
    p_add.add_argument("--trigger", "-t", required=True, help="触发条件")
    p_add.add_argument("--affect", "-a", nargs="*", type=int, help="影响章节列表")

    # impact
    p_impact = subparsers.add_parser("impact", help="检查某章节受哪些分叉影响")
    p_impact.add_argument("--novel-id", required=True)
    p_impact.add_argument("--chapter", required=True, type=int)

    # list
    p_list = subparsers.add_parser("list", help="列出所有分叉")
    p_list.add_argument("--novel-id", required=True)

    # pay-off
    p_pay = subparsers.add_parser("pay-off", help="标记分叉已回收")
    p_pay.add_argument("--novel-id", required=True)
    p_pay.add_argument("--branch-id", required=True)
    p_pay.add_argument("--chapter", required=True, type=int)

    # abandon
    p_abandon = subparsers.add_parser("abandon", help="标记分叉已废弃")
    p_abandon.add_argument("--novel-id", required=True)
    p_abandon.add_argument("--branch-id", required=True)

    # stats
    p_stats = subparsers.add_parser("stats", help="分叉统计")
    p_stats.add_argument("--novel-id", required=True)

    # export
    p_export = subparsers.add_parser("export", help="导出为Markdown")
    p_export.add_argument("--novel-id", required=True)
    p_export.add_argument("--output", "-o", default="")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    tracker = ButterflyTracker(args.novel_id)

    if args.command == "init":
        print(f"✅ 已初始化 '{args.novel_id}' 的蝴蝶效应追踪")
        print(f"   数据文件：{tracker.branches_path}")

    elif args.command == "add-branch":
        branch = tracker.add_branch(
            chapter=args.chapter,
            beat=args.beat,
            description=args.description,
            original=args.original,
            trigger=args.trigger,
            affected_chapters=args.affect,
        )
        print(f"✅ 已添加分叉点 {branch.id}")
        print(f"   章节: 第{branch.chapter}章 节拍{branch.beat}")
        print(f"   触发: {branch.trigger}")
        print(f"   原历史: {branch.original}")
        print(f"   新历史: {branch.description}")
        if branch.affected_chapters:
            print(f"   影响章节: {branch.affected_chapters}")

    elif args.command == "impact":
        result = tracker.check_impact(args.chapter)
        if result["active_branches"] == 0:
            print(f"✅ 第 {args.chapter} 章无活跃分叉影响")
        else:
            print(f"⚠️ 第 {args.chapter} 章受 {result['active_branches']} 个分叉影响：")
            for b in result["branches"]:
                print(f"  [{b['id']}] {b['description'][:50]}...")
                print(f"    触发: {b['trigger']}")
                print(f"    原历史: {b['original']}")
                print()

    elif args.command == "list":
        summary = tracker.get_summary()
        print(f"\n📊 分叉追踪统计（共 {summary['total']} 个）：")
        print(f"  活跃: {summary['active']} | 已回收: {summary['paid_off']} | 已废弃: {summary['abandoned']}")
        print()
        for b in tracker.branches:
            icon = {"active": "🟡", "paid_off": "✅", "abandoned": "⬜"}.get(b.status, "?")
            print(f"  {icon} {b.id} | 第{b.chapter}章节{b.beat} | {b.description[:40]}...")

    elif args.command == "pay-off":
        branch = tracker.mark_paid_off(args.branch_id, args.chapter)
        if branch:
            print(f"✅ 已标记 {branch.id} 在第{args.chapter}章回收")
        else:
            print(f"❌ 未找到分叉点 {args.branch_id}")

    elif args.command == "abandon":
        branch = tracker.mark_abandoned(args.branch_id)
        if branch:
            print(f"✅ 已废弃分叉点 {branch.id}")
        else:
            print(f"❌ 未找到分叉点 {args.branch_id}")

    elif args.command == "stats":
        summary = tracker.get_summary()
        print(f"\n📊 '{args.novel_id}' 分叉统计：")
        print(f"  总计: {summary['total']}")
        print(f"  活跃: {summary['active']}")
        print(f"  已回收: {summary['paid_off']}")
        print(f"  已废弃: {summary['abandoned']}")

    elif args.command == "export":
        md = tracker.export_md()
        if args.output:
            Path(args.output).write_text(md, encoding='utf-8')
            print(f"✅ 已导出到 {args.output}")
        else:
            print(md)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
