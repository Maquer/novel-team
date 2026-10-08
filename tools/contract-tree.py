#!/usr/bin/env python3
"""
contract-tree.py — 合同树程序校验（借鉴 AI-automatically-generates-novels）

核心功能：
  1. 合同节点：每个节点带结构化进口/出口（账目/线头/事实三类字段）
  2. 程序校验：「上一块出口 == 下一块进口」由程序逐字段比对
  3. 咬合检查：不靠模型自觉，靠程序强制

使用：
  python contract-tree.py init --title "我的小说"
  python contract-tree.py add --contract C001 --import "100两银子" --export "50两"
  python contract-tree.py check
  python contract-tree.py visualize
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


# 配置
LEDGER_DIR = Path("/var/minis/shared/novel-team/.contract-tree")
LEDGER_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ContractNode:
    """合同节点"""
    id: str
    title: str
    chapter_range: Tuple[int, int]  # (起始章, 结束章)
    
    # 三类字段
    accounts: List[str] = field(default_factory=list)      # 账目：兵力、钱粮等可计数状态
    threads: List[str] = field(default_factory=list)       # 线头：伏笔、悬念等未解线索
    facts: List[str] = field(default_factory=list)         # 事实：已确认的事件和状态
    
    # 状态
    status: str = "draft"  # draft | approved | halted
    export_fields: Dict = field(default_factory=dict)
    import_fields: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "chapter_range": list(self.chapter_range),
            "accounts": self.accounts,
            "threads": self.threads,
            "facts": self.facts,
            "status": self.status,
            "export_fields": self.export_fields,
            "import_fields": self.import_fields,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ContractNode":
        return cls(
            id=data["id"],
            title=data["title"],
            chapter_range=tuple(data["chapter_range"]),
            accounts=data.get("accounts", []),
            threads=data.get("threads", []),
            facts=data.get("facts", []),
            status=data.get("status", "draft"),
            export_fields=data.get("export_fields", {}),
            import_fields=data.get("import_fields", {}),
        )


class ContractTree:
    """合同树管理器"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = LEDGER_DIR / f"{project_id}.json"
        self.nodes: Dict[str, ContractNode] = {}
        self._load()
    
    def _load(self):
        """加载合同树数据"""
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.nodes = {k: ContractNode.from_dict(v) for k, v in data.get("contracts", {}).items()}
    
    def _save(self):
        """保存合同树数据"""
        tmp = self.storage_path.with_suffix('.tmp')
        data = {"contracts": {k: v.to_dict() for k, v in self.nodes.items()}}
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)
    
    def add_node(self, node_id: str, title: str, start_chapter: int, end_chapter: int,
                accounts: List[str] = None, threads: List[str] = None,
                facts: List[str] = None) -> ContractNode:
        """添加合同节点"""
        if node_id in self.nodes:
            print(f"⚠️ 合同节点已存在: {node_id}")
            return self.nodes[node_id]
        
        node = ContractNode(
            id=node_id,
            title=title,
            chapter_range=(start_chapter, end_chapter),
            accounts=accounts or [],
            threads=threads or [],
            facts=facts or [],
        )
        
        self.nodes[node_id] = node
        self._save()
        
        return node
    
    def update_node(self, node_id: str, **kwargs) -> Optional[ContractNode]:
        """更新合同节点"""
        node = self.nodes.get(node_id)
        if not node:
            return None
        
        for key, value in kwargs.items():
            if hasattr(node, key):
                setattr(node, key, value)
        
        self._save()
        return node
    
    def check咬合(self, node_id: str) -> List[Dict]:
        """
        检查合同咬合：上一块出口 == 下一块进口
        
        返回咬合问题列表
        """
        issues = []
        node = self.nodes.get(node_id)
        if not node:
            return [{"type": "error", "message": f"合同节点不存在: {node_id}"}]
        
        # 找到前一个和后一个节点
        sorted_nodes = sorted(self.nodes.values(), key=lambda n: n.chapter_range[0])
        current_idx = next((i for i, n in enumerate(sorted_nodes) if n.id == node_id), None)
        
        if current_idx is None:
            return issues
        
        # 检查与前一节点的咬合
        if current_idx > 0:
            prev_node = sorted_nodes[current_idx - 1]
            # 出口 vs 进口
            prev_exports = set(prev_node.accounts + prev_node.facts)
            curr_imports = set(node.accounts + node.import_fields.keys())
            
            missing = prev_exports - curr_imports
            if missing:
                issues.append({
                    "type": "warning",
                    "from": prev_node.id,
                    "to": node_id,
                    "message": f"前节点出口未在本节点进口: {', '.join(list(missing)[:3])}",
                    "fields": list(missing)[:5]
                })
        
        # 检查与后一节点的咬合
        if current_idx < len(sorted_nodes) - 1:
            next_node = sorted_nodes[current_idx + 1]
            curr_exports = set(node.accounts + node.facts)
            next_imports = set(next_node.accounts + next_node.import_fields.keys())
            
            missing = curr_exports - next_imports
            if missing:
                issues.append({
                    "type": "warning",
                    "from": node_id,
                    "to": next_node.id,
                    "message": f"本节点出口未在后节点进口: {', '.join(list(missing)[:3])}",
                    "fields": list(missing)[:5]
                })
        
        return issues
    
    def validate_all(self) -> Dict:
        """验证整个合同树"""
        all_issues = []
        valid_nodes = []
        
        for node_id in self.nodes:
            issues = self.check咬合(node_id)
            if issues:
                all_issues.extend(issues)
            else:
                valid_nodes.append(node_id)
        
        return {
            "total_nodes": len(self.nodes),
            "valid_nodes": len(valid_nodes),
            "issues": all_issues,
            "status": "all_ok" if not all_issues else "has_issues"
        }
    
    def visualize(self) -> str:
        """生成可视化文本"""
        lines = []
        lines.append("\n=== 合同树结构 ===\n")
        
        sorted_nodes = sorted(self.nodes.values(), key=lambda n: n.chapter_range[0])
        
        for i, node in enumerate(sorted_nodes):
            lines.append(f"【{node.id}】{node.title}")
            lines.append(f"  章节范围: {node.chapter_range[0]}-{node.chapter_range[1]}")
            lines.append(f"  状态: {node.status}")
            
            if node.accounts:
                lines.append(f"  账目: {', '.join(node.accounts[:3])}")
            if node.threads:
                lines.append(f"  线头: {', '.join(node.threads[:3])}")
            if node.facts:
                lines.append(f"  事实: {len(node.facts)}条")
            
            if i < len(sorted_nodes) - 1:
                lines.append("  ↓")
            lines.append("")
        
        return "\n".join(lines)
    
    def get_summary(self) -> Dict:
        """获取合同树摘要"""
        total = len(self.nodes)
        approved = len([n for n in self.nodes.values() if n.status == "approved"])
        draft = len([n for n in self.nodes.values() if n.status == "draft"])
        halted = len([n for n in self.nodes.values() if n.status == "halted"])
        
        return {
            "total": total,
            "approved": approved,
            "draft": draft,
            "halted": halted,
            "status": "all_approved" if approved == total else "in_progress"
        }


