#!/usr/bin/env python3
"""
team-manager.py — 团队管理器

功能：
  1. 团队配置加载和管理
  2. 任务分配和调度
  3. 进度跟踪和统计
  4. 质量门禁执行

使用：
  python team-manager.py init --project "天命"
  python team-manager.py assign --role lead_writer --task "创作第1章"
  python team-manager.py status
  python team-manager.py report
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict

# 代际项目守卫（唯一路径入口）
sys.path.insert(0, str(Path(__file__).parent))
from project_guard import resolve


@dataclass
class TeamMember:
    """团队成员"""
    member_id: str
    role: str
    name: str
    department: str
    tasks: List[Dict] = field(default_factory=list)
    completed_tasks: List[Dict] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TeamMember':
        return cls(**data)


@dataclass
class Task:
    """任务"""
    task_id: str
    title: str
    description: str
    assignee: str
    priority: str  # high/medium/low
    status: str    # pending/in_progress/completed/blocked
    created_at: str
    due_at: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Task':
        return cls(**data)


class TeamManager:
    """团队管理器"""
    
    def __init__(self, config_path: str = "team/team-config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.members: Dict[str, TeamMember] = {}
        self.tasks: Dict[str, Task] = {}
        self.project_dir = resolve(args.project).root_dir
        self._load_state()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        if self.config_path.exists():
            return json.loads(self.config_path.read_text())
        return {"roles": [], "departments": [], "workflow": {}}
    
    def _load_state(self):
        """加载状态"""
        state_path = self.config_path.parent / "state.json"
        if state_path.exists():
            data = json.loads(state_path.read_text())
            self.members = {k: TeamMember.from_dict(v) for k, v in data.get("members", {}).items()}
            self.tasks = {k: Task.from_dict(v) for k, v in data.get("tasks", {}).items()}
    
    def _save_state(self):
        """保存状态"""
        state_path = self.config_path.parent / "state.json"
        data = {
            "members": {k: v.to_dict() for k, v in self.members.items()},
            "tasks": {k: v.to_dict() for k, v in self.tasks.items()},
            "updated_at": datetime.now().isoformat(),
        }
        state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    def init_team(self, project_name: str):
        """初始化团队"""
        roles = self.config.get("roles", [])
        
        for role in roles:
            member_id = f"member-{role['id']}"
            member = TeamMember(
                member_id=member_id,
                role=role['id'],
                name=role['name'],
                department=role.get('department', 'unknown'),
            )
            self.members[member_id] = member
        
        self._save_state()
        print(f"✅ 团队初始化完成：{len(self.members)}个成员")
    
    def assign_task(self, role: str, title: str, description: str = "", 
                   priority: str = "medium", due_days: int = 1) -> str:
        """分配任务"""
        # 找到对应角色的成员
        assignee = None
        for mid, member in self.members.items():
            if member.role == role:
                assignee = mid
                break
        
        if not assignee:
            raise ValueError(f"未找到角色为 {role} 的成员")
        
        # 创建任务
        task_id = f"task-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        due_at = (datetime.now() + timedelta(days=due_days)).isoformat()
        
        task = Task(
            task_id=task_id,
            title=title,
            description=description,
            assignee=assignee,
            priority=priority,
            status="pending",
            created_at=datetime.now().isoformat(),
            due_at=due_at,
        )
        
        self.tasks[task_id] = task
        self.members[assignee].tasks.append(task_id)
        
        self._save_state()
        return task_id
    
    def complete_task(self, task_id: str):
        """完成任务"""
        if task_id not in self.tasks:
            raise ValueError(f"任务不存在: {task_id}")
        
        task = self.tasks[task_id]
        task.status = "completed"
        task.completed_at = datetime.now().isoformat()
        
        # 移动到已完成列表
        member = self.members[task.assignee]
        if task_id in member.tasks:
            member.tasks.remove(task_id)
        member.completed_tasks.append(task_id)
        
        self._save_state()
        print(f"✅ 任务已完成: {task_id}")
    
    def get_status(self) -> Dict:
        """获取状态"""
        stats = {
            "total_members": len(self.members),
            "total_tasks": len(self.tasks),
            "pending_tasks": sum(1 for t in self.tasks.values() if t.status == "pending"),
            "in_progress_tasks": sum(1 for t in self.tasks.values() if t.status == "in_progress"),
            "completed_tasks": sum(1 for t in self.tasks.values() if t.status == "completed"),
            "members": {},
        }
        
        for mid, member in self.members.items():
            stats["members"][mid] = {
                "name": member.name,
                "role": member.role,
                "department": member.department,
                "pending_tasks": len(member.tasks),
                "completed_tasks": len(member.completed_tasks),
            }
        
        return stats
    
    def generate_report(self) -> str:
        """生成报告"""
        stats = self.get_status()
        
        report = []
        report.append("# 团队状态报告")
        report.append("")
        report.append(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"团队成员：{stats['total_members']}人")
        report.append(f"任务总数：{stats['total_tasks']}个")
        report.append(f"待处理：{stats['pending_tasks']}个")
        report.append(f"进行中：{stats['in_progress_tasks']}个")
        report.append(f"已完成：{stats['completed_tasks']}个")
        report.append("")
        
        report.append("## 成员状态")
        report.append("")
        report.append("| 姓名 | 角色 | 部门 | 待处理 | 已完成 |")
        report.append("|------|------|------|--------|--------|")
        for mid, info in stats["members"].items():
            report.append(f"| {info['name']} | {info['role']} | {info['department']} | {info['pending_tasks']} | {info['completed_tasks']} |")
        report.append("")
        
        report.append("## 待处理任务")
        report.append("")
        for tid, task in self.tasks.items():
            if task.status == "pending":
                member_name = self.members[task.assignee].name if task.assignee in self.members else "Unknown"
                report.append(f"- **{task.title}** ({task.priority}) → {member_name}")
        report.append("")
        
        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="团队管理器")
    parser.add_argument("--config", "-c", default="team/team-config.json", help="配置文件路径")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # init
    init_parser = subparsers.add_parser("init", help="初始化团队")
    init_parser.add_argument("--project", "-p", required=True, help="项目名称")
    
    # assign
    assign_parser = subparsers.add_parser("assign", help="分配任务")
    assign_parser.add_argument("--role", "-r", required=True, help="角色")
    assign_parser.add_argument("--title", "-t", required=True, help="任务标题")
    assign_parser.add_argument("--desc", "-d", default="", help="任务描述")
    assign_parser.add_argument("--priority", "-P", default="medium", choices=["high", "medium", "low"])
    assign_parser.add_argument("--due", "-D", type=int, default=1, help="截止时间（天）")
    
    # complete
    complete_parser = subparsers.add_parser("complete", help="完成任务")
    complete_parser.add_argument("--task-id", "-i", required=True, help="任务ID")
    
    # status
    subparsers.add_parser("status", help="查看状态")
    
    # report
    report_parser = subparsers.add_parser("report", help="生成报告")
    report_parser.add_argument("--output", "-o", help="输出文件")
    
    args = parser.parse_args()
    
    manager = TeamManager(args.config)
    
    if args.command == "init":
        manager.init_team(args.project)
        
    elif args.command == "assign":
        task_id = manager.assign_task(args.role, args.title, args.desc, args.priority, args.due)
        print(f"✅ 任务已分配: {task_id}")
        
    elif args.command == "complete":
        manager.complete_task(args.task_id)
        
    elif args.command == "status":
        stats = manager.get_status()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        
    elif args.command == "report":
        report = manager.generate_report()
        if args.output:
            Path(args.output).write_text(report)
            print(f"✅ 报告已保存: {args.output}")
        else:
            print(report)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
