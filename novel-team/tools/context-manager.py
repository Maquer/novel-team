#!/usr/bin/env python3
"""
上下文管理器 — 借鉴 Long-Novel-GPT 的上下文注入机制

功能：
  1. 多轮对话注入（用于Prompt Caching）
  2. 上下文切分与重组
  3. 上下文长度控制
  4. 上下文缓存管理

设计原则：
  - 低上下文策略：写前默认只读必要文件
  - Prompt Caching：多轮注入，固定部分复用
  - 智能切分：超长内容自动分段
  - 长度控制：避免超出模型token限制
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 代际项目守卫（唯一路径入口）
sys.path.insert(0, str(Path(__file__).parent))
from project_guard import resolve

# 配置
LEDGER_DIR = Path("/var/minis/shared/novel-team/ledger")
CONTEXT_DIR = LEDGER_DIR / "contexts"
CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

# 默认配置
MAX_CONTEXT_LENGTH = 4000  # 最大上下文长度（字符）
MAX_CHUNK_SIZE = 2000      # 单chunk大小
CACHING_THRESHOLD = 1000   # 超过此长度启用caching模式

# 记忆压缩配置（v0.45.0新增）
COMPRESSION_ENABLED = True
COMPRESSION_LEVELS = {
    "critical": {"keep": True, "description": "关键信息：角色名、境界、地点"},
    "important": {"keep": True, "compress_ratio": 0.7, "description": "重要信息：剧情要点、伏笔"},
    "normal": {"keep": False, "compress_ratio": 0.3, "description": "一般信息：环境描写、对话细节"},
    "noise": {"keep": False, "compress_ratio": 0.0, "description": "噪声：重复描述、冗余修饰"}
}

# 有界完成配置
BOUNDED_COMPLETION = {
    "enabled": True,
    "word_range": {"min_ratio": 0.9, "max_ratio": 1.1},  # 目标字数±10%
    "timeout_seconds": 300,  # 5分钟超时
    "truncate_strategy": "nearest_sentence_boundary"  # 在句子边界截断
}


class ContextManager:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.project_dir = resolve(project_id).root_dir
        self.context_file = CONTEXT_DIR / f"{project_id}.json"
    
    def load_context(self) -> Dict:
        """加载上下文数据"""
        if not self.context_file.exists():
            return {
                "project_id": self.project_id,
                "summary": "",
                "world_setting": "",
                "character_setting": "",
                "chapters": {},
                "last_updated": None
            }
        return json.loads(self.context_file.read_text(encoding='utf-8'))
    
    def save_context(self, data: Dict) -> None:
        """保存上下文数据"""
        data["last_updated"] = self._now_iso()
        tmp = self.context_file.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.context_file)
    
    def _now_iso(self) -> str:
        from datetime import datetime, timezone, timedelta
        tz = timezone(timedelta(hours=8))
        return datetime.now(tz).isoformat()
    
    def build_context_prompt(self, chapter_no: int, mode: str = "draft") -> str:
        """
        构建上下文Prompt（RTCO框架：只取相关，不取全部）
        
        RTCO = Relevant Text + Character Options
        
        Args:
            chapter_no: 章节号
            mode: 创作模式（draft/expand/polish）
        """
        ctx = self.load_context()
        
        # 基础注入（固定，用于Caching）
        lines = []
        
        # 第1轮：小说简介
        if ctx.get("summary"):
            lines.append("user:")
            lines.append("下面是**小说简介**。")
            lines.append("")
            lines.append("**小说简介**")
            lines.append(ctx["summary"])
            lines.append("")
            lines.append("assistant:")
            lines.append("收到，我会参考小说简介进行创作。")
            lines.append("")
        
        # 第2轮：核心设定
        if ctx.get("world_setting"):
            lines.append("user:")
            lines.append("下面是**核心设定**。")
            lines.append("")
            lines.append("**核心设定**")
            lines.append(ctx["world_setting"])
            lines.append("")
            lines.append("assistant:")
            lines.append("收到，我会参考核心设定进行创作。")
            lines.append("")
        
        # 第3轮：主角设定
        if ctx.get("character_setting"):
            lines.append("user:")
            lines.append("下面是**主角设定**。")
            lines.append("")
            lines.append("**主角设定**")
            lines.append(ctx["character_setting"])
            lines.append("")
            lines.append("assistant:")
            lines.append("收到，我会参考主角设定进行创作。")
            lines.append("")
        
        # 第4轮：RTCO框架 - 只取相关的
        # 4.1 前章结尾（最近500字）
        prev_chapter = self._get_chapter(chapter_no - 1, ctx)
        if prev_chapter:
            lines.append("user:")
            lines.append("下面是**上一章结尾**（仅参考最后部分）。")
            lines.append("")
            lines.append("**前章结尾**")
            lines.append(prev_chapter[-500:] if len(prev_chapter) > 500 else prev_chapter)
            lines.append("")
            lines.append("assistant:")
            lines.append("收到，我会承接上文。")
            lines.append("")
        
        # 4.2 后章大纲（如有）
        next_chapter = self._get_chapter(chapter_no + 1, ctx)
        if next_chapter:
            lines.append("user:")
            lines.append("下面是**下一章大纲**（仅供参考方向）。")
            lines.append("")
            lines.append("**后章大纲**")
            lines.append(next_chapter[:300] + "..." if len(next_chapter) > 300 else next_chapter)
            lines.append("")
            lines.append("assistant:")
            lines.append("收到，我会注意不要提前泄露。")
            lines.append("")
        
        # 4.3 角色状态（只取当前章节相关的）
        characters = ctx.get("characters", [])
        if characters:
            lines.append("user:")
            lines.append("下面是**当前活跃角色**（仅取本章出场人物）。")
            lines.append("")
            lines.append("**角色状态**")
            for char in characters[:5]:  # 只取前5个
                lines.append(f"- {char.get('name', '')}: {char.get('status', '')}")
            lines.append("")
            lines.append("assistant:")
            lines.append("收到，我会只写出场角色的行动。")
            lines.append("")
        
        # 4.4 伏笔检查（只取未回收的）
        foreshadows = ctx.get("foreshadows", [])
        active_foreshadows = [f for f in foreshadows if f.get("category") == "planted"]
        if active_foreshadows:
            lines.append("user:")
            lines.append("下面是**未回收伏笔**（需要在本章或近期回收）。")
            lines.append("")
            lines.append("**待回收伏笔**")
            for f in active_foreshadows[:3]:  # 只取前3个
                lines.append(f"- [{f.get('chapter_id', '')}] {f.get('content', '')[:30]}...")
            lines.append("")
            lines.append("assistant:")
            lines.append("收到，我会注意伏笔回收。")
            lines.append("")
        
        # 第5轮：本章指令
        lines.append("user:")
        lines.append(f"下面是**第{chapter_no}章**的创作指令。")
        lines.append("")
        
        if mode == "draft":
            lines.append("**任务**：创作本章初稿")
            lines.append("**要求**：")
            lines.append("- 字数：300-500字")
            lines.append("- 开篇钩子")
            lines.append("- 结尾悬念")
            lines.append("- 无AI味")
            lines.append("- 只写出场角色")
            lines.append("- 注意伏笔回收")
        elif mode == "expand":
            lines.append("**任务**：扩写本章")
            lines.append("**要求**：")
            lines.append("- 保持原有情节")
            lines.append("- 增加细节描写")
            lines.append("- 字数：1000-1500字")
        elif mode == "polish":
            lines.append("**任务**：精修本章")
            lines.append("**要求**：")
            lines.append("- 清除AI模式")
            lines.append("- 两遍式润色")
            lines.append("- 字数：2000-3000字")
        
        lines.append("")
        lines.append("assistant:")
        lines.append(f"收到，开始创作第{chapter_no}章...")
        
        return "\n".join(lines)
    
    def _get_chapter(self, chapter_no: int, ctx: Dict) -> str:
        """获取指定章节内容"""
        chapters = ctx.get("chapters", {})
        return chapters.get(str(chapter_no), "")
    
    def split_context(self, text: str, max_length: int = MAX_CHUNK_SIZE) -> List[str]:
        """
        切分上下文为多个chunk
        
        Args:
            text: 原文
            max_length: 单chunk最大长度
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        current = ""
        current_len = 0
        
        for char in text:
            current += char
            current_len += 1
            
            if current_len >= max_length:
                # 尝试在句子边界切分
                last_period = current.rfind('。')
                if last_period > max_length * 0.8:
                    chunks.append(current[:last_period + 1])
                    current = current[last_period + 1:]
                    current_len = len(current)
                else:
                    chunks.append(current)
                    current = ""
                    current_len = 0
        
        if current:
            chunks.append(current)
        
        return chunks
    
    def calculate_token_estimate(self, text: str) -> int:
        """估算token数量（简化版：中文字符×1.5）"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.5)
    
    def apply_bounded_completion(self, text: str, target_words: int) -> Tuple[str, bool]:
        """
        应用有界完成机制
        
        Args:
            text: 原始文本
            target_words: 目标字数
        
        Returns:
            (截断后文本, 是否被截断)
        """
        if not BOUNDED_COMPLETION["enabled"]:
            return text, False
        
        current_words = len(re.sub(r'\s+', '', text))
        min_words = int(target_words * BOUNDED_COMPLETION["word_range"]["min_ratio"])
        max_words = int(target_words * BOUNDED_COMPLETION["word_range"]["max_ratio"])
        
        # 检查是否在范围内
        if min_words <= current_words <= max_words:
            return text, False
        
        # 需要截断
        if current_words > max_words:
            # 找到最近的句子边界
            strategy = BOUNDED_COMPLETION["truncate_strategy"]
            if strategy == "nearest_sentence_boundary":
                # 在第max_words个字符附近找句号
                cutoff = max_words
                while cutoff < len(text) and text[cutoff] not in '。！？':
                    cutoff += 1
                if cutoff >= len(text):
                    cutoff = max_words
                return text[:cutoff+1], True
            else:
                return text[:max_words], True
        
        # 字数不足，标记但不过截
        return text, False
    
    def get_context_status(self) -> Dict:
        """获取上下文状态"""
        ctx = self.load_context()
        
        total_length = len(ctx.get("summary", ""))
        total_length += len(ctx.get("world_setting", ""))
        total_length += len(ctx.get("character_setting", ""))
        
        chapters = ctx.get("chapters", {})
        chapter_count = len(chapters)
        
        total_words = sum(len(c) for c in chapters.values())
        
        return {
            "project_id": self.project_id,
            "summary_length": len(ctx.get("summary", "")),
            "world_setting_length": len(ctx.get("world_setting", "")),
            "character_setting_length": len(ctx.get("character_setting", "")),
            "chapter_count": chapter_count,
            "total_words": total_words,
            "estimated_tokens": self.calculate_token_estimate(
                ctx.get("summary", "") + 
                ctx.get("world_setting", "") + 
                ctx.get("character_setting", "")
            ),
            "last_updated": ctx.get("last_updated")
        }


def cmd_build(args):
    """构建上下文"""
    manager = ContextManager(args.project_id)
    
    # 检查项目目录
    project_dir = manager.project_dir
    if not project_dir.exists():
        # 契约：stderr 输出 ERROR: 前缀（TEAM.md 工具契约规范）。修前用 ❌ 无前缀，机器不可判定。
        import sys as _sys
        print(f"ERROR: 项目目录不存在: {project_dir}", file=_sys.stderr)
        return 1
    
    # 加载项目文件
    ctx = manager.load_context()
    
    # 读取小说简介
    idea_file = project_dir / "idea_seed.md"
    if idea_file.exists():
        ctx["summary"] = idea_file.read_text(encoding='utf-8')[:2000]
    
    # 读取世界观
    world_file = project_dir / "worldbuilding.md"
    if world_file.exists():
        ctx["world_setting"] = world_file.read_text(encoding='utf-8')[:3000]
    
    # 读取角色设定
    char_file = project_dir / "characters.md"
    if char_file.exists():
        ctx["character_setting"] = char_file.read_text(encoding='utf-8')[:2000]
    
    # 读取已创作章节
    chapters_dir = project_dir / "chapters"
    if chapters_dir.exists():
        for chapter_file in sorted(chapters_dir.glob("*.md")):
            chapter_no = int(re.search(r'(\d+)', chapter_file.stem).group(1))
            ctx["chapters"][str(chapter_no)] = chapter_file.read_text(encoding='utf-8')
    
    manager.save_context(ctx)
    
    print(f"✅ 上下文已构建")
    status = manager.get_context_status()
    print(f"   简介: {status['summary_length']}字符")
    print(f"   世界观: {status['world_setting_length']}字符")
    print(f"   角色设定: {status['character_setting_length']}字符")
    print(f"   章节数: {status['chapter_count']}")
    print(f"   总字数: {status['total_words']:,}")


def cmd_generate(args):
    """生成上下文Prompt"""
    manager = ContextManager(args.project_id)
    
    prompt = manager.build_context_prompt(args.chapter, args.mode)
    
    if args.output:
        Path(args.output).write_text(prompt, encoding='utf-8')
        print(f"✅ Prompt已保存到: {args.output}")
    else:
        print(prompt)


def cmd_status(args):
    """查看上下文状态"""
    manager = ContextManager(args.project_id)
    status = manager.get_context_status()
    
    print("\n📊 上下文状态")
    print("=" * 60)
    print(f"项目ID: {status['project_id']}")
    print(f"简介长度: {status['summary_length']:,} 字符")
    print(f"世界观长度: {status['world_setting_length']:,} 字符")
    print(f"角色设定长度: {status['character_setting_length']:,} 字符")
    print(f"章节数量: {status['chapter_count']} 章")
    print(f"总字数: {status['total_words']:,} 字")
    print(f"估算Token: {status['estimated_tokens']:,}")
    print(f"最后更新: {status['last_updated'] or '从未'}")
    print("=" * 60)


def cmd_estimate(args):
    """估算创作成本"""
    manager = ContextManager(args.project_id)
    status = manager.get_context_status()
    
    # 估算各阶段Token
    base_tokens = status['estimated_tokens']
    
    # 假设每章平均字数
    avg_words_per_chapter = status['total_words'] / max(status['chapter_count'], 1)
    
    # 阶段1: 大纲创作（假设50章）
    outline_chapters = 50
    outline_tokens = int(outline_chapters * avg_words_per_chapter * 0.3 * 1.5)
    
    # 阶段2: 章节创作（当前已完成）
    chapter_tokens = int(status['total_words'] * 1.5)
    
    # 阶段3: 扩写（假设扩展到1.5k字/章）
    expand_target = 1500
    expand_tokens = int(outline_chapters * (expand_target - avg_words_per_chapter) * 1.5)
    
    # 阶段4: 精修
    polish_tokens = int(outline_chapters * 2000 * 1.5)
    
    total_tokens = outline_tokens + chapter_tokens + expand_tokens + polish_tokens
    
    # 估算费用（按GPT-4价格）
    cost_per_1k = 0.03  # $
    estimated_cost = total_tokens / 1000 * cost_per_1k
    
    print("\n💰 创作成本估算")
    print("=" * 60)
    print(f"大纲创作: {outline_tokens:,} tokens (~${outline_tokens/1000*cost_per_1k:.2f})")
    print(f"章节创作: {chapter_tokens:,} tokens (~${chapter_tokens/1000*cost_per_1k:.2f})")
    print(f"剧情扩写: {expand_tokens:,} tokens (~${expand_tokens/1000*cost_per_1k:.2f})")
    print(f"正文精修: {polish_tokens:,} tokens (~${polish_tokens/1000*cost_per_1k:.2f})")
    print("-" * 60)
    print(f"总计: {total_tokens:,} tokens (~${estimated_cost:.2f})")
    print("=" * 60)


def cmd_bounded_check(args):
    """检查有界完成配置"""
    print("\n📐 有界完成配置")
    print("=" * 60)
    print(f"启用状态: {'✅ 已启用' if BOUNDED_COMPLETION['enabled'] else '❌ 已禁用'}")
    print(f"字数范围: ±{(1-BOUNDED_COMPLETION['word_range']['min_ratio'])*100:.0f}% ~ ±{(BOUNDED_COMPLETION['word_range']['max_ratio']-1)*100:.0f}%")
    print(f"超时限制: {BOUNDED_COMPLETION['timeout_seconds']}秒")
    print(f"截断策略: {BOUNDED_COMPLETION['truncate_strategy']}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="上下文管理器（借鉴Long-Novel-GPT）")
    subparsers = parser.add_subparsers(dest="command")
    
    # build
    p_build = subparsers.add_parser("build", help="构建上下文")
    p_build.add_argument("--project-id", required=True)
    
    # generate
    p_gen = subparsers.add_parser("generate", help="生成上下文Prompt")
    p_gen.add_argument("--project-id", required=True)
    p_gen.add_argument("--chapter", type=int, required=True)
    p_gen.add_argument("--mode", choices=["draft", "expand", "polish"], default="draft")
    p_gen.add_argument("--output", help="输出文件路径")
    
    # status
    p_status = subparsers.add_parser("status", help="查看上下文状态")
    p_status.add_argument("--project-id", required=True)
    
    # estimate
    p_est = subparsers.add_parser("estimate", help="估算创作成本")
    p_est.add_argument("--project-id", required=True)
    
    # bounded-check
    subparsers.add_parser("bounded-check", help="检查有界完成配置")
    
    args = parser.parse_args()

    # 契约（TEAM.md 工具契约规范）：失败 → exit 1。
    # 修前缺陷：cmd_build 的 return 1 被调用处丢弃，错误静默，调用方 exit 0。
    rc = 0
    if args.command == "build":
        rc = cmd_build(args) or 0
    elif args.command == "generate":
        rc = cmd_generate(args) or 0
    elif args.command == "status":
        rc = cmd_status(args) or 0
    elif args.command == "estimate":
        rc = cmd_estimate(args) or 0
    elif args.command == "bounded-check":
        rc = cmd_bounded_check(args) or 0
    else:
        parser.print_help()
        rc = 1
    if rc:
        import sys
        sys.exit(rc)
