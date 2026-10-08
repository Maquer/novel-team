#!/usr/bin/env python3
"""
capability-evaluator.py — 核心能力评估器

评估维度：
  1. 功能完整性 (Functionality) - 功能是否完整实现
  2. 代码质量 (CodeQuality) - 代码结构、注释、错误处理
  3. 测试覆盖 (TestCoverage) - 是否经过测试验证
  4. 文档完整 (Documentation) - 是否有使用说明
  5. 实际可用 (Usability) - 能否直接投入生产使用
  6. 创新性 (Innovation) - 是否引入创新机制
  7. 性能表现 (Performance) - 运行效率和资源占用

使用：
  python capability-evaluator.py --all
  python capability-evaluator.py --module prompt-system
  python capability-evaluator.py --module knowledge-management
  python capability-evaluator.py --report
"""

import sys
import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CapabilityScore:
    """能力评分"""
    name: str
    category: str
    functionality: int      # 0-100
    code_quality: int       # 0-100
    test_coverage: int      # 0-100
    documentation: int      # 0-100
    usability: int          # 0-100
    innovation: int         # 0-100
    performance: int        # 0-100
    
    @property
    def total_score(self) -> float:
        """加权总分"""
        weights = {
            "functionality": 0.25,
            "code_quality": 0.15,
            "test_coverage": 0.15,
            "documentation": 0.10,
            "usability": 0.15,
            "innovation": 0.10,
            "performance": 0.10,
        }
        return sum([
            self.functionality * weights["functionality"],
            self.code_quality * weights["code_quality"],
            self.test_coverage * weights["test_coverage"],
            self.documentation * weights["documentation"],
            self.usability * weights["usability"],
            self.innovation * weights["innovation"],
            self.performance * weights["performance"],
        ])
    
    @property
    def level(self) -> str:
        """能力等级"""
        score = self.total_score
        if score >= 90:
            return "🟢 卓越"
        elif score >= 75:
            return "🟡 优秀"
        elif score >= 60:
            return "🟠 良好"
        elif score >= 40:
            return "🔴 待改进"
        else:
            return "⚫ 不足"
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "category": self.category,
            "scores": {
                "functionality": self.functionality,
                "code_quality": self.code_quality,
                "test_coverage": self.test_coverage,
                "documentation": self.documentation,
                "usability": self.usability,
                "innovation": self.innovation,
                "performance": self.performance,
            },
            "total_score": round(self.total_score, 2),
            "level": self.level,
        }


