#!/usr/bin/env python3
"""
decide-trigger.py — 决策触发判定（借鉴 ai-novel-writer v6）

核心功能：
  从事件流里识别值得停下来问人的岔路
  
四种触发类型：
  moral         → 道德两难
  cost          → 重大代价
  irreversible  → 不可逆行动
  user_focus    → 用户关注的焦点

使用：
  python decide-trigger.py --events events.json --focus "林默"
  python decide-trigger.py --input events.json --output decisions.json
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


# 触发词定义
_IRREVERSIBLE_WORDS = ("毁掉", "杀死", "永久", "不可逆", "彻底", "出卖", "背叛",
                       "销毁", "泄漏", "暴露", "断交", "辞职", "处决", "死亡", "牺牲")
_COST_WORDS = ("代价", "失去", "牺牲", "放弃", "交换", "以……换", "赌上",
               "付出", "透支", "抵押", "亏损", "破产", "败家")
_MORAL_WORDS = ("道德", "良心", "对错", "善恶", "正义", "背叛", "信任", "欺骗",
                "选择", "两难", "困难", "痛苦", "挣扎")


@dataclass
class DecisionPoint:
    """决策点"""
    id: str
    trigger_type: str
    trigger_label: str
    actor_name: str
    title: str
    situation: str
    stakes: str
    importance: int
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "trigger_type": self.trigger_type,
            "trigger_label": self.trigger_label,
            "actor_name": self.actor_name,
            "title": self.title,
            "situation": self.situation,
            "stakes": self.stakes,
            "importance": self.importance,
        }


class DecisionTrigger:
    """决策触发判定"""
    
    def __init__(self):
        self.decisions: List[DecisionPoint] = []
        self.decision_counter = 0
    
    def trigger_from_events(self, events: List[Dict], 
                           user_focus: List[str] = None) -> List[DecisionPoint]:
        """
        从事件流里识别值得停下来问人的岔路
        
        规则：只有当事件同时具备"高重要度"和"不可逆性"信号时才触发
        """
        self.decisions = []
        user_focus = user_focus or []
        
        for ev in events:
            # 提取重要性
            try:
                importance = int(float(str(ev.get("importance") or 3).strip()))
            except (TypeError, ValueError):
                importance = 3
            
            # 低重要度不打扰用户（除非是用户关注点）
            if importance < 4:
                text = f"{ev.get('intent', '')} {ev.get('result', '')}"
                if not any(f in text for f in user_focus):
                    continue
            
            # 判定触发类型
            trigger = self._detect_trigger(ev, user_focus)
            
            if trigger:
                self.decision_counter += 1
                decision = DecisionPoint(
                    id=f"D{self.decision_counter:04d}",
                    trigger_type=trigger,
                    trigger_label=self._get_trigger_label(trigger),
                    actor_name=ev.get("actor") or "",
                    title=ev.get("title") or "需要决断",
                    situation=ev.get("description") or "",
                    stakes=ev.get("result") or "",
                    importance=importance,
                )
                self.decisions.append(decision)
        
        return self.decisions
    
    def _detect_trigger(self, event: Dict, user_focus: List[str]) -> Optional[str]:
        """检测触发类型"""
        text = f"{event.get('intent', '')} {event.get('result', '')} {event.get('description', '')}"
        etype = event.get("event_type", "")
        
        # 用户关注点优先
        if user_focus:
            for focus in user_focus:
                if focus in text:
                    return "user_focus"
        
        # 不可逆行动
        if etype == "decision" or self._has_irreversible(text):
            return "irreversible"
        
        # 重大代价
        if self._has_cost(text):
            return "cost"
        
        # 道德两难（最后检测，因为多数决策都有道德元素）
        if self._has_moral(text):
            return "moral"
        
        return None
    
    def _has_irreversible(self, text: str) -> bool:
        return any(w in text for w in _IRREVERSIBLE_WORDS)
    
    def _has_cost(self, text: str) -> bool:
        return any(w in text for w in _COST_WORDS)
    
    def _has_moral(self, text: str) -> bool:
        return any(w in text for w in _MORAL_WORDS)
    
    def _get_trigger_label(self, trigger_type: str) -> str:
        labels = {
            "moral": "道德两难",
            "cost": "重大代价",
            "irreversible": "不可逆行动",
            "user_focus": "你关注的焦点",
        }
        return labels.get(trigger_type, trigger_type)
    
    def print_report(self):
        """打印触发报告"""
        print("\n" + "=" * 60)
        print("🎯 决策触发判定报告")
        print("=" * 60)
        print(f"发现 {len(self.decisions)} 个需要用户决策的点\n")
        
        for d in self.decisions:
            print(f"【{d.trigger_label}】{d.title}")
            print(f"  角色: {d.actor_name or '世界'}")
            print(f"  局势: {d.situation[:80]}...")
            print(f"  代价: {d.stakes[:80]}...")
            print(f"  重要度: {'⭐' * d.importance}")
            print()
        
        print("=" * 60)


def cmd_trigger(args):
    """执行触发判定"""
    trigger = DecisionTrigger()
    
    # 加载事件
    try:
        with open(args.events, 'r', encoding='utf-8') as f:
            events = json.load(f)
    except Exception as e:
        print(f"❌ 加载事件文件失败: {e}")
        return 1
    
    # 解析用户关注点
    user_focus = []
    if args.focus:
        user_focus = [f.strip() for f in args.focus.split(',')]
    
    # 执行判定
    print(f"🔍 正在分析 {len(events)} 条事件...")
    decisions = trigger.trigger_from_events(events, user_focus)
    
    # 打印报告
    trigger.print_report()
    
    # 保存结果
    if args.output:
        result = {
            "decision_count": len(decisions),
            "decisions": [d.to_dict() for d in decisions],
        }
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"\n📄 结果已保存到: {args.output}")
    
    return 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="决策触发判定（借鉴ai-novel-writer v6）")
    parser.add_argument("--events", "-e", required=True, help="事件JSON文件")
    parser.add_argument("--focus", "-f", help="用户关注点（逗号分隔）")
    parser.add_argument("--output", "-o", help="输出文件")
    
    args = parser.parse_args()
    sys.exit(cmd_trigger(args))
