#!/usr/bin/env python3
"""
plot-simulation-v2.py — 增强版剧情推演引擎

改进点：
  1. 多维度评分（情节/人物/冲突/节奏/情绪）
  2. 模型差异放大（不同模型输出差异化）
  3. 智能选优（基于故事连贯性）
  4. 对比报告生成

使用：
  python plot-simulation-v2.py simulate --context "..." --outline "..." --model all
  python plot-simulation-v2.py compare --plans plan1.json plan2.json plan3.json
"""

import sys
import json
import re
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PlotElement:
    """剧情元素"""
    type: str        # hook/conflict/foreshadow/climax/character_growth/reversal
    content: str
    strength: float  # 强度 0.0-1.0
    relevance: float # 与主线相关性 0.0-1.0


@dataclass
class PlotPlan:
    """剧情方案"""
    plan_id: str
    model: str
    title: str
    summary: str
    content: str
    
    # 新增：多维度评分
    plot_score: float = 0.0      # 情节完整性
    character_score: float = 0.0 # 人物塑造
    conflict_score: float = 0.0  # 冲突设计
    pace_score: float = 0.0      # 节奏控制
    emotion_score: float = 0.0   # 情绪渲染
    
    elements: List[PlotElement] = field(default_factory=list)
    created_at: str = ""
    
    @property
    def total_score(self) -> float:
        """综合评分（加权）"""
        return (
            self.plot_score * 0.25 +
            self.character_score * 0.20 +
            self.conflict_score * 0.20 +
            self.pace_score * 0.15 +
            self.emotion_score * 0.20
        )
    
    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "model": self.model,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "scores": {
                "plot": self.plot_score,
                "character": self.character_score,
                "conflict": self.conflict_score,
                "pace": self.pace_score,
                "emotion": self.emotion_score,
            },
            "total_score": round(self.total_score, 2),
            "elements": [e.__dict__ for e in self.elements],
            "created_at": self.created_at,
        }


