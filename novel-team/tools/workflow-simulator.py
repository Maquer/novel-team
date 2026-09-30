#!/usr/bin/env python3
"""
workflow-simulator.py — 工作流程模拟器

功能：
  1. 模拟各环节执行
  2. 检测流程瓶颈
  3. 生成优化建议
  4. 输出流程报告
"""

import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class WorkflowStep:
    """流程步骤"""
    step_id: str
    name: str
    actor: str
    tool: str
    action: str
    duration_seconds: float = 0.0
    status: str = "pending"  # pending/running/completed/failed
    errors: List[str] = field(default_factory=list)
    outputs: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "actor": self.actor,
            "tool": self.tool,
            "action": self.action,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "errors": self.errors,
            "outputs": self.outputs,
        }


@dataclass
class WorkflowSimulation:
    """流程模拟"""
    simulation_id: str
    workflow_name: str
    start_time: str
    end_time: str
    steps: List[WorkflowStep] = field(default_factory=list)
    total_duration: float = 0.0
    bottlenecks: List[Dict] = field(default_factory=list)
    issues: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "simulation_id": self.simulation_id,
            "workflow_name": self.workflow_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "steps": [s.to_dict() for s in self.steps],
            "total_duration": self.total_duration,
            "bottlenecks": self.bottlenecks,
            "issues": self.issues,
        }


