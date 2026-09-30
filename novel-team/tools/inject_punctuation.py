#!/usr/bin/env python3
"""
inject_punctuation.py — 标点密度注入工具（借鉴 Casting-Workflow）

功能：
  按照番茄小说风格注入标点密度
  
参数：
  --excl FLOAT  感叹号密度（每百字多少个！）  默认: 0.15
  --comma FLOAT 逗号密度（每百字多少个，）  默认: 1.2
  
使用：
  python inject_punctuation.py input.txt --excl 0.15 --comma 1.2
  python inject_punctuation.py input.txt -e 0.15 -c 1.2 -o output.txt
"""

import sys
import re
import random
from pathlib import Path


def inject_exclamation(text: str, density: float = 0.15) -> str:
    """
    注入感叹号密度
    
    策略：
    - 在情绪高点（对话、动作）后添加感叹号
    - 避免过度使用（每百字density个）
    """
    if density <= 0:
        return text
    
    # 计算目标感叹号数量
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    target_excl = int(chinese_chars * density / 100)
    
    # 找候选位置（句末）
    sentence_endings = [(m.start(), m.end()) for m in re.finditer(r'[。！？]', text)]
    
    if not sentence_endings:
        return text
    
    # 随机选择位置添加感叹号
    current_excl = text.count('！')
    needed = max(0, target_excl - current_excl)
    
    if needed <= 0:
        return text
    
    # 筛选候选（非感叹号结尾的）
    candidates = [(pos, end) for pos, end in sentence_endings if text[end:end+1] != '！']
    random.shuffle(candidates)
    
    # 注入感叹号
    result = list(text)
    for i, (pos, end) in enumerate(candidates[:needed]):
        # 在句末后插入感叹号
        result.insert(end, '！')
    
    return ''.join(result)


def inject_comma(text: str, density: float = 1.2) -> str:
    """
    注入逗号密度
    
    策略：
    - 在长句中添加合理逗号
    - 避免破坏原有结构
    """
    if density <= 0:
        return text
    
    # 计算目标逗号数量
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    target_comma = int(chinese_chars * density / 100)
    
    current_comma = text.count('，')
    needed = max(0, target_comma - current_comma)
    
    if needed <= 0:
        return text
    
    # 找长句（>30字）
    sentences = list(re.finditer(r'[。！？]', text))
    long_sentences = []
    for i, m in enumerate(sentences):
        if i > 0:
            prev_end = sentences[i-1].end()
            sentence_len = m.start() - prev_end
            if sentence_len > 30:
                long_sentences.append((prev_end, m.start()))
    
    if not long_sentences:
        return text
    
    # 在长句中添加逗号
    result = list(text)
    inserted = 0
    
    for start, end in long_sentences:
        if inserted >= needed:
            break
        
        # 找插入点（避开已有标点）
        segment = text[start:end]
        candidates = []
        for i, char in enumerate(segment):
            if char not in '，。！？、；：' and i > 5 and i < len(segment) - 5:
                candidates.append(start + i)
        
        if candidates:
            pos = random.choice(candidates[:5])  # 从前5个候选中选
            result.insert(pos, '，')
            inserted += 1
    
    return ''.join(result)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="标点密度注入工具")
    parser.add_argument("input", help="输入文件路径")
    parser.add_argument("--excl", "-e", type=float, default=0.15, help="感叹号密度（每百字）")
    parser.add_argument("--comma", "-c", type=float, default=1.2, help="逗号密度（每百字）")
    parser.add_argument("--output", "-o", help="输出文件路径")
    
    args = parser.parse_args()
    
    # 读取输入
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 错误: 文件不存在: {args.input}")
        return 1
    
    text = input_path.read_text(encoding='utf-8', errors='replace')
    
    # 注入标点
    print(f"📝 正在注入标点密度...")
    print(f"   感叹号目标: {args.excl}/百字")
    print(f"   逗号目标: {args.comma}/百字")
    
    result = inject_exclamation(text, args.excl)
    result = inject_comma(result, args.comma)
    
    # 统计
    original_excl = text.count('！')
    original_comma = text.count('，')
    result_excl = result.count('！')
    result_comma = result.count('，')
    
    print(f"\n=== 注入结果 ===")
    print(f"感叹号: {original_excl} → {result_excl} (+{result_excl - original_excl})")
    print(f"逗号: {original_comma} → {result_comma} (+{result_comma - original_comma})")
    
    # 输出
    output_path = Path(args.output) if args.output else input_path.with_suffix('.punctuated.txt')
    output_path.write_text(result, encoding='utf-8')
    print(f"\n✅ 已保存: {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
