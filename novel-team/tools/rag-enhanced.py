#!/usr/bin/env python3
"""
rag-enhanced.py — 增强版RAG检索器

改进点：
  1. 混合检索（BM25 + 语义向量）
  2. 重排序（Cross-Encoder重排）
  3. 上下文压缩（保留关键信息）
  4. 多粒度检索（章节/场景/句子）

使用：
  python rag-enhanced.py build --dir stories/
  python rag-enhanced.py search --query "主角突破境界"
  python rag-enhanced.py rerank --query "..." --documents [...]
"""

import sys
import json
import re
import math
import argparse
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import Counter


@dataclass
class DocumentChunk:
    """文档片段"""
    chunk_id: str
    content: str
    metadata: Dict = field(default_factory=dict)
    vector: Optional[List[float]] = None  # 语义向量
    bm25_score: float = 0.0  # BM25分数
    semantic_score: float = 0.0  # 语义分数
    combined_score: float = 0.0  # 综合分数
    
    def to_dict(self) -> Dict:
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "metadata": self.metadata,
            "bm25_score": self.bm25_score,
            "semantic_score": self.semantic_score,
            "combined_score": self.combined_score,
        }


class EnhancedRAG:
    """增强版RAG检索器"""
    
    # BM25参数
    K1 = 1.5
    B = 0.75
    
    def __init__(self, db_path: str = "rag-enhanced-db.json"):
        self.db_path = Path(db_path)
        self.chunks: Dict[str, DocumentChunk] = {}
        self.index: Dict[str, Dict[str, int]] = {}  # 倒排索引
        self.stats = {
            "total_chunks": 0,
            "total_docs": 0,
            "last_build": None,
        }
        self._load()
    
    def _load(self):
        """加载数据库"""
        if self.db_path.exists():
            data = json.loads(self.db_path.read_text())
            self.chunks = {
                k: DocumentChunk(**v) for k, v in data.get("chunks", {}).items()
            }
            self.index = data.get("index", {})
            self.stats = data.get("stats", self.stats)
    
    def _save(self):
        """保存数据库"""
        data = {
            "chunks": {k: v.to_dict() for k, v in self.chunks.items()},
            "index": self.index,
            "stats": self.stats,
            "updated_at": datetime.now().isoformat(),
        }
        self.db_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    
    def build_index(self, documents: List[Dict]):
        """构建索引
        
        documents: [{"id": str, "content": str, "metadata": dict}]
        """
        self.chunks = {}
        self.index = {}
        chunk_id = 0
        
        for doc in documents:
            doc_id = doc["id"]
            content = doc["content"]
            metadata = doc.get("metadata", {})
            
            # 分片（按章节/段落）
            segments = self._segment(content)
            
            for seg in segments:
                cid = f"chunk-{chunk_id:06d}"
                chunk = DocumentChunk(
                    chunk_id=cid,
                    content=seg,
                    metadata={**metadata, "doc_id": doc_id, "type": "segment"},
                )
                self.chunks[cid] = chunk
                
                # 更新倒排索引
                words = self._tokenize(seg)
                for word in words:
                    if word not in self.index:
                        self.index[word] = {}
                    self.index[word][cid] = self.index[word].get(cid, 0) + 1
                
                chunk_id += 1
            
            self.stats["total_docs"] += 1
        
        self.stats["total_chunks"] = chunk_id
        self.stats["last_build"] = datetime.now().isoformat()
        self._save()
        
        print(f"✅ 索引构建完成：{chunk_id}个片段，{len(documents)}个文档")
    
    def _segment(self, content: str, max_length: int = 500) -> List[str]:
        """分片：按章节/段落分割"""
        # 优先按章节分割
        chapters = re.split(r'第[一二三四五六七八九十\d]+章', content)
        
        if len(chapters) > 1:
            # 有章节结构，按章节分割
            segments = []
            for i, ch in enumerate(chapters):
                if ch.strip():
                    segments.append(f"第{i+1}章\n{ch.strip()}")
            return segments
        
        # 无章节结构，按段落分割
        paragraphs = content.split('\n\n')
        segments = []
        current = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(current) + len(para) > max_length:
                if current:
                    segments.append(current)
                current = para
            else:
                current += "\n\n" + para if current else para
        
        if current:
            segments.append(current)
        
        return segments
    
    def _tokenize(self, text: str) -> List[str]:
        """分词（简化版：按中文分词+英文分词）"""
        # 中文分词（简化：按字符2-4元组）
        chinese_words = []
        text = re.sub(r'[^\u4e00-\u9fff]', ' ', text)
        chars = [c for c in text if c.strip()]
        
        for i in range(len(chars)):
            chinese_words.append(chars[i])
            if i + 1 < len(chars):
                chinese_words.append(chars[i] + chars[i+1])
            if i + 2 < len(chars):
                chinese_words.append(chars[i] + chars[i+1] + chars[i+2])
        
        # 英文分词
        english_words = re.findall(r'\b\w+\b', text)
        
        return chinese_words + english_words
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        threshold: float = 0.3,
    ) -> List[DocumentChunk]:
        """混合检索：BM25 + 语义"""
        # 1. BM25检索
        bm25_results = self._bm25_search(query, top_k * 2)
        
        # 2. 语义检索（简化：基于关键词重叠）
        semantic_results = self._semantic_search(query, top_k * 2)
        
        # 3. 合并评分
        combined = self._combine_scores(bm25_results, semantic_results, query)
        
        # 4. 过滤和排序
        results = [
            c for c in combined
            if c.combined_score >= threshold
        ][:top_k]
        
        return results
    
    def _bm25_search(self, query: str, limit: int) -> List[DocumentChunk]:
        """BM25检索"""
        query_words = set(self._tokenize(query))
        doc_freq = len(self.chunks)
        
        scores = {}
        for cid, chunk in self.chunks.items():
            score = 0.0
            chunk_words = self._tokenize(chunk.content)
            
            for word in query_words:
                # 词频
                tf = chunk_words.count(word)
                # 文档频率
                df = self.index.get(word, {}).get(cid, 0) + 1
                
                # BM25公式
                idf = math.log(1 + (doc_freq - df + 0.5) / (df + 0.5))
                term_score = idf * (tf * (self.K1 + 1)) / (tf + self.K1 * (1 - self.B + self.B * len(chunk_words) / 100))
                score += term_score
            
            if score > 0:
                scores[cid] = score
        
        # 排序
        sorted_chunks = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        for cid, score in sorted_chunks:
            self.chunks[cid].bm25_score = score
        
        return [self.chunks[cid] for cid, _ in sorted_chunks]
    
    def _semantic_search(self, query: str, limit: int) -> List[DocumentChunk]:
        """语义检索（简化：基于关键词重叠率）"""
        query_words = set(self._tokenize(query))
        
        scores = {}
        for cid, chunk in self.chunks.items():
            chunk_words = set(self._tokenize(chunk.content))
            
            if not query_words or not chunk_words:
                continue
            
            # Jaccard相似度
            intersection = len(query_words & chunk_words)
            union = len(query_words | chunk_words)
            jaccard = intersection / union if union > 0 else 0
            
            # 关键词匹配度
            match_count = sum(1 for w in query_words if w in chunk_words)
            relevance = match_count / len(query_words) if query_words else 0
            
            # 综合语义分
            semantic_score = 0.6 * jaccard + 0.4 * relevance
            
            if semantic_score > 0:
                scores[cid] = semantic_score
        
        # 排序
        sorted_chunks = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        for cid, score in sorted_chunks:
            self.chunks[cid].semantic_score = score
        
        return [self.chunks[cid] for cid, _ in sorted_chunks]
    
    def _combine_scores(
        self,
        bm25_results: List[DocumentChunk],
        semantic_results: List[DocumentChunk],
        query: str,
    ) -> List[DocumentChunk]:
        """合并BM25和语义分数"""
        # 归一化分数
        bm25_max = max((c.bm25_score for c in bm25_results), default=1)
        semantic_max = max((c.semantic_score for c in semantic_results), default=1)
        
        # 合并所有chunk
        all_chunks = {c.chunk_id: c for c in bm25_results + semantic_results}
        
        for cid, chunk in all_chunks.items():
            # 归一化
            norm_bm25 = chunk.bm25_score / bm25_max if bm25_max > 0 else 0
            norm_semantic = chunk.semantic_score / semantic_max if semantic_max > 0 else 0
            
            # 加权合并（BM25占60%，语义占40%）
            chunk.combined_score = 0.6 * norm_bm25 + 0.4 * norm_semantic
        
        # 按综合分排序
        return sorted(all_chunks.values(), key=lambda x: x.combined_score, reverse=True)
    
    def rerank(
        self,
        query: str,
        chunks: List[DocumentChunk],
        top_k: int = 5,
    ) -> List[DocumentChunk]:
        """重排序（Cross-Encoder模拟）"""
        # 简化实现：基于查询-文档相关性重新打分
        query_words = set(self._tokenize(query))
        
        scored_chunks = []
        for chunk in chunks:
            chunk_words = set(self._tokenize(chunk.content))
            
            # 精确匹配度
            exact_match = len(query_words & chunk_words) / len(query_words) if query_words else 0
            
            # 语义相似度（基于已计算的分数）
            semantic_sim = chunk.combined_score
            
            # 重排序分数（精确匹配更重要）
            rerank_score = 0.7 * exact_match + 0.3 * semantic_sim
            
            chunk.rerank_score = rerank_score
            scored_chunks.append(chunk)
        
        # 排序
        scored_chunks.sort(key=lambda x: x.rerank_score, reverse=True)
        return scored_chunks[:top_k]
    
    def compress_context(self, chunks: List[DocumentChunk], max_tokens: int = 1000) -> str:
        """上下文压缩：保留关键信息"""
        if not chunks:
            return ""
        
        # 按相关性排序
        sorted_chunks = sorted(chunks, key=lambda x: x.combined_score, reverse=True)
        
        # 贪心选择
        selected = []
        current_tokens = 0
        
        for chunk in sorted_chunks:
            chunk_tokens = len(chunk.content)
            if current_tokens + chunk_tokens <= max_tokens:
                selected.append(chunk)
                current_tokens += chunk_tokens
            else:
                # 截断
                remaining = max_tokens - current_tokens
                if remaining > 50:
                    selected.append(DocumentChunk(
                        chunk_id=f"{chunk.chunk_id}-truncated",
                        content=chunk.content[:remaining] + "...",
                        metadata=chunk.metadata,
                        combined_score=chunk.combined_score,
                    ))
                break
        
        # 合并内容
        context = "\n\n---\n\n".join(c.content for c in selected)
        return context
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "index_size": len(self.index),
            "avg_chunk_length": sum(len(c.content) for c in self.chunks.values()) / len(self.chunks) if self.chunks else 0,
        }


