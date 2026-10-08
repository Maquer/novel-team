#!/usr/bin/env python3
"""
风格保留机制 — v0.46.0新增

功能：
  1. 识别作者独特表达习惯
  2. 标记不可修复的"风格指纹"
  3. 只在非风格区域执行修复
  4. 生成风格保护报告

核心逻辑：
  - 作者风格 = 高频独特表达（如特定比喻、句式、词汇偏好）
  - AI味特征 = 通用AI痕迹（如"首先/其次/最后"、长破折号、排比句）
  - 保留风格，只修复AI味

使用：
  python style-preserver.py analyze --file chapter.md --output style-report.json
  python style-preserver.py protect --file chapter.md --max-fixes 5
"""

import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter


# 作者风格指纹库（可配置）
DEFAULT_STYLE_FINGERPRINTS = {
    "sentence_patterns": [
        r"[、][^、]{5,15}[、][^、]{5,15}[、]",  # 顿号排比
        r"……",  # 省略号
        r"[！？]{2,}",  # 双标点
        r"[（(][^）)]{2,10}[)）]",  # 括号注释
    ],
    "vocabulary_preferences": [
        r"倏地",  # 古风词汇
        r"眸光",  # 特定描写词
        r"唇角",  # 面部描写偏好
        r"指尖",  # 动作描写偏好
        r"眸色",  # 眼神描写偏好
    ],
    "forbidden_ai_patterns": [
        r"首先.*其次.*最后",  # 序数词结构
        r"综上所述",  # 总结词
        r"不可否认",  # AI惯用语
        r"毋庸置疑",  # AI惯用语
        r"值得注意的是",  # AI惯用语
    ]
}


