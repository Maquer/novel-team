# Version: 0.1.0
"""
fine_tuning_suppression.py — The Last Fingerprint 抑制策略

核心思想:
  "禁止 Markdown 后残留"的发现说明简单 prompt 抑制不够
  需要多层抑制策略（prompt + structural + post-processing）

用法:
    from fine_tuning_suppression import suppress_markdown_residuals
    suppressed = suppress_markdown_residuals(text)
    
    # 或创建 suppression prompt template
    prompt = build_suppression_prompt(model_family='gpt', style='prose')
"""

import re
from typing import List, Dict


# ── 抑制策略配置 ─────────────────────────────────────────────────

SUPPRESSION_STRATEGIES = {
    'gpt': {  # GPT 系列（高 em dash 残留）
        'em_dash_threshold': 3.0,  # 每千字允许的最大 em dash 数
        'em_dash_replacement': '—',  # 替换为中文破折号
        'ban_patterns': [
            r'——+',  # 长破折号
            r'\*\*[^*]+\*\*',  # 粗体标记
            r'#{1,6}\s',  # 标题标记
            r'^\s*-\s',  # 无序列表
            r'^\s*\d+\.\s',  # 有序列表
        ],
        'style_mode': 'prose',  # 散文模式：最小化结构化输出
    },
    'llama': {  # Llama 系列（零残留基线）
        'em_dash_threshold': 0.0,
        'em_dash_replacement': None,  # 直接删除
        'ban_patterns': [
            r'——+',
            r'\*\*[^*]+\*\*',
            r'#{1,6}\s',
        ],
        'style_mode': 'minimal',  # 极简模式
    },
    'claude': {  # Claude 系列（中等残留）
        'em_dash_threshold': 2.0,
        'em_dash_replacement': '——',
        'ban_patterns': [
            r'——+',
            r'\*\*[^*]+\*\*',
        ],
        'style_mode': 'balanced',  # 平衡模式
    },
}


# ── 抑制函数 ─────────────────────────────────────────────────────

def suppress_markdown_residuals(text: str, model_family: str = 'auto') -> dict:
    """
    对文本应用 Markdown 残留抑制策略。

    参数:
        text: 原始 Markdown 文本
        model_family: 'auto'（自动检测）、'gpt'、'llama'、'claude'

    返回:
        dict: {suppressed_text, em_dash_count, suppression_actions[]}
    """
    # 自动检测模型家族
    if model_family == 'auto':
        model_family = detect_model_family(text)
    
    config = SUPPRESSION_STRATEGIES.get(model_family, SUPPRESSION_STRATEGIES['gpt'])
    
    actions = []
    suppressed = text
    
    # 策略 1: Em dash 抑制（核心）
    em_dash_count_before = len(re.findall(r'——+', text))
    em_dash_count_after = len(re.findall(r'——+', suppressed))
    
    if em_dash_count_after > 0:
        if config['em_dash_replacement']:
            suppressed = suppressed.replace('——', config['em_dash_replacement'])
            actions.append({
                'type': 'em_dash_replace',
                'count': em_dash_count_before - em_dash_count_after,
                'strategy': config['em_dash_replacement'],
            })
        else:
            suppressed = re.sub(r'——+', '', suppressed)
            actions.append({
                'type': 'em_dash_remove',
                'count': em_dash_count_before,
            })
    
    # 策略 2: 禁止模式抑制
    for pattern in config['ban_patterns']:
        matches = re.findall(pattern, suppressed)
        if matches:
            suppressed = re.sub(pattern, '', suppressed)
            actions.append({
                'type': 'pattern_ban',
                'pattern': pattern,
                'count': len(matches),
            })
    
    # 策略 3: 段落重组（散文模式）
    if config['style_mode'] == 'prose':
        suppressed = reassemble_prose(suppressed)
        actions.append({'type': 'prose_reassemble'})
    
    return {
        'suppressed_text': suppressed,
        'original_em_dash_count': em_dash_count_before,
        'final_em_dash_count': len(re.findall(r'——+', suppressed)),
        'model_family': model_family,
        'suppression_actions': actions,
    }


def detect_model_family(text: str) -> str:
    """
    从文本特征推断可能的模型家族。
    
    启发式规则:
      - 高 em dash 密度 → GPT 系列
      - 零 em dash + 极简 → Llama 系列
      - 中等 em dash → Claude 系列
    """
    em_dash_density = len(re.findall(r'——+', text)) / max(1, len(text) / 1000)
    
    if em_dash_density > 5:
        return 'gpt'
    elif em_dash_density == 0 and len(text.split('\n')) < 20:
        return 'llama'
    else:
        return 'claude'


