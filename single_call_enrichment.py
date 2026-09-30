# Version: 0.1.0
"""
single_call_enrichment.py — MDKeyChunker Stage 2 单次元数据提取

对每个 markdown chunk 单次 LLM 调用提取 7 个字段：
  title, summary, keywords, entities, hypothetical_questions, semantic_key, related_keys

依赖 OpenAI-compatible endpoint（通过环境变量 OPENAI_API_BASE / OPENAI_API_KEY 配置）。
无 API key 时自动降级为规则提取（不依赖 LLM）。

用法:
    from single_call_enrichment import enrich_chunk, enrich_document
    result = enrich_chunk("chunk text here")
    # 或批量:
    results = enrich_document(["chunk1", "chunk2", ...])
"""

import os
import re
import json
import time
import importlib

# ── 规则提取器（无 LLM 时的降级方案）─────────────────────────────

def _rule_extract(chunk_text: str) -> dict:
    """纯规则提取：标题/关键词/实体从 markdown 结构推断。"""
    lines = chunk_text.strip().split('\n')
    
    # 标题：取第一个 # 行
    title = ""
    for line in lines:
        m = re.match(r'^#{1,3}\s+(.+)$', line)
        if m:
            title = m.group(1).strip()
            break
    if not title and lines:
        title = lines[0][:60]
    
    # 关键词：从标题和 frontmatter 提取
    keywords = []
    if title:
        # 标题分词（中文按 2-3 字滑动窗口）
        for t in re.findall(r'[\u4e00-\u9fff]{2,}', title):
            if len(t) <= 3:
                keywords.append(t)
            else:
                for i in range(len(t) - 2):
                    keywords.append(t[i:i+3])
        keywords = list(dict.fromkeys(keywords))[:5]  # 去重
    
    # 实体：人名/地名/项目名（大写字母开头 + 中文专有名词模式）
    entities = []
    for m in re.finditer(r'[A-Z][a-z]+(?:[A-Z][a-z]+)*', chunk_text):
        entities.append(m.group())
    entities = list(set(entities[:5]))
    
    # 假设问题：基于标题生成
    hypothetical_questions = []
    if title:
        hypothetical_questions.append(f"{title}是什么？")
        hypothetical_questions.append(f"如何使用{title}？")
    
    # 语义键：取标题前 2-3 个词作为 topic key
    semantic_key = title[:20] if title else "unknown"
    
    # 相关键：从关键词推导
    related_keys = keywords[:3] if keywords else [semantic_key]
    
    return {
        'title': title,
        'summary': chunk_text[:200].replace('\n', ' '),
        'keywords': keywords,
        'entities': entities,
        'hypothetical_questions': hypothetical_questions,
        'semantic_key': semantic_key,
        'related_keys': related_keys,
        'source': 'rule-based',
    }


# ── LLM 提取器（可选，需要 API key）─────────────────────────────

def _llm_extract(chunk_text: str, api_base: str = None, api_key: str = None) -> dict:
    """单次 LLM 调用提取 7 个元数据字段。"""
    import http.client
    
    base = api_base or os.environ.get('OPENAI_API_BASE', '')
    key = api_key or os.environ.get('OPENAI_API_KEY', '')
    
    if not base or not key:
        return _rule_extract(chunk_text)
    
    prompt = f"""Extract structured metadata from this markdown chunk. Return ONLY valid JSON:

```json
{{
  "title": "string",
  "summary": "one-sentence summary",
  "keywords": ["kw1", "kw2", "kw3"],
  "entities": ["Person/Project/Location"],
  "hypothetical_questions": ["Q1?", "Q2?"],
  "semantic_key": "main-topic-keyword",
  "related_keys": ["k1", "k2"]
}}
```

Content:
{chunk_text[:1500]}
"""
    
    try:
        body = json.dumps({
            'model': os.environ.get('ENRICH_MODEL', 'glm-5.3-flash'),
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 500,
            'temperature': 0,
        }).encode()
        
        conn = http.client.HTTPSConnection(base.replace('http://', '').replace('https://', ''), timeout=30)
        conn.request('POST', '/v1/chat/completions', body, {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}',
        })
        resp = conn.getresponse()
        data = json.loads(resp.read())
        conn.close()
        
        extracted = data['choices'][0]['message']['content'].strip()
        # 提取 JSON 部分
        m = re.search(r'\{.*\}', extracted, re.DOTALL)
        if m:
            result = json.loads(m.group())
            result['source'] = 'llm'
            return result
    except Exception as e:
        print(f"[enrichment] LLM extract failed: {e}", file=__import__('sys').stderr)
    
    return _rule_extract(chunk_text)


# ── 主接口 ───────────────────────────────────────────────────────

def enrich_chunk(chunk_text: str, use_llm: bool = False) -> dict:
    """
    对单个 chunk 提取元数据。

    参数:
        chunk_text: markdown 文本片段
        use_llm: True=尝试 LLM 提取（需配置 API key），False=纯规则提取

    返回:
        dict with 7 fields: title, summary, keywords, entities,
        hypothetical_questions, semantic_key, related_keys, source
    """
    if use_llm:
        return _llm_extract(chunk_text)
    return _rule_extract(chunk_text)


def enrich_document(chunks: list, use_llm: bool = False) -> list:
    """
    对文档的多个 chunk 批量提取元数据。

    参数:
        chunks: list of str（每个元素是一个 chunk）
        use_llm: 是否使用 LLM 提取

    返回:
        list of dict（每个 chunk 一条元数据）
    """
    results = []
    for i, chunk in enumerate(chunks):
        r = enrich_chunk(chunk, use_llm=use_llm)
        r['chunk_index'] = i
        results.append(r)
    return results


def rolling_key_propagation(enrichments: list) -> list:
    """
    Rolling Key 传播：chunk N 携带 0..N-1 的语义键字典。

    参数:
        enrichments: list of dict（enrich_document 的输出）

    返回:
        更新后的 list（每个 dict 新增 'rolling_keys' 字段）
    """
    seen_keys = {}  # semantic_key → count
    for i, e in enumerate(enrichments):
        rolling = list(seen_keys.keys())[-5:]  # 最近 5 个 key
        e['rolling_keys'] = rolling
        key = e.get('semantic_key', '')
        if key:
            seen_keys[key] = seen_keys.get(key, 0) + 1
    return enrichments


if __name__ == '__main__':
    # 自测
    sample_chunks = [
        "# Markdown 训练论文研究\n\n本文综述了 The Last Fingerprint 等论文...",
        "## Em dash 分析\n\nGPT-4.1 产生 10.62‰ em dash，Llama 全系列为零...",
        "### MDKeyChunker 方法\n\n结构感知分块 + 单次要元数据提取...",
    ]
    
    print("=== 规则提取模式 ===")
    results = enrich_document(sample_chunks, use_llm=False)
    for r in results:
        print(f"\nChunk {r['chunk_index']}:")
        print(f"  title: {r['title']}")
        print(f"  keywords: {r['keywords']}")
        print(f"  semantic_key: {r['semantic_key']}")
    
    print("\n=== Rolling Key 传播 ===")
    propagated = rolling_key_propagation(results)
    for p in propagated:
        print(f"  chunk {p['chunk_index']}: rolling_keys={p.get('rolling_keys', [])}")
