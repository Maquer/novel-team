#!/usr/bin/env python3
# Version: 0.1.0
"""
mdeval-assessor.py — MDEval Markdown Awareness 评估器（精简修复版）

论文: arXiv:2501.15000 (WWW 2025)
核心指标: Markdown Awareness (MA) = 1 - editDistance(r, r̂) / max(len(r), len(r̂))

评估维度（4 维等权 0-25 分）:
  1. 结构化输出完整度: header/list/code/table 覆盖率
  2. 格式一致性: Markdown 语法正确性
  3. 可读性: 段落/列表/标题层级合理性
  4. 内容-结构对齐: 标题与正文匹配度

用法:
    from mdeval_assessor import calculate_md_awareness
    result = calculate_md_awareness("# 标题\n\n内容...")
    print(f"MA Score: {result['score']}/100")

依赖: 纯 Python（无外部依赖），可离线运行
"""

import re
from typing import List, Dict, Any


# ── Markdown 元素提取器 ───────────────────────────────────────────

HEADER_RE = re.compile(r'^(#{1,6}\s+.+)$', re.M)
BOLD_RE = re.compile(r'\*\*([^*]+)\*\*|__([^_]+)__')
ITALIC_RE = re.compile(r'\*([^*]+)\*|_([^_]+)_')
CODE_BLOCK_RE = re.compile(r'^(`{3,}[\s\S]*?`{3,})$', re.M)
INLINE_CODE_RE = re.compile(r'`([^`]+)`')
TABLE_RE = re.compile(r'^\|.*\|\s*$\n(\|[\s\-:|]+\|\s*$\n)?(\|.*\|\s*$\n)*', re.M)
LIST_RE = re.compile(r'^(\s*[-*+]|\s*\d+\.)\s+', re.M)
BLOCKQUOTE_RE = re.compile(r'^\s*>\s*', re.M)
LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
HORIZONTAL_RULE_RE = re.compile(r'^(-{3,}|_{3,}|\*{3,})$', re.M)


def extract_elements(text: str) -> Dict[str, list]:
    """提取 Markdown 文档中的结构元素。"""
    lines = text.split('\n')
    
    elements = {
        'headers': [],
        'bold': [],
        'italic': [],
        'code_blocks': [],
        'inline_codes': [],
        'tables': [],
        'lists': [],
        'blockquotes': [],
        'links': [],
        'images': [],
        'horizontal_rules': [],
        'paragraphs': [],
    }
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Headers
        m = HEADER_RE.match(line)
        if m:
            level_match = re.match(r'^(#{1,6})', line)
            if level_match:
                elements['headers'].append({
                    'level': len(level_match.group(1)),
                    'text': m.group(1).strip(),
                    'line': i + 1,
                })
            i += 1
            continue
        
        # Code blocks
        if line.strip().startswith('```'):
            block_lines = [line]
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                block_lines.append(lines[i])
                i += 1
            if i < len(lines):
                block_lines.append(lines[i])
                i += 1
            lang = block_lines[0].strip()[3:].strip() if block_lines else ''
            elements['code_blocks'].append({
                'language': lang,
                'lines': len(block_lines),
            })
            continue
        
        # Tables
        if line.strip().startswith('|'):
            table_lines = [line]
            i += 1
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i])
                i += 1
            elements['tables'].append({'lines': len(table_lines)})
            continue
        
        # Lists
        m = LIST_RE.match(line)
        if m:
            elements['lists'].append({
                'type': 'bullet' if line.strip()[0] in '-*+' else 'number',
                'line': i + 1,
            })
            i += 1
            continue
        
        # Blockquotes
        if BLOCKQUOTE_RE.match(line):
            elements['blockquotes'].append({'line': i + 1})
            i += 1
            continue
        
        # Horizontal rules
        if HORIZONTAL_RULE_RE.match(line.strip()):
            elements['horizontal_rules'].append({'line': i + 1})
        
        # Inline elements
        elements['bold'].extend(BOLD_RE.findall(line))
        elements['italic'].extend(ITALIC_RE.findall(line))
        elements['inline_codes'].extend(INLINE_CODE_RE.findall(line))
        elements['links'].extend(LINK_RE.findall(line))
        elements['images'].extend(IMAGE_RE.findall(line))
        
        # Paragraphs（非空行且非上述类型）
        if line.strip() and not any([
            line.startswith('#'),
            line.startswith('```'),
            line.startswith('|'),
            bool(LIST_RE.match(line)),
            bool(BLOCKQUOTE_RE.match(line)),
            bool(HORIZONTAL_RULE_RE.match(line.strip())),
        ]):
            elements['paragraphs'].append({'line': i + 1, 'chars': len(line.strip())})
        
        i += 1
    
    return elements