class StylePreserver:
    """风格保留器"""
    
    def __init__(self, custom_fingerprints: Optional[Dict] = None):
        self.fingerprints = custom_fingerprints or DEFAULT_STYLE_FINGERPRINTS
        self.style_markers = []  # 标记的风格区域
        self.ai_hits = []  # 检测到的AI味
        self.protected_regions = []  # 受保护的区域（不修复）
    
    def analyze(self, text: str) -> Dict:
        """
        分析文本，识别作者风格和AI味
        
        参数：
            text: 原文本
        
        返回：
            风格分析报告
        """
        result = {
            "style_fingerprints": [],
            "ai_tone_hits": [],
            "protected_regions": [],
            "safe_regions": [],
            "recommendations": []
        }
        
        # 1. 识别作者风格指纹
        style_fingerprints = self._detect_style_fingerprints(text)
        result["style_fingerprints"] = style_fingerprints
        
        # 2. 检测AI味特征
        ai_hits = self._detect_ai_tone(text)
        result["ai_tone_hits"] = ai_hits
        
        # 3. 标记受保护区域（风格指纹附近）
        protected_regions = self._mark_protected_regions(text, style_fingerprints, ai_hits)
        result["protected_regions"] = protected_regions
        
        # 4. 计算安全区域（可以修复的区域）
        safe_regions = self._calculate_safe_regions(text, protected_regions)
        result["safe_regions"] = safe_regions
        
        # 5. 生成修复建议
        recommendations = self._generate_recommendations(style_fingerprints, ai_hits, protected_regions)
        result["recommendations"] = recommendations
        
        # 保存当前状态
        self.style_markers = style_fingerprints
        self.ai_hits = ai_hits
        self.protected_regions = protected_regions
        
        return result
    
    def protect_and_fix(self, text: str, max_fixes: int = 5) -> Dict:
        """
        保护风格区域，仅修复安全区域
        
        参数：
            text: 原文本
            max_fixes: 最大修复数量
        
        返回：
            修复结果（包含修复后的文本和修复日志）
        """
        # 分析文本
        analysis = self.analyze(text)
        
        # 获取安全区域
        safe_regions = analysis["safe_regions"]
        
        # 只在安全区域执行修复
        fixed_text = text
        fix_log = []
        
        for region in safe_regions[:max_fixes]:
            # 在安全区域内尝试修复AI味
            region_text = fixed_text[region["start"]:region["end"]]
            original_text = region_text
            
            # 执行修复（简化版，实际应调用novel-humanizer）
            region_text = self._fix_ai_tone_in_region(region_text)
            
            # 记录修复
            if region_text != original_text:
                fix_log.append({
                    "region": region,
                    "original": original_text[:50] + "..." if len(original_text) > 50 else original_text,
                    "fixed": region_text[:50] + "..." if len(region_text) > 50 else region_text
                })
                fixed_text = fixed_text[:region["start"]] + region_text + fixed_text[region["end"]:]
        
        return {
            "original_text": text,
            "fixed_text": fixed_text,
            "fix_count": len(fix_log),
            "max_fixes": max_fixes,
            "fix_log": fix_log,
            "protected_regions_count": len(analysis["protected_regions"]),
            "style_preserved": True
        }
    
    def generate_style_report(self, text: str) -> str:
        """生成风格保护报告（用户友好格式）"""
        analysis = self.analyze(text)
        
        report_lines = [
            "=== 风格保护报告 ===",
            f"分析时间：{__import__('datetime').datetime.now().isoformat()}",
            "",
            "【作者风格指纹】",
        ]
        
        for fp in analysis["style_fingerprints"]:
            report_lines.append(f"  - {fp['type']}: {fp['pattern'][:30]}...")
        
        report_lines.extend([
            "",
            "【AI味检测】",
        ])
        
        for hit in analysis["ai_tone_hits"]:
            report_lines.append(f"  - [{hit['level']}] {hit['pattern']}: {hit['text'][:30]}...")
        
        report_lines.extend([
            "",
            "【保护区域】",
            f"  共 {len(analysis['protected_regions'])} 个区域受保护（不修复）",
            "",
            "【安全区域】",
            f"  共 {len(analysis['safe_regions'])} 个区域可修复",
            "",
            "【修复建议】",
        ])
        
        for rec in analysis["recommendations"]:
            report_lines.append(f"  - {rec}")
        
        report_lines.append("")
        report_lines.append("=== 报告结束 ===")
        
        return "\n".join(report_lines)
    
    # ========== 内部方法 ==========
    
    def _detect_style_fingerprints(self, text: str) -> List[Dict]:
        """检测作者风格指纹"""
        fingerprints = []
        
        # 检测句式模式
        for pattern in self.fingerprints.get("sentence_patterns", []):
            matches = re.findall(pattern, text)
            if matches:
                fingerprints.append({
                    "type": "sentence_pattern",
                    "pattern": pattern,
                    "count": len(matches),
                    "examples": matches[:3]
                })
        
        # 检测词汇偏好
        for pattern in self.fingerprints.get("vocabulary_preferences", []):
            matches = re.findall(pattern, text)
            if matches:
                fingerprints.append({
                    "type": "vocabulary_preference",
                    "pattern": pattern,
                    "count": len(matches),
                    "examples": list(set(matches))[:5]
                })
        
        return fingerprints
    
    def _detect_ai_tone(self, text: str) -> List[Dict]:
        """检测AI味特征"""
        hits = []
        
        # 检测AI惯用语
        for pattern in self.fingerprints.get("forbidden_ai_patterns", []):
            matches = re.finditer(pattern, text)
            for match in matches:
                hits.append({
                    "type": "ai_cliché",
                    "pattern": pattern,
                    "text": match.group(0),
                    "position": match.start(),
                    "level": "high"
                })
        
        # 检测顿号罗列过密
        duo_pattern = re.compile(r'[^\n。！？；]{0,60}[、][^、\n。！？；]{1,12}[、][^、\n。！？；]{1,12}')
        for match in duo_pattern.finditer(text):
            hits.append({
                "type": "duo_list_dense",
                "pattern": "顿号罗列过密",
                "text": match.group(0)[:50],
                "position": match.start(),
                "level": "medium"
            })
        
        # 检测长破折号
        em_dash_pattern = re.compile(r'——[^—]{20,}——')
        for match in em_dash_pattern.finditer(text):
            hits.append({
                "type": "em_dash_overuse",
                "pattern": "长破折号",
                "text": match.group(0)[:50],
                "position": match.start(),
                "level": "medium"
            })
        
        return hits
    
    def _mark_protected_regions(self, text: str, fingerprints: List[Dict], ai_hits: List[Dict]) -> List[Dict]:
        """标记受保护区域（风格指纹附近）"""
        protected = []
        
        for fp in fingerprints:
            # 找到风格指纹在文本中的位置
            pattern = fp["pattern"]
            for match in re.finditer(pattern, text):
                # 标记指纹前后各50字符为受保护区域
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                
                protected.append({
                    "start": start,
                    "end": end,
                    "reason": f"风格指纹: {fp['type']}",
                    "content": text[start:end]
                })
        
        # 去重并合并重叠区域
        protected = self._merge_regions(protected)
        
        return protected
    
    def _calculate_safe_regions(self, text: str, protected: List[Dict]) -> List[Dict]:
        """计算安全区域（未被保护的区域）"""
        if not protected:
            # 如果没有受保护区域，整个文本都是安全的
            return [{"start": 0, "end": len(text), "reason": "无风格指纹保护"}]
        
        safe = []
        last_end = 0
        
        for region in protected:
            if region["start"] > last_end:
                safe.append({
                    "start": last_end,
                    "end": region["start"],
                    "reason": "非风格区域"
                })
            last_end = region["end"]
        
        # 添加最后的安全区域
        if last_end < len(text):
            safe.append({
                "start": last_end,
                "end": len(text),
                "reason": "非风格区域"
            })
        
        return safe
    
    def _fix_ai_tone_in_region(self, text: str) -> str:
        """在安全区域内修复AI味（简化版）"""
        fixed = text
        
        # 修复AI惯用语
        for pattern in self.fingerprints.get("forbidden_ai_patterns", []):
            fixed = re.sub(pattern, "", fixed)
        
        # 简化顿号罗列
        duo_pattern = re.compile(r'([^\n。！？；]{0,30})[、]([^\n。！？；]{1,10})[、]([^\n。！？；]{1,10})')
        fixed = duo_pattern.sub(r'\1、\2。\3', fixed)
        
        return fixed
    
    def _merge_regions(self, regions: List[Dict]) -> List[Dict]:
        """合并重叠区域"""
        if not regions:
            return []
        
        # 按起始位置排序
        sorted_regions = sorted(regions, key=lambda x: x["start"])
        merged = [sorted_regions[0]]
        
        for region in sorted_regions[1:]:
            last = merged[-1]
            if region["start"] <= last["end"]:
                # 重叠，合并
                last["end"] = max(last["end"], region["end"])
                last["reason"] += f"+{region['reason']}"
            else:
                merged.append(region)
        
        return merged
    
    def _generate_recommendations(self, fingerprints: List[Dict], ai_hits: List[Dict], protected: List[Dict]) -> List[str]:
        """生成修复建议"""
        recommendations = []
        
        # 基于风格指纹的建议
        if len(fingerprints) > 5:
            recommendations.append("作者风格鲜明，建议保持现有风格，仅修复AI味特征")
        elif len(fingerprints) < 2:
            recommendations.append("作者风格不明显，建议先建立风格基准")
        
        # 基于AI味检测的建议
        high_level_hits = [h for h in ai_hits if h.get("level") == "high"]
        if len(high_level_hits) > 3:
            recommendations.append(f"检测到{len(high_level_hits)}处高优先级AI味，建议优先修复")
        
        # 基于保护区域的建议
        if len(protected) > 0:
            recommendations.append(f"已保护{len(protected)}个风格区域，将在安全区域执行修复")
        
        return recommendations


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="风格保留机制")
    parser.add_argument("--file", help="输入文件")
    parser.add_argument("--text", help="输入文本")
    parser.add_argument("--output", help="输出文件")
    parser.add_argument("--max-fixes", type=int, default=5, help="最大修复数量")
    parser.add_argument("--mode", choices=["analyze", "protect", "report"], default="analyze")
    
    args = parser.parse_args()
    
    preserver = StylePreserver()
    
    # 读取输入
    if args.file:
        text = Path(args.file).read_text(encoding='utf-8')
    elif args.text:
        text = args.text
    else:
        print(json.dumps({"error": "请提供--file或--text参数"}, ensure_ascii=False))
        sys.exit(1)
    
    if args.mode == "analyze":
        result = preserver.analyze(text)
        output = json.dumps(result, ensure_ascii=False, indent=2)
    
    elif args.mode == "protect":
        result = preserver.protect_and_fix(text, args.max_fixes)
        output = json.dumps(result, ensure_ascii=False, indent=2)
    
    elif args.mode == "report":
        output = preserver.generate_style_report(text)
    
    # 输出结果
    if args.output:
        Path(args.output).write_text(output, encoding='utf-8')
        print(f"结果已保存到 {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
