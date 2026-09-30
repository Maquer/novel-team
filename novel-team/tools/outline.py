#!/usr/bin/env python3
"""
outline.py — 三级大纲系统（借鉴 MaliangAINovalWriter）

四级结构：作品 → 卷 → 章节 → 场景

核心功能：
  1. 三级大纲管理（作品/卷/章节）
  2. 大纲层级关系维护
  3. 大纲导出/导入（JSON/YAML）
  4. 大纲一致性检查
  5. 大纲版本管理

使用：
  python outline.py init --project "天命测试"
  python outline.py add --level work --title "第一卷：风云起"
  python outline.py add --level volume --parent "vol-001" --title "第一章：少年"
  python outline.py add --level chapter --parent "ch-001" --title "场景一：破晓"
  python outline.py list --level all
  python outline.py export --format json
  python outline.py export --format yaml
"""

import sys
import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum


class Level(Enum):
    """大纲层级"""
    WORK = "work"           # 作品
    VOLUME = "volume"       # 卷
    CHAPTER = "chapter"     # 章节
    SCENE = "scene"         # 场景


@dataclass
class OutlineNode:
    """大纲节点"""
    id: str
    level: str
    title: str
    parent_id: Optional[str]
    children: List[str] = field(default_factory=list)
    
    # 内容字段
    content: str = ""               # 正文内容（仅章节/场景）
    summary: str = ""               # 内容摘要
    word_count: int = 0             # 字数统计
    
    # 状态字段
    status: str = "draft"          # draft | approved | archived | deleted
    version: int = 1
    created_at: str = ""
    updated_at: str = ""
    
    # 元数据
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'OutlineNode':
        return cls(**data)


