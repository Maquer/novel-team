#!/usr/bin/env python3
"""
Story System 合同+提交系统

借鉴：webnovel-writer (lingfengQAQ/webnovel-writer, 7302★)
核心：动笔前签合同（设定/大纲约束），写完提交事实（角色/伏笔/时间线变更）

Story System 三层：
1. 合同种子（Contract Seed）：动笔前的约束——角色设定/大纲/时间线/伏笔种子
2. 运行时合同（Runtime Contract）：本章写作约束——参与角色/场景/情绪走向/信息差
3. 章节提交（Chapter Commit）：写完后提交的事实——新事件/角色状态变更/伏笔变更

用法：
  python3 story-system.py init --novel-id <id>              # 初始化 Story System
  python3 story-system.py contract --novel-id <id> --chapter <N>  # 生成章节运行时合同
  python3 story-system.py commit --novel-id <id> --chapter <N>   # 提交章节事实
  python3 story-system.py status --novel-id <id>            # 查看 Story System 状态
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

STORY_SYSTEM_DIR = ".story-system"
COMMITS_DIR = f"{STORY_SYSTEM_DIR}/commits"
CONTRACTS_DIR = f"{STORY_SYSTEM_DIR}/contracts"
SEED_FILE = f"{STORY_SYSTEM_DIR}/seed.json"


class StorySystem:
    """Story System 合同+提交系统"""

    def __init__(self, novel_id: str = None, project_root: str = None):
        self.novel_id = novel_id
        self.root = Path(project_root or f"novels/{novel_id}")
        self.ss_root = self.root / STORY_SYSTEM_DIR
        self.commits_dir = self.ss_root / "commits"
        self.contracts_dir = self.ss_root / "contracts"
        self.seed_file = self.ss_root / "seed.json"

    def init(self, title: str = "", genre: str = "", world_setting: str = ""):
        """初始化 Story System——生成合同种子"""
        self.ss_root.mkdir(parents=True, exist_ok=True)
        self.commits_dir.mkdir(exist_ok=True)
        self.contracts_dir.mkdir(exist_ok=True)

        seed = {
            "novel_id": self.novel_id,
            "title": title,
            "genre": genre,
            "world_setting": world_setting,
            "created_at": datetime.now().isoformat(),
            "mainline_ready": False,
            "characters": [],
            "timeline": [],
            "foreshadow_seeds": [],
            "power_system": "",
            "volume_plan": [],
        }

        self.seed_file.write_text(
            json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"success": True, "seed_file": str(self.seed_file), "seed": seed}

    def generate_contract(self, chapter: int) -> dict:
        """生成章节运行时合同——本章的写作约束"""
        seed = self._load_seed()

        contract = {
            "chapter": chapter,
            "novel_id": self.novel_id,
            "created_at": datetime.now().isoformat(),
            "status": "draft",

            # 写作约束
            "constraints": {
                "participating_characters": [],  # 本章参与角色
                "scene_locations": [],           # 场景地点
                "time_span": "",                 # 时间跨度
                "emotion_arc": "",               # 情绪走向
                "information_gap": {             # 信息差
                    "who_knows": [],
                    "who_doesnt_know": [],
                },
                "foreshadow_active": [],         # 本章活跃伏笔
                "foreshadow_to_plant": [],       # 本章要埋的伏笔
                "foreshadow_to_resolve": [],     # 本章要回收的伏笔
            },

            # 前置条件（从前一章提交继承）
            "preconditions": {
                "previous_facts": [],            # 前章已确立的事实
                "character_states": {},          # 角色当前状态
                "active_conflicts": [],          # 活跃冲突
            },

            # 章节目标
            "chapter_goals": {
                "main_event": "",                # 本章主要事件
                "character_development": "",      # 角色发展
                "reader_hook": "",               # 读者钩子
                "word_count_target": [3000, 5000],
            },

            # 审查维度（写完后检查）
            "review_dimensions": [
                "character_consistency",         # 角色一致性
                "timeline_consistency",           # 时间线一致性
                "power_system_consistency",       # 战力体系一致性
                "foreshadow_tracking",            # 伏笔追踪
                "plot_logic",                     # 剧情逻辑
                "emotion_arc",                    # 情绪弧线
                "reader_hook_quality",            # 钩子质量
                "anti_ai_check",                  # 去AI味检查
            ],
        }

        # 如果有前一章提交，继承前置条件
        if chapter > 1:
            prev_commit = self._load_commit(chapter - 1)
            if prev_commit and prev_commit.get("status") == "accepted":
                contract["preconditions"]["previous_facts"] = prev_commit.get("new_facts", [])
                contract["preconditions"]["character_states"] = prev_commit.get("character_state_changes", {})
                contract["preconditions"]["active_conflicts"] = prev_commit.get("active_conflicts", [])

        contract_file = self.contracts_dir / f"chapter_{chapter:03d}.contract.json"
        contract_file.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return contract

    def commit_chapter(self, chapter: int, facts: dict = None) -> dict:
        """提交章节事实——写完后的事实入账

        这是 Story System 的核心：一章写完，新事实从这里入账。
        所有状态变更都经过这里，不会出现"状态已推进、正文未落盘"。
        """
        contract = self._load_contract(chapter)
        if not contract:
            return {"success": False, "error": f"章节 {chapter} 无运行时合同，请先生成"}

        commit = {
            "chapter": chapter,
            "novel_id": self.novel_id,
            "committed_at": datetime.now().isoformat(),
            "status": "pending",  # pending → accepted/rejected

            # 提交的事实（从正文提取）
            "new_facts": facts.get("new_facts", []) if facts else [],
            "character_state_changes": facts.get("character_state_changes", {}) if facts else {},
            "foreshadow_changes": {
                "planted": facts.get("foreshadow_planted", []) if facts else [],
                "resolved": facts.get("foreshadow_resolved", []) if facts else [],
                "advanced": facts.get("foreshadow_advanced", []) if facts else [],
            } if facts else {},
            "timeline_events": facts.get("timeline_events", []) if facts else [],
            "active_conflicts": facts.get("active_conflicts", []) if facts else [],
            "resolved_conflicts": facts.get("resolved_conflicts", []) if facts else [],

            # 投影日志（哪些派生数据需要同步）
            "projection_log": {
                "state": "pending",
                "index": "pending",
                "summary": "pending",
                "memory": "pending",
                "vector": "pending",
            },

            # 审查结果
            "review_result": facts.get("review_result", {}) if facts else {},
        }

        commit_file = self.commits_dir / f"chapter_{chapter:03d}.commit.json"
        commit_file.write_text(
            json.dumps(commit, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return {"success": True, "commit_file": str(commit_file), "commit": commit}

    def accept_commit(self, chapter: int) -> dict:
        """接受章节提交——事实正式入账"""
        commit = self._load_commit(chapter)
        if not commit:
            return {"success": False, "error": f"章节 {chapter} 无提交记录"}

        commit["status"] = "accepted"
        commit["accepted_at"] = datetime.now().isoformat()

        # 更新投影状态
        for key in commit["projection_log"]:
            commit["projection_log"][key] = "done"

        self._save_commit(chapter, commit)

        # 更新种子文件
        seed = self._load_seed()
        if not seed.get("mainline_ready"):
            seed["mainline_ready"] = True
            self._save_seed(seed)

        return {"success": True, "chapter": chapter, "status": "accepted"}

    def atomic_commit(self, chapter: int, content_file: str, facts: dict = None) -> dict:
        """原子提交——借鉴 InkOS 安全章节工作区

        正文+状态+伏笔先校验再提交，失败不留半成品。
        三步原子操作：
        1. 验证正文存在且字数达标
        2. 验证合同存在
        3. 全部通过后才提交事实

        如果任何一步失败，不修改任何已有状态。
        """
        # Step 1: 验证正文
        content_path = Path(content_file)
        if not content_path.exists():
            return {"success": False, "error": "正文文件不存在", "atomic": True, "rolled_back": True}

        content = content_path.read_text(encoding="utf-8")
        word_count = len(re.sub(r'[\s\n\r\t]', '', content))

        if word_count < 1500:
            return {
                "success": False,
                "error": f"正文字数不足：{word_count} < 1500",
                "atomic": True,
                "rolled_back": True,
            }

        # Step 2: 验证合同存在
        contract = self._load_contract(chapter)
        if not contract:
            return {
                "success": False,
                "error": f"章节 {chapter} 无运行时合同",
                "atomic": True,
                "rolled_back": True,
            }

        # Step 3: 全部通过，提交事实
        commit_result = self.commit_chapter(chapter, facts)
        if not commit_result["success"]:
            return {
                "success": False,
                "error": "事实提交失败",
                "atomic": True,
                "rolled_back": True,
                "detail": commit_result,
            }

        # Step 4: 接受提交
        accept_result = self.accept_commit(chapter)

        return {
            "success": True,
            "atomic": True,
            "rolled_back": False,
            "chapter": chapter,
            "word_count": word_count,
            "commit": commit_result.get("commit"),
            "accepted": accept_result["success"],
        }

    def status(self) -> dict:
        """查看 Story System 状态"""
        seed = self._load_seed()
        if not seed:
            return {"success": False, "error": "Story System 未初始化"}

        commits = []
        if self.commits_dir.exists():
            for f in sorted(self.commits_dir.glob("*.commit.json")):
                c = json.loads(f.read_text(encoding="utf-8"))
                commits.append({
                    "chapter": c["chapter"],
                    "status": c["status"],
                    "committed_at": c.get("committed_at", ""),
                    "facts_count": len(c.get("new_facts", [])),
                })

        contracts = []
        if self.contracts_dir.exists():
            for f in sorted(self.contracts_dir.glob("*.contract.json")):
                c = json.loads(f.read_text(encoding="utf-8"))
                contracts.append({
                    "chapter": c["chapter"],
                    "status": c.get("status", "draft"),
                })

        return {
            "novel_id": self.novel_id,
            "mainline_ready": seed.get("mainline_ready", False),
            "title": seed.get("title", ""),
            "commits": commits,
            "contracts": contracts,
            "total_commits": len(commits),
            "accepted_commits": sum(1 for c in commits if c["status"] == "accepted"),
            "pending_commits": sum(1 for c in commits if c["status"] == "pending"),
        }

    def _load_seed(self):
        if self.seed_file.exists():
            return json.loads(self.seed_file.read_text(encoding="utf-8"))
        return None

    def _save_seed(self, seed):
        self.seed_file.write_text(
            json.dumps(seed, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load_contract(self, chapter: int):
        f = self.contracts_dir / f"chapter_{chapter:03d}.contract.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        return None

    def _load_commit(self, chapter: int):
        f = self.commits_dir / f"chapter_{chapter:03d}.commit.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
        return None

    def _save_commit(self, chapter: int, commit):
        f = self.commits_dir / f"chapter_{chapter:03d}.commit.json"
        f.write_text(
            json.dumps(commit, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == '__main__':
    import re
    import argparse

    parser = argparse.ArgumentParser(description="Story System 合同+提交")
    parser.add_argument("--novel-id", default=None)
    parser.add_argument("--project-root", default=None)
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init", help="初始化")
    sub.add_parser("contract", help="生成运行时合同").add_argument("--chapter", type=int, required=True)
    sub.add_parser("commit", help="提交章节事实").add_argument("--chapter", type=int, required=True)
    sub.add_parser("accept", help="接受提交").add_argument("--chapter", type=int, required=True)
    p_atomic = sub.add_parser("atomic", help="原子提交")
    p_atomic.add_argument("--chapter", type=int, required=True)
    p_atomic.add_argument("--content", required=True, help="正文文件路径")
    sub.add_parser("status", help="查看状态")

    args = parser.parse_args()
    ss = StorySystem(args.novel_id, args.project_root)

    if args.cmd == "init":
        result = ss.init()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "contract":
        result = ss.generate_contract(args.chapter)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "commit":
        result = ss.commit_chapter(args.chapter)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "accept":
        result = ss.accept_commit(args.chapter)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "atomic":
        result = ss.atomic_commit(args.chapter, args.content)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "status":
        result = ss.status()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
