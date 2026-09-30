#!/usr/bin/env python3
"""
plot-analyzer.py — 剧情分析服务（借鉴 MuMuAINovel）

核心功能：
  1. 章节分析：识别钩子、冲突、伏笔
  2. 情节结构：分析三幕式结构
  3. 节奏检测：检测快慢节奏变化
  4. 情感曲线：分析情感波动

使用：
  python plot-analyzer.py analyze --chapter 1 --content "..."
  python plot-analyzer.py structure --file chapter.md
  python plot-analyzer.py rhythm --file chapter.md
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class PlotElement:
    """剧情元素"""
    type: str  # "hook" | "conflict" | "foreshadow" | "climax" | "resolution"
    content: str
    position: int  # 在章节中的位置（字符索引）
    confidence: float  # 0.0-1.0
    description: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "type": self.type,
            "content": self.content,
            "position": self.position,
            "confidence": self.confidence,
            "description": self.description,
        }


@dataclass
class PlotAnalysis:
    """剧情分析报告"""
    chapter_id: str
    word_count: int
    elements: List[PlotElement] = field(default_factory=list)
    structure: str = ""  # "three_act" | "hero_journey" | "kishotenketsu"
    pace: str = ""  # "fast" | "medium" | "slow"
    emotional_curve: List[float] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    foreshadows: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "chapter_id": self.chapter_id,
            "word_count": self.word_count,
            "elements": [e.to_dict() for e in self.elements],
            "structure": self.structure,
            "pace": self.pace,
            "emotional_curve": self.emotional_curve,
            "hooks": self.hooks,
            "conflicts": self.conflicts,
            "foreshadows": self.foreshadows,
        }


class PlotAnalyzer:
    """剧情分析器"""
    
    # 钩子标记词
    HOOK_MARKERS = [
        "突然", "没想到", "竟", "居然", "然而", "但是", "可是",
        "就在这时", "忽然", "猛然", "骤然",
    ]
    
    # 冲突标记词
    CONFLICT_MARKERS = [
        "打", "杀", "斗", "争", "抢", "夺", "攻", "防",
        "反对", "对抗", "冲突", "矛盾", "纠纷", "争吵",
    ]
    
    # 伏笔标记词
    FORESHADOW_MARKERS = [
        "暗示", "预示", "预兆", "征兆", "线索", "痕迹",
        "隐约", "似乎", "好像", "仿佛",
    ]
    
    # 高潮标记词
    CLIMAX_MARKERS = [
        "终于", "关键时刻", "最高潮", "最终", "最后",
        "生死", "存亡", "成败", "决断",
    ]
    
    def __init__(self):
        self.analysis_history: List[PlotAnalysis] = []
    
    def analyze(self, chapter_id: str, content: str, 
               word_count: int = None) -> PlotAnalysis:
        """分析章节剧情"""
        if word_count is None:
            word_count = len(re.findall(r'[\u4e00-\u9fff]', content))
        
        analysis = PlotAnalysis(
            chapter_id=chapter_id,
            word_count=word_count,
        )
        
        # 1. 识别剧情元素
        analysis.elements = self._identify_elements(content)
        
        # 2. 分析情节结构
        analysis.structure = self._analyze_structure(content)
        
        # 3. 检测节奏
        analysis.pace = self._detect_pace(content)
        
        # 4. 分析情感曲线
        analysis.emotional_curve = self._analyze_emotional_curve(content)
        
        # 5. 提取钩子、冲突、伏笔
        analysis.hooks = self._extract_hooks(content)
        analysis.conflicts = self._extract_conflicts(content)
        analysis.foreshadows = self._extract_foreshadows(content)
        
        self.analysis_history.append(analysis)
        
        return analysis
    
    def _identify_elements(self, content: str) -> List[PlotElement]:
        """识别剧情元素"""
        elements = []
        
        # 查找钩子
        for marker in self.HOOK_MARKERS:
            matches = list(re.finditer(re.escape(marker), content))
            for m in matches:
                start = max(0, m.start() - 50)
                end = min(len(content), m.end() + 50)
                context = content[start:end]
                elements.append(PlotElement(
                    type="hook",
                    content=context,
                    position=m.start(),
                    confidence=0.7,
                    description=f"钩子标记: {marker}"
                ))
        
        # 查找冲突
        for marker in self.CONFLICT_MARKERS:
            matches = list(re.finditer(re.escape(marker), content))
            for m in matches:
                start = max(0, m.start() - 50)
                end = min(len(content), m.end() + 50)
                context = content[start:end]
                elements.append(PlotElement(
                    type="conflict",
                    content=context,
                    position=m.start(),
                    confidence=0.6,
                    description=f"冲突标记: {marker}"
                ))
        
        # 查找伏笔
        for marker in self.FORESHADOW_MARKERS:
            matches = list(re.finditer(re.escape(marker), content))
            for m in matches:
                start = max(0, m.start() - 50)
                end = min(len(content), m.end() + 50)
                context = content[start:end]
                elements.append(PlotElement(
                    type="foreshadow",
                    content=context,
                    position=m.start(),
                    confidence=0.5,
                    description=f"伏笔标记: {marker}"
                ))
        
        # 查找高潮
        for marker in self.CLIMAX_MARKERS:
            matches = list(re.finditer(re.escape(marker), content))
            for m in matches:
                start = max(0, m.start() - 50)
                end = min(len(content), m.end() + 50)
                context = content[start:end]
                elements.append(PlotElement(
                    type="climax",
                    content=context,
                    position=m.start(),
                    confidence=0.8,
                    description=f"高潮标记: {marker}"
                ))
        
        # 去重（相同位置只保留最高置信度的）
        seen_positions = {}
        for elem in elements:
            pos_key = elem.position // 100  # 100字符内算同一位置
            if pos_key not in seen_positions or elem.confidence > seen_positions[pos_key].confidence:
                seen_positions[pos_key] = elem
        
        return list(seen_positions.values())
    
    def _analyze_structure(self, content: str) -> str:
        """分析情节结构"""
        # 简化版：根据开头结尾判断
        paragraphs = content.split('\n')
        
        if len(paragraphs) < 3:
            return "unknown"
        
        first_para = paragraphs[0][:100]
        last_para = paragraphs[-1][:100]
        
        # 检测三幕式
        has_setup = any(w in first_para for w in ["清晨", "昨天", "之前", "自从"])
        has_confrontation = any(w in content for w in ["然而", "但是", "冲突", "对抗"])
        has_resolution = any(w in last_para for w in ["终于", "结果", "最终", " ending"])
        
        if has_setup and has_confrontation and has_resolution:
            return "three_act"
        elif has_confrontation:
            return "conflict_heavy"
        else:
            return "linear"
    
    def _detect_pace(self, content: str) -> str:
        """检测节奏"""
        # 计算平均句长
        sentences = re.split(r'[。！？]', content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return "unknown"
        
        avg_len = sum(len(s) for s in sentences) / len(sentences)
        
        if avg_len < 15:
            return "fast"
        elif avg_len < 30:
            return "medium"
        else:
            return "slow"
    
    def _analyze_emotional_curve(self, content: str) -> List[float]:
        """分析情感曲线（简化版）"""
        # 根据标点符号和语气词推断情感强度
        emotions = []
        paragraphs = content.split('\n')
        
        for para in paragraphs:
            # 计算情感强度（简化版）
            intensity = 0.0
            
            # 感叹号增加强度
            intensity += para.count('！') * 0.2
            
            # 问号增加不确定性
            intensity += para.count('？') * 0.1
            
            # 动作描写增加强度
            if any(w in para for w in ["打", "跑", "冲", "喊", "吼"]):
                intensity += 0.3
            
            # 心理描写增加强度
            if any(w in para for w in ["想", "心", "意识", "感到"]):
                intensity += 0.2
            
            emotions.append(min(intensity, 1.0))
        
        return emotions
    
    def _extract_hooks(self, content: str) -> List[str]:
        """提取钩子"""
        hooks = []
        for marker in self.HOOK_MARKERS:
            matches = re.findall(f'.{{0,30}}{re.escape(marker)}.{{0,50}}', content)
            hooks.extend(matches)
        return list(set(hooks))[:5]  # 去重，最多5个
    
    def _extract_conflicts(self, content: str) -> List[str]:
        """提取冲突"""
        conflicts = []
        for marker in self.CONFLICT_MARKERS:
            matches = re.findall(f'.{{0,30}}{re.escape(marker)}.{{0,50}}', content)
            conflicts.extend(matches)
        return list(set(conflicts))[:5]
    
    def _extract_foreshadows(self, content: str) -> List[str]:
        """提取伏笔"""
        foreshadows = []
        for marker in self.FORESHADOW_MARKERS:
            matches = re.findall(f'.{{0,30}}{re.escape(marker)}.{{0,50}}', content)
            foreshadows.extend(matches)
        return list(set(foreshadows))[:5]
    
    def print_report(self, analysis: PlotAnalysis):
        """打印分析报告"""
        print("\n" + "=" * 60)
        print(f"📊 剧情分析报告 - 第{analysis.chapter_id}章")
        print("=" * 60)
        print(f"字数: {analysis.word_count:,}")
        print(f"结构: {analysis.structure}")
        print(f"节奏: {analysis.pace}")
        print()
        
        if analysis.hooks:
            print("【钩子】")
            for h in analysis.hooks[:3]:
                print(f"  - {h[:50]}...")
            print()
        
        if analysis.conflicts:
            print("【冲突】")
            for c in analysis.conflicts[:3]:
                print(f"  - {c[:50]}...")
            print()
        
        if analysis.foreshadows:
            print("【伏笔】")
            for f in analysis.foreshadows[:3]:
                print(f"  - {f[:50]}...")
            print()
        
        if analysis.elements:
            print("【剧情元素】")
            for elem in analysis.elements[:10]:
                print(f"  [{elem.type}] {elem.content[:40]}... (置信度: {elem.confidence:.2f})")
            print()
        
        print("=" * 60)


def cmd_analyze(args):
    """执行剧情分析"""
    analyzer = PlotAnalyzer()
    
    content = args.content or ""
    if args.file:
        content = Path(args.file).read_text(encoding='utf-8', errors='replace')
    
    if not content.strip():
        print("❌ 错误: 没有提供内容")
        return 1
    
    analysis = analyzer.analyze(args.chapter, content)
    analyzer.print_report(analysis)
    
    # 保存报告
    if args.output:
        report = analysis.to_dict()
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"\n📄 报告已保存到: {args.output}")
    
    return 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="剧情分析服务（借鉴MuMuAINovel）")
    parser.add_argument("--chapter", "-c", required=True, help="章节ID")
    parser.add_argument("--content", help="章节内容")
    parser.add_argument("--file", "-f", help="章节文件")
    parser.add_argument("--output", "-o", help="输出报告文件")
    
    args = parser.parse_args()
    sys.exit(cmd_analyze(args))
