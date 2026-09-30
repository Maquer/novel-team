#!/usr/bin/env python3
"""
timeline.py — 时间线管理工具（借鉴 51mazi）

核心功能：
  1. 事件时间轴管理
  2. 事件类型分类
  3. 时间线可视化
  4. 事件关联分析

使用：
  python timeline.py add --event "主角出生" --date "第1章" --type birth
  python timeline.py list
  python timeline.py visualize
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field


# 配置
LEDGER_DIR = Path("/var/minis/shared/novel-team/.timeline")
LEDGER_DIR.mkdir(parents=True, exist_ok=True)


# 事件类型定义
EVENT_TYPES = {
    "birth": {"label": "出生", "color": "#3498DB", "icon": "👶"},
    "death": {"label": "死亡", "color": "#E74C3C", "icon": "💀"},
    "meeting": {"label": "相遇", "color": "#2ECC71", "icon": "🤝"},
    "conflict": {"label": "冲突", "color": "#E67E22", "icon": "⚔️"},
    "achievement": {"label": "成就", "color": "#F1C40F", "icon": "🏆"},
    "loss": {"label": "失去", "color": "#9B59B6", "icon": "😢"},
    "discovery": {"label": "发现", "color": "#1ABC9C", "icon": "🔍"},
    "betrayal": {"label": "背叛", "color": "#C0392B", "icon": "🗡️"},
    "romance": {"label": "爱情", "color": "#FF69B4", "icon": "❤️"},
    "transformation": {"label": "转变", "color": "#3498DB", "icon": "🔄"},
    "climax": {"label": "高潮", "color": "#E74C3C", "icon": "🔥"},
    "resolution": {"label": "解决", "color": "#2ECC71", "icon": "✅"},
    "foreshadow": {"label": "伏笔", "color": "#9B59B6", "icon": "📌"},
    "reveal": {"label": "揭露", "color": "#E67E22", "icon": "💡"},
}


@dataclass
class TimelineEvent:
    """时间线事件"""
    id: str
    chapter: int
    title: str
    content: str
    event_type: str
    characters: List[str] = field(default_factory=list)
    location: str = ""
    tags: List[str] = field(default_factory=list)
    importance: int = 1  # 1-5
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "chapter": self.chapter,
            "title": self.title,
            "content": self.content,
            "event_type": self.event_type,
            "characters": self.characters,
            "location": self.location,
            "tags": self.tags,
            "importance": self.importance,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TimelineEvent":
        return cls(
            id=data["id"],
            chapter=data["chapter"],
            title=data["title"],
            content=data["content"],
            event_type=data["event_type"],
            characters=data.get("characters", []),
            location=data.get("location", ""),
            tags=data.get("tags", []),
            importance=data.get("importance", 1),
            created_at=data.get("created_at", ""),
        )


class TimelineManager:
    """时间线管理器"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = LEDGER_DIR / f"{project_id}.json"
        self.events: List[TimelineEvent] = []
        self._load()
    
    def _load(self):
        """加载时间线数据"""
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.events = [TimelineEvent.from_dict(e) for e in data.get("events", [])]
    
    def _save(self):
        """保存时间线数据"""
        tmp = self.storage_path.with_suffix('.tmp')
        data = {"events": [e.to_dict() for e in self.events]}
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)
    
    def add_event(self, chapter: int, title: str, content: str,
                 event_type: str = "other", characters: List[str] = None,
                 location: str = "", tags: List[str] = None,
                 importance: int = 1) -> TimelineEvent:
        """添加事件"""
        # 生成事件ID
        event_id = f"E{len(self.events)+1:04d}"
        
        event = TimelineEvent(
            id=event_id,
            chapter=chapter,
            title=title,
            content=content,
            event_type=event_type,
            characters=characters or [],
            location=location,
            tags=tags or [],
            importance=importance,
        )
        
        self.events.append(event)
        self._save()
        
        return event
    
    def get_events_by_chapter(self, chapter: int) -> List[TimelineEvent]:
        """获取指定章节的事件"""
        return [e for e in self.events if e.chapter == chapter]
    
    def get_events_by_type(self, event_type: str) -> List[TimelineEvent]:
        """获取指定类型的事件"""
        return [e for e in self.events if e.event_type == event_type]
    
    def get_related_events(self, character: str, range_chapters: int = 5) -> List[TimelineEvent]:
        """获取与角色相关的事件（前后range_chapters章）"""
        # 找到角色的事件
        char_events = [e for e in self.events if character in e.characters]
        
        if not char_events:
            return []
        
        # 获取范围
        ref_chapter = char_events[-1].chapter
        start = max(1, ref_chapter - range_chapters)
        end = ref_chapter + range_chapters
        
        return [e for e in self.events if start <= e.chapter <= end]
    
    def visualize(self) -> str:
        """生成可视化文本"""
        lines = []
        lines.append("\n=== 时间线 ===\n")
        
        # 按章节排序
        sorted_events = sorted(self.events, key=lambda e: (e.chapter, e.created_at))
        
        current_chapter = 0
        for event in sorted_events:
            if event.chapter != current_chapter:
                current_chapter = event.chapter
                lines.append(f"\n【第{current_chapter}章】\n")
            
            # 获取事件类型图标
            type_info = EVENT_TYPES.get(event.event_type, {"icon": "📌", "label": "其他"})
            
            lines.append(f"  {type_info['icon']} {event.title}")
            lines.append(f"     类型: {type_info['label']} | 重要度: {'⭐' * event.importance}")
            if event.characters:
                lines.append(f"     角色: {', '.join(event.characters)}")
            if event.location:
                lines.append(f"     地点: {event.location}")
            lines.append(f"     {event.content[:50]}...")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_summary(self) -> Dict:
        """获取时间线摘要"""
        type_counts = {}
        chapter_counts = {}
        
        for event in self.events:
            type_counts[event.event_type] = type_counts.get(event.event_type, 0) + 1
            chapter_counts[event.chapter] = chapter_counts.get(event.chapter, 0) + 1
        
        return {
            "total_events": len(self.events),
            "type_distribution": type_counts,
            "chapter_distribution": chapter_counts,
            "events_by_chapter": dict(sorted(chapter_counts.items())),
        }
    
    def print_summary(self):
        """打印时间线摘要"""
        summary = self.get_summary()
        
        print("\n=== 时间线摘要 ===\n")
        print(f"总事件数: {summary['total_events']}")
        print()
        
        if summary['type_distribution']:
            print("【事件类型分布】")
            for etype, count in sorted(summary['type_distribution'].items()):
                type_info = EVENT_TYPES.get(etype, {"icon": "📌", "label": etype})
                print(f"  {type_info['icon']} {type_info['label']}: {count}")
            print()
        
        if summary['chapter_distribution']:
            print("【章节分布】")
            for ch, count in sorted(summary['chapter_distribution'].items()):
                print(f"  第{ch}章: {count}个事件")
            print()


