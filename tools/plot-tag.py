#!/usr/bin/env python3
"""
plot-tag.py — 剧情标签系统（借鉴 AbilityKit GameplayTags 模块）

核心设计：
  标签树形结构：支持层级和组织
  按标签查询：FindTags("HasBuff.Fire") 返回所有带火系Buff的角色
  用于规则配置引用，避免硬编码

小说适配：
  剧情标签：#复仇线 / #感情线 / #成长线 / #伏笔_天命剑
  角色标签：#主角 / #反派 / #中立 / #已死
  世界标签：#玄天大陆 / #天剑宗 / #血煞门
  用途：快速检索、批量过滤、剧情线分析

使用：
  python plot-tag.py add --project my-novel --tag 复仇线 --parent 主线 --depth 2
  python plot-tag.py query --project my-novel --tag 复仇线
  python plot-tag.py search --project my-novel --keyword 天命
  python plot-tag.py tree --project my-novel
  python plot-tag.py count --project my-novel
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

# 代际项目守卫（唯一路径入口）
sys.path.insert(0, str(Path(__file__).parent))
from project_guard import resolve


@dataclass
class PlotTag:
    """剧情标签"""
    id: str
    name: str  # 标签名（如 复仇线）
    path: str  # 完整路径（如 主线/复仇线）
    parent_id: Optional[str] = None
    depth: int = 1
    description: str = ""
    tags: List[str] = field(default_factory=list)  # 关联实体标签
    entity_refs: Dict[str, List[str]] = field(default_factory=dict)  # 实体引用: {entity_type: [entity_ids]}
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "description": self.description,
            "tags": self.tags,
            "entity_refs": self.entity_refs,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'PlotTag':
        return cls(**data)


class PlotTagManager:
    """剧情标签管理器"""

    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = resolve(project_id).tags() / f"{project_id}.json"
        self.tags: Dict[str, PlotTag] = {}
        self._counter = 0
        self._load()

    def _load(self):
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.tags = {k: PlotTag.from_dict(v) for k, v in data.get("tags", {}).items()}
            self._counter = data.get("counter", 0)

    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "tags": {k: v.to_dict() for k, v in self.tags.items()},
            "counter": self._counter,
            "updated_at": datetime.now().isoformat(),
        }
        tmp = self.storage_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)

    def add(self, name: str, parent_id: Optional[str] = None,
            depth: int = 1, description: str = "",
            tags: List[str] = None, metadata: Dict = None) -> str:
        """添加标签"""
        self._counter += 1
        tag_id = f"TG{self._counter:04d}"

        # 计算路径
        if parent_id and parent_id in self.tags:
            parent = self.tags[parent_id]
            path = f"{parent.path}/{name}"
            actual_depth = parent.depth + 1
        else:
            path = name
            actual_depth = 1

        tag = PlotTag(
            id=tag_id,
            name=name,
            path=path,
            parent_id=parent_id,
            depth=actual_depth,
            description=description,
            tags=tags or [],
            created_at=datetime.now().isoformat(),
            metadata=metadata or {},
        )
        self.tags[tag_id] = tag
        self._save()
        return tag_id

    def link_entity(self, tag_id: str, entity_type: str, entity_id: str) -> bool:
        """关联实体到标签"""
        tag = self.tags.get(tag_id)
        if not tag:
            return False
        if entity_type not in tag.entity_refs:
            tag.entity_refs[entity_type] = []
        if entity_id not in tag.entity_refs[entity_type]:
            tag.entity_refs[entity_type].append(entity_id)
        self._save()
        return True

    def unlink_entity(self, tag_id: str, entity_type: str, entity_id: str) -> bool:
        """解除实体关联"""
        tag = self.tags.get(tag_id)
        if not tag or entity_type not in tag.entity_refs:
            return False
        if entity_id in tag.entity_refs[entity_type]:
            tag.entity_refs[entity_type].remove(entity_id)
            self._save()
            return True
        return False

    def find_by_tag(self, keyword: str) -> List[PlotTag]:
        """按关键词搜索标签（名称/描述/tags字段模糊匹配）"""
        kw = keyword.lower()
        return [t for t in self.tags.values()
                if kw in t.name.lower() or kw in t.description.lower()
                or any(kw in tk.lower() for tk in t.tags)]

    def find_by_path_prefix(self, prefix: str) -> List[PlotTag]:
        """按路径前缀查找"""
        return [t for t in self.tags.values() if t.path.startswith(prefix)]

    def get_entities_by_tag(self, tag_id: str) -> Dict[str, List[str]]:
        """获取标签关联的所有实体"""
        tag = self.tags.get(tag_id)
        if not tag:
            return {}
        return dict(tag.entity_refs)

    def get_descendants(self, tag_id: str) -> List[PlotTag]:
        """获取子标签（递归）"""
        parent = self.tags.get(tag_id)
        if not parent:
            return []
        result = []
        for t in self.tags.values():
            if t.parent_id == tag_id:
                result.append(t)
                result.extend(self.get_descendants(t.id))
        return result

    def get_tree(self) -> List[Dict]:
        """生成标签树"""
        roots = [t for t in self.tags.values() if not t.parent_id]

        def build_node(tag: PlotTag) -> Dict:
            children = [build_node(self.tags[cid]) for cid, t in self.tags.items() if t.parent_id == tag.id]
            return {
                "id": tag.id,
                "name": tag.name,
                "path": tag.path,
                "depth": tag.depth,
                "entity_count": sum(len(v) for v in tag.entity_refs.values()),
                "children": children,
            }

        return [build_node(r) for r in roots]

    def get_summary(self) -> Dict:
        """获取摘要"""
        by_depth = defaultdict(int)
        total_entities = 0
        for t in self.tags.values():
            by_depth[t.depth] += 1
            total_entities += sum(len(v) for v in t.entity_refs.values())
        return {
            "total_tags": len(self.tags),
            "max_depth": max(by_depth.keys()) if by_depth else 0,
            "by_depth": dict(by_depth),
            "total_entity_refs": total_entities,
        }


def cmd_add(args):
    mgr = PlotTagManager(args.project)
    tag_id = mgr.add(
        name=args.name,
        parent_id=args.parent if args.parent else None,
        depth=int(args.depth or 1),
        description=args.desc or "",
        tags=args.tags.split(",") if args.tags else None,
    )
    tag = mgr.tags[tag_id]
    print(json.dumps({"tag_id": tag_id, "name": tag.name, "path": tag.path,
                       "depth": tag.depth}, ensure_ascii=False, indent=2))
    return 0


def cmd_link(args):
    mgr = PlotTagManager(args.project)
    ok = mgr.link_entity(args.tag_id, args.entity_type, args.entity_id)
    print(f"{'✅' if ok else '❌'} 实体关联 {'成功' if ok else '失败'}: {args.entity_type}:{args.entity_id} → {args.tag_id}")
    return 0 if ok else 1


def cmd_search(args):
    mgr = PlotTagManager(args.project)
    results = mgr.find_by_tag(args.keyword)
    print(json.dumps({"keyword": args.keyword, "count": len(results),
                       "tags": [{"id": t.id, "name": t.name, "path": t.path, "entities": sum(len(v) for v in t.entity_refs.values())}
                                for t in results]}, ensure_ascii=False, indent=2))
    return 0


def cmd_tree(args):
    mgr = PlotTagManager(args.project)
    tree = mgr.get_tree()
    print(json.dumps(tree, ensure_ascii=False, indent=2))
    return 0


def cmd_entities(args):
    mgr = PlotTagManager(args.project)
    entities = mgr.get_entities_by_tag(args.tag_id)
    print(json.dumps({"tag_id": args.tag_id, "entities": entities}, ensure_ascii=False, indent=2))
    return 0


def cmd_summary(args):
    mgr = PlotTagManager(args.project)
    print(json.dumps(mgr.get_summary(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="剧情标签系统（借鉴AbilityKit GameplayTags）")
    parser.add_argument("--project", "-p", required=True)
    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="添加标签")
    p_add.add_argument("--name", "-n", required=True)
    p_add.add_argument("--parent", help="父标签ID")
    p_add.add_argument("--depth", help="深度")
    p_add.add_argument("--desc", help="描述")
    p_add.add_argument("--tags", help="关联标签（逗号分隔）")

    p_link = sub.add_parser("link", help="关联实体")
    p_link.add_argument("--tag-id", required=True)
    p_link.add_argument("--entity-type", required=True, help="实体类型（character/world/event）")
    p_link.add_argument("--entity-id", required=True)

    p_search = sub.add_parser("search", help="搜索标签")
    p_search.add_argument("--keyword", "-k", required=True)

    p_tree = sub.add_parser("tree", help="显示标签树")

    p_ents = sub.add_parser("entities", help="查看标签关联实体")
    p_ents.add_argument("--tag-id", required=True)

    p_sum = sub.add_parser("summary", help="总体摘要")

    args = parser.parse_args()
    cmd_map = {"add": cmd_add, "link": cmd_link, "search": cmd_search,
               "tree": cmd_tree, "entities": cmd_entities, "summary": cmd_summary}
    fn = cmd_map.get(args.command)
    if fn:
        sys.exit(fn(args))
    else:
        parser.print_help()
        sys.exit(1)
