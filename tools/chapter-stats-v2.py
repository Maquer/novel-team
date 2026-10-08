#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chapter-stats-v2.py — 章节字数分布分析

分析小说章节字数分布，识别节奏模式。

用法：
    python3 chapter-stats-v2.py --input research/chapters-full.json --output research/chapter-analysis-v2.json
"""

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class StatsResult:
    total_chapters: int
    total_words: int
    avg_words: float
    min_words: int
    max_words: int
    median_words: int
    std_dev: float
    coefficient_of_variation: float
    distribution: Dict[str, int]
    percentiles: Dict[str, int]
    patterns: List[str]


def analyze_chapters(data: dict) -> StatsResult:
    chapters = data.get("chapters", [])

    if not chapters:
        return StatsResult(0, 0, 0, 0, 0, 0, 0, 0, {}, {}, [])

    word_counts = [c["word_count"] for c in chapters]
    total = sum(word_counts)
    count = len(word_counts)
    avg = total / count

    # 排序计算中位数
    sorted_counts = sorted(word_counts)
    median = sorted_counts[count // 2] if count % 2 == 1 else (sorted_counts[count // 2 - 1] + sorted_counts[count // 2]) / 2

    # 标准差
    variance = sum((x - avg) ** 2 for x in word_counts) / count
    std_dev = math.sqrt(variance)

    # 变异系数
    cv = std_dev / avg if avg > 0 else 0

    # 百分位数
    def percentile(p):
        idx = int(count * p / 100)
        return sorted_counts[min(idx, count - 1)]

    percentiles = {
        "p10": percentile(10),
        "p25": percentile(25),
        "p50": median,
        "p75": percentile(75),
        "p90": percentile(90),
    }

    # 字数分布（按1000字区间）
    distribution = {}
    bins = [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 20000]
    for i in range(len(bins) - 1):
        low = bins[i]
        high = bins[i + 1]
        count_in_bin = sum(1 for x in word_counts if low <= x < high)
        distribution[f"{low}-{high}"] = count_in_bin

    # 识别节奏模式
    patterns = []

    if cv < 0.3:
        patterns.append("章节字数稳定")
    elif cv < 0.5:
        patterns.append("章节字数中等波动")
    else:
        patterns.append("章节字数波动大")

    if avg > 4000:
        patterns.append("长章节风格（>4000字/章）")
    elif avg > 2500:
        patterns.append("中长章节风格（2500-4000字/章）")
    elif avg > 1500:
        patterns.append("标准章节风格（1500-2500字/章）")
    else:
        patterns.append("短章节风格（<1500字/章）")

    # 检查是否有异常短章
    short_chapters = [c for c in chapters if c["word_count"] < 500]
    if short_chapters:
        patterns.append(f"存在{len(short_chapters)}章异常短章（<500字）")

    # 检查章节长度方差趋势（前100章 vs 后100章）
    if count >= 200:
        first_100 = word_counts[:100]
        last_100 = word_counts[-100:]
        first_avg = sum(first_100) / len(first_100)
        last_avg = sum(last_100) / len(last_100)
        if last_avg > first_avg * 1.2:
            patterns.append("后期章节变长趋势")
        elif first_avg > last_avg * 1.2:
            patterns.append("后期章节变短趋势")

    return StatsResult(
        total_chapters=count,
        total_words=total,
        avg_words=round(avg, 1),
        min_words=min(word_counts),
        max_words=max(word_counts),
        median_words=int(median),
        std_dev=round(std_dev, 1),
        coefficient_of_variation=round(cv, 3),
        distribution=distribution,
        percentiles=percentiles,
        patterns=patterns
    )


def main():
    parser = argparse.ArgumentParser(description="章节字数分布分析 v2")
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"分析完成：\n")
    print(f"总章节数：{result.total_chapters:,}")
    print(f"总字数：{result.total_words:,}")
    print(f"平均每章：{result.avg_words:,} 字")
    print(f"中位数：{result.median_words:,} 字")
    print(f"字数范围：{result.min_words:,} - {result.max_words:,} 字")
    print(f"标准差：{result.std_dev:,}")
    print(f"变异系数：{result.coefficient_of_variation}")
    print(f"\n识别模式：")
    for p in result.patterns:
        print(f"  • {p}")
    print(f"\n已保存到 {output_path}")


if __name__ == "__main__":
    main()
