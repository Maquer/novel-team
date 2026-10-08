#!/usr/bin/env python3
"""
plot-pipeline.py — 剧情流水线引擎（借鉴 AbilityKit Pipeline 模块）

核心设计：
  Phase 图模型，支持 Sequence / Parallel / Conditional / Repeat / Delay / WaitUntil
  每个 Phase 有明确生命周期：Execute() → OnUpdate(dt) → IsComplete() → Reset()
  复合阶段可嵌套，支持中断与恢复

小说适配：
  Phase = 剧情段落：开场(Hook)→发展(Rise)→冲突(Conflict)→高潮(Climax)→收尾(Resolution)
  多线并行：ParallelPhase 支持多角色视角交替推进
  条件分支：ConditionalPhase 根据剧情状态分叉

使用：
  python plot-pipeline.py build --project my-novel --phases sequence,hook,rise,climax,resolution
  python plot-pipeline.py run --project my-novel --start hook
  python plot-pipeline.py status --project my-novel
  python plot-pipeline.py complete --project my-novel --phase climax
"""

import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ==================== Phase 类型定义 ====================

class PhaseStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    SKIPPED = "skipped"


class PhaseType(Enum):
    # 基础阶段
    SEQUENCE = "sequence"       # 顺序执行子阶段
    PARALLEL = "parallel"       # 并行执行子阶段
    CONDITIONAL = "conditional" # 条件分支
    REPEAT = "repeat"           # 重复执行
    DELAY = "delay"             # 延迟等待
    WAIT_UNTIL = "wait_until"   # 等待条件满足
    
    # 业务阶段（小说专用）
    HOOK = "hook"               # 开篇钩子
    RISE = "rise"               # 发展推进
    CONFLICT = "conflict"       # 冲突升级
    CLIMAX = "climax"           # 高潮爆发
    RESOLUTION = "resolution"   # 收尾收束
    TRANSITION = "transition"   # 场景过渡
    
    # 特殊
    BRANCH = "branch"           # 剧情分叉（多结局）
    TIMELINE = "timeline"       # 时间轴事件


# ==================== Phase 数据模型 ====================

@dataclass
class PhaseDef:
    """单个 Phase 的定义"""
    id: str
    name: str
    ptype: PhaseType
    params: Dict[str, Any] = field(default_factory=dict)
    children: List['PhaseDef'] = field(default_factory=list)  # 子阶段（复合Phase用）
    condition: Optional[str] = None  # 条件表达式（字符串，ConditionalPhase用）
    repeat_count: int = 1  # 重复次数（RepeatPhase用）
    delay_seconds: float = 0  # 延迟秒数（DelayPhase用）
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "ptype": self.ptype.value,
            "params": self.params,
            "children": [c.to_dict() for c in self.children],
            "condition": self.condition,
            "repeat_count": self.repeat_count,
            "delay_seconds": self.delay_seconds,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PhaseDef':
        children = [cls.from_dict(c) for c in data.get("children", [])]
        return cls(
            id=data["id"],
            name=data["name"],
            ptype=PhaseType(data["ptype"]),
            params=data.get("params", {}),
            children=children,
            condition=data.get("condition"),
            repeat_count=data.get("repeat_count", 1),
            delay_seconds=data.get("delay_seconds", 0),
        )


@dataclass
class PhaseInstance:
    """运行时 Phase 实例"""
    def_id: str
    status: PhaseStatus = PhaseStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    child_instances: Dict[str, 'PhaseInstance'] = field(default_factory=dict)
    repeat_index: int = 0
    exec_history: List[Dict] = field(default_factory=list)  # 每次执行的记录


# ==================== Pipeline 引擎 ====================

