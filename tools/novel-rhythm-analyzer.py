#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
novel-rhythm-analyzer.py — 小说节奏分析器

分析小说章节字数分布，识别写作节奏模式。

用法：
    python3 novel-rhythm-analyzer.py --novel "我的公公叫康熙" --input research/chapters-full.json
"""

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class RhythmPattern:
    name: str
    description: str
    confidence: float
    evidence: List[str]


@dataclass
class NovelRhythm:
    novel_title: str
    total_chapters: int
    total_words: int
    avg_words_per_chapter: float
    std_dev: float
    cv: float
    patterns: List[RhythmPattern]
    recommendations: List[str]


def analyze_rhythm(data: dict, novel_title: str) -> NovelRhythm:
    chapters = data.get("chapters", [])

    if not chapters:
        return NovelRhythm(novel_title, 0, 0, 0, 0, 0, [], [])

    word_counts = [c["word_count"] for c in chapters]
    total = sum(word_counts)
    count = len(word_counts)
    avg = total / count
    variance = sum((x - avg) ** 2 for x in word_counts) / count
    std_dev = math.sqrt(variance)
    cv = std_dev / avg if avg > 0 else 0

    patterns = []
    recommendations = []

    # 1. 字数稳定性分析
    if cv < 0.15:
        patterns.append(RhythmPattern(
            "稳定型",
            "章节字数非常稳定，作者有明确的字数规划",
            1.0 - cv,
            [f"变异系数: {cv:.3f}"]
        ))
    elif cv < 0.3:
        patterns.append(RhythmPattern(
            "中等稳定",
            "章节字数有一定波动，但在合理范围内",
            0.7,
            [f"变异系数: {cv:.3f}"]
        ))
    else:
        patterns.append(RhythmPattern(
            "波动型",
            "章节字数波动较大，可能随剧情需要调整",
            max(0.1, 0.5 - cv),
            [f"变异系数: {cv:.3f}"]
        ))

    # 2. 章节长度分析
    if avg > 4000:
        patterns.append(RhythmPattern(
            "长篇风格",
            "单章篇幅较长，适合深度描写",
            0.8,
            [f"平均每章: {avg:.0f}字"]
        ))
    elif avg > 2500:
        patterns.append(RhythmPattern(
            "中篇风格",
            "单章篇幅适中，平衡密度与可读性",
            0.9,
            [f"平均每章: {avg:.0f}字"]
        ))
    else:
        patterns.append(RhythmPattern(
            "短篇风格",
            "单章篇幅较短，节奏明快",
            0.7,
            [f"平均每章: {avg:.0f}字"]
        ))

    # 3. 字数趋势分析（前10% vs 后10%）
    if count >= 100:
        first_10pct = word_counts[:int(count * 0.1)]
        last_10pct = word_counts[-int(count * 0.1):]
        first_avg = sum(first_10pct) / len(first_10pct)
        last_avg = sum(last_10pct) / len(last_10pct)

        if last_avg > first_avg * 1.2:
            patterns.append(RhythmPattern(
                "渐进加长",
                "后期章节逐渐变长，剧情复杂度提升",
                (last_avg - first_avg) / first_avg,
                [f"前10%平均: {first_avg:.0f}字", f"后10%平均: {last_avg:.0f}字"]
            ))
        elif first_avg > last_avg * 1.2:
            patterns.append(RhythmPattern(
                "渐进缩短",
                "后期章节逐渐变短，节奏加快",
                (first_avg - last_avg) / first_avg,
                [f"前10%平均: {first_avg:.0f}字", f"后10%平均: {last_avg:.0f}字"]
            ))

    # 4. 异常检测
    short_chapters = [c for c in chapters if c["word_count"] < 500]
    long_chapters = [c for c in chapters if c["word_count"] > 8000]

    if short_chapters:
        patterns.append(RhythmPattern(
            "存在短章",
            f"有{len(short_chapters)}章字数不足500字，可能是过渡章或特殊设计",
            0.6,
            [f"短章数: {len(short_chapters)}"]
        ))

    if long_chapters:
        patterns.append(RhythmPattern(
            "存在长篇",
            f"有{len(long_chapters)}章字数超8000字，可能是高潮章或特殊章节",
            0.6,
            [f"长篇数: {len(long_chapters)}"]
        ))

    # 生成建议
    if cv > 0.3:
        recommendations.append("章节字数波动较大，建议保持每章2000-4000字的稳定区间")
    if short_chapters:
        recommendations.append(f"发现{len(short_chapters)}章异常短章，建议检查是否为未完成的过渡段")
    if long_chapters:
        recommendations.append(f"发现{len(long_chapters)}章超长章，建议拆分或检查是否为特殊设计")

    return NovelRhythm(
        novel_title=novel_title,
        total_chapters=count,
        total_words=total,
        avg_words_per_chapter=round(avg, 1),
        std_dev=round(std_dev, 1),
        cv=round(cv, 3),
        patterns=patterns,
        recommendations=recommendations
    )


def main():
    parser = argparse.ArgumentParser(description="小说节奏分析器")
    parser.add_argument("--novel", "-n", required=True, help="小说名称")
    parser.add_argument("--input", "-i", required=True, help="输入JSON文件")
    parser.add_argument("--output", "-o", default=None, help="输出JSON文件（可选）")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：文件不存在 {input_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(input_path.read_text(encoding='utf-8'))
    result = analyze_rhythm(data, args.novel)

    # 输出
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"已保存到 {output_path}\n")

    # 打印报告
    print(f"《{result.novel_title}》节奏分析报告\n")
    print(f"{'='*50}")
    print(f"总章节数：{result.total_chapters:,}")
    print(f"总字数：{result.total_words:,}")
    print(f"平均每章：{result.avg_words_per_chapter:,} 字")
    print(f"标准差：{result.std_dev:,}")
    print(f"变异系数：{result.cv}")
    print(f"{'='*50}\n")

    print("识别模式：")
    for p in result.patterns:
        print(f"  • [{p.name}] 置信度: {p.confidence:.0%}")
        print(f"    {p.description}")
        for e in p.evidence:
            print(f"    - {e}")
        print()

    if result.recommendations:
        print("建议：")
        for r in result.recommendations:
            print(f"  • {r}")


if __name__ == "__main__":
    main()
