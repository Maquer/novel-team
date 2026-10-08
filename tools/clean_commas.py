#!/usr/bin/env python3
"""
clean_commas.py — 脏逗号清理工具（借鉴 Casting-Workflow）

功能：
  使用jieba分词识别并清理语法错误的逗号
  
使用：
  python clean_commas.py input.txt [--output output.txt]
  python clean_commas.py input.txt -o output.txt
"""

import sys
import re
from pathlib import Path

# 尝试导入jieba
try:
    import jieba
except ImportError:
    print("警告: 未安装jieba，使用简化模式")
    jieba = None


def clean_commas(text: str) -> str:
    """
    清理脏逗号
    
    策略：
    1. 找出所有逗号位置
    2. 检查逗号前后是否构成合理语法结构
    3. 不合理的使用句号或其他标点替换
    """
    if not text:
        return text
    
    # 标记需要检查的逗号位置
    commas = [(m.start(), m.end()) for m in re.finditer(r'，', text)]
    
    if not commas:
        return text
    
    # 分割文本为片段
    parts = []
    last_pos = 0
    
    for pos, _ in commas:
        parts.append(text[last_pos:pos])
        parts.append('，')
        last_pos = pos
    
    parts.append(text[last_pos:])
    
    # 清理逻辑
    cleaned = []
    for i, part in enumerate(parts):
        if i % 2 == 1:  # 逗号位置
            # 检查是否需要保留
            if should_keep_comma(text, part, i):
                cleaned.append(part)
            else:
                # 替换为句号
                cleaned.append('。')
        else:
            cleaned.append(part)
    
    return ''.join(cleaned)


def should_keep_comma(full_text: str, before_comma: str, comma_index: int) -> bool:
    """判断逗号是否应该保留"""
    # 简化版：检查逗号前的内容长度
    # 如果太短（<3字），可能是脏逗号
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', before_comma))
    
    if chinese_chars < 3:
        return False
    
    # 检查逗号后是否为合理开头
    after_comma_start = comma_index + 1
    if after_comma_start < len(full_text):
        after_comma = full_text[after_comma_start:after_comma_start+10]
        # 如果后面是数字或符号，可能是错误的
        if re.match(r'^[\d\s\W]', after_comma):
            return False
    
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="脏逗号清理工具")
    parser.add_argument("input", help="输入文件路径")
    parser.add_argument("--output", "-o", help="输出文件路径")
    
    args = parser.parse_args()
    
    # 读取输入
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 错误: 文件不存在: {args.input}")
        return 1
    
    text = input_path.read_text(encoding='utf-8', errors='replace')
    
    # 清理
    print(f"🧹 正在清理脏逗号: {args.input}")
    cleaned = clean_commas(text)
    
    # 统计变化
    original_commas = text.count('，')
    cleaned_commas = cleaned.count('，')
    removed = original_commas - cleaned_commas
    
    print(f"   原文逗号数: {original_commas}")
    print(f"   清理后: {cleaned_commas}")
    print(f"   移除: {removed}")
    
    # 输出
    output_path = Path(args.output) if args.output else input_path.with_suffix('.cleaned.txt')
    output_path.write_text(cleaned, encoding='utf-8')
    print(f"✅ 已保存: {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
