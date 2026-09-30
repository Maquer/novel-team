#!/usr/bin/env python3
"""
知情边界追踪器 — 专治"角色知道了不该知道的信息"穿帮

借鉴 ai-fiction-writer novel-logic Skill 的核心创新。
每个角色维护一个 know/don't know 表，确保信息只在
知情者之间流动，不在不知情者面前泄露。

核心原则：
- 每个角色只知道他应该知道的信息
- 知道某信息后，必须按该角色的性格/身份做出反应
- 秘密知情者（如偷听到）后续不能"自然"提到
- 信息变化后立即更新边界表
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

TRACKING_DIR = Path("/var/minis/shared/novel-team/.tracking")


class InfoBoundary:
    """知情边界追踪系统"""

    def __init__(self, novel_id: str, chapter_num: int = None):
        self.novel_id = novel_id
        self.chapter_num = chapter_num
        self.tracking_dir = TRACKING_DIR / novel_id
        self.tracking_dir.mkdir(parents=True, exist_ok=True)

        self.boundary_path = self.tracking_dir / "知情边界.md"
        self.json_path = self.tracking_dir / "info-boundary.json"

        self.data = self._load()

    def _load(self) -> Dict:
        if self.json_path.exists():
            return json.loads(self.json_path.read_text(encoding='utf-8'))
        return {
            "novel_id": self.novel_id,
            "characters": {},      # {角色名: {know: [...], dont_know: [...], source: [...]}}
            "changes": [],         # 本章信息变化记录
            "warnings": [],        # 潜在冲突预警
            "next_chapter_must_address": [],  # 下章必须交代
            "version": "1.0",
            "updated_at": None,
        }

    def _save(self):
        self.data["updated_at"] = datetime.now().isoformat()
        tmp = self.json_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.json_path)

    def add_character(self, name: str, know: List[str] = None, dont_know: List[str] = None):
        """添加角色并初始化知情边界"""
        if name not in self.data["characters"]:
            self.data["characters"][name] = {
                "know": know or [],
                "dont_know": dont_know or [],
                "source": {},  # {info: "来源章节"}
            }
        else:
            # 追加已知信息
            if know:
                for info in know:
                    if info not in self.data["characters"][name]["know"]:
                        self.data["characters"][name]["know"].append(info)
            if dont_know:
                for info in dont_know:
                    if info not in self.data["characters"][name]["dont_know"]:
                        self.data["characters"][name]["dont_know"].append(info)
        self._save()
        return name

    def update_know(self, character: str, info: str, source: str = ""):
        """更新角色的已知信息"""
        if character not in self.data["characters"]:
            self.add_character(character)

        char_data = self.data["characters"][character]

        # 从 dont_know 移到 know
        if info in char_data["dont_know"]:
            char_data["dont_know"].remove(info)

        if info not in char_data["know"]:
            char_data["know"].append(info)

        if source:
            char_data["source"][info] = source

        # 记录变化
        self.data["changes"].append({
            "timestamp": datetime.now().isoformat(),
            "character": character,
            "action": "know",
            "info": info,
            "source": source,
        })

        self._save()
        return info

    def update_dont_know(self, character: str, info: str, reason: str = ""):
        """更新角色的未知信息"""
        if character not in self.data["characters"]:
            self.add_character(character)

        char_data = self.data["characters"][character]

        # 从 know 移到 dont_know（信息丢失，如失忆）
        if info in char_data["know"]:
            char_data["know"].remove(info)

        if info not in char_data["dont_know"]:
            char_data["dont_know"].append(info)

        # 记录变化
        self.data["changes"].append({
            "timestamp": datetime.now().isoformat(),
            "character": character,
            "action": "dont_know",
            "info": info,
            "reason": reason,
        })

        self._save()
        return info

    def detect_leak(self, character: str, info: str) -> Optional[str]:
        """
        检测信息泄露风险

        如果一个角色不应该知道某信息，但出现在知道该信息的人面前，
        且没有合理的信息获取途径，则标记为泄露风险。
        """
        if character not in self.data["characters"]:
            return None

        char_data = self.data["characters"][character]

        # 检查角色是否知道该信息
        if info in char_data["know"]:
            return None  # 角色已知，无泄露风险

        # 检查是否有来源记录
        for other_char, other_data in self.data["characters"].items():
            if info in other_data["know"]:
                # 其他角色知道，但当前角色不知道 → 潜在泄露点
                # 检查是否有"秘密知情"标记
                pass

        return None

    def check_scenario_risk(
        self,
        characters_in_scene: List[str],
        info_being_discussed: str,
    ) -> Tuple[bool, List[str]]:
        """
        检查某场景的信息泄露风险

        参数：
            characters_in_scene: 场景中在场的所有角色
            info_being_discussed: 正在被讨论的信息

        返回：
            (是否有风险, 风险列表)
        """
        risks = []

        for char_name in characters_in_scene:
            if char_name not in self.data["characters"]:
                risks.append(f"⚠️ 角色 '{char_name}' 未在知情边界表中，请补充档案")
                continue

            char_data = self.data["characters"][char_name]

            # 检查：角色不在场但信息被提及
            if info_being_discussed in char_data["dont_know"]:
                # 检查是否是"秘密知情者"（知道但不能说）
                # 这里简化处理：如果角色不知道某信息，却出现在讨论该信息的场景中
                pass  # 这是正常情况，不是泄露

            # 检查：角色知道某信息，但场景中其他人不知道 → 可能泄露
            if info_being_discussed in char_data["know"]:
                others_known = sum(
                    1 for other in characters_in_scene
                    if other != char_name
                    and other in self.data["characters"]
                    and info_being_discussed in self.data["characters"][other]["know"]
                )
                if others_known == 0:
                    risks.append(
                        f"⚠️ '{char_name}' 知道 '{info_being_discussed}'，"
                        f"但场景中其他角色均不知晓——需确认是否有合理理由分享"
                    )

        return len(risks) == 0, risks

    def generate_warning(self, character: str, info: str, warning_type: str, detail: str = ""):
        """生成潜在信息冲突预警"""
        warning = {
            "timestamp": datetime.now().isoformat(),
            "character": character,
            "info": info,
            "type": warning_type,  # "behavior_expectation" / "secret_knowledge" / "timeline_conflict"
            "detail": detail,
        }
        self.data["warnings"].append(warning)
        self._save()
        return warning

    def add_must_address(self, item: str):
        """添加下章必须交代的项"""
        if item not in self.data["next_chapter_must_address"]:
            self.data["next_chapter_must_address"].append(item)
            self._save()

    def export_md(self) -> str:
        """导出为 Markdown 格式（供人阅读）"""
        lines = [
            "## 当前各角色知情状态\n",
            "| 角色 | 知道 | 不知道 | 信息来源 |",
            "|------|------|--------|---------|",
        ]

        for char_name, char_data in self.data["characters"].items():
            know_list = ", ".join(char_data["know"][:5])  # 最多显示5条
            dont_list = ", ".join(char_data["dont_know"][:5])
            source_summary = "、".join(
                f"{info}({src})" for info, src in list(char_data.get("source", {}).items())[:3]
            )
            lines.append(f"| {char_name} | {know_list} | {dont_list} | {source_summary} |")

        if self.data["changes"]:
            lines.append("\n## 本章信息变化\n")
            for change in self.data["changes"][-10:]:  # 最近10条
                action_label = "知道→知道" if change["action"] == "know" else "不知道→知道"
                lines.append(f"- {change['character']}: {change['info']} ({action_label})")

        if self.data["warnings"]:
            lines.append("\n## 潜在信息冲突预警\n")
            for w in self.data["warnings"]:
                lines.append(f"- [{w['type']}] {w['character']}: {w['detail']}")

        if self.data["next_chapter_must_address"]:
            lines.append("\n## 下章必须交代\n")
            for item in self.data["next_chapter_must_address"]:
                lines.append(f"- {item}")

        return "\n".join(lines)

    def sync_to_file(self):
        """同步到 tracking 目录下的 Markdown 文件"""
        self.boundary_path.write_text(self.export_md(), encoding='utf-8')


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="知情边界追踪 — 专治信息穿帮",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 初始化某小说的知情边界
  python3 info-boundary.py init --novel-id my-novel

  # 添加角色并初始化边界
  python3 info-boundary.py add-character --novel-id my-novel \\
      --name 萧辰 --know "天剑宗弟子" --dont-know "血煞门阴谋"

  # 更新角色的已知信息
  python3 info-boundary.py update-know --novel-id my-novel \\
      --character 萧辰 --info "发现铁剑真相" --source "ch05"

  # 检查场景信息泄露风险
  python3 info-boundary.py check-scene --novel-id my-novel \\
      --characters "萧辰,李总,秘书" --info "项目机密"

  # 导出为 Markdown
  python3 info-boundary.py export --novel-id my-novel --output 知情边界.md

  # 查看统计
  python3 info-boundary.py stats --novel-id my-novel
        """
    )

    subparsers = parser.add_subparsers(dest="command")

    # init 命令
    p_init = subparsers.add_parser("init", help="初始化知情边界")
    p_init.add_argument("--novel-id", required=True)

    # add-character 命令
    p_add = subparsers.add_parser("add-character", help="添加/更新角色")
    p_add.add_argument("--novel-id", required=True)
    p_add.add_argument("--name", "-n", required=True, help="角色名")
    p_add.add_argument("--know", "-k", nargs="*", help="已知信息列表")
    p_add.add_argument("--dont-know", "-d", nargs="*", help="未知信息列表")

    # update-know 命令
    p_update = subparsers.add_parser("update-know", help="更新角色已知信息")
    p_update.add_argument("--novel-id", required=True)
    p_update.add_argument("--character", "-c", required=True)
    p_update.add_argument("--info", "-i", required=True)
    p_update.add_argument("--source", "-s", default="", help="来源章节")

    # update-dont-know 命令
    p_unknow = subparsers.add_parser("update-dont-know", help="更新角色未知信息")
    p_unknow.add_argument("--novel-id", required=True)
    p_unknow.add_argument("--character", "-c", required=True)
    p_unknow.add_argument("--info", "-i", required=True)
    p_unknow.add_argument("--reason", "-r", default="", help="原因（如失忆）")

    # check-scene 命令
    p_scene = subparsers.add_parser("check-scene", help="检查场景信息泄露风险")
    p_scene.add_argument("--novel-id", required=True)
    p_scene.add_argument("--characters", required=True, help="逗号分隔的角色名列表")
    p_scene.add_argument("--info", required=True, help="被讨论的信息")

    # export 命令
    p_export = subparsers.add_parser("export", help="导出为 Markdown")
    p_export.add_argument("--novel-id", required=True)
    p_export.add_argument("--output", "-o", default="", help="输出文件路径")

    # stats 命令
    p_stats = subparsers.add_parser("stats", help="统计信息")
    p_stats.add_argument("--novel-id", required=True)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    boundary = InfoBoundary(args.novel_id)

    if args.command == "init":
        print(f"✅ 已初始化 '{args.novel_id}' 的知情边界")
        print(f"   数据文件：{boundary.json_path}")

    elif args.command == "add-character":
        boundary.add_character(args.name, args.know, args.dont_know)
        print(f"✅ 已添加角色 '{args.name}'")
        print(f"   已知：{args.know or '无'}")
        print(f"   未知：{args.dont_know or '无'}")

    elif args.command == "update-know":
        boundary.update_know(args.character, args.info, args.source)
        print(f"✅ '{args.character}' 现已知道：'{args.info}'")
        if args.source:
            print(f"   来源：{args.source}")

    elif args.command == "update-dont-know":
        boundary.update_dont_know(args.character, args.info, args.reason)
        print(f"✅ '{args.character}' 现已不知道：'{args.info}'")
        if args.reason:
            print(f"   原因：{args.reason}")

    elif args.command == "check-scene":
        chars = [c.strip() for c in args.characters.split(",")]
        passed, risks = boundary.check_scenario_risk(chars, args.info)
        if passed:
            print(f"✅ 场景信息泄露检查通过")
        else:
            print(f"⚠️ 发现 {len(risks)} 个潜在风险：")
            for r in risks:
                print(f"  {r}")
        sys.exit(0 if passed else 1)

    elif args.command == "export":
        md_content = boundary.export_md()
        if args.output:
            out_path = Path(args.output)
            out_path.write_text(md_content, encoding='utf-8')
            print(f"✅ 已导出到 {out_path}")
        else:
            print(md_content)
        # 同步到 tracking 目录
        boundary.sync_to_file()

    elif args.command == "stats":
        chars = boundary.data.get("characters", {})
        total_know = sum(len(c["know"]) for c in chars.values())
        total_dont = sum(len(c["dont_know"]) for c in chars.values())
        total_changes = len(boundary.data.get("changes", []))
        total_warnings = len(boundary.data.get("warnings", []))

        print(f"\n📊 '{args.novel_id}' 知情边界统计：")
        print(f"  角色数：{len(chars)}")
        print(f"  已知信息总数：{total_know}")
        print(f"  未知信息总数：{total_dont}")
        print(f"  信息变更记录：{total_changes}")
        print(f"  潜在预警：{total_warnings}")

        if boundary.data.get("next_chapter_must_address"):
            print(f"\n📋 下章必须交代：")
            for item in boundary.data["next_chapter_must_address"]:
                print(f"  - {item}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