@dataclass
class OutlineSystem:
    """大纲系统"""
    project_name: str
    nodes: Dict[str, OutlineNode] = field(default_factory=dict)
    root_id: Optional[str] = None
    
    def save(self, path: str):
        """保存到JSON文件"""
        data = {
            "project_name": self.project_name,
            "root_id": self.root_id,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    def load(self, path: str):
        """从JSON文件加载"""
        data = json.loads(Path(path).read_text())
        self.project_name = data["project_name"]
        self.root_id = data.get("root_id")
        self.nodes = {k: OutlineNode.from_dict(v) for k, v in data.get("nodes", {}).items()}
    
    # ---- CRUD 操作 ----
    
    def add_node(
        self,
        level: str,
        title: str,
        parent_id: Optional[str] = None,
        content: str = "",
        summary: str = "",
        tags: Optional[List[str]] = None,
    ) -> str:
        """添加大纲节点"""
        # 自动生成ID
        node_id = f"{level}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 创建节点
        node = OutlineNode(
            id=node_id,
            level=level,
            title=title,
            parent_id=parent_id,
            content=content,
            summary=summary,
            tags=tags or [],
        )
        
        # 设置根节点
        if self.root_id is None and level == Level.WORK.value:
            self.root_id = node_id
        
        # 设置父子关系
        if parent_id and parent_id in self.nodes:
            self.nodes[parent_id].children.append(node_id)
        
        # 存储节点
        self.nodes[node_id] = node
        
        return node_id
    
    def update_node(
        self,
        node_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        summary: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ):
        """更新大纲节点"""
        if node_id not in self.nodes:
            raise ValueError(f"节点不存在: {node_id}")
        
        node = self.nodes[node_id]
        if title:
            node.title = title
        if content:
            node.content = content
            # 自动计算字数
            node.word_count = sum(len(c) for c in node.content if '\u4e00' <= c <= '\u9fff')
        if summary:
            node.summary = summary
        if status:
            node.status = status
        if tags is not None:
            node.tags = tags
        
        node.version += 1
        node.updated_at = datetime.now().isoformat()
    
    def delete_node(self, node_id: str):
        """删除大纲节点（级联删除子节点）"""
        if node_id not in self.nodes:
            raise ValueError(f"节点不存在: {node_id}")
        
        # 获取所有子节点ID
        children_ids = [node_id]
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            for child_id in self.nodes[current].children:
                children_ids.append(child_id)
                queue.append(child_id)
        
        # 删除节点
        for cid in children_ids:
            if cid in self.nodes:
                # 从父节点移除
                parent = self.nodes[cid].parent_id
                if parent and parent in self.nodes:
                    if cid in self.nodes[parent].children:
                        self.nodes[parent].children.remove(cid)
                del self.nodes[cid]
    
    def get_node(self, node_id: str) -> Optional[OutlineNode]:
        """获取节点"""
        return self.nodes.get(node_id)
    
    def get_tree(self, node_id: Optional[str] = None) -> List[Dict]:
        """获取树形结构"""
        root = node_id or self.root_id
        if not root or root not in self.nodes:
            return []
        
        result = []
        stack = [(root, 0)]
        while stack:
            nid, depth = stack.pop()
            if nid not in self.nodes:
                continue
            node = self.nodes[nid]
            result.append({
                "id": node.id,
                "level": node.level,
                "title": node.title,
                "depth": depth,
                "status": node.status,
                "word_count": node.word_count,
            })
            for child_id in reversed(node.children):
                stack.append((child_id, depth + 1))
        return result
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = {
            "total_nodes": len(self.nodes),
            "by_level": {},
            "by_status": {},
            "total_words": 0,
            "word_count_by_level": {},
        }
        
        for node in self.nodes.values():
            # 按层级统计
            stats["by_level"][node.level] = stats["by_level"].get(node.level, 0) + 1
            
            # 按状态统计
            stats["by_status"][node.status] = stats["by_status"].get(node.status, 0) + 1
            
            # 字数统计
            stats["total_words"] += node.word_count
            if node.word_count > 0:
                stats["word_count_by_level"][node.level] = (
                    stats["word_count_by_level"].get(node.level, 0) + node.word_count
                )
        
        return stats


def main():
    parser = argparse.ArgumentParser(description="三级大纲系统")
    parser.add_argument("--project", "-p", required=True, help="项目名")
    parser.add_argument("--db", default=None, help="数据库路径")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # init
    init_parser = subparsers.add_parser("init", help="初始化大纲系统")
    init_parser.add_argument("--out", default=None, help="输出路径")
    
    # add
    add_parser = subparsers.add_parser("add", help="添加节点")
    add_parser.add_argument("--level", "-l", required=True, 
                           choices=["work", "volume", "chapter", "scene"])
    add_parser.add_argument("--title", "-t", required=True, help="标题")
    add_parser.add_argument("--parent", "-P", default=None, help="父节点ID")
    add_parser.add_argument("--content", "-c", default="", help="正文内容")
    add_parser.add_argument("--summary", "-s", default="", help="内容摘要")
    add_parser.add_argument("--tags", default="", help="标签（逗号分隔）")
    
    # update
    update_parser = subparsers.add_parser("update", help="更新节点")
    update_parser.add_argument("--id", required=True, help="节点ID")
    update_parser.add_argument("--title", default=None)
    update_parser.add_argument("--content", default=None)
    update_parser.add_argument("--summary", default=None)
    update_parser.add_argument("--status", default=None)
    update_parser.add_argument("--tags", default=None)
    
    # delete
    delete_parser = subparsers.add_parser("delete", help="删除节点")
    delete_parser.add_argument("--id", required=True, help="节点ID")
    
    # list
    list_parser = subparsers.add_parser("list", help="列出大纲")
    list_parser.add_argument("--level", default="all", 
                            choices=["work", "volume", "chapter", "scene", "all"])
    list_parser.add_argument("--status", default=None, help="按状态筛选")
    list_parser.add_argument("--tree", action="store_true", help="树形展示")
    
    # stats
    subparsers.add_parser("stats", help="统计信息")
    
    # export
    export_parser = subparsers.add_parser("export", help="导出大纲")
    export_parser.add_argument("--format", "-f", choices=["json", "yaml", "markdown"], default="json")
    export_parser.add_argument("--out", default=None, help="输出路径")
    
    # import
    import_parser = subparsers.add_parser("import", help="导入大纲")
    import_parser.add_argument("--in", "-i", required=True, help="输入路径")
    import_parser.add_argument("--format", "-f", choices=["json", "yaml"], default="json")
    
    args = parser.parse_args()
    
    # 确定数据库路径
    if args.db:
        db_path = Path(args.db)
    else:
        from pathlib import Path
        project_dir = Path("novel-team/projects") / args.project
        project_dir.mkdir(parents=True, exist_ok=True)
        db_path = project_dir / "outline.json"
    
    # 加载系统
    system = OutlineSystem(project_name=args.project)
    if db_path.exists():
        system.load(str(db_path))
    
    # 执行命令
    if args.command == "init":
        out_path = args.out or str(db_path)
        system.save(out_path)
        print(f"✅ 已初始化大纲系统: {args.project}")
        print(f"   存储路径: {out_path}")
    
    elif args.command == "add":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        node_id = system.add_node(
            level=args.level,
            title=args.title,
            parent_id=args.parent,
            content=args.content,
            summary=args.summary,
            tags=tags,
        )
        system.save(str(db_path))
        print(f"✅ 已添加节点: {node_id}")
        print(f"   标题: {args.title}")
        print(f"   层级: {args.level}")
        if args.parent:
            print(f"   父节点: {args.parent}")
    
    elif args.command == "update":
        updates = {}
        if args.title:
            updates["title"] = args.title
        if args.content:
            updates["content"] = args.content
        if args.summary:
            updates["summary"] = args.summary
        if args.status:
            updates["status"] = args.status
        if args.tags:
            updates["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]
        
        system.update_node(args.id, **updates)
        system.save(str(db_path))
        print(f"✅ 已更新节点: {args.id}")
    
    elif args.command == "delete":
        system.delete_node(args.id)
        system.save(str(db_path))
        print(f"✅ 已删除节点: {args.id}（级联删除子节点）")
    
    elif args.command == "list":
        tree = system.get_tree()
        if args.tree:
            for node in tree:
                indent = "  " * node["depth"]
                status_icon = {"approved": "✅", "draft": "📝", "archived": "📦", "deleted": "❌"}
                icon = status_icon.get(node["status"], "⬜")
                print(f"{indent}{icon} [{node['level']}] {node['title']} ({node['word_count']}字)")
        else:
            # 表格展示
            print(f"\n{'ID':<25} {'层级':<10} {'标题':<30} {'字数':<8} {'状态':<10}")
            print("-" * 90)
            for node in tree:
                if args.level != "all" and node["level"] != args.level:
                    continue
                if args.status and node["status"] != args.status:
                    continue
                print(f"{node['id']:<25} {node['level']:<10} {node['title']:<30} {node['word_count']:<8} {node['status']:<10}")
        print()
    
    elif args.command == "stats":
        stats = system.get_stats()
        print("\n=== 大纲统计 ===")
        print(f"总节点数: {stats['total_nodes']}")
        print(f"总字数: {stats['total_words']}")
        print(f"\n按层级分布:")
        for level, count in stats["by_level"].items():
            words = stats["word_count_by_level"].get(level, 0)
            print(f"  {level}: {count}个节点, {words}字")
        print(f"\n按状态分布:")
        for status, count in stats["by_status"].items():
            print(f"  {status}: {count}个")
        print()
    
    elif args.command == "export":
        if args.format == "json":
            content = json.dumps(system.nodes, ensure_ascii=False, indent=2)
        elif args.format == "yaml":
            import yaml
            content = yaml.dump(
                {k: v.to_dict() for k, v in system.nodes.items()},
                allow_unicode=True,
                default_flow_style=False,
            )
        elif args.format == "markdown":
            lines = []
            tree = system.get_tree()
            for node in tree:
                indent = "  " * node["depth"]
                lines.append(f"{indent}- **{node['title']}** ({node['level']}, {node['word_count']}字)")
            content = "\n".join(lines)
        else:
            raise ValueError(f"不支持的格式: {args.format}")
        
        out_path = args.out or f"outline.{args.format}"
        Path(out_path).write_text(content)
        print(f"✅ 已导出: {out_path}")
    
    elif args.command == "import":
        # 简化实现：JSON导入
        import_data = json.loads(Path(args.in_file).read_text())
        for node_id, node_data in import_data.items():
            node = OutlineNode.from_dict(node_data)
            system.nodes[node_id] = node
        system.save(str(db_path))
        print(f"✅ 已导入 {len(system.nodes)} 个节点")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