def reassemble_prose(text: str) -> str:
    """将 Markdown 结构化文本重组为散文格式。"""
    lines = text.split('\n')
    prose_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 移除 Markdown 标记
        line = re.sub(r'#{1,6}\s+', '', line)  # 标题
        line = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)  # 粗体
        line = re.sub(r'\*([^*]+)\*', r'\1', line)  # 斜体
        line = re.sub(r'`([^`]+)`', r'\1', line)  # 代码
        line = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', line)  # 链接
        
        # 列表项转段落
        if line.startswith('- ') or line.startswith('* ') or line.startswith('+ '):
            line = line[2:]
        elif re.match(r'^\d+\.\s', line):
            line = re.sub(r'^\d+\.\s', '', line)
        
        if line:
            prose_lines.append(line)
    
    # 合并为散文段落
    prose = '. '.join(prose_lines)
    prose = prose.replace('. .', '.').strip()
    return prose


# ── Suppression Prompt Template ──────────────────────────────────

SUPPRESSION_PROMPTS = {
    'gpt': """你是一个专业的技术写作者。请按照以下规则重写文本：

1. 禁止使用 em dash（——），改用逗号、分号或重新组织句子
2. 不使用 Markdown 格式（无 # 标题、无 **粗体**、无 - 列表）
3. 使用自然段落和完整句子
4. 保持专业性和清晰度

目标风格：学术论文散文体（类似 Nature/Science 写作风格）

待重写文本：
{input_text}

重写后：""",
    
    'llama': """直接输出纯文本，不用任何 Markdown 格式。
保持简洁，每段不超过 3 句话。

输入：{input_text}

输出：""",
    
    'claude': """请用自然散文风格重写，避免 Markdown 结构痕迹。
可以适当使用段落分隔，但不使用标题、列表等显式标记。

输入：{input_text}

输出：""",
}


def build_suppression_prompt(model_family: str = 'auto', style: str = 'prose') -> str:
    """
    构建抑制策略 prompt template。

    参数:
        model_family: 'gpt' / 'llama' / 'claude' / 'auto'
        style: 'prose' / 'minimal' / 'balanced'

    返回:
        str: 可直接用于 LLM 的 prompt template
    """
    if model_family == 'auto':
        # 根据 style 选择默认 family
        if style == 'minimal':
            model_family = 'llama'
        elif style == 'balanced':
            model_family = 'claude'
        else:
            model_family = 'gpt'
    
    prompt = SUPPRESSION_PROMPTS.get(model_family, SUPPRESSION_PROMPTS['gpt'])
    return prompt


# ── 测试 ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 60)
    print("  Fine-Tuning Suppression 抑制策略测试")
    print("=" * 60)
    
    # 测试用例：高 em dash 密度文本
    test_text = """# 引言

这是一段测试文本——用于演示抑制效果——包含多个 em dash。

## 关键点

- 第一点：em dash 是 Markdown 残留的最小单元
- 第二点：GPT-4.1 产生 10.62‰ em dash
- 第三点：Llama 全系列为零

> **提示**: 这是引用块测试。
> 包含**粗体**和*斜体*。
"""
    
    print("\n1. 测试 GPT 系列抑制（em dash 替换）:")
    result_gpt = suppress_markdown_residuals(test_text, model_family='gpt')
    print(f"   Em dash 数量: {result_gpt['original_em_dash_count']} → {result_gpt['final_em_dash_count']}")
    print(f"   抑制动作: {len(result_gpt['suppression_actions'])} 项")
    
    print("\n2. 测试 Llama 系列抑制（em dash 删除）:")
    result_llama = suppress_markdown_residuals(test_text, model_family='llama')
    print(f"   Em dash 数量: {result_llama['original_em_dash_count']} → {result_llama['final_em_dash_count']}")
    
    print("\n3. 测试自动检测:")
    detected = detect_model_family(test_text)
    print(f"   检测到的模型家族: {detected}")
    
    print("\n4. 测试 Suppression Prompt:")
    prompt = build_suppression_prompt(model_family='gpt', style='prose')
    print(f"   Prompt 长度: {len(prompt)} 字符")
    print(f"   前 100 字符: {prompt[:100]}...")
    
    print("\n✅ 抑制策略测试完成")
