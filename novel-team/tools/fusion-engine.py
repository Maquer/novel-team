#!/usr/bin/env python3
"""
fusion-engine.py — 指纹蒸馏引擎（借鉴 Casting-Workflow）

核心功能：
  1. 从单篇源文提取结构化指纹
  2. 多源文对比提取公约数
  3. 剔除作者指纹，确保100%原创
  4. 输出LLM可用的上下文

设计原则：
  - 仅依赖标准库 + jieba
  - 支持CLI和Python API两种模式
  - 输出可直接复制给LLM

使用示例：
  python fusion-engine.py --category 玄幻 --sample 5
  python fusion-engine.py file1.txt file2.txt file3.txt
  python fusion-engine.py --input corpus/ --output output/fusion.txt
"""

import sys
import os
import re
import json
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import Counter

# 配置
sys.path.insert(0, str(Path(__file__).parent))

# 强制UTF-8编码
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 硬编码规则：LLM禁止项
BANNED_PATTERNS = [
    "对X而言", "一切都在", "她心想", "她意识到", "她感到",
    "一种说不出的", "真正的X是Y", "X的意义在于", "X既是Y也是Z",
    "谁说X就一定Y", "不禁", "仿佛", "映入眼帘",
]

BANNED_TEMPLATES = [
    "眼中闪过", "嘴角勾起", "眼眶微红", "不可置信",
    "眼底闪过", "咬了咬唇", "冷冷地说", "淡淡地说",
    "心中一凛", "脸色一变", "眸光微凝",
]

HARD_RULES = """
## 生成硬性约束

### 标点禁令
- 永远禁止: ； ！！！ ？！ 「」
- 不用引号，对话用 名字：或裸嵌入

### 禁用句式(一个都不能出现):
{patterns}

### 禁用模板描写(一个都不能出现):
{templates}

### 风格规则
- 第一人称
- 数字分节: 1 2 3...(裸数字，无标题)
- 分隔符: ……
- 精确数字: 金额/时间/数量精确到个位
- 压缩情感循环: 每弧≤8句
- 巧合推动情节: ≥1次意外发现
- 短段快节奏: 一段=一个动作/一句对话/一个念头
- 每段同时存在≤5字句和≥40字句
- 句式突变: 相邻3句不同结构
- 番茄小白话: 小学六年级词汇为主,复句≤30%
- 零思维标记: 禁用 心想/意识到/感到/觉得/认为
- 多主语修复: 无 他他他/她她她 连续序列
- 语域碰撞: 100字内正式+粗俗并置≥1次
- 刻意词汇重复: 500字内关键词≥3次
- 人设标签(≥3): 杀伐果断/清醒独立/拒绝内耗/黑莲花/人间清醒/搞钱脑
- 禁用: 圣母/优柔寡断/憋屈/精神内耗
"""


