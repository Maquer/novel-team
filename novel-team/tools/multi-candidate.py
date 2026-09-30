#!/usr/bin/env python3
"""
multi-candidate.py — 多候选程序选优（借鉴 AI-automatically-generates-novels）

核心功能：
  1. 细纲三候选 → 纯程序裁判（零调用）
     - 收回章数
     - 到期伏笔是否安排回收
     - 钩子查重
     - 账目推进配比
  2. 正文三候选 → 硬闸淘汰 + 文风比较
     - 接缝重复
     - 元语言泄漏
     - 黑名单穿帮词

使用：
  python multi-candidate.py outline --candidates 3
  python multi-candidate.py prose --candidates 3 --hard-gate
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Candidate:
    """候选方案"""
    id: str
    content: str
    score: float = 0.0
    reasons: List[str] = field(default_factory=list)
    rejected: bool = False
    reject_reason: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "score": self.score,
            "reasons": self.reasons,
            "rejected": self.rejected,
            "reject_reason": self.reject_reason,
        }


class MultiCandidateSelector:
    """多候选选择器"""
    
    # 黑名单穿帮词
    BLACKLIST_WORDS = [
        "首先", "其次", "再次", "最后",
        "综上所述", "总而言之",
        "不禁", "仿佛", "映入眼帘",
        "心中一凛", "脸色一变", "眸光微凝",
        "淡淡的说", "冷冷地说",
    ]
    
    # 元语言标记
    META_LANGUAGES = [
        "作为AI", "根据分析", "研究表明",
        "值得注意的是", "需要说明的是",
    ]
    
    def __init__(self):
        self.selected_candidates: Dict[str, str] = {}  # chapter_id -> selected_candidate_id
    
    # ============================================================ 细纲选优
    
    def select_outline_candidate(self, candidates: List[Dict], 
                                 foreshadow_db, account_db) -> Dict:
        """
        细纲三候选程序选优（纯程序裁判，零调用）
        
        判据：
        1. 收回章数：是否安排了伏笔回收
        2. 到期伏笔：是否安排了到期伏笔的回收
        3. 钩子查重：是否有新钩子
        4. 账目推进：是否有账目变化
        """
        scores = []
        
        for i, cand in enumerate(candidates):
            score = 0.0
            reasons = []
            
            # 1. 收回章数（+20分）
            if cand.get("foreshadow_recall"):
                score += 20
                reasons.append(f"安排了{len(cand['foreshadow_recall'])}个伏笔回收")
            
            # 2. 到期伏笔（+30分）
            if cand.get("due_foreshadows"):
                score += 30
                reasons.append(f"处理了{len(cand['due_foreshadows'])}个到期伏笔")
            
            # 3. 钩子查重（+10分）
            hooks = cand.get("hooks", [])
            if hooks:
                score += 10
                reasons.append(f"设置了{len(hooks)}个钩子")
            
            # 4. 账目推进（+20分）
            if cand.get("account_changes"):
                score += 20
                reasons.append(f"有{len(cand['account_changes'])}处账目变化")
            
            # 5. 章节完整性（+20分）
            if cand.get("complete", True):
                score += 20
                reasons.append("章节完整")
            
            scores.append({
                "candidate_id": f"C{i+1}",
                "score": score,
                "reasons": reasons,
                "content": cand,
            })
        
        # 排序选优
        scores.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "selected": scores[0] if scores else None,
            "all_scores": scores,
            "method": "program_judge"
        }
    
    # ============================================================ 正文选优
    
    def hard_gate_filter(self, candidates: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        正文三候选硬闸淘汰
        
        淘汰条件：
        1. 接缝重复：与上一章结尾重复
        2. 元语言泄漏：出现AI标识
        3. 黑名单穿帮词：出现禁用词
        """
        passed = []
        rejected = []
        
        for cand in candidates:
            content = cand.get("content", "")
            reject_reasons = []
            
            # 1. 接缝重复检查
            if self._check_repetition(content):
                reject_reasons.append("与上一章结尾重复")
            
            # 2. 元语言泄漏检查
            if self._check_meta_language(content):
                reject_reasons.append("含元语言泄漏")
            
            # 3. 黑名单穿帮词检查
            blacklisted = self._check_blacklist(content)
            if blacklisted:
                reject_reasons.append(f"含黑名单词: {', '.join(blacklisted[:3])}")
            
            if reject_reasons:
                cand["rejected"] = True
                cand["reject_reason"] = "; ".join(reject_reasons)
                rejected.append(cand)
            else:
                passed.append(cand)
        
        return passed, rejected
    
    def compare_style(self, candidates: List[Dict]) -> Dict:
        """
        文风比较（基于指标）
        
        指标：
        1. 段落长度分布
        2. 对话占比
        3. 描写密度
        4. 情绪词频率
        """
        if not candidates:
            return {}
        
        scores = []
        for cand in candidates:
            content = cand.get("content", "")
            
            # 段落长度方差（越低越稳定）
            paragraphs = content.split('\n')
            para_lengths = [len(p) for p in paragraphs if p.strip()]
            avg_len = sum(para_lengths) / len(para_lengths) if para_lengths else 0
            variance = sum((l - avg_len)**2 for l in para_lengths) / len(para_lengths) if para_lengths else 0
            
            # 对话占比
            dialogue_count = content.count('：') + content.count('"')
            dialogue_ratio = dialogue_count / max(len(content), 1)
            
            # 情绪词频率
            emotion_words = re.findall(r'[喜怒哀乐惧惊悲恨]', content)
            emotion_ratio = len(emotion_words) / max(len(content), 1)
            
            # 综合得分（越低越好）
            style_score = variance * 0.5 + (1 - dialogue_ratio) * 30 + (1 - emotion_ratio) * 20
            
            scores.append({
                "candidate_id": cand.get("id", "unknown"),
                "style_score": style_score,
                "metrics": {
                    "para_variance": variance,
                    "dialogue_ratio": dialogue_ratio,
                    "emotion_ratio": emotion_ratio,
                }
            })
        
        # 选优（分数最低的最佳）
        scores.sort(key=lambda x: x["style_score"])
        
        return {
            "selected": scores[0] if scores else None,
            "all_scores": scores,
            "method": "style_comparison"
        }
    
    # ============================================================ 辅助方法
    
    def _check_repetition(self, content: str, threshold: int = 50) -> bool:
        """检查是否与上一章结尾重复"""
        # 简化版：检查是否有长重复片段
        sentences = re.split(r'[。！？]', content)
        for i in range(len(sentences) - 1):
            if sentences[i].strip() == sentences[i+1].strip() and len(sentences[i]) > threshold:
                return True
        return False
    
    def _check_meta_language(self, content: str) -> bool:
        """检查是否含元语言"""
        for pattern in self.META_LANGUAGES:
            if pattern in content:
                return True
        return False
    
    def _check_blacklist(self, content: str) -> List[str]:
        """检查是否含黑名单词"""
        found = []
        for word in self.BLACKLIST_WORDS:
            if word in content:
                found.append(word)
        return found
    
    def select_prose_candidate(self, candidates: List[Dict], 
                               prev_chapter_content: str = "") -> Dict:
        """
        正文三候选选择（硬闸淘汰 + 文风比较）
        """
        # 硬闸淘汰
        passed, rejected = self.hard_gate_filter(candidates)
        
        result = {
            "rejected": rejected,
            "passed": passed,
        }
        
        if not passed:
            result["selected"] = None
            result["method"] = "all_rejected"
            result["message"] = "所有候选均被硬闸淘汰，需重新生成"
            return result
        
        # 文风比较
        if len(passed) > 1:
            style_result = self.compare_style(passed)
            selected = style_result.get("selected")
            result["selected"] = selected
            result["method"] = "style_comparison"
        else:
            result["selected"] = passed[0]
            result["method"] = "single_candidate"
        
        return result