def cmd_add(args):
    """添加事件命令"""
    manager = TimelineManager(args.project_id)
    
    event = manager.add_event(
        chapter=args.chapter,
        title=args.title,
        content=args.content,
        event_type=args.type,
        characters=args.characters.split(',') if args.characters else None,
        location=args.location,
        tags=args.tags.split(',') if args.tags else None,
        importance=args.importance,
    )
    
    print(f"✅ 已添加事件: {event.id}")
    print(f"   章节: 第{event.chapter}章")
    print(f"   标题: {event.title}")
    print(f"   类型: {EVENT_TYPES.get(args.type, {}).get('label', args.type)}")
    if event.characters:
        print(f"   角色: {', '.join(event.characters)}")


def cmd_list(args):
    """列出事件命令"""
    manager = TimelineManager(args.project_id)
    
    if args.chapter:
        events = manager.get_events_by_chapter(args.chapter)
        print(f"\n📍 第{args.chapter}章的事件:\n")
    elif args.type:
        events = manager.get_events_by_type(args.type)
        print(f"\n📍 {args.type}类型的事件:\n")
    else:
        events = manager.events
        print("\n📍 所有事件:\n")
    
    for event in events:
        type_info = EVENT_TYPES.get(event.event_type, {"icon": "📌", "label": "其他"})
        print(f"{type_info['icon']} [第{event.chapter}章] {event.title}")
        print(f"   {event.content[:50]}...")
        print()


def cmd_visualize(args):
    """可视化时间线"""
    manager = TimelineManager(args.project_id)
    print(manager.visualize())


def cmd_summary(args):
    """查看时间线摘要"""
    manager = TimelineManager(args.project_id)
    manager.print_summary()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="时间线管理工具（借鉴51mazi）")
    parser.add_argument("--project-id", "-p", required=True, help="项目ID")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # add命令
    p_add = subparsers.add_parser("add", help="添加事件")
    p_add.add_argument("--chapter", "-c", type=int, required=True, help="章节号")
    p_add.add_argument("--title", "-t", required=True, help="事件标题")
    p_add.add_argument("--content", required=True, help="事件内容")
    p_add.add_argument("--type", "-y", default="other", help="事件类型")
    p_add.add_argument("--characters", help="相关角色（逗号分隔）")
    p_add.add_argument("--location", help="地点")
    p_add.add_argument("--tags", help="标签（逗号分隔）")
    p_add.add_argument("--importance", "-i", type=int, default=1, help="重要度(1-5)")
    
    # list命令
    p_list = subparsers.add_parser("list", help="列出事件")
    p_list.add_argument("--chapter", type=int, help="按章节过滤")
    p_list.add_argument("--type", help="按类型过滤")
    
    # visualize命令
    subparsers.add_parser("visualize", help="可视化时间线")
    
    # summary命令
    subparsers.add_parser("summary", help="查看时间线摘要")
    
    args = parser.parse_args()
    
    if args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "visualize":
        cmd_visualize(args)
    elif args.command == "summary":
        cmd_summary(args)
    else:
        parser.print_help()