def cmd_init(args):
    """初始化合同树"""
    tree = ContractTree(args.project_id)
    
    # 创建根合同
    root = tree.add_node(
        node_id="ROOT",
        title="根合同",
        start_chapter=1,
        end_chapter=1,
        accounts=["全书总字数目标"],
        facts=["故事起点设定"]
    )
    
    print(f"✅ 已初始化合同树: {args.project_id}")
    print(f"   根合同: {root.id}")
    print(f"   节点数: {len(tree.nodes)}")


def cmd_add(args):
    """添加合同节点"""
    tree = ContractTree(args.project_id)
    
    node = tree.add_node(
        node_id=args.id,
        title=args.title,
        start_chapter=args.start,
        end_chapter=args.end,
        accounts=args.accounts.split(',') if args.accounts else None,
        threads=args.threads.split(',') if args.threads else None,
        facts=args.facts.split(',') if args.facts else None,
    )
    
    print(f"✅ 已添加合同节点: {node.id}")
    print(f"   标题: {node.title}")
    print(f"   章节: {node.chapter_range[0]}-{node.chapter_range[1]}")


def cmd_check(args):
    """检查合同咬合"""
    tree = ContractTree(args.project_id)
    
    if args.node:
        issues = tree.check咬合(args.node)
        if issues:
            print(f"\n⚠️ 合同 {args.node} 存在咬合问题:\n")
            for issue in issues:
                print(f"  [{issue['type']}] {issue['message']}")
        else:
            print(f"\n✅ 合同 {args.node} 咬合检查通过")
    else:
        result = tree.validate_all()
        print(f"\n=== 合同树验证结果 ===")
        print(f"总节点: {result['total']}")
        print(f"有效节点: {result['valid_nodes']}")
        print(f"状态: {result['status']}")
        
        if result['issues']:
            print(f"\n【咬合问题】")
            for issue in result['issues'][:10]:
                print(f"  [{issue['type']}] {issue['message']}")


def cmd_visualize(args):
    """可视化合同树"""
    tree = ContractTree(args.project_id)
    print(tree.visualize())


def cmd_summary(args):
    """查看合同树摘要"""
    tree = ContractTree(args.project_id)
    summary = tree.get_summary()
    
    print("\n=== 合同树摘要 ===\n")
    print(f"总节点: {summary['total']}")
    print(f"  已通过: {summary['approved']}")
    print(f"  草稿: {summary['draft']}")
    print(f"  已暂停: {summary['halted']}")
    print(f"\n状态: {summary['status']}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="合同树程序校验（借鉴AI-automatically-generates-novels）")
    parser.add_argument("--project-id", "-p", required=True, help="项目ID")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # init命令
    subparsers.add_parser("init", help="初始化合同树")
    
    # add命令
    p_add = subparsers.add_parser("add", help="添加合同节点")
    p_add.add_argument("--id", required=True, help="合同ID")
    p_add.add_argument("--title", required=True, help="标题")
    p_add.add_argument("--start", type=int, required=True, help="起始章")
    p_add.add_argument("--end", type=int, required=True, help="结束章")
    p_add.add_argument("--accounts", help="账目（逗号分隔）")
    p_add.add_argument("--threads", help="线头（逗号分隔）")
    p_add.add_argument("--facts", help="事实（逗号分隔）")
    
    # check命令
    p_check = subparsers.add_parser("check", help="检查合同咬合")
    p_check.add_argument("--node", help="指定节点ID（不指定则检查全部）")
    
    # visualize命令
    subparsers.add_parser("visualize", help="可视化合同树")
    
    # summary命令
    subparsers.add_parser("summary", help="查看合同树摘要")
    
    args = parser.parse_args()
    
    if args.command == "init":
        cmd_init(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "check":
        cmd_check(args)
    elif args.command == "visualize":
        cmd_visualize(args)
    elif args.command == "summary":
        cmd_summary(args)
    else:
        parser.print_help()