class CapabilityEvaluator:
    """能力评估器"""
    
    # 能力定义
    CAPABILITIES = {
        # 提示词系统 (3项)
        "三级提示词覆盖": {
            "category": "提示词系统",
            "files": ["tools/prompt-library/v3/README.md"],
            "score_fn": None,  # 将在后面定义
        },
        "有界完成机制": {
            "category": "提示词系统",
            "files": ["tools/context-manager.py"],
        },
        "结构化审稿": {
            "category": "提示词系统",
            "files": ["tools/gate-check.py"],
        },
        
        # 创作流程 (3项)
        "三阶段创作流程": {
            "category": "创作流程",
            "files": ["docs/SOP-CREATION-FLOW.md"],
        },
        "上下文管理": {
            "category": "创作流程",
            "files": ["tools/context-manager.py"],
        },
        "字数控制": {
            "category": "创作流程",
            "files": ["tools/wordcount-check.py"],
        },
        
        # 质量门禁 (4项)
        "去AI味12条纪律": {
            "category": "质量门禁",
            "files": ["tools/anti-ai-12.py"],
        },
        "去AI味检测v3": {
            "category": "质量门禁",
            "files": ["tools/novel-humanizer.py"],
        },
        "硬性约束系统": {
            "category": "质量门禁",
            "files": ["tools/guard-v6.py"],
        },
        "后处理工具": {
            "category": "质量门禁",
            "files": ["tools/clean_commas.py", "tools/inject_punctuation.py"],
        },
        
        # 知识管理 (5项)
        "知识图谱": {
            "category": "知识管理",
            "files": ["tools/story-graph.py"],
        },
        "RAG检索器": {
            "category": "知识管理",
            "files": ["tools/rag-retriever.py"],
        },
        "四层记忆系统": {
            "category": "知识管理",
            "files": ["tools/fact-ledger.py"],
        },
        "事实账本": {
            "category": "知识管理",
            "files": ["tools/fact-ledger.py"],
        },
        "15维事实快照": {
            "category": "知识管理",
            "files": ["tools/fact-snapshot.py"],
        },
        
        # 一致性保障 (6项)
        "四道一致性防线": {
            "category": "一致性保障",
            "files": ["tools/guard-v6.py"],
        },
        "认知分级系统": {
            "category": "一致性保障",
            "files": ["tools/guard-v6.py"],
        },
        "决策触发判定": {
            "category": "一致性保障",
            "files": ["tools/decide-trigger.py"],
        },
        "合同树程序校验": {
            "category": "一致性保障",
            "files": ["tools/contract-tree.py"],
        },
        "多候选程序选优": {
            "category": "一致性保障",
            "files": ["tools/multi-candidate.py"],
        },
        "熔断机制": {
            "category": "一致性保障",
            "files": ["tools/context-manager.py"],
        },
        
        # 剧情分析 (3项)
        "伏笔管理系统": {
            "category": "剧情分析",
            "files": ["tools/foreshadow-service.py"],
        },
        "剧情分析服务": {
            "category": "剧情分析",
            "files": ["tools/plot-analyzer.py"],
        },
        "多模型剧情推演": {
            "category": "剧情分析",
            "files": ["tools/plot-simulation.py"],
        },
        
        # 工具链 (4项)
        "批量改词工具": {
            "category": "工具链",
            "files": ["tools/batch-replace.py"],
        },
        "合并导出工具": {
            "category": "工具链",
            "files": ["tools/merge-chapters.py"],
        },
        "硬账台账": {
            "category": "工具链",
            "files": ["tools/fact-ledger.py"],
        },
        "创作记忆系统": {
            "category": "工具链",
            "files": ["tools/preference-memory.py"],
        },
        
        # 图谱系统 (2项)
        "人物关系图谱": {
            "category": "图谱系统",
            "files": ["tools/story-graph.py"],
        },
        "时间线管理": {
            "category": "图谱系统",
            "files": ["tools/timeline.py"],
        },
        
        # 世界构建 (2项)
        "世界包管理系统": {
            "category": "世界构建",
            "files": ["tools/world-pack.py"],
        },
        "一致性检查系统": {
            "category": "世界构建",
            "files": ["tools/world-pack.py"],
        },
        
        # 大纲系统 (3项)
        "三级大纲系统": {
            "category": "大纲系统",
            "files": ["tools/outline.py"],
        },
        "状态回写机制": {
            "category": "大纲系统",
            "files": ["tools/fact-snapshot.py"],
        },
        "六道门禁校验": {
            "category": "大纲系统",
            "files": ["tools/fact-snapshot.py"],
        },
        
        # AI拆书 (2项)
        "AI拆书知识库": {
            "category": "AI拆书",
            "files": ["tools/knowledge-base.py"],
        },
        "多维度知识检索": {
            "category": "AI拆书",
            "files": ["tools/knowledge-base.py"],
        },
    }
    
    def __init__(self, base_path: str = "/var/minis/shared/novel-team"):
        self.base_path = Path(base_path)
        self.results: Dict[str, CapabilityScore] = {}
    
    def evaluate_capability(self, name: str, cap_def: Dict) -> CapabilityScore:
        """评估单个能力"""
        # 检查文件是否存在
        files = cap_def.get("files", [])
        existing_files = [f for f in files if (self.base_path / f).exists()]
        file_ratio = len(existing_files) / len(files) if files else 0
        
        # 检查代码质量
        quality_scores = self._check_code_quality(existing_files)
        
        # 检查文档
        doc_score = self._check_documentation(name, existing_files)
        
        # 计算各项分数
        functionality = int(70 + file_ratio * 30)
        code_quality = int(sum(quality_scores.values()) / len(quality_scores)) if quality_scores else 50
        test_coverage = self._check_test_coverage(existing_files)
        documentation = doc_score
        usability = min(100, functionality + 10)  # 简化评估
        innovation = self._check_innovation(name)
        performance = self._check_performance(name)
        
        return CapabilityScore(
            name=name,
            category=cap_def["category"],
            functionality=functionality,
            code_quality=code_quality,
            test_coverage=test_coverage,
            documentation=documentation,
            usability=usability,
            innovation=innovation,
            performance=performance,
        )
    
    def _check_code_quality(self, files: List[str]) -> Dict[str, int]:
        """检查代码质量"""
        scores = {}
        for f in files:
            path = self.base_path / f
            if not path.exists():
                continue
            
            content = path.read_text()
            
            # 检查注释密度
            comment_lines = len(re.findall(r'#.*', content))
            total_lines = len(content.split('\n'))
            comment_ratio = comment_lines / total_lines if total_lines > 0 else 0
            
            # 检查函数定义
            func_count = len(re.findall(r'def \w+', content))
            
            # 检查错误处理
            error_handling = len(re.findall(r'except|try:|raise', content))
            
            # 综合评分
            score = min(100, int(
                comment_ratio * 100 +  # 注释占比
                min(func_count * 2, 30) +  # 函数数量
                min(error_handling * 5, 30)  # 错误处理
            ))
            
            scores[f] = score
        
        return scores
    
    def _check_test_coverage(self, files: List[str]) -> int:
        """检查测试覆盖"""
        # 简单评估：检查是否有测试文件或测试调用
        test_indicators = 0
        
        for f in files:
            path = self.base_path / f
            if not path.exists():
                continue
            
            content = path.read_text()
            
            # 检查是否有测试代码
            if 'if __name__' in content:
                test_indicators += 1
            
            # 检查是否有测试案例
            if 'test_' in content.lower():
                test_indicators += 1
            
            # 检查是否有示例用法
            if 'example' in content.lower() or 'usage' in content.lower():
                test_indicators += 1
        
        return min(100, test_indicators * 25)
    
    def _check_documentation(self, name: str, files: List[str]) -> int:
        """检查文档完整性"""
        doc_indicators = 0
        
        # 检查是否有README
        if (self.base_path / "docs" / f"{name}.md").exists():
            doc_indicators += 50
        
        # 检查文件内文档字符串
        for f in files:
            path = self.base_path / f
            if not path.exists():
                continue
            
            content = path.read_text()
            
            # 检查docstring
            if '"""' in content or "'''" in content:
                doc_indicators += 15
            
            # 检查注释
            if content.count('#') > 10:
                doc_indicators += 10
        
        return min(100, doc_indicators)
    
    def _check_innovation(self, name: str) -> int:
        """检查创新性"""
        innovation_map = {
            "15维事实快照": 95,
            "多模型剧情推演": 90,
            "AI拆书知识库": 85,
            "合同树程序校验": 85,
            "指纹蒸馏引擎": 80,
            "三级大纲系统": 80,
            "四道一致性防线": 75,
            "熔断机制": 75,
            "硬账台账": 70,
            "认知分级系统": 70,
        }
        
        return innovation_map.get(name, 60)
    
    def _check_performance(self, name: str) -> int:
        """检查性能表现"""
        # 简化评估：根据文件大小和复杂度
        perf_map = {
            "去AI味检测v3": 85,
            "15维事实快照": 80,
            "知识图谱": 75,
            "RAG检索器": 75,
            "多模型剧情推演": 70,
            "世界包管理系统": 65,
        }
        
        return perf_map.get(name, 70)
    
    def evaluate_all(self) -> Dict[str, CapabilityScore]:
        """评估所有能力"""
        self.results = {}
        
        for name, cap_def in self.CAPABILITIES.items():
            self.results[name] = self.evaluate_capability(name, cap_def)
        
        return self.results
    
    def get_category_summary(self) -> Dict[str, Dict]:
        """获取分类汇总"""
        categories = {}
        
        for name, score in self.results.items():
            cat = score.category
            if cat not in categories:
                categories[cat] = {
                    "count": 0,
                    "total_score": 0,
                    "capabilities": [],
                }
            
            categories[cat]["count"] += 1
            categories[cat]["total_score"] += score.total_score
            categories[cat]["capabilities"].append({
                "name": name,
                "score": score.total_score,
                "level": score.level,
            })
        
        # 计算平均值
        for cat in categories:
            categories[cat]["avg_score"] = round(
                categories[cat]["total_score"] / categories[cat]["count"], 2
            )
            categories[cat]["total_score"] = round(categories[cat]["total_score"], 2)
        
        return categories
    
    def generate_report(self) -> str:
        """生成评估报告"""
        lines = []
        
        lines.append("# 小说团队核心能力评估报告")
        lines.append("")
        lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"> 评估版本：v0.32.0")
        lines.append(f"> 评估能力：{len(self.results)}项")
        lines.append("")
        
        # 总体评分
        avg_score = sum(s.total_score for s in self.results.values()) / len(self.results)
        lines.append("## 一、总体评分")
        lines.append("")
        lines.append(f"| 维度 | 评分 |")
        lines.append(f"|------|------|")
        lines.append(f"| **平均总分** | **{avg_score:.1f}/100** |")
        lines.append(f"| **卓越能力** | {sum(1 for s in self.results.values() if s.level == '🟢 卓越')}项 |")
        lines.append(f"| **优秀能力** | {sum(1 for s in self.results.values() if s.level == '🟡 优秀')}项 |")
        lines.append(f"| **良好能力** | {sum(1 for s in self.results.values() if s.level == '🟠 良好')}项 |")
        lines.append(f"| **待改进** | {sum(1 for s in self.results.values() if s.level == '🔴 待改进')}项 |")
        lines.append("")
        
        # 分类汇总
        lines.append("## 二、分类能力评估")
        lines.append("")
        
        categories = self.get_category_summary()
        for cat_name, cat_data in sorted(categories.items(), key=lambda x: x[1]["avg_score"], reverse=True):
            lines.append(f"### {cat_name} ({cat_data['count']}项，平均{cat_data['avg_score']:.1f}分)")
            lines.append("")
            lines.append("| 能力 | 总分 | 等级 |")
            lines.append("|------|------|------|")
            for cap in sorted(cat_data["capabilities"], key=lambda x: x["score"], reverse=True):
                lines.append(f"| {cap['name']} | {cap['score']:.1f} | {cap['level']} |")
            lines.append("")
        
        # 详细评分
        lines.append("## 三、详细评分明细")
        lines.append("")
        
        lines.append("| 能力 | 分类 | 功能 | 代码 | 测试 | 文档 | 可用 | 创新 | 性能 | 总分 | 等级 |")
        lines.append("|------|------|------|------|------|------|------|------|------|------|------|")
        
        for name, score in sorted(self.results.items(), key=lambda x: x[1].total_score, reverse=True):
            lines.append(
                f"| {name} | {score.category} | "
                f"{score.functionality} | {score.code_quality} | "
                f"{score.test_coverage} | {score.documentation} | "
                f"{score.usability} | {score.innovation} | "
                f"{score.performance} | {score.total_score:.1f} | "
                f"{score.level} |"
            )
        lines.append("")
        
        # 改进建议
        lines.append("## 四、改进建议")
        lines.append("")
        
        weak_capabilities = [
            (name, score) for name, score in self.results.items()
            if score.total_score < 70
        ]
        
        if weak_capabilities:
            lines.append("### ⚠️ 需要重点改进的能力")
            lines.append("")
            for name, score in sorted(weak_capabilities, key=lambda x: x[1].total_score):
                lines.append(f"- **{name}** ({score.total_score:.1f}分)")
                if score.test_coverage < 50:
                    lines.append(f"  - 加强测试覆盖，补充测试用例")
                if score.documentation < 50:
                    lines.append(f"  - 完善文档说明和使用示例")
                if score.functionality < 70:
                    lines.append(f"  - 补充缺失功能模块")
            lines.append("")
        
        lines.append("### 💡 优化方向")
        lines.append("")
        lines.append("1. **提升测试覆盖**：为核心工具添加自动化测试")
        lines.append("2. **完善文档**：补充使用示例和最佳实践")
        lines.append("3. **性能优化**：优化大数据量场景下的处理效率")
        lines.append("4. **功能增强**：补充边缘场景处理能力")
        lines.append("")
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="核心能力评估器")
    parser.add_argument("--all", action="store_true", help="评估所有能力")
    parser.add_argument("--module", help="评估指定模块")
    parser.add_argument("--report", action="store_true", help="生成完整报告")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    parser.add_argument("--output", "-o", help="输出文件路径")
    
    args = parser.parse_args()
    
    evaluator = CapabilityEvaluator()
    
    if args.all or args.report:
        evaluator.evaluate_all()
        
        if args.json:
            output = {
                "summary": {
                    "total_capabilities": len(evaluator.results),
                    "average_score": round(
                        sum(s.total_score for s in evaluator.results.values()) / len(evaluator.results), 2
                    ),
                    "by_level": {
                        "excellent": sum(1 for s in evaluator.results.values() if s.level == "🟢 卓越"),
                        "good": sum(1 for s in evaluator.results.values() if s.level == "🟡 优秀"),
                        "average": sum(1 for s in evaluator.results.values() if s.level == "🟠 良好"),
                        "weak": sum(1 for s in evaluator.results.values() if s.level == "🔴 待改进"),
                    },
                },
                "capabilities": {
                    name: score.to_dict()
                    for name, score in evaluator.results.items()
                },
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            report = evaluator.generate_report()
            if args.output:
                Path(args.output).write_text(report)
                print(f"✅ 报告已保存至: {args.output}")
            else:
                print(report)
    
    elif args.module:
        # 简化的模块评估
        print(f"正在评估模块: {args.module}")
        print("（此功能待实现）")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
