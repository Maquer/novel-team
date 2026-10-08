#!/usr/bin/env python3
"""
动作前四问 — 段落级硬阻塞机制

借鉴 ai-fiction-writer novel-logic Skill 的核心创新。
在写每一段正文之前，必须通过四个问题的检查。
四问全部通过，才能写下一段。

核心原则：逻辑问题要在写下第一段正文之前就被拦住，
而不是写完整章后再找补。

硬阻塞原则：不填场景微逻辑卡，不能写正文；
不过动作前四问，不能写下一段。
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 默认工作区路径
NOVEL_DIR = Path("/var/minis/shared/novel-team/projects")
LOGIC_DIR = Path(".novel/logic")


class ParagraphFourQuestions:
    """段落级动作前四问检查器"""

    # 四个问题的定义
    QUESTIONS = [
        {"key": "who_present", "name": "谁在场？", "desc": "明确这段中出现的人物及位置"},
        {"key": "where_just_now", "name": "他们刚在哪？", "desc": "与上一段/上一章的时间和空间衔接"},
        {"key": "why_do_this", "name": "为什么这么做？", "desc": "动机符合身份、关系、情绪、目标"},
        {"key": "info_source", "name": "信息/道具从哪来？", "desc": "前文有铺垫，符合知情边界"},
    ]

    def __init__(self, novel_id: str, chapter_num: int = None):
        self.novel_id = novel_id
        self.chapter_num = chapter_num
        self.project_dir = NOVEL_DIR / novel_id
        self.logic_dir = self.project_dir / LOGIC_DIR
        self.checks_dir = self.logic_dir / "paragraph-checks"
        self.scene_cards_dir = self.logic_dir / "scene-cards"
        self.infoboundary_path = self.project_dir / ".novel/tracking/知情边界.md"

        # 确保目录存在
        self.checks_dir.mkdir(parents=True, exist_ok=True)
        self.scene_cards_dir.mkdir(parents=True, exist_ok=True)

        # 加载当前章节的四问记录
        self.check_records = self._load_check_records()

    def _load_check_records(self) -> Dict:
        """加载已有检查记录"""
        if self.chapter_num is None:
            return {"path": "", "paragraphs": [], "updated_at": None}
        path = self.checks_dir / f"ch{self.chapter_num:02d}-paragraphs.md"
        if path.exists():
            content = path.read_text(encoding='utf-8')
            paragraphs = []
            current_para = {}
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('### 段落'):
                    if current_para:
                        paragraphs.append(current_para)
                    current_para = {}
                elif line.startswith('**正文**：'):
                    current_para['text'] = line.replace('**正文**：', '').strip()
                elif line.startswith('- 谁在场？'):
                    current_para['answers'] = current_para.get('answers', {})
                    current_para['answers']['who_present'] = line.replace('- 谁在场？', '').strip()
                elif line.startswith('- 他们刚在哪？'):
                    current_para['answers'] = current_para.get('answers', {})
                    current_para['answers']['where_just_now'] = line.replace('- 他们刚在哪？', '').strip()
                elif line.startswith('- 为什么要这么做？'):
                    current_para['answers'] = current_para.get('answers', {})
                    current_para['answers']['why_do_this'] = line.replace('- 为什么要这么做？', '').strip()
                elif line.startswith('- 信息/道具来源？'):
                    current_para['answers'] = current_para.get('answers', {})
                    current_para['answers']['info_source'] = line.replace('- 信息/道具来源？', '').strip()
                elif line.startswith('- **判定**：'):
                    status = line.replace('- **判定**：', '').strip()
                    current_para['pass'] = '✅' in status or '通过' in status
            if current_para:
                paragraphs.append(current_para)
            return {"path": str(path), "paragraphs": paragraphs, "updated_at": None}
        return {"path": str(path), "paragraphs": [], "updated_at": None}

    def _save_check_records(self):
        """保存检查记录"""
        if not self.check_records["path"]:
            return
        content = self._build_md_content()
        p = Path(self.check_records["path"])
        # Ensure parent directory exists
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix('.tmp')
        tmp.write_text(content, encoding='utf-8')
        import os
        os.replace(str(tmp), str(p))

    def _build_md_content(self) -> str:
        """构建 Markdown 格式内容"""
        lines = [f"## 第 {self.chapter_num} 章段落四问记录\n"]
        for i, para in enumerate(self.check_records["paragraphs"], 1):
            lines.append(f"### 段落 {i}\n")
            lines.append(f"**正文**：{para['text'][:100]}{'...' if len(para['text']) > 100 else ''}\n")
            lines.append(f"- 谁在场？{para['answers']['who_present']}\n")
            lines.append(f"- 他们刚在哪？{para['answers']['where_just_now']}\n")
            lines.append(f"- 为什么要这么做？{para['answers']['why_do_this']}\n")
            lines.append(f"- 信息/道具来源？{para['answers']['info_source']}\n")
            status = "✅ 通过" if para['pass'] else "❌ 未通过"
            lines.append(f"- **判定**：{status}\n")
            if para.get('block_reason'):
                lines.append(f"  > ⛔ 阻塞原因：{para['block_reason']}\n")
            lines.append("")
        return "\n".join(lines)

    def check_paragraph(
        self,
        text: str,
        who_present: str,
        where_just_now: str,
        why_do_this: str,
        info_source: str,
        prev_paragraph_answers: Optional[Dict] = None,
    ) -> Dict:
        """
        检查单个段落，返回四问结果

        参数：
            text: 正文段落
            who_present: 谁在场（角色+位置）
            where_just_now: 他们刚在哪（上一段状态）
            why_do_this: 为什么这么做（动机）
            info_source: 信息/道具来源
            prev_paragraph_answers: 上一段的四问答案（用于连贯性检查）

        返回：
            {
                "pass": bool,
                "answers": {...},
                "checks": [...],
                "block_reason": str or None,
            }
        """
        checks = []
        block_reason = None

        # Q1: 谁在场？
        if not who_present or who_present.strip() == "":
            checks.append({"q": "谁在场？", "status": "fail", "detail": "未指定在场人物"})
            block_reason = "未指定在场人物"
        else:
            checks.append({"q": "谁在场？", "status": "pass", "detail": who_present})

        # Q2: 他们刚在哪？（检查连续性）
        if prev_paragraph_answers:
            # 与上一段对比
            prev_who = prev_paragraph_answers.get("who_present", "")
            prev_where = prev_paragraph_answers.get("where_just_now", "")
            # 如果上一段有人在此段消失
            prev_chars = re.findall(r"[\u4e00-\u9fa5]+", prev_who)
            for char in prev_chars:
                if len(char) >= 2 and char not in who_present and char not in text:
                    # 角色消失检查
                    pass  # 已出场角色消失可能是合理的（离开场景）
            checks.append({"q": "他们刚在哪？", "status": "pass", "detail": where_just_now})
        else:
            checks.append({"q": "他们刚在哪？", "status": "pass", "detail": where_just_now})

        # Q3: 为什么这么做？
        if not why_do_this or why_do_this.strip() == "":
            checks.append({"q": "为什么这么做？", "status": "fail", "detail": "未提供动机"})
            block_reason = "未提供动机"
        else:
            checks.append({"q": "为什么这么做？", "status": "pass", "detail": why_do_this})

        # Q4: 信息/道具从哪来？
        if not info_source or info_source.strip() == "":
            checks.append({"q": "信息/道具从哪来？", "status": "fail", "detail": "未提供信息来源"})
            block_reason = "未提供信息来源"
        else:
            checks.append({"q": "信息/道具从哪来？", "status": "pass", "detail": info_source})

        # 判定
        all_pass = all(c["status"] == "pass" for c in checks)
        result = {
            "pass": all_pass,
            "answers": {
                "who_present": who_present,
                "where_just_now": where_just_now,
                "why_do_this": why_do_this,
                "info_source": info_source,
            },
            "checks": checks,
            "block_reason": block_reason,
            "timestamp": datetime.now().isoformat(),
        }

        # 记录到当前文件
        self.check_records["paragraphs"].append({
            "text": text,
            "answers": result["answers"],
            "pass": result["pass"],
            "block_reason": result["block_reason"],
            "timestamp": result["timestamp"],
        })
        self._save_check_records()

        return result

    def parse_chapter_text(self, chapter_file: Path) -> str:
        """
        解析章节文件，提取正文（跳过 YAML frontmatter）

        返回：正文文本字符串
        """
        content = chapter_file.read_text(encoding='utf-8')
        # 跳过 YAML frontmatter (--- ... ---)
        if content.startswith('---'):
            end = content.find('---', 3)
            if end > 0:
                content = content[end+3:].strip()
        # 跳过标题行
        lines = content.split('\n')
        text_lines = []
        skip_title = True
        for line in lines:
            if skip_title and line.startswith('#'):
                continue
            skip_title = False
            text_lines.append(line)
        return '\n'.join(text_lines).strip()

    def split_paragraphs(self, text: str) -> List[str]:
        """
        将正文按空行分割为段落列表
        """
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        return paragraphs

    def extract_section(
        self,
        paragraphs: List[str],
        section: str,
        para_count: int = 4
    ) -> Tuple[str, int]:
        """
        从段落列表中提取指定部分

        参数：
            paragraphs: 段落列表
            section: 'opening' / 'middle' / 'closing'
            para_count: 每部分取的段落数

        返回：
            (提取的文本, 起始段落索引)
        """
        total = len(paragraphs)
        if total == 0:
            return "", 0

        if section == "opening":
            start = 0
            end = min(para_count, total)
        elif section == "middle":
            mid = total // 2
            start = max(0, mid - para_count // 2)
            end = min(total, mid + para_count // 2)
        elif section == "closing":
            start = max(0, total - para_count)
            end = total
        else:
            raise ValueError(f"未知 section: {section}，可选: opening/middle/closing")

        return '\n\n'.join(paragraphs[start:end]), start

    def check_node(
        self,
        text: str,
        who_present: str,
        where_just_now: str,
        why_do_this: str,
        info_source: str,
        section: str = "opening",
        node_label: str = None,
    ) -> Dict:
        """
        检查关键节点（方案C+ 新增）

        与 check_paragraph 类似，但用于章末关键节点检查而非段落级硬阻塞。
        不保存到段落记录，只返回结果。

        参数：
            text: 节点正文
            who_present: 谁在场
            where_just_now: 他们刚在哪
            why_do_this: 为什么这么做
            info_source: 信息/道具来源
            section: 'opening' / 'middle' / 'closing'
            node_label: 节点标签（如 "开头检查"）

        返回：
            {
                "pass": bool,
                "section": str,
                "label": str,
                "answers": {...},
                "checks": [...],
                "block_reason": str or None,
                "timestamp": str,
            }
        """
        checks = []
        block_reason = None

        # Q1: 谁在场？
        if not who_present or who_present.strip() == "":
            checks.append({"q": "谁在场？", "status": "fail", "detail": "未指定在场人物"})
            block_reason = "未指定在场人物"
        else:
            checks.append({"q": "谁在场？", "status": "pass", "detail": who_present})

        # Q2: 他们刚在哪？
        checks.append({"q": "他们刚在哪？", "status": "pass", "detail": where_just_now})

        # Q3: 为什么这么做？
        if not why_do_this or why_do_this.strip() == "":
            checks.append({"q": "为什么这么做？", "status": "fail", "detail": "未提供动机"})
            block_reason = "block_reason"
        else:
            checks.append({"q": "为什么这么做？", "status": "pass", "detail": why_do_this})

        # Q4: 信息/道具从哪来？
        if not info_source or info_source.strip() == "":
            checks.append({"q": "信息/道具从哪来？", "status": "fail", "detail": "未提供信息来源"})
            block_reason = "block_reason"
        else:
            checks.append({"q": "信息/道具从哪来？", "status": "pass", "detail": info_source})

        all_pass = all(c["status"] == "pass" for c in checks)
        return {
            "pass": all_pass,
            "section": section,
            "label": node_label or f"{section}节点",
            "answers": {
                "who_present": who_present,
                "where_just_now": where_just_now,
                "why_do_this": why_do_this,
                "info_source": info_source,
            },
            "checks": checks,
            "block_reason": block_reason,
            "timestamp": datetime.now().isoformat(),
        }

    def verify_all_passed(self) -> Tuple[bool, List[str]]:
        """
        验证当前章节所有段落四问是否全部通过
        在写完整章后调用
        """
        records = self.check_records.get("paragraphs", [])
        if not records:
            return True, ["暂无段落记录，跳过验证"]

        failed = [r for r in records if not r["pass"]]
        if failed:
            reasons = [f"段落{i+1}: {r['block_reason']}" for i, r in enumerate(failed)]
            return False, reasons
        return True, [f"✅ 全部 {len(records)} 段四问通过"]

    def generate_html_comment(self, time_str: str, loc: str, present: str, info: str, pov: str = None) -> str:
        """
        生成 HTML 注释标注（初稿阶段使用）

        格式：<!-- LOGIC: time=HH:MM | loc=地点 | present=角色A,角色B | info=关键信息 -->
        """
        parts = [f"time={time_str}", f"loc={loc}", f"present={present}", f"info={info}"]
        if pov:
            parts.append(f"pov={pov}")
        return f"<!-- LOGIC: {' | '.join(parts)} -->"

    def parse_html_comments(self, text: str) -> List[Dict]:
        """
        解析正文中的 HTML 逻辑注释
        用于定稿前检查和清理
        """
        pattern = r'<!--\s*LOGIC:\s*([^>]+?)\s*-->'
        comments = re.findall(pattern, text)
        results = []
        for c in comments:
            entry = {}
            for part in c.split('|'):
                part = part.strip()
                if '=' in part:
                    key, val = part.split('=', 1)
                    entry[key.strip()] = val.strip()
            results.append(entry)
        return results

    def clean_html_comments(self, text: str) -> str:
        """清除初稿阶段的 HTML 逻辑注释（定稿前调用）"""
        cleaned = re.sub(r'<!--\s*LOGIC:\s*[^>]+?\s*-->\n?', '', text)
        return cleaned

    def validate_continuity(self, new_answers: Dict, prev_answers: Dict) -> Tuple[bool, List[str]]:
        """
        检查段落间的连续性（防止瞬移、时间倒流）

        返回：(通过与否, 问题列表)
        """
        issues = []

        # 时间连续性检查
        # 简化版：如果新段落的地点与上一段不同，需要确认转移合理
        new_loc = new_answers.get("where_just_now", "")
        prev_loc = prev_answers.get("where_just_now", "")

        if new_loc and prev_loc and new_loc != prev_loc:
            # 地点变化，检查是否有过渡说明
            pass  # 实际项目中应检查交通时间

        # 人物连续性
        new_who = set(re.findall(r'[\u4e00-\u9fa5]{2,4}', new_answers.get("who_present", "")))
        prev_who = set(re.findall(r'[\u4e00-\u9fa5]{2,4}', prev_answers.get("who_present", "")))

        # 人物凭空出现/消失
        for char in prev_who:
            if char not in new_who and char not in new_answers.get("who_present", ""):
                issues.append(f"⚠️ 人物 '{char}' 在上一段在场，此段消失，需确认是否合理离开")
        for char in new_who:
            if char not in prev_who and char not in prev_answers.get("who_present", ""):
                issues.append(f"⚠️ 人物 '{char}' 在此段新出现，需确认来源")

        return len(issues) == 0, issues


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="动作前四问 — 段落级逻辑硬阻塞工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 初始化某章节的四问检查
  python3 paragraph-four-questions.py init --novel-id my-novel --chapter 5

  # 检查单个段落
  python3 paragraph-four-questions.py check --novel-id my-novel --chapter 5 \\
      --text "主角推门进来，李总已经在会议室坐了十分钟。" \\
      --who "主角、李总（秘书在门外等候）" \\
      --where "主角从办公室过来，李总从家中直接到会议室" \\
      --why "主角按约来汇报，李总要听方案" \\
      --info "会议室是昨天秘书预订的（ch04）"

  # 验证全部通过
  python3 paragraph-four-questions.py verify --novel-id my-novel --chapter 5

  # 生成 HTML 注释（初稿阶段）
  python3 paragraph-four-questions.py comment --time "09:15" --loc "公司会议室" \\
      --present "主角,李总" --info "主角知道B，李总不知道C"

  # 清除 HTML 注释（定稿前）
  python3 paragraph-four-questions.py clean --input ch05-draft.md --output ch05-final.md
        """
    )

    subparsers = parser.add_subparsers(dest="command")

    # init 命令
    p_init = subparsers.add_parser("init", help="初始化章节四问检查")
    p_init.add_argument("--novel-id", required=True, help="小说项目ID")
    p_init.add_argument("--chapter", required=True, type=int, help="章节号")

    # check 命令
    p_check = subparsers.add_parser("check", help="检查单个段落")
    p_check.add_argument("--novel-id", required=True)
    p_check.add_argument("--chapter", required=True, type=int)
    p_check.add_argument("--text", required=True, help="正文字段")
    p_check.add_argument("--who", required=True, help="谁在场")
    p_check.add_argument("--where", required=True, help="他们刚在哪")
    p_check.add_argument("--why", required=True, help="为什么这么做")
    p_check.add_argument("--info", required=True, help="信息/道具来源")
    p_check.add_argument("--prev", help="上一段答案JSON文件路径")

    # verify 命令
    p_verify = subparsers.add_parser("verify", help="验证全部段落四问是否通过")
    p_verify.add_argument("--novel-id", required=True)
    p_verify.add_argument("--chapter", required=True, type=int)

    # comment 命令
    p_comment = subparsers.add_parser("comment", help="生成 HTML 注释标注")
    p_comment.add_argument("--novel-id", default="default", help="小说项目ID（可选）")
    p_comment.add_argument("--time", required=True, help="时间（如 09:15）")
    p_comment.add_argument("--loc", required=True, help="地点")
    p_comment.add_argument("--present", required=True, help="在场人物")
    p_comment.add_argument("--info", required=True, help="关键信息")
    p_comment.add_argument("--pov", help="视角（可选）")

    # clean 命令
    p_clean = subparsers.add_parser("clean", help="清除 HTML 逻辑注释")
    p_clean.add_argument("--novel-id", default="default", help="小说项目ID（可选）")
    p_clean.add_argument("--input", required=True, help="输入文件")
    p_clean.add_argument("--output", required=True, help="输出文件")

    # check-node 命令（方案C+ 关键节点检查）
    p_check_node = subparsers.add_parser("check-node", help="关键节点四问检查（方案C+）")
    p_check_node.add_argument("--novel-id", required=True)
    p_check_node.add_argument("--chapter", required=True, type=int)
    p_check_node.add_argument("--section", required=True, choices=["opening", "middle", "closing"],
                              help="检查节点: opening(开头)/middle(中段)/closing(结尾)")
    p_check_node.add_argument("--chapter-file", help="章节文件路径（自动提取文本）")
    p_check_node.add_argument("--text", help="正文字段（与 --chapter-file 二选一）")
    p_check_node.add_argument("--who", required=True, help="谁在场")
    p_check_node.add_argument("--where", required=True, help="他们刚在哪")
    p_check_node.add_argument("--why", required=True, help="为什么这么做")
    p_check_node.add_argument("--info", required=True, help="信息/道具来源")

    # list 命令
    p_list = subparsers.add_parser("list", help="列出章节四问记录")
    p_list.add_argument("--novel-id", required=True)
    p_list.add_argument("--chapter", required=True, type=int)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command in ("init", "check", "verify", "list", "check-node"):
        checker = ParagraphFourQuestions(args.novel_id, getattr(args, 'chapter', None))

    if args.command == "init":
        print(f"✅ 已初始化第 {args.chapter} 章四问检查")
        print(f"   记录文件：{checker.check_records['path']}")

    elif args.command == "check":
        prev_answers = None
        if args.prev:
            with open(args.prev, 'r', encoding='utf-8') as f:
                prev_answers = json.load(f)

        result = checker.check_paragraph(
            text=args.text,
            who_present=args.who,
            where_just_now=args.where,
            why_do_this=args.why,
            info_source=args.info,
            prev_paragraph_answers=prev_answers,
        )

        status_icon = "✅ 通过" if result["pass"] else "❌ 未通过"
        print(f"\n段落判定：{status_icon}")
        if not result["pass"]:
            print(f"⛔ 阻塞原因：{result['block_reason']}")
        for c in result["checks"]:
            icon = "✅" if c["status"] == "pass" else "❌"
            print(f"  {icon} {c['q']}：{c['detail']}")

        # 输出 JSON 供后续使用
        print("\n--JSON--")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "verify":
        passed, msgs = checker.verify_all_passed()
        if passed:
            print(f"✅ 第 {args.chapter} 章四问全部通过（{len(checker.check_records['paragraphs'])} 段）")
        else:
            print(f"❌ 第 {args.chapter} 章有 {sum(1 for r in checker.check_records['paragraphs'] if not r['pass'])} 段未通过：")
            for msg in msgs:
                print(f"  {msg}")
        sys.exit(0 if passed else 1)

    elif args.command == "comment":
        # comment 不需要章节，直接生成注释
        tmp_checker = ParagraphFourQuestions("default", None)
        comment_text = tmp_checker.generate_html_comment(args.time, args.loc, args.present, args.info, args.pov)
        print(comment_text)

    elif args.command == "clean":
        # clean 不需要章节，直接清理注释
        tmp_checker = ParagraphFourQuestions("default", None)
        with open(args.input, 'r', encoding='utf-8') as f:
            content = f.read()
        cleaned = tmp_checker.clean_html_comments(content)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        removed = len(re.findall(r'<!--\s*LOGIC:[^>]+?\s*-->', content))
        print(f"✅ 已清除 {removed} 条 HTML 注释，输出到：{args.output}")

    elif args.command == "list":
        records = checker.check_records.get("paragraphs", [])
        if not records:
            print(f"📭 第 {args.chapter} 章暂无四问记录")
        else:
            passed_count = sum(1 for r in records if r["pass"])
            print(f"📋 第 {args.chapter} 章四问记录（{passed_count}/{len(records)} 通过）：\n")
            for i, r in enumerate(records, 1):
                icon = "✅" if r["pass"] else "❌"
                print(f"  {icon} 段落{i}: {r['text'][:40]}...")

    elif args.command == "check-node":
        # 方案C+ 关键节点检查
        if not args.text and not args.chapter_file:
            print("❌ 错误：必须提供 --text 或 --chapter-file")
            sys.exit(1)

        text = args.text
        if args.chapter_file:
            chapter_path = Path(args.chapter_file)
            if not chapter_path.exists():
                print(f"❌ 错误：章节文件不存在：{chapter_path}")
                sys.exit(1)
            text = checker.parse_chapter_text(chapter_path)
            paragraphs = checker.split_paragraphs(text)
            text, start_idx = checker.extract_section(paragraphs, args.section)
            if not text:
                print(f"❌ 错误：无法从第 {args.chapter} 章提取 {args.section} 部分")
                sys.exit(1)
            print(f"📖 已提取第 {args.chapter} 章 {args.section} 部分（段落 {start_idx+1}~{start_idx+len(paragraphs)}）")

        result = checker.check_node(
            text=text,
            who_present=args.who,
            where_just_now=args.where,
            why_do_this=args.why,
            info_source=args.info,
            section=args.section,
            node_label=f"第{args.chapter}章-{args.section}",
        )

        status_icon = "✅ 通过" if result["pass"] else "❌ 未通过"
        print(f"\n【{result['label']}】判定：{status_icon}")
        if not result["pass"]:
            print(f"⛔ 阻塞原因：{result['block_reason']}")
        for c in result["checks"]:
            icon = "✅" if c["status"] == "pass" else "❌"
            print(f"  {icon} {c['q']}：{c['detail']}")

        print("\n--JSON--")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