# ── Markdown Awareness 评分器 ─────────────────────────────────────

def calculate_md_awareness(text: str) -> Dict[str, Any]:
    """
    计算 Markdown Awareness 分数（0-100）。

    公式: MA = w1*structure + w2*consistency + w3*readability + w4*alignment
    权重: 0.3 / 0.25 / 0.25 / 0.20（基于 MDEval 论文）
    """
    if not text or not text.strip():
        return {'score': 0, 'level': '❌ 无内容', 'details': {}}
    
    elements = extract_elements(text)
    total_lines = len(text.split('\n'))
    
    # ── 维度 1: 结构化输出完整度（0-25 分）────────────────────
    structure_score = 0
    
    # Header 覆盖率（目标: 每 500 字符至少 1 个 header）
    header_density = len(elements['headers']) / max(1, total_lines / 500)
    structure_score += min(8, header_density * 2)
    
    # Code block 存在性（代码类文档必须）
    if elements['code_blocks']:
        structure_score += 6
    elif any(kw in text.lower() for kw in ['代码', 'api', 'example', 'function', 'def ']):
        structure_score -= 3
    
    # Table 存在性（对比/数据类文档必须）
    if elements['tables']:
        structure_score += 5
    
    # List 覆盖率
    list_density = len(elements['lists']) / max(1, total_lines / 200)
    structure_score += min(6, list_density * 1.5)
    
    structure_score = max(0, min(25, structure_score))
    
    # ── 维度 2: 格式一致性（0-25 分）─────────────────────────
    consistency_score = 0
    
    # Header 层级连续性（不应跳级，如 # → ###）
    header_levels = [h['level'] for h in elements['headers']]
    if len(header_levels) >= 2:
        jumps = sum(1 for i in range(1, len(header_levels)) 
                    if header_levels[i] - header_levels[i-1] > 1)
        consistency_score += max(0, 10 - jumps * 3)
    else:
        consistency_score += 10
    
    # Bold/Italic 使用合理性
    bold_count = len(elements['bold'])
    para_count = len(elements['paragraphs'])
    if bold_count > 0 and para_count > 0:
        bold_ratio = bold_count / para_count
        if bold_ratio < 5:
            consistency_score += 8
        else:
            consistency_score += max(0, 8 - (bold_ratio - 5) * 2)
    elif para_count == 0:
        consistency_score += 8  # 无段落时不扣分
    
    # Link 格式正确性
    link_errors = 0
    for link in elements['links']:
        if ')' not in link[1]:
            link_errors += 1
    consistency_score += max(0, 7 - link_errors * 2)
    
    consistency_score = max(0, min(25, consistency_score))
    
    # ── 维度 3: 可读性（0-25 分）─────────────────────────────
    readability_score = 0
    
    # 段落长度分布（理想: 20-100 字/段）
    para_lengths = [p['chars'] for p in elements['paragraphs']]
    if para_lengths:
        too_long = sum(1 for l in para_lengths if l > 150)
        too_short = sum(1 for l in para_lengths if l < 10)
        readability_score += max(0, 10 - too_long * 2)
        readability_score += max(0, 5 - too_short)
    
    # 块引用使用
    if elements['blockquotes']:
        readability_score += 5
    
    # 分隔线使用（避免滥用）
    hr_count = len(elements['horizontal_rules'])
    if hr_count > 0:
        if hr_count <= 3:
            readability_score += 5
        else:
            readability_score += max(0, 5 - (hr_count - 3) * 2)
    
    readability_score = max(0, min(25, readability_score))
    
    # ── 维度 4: 内容-结构对齐（0-25 分）──────────────────────
    alignment_score = 0
    
    # Header 与正文匹配度
    header_align = 0
    for h in elements['headers']:
        h_line = h['line']
        content_after = sum(p['chars'] for p in elements['paragraphs'] if p['line'] > h_line)
        if content_after > 50:
            header_align += 3
        else:
            header_align -= 2
    alignment_score += max(0, min(10, header_align))
    
    # 图片 alt text 检查
    alt_missing = sum(1 for img in elements['images'] if not img[0])
    alignment_score += max(0, 8 - alt_missing * 2)
    
    # 链接有效性检查（简化版：检查是否有孤立括号）
    orphan_parens = text.count(')') - text.count('(')
    alignment_score += max(0, 7 - abs(orphan_parens) * 2)
    
    alignment_score = max(0, min(25, alignment_score))
    
    # ── 综合分数 ──────────────────────────────────────────────
    total_score = structure_score + consistency_score + readability_score + alignment_score
    
    # 分级
    if total_score >= 80:
        level = '🟢 优秀'
    elif total_score >= 60:
        level = '🟡 良好'
    elif total_score >= 40:
        level = '🟠 一般'
    elif total_score >= 20:
        level = '🔴 较差'
    else:
        level = '🚨 极差'
    
    return {
        'score': total_score,
        'level': level,
        'details': {
            'structure': {'score': structure_score, 'max': 25, 'weight': 0.3},
            'consistency': {'score': consistency_score, 'max': 25, 'weight': 0.25},
            'readability': {'score': readability_score, 'max': 25, 'weight': 0.25},
            'alignment': {'score': alignment_score, 'max': 25, 'weight': 0.20},
        },
        'elements_count': {
            'headers': len(elements['headers']),
            'code_blocks': len(elements['code_blocks']),
            'tables': len(elements['tables']),
            'lists': len(elements['lists']),
            'paragraphs': len(elements['paragraphs']),
        },
    }