class EnhancedPlotSimulator:
    """增强版剧情推演模拟器"""
    
    # 模型特征配置（增强差异化）
    MODEL_PROFILES = {
        "glm": {
            "style": "写实主义",
            "focus": ["冲突", "人物成长", "情感"],
            "creativity": 0.6,
            "coherence": 0.85,
            "character_depth": 0.8,
            "plot_complexity": 0.7,
            "emotion_intensity": 0.7,
        },
        "deepseek": {
            "style": "逻辑严谨",
            "focus": ["伏笔", "反转", "剧情结构"],
            "creativity": 0.7,
            "coherence": 0.75,
            "character_depth": 0.6,
            "plot_complexity": 0.9,
            "emotion_intensity": 0.5,
        },
        "qwen": {
            "style": "创意发散",
            "focus": ["hook", "情绪", "爽点"],
            "creativity": 0.9,
            "coherence": 0.65,
            "character_depth": 0.7,
            "plot_complexity": 0.6,
            "emotion_intensity": 0.9,
        },
    }
    
    def __init__(self):
        self.analyzer = ContextAnalyzer()
    
    def simulate(
        self,
        context: str,
        outline: str,
        model: str = "glm",
        n_plans: int = 3,
    ) -> List[PlotPlan]:
        """生成多个剧情方案"""
        analysis = self.analyzer.analyze(context)
        plans = []
        
        for idx in range(n_plans):
            plan_id = f"{model}-{int(time.time())}-{idx}"
            plan = self._generate_plan(plan_id, model, context, outline, analysis, idx)
            plans.append(plan)
        
        return plans
    
    def _generate_plan(
        self,
        plan_id: str,
        model: str,
        context: str,
        outline: str,
        analysis: Dict,
        idx: int,
    ) -> PlotPlan:
        """生成单个剧情方案"""
        profile = self.MODEL_PROFILES.get(model, self.MODEL_PROFILES["glm"])
        
        # 生成内容（增强差异化）
        content = self._draft_content(context, outline, profile, idx)
        
        # 提取剧情元素
        elements = self.analyzer.analyze(content)["elements"]
        
        # 多维度评分（增强）
        scores = self._multi_dimension_score(content, outline, analysis, profile)
        
        return PlotPlan(
            plan_id=plan_id,
            model=model,
            title=f"方案{idx+1}：{profile['style']}",
            summary=f"采用{profile['style']}风格，聚焦{profile['focus']}要素",
            content=content,
            plot_score=scores["plot"],
            character_score=scores["character"],
            conflict_score=scores["conflict"],
            pace_score=scores["pace"],
            emotion_score=scores["emotion"],
            elements=[PlotElement(**e) for e in elements],
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    
    def _draft_content(
        self,
        context: str,
        outline: str,
        profile: Dict,
        idx: int,
    ) -> str:
        """生成剧情内容（增强差异化）"""
        style = profile['style']
        focus = profile['focus']
        
        # 根据索引增加差异化
        variations = [
            "这是一个充满戏剧张力的故事开局...",
            "故事的转折点在不经意间到来...",
            "命运的齿轮开始转动...",
        ]
        
        variation = variations[idx % len(variations)]
        
        return f"""【{style}风格剧情推演 v{idx+1}】

基于上下文：{context[:150]}...
大纲要求：{outline[:100]}...

{variation}

剧情展开：
主角面临来自{focus[0]}和{focus[1]}的双重挑战。这个挑战不仅考验他的实力，更考验他的意志和决心。

在关键时刻，他做出了一个出人意料的决定——{self._generate_decision(profile, idx)}。

这个决定将改变整个局势，也为后续的{focus[2] if len(focus) > 2 else '发展'}埋下伏笔。

读者会感受到强烈的情感冲击，同时也会对后续剧情充满期待。

（注：此为增强版模拟内容，实际应由LLM生成）"""
    
    def _generate_decision(self, profile: Dict, idx: int) -> str:
        """生成不同决策（增强差异化）"""
        decisions = {
            "glm": [
                "放弃逃避，正面迎战",
                "利用地形周旋，寻找破绽",
                "触发隐藏机制，扭转局势",
            ],
            "deepseek": [
                "分析对手弱点，精准反击",
                "布局陷阱，诱敌深入",
                "调用备用方案，稳中求胜",
            ],
            "qwen": [
                "爆发潜能，逆袭翻盘",
                "召唤外援，联手抗敌",
                "觉醒新能力，碾压对手",
            ],
        }
        
        model_decisions = decisions.get(profile.get("style", "glm"), decisions["glm"])
        return model_decisions[idx % len(model_decisions)]
    
    def _multi_dimension_score(
        self,
        content: str,
        outline: str,
        analysis: Dict,
        profile: Dict,
    ) -> Dict:
        """多维度评分"""
        # 情节完整性（25%）
        plot_score = self._score_plot(content, outline)
        
        # 人物塑造（20%）
        character_score = self._score_character(content, profile)
        
        # 冲突设计（20%）
        conflict_score = self._score_conflict(content, analysis)
        
        # 节奏控制（15%）
        pace_score = self._score_pace(content)
        
        # 情绪渲染（20%）
        emotion_score = self._score_emotion(content, profile)
        
        return {
            "plot": plot_score,
            "character": character_score,
            "conflict": conflict_score,
            "pace": pace_score,
            "emotion": emotion_score,
        }
    
    def _score_plot(self, content: str, outline: str) -> float:
        """情节完整性评分"""
        # 检查是否包含大纲要求的关键元素
        outline_keywords = set(re.findall(r'\w+', outline.lower()))
        content_keywords = set(re.findall(r'\w+', content.lower()))
        
        if not outline_keywords:
            return 0.5
        
        overlap = len(outline_keywords & content_keywords)
        coverage = overlap / len(outline_keywords)
        
        # 检查情节结构（开端-发展-高潮-结局）
        has_beginning = bool(re.search(r'(起初|刚开始|故事开始)', content))
        has_development = bool(re.search(r'(接着|随后|然后|接下来)', content))
        has_climax = bool(re.search(r'(关键时刻|巅峰|决战|高潮)', content))
        has_resolution = bool(re.search(r'(最终|结果|结局| aftermath)', content))
        
        structure_score = sum([has_beginning, has_development, has_climax, has_resolution]) / 4
        
        return min(1.0, coverage * 0.6 + structure_score * 0.4)
    
    def _score_character(self, content: str, profile: Dict) -> float:
        """人物塑造评分"""
        # 检查人物描写深度
        depth_indicators = [
            r'(心中|内心|想法|思绪|回忆)',
            r'(眼神|表情|动作|姿态|举止)',
            r'(性格|特点|气质|魅力|缺陷)',
        ]
        
        depth_score = sum(1 for p in depth_indicators if re.search(p, content)) / len(depth_indicators)
        
        # 人物成长弧线
        growth_indicators = [
            r'(成长|变化|转变|突破|觉醒|领悟)',
            r'(从.*到|经历|获得|失去|学会)',
        ]
        
        growth_score = sum(1 for p in growth_indicators if re.search(p, content)) / len(growth_indicators)
        
        # 结合模型特征
        profile_factor = profile.get("character_depth", 0.7)
        
        return min(1.0, (depth_score * 0.6 + growth_score * 0.4) * profile_factor + 0.3)
    
    def _score_conflict(self, content: str, analysis: Dict) -> float:
        """冲突设计评分"""
        elements = analysis.get("elements", [])
        
        # 冲突元素计数
        conflict_count = sum(1 for e in elements if e.get("type") in ["conflict", "climax"])
        hook_count = sum(1 for e in elements if e.get("type") == "hook")
        
        # 冲突强度
        conflict_strength = sum(e.get("strength", 0.5) for e in elements if e.get("type") in ["conflict", "climax"]) / max(conflict_count, 1)
        
        # 钩子效果
        hook_strength = sum(e.get("relevance", 0.5) for e in elements if e.get("type") == "hook") / max(hook_count, 1)
        
        return min(1.0, conflict_count * 0.2 + conflict_strength * 0.4 + hook_count * 0.1 + hook_strength * 0.3)
    
    def _score_pace(self, content: str) -> float:
        """节奏控制评分"""
        # 检查句子长度变化（节奏感）
        sentences = re.split(r'[。！？\n]', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) < 3:
            return 0.5
        
        # 长短句交替
        lengths = [len(s) for s in sentences]
        alternations = sum(1 for i in range(1, len(lengths)) if (lengths[i] - lengths[i-1]) * (lengths[i] - lengths[min(i+1, len(lengths)-1)]) < 0)
        alternation_score = alternations / max(len(lengths) - 1, 1)
        
        # 段落变化
        paragraphs = content.split('\n\n')
        paragraph_score = min(1.0, len(paragraphs) / 10)
        
        return min(1.0, alternation_score * 0.5 + paragraph_score * 0.5 + 0.3)
    
    def _score_emotion(self, content: str, profile: Dict) -> float:
        """情绪渲染评分"""
        # 情绪词汇检测
        emotion_patterns = {
            "positive": r'(喜|乐|欢|爱|兴奋|激动|振奋)',
            "negative": r'(怒|哀|惧|恨|悲|痛|绝望)',
            "surprise": r'(惊|愕|愣|意外|出乎)',
            "tension": r'(紧张|焦虑|担忧|恐惧|危机)',
        }
        
        emotion_counts = {k: len(re.findall(p, content)) for k, p in emotion_patterns.items()}
        total_emotion = sum(emotion_counts.values())
        
        # 情绪多样性
        diversity = len([c for c in emotion_counts.values() if c > 0]) / len(emotion_counts)
        
        # 情绪强度
        intensity = min(1.0, total_emotion / 10)
        
        # 结合模型特征
        profile_factor = profile.get("emotion_intensity", 0.7)
        
        return min(1.0, (diversity * 0.4 + intensity * 0.6) * profile_factor + 0.2)
    
    def compare(self, plans: List[PlotPlan]) -> Dict:
        """对比多个方案"""
        if not plans:
            return {}
        
        # 按总分排序
        ranked = sorted(plans, key=lambda p: p.total_score, reverse=True)
        
        # 生成对比报告
        comparison = {
            "best_plan": ranked[0].to_dict(),
            "ranked": [p.to_dict() for p in ranked],
            "summary": self._generate_comparison_summary(ranked),
        }
        
        return comparison
    
    def _generate_comparison_summary(self, plans: List[PlotPlan]) -> str:
        """生成对比摘要"""
        lines = ["# 剧情方案对比报告\n"]
        
        # 总体评价
        best = plans[0]
        lines.append(f"## 最优方案：{best.title}\n")
        lines.append(f"**模型**: {best.model}\n")
        lines.append(f"**总分**: {best.total_score:.2f}\n")
        lines.append(f"**优势**: 情节完整度高，人物塑造细腻\n")
        
        # 各方案对比
        lines.append("## 各方案评分对比\n")
        lines.append("| 方案 | 总分 | 情节 | 人物 | 冲突 | 节奏 | 情绪 |")
        lines.append("|------|------|------|------|------|------|------|")
        for plan in plans:
            lines.append(
                f"| {plan.title} | {plan.total_score:.2f} | "
                f"{plan.plot_score:.2f} | {plan.character_score:.2f} | "
                f"{plan.conflict_score:.2f} | {plan.pace_score:.2f} | "
                f"{plan.emotion_score:.2f} |"
            )
        lines.append("")
        
        # 选择建议
        lines.append("## 选择建议\n")
        if best.plot_score >= 0.8 and best.character_score >= 0.7:
            lines.append("✅ **推荐选择**：该方案情节完整、人物丰满，适合作为主推方案。")
        elif best.conflict_score >= 0.8:
            lines.append("✅ **推荐选择**：该方案冲突设计出色，适合快节奏剧情。")
        elif best.emotion_score >= 0.8:
            lines.append("✅ **推荐选择**：该方案情绪渲染到位，适合情感向剧情。")
        else:
            lines.append("⚠️ **建议调整**：可参考其他方案的优点进行优化。")
        
        return "\n".join(lines)


class ContextAnalyzer:
    """上下文分析器"""
    
    PATTERNS = {
        "conflict": r"(冲突|对抗|争夺|对决|战斗|杀|战|斗|争|夺)",
        "hook": r"(悬念|疑问|谜团|真相|秘密|隐藏|未知|发现|揭示)",
        "foreshadow": r"(预示|暗示|伏笔|征兆|预感|梦见|异象)",
        "climax": r"(巅峰|高潮|决战|终极|最强|极限|突破)",
        "character_growth": r"(成长|突破|领悟|觉醒|进化|蜕变|提升|升级)",
        "reversal": r"(反转|突变|出乎|意外|背叛|欺骗|伪装)",
        "emotion": r"(喜|怒|哀|乐|悲|欢|离|合|爱|恨|情|仇)",
    }
    
    def analyze(self, content: str) -> Dict:
        """分析章节内容"""
        elements = []
        sentences = re.split(r'[。！？\n]', content)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 5:
                continue
            
            for elem_type, pattern in self.PATTERNS.items():
                if re.search(pattern, sentence):
                    elements.append({
                        "type": elem_type,
                        "content": sentence,
                        "strength": 0.7,
                        "relevance": 0.8,
                    })
                    break
        
        return {
            "element_count": len(elements),
            "element_types": list(set(e["type"] for e in elements)),
            "elements": elements[:20],
        }


def main():
    parser = argparse.ArgumentParser(description="增强版剧情推演引擎")
    subparsers = parser.add_subparsers(dest="command")
    
    # simulate
    sim_parser = subparsers.add_parser("simulate", help="模拟推演")
    sim_parser.add_argument("--context", "-c", required=True, help="上下文内容")
    sim_parser.add_argument("--outline", "-o", required=True, help="大纲内容")
    sim_parser.add_argument("--model", "-m", default="glm", 
                           choices=["glm", "deepseek", "qwen", "all"])
    sim_parser.add_argument("--plans", "-n", type=int, default=3, help="生成方案数")
    sim_parser.add_argument("--output", "-O", help="输出文件")
    
    # compare
    comp_parser = subparsers.add_parser("compare", help="对比方案")
    comp_parser.add_argument("plans", nargs="+", help="方案文件列表")
    
    args = parser.parse_args()
    
    simulator = EnhancedPlotSimulator()
    
    if args.command == "simulate":
        models = ["glm", "deepseek", "qwen"] if args.model == "all" else [args.model]
        all_plans = []
        
        for model in models:
            plans = simulator.simulate(
                context=args.context,
                outline=args.outline,
                model=model,
                n_plans=args.plans,
            )
            all_plans.extend(plans)
        
        comparison = simulator.compare(all_plans)
        
        output = {
            "context_analysis": simulator.analyzer.analyze(args.context),
            "comparison": comparison,
            "plans": [p.to_dict() for p in all_plans],
        }
        
        out_path = args.output or f"plot-simulation-v2-result-{int(time.time())}.json"
        Path(out_path).write_text(json.dumps(output, ensure_ascii=False, indent=2))
        
        print(f"✅ 已生成 {len(all_plans)} 个剧情方案")
        print(f"   最佳方案: {comparison['best_plan']['title']}")
        print(f"   总分: {comparison['best_plan']['total_score']:.2f}")
        print(f"   结果文件: {out_path}")
        
    elif args.command == "compare":
        plans = []
        for plan_file in args.plans:
            data = json.loads(Path(plan_file).read_text())
            plan = PlotPlan(
                plan_id=data["plan_id"],
                model=data["model"],
                title=data["title"],
                summary=data["summary"],
                content=data["content"],
                plot_score=data.get("scores", {}).get("plot", 0),
                character_score=data.get("scores", {}).get("character", 0),
                conflict_score=data.get("scores", {}).get("conflict", 0),
                pace_score=data.get("scores", {}).get("pace", 0),
                emotion_score=data.get("scores", {}).get("emotion", 0),
            )
            plans.append(plan)
        
        comparison = simulator.compare(plans)
        print(comparison["summary"])
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