class PlotPipeline:
    """剧情流水线引擎"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.storage_path = Path(f"/var/minis/shared/novel-team/.pipeline/{project_id}.json")
        self.phases: Dict[str, PhaseDef] = {}
        self.instances: Dict[str, PhaseInstance] = {}
        self.context: Dict[str, Any] = {}  # 共享上下文
        self._load()
    
    def _load(self):
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            self.phases = {k: PhaseDef.from_dict(v) for k, v in data.get("phases", {}).items()}
            # 修复：从JSON加载时status是字符串，需要转换回enum
            instances_data = data.get("instances", {})
            self.instances = {}
            for k, v in instances_data.items():
                v["status"] = PhaseStatus(v["status"])
                self.instances[k] = PhaseInstance(**v)
            self.context = data.get("context", {})
    
    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "instances": {k: {"def_id": v.def_id, "status": v.status.value,
                               "started_at": v.started_at, "completed_at": v.completed_at,
                               "error": v.error, "result": str(v.result)[:200] if v.result else None,
                               "repeat_index": v.repeat_index,
                               "exec_history": v.exec_history,
                               "child_instances": {kc: {"def_id": vc.def_id, "status": vc.status.value,
                                                         "started_at": vc.started_at,
                                                         "completed_at": vc.completed_at}
                                                    for kc, vc in v.child_instances.items()}
                              } for k, v in self.instances.items()},
            "context": self.context,
            "updated_at": datetime.now().isoformat(),
        }
        tmp = self.storage_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.storage_path)
    
    def add_phase(self, phase: PhaseDef) -> str:
        """添加 Phase 到流水线"""
        self.phases[phase.id] = phase
        self.instances[phase.id] = PhaseInstance(def_id=phase.id)
        self._save()
        return phase.id
    
    def add_sequence(self, phases: List[PhaseDef]) -> str:
        """添加顺序执行序列"""
        seq_id = f"seq_{int(time.time())}"
        seq = PhaseDef(id=seq_id, name=f"顺序流程{len(self.phases)+1}", ptype=PhaseType.SEQUENCE, children=phases)
        return self.add_phase(seq)
    
    def add_parallel(self, phases: List[PhaseDef]) -> str:
        """添加并行执行（多线叙事）"""
        par_id = f"par_{int(time.time())}"
        par = PhaseDef(id=par_id, name=f"并行流程{len(self.phases)+1}", ptype=PhaseType.PARALLEL, children=phases)
        return self.add_phase(par)
    
    def add_conditional(self, condition: str, true_phase: PhaseDef, false_phase: Optional[PhaseDef] = None) -> str:
        """添加条件分支"""
        cond_id = f"cond_{int(time.time())}"
        children = [true_phase]
        if false_phase:
            children.append(false_phase)
        cond = PhaseDef(id=cond_id, name=f"条件分支{len(self.phases)+1}", ptype=PhaseType.CONDITIONAL, 
                       condition=condition, children=children)
        return self.add_phase(cond)
    
    def execute_phase(self, phase_id: str, context: Optional[Dict] = None) -> Dict:
        """执行单个 Phase，返回执行结果"""
        phase = self.phases.get(phase_id)
        if not phase:
            return {"status": "error", "error": f"Phase {phase_id} 不存在"}
        
        inst = self.instances.get(phase_id) or PhaseInstance(def_id=phase_id)
        inst.status = PhaseStatus.RUNNING
        inst.started_at = datetime.now().isoformat()
        
        ctx = {**self.context, **(context or {})}
        result = {"status": "ok", "phase_id": phase_id, "result": None, "next": []}
        
        try:
            if phase.ptype == PhaseType.HOOK:
                inst.result = self._exec_hook(phase, ctx)
            elif phase.ptype == PhaseType.RISE:
                inst.result = self._exec_rise(phase, ctx)
            elif phase.ptype == PhaseType.CONFLICT:
                inst.result = self._exec_conflict(phase, ctx)
            elif phase.ptype == PhaseType.CLIMAX:
                inst.result = self._exec_climax(phase, ctx)
            elif phase.ptype == PhaseType.RESOLUTION:
                inst.result = self._exec_resolution(phase, ctx)
            elif phase.ptype == PhaseType.TRANSITION:
                inst.result = self._exec_transition(phase, ctx)
            elif phase.ptype == PhaseType.SEQUENCE:
                inst.result = self._exec_sequence(phase, ctx)
            elif phase.ptype == PhaseType.PARALLEL:
                inst.result = self._exec_parallel(phase, ctx)
            elif phase.ptype == PhaseType.CONDITIONAL:
                inst.result = self._exec_conditional(phase, ctx)
            else:
                inst.result = {"note": f"PhaseType={phase.ptype.value} 未实现"}
        except Exception as e:
            inst.status = PhaseStatus.INTERRUPTED
            inst.error = str(e)
            result = {"status": "error", "error": str(e)}
        
        inst.status = PhaseStatus.COMPLETED
        inst.completed_at = datetime.now().isoformat()
        inst.exec_history.append({
            "started_at": inst.started_at,
            "completed_at": inst.completed_at,
            "result": str(inst.result)[:200] if inst.result else None,
        })
        
        self.instances[phase_id] = inst
        self._save()
        return result
    
    # ---- 业务 Phase 执行器 ----
    
    def _exec_hook(self, phase: PhaseDef, ctx: Dict) -> Dict:
        """开篇钩子：建立悬念、引入主角、点明冲突"""
        return {
            "type": "hook",
            "suggested_elements": ["主角出场", "日常打破", "悬念设置"],
            "goal": "让读者产生'接下来会发生什么'的好奇心",
            "executed": True,
        }
    
    def _exec_rise(self, phase: PhaseDef, ctx: Dict) -> Dict:
        """发展推进：铺垫、积累、升级"""
        return {
            "type": "rise",
            "suggested_elements": ["信息释放", "关系发展", "小冲突"],
            "goal": "逐步累积张力，为高潮做准备",
            "executed": True,
        }
    
    def _exec_conflict(self, phase: PhaseDef, ctx: Dict) -> Dict:
        """冲突升级：对抗加剧"""
        return {
            "type": "conflict",
            "suggested_elements": ["对抗升级", "代价显现", "选择困境"],
            "goal": "把冲突推到临界点",
            "executed": True,
        }
    
    def _exec_climax(self, phase: PhaseDef, ctx: Dict) -> Dict:
        """高潮爆发：最大张力释放"""
        return {
            "type": "climax",
            "suggested_elements": ["决战", "真相揭示", "命运转折"],
            "goal": "情绪最高点，释放前面累积的所有张力",
            "executed": True,
        }
    
    def _exec_resolution(self, phase: PhaseDef, ctx: Dict) -> Dict:
        """收尾收束：交代后果，留余韵"""
        return {
            "type": "resolution",
            "suggested_elements": ["结果交代", "情感沉淀", "新悬念（可选）"],
            "goal": "给当前段落闭环，可留钩子引向下一段",
            "executed": True,
        }
    
    def _exec_transition(self, phase: PhaseDef, ctx: Dict) -> Dict:
        """场景过渡"""
        return {
            "type": "transition",
            "suggested_elements": ["时间流逝", "空间转换", "状态变化"],
            "goal": "平滑过渡到下一场景",
            "executed": True,
        }
    
    # ---- 复合 Phase 执行器 ----
    
    def _exec_sequence(self, phase: PhaseDef, ctx: Dict) -> Dict:
        """顺序执行所有子 Phase"""
        results = []
        for child in phase.children:
            r = self.execute_phase(child.id, ctx)
            results.append(r)
            if r.get("status") == "error":
                return {"status": "error", "error": r.get("error"), "partial_results": results}
        return {"status": "ok", "results": results}
    
    def _exec_parallel(self, phase: PhaseDef, ctx: Dict) -> Dict:
        """并行执行子 Phase（多线叙事）"""
        results = {}
        for child in phase.children:
            results[child.id] = self.execute_phase(child.id, ctx)
        return {"status": "ok", "results": results}
    
    def _exec_conditional(self, phase: PhaseDef, ctx: Dict) -> Dict:
        """条件分支执行"""
        if len(phase.children) < 1:
            return {"status": "error", "error": "ConditionalPhase 至少需要1个子Phase"}
        
        # 简化版条件评估：检查 context 中是否有指定 key
        cond = phase.condition or ""
        taken_branch = 0  # 默认走第一个分支
        
        if cond in ctx:
            taken_branch = 1 if ctx[cond] else 0
        
        if taken_branch >= len(phase.children):
            taken_branch = 0
        
        branch = phase.children[taken_branch]
        return self.execute_phase(branch.id, ctx)
    
    def get_status(self, phase_id: Optional[str] = None) -> Dict:
        """获取流水线状态"""
        if phase_id:
            inst = self.instances.get(phase_id)
            phase = self.phases.get(phase_id)
            if not inst or not phase:
                return {"error": "Phase 不存在"}
            return {
                "id": phase_id,
                "name": phase.name,
                "type": phase.ptype.value,
                "status": inst.status.value,
                "started_at": inst.started_at,
                "completed_at": inst.completed_at,
                "error": inst.error,
                "exec_history_count": len(inst.exec_history),
            }
        
        # 全量状态
        return {
            "project_id": self.project_id,
            "total_phases": len(self.phases),
            "phases": {pid: {
                "name": p.name,
                "type": p.ptype.value,
                "status": self.instances.get(pid, PhaseInstance(def_id=pid)).status.value,
            } for pid, p in self.phases.items()},
            "context_keys": list(self.context.keys()),
        }
    
    def mark_skipped(self, phase_id: str, reason: str = ""):
        """标记 Phase 为跳过"""
        inst = self.instances.get(phase_id)
        if inst:
            inst.status = PhaseStatus.SKIPPED
            inst.error = reason
            self._save()


# ==================== CLI ====================

def cmd_build(args):
    """构建流水线"""
    pipe = PlotPipeline(args.project)
    default_phases = {
        "hook": PhaseDef(id="hook", name="开篇钩子", ptype=PhaseType.HOOK),
        "rise": PhaseDef(id="rise", name="发展推进", ptype=PhaseType.RISE),
        "conflict": PhaseDef(id="conflict", name="冲突升级", ptype=PhaseType.CONFLICT),
        "climax": PhaseDef(id="climax", name="高潮爆发", ptype=PhaseType.CLIMAX),
        "resolution": PhaseDef(id="resolution", name="收尾收束", ptype=PhaseType.RESOLUTION),
    }
    
    phases_to_add = args.phases.split(",") if args.phases else ["hook", "rise", "conflict", "climax", "resolution"]
    
    for pid in phases_to_add:
        pid = pid.strip()
        if pid in default_phases:
            pipe.add_phase(default_phases[pid])
        else:
            # 自定义 Phase
            phase = PhaseDef(id=pid, name=pid, ptype=PhaseType(args.ptype or "hook"))
            pipe.add_phase(phase)
    
    status = pipe.get_status()
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


def cmd_run(args):
    """执行 Phase"""
    pipe = PlotPipeline(args.project)
    ctx = None
    if args.context_json:
        import json as _json
        try:
            ctx = _json.loads(args.context_json)
        except Exception as e:
            print(json.dumps({"status": "error", "error": f"JSON解析失败: {e}"}))
            return 1
    result = pipe.execute_phase(args.phase, ctx)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_status(args):
    """查看状态"""
    pipe = PlotPipeline(args.project)
    status = pipe.get_status(args.phase)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


def cmd_complete(args):
    """标记 Phase 完成"""
    pipe = PlotPipeline(args.project)
    result = pipe.execute_phase(args.phase)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_skips(args):
    """标记 Phase 跳过"""
    pipe = PlotPipeline(args.project)
    pipe.mark_skipped(args.phase, args.reason)
    print(f"✅ Phase {args.phase} 已标记为跳过: {args.reason}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="剧情流水线引擎（借鉴AbilityKit Pipeline）")
    sub = parser.add_subparsers(dest="command")
    
    p_build = sub.add_parser("build", help="构建流水线")
    p_build.add_argument("--project", "-p", required=True, help="项目ID")
    p_build.add_argument("--phases", "-f", help="Phase列表（逗号分隔，默认全5个）")
    p_build.add_argument("--ptype", default="hook", help="自定义Phase类型")
    
    p_run = sub.add_parser("run", help="执行单个Phase")
    p_run.add_argument("--project", "-p", required=True, help="项目ID")
    p_run.add_argument("--phase", required=True, help="Phase ID")
    p_run.add_argument("--context-json", help="上下文JSON字符串")
    
    p_status = sub.add_parser("status", help="查看状态")
    p_status.add_argument("--project", "-p", required=True, help="项目ID")
    p_status.add_argument("--phase", help="指定Phase（不指定则显示全部）")
    
    p_complete = sub.add_parser("complete", help="标记Phase完成并执行")
    p_complete.add_argument("--project", "-p", required=True, help="项目ID")
    p_complete.add_argument("--phase", required=True)
    
    p_skip = sub.add_parser("skip", help="跳过Phase")
    p_skip.add_argument("--project", "-p", required=True, help="项目ID")
    p_skip.add_argument("--phase", required=True)
    p_skip.add_argument("--reason", default="用户选择跳过")
    
    args = parser.parse_args()
    
    cmd_map = {"build": cmd_build, "run": cmd_run, "status": cmd_status,
               "complete": cmd_complete, "skip": cmd_skips}
    fn = cmd_map.get(args.command)
    if fn:
        sys.exit(fn(args))
    else:
        parser.print_help()
        sys.exit(1)
