#!/usr/bin/env python3
"""
world-init.py — 世界包初始化器

功能：
  1. 初始化世界包基础数据
  2. 定义核心设定（力量体系、地理、势力）
  3. 建立一致性检查基准

使用：
  python world-init.py init --project "天命"
  python world-init.py add-world --name "玄天大陆" --type continent
  python world-init.py add-power-system --name "修炼体系" --realms "淬体,筑基,金丹,元婴,化神"
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class WorldNode:
    """世界节点"""
    node_id: str
    node_type: str          # world/region/place/faction/organization/race/power_system/secret/item
    name: str
    description: str = ""
    attributes: Dict = field(default_factory=dict)
    relationships: List[Dict] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'WorldNode':
        return cls(**data)


class WorldBuilder:
    """世界构建器"""
    
    # 节点类型定义
    NODE_TYPES = {
        "world": {"cn": "世界", "parent": None, "children": ["region", "power_system"]},
        "continent": {"cn": "大陆", "parent": "world", "children": ["region", "place"]},
        "region": {"cn": "区域", "parent": "continent", "children": ["place", "faction"]},
        "place": {"cn": "地点", "parent": "region", "children": []},
        "faction": {"cn": "势力", "parent": "region", "children": ["organization"]},
        "organization": {"cn": "组织", "parent": "faction", "children": []},
        "race": {"cn": "种族", "parent": "world", "children": []},
        "power_system": {"cn": "力量体系", "parent": "world", "children": ["realm"]},
        "realm": {"cn": "境界", "parent": "power_system", "children": []},
        "secret": {"cn": "秘密", "parent": "world", "children": []},
        "item": {"cn": "物品", "parent": "world", "children": []},
    }
    
    # 关系类型定义
    RELATIONSHIP_TYPES = {
        "located_in": {"cn": "位于", "bidirectional": True},
        "belongs_to": {"cn": "隶属于", "bidirectional": True},
        "rivals": {"cn": " rival ", "bidirectional": True},
        "alliance": {"cn": "同盟", "bidirectional": True},
        "controls": {"cn": "控制", "bidirectional": False},
        "connected_to": {"cn": "连接", "bidirectional": True},
        "related_to": {"cn": "相关", "bidirectional": True},
    }
    
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.world_file = self.project_dir / "world" / "world-pack.json"
        self.nodes: Dict[str, WorldNode] = {}
        self._load()
    
    def _load(self):
        """加载世界包"""
        if self.world_file.exists():
            data = json.loads(self.world_file.read_text())
            self.nodes = {k: WorldNode.from_dict(v) for k, v in data.get("nodes", {}).items()}
    
    def _save(self):
        """保存世界包"""
        data = {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "updated_at": datetime.now().isoformat(),
        }
        self.world_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    def add_node(
        self,
        node_type: str,
        name: str,
        node_id: Optional[str] = None,
        description: str = "",
        attributes: Optional[Dict] = None,
    ) -> str:
        """添加世界节点"""
        # 验证节点类型
        if node_type not in self.NODE_TYPES:
            raise ValueError(f"不支持的节点类型: {node_type}")
        
        # 生成ID
        if not node_id:
            node_id = f"{node_type}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # 创建节点
        node = WorldNode(
            node_id=node_id,
            node_type=node_type,
            name=name,
            description=description,
            attributes=attributes or {},
        )
        
        self.nodes[node_id] = node
        self._save()
        
        return node_id
    
    def add_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        attributes: Optional[Dict] = None,
    ):
        """添加关系"""
        if rel_type not in self.RELATIONSHIP_TYPES:
            raise ValueError(f"不支持的关系类型: {rel_type}")
        
        if from_id not in self.nodes or to_id not in self.nodes:
            raise ValueError("节点不存在")
        
        # 添加关系到两个节点
        rel = {
            "type": rel_type,
            "target": to_id,
            "attributes": attributes or {},
        }
        self.nodes[from_id].relationships.append(rel)
        
        # 双向关系
        if self.RELATIONSHIP_TYPES[rel_type]["bidirectional"]:
            rel_reverse = {
                "type": rel_type,
                "target": from_id,
                "attributes": attributes or {},
            }
            self.nodes[to_id].relationships.append(rel_reverse)
        
        self._save()
    
    def check_consistency(self) -> List[Dict]:
        """检查一致性"""
        issues = []
        
        for node_id, node in self.nodes.items():
            # 检查父子关系
            parent_type = self.NODE_TYPES.get(node.node_type, {}).get("parent")
            if parent_type:
                has_parent = any(
                    rel["type"] == "located_in" or rel["type"] == "belongs_to"
                    for rel in node.relationships
                )
                if not has_parent:
                    issues.append({
                        "node_id": node_id,
                        "issue": f"{node.name}缺少父级关系",
                        "severity": "warning",
                    })
            
            # 检查必填属性
            if node.node_type == "realm":
                if "level" not in node.attributes:
                    issues.append({
                        "node_id": node_id,
                        "issue": f"{node.name}缺少境界等级",
                        "severity": "error",
                    })
        
        return issues
    
    def get_stats(self) -> Dict:
        """获取统计"""
        type_counts = {}
        for node in self.nodes.values():
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1
        
        return {
            "total_nodes": len(self.nodes),
            "by_type": type_counts,
            "total_relationships": sum(len(n.relationships) for n in self.nodes.values()) // 2,
        }


def main():
    parser = argparse.ArgumentParser(description="世界包初始化器")
    parser.add_argument("--project", "-p", required=True, help="项目目录")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # init
    init_parser = subparsers.add_parser("init", help="初始化世界包")
    init_parser.add_argument("--name", "-n", help="世界名称")
    init_parser.add_argument("--type", "-t", default="world", help="节点类型")
    
    # add-node
    add_parser = subparsers.add_parser("add-node", help="添加节点")
    add_parser.add_argument("--type", "-t", required=True, help="节点类型")
    add_parser.add_argument("--name", "-n", required=True, help="节点名称")
    add_parser.add_argument("--id", "-i", help="节点ID")
    add_parser.add_argument("--desc", "-d", default="", help="描述")
    add_parser.add_argument("--attr", "-a", help="属性JSON")
    
    # add-rel
    rel_parser = subparsers.add_parser("add-rel", help="添加关系")
    rel_parser.add_argument("--from", dest="from_id", required=True, help="源节点ID")
    rel_parser.add_argument("--to", dest="to_id", required=True, help="目标节点ID")
    rel_parser.add_argument("--type", "-t", required=True, help="关系类型")
    
    # check
    subparsers.add_parser("check", help="一致性检查")
    
    # stats
    subparsers.add_parser("stats", help="统计信息")
    
    args = parser.parse_args()
    
    builder = WorldBuilder(args.project)
    
    if args.command == "init":
        # 初始化基础世界
        world_id = builder.add_node("world", args.name or "my-world", "w001")
        print(f"✅ 已创建世界: {world_id}")
        
        # 创建默认力量体系
        power_id = builder.add_node("power_system", "修炼体系", "ps001", 
                                   "淬体→筑基→金丹→元婴→化神→炼虚→合体→大乘→渡劫")
        builder.add_relationship(world_id, power_id, "related_to")
        
        # 创建默认境界
        realms = ["淬体", "筑基", "金丹", "元婴", "化神", "炼虚", "合体", "大乘", "渡劫"]
        for i, realm in enumerate(realms, 1):
            realm_id = builder.add_node("realm", realm, f"realm-{i:03d}", 
                                       attributes={"level": i, "description": f"第{i}重境界"})
            builder.add_relationship(power_id, realm_id, "related_to")
        
        print(f"✅ 已创建力量体系: {power_id}")
        print(f"✅ 已创建 {len(realms)} 个境界")
        
    elif args.command == "add-node":
        attr = json.loads(args.attr) if args.attr else None
        node_id = builder.add_node(args.type, args.name, args.id, args.desc, attr)
        print(f"✅ 已创建节点: {node_id}")
        
    elif args.command == "add-rel":
        builder.add_relationship(args.from_id, args.to_id, args.type)
        print(f"✅ 已添加关系: {args.from_id} → {args.to_id}")
        
    elif args.command == "check":
        issues = builder.check_consistency()
        if issues:
            print(f"⚠️ 发现 {len(issues)} 个问题:\n")
            for issue in issues:
                icon = "❌" if issue["severity"] == "error" else "⚠️"
                print(f"  {icon} {issue['node_id']}: {issue['issue']}")
        else:
            print("✅ 一致性检查通过")
        
    elif args.command == "stats":
        stats = builder.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