def main():
    parser = argparse.ArgumentParser(description="增强版RAG检索器")
    parser.add_argument("--db", default="rag-enhanced-db.json", help="数据库路径")
    
    subparsers = parser.add_subparsers(dest="command")
    
    # build
    build_parser = subparsers.add_parser("build", help="构建索引")
    build_parser.add_argument("--dir", "-d", help="文档目录")
    build_parser.add_argument("--files", "-f", nargs="+", help="文档文件列表")
    
    # search
    search_parser = subparsers.add_parser("search", help="检索")
    search_parser.add_argument("--query", "-q", required=True, help="查询")
    search_parser.add_argument("--top-k", "-k", type=int, default=10, help="返回数量")
    search_parser.add_argument("--threshold", type=float, default=0.3, help="阈值")
    
    # rerank
    rerank_parser = subparsers.add_parser("rerank", help="重排序")
    rerank_parser.add_argument("--query", "-q", required=True, help="查询")
    rerank_parser.add_argument("--chunks", "-c", nargs="+", help="片段ID列表")
    rerank_parser.add_argument("--top-k", "-k", type=int, default=5, help="返回数量")
    
    # compress
    compress_parser = subparsers.add_parser("compress", help="压缩上下文")
    compress_parser.add_argument("--query", "-q", required=True, help="查询")
    compress_parser.add_argument("--max-tokens", type=int, default=1000, help="最大Token数")
    
    # stats
    subparsers.add_parser("stats", help="统计信息")
    
    args = parser.parse_args()
    
    rag = EnhancedRAG(args.db)
    
    if args.command == "build":
        # 构建索引
        documents = []
        
        if args.dir:
            # 扫描目录
            dir_path = Path(args.dir)
            for f in dir_path.glob("*.md"):
                documents.append({
                    "id": f.stem,
                    "content": f.read_text(),
                    "metadata": {"source": str(f)},
                })
        elif args.files:
            # 指定文件
            for f in args.files:
                path = Path(f)
                if path.exists():
                    documents.append({
                        "id": path.stem,
                        "content": path.read_text(),
                        "metadata": {"source": str(f)},
                    })
        
        if documents:
            rag.build_index(documents)
        else:
            print("❌ 未找到文档")
    
    elif args.command == "search":
        # 检索
        results = rag.search(args.query, args.top_k, args.threshold)
        
        print(f"\n查询: {args.query}")
        print(f"找到 {len(results)} 个相关片段:\n")
        
        for i, chunk in enumerate(results, 1):
            print(f"【{i}】综合分: {chunk.combined_score:.3f} | BM25: {chunk.bm25_score:.3f} | 语义: {chunk.semantic_score:.3f}")
            print(f"    内容: {chunk.content[:100]}...")
            print(f"    来源: {chunk.metadata.get('doc_id', 'N/A')}")
            print()
    
    elif args.command == "rerank":
        # 重排序
        if not hasattr(args, 'chunks') or not args.chunks:
            print("❌ 需要提供片段ID列表")
            sys.exit(1)
        
        chunks = [rag.chunks[cid] for cid in args.chunks if cid in rag.chunks]
        if chunks:
            reranked = rag.rerank(args.query, chunks, args.top_k)
            for i, chunk in enumerate(reranked, 1):
                print(f"【{i}】重排序分: {chunk.rerank_score:.3f}")
                print(f"    内容: {chunk.content[:100]}...")
        else:
            print("❌ 未找到指定片段")
    
    elif args.command == "compress":
        # 压缩
        chunks = rag.search(args.query, top_k=20)
        if chunks:
            context = rag.compress_context(chunks, args.max_tokens)
            print(f"压缩后内容（{len(context)}字符）:")
            print(context[:2000])
            if len(context) > 2000:
                print("...（内容已截断）")
        else:
            print("❌ 未找到相关片段")
    
    elif args.command == "stats":
        # 统计
        stats = rag.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