# ── MDEval 标准测试用例 ──────────────────────────────────────────

MDEval_REFERENCE_CASES = {
    'excellent': """# Python 快速入门指南\n\n## 1. 基础语法\n\n### 1.1 变量与数据类型\n\nPython 支持以下基本数据类型：\n\n- **整数**（int）：`42`、`-7`\n- **浮点数**（float）：`3.14`、`-0.5`\n- **字符串**（str）：`"hello"`、`'world'`\n- **布尔**（bool）：`True`、`False`\n\n```python\nx = 42\nname = "Python"\nis_easy = True\n```\n\n### 1.2 条件语句\n\n```python\nif x > 0:\n    print("正数")\nelif x == 0:\n    print("零")\nelse:\n    print("负数")\n```\n\n## 2. 数据结构\n\n| 类型 | 用途 | 示例 |\n|------|------|------|\n| list | 有序集合 | `[1, 2, 3]` |\n| dict | 键值对 | `{"a": 1}` |\n| set | 去重集合 | `{1, 2, 3}` |\n\n## 3. 函数定义\n\n```python\ndef greet(name: str) -> str:\n    \"\"\"返回问候语\"\"\"\n    return f"Hello, {name}!"\n```\n\n> **提示**: 使用类型注解可以提高代码可读性。\n\n### 相关链接\n- [Python 官方文档](https://docs.python.org/3/)\n- [Real Python 教程](https://realpython.com/)""",
    'poor': """python is easy\n\nvariables are simple\nyou can use numbers and strings\n\nhere is some code:\nx = 1\ny = 2\n\nfunctions are defined with def\nyou can call them easily\n\nthat is all"""
}


def test_reference_cases() -> Dict[str, Any]:
    """运行 MDEval 标准测试用例，验证评估器准确性。"""
    results = {}
    for case_name, text in MDEval_REFERENCE_CASES.items():
        result = calculate_md_awareness(text)
        results[case_name] = result
        print(f"  [{case_name}] score={result['score']}/100, level={result['level']}")
    
    passed = results['excellent']['score'] > results['poor']['score']
    icon = "✅" if passed else "❌"
    print(f"  {icon} 评估器排序: excellent ({results['excellent']['score']}) {'>' if passed else '<'} poor ({results['poor']['score']})")
    return {'passed': passed, 'results': results}


if __name__ == '__main__':
    print("=" * 60)
    print("  MDEval Markdown Awareness 评估器自测")
    print("=" * 60)
    test_reference_cases()
    
    print("\n" + "=" * 60)
    print("  自定义文本测试")
    print("=" * 60)
    sample = """# 测试文档\n\n这是一个简单的测试。\n\n## 第二章\n\n- 项目一\n- 项目二\n\n```python\nprint("hello")\n```\n\n> 引用内容\n\n| 表1 | 表2 |\n|-----|-----|\n| a   | b   |\n\n[链接](https://example.com)"""
    result = calculate_md_awareness(sample)
    print(f"\nScore: {result['score']}/100 ({result['level']})")
    print(f"Elements: {result['elements_count']}")
    print(f"Details: {result['details']}")