class WorkflowSimulator:
    """工作流模拟器"""
    
    # 章节创作流程定义
    CHAPTER_CREATION_FLOW = [
        {"step": 1, "name": "大纲设计", "actor": "outline_designer", "tool": "outline-builder", "action": "add-chapter", "duration": 30},
        {"step": 2, "name": "LLM创作", "actor": "lead_writer", "tool": "llm-integrator", "action": "chat", "duration": 120},
        {"step": 3, "name": "剧情分析", "actor": "lead_writer", "tool": "plot-analyzer", "action": "analyze", "duration": 15},
        {"step": 4, "name": "批量处理", "actor": "writer", "tool": "batch-replace", "action": "replace", "duration": 20},
        {"step": 5, "name": "门禁检查", "actor": "editor", "tool": "gate-check", "action": "check", "duration": 25},
        {"step": 6, "name": "去AI味", "actor": "style_optimizer", "tool": "novel-humanizer", "action": "check", "duration": 18},
        {"step": 7, "name": "字数检查", "actor": "analyst", "tool": "wordcount-check", "action": "check", "duration": 5},
        {"step": 8, "name": "事实快照", "actor": "world_builder", "tool": "fact-snapshot", "action": "write", "duration": 10},
        {"step": 9, "name": "合同校验", "actor": "director", "tool": "contract-tree", "action": "check", "duration": 15},
    ]
    
    # 世界构建流程定义
    WORLD_BUILDING_FLOW = [
        {"step": 1, "name": "初始化", "actor": "world_builder", "tool": "world-init", "action": "init", "duration": 20},
        {"step": 2, "name": "添加节点", "actor": "world_builder", "tool": "world-pack", "action": "add-node", "duration": 15},
        {"step": 3, "name": "建立关系", "actor": "world_builder", "tool": "story-graph", "action": "add-node", "duration": 10},
        {"step": 4, "name": "一致性检查", "actor": "world_builder", "tool": "world-pack", "action": "check", "duration": 25},
        {"step": 5, "name": "读取同步", "actor": "outline_designer", "tool": "fact-snapshot", "action": "read", "duration": 8},
    ]
    
    # 质量控制流程定义
    QUALITY_CONTROL_FLOW = [
        {"step": 1, "name": "门禁检查", "actor": "editor", "tool": "gate-check", "action": "check", "duration": 25},
        {"step": 2, "name": "一致性防线", "actor": "editor", "tool": "guard-v6", "action": "check", "duration": 20},
        {"step": 3, "name": "事实核验", "actor": "editor", "tool": "fact-ledger", "action": "list-facts", "duration": 15},
        {"step": 4, "name": "去AI味检测", "actor": "style_optimizer", "tool": "anti-ai-12", "action": "check", "duration": 18},
        {"step": 5, "name": "深度去AI味", "actor": "style_optimizer", "tool": "novel-humanizer", "action": "check", "duration": 20},
        {"step": 6, "name": "指纹蒸馏", "actor": "style_optimizer", "tool": "fusion-engine", "action": "fuse", "duration": 30},
    ]
    
    def __init__(self):
        self.simulations: List[WorkflowSimulation] = []
    
    def simulate(self, workflow_name: str, flow_definition: List[Dict]) -> WorkflowSimulation:
        """模拟工作流程"""
        start_time = datetime.now()
        simulation = WorkflowSimulation(
            simulation_id=f"sim-{int(time.time())}",
            workflow_name=workflow_name,
            start_time=start_time.isoformat(),
            end_time="",
        )
        
        total_duration = 0
        bottlenecks = []
        issues = []
        
        for step_def in flow_definition:
            step = WorkflowStep(
                step_id=f"step-{step_def['step']:02d}",
                name=step_def["name"],
                actor=step_def["actor"],
                tool=step_def["tool"],
                action=step_def["action"],
                duration_seconds=step_def["duration"],
                status="completed",
            )
            
            # 模拟执行（添加随机波动）
            import random
            actual_duration = step.duration_seconds * (0.8 + random.random() * 0.4)
            step.duration_seconds = actual_duration
            total_duration += actual_duration
            
            # 检测瓶颈（超过平均时间50%的）
            expected_duration = next((s["duration"] for s in flow if s["step"] == step_def["step"]), step.duration_seconds)
            if actual_duration > expected_duration * 1.5:
                bottlenecks.append({
                    "step": step.name,
                    "actor": step.actor,
                    "expected": step.definition["duration"],
                    "actual": actual_duration,
                    "delay_percent": (actual_duration - step.definition["duration"]) / step.definition["duration"] * 100,
                })
            
            # 检测问题
            if step.duration_seconds > 60:
                issues.append({
                    "step": step.name,
                    "issue": "执行时间过长",
                    "duration": actual_duration,
                    "suggestion": f"考虑拆分或优化{step.name}环节",
                })
            
            simulation.steps.append(step)
        
        simulation.total_duration = total_duration
        simulation.bottlenecks = bottlenecks
        simulation.issues = issues
        simulation.end_time = datetime.now().isoformat()
        
        self.simulations.append(simulation)
        return simulation
    
    def analyze_bottlenecks(self, simulation: WorkflowSimulation) -> Dict:
        """分析瓶颈"""
        if not simulation.steps:
            return {}
        
        durations = [s.duration_seconds for s in simulation.steps]
        avg_duration = sum(durations) / len(durations)
        max_duration = max(durations)
        min_duration = min(durations)
        
        bottleneck_steps = [
            s for s in simulation.steps
            if s.duration_seconds > avg_duration * 1.3
        ]
        
        return {
            "total_duration": simulation.total_duration,
            "avg_step_duration": avg_duration,
            "max_step_duration": max_duration,
            "min_step_duration": min_duration,
            "bottleneck_count": len(bottleneck_steps),
            "bottleneck_steps": [
                {"name": s.name, "duration": s.duration_seconds, "actor": s.actor}
                for s in bottleneck_steps
            ],
            "efficiency": len(simulation.steps) / simulation.total_duration * 60 if simulation.total_duration > 0 else 0,
        }
    
    def generate_recommendations(self, simulation: WorkflowSimulation) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 基于瓶颈分析
        bottlenecks = self.analyze_bottlenecks(simulation)
        
        if bottlenecks["bottleneck_count"] > 0:
            recommendations.append(
                f"发现{bottlenecks['bottleneck_count']}个瓶颈环节，建议优先优化"
            )
            for step in bottlenecks["bottleneck_steps"][:3]:
                recommendations.append(
                    f"  - {step['name']}（{step['actor']}）: {step['duration']:.1f}秒，考虑并行处理或拆分"
                )
        
        # 基于整体效率
        if bottlenecks["efficiency"] < 0.1:
            recommendations.append(
                "整体流程效率偏低，建议审查各环节依赖关系"
            )
        
        # 基于问题列表
        for issue in simulation.issues:
            recommendations.append(f"  - {issue['suggestion']}")
        
        # 通用建议
        recommendations.extend([
            "建议引入缓存机制，减少重复计算",
            "建议建立环节间自动触发机制，减少人工等待",
            "建议增加实时监控，及时发现异常",
        ])
        
        return recommendations
    
    def generate_report(self, simulation: WorkflowSimulation) -> str:
        """生成报告"""
        lines = []
        
        lines.append(f"# 工作流程模拟报告")
        lines.append("")
        lines.append(f"> 模拟ID：{simulation.simulation_id}")
        lines.append(f"> 流程名称：{simulation.workflow_name}")
        lines.append(f"> 开始时间：{simulation.start_time}")
        lines.append(f"> 结束时间：{simulation.end_time}")
        lines.append("")
        
        # 总体统计
        lines.append("## 一、总体统计")
        lines.append("")
        bottlenecks = self.analyze_bottlenecks(simulation)
        lines.append(f"- 总耗时：{bottlenecks['total_duration']:.1f}秒")
        lines.append(f"- 步骤数：{len(simulation.steps)}")
        lines.append(f"- 平均步骤耗时：{bottlenecks['avg_step_duration']:.1f}秒")
        lines.append(f"- 瓶颈数：{bottlenecks['bottleneck_count']}")
        lines.append(f"- 效率：{bottlenecks['efficiency']:.2f}步/分钟")
        lines.append("")
        
        # 步骤详情
        lines.append("## 二、步骤详情")
        lines.append("")
        lines.append("| 序号 | 步骤 | 负责人 | 工具 | 耗时(秒) | 状态 |")
        lines.append("|------|------|--------|------|---------|------|")
        for step in simulation.steps:
            status_icon = "✅" if step.status == "completed" else "❌"
            lines.append(f"| {step.step_id} | {step.name} | {step.actor} | {step.tool} | {step.duration_seconds:.1f} | {status_icon} |")
        lines.append("")
        
        # 瓶颈分析
        if bottlenecks["bottleneck_steps"]:
            lines.append("## 三、瓶颈分析")
            lines.append("")
            for i, bn in enumerate(bottlenecks["bottleneck_steps"], 1):
                lines.append(f"{i}. **{bn['name']}**（{bn['actor']}）: {bn['duration']:.1f}秒")
            lines.append("")
        
        # 问题列表
        if simulation.issues:
            lines.append("## 四、问题列表")
            lines.append("")
            for issue in simulation.issues:
                lines.append(f"- {issue['issue']}: {issue['suggestion']}")
            lines.append("")
        
        # 优化建议
        lines.append("## 五、优化建议")
        lines.append("")
        recommendations = self.generate_recommendations(simulation)
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="工作流程模拟器")
    parser.add_argument("--workflow", "-w", choices=["chapter", "world", "quality"], required=True, help="工作流类型")
    parser.add_argument("--report", "-r", help="报告输出文件")
    
    args = parser.parse_args()
    
    simulator = WorkflowSimulator()
    
    # 选择流程
    if args.workflow == "chapter":
        flow = WorkflowSimulator.CHAPTER_CREATION_FLOW
        workflow_name = "章节创作流程"
    elif args.workflow == "world":
        flow = WorkflowSimulator.WORLD_BUILDING_FLOW
        workflow_name = "世界构建流程"
    elif args.workflow == "quality":
        flow = WorkflowSimulator.QUALITY_CONTROL_FLOW
        workflow_name = "质量控制流程"
    else:
        print("❌ 未知的工作流类型")
        sys.exit(1)
    
    # 执行模拟
    print(f"🔄 开始模拟: {workflow_name}")
    simulation = simulator.simulate(workflow_name, flow)
    print(f"✅ 模拟完成，总耗时: {simulation.total_duration:.1f}秒")
    print()
    
    # 生成报告
    report = simulator.generate_report(simulation)
    
    if args.report:
        Path(args.report).write_text(report)
        print(f"📄 报告已保存: {args.report}")
    else:
        print(report)


if __name__ == "__main__":
    main()
