# Version: 0.1.0
"""
structural_chunker.py — 结构感知分块器（MDKeyChunker Stage 1 借鉴）

按 Markdown 语义边界切割：header / code_block / table / list / blockquote / paragraph
原子性保证：table、code_block 永不跨 chunk 切割
最小尺寸过滤：相邻小块自动合并，避免无上下文的 micro-chunk

用法:
    from structural_chunker import structural_chunk
    chunks = structural_chunk(markdown_text, max_size=1500)
"""

import re

# ── Markdown 块类型识别 ─────────────────────────────────────────
ATOMIC_TYPES = {'code', 'table', 'blockquote'}
HEADER_RE = re.compile(r'^(#{1,6}\s+.+)$', re.M)
CODE_FENCE_RE = re.compile(r'^(`{3,}|~{3,})\s*(\w+)?$', re.M)
TABLE_START_RE = re.compile(r'^\|')
LIST_START_RE = re.compile(r'^(\s*(- |\* |\d+\. ))')
BLOCKQUOTE_RE = re.compile(r'^(\s*>\s*.+)')
TH_RE = re.compile(r'^(\|[\s\-:|]+\|)$')  # table header separator

def _classify_line(line: str):
    """判断行类型。"""
    if not line.strip():
        return 'empty'
    if HEADER_RE.match(line):
        return 'header'
    if line.startswith('```') or line.startswith('~~~'):
        return 'code_fence'
    if TABLE_START_RE.match(line):
        return 'table'
    if LIST_START_RE.match(line):
        return 'list'
    if BLOCKQUOTE_RE.match(line):
        return 'blockquote'
    if TH_RE.match(line):
        return 'table_sep'
    return 'paragraph'

def structural_chunk(markdown_text: str, max_size: int = 1500, min_size: int = 200) -> list:
    """
    将 Markdown 文本按语义边界切割为 chunk 列表。

    参数:
        markdown_text: 原始 Markdown 文本
        max_size: 软上限（字符数），原子块可超过此值
        min_size: 软下限（字符数），低于此值与相邻块合并

    返回:
        list of str — 每个元素是一个语义完整的 chunk
    """
    if not markdown_text or not markdown_text.strip():
        return []

    lines = markdown_text.split('\n')
    chunks = []          # 最终 chunk 列表，每项为 dict: {text, type, size}
    current_lines = []
    current_type = None
    current_size = 0
    in_code_fence = False
    fence_char = None

    i = 0
    while i < len(lines):
        line = lines[i]
        cls = _classify_line(line)

        # ── 代码围栏处理 ─────────────────────────────────────────
        if line.strip().startswith('```') or line.strip().startswith('~~~'):
            if not in_code_fence:
                in_code_fence = True
                fence_char = line.strip()[0]
                current_lines = [line]
                current_type = 'code_fence_start'
                current_size = len(line)
            else:
                # 关闭围栏
                current_lines.append(line)
                current_type = 'code_block'
                current_size = sum(len(l) for l in current_lines)
                chunks.append({'text': '\n'.join(current_lines), 'type': 'code_block', 'size': current_size})
                current_lines = []
                in_code_fence = False
                fence_char = None
            i += 1
            continue

        if in_code_fence:
            current_lines.append(line)
            current_size = sum(len(l) for l in current_lines)
            i += 1
            continue

        # ── 表格处理（原子块） ─────────────────────────────────────
        if cls == 'table' or cls == 'table_sep':
            # 收集完整表格（直到遇到空行或非表格行）
            table_lines = [line]
            j = i + 1
            while j < len(lines):
                next_cls = _classify_line(lines[j])
                if next_cls in ('table', 'table_sep'):
                    table_lines.append(lines[j])
                    j += 1
                elif next_cls == 'empty':
                    # 空行后可能还有表格行
                    if j + 1 < len(lines) and _classify_line(lines[j+1]) in ('table', 'table_sep'):
                        table_lines.append(lines[j])  # 保留空行
                        j += 1
                    else:
                        break
                else:
                    break
            chunk_text = '\n'.join(table_lines)
            chunks.append({'text': chunk_text, 'type': 'table', 'size': len(chunk_text)})
            i = j
            continue

        # ── 普通块处理 ─────────────────────────────────────────────
        if cls == 'header' and current_lines:
            # 保存当前 chunk（如果非空）
            _flush_current(chunks, current_lines, current_type, current_size, min_size)
            current_lines = [line]
            current_type = 'header'
            current_size = len(line)
        elif cls == 'list' and current_lines and current_type in ('paragraph', 'empty'):
            # 列表前 flush paragraph
            _flush_current(chunks, current_lines, current_type, current_size, min_size)
            current_lines = [line]
            current_type = 'list'
            current_size = len(line)
        elif cls in ATOMIC_TYPES and current_lines:
            # 原子块到来，先 flush 当前
            _flush_current(chunks, current_lines, current_type, current_size, min_size)
            current_lines = [line]
            current_type = cls
            current_size = len(line)
        else:
            # 同类型或段落：追加
            current_lines.append(line)
            current_size = sum(len(l) for l in current_lines)

            # 软上限触发 flush（跳过原子块）
            if current_size >= max_size and current_type not in ATOMIC_TYPES:
                _flush_current(chunks, current_lines, current_type, current_size, min_size)
                current_lines = []
                current_type = None
                current_size = 0

        i += 1

    # 收尾
    if current_lines:
        _flush_current(chunks, current_lines, current_type, current_size, min_size)

    return [c['text'] for c in chunks if c['text'].strip()]


def _flush_current(chunks: list, lines: list, chunk_type: str, size: int, min_size: int):
    """将当前行组 flush 为 chunk，处理最小尺寸合并。"""
    text = '\n'.join(lines)
    if not text.strip():
        return

    # 最小尺寸检查：太小则暂存，等待合并
    if size < min_size and chunks and chunks[-1]['size'] + size < min_size * 2:
        # 合并到上一个 chunk
        chunks[-1]['text'] = chunks[-1]['text'] + '\n' + text
        chunks[-1]['size'] += size + 1
        return

    chunks.append({'text': text, 'type': chunk_type or 'paragraph', 'size': size})


def chunk_stats(chunks: list) -> dict:
    """返回 chunk 统计信息（接受 dict 列表或 string 列表）。"""
    if not chunks:
        return {'count': 0, 'avg_size': 0, 'types': {}}
    # 兼容：string list → 自动包装
    if isinstance(chunks[0], str):
        items = [{'text': c, 'type': 'paragraph', 'size': len(c)} for c in chunks]
    else:
        items = chunks
    types = {}
    total = 0
    for c in items:
        t = c.get('type', 'unknown')
        types[t] = types.get(t, 0) + 1
        total += c.get('size', len(c.get('text', '')))
    return {
        'count': len(items),
        'avg_size': total // len(items) if items else 0,
        'types': types,
    }


if __name__ == '__main__':
    # 自测
    sample = """# 测试文档

这是第一段内容，包含一些文字。

```python
def hello():
    print("world")
```

| 列1 | 列2 |
|-----|-----|
| a   | b   |

- 列表项一
- 列表项二

## 第二节

继续内容...

> 引用块内容
> 第二行引用

普通段落结束。"""

    chunks = structural_chunk(sample, max_size=300)
    stats = chunk_stats(chunks)
    print(f"Chunks: {stats['count']}, avg_size: {stats['avg_size']}")
    print(f"Types: {stats['types']}")
    for i, c in enumerate(chunks):
        print(f"\n--- Chunk {i+1} ({len(c)} chars) ---")
        print(c[:100] + '...' if len(c) > 100 else c)
