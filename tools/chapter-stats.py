#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chapter-stats.py — 章节字数统计与节奏分析

分析小说章节字数分布，识别节奏模式。

用法：
    python3 chapter-stats.py --input research/chapters-sample.json --output research/chapter-analysis.json
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ChapterStats:
    """单章统计"""
    number: int
    title: str
    word_count: int
    line_count: int


@dataclass
class AnalysisResult:
    """分析结果"""
    total_chapters: int
    total_words: int
    avg_words_per_chapter: float
    min_words: int
    max_words: int
    std_dev: float
    distribution: Dict[str, int]  # 字数区间统计
    patterns: List[str]


def analyze_chapters(data: dict) -> AnalysisResult:
    """分析章节数据"""
    chapters = data.get("chapters", [])

    if not chapters:
        return AnalysisResult(
            total_chapters=0,
            total_words=0,
            avg_words_per_chapter=0,
            min_words=0,
            max_words=0,
            std_dev=0,
            distribution={},
            patterns=[]
        )

    # 统计字数（从原文计算）
    word_counts = []
    for ch in chapters:
        # 这里用行号差估算字数
        line_diff = ch.get("line_end", 0) - ch.get("line_start", 0)
        word_counts.append(line_diff)

    total = sum(word_counts)
    avg = total / len(word_counts) if word_counts else 0
    min_w = min(word_counts) if word_counts else 0
    max_w = max(word_counts) if word_counts else 0

    # 标准差
    variance = sum((x - avg) ** 2 for x in word_counts) / len(word_counts) if word_counts else 0
    std_dev = variance ** 0.5

    # 分布统计
    distribution = {
        "0-50行": sum(1 for x in word_counts if x < 50),
        "50-100行": sum(1 for x in word_counts if 50 <= x < 100),
        "100-150行": sum(1 for x in word_counts if 100 <= x < 150),
        "150-200行": sum(1 for x in word_counts if 150 <= x < 200),
        "200+行": sum(1 for x in word_counts if x >= 200),
    }

    # 识别模式
    patterns = []
    if std_dev / avg < 0.3:
        patterns.append("字数稳定")
    else:
        patterns.append("字数波动大")

    if avg > 100:
        patterns.append("长章节风格")
    elif avg < 60:
        patterns.append("短章节风格")

    return AnalysisResult(
        total_chapters=len(chapters),
        total_words=total,
        avg_words_per_chapter=avg,
        min_words=min_w,
        max_words=max_w,
        std_dev=std_dev,
        distribution=distribution,
        patterns=patterns
    )


def main():
    parser = argparse.ArgumentParser(description="章节字数统计与节奏分析")
    parser.add_argument("--input", "-i", required=True, help="输入JSON文件")
    parser.add_argument("--output", "-o", required=True, help="输出JSON文件")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"错误：文件不存在 {input_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(input_path.read_text(encoding='utf-8'))
    result = analyze_chapters(data)

    # 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = asdict(result)
    output_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"分析完成：")
    print(f"  - 总章节数：{result.total_chapters}")
    print(f"  - 平均每章节：{result.avg_words_per_chapter:.1f} 行")
    print(f"  - 字数范围：{result.min_words} - {result.max_words} 行")
    print(f"  - 识别模式：{', '.join(result.patterns)}")
    print(f"\n已保存到 {output_path}")


if __name__ == "__main__":
    main()