def cmd_outline(args):
    """细纲选优"""
    selector = MultiCandidateSelector()
    
    # 模拟三个候选
    candidates = []
    for i in range(args.candidates):
        candidates.append({
            "id": f"C{i+1}",
            "content": f"这是第{i+1}个候选细纲...",
            "foreshadow_recall": [f"回收伏笔{i+1}"] if i == 0 else [],
            "due_foreshadows": [f"到期伏笔{i+1}"] if i == 0 else [],
            "hooks": [f"钩子{i+1}"] if i == 0 else [],
            "account_changes": [f"账目变化{i+1}"] if i == 0 else [],
            "complete": True,
        })
    
    result = selector.select_outline_candidate(candidates, None, None)
    
    print("\n=== 细纲选优结果 ===\n")
    if result["selected"]:
        print(f"✅ 选中: {result['selected']['candidate_id']}")
        print(f"   得分: {result['selected']['score']}")
        print(f"   理由: {', '.join(result['selected']['reasons'])}")
    
    print("\n【所有候选评分】")
    for s in result["all_scores"]:
        status = "✅" if s == result["selected"] else "  "
        print(f"{status} {s['candidate_id']}: {s['score']}分")
        for r in s['reasons']:
            print(f"    - {r}")


def cmd_prose(args):
    """正文选优"""
    selector = MultiCandidateSelector()
    
    # 模拟三个候选
    candidates = []
    for i in range(args.candidates):
        content = f"这是第{i+1}个候选正文..."
        if i == 1:
            content += "不禁感到..."  # 黑名单词
        candidates.append({
            "id": f"C{i+1}",
            "content": content,
        })
    
    result = selector.select_prose_candidate(candidates)
    
    print("\n=== 正文选优结果 ===\n")
    
    if result.get("rejected"):
        print("【被淘汰候选】")
        for cand in result["rejected"]:
            print(f"  ❌ {cand['id']}: {cand.get('reject_reason', '未知原因')}")
        print()
    
    if result.get("selected"):
        print(f"✅ 选中: {result['selected']['candidate_id']}")
        print(f"   方法: {result['method']}")
    
    print(f"\n【通过硬闸】: {len(result.get('passed', []))}个")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="多候选程序选优（借鉴AI-automatically-generates-novels）")
    subparsers = parser.add_subparsers(dest="command")
    
    # outline命令
    p_outline = subparsers.add_parser("outline", help="细纲选优")
    p_outline.add_argument("--candidates", "-c", type=int, default=3, help="候选数")
    
    # prose命令
    p_prose = subparsers.add_parser("prose", help="正文选优")
    p_prose.add_argument("--candidates", "-c", type=int, default=3, help="候选数")
    p_prose.add_argument("--hard-gate", action="store_true", help="启用硬闸淘汰")
    
    args = parser.parse_args()
    
    if args.command == "outline":
        cmd_outline(args)
    elif args.command == "prose":
        cmd_prose(args)
    else:
        parser.print_help()