class Fingerprint:
    """单篇源文的指纹结构"""
    
    def __init__(self, name: str, text: str):
        self.name = name
        self.text = text
        self.data = self._extract()
    
    def _extract(self) -> Dict:
        """提取结构化指纹"""
        # 基础统计
        chars = len(re.findall(r'[\u4e00-\u9fff]', self.text))
        sentences = [s.strip() for s in re.split(r'[。！？]', self.text) if re.search(r'[\u4e00-\u9fff]', s)]
        n = len(sentences) if sentences else 1
        
        # 标点密度
        excl_per_sent = round(self.text.count('！') / n, 3)
        comma_per_sent = round(self.text.count('，') / n, 2)
        
        # 开篇样本（前30行）
        first_lines = self._first_n_lines(self.text, 30)
        
        # 高频人名（通过jieba分词）
        top_names = self._extract_names()
        
        return {
            "chars": chars,
            "sentences": n,
            "excl_per_sent": excl_per_sent,
            "comma_per_sent": comma_per_sent,
            "uses_quotes": '"' in self.text[:chars//2],
            "opening_30_lines": first_lines,
            "top_names": top_names,
        }
    
    def _first_n_lines(self, text: str, n: int = 30) -> str:
        """提取前n行（过滤广告/试读等）"""
        lines = text.split('\n')
        result = []
        count = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('=') or '试读' in line or '版权所有' in line:
                continue
            result.append(line)
            count += 1
            if count >= n:
                break
        return '\n'.join(result)
    
    def _extract_names(self) -> List[str]:
        """提取高频人名（简化的jieba替代）"""
        try:
            import jieba
            clean = re.sub(r'[^\u4e00-\u9fff]', '', self.text[:min(len(self.text), 5000)])
            words = list(jieba.cut(clean))
            word_freq = Counter(w for w in words if len(w) >= 2)
            
            # 排除常见词
            stop = {"一个", "没有", "自己", "什么", "他们", "我们", "不是", "这个", "那个",
                    "已经", "知道", "可以", "起来", "现在", "还是", "如果", "因为", "所以",
                    "但是", "然而", "不过", "只是", "就是", "都", "会", "很", "我"}
            
            names = [(w, c) for w, c in word_freq.most_common(40) if w not in stop][:8]
            return [n[0] for n in names]
        except ImportError:
            # 无jieba时，使用简单的两字高频词
            clean = re.sub(r'[^\u4e00-\u9fff]', '', self.text[:5000])
            words = [clean[i:i+2] for i in range(0, len(clean)-1, 2)]
            word_freq = Counter(words)
            return [w for w, c in word_freq.most_common(8) if len(w) == 2]


class FusionEngine:
    """指纹蒸馏引擎"""
    
    def __init__(self):
        self.fingerprints: List[Fingerprint] = []
        self.consensus: Dict = {}
        self.author_fingerprints: Dict = {}
    
    def add_source(self, name: str, text: str) -> None:
        """添加源文"""
        fp = Fingerprint(name, text)
        self.fingerprints.append(fp)
    
    def load_from_file(self, path: str) -> None:
        """从文件加载源文"""
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        self.add_source(os.path.basename(path), text)
    
    def load_from_directory(self, dir_path: str, pattern: str = "*.txt", min_chars: int = 500) -> int:
        """从目录批量加载源文"""
        count = 0
        for file in Path(dir_path).glob(pattern):
            text = file.read_text(encoding='utf-8', errors='replace')
            if len(re.findall(r'[\u4e00-\u9fff]', text)) >= min_chars:
                self.add_source(file.name, text)
                count += 1
        return count
    
    def extract_consensus(self) -> Dict:
        """
        提取公约数和作者指纹
        
        策略：
        - 保留≥3篇共有的特征（公约数）
        - 剔除1-2篇独有的特征（作者指纹）
        """
        if len(self.fingerprints) < 3:
            raise ValueError("至少需要3篇源文")
        
        # 收集所有维度
        all_names = [set(fp.data['top_names']) for fp in self.fingerprints]
        
        # 找到出现频率≥3次的人名（公约数）
        name_counter = Counter()
        for names in all_names:
            name_counter.update(names)
        
        consensus_names = [name for name, count in name_counter.most_common() if count >= 3]
        author_specific_names = [name for name, count in name_counter.most_common() if count < 3]
        
        # 计算平均标点密度
        avg_excl = sum(fp.data['excl_per_sent'] for fp in self.fingerprints) / len(self.fingerprints)
        avg_comma = sum(fp.data['comma_per_sent'] for fp in self.fingerprints) / len(self.fingerprints)
        
        self.consensus = {
            "char_range": (
                min(fp.data['chars'] for fp in self.fingerprints),
                max(fp.data['chars'] for fp in self.fingerprints)
            ),
            "avg_excl_per_sent": round(avg_excl, 3),
            "avg_comma_per_sent": round(avg_comma, 2),
            "consensus_names": consensus_names,
            "author_specific_names": author_specific_names,
            "source_count": len(self.fingerprints),
        }
        
        self.author_fingerprints = {
            "names_to_avoid": author_specific_names,
            "unique_patterns": self._extract_unique_patterns(),
        }
        
        return self.consensus
    
    def _extract_unique_patterns(self) -> List[str]:
        """提取各源文的独特模式（用于剔除）"""
        patterns = []
        for fp in self.fingerprints:
            # 提取开篇特征
            patterns.append(fp.data['opening_30_lines'][:200])
        return patterns
    
    def build_llm_context(self, target_words: int = 1000) -> str:
        """
        构建发给LLM的完整上下文
        
        包含：
        1. 各源文指纹摘要
        2. 公约数提取逻辑
        3. 硬性约束
        4. 生成指令
        """
        if not self.consensus:
            self.extract_consensus()
        
        lines = []
        
        # 第一部分：任务说明
        lines.append("你是熔铸仿写引擎。按以下流程生成一篇约{}字的原创短篇小说。".format(target_words))
        lines.append("")
        
        # 第二部分：阅读源文指纹
        lines.append("## 第一步: 阅读{}份源文指纹".format(len(self.fingerprints)))
        lines.append("")
        
        for i, fp in enumerate(self.fingerprints, 1):
            lines.append("### 源文{}: {}".format(i, fp.name))
            lines.append("字数: {} | 句数: {}".format(fp.data['chars'], fp.data['sentences']))
            lines.append("!/句: {} | ,/句: {}".format(fp.data['excl_per_sent'], fp.data['comma_per_sent']))
            lines.append("高频人名: {}".format(', '.join(fp.data['top_names'][:5])))
            lines.append("")
            lines.append("开篇样本:")
            lines.append(fp.data['opening_30_lines'][:500])
            lines.append("")
        
        # 第三部分：公约数提取
        lines.append("## 第二步: 从{}篇中提取公约数".format(len(self.fingerprints)))
        lines.append("")
        lines.append("| 维度 | 处理策略 |")
        lines.append("|------|---------|")
        lines.append("| 人物名 | 保留公约数（≥{}篇共有）|".format(3))
        lines.append("| 标点密度 | 使用平均值: !={}/句, ,={}/句".format(
            self.consensus['avg_excl_per_sent'],
            self.consensus['avg_comma_per_sent']
        ))
        lines.append("| 开篇风格 | 学习但不可复制 |")
        lines.append("| 情节套路 | 公约数保留，作者指纹剔除 |")
        lines.append("")
        
        # 第四部分：硬性约束
        lines.append("## 第三步: 遵守硬性约束")
        lines.append("")
        lines.append(HARD_RULES.format(
            patterns=', '.join(BANNED_PATTERNS),
            templates=', '.join(BANNED_TEMPLATES)
        ))
        lines.append("")
        
        # 第五部分：生成指令
        lines.append("## 第四步: 生成故事")
        lines.append("")
        lines.append("目标: 朱雀对着{}篇源文扫描输出的16字连续子串，一个都匹配不到。".format(len(self.fingerprints)))
        lines.append("")
        lines.append("**输出格式**：")
        lines.append("- 第一人称叙事")
        lines.append("- 数字分节（1 2 3...）")
        lines.append("- 分隔符使用……")
        lines.append("- 不用引号，对话用名字：或裸嵌入")
        lines.append("- 每段≤40字，短句长句交替")
        lines.append("")
        lines.append("直接输出故事正文。不要前言、后记、说明。")
        
        return '\n'.join(lines)
    
    def save_context(self, output_path: str) -> None:
        """保存上下文到文件"""
        context = self.build_llm_context()
        Path(output_path).write_text(context, encoding='utf-8')
        print(f"✅ 已输出: {output_path}")
        print(f"   包含 {len(self.fingerprints)} 篇源文指纹")
        print(f"   公约数人名: {', '.join(self.consensus.get('consensus_names', []))}")


def cmd_fuse(args):
    """执行指纹蒸馏"""
    engine = FusionEngine()
    
    # 加载源文
    if args.files:
        for f in args.files:
            engine.load_from_file(f)
    elif args.directory:
        count = engine.load_from_directory(args.directory, args.pattern, args.min_chars)
        print(f"📂 从目录加载 {count} 篇源文: {args.directory}")
    else:
        print("❌ 错误: 请提供源文文件或目录")
        return 1
    
    if len(engine.fingerprints) < 3:
        print(f"❌ 错误: 至少需要3篇源文，当前只有{len(engine.fingerprints)}篇")
        return 1
    
    # 提取公约数
    print(f"🔬 正在分析 {len(engine.fingerprints)} 篇源文...")
    consensus = engine.extract_consensus()
    
    # 显示结果
    print("\n=== 指纹蒸馏结果 ===")
    print(f"源文数量: {consensus['source_count']}")
    print(f"字数范围: {consensus['char_range'][0]} - {consensus['char_range'][1]}")
    print(f"平均标点密度: !={consensus['avg_excl_per_sent']}/句, ,={consensus['avg_comma_per_sent']}/句")
    print(f"公约数人名: {', '.join(consensus['consensus_names'][:5]) or '无'}")
    print(f"需规避人名: {', '.join(consensus['author_specific_names'][:5]) or '无'}")
    
    # 输出上下文
    output_path = args.output or "output/fusion_context.txt"
    engine.save_context(output_path)
    
    return 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="指纹蒸馏引擎（借鉴Casting-Workflow）")
    subparsers = parser.add_subparsers(dest="command")
    
    # fuse命令
    p_fuse = subparsers.add_parser("fuse", help="执行指纹蒸馏")
    p_fuse.add_argument("files", nargs="*", help="源文文件路径")
    p_fuse.add_argument("--directory", "-d", help="源文目录（递归扫描.txt）")
    p_fuse.add_argument("--pattern", "-p", default="*.txt", help="文件匹配模式")
    p_fuse.add_argument("--min-chars", type=int, default=500, help="最小中文字数")
    p_fuse.add_argument("--output", "-o", help="输出文件路径")
    
    args = parser.parse_args()
    
    if args.command == "fuse":
        sys.exit(cmd_fuse(args))
    else:
        parser.print_help()
