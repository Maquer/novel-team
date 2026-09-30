#!/usr/bin/env python3
"""
事实账本 + 认知分级系统 — 小说创作记忆系统

v2 Phase 1 迁移：
- FactLedger 改为 novelkit.stores.fact_store.FactStore 的薄兼容别名
  （方法/属性名全部一致；gate-check 等调用方无需改动）。
- 路径修正（有意的 bug 修复，见 FactStore docstring）：v1 把根路径硬编码为
  /var/minis/shared/novel-team，无视 NOVEL_TEAM_ROOT；现在走
  novelkit.core.config.novel_team_root()。路径约定本身不变
  （<root>/ledger/<novel_id>/facts.json），与 gate-check 读取路径一致；
  OpenMinis 生产环境（NOVEL_TEAM_ROOT 未设置）行为与 v1 完全一致。
- 补上 v1 缺失的 account_cmd（main() 里引用了但从未定义，
  跑 `account` 子命令会 NameError）。

借鉴 StoryForge 四层记忆系统：
  正文 → 事实 → 摘要 → 检索

核心功能：
  1. 事实追踪：记录人物状态、物品归属、事件时间线
  2. 版本保护：正文变化使旧候选失效
  3. 摘要生成：章节/卷/全局三层摘要
  4. 检索索引：快速查找相关片段
  5. 认知分级：know/believe/suspect/infer 四层（借鉴 ai-novel-writer v6）

数据模型：
  - facts.json: 已确认事实账本
  - states.json: 人物/物品状态追踪
  - summaries.json: 三层摘要
  - index.json: 检索索引
  - knowledge.json: 认知分级系统

事实状态机（FIX 2026-09-30 新增）：
  - add-fact 写入 status="unverified"；verify-fact --id 可置为 "verified"
  - source 命中测试黑名单（测试/test）时拒绝写入，除非 --allow-test
"""

import json
import os
import sys
import argparse
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

# novelkit 导入：仓库根目录（novelkit/ 所在）入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# 兼容 v1：tools/ 目录入 sys.path（project_guard 等仍在此）
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 代际项目守卫（唯一路径入口）
from project_guard import resolve

from novelkit.stores.fact_store import FactStore

# 向后兼容：v1 的类名。方法/属性与 FactStore 完全一致。
FactLedger = FactStore

# 数据目录（全局，不随代际变化）——v1 遗留常量，保留供外部引用；
# 实际路径以 novelkit.core.config.novel_team_root() 为准。
LEDGER_DIR = Path("/var/minis/shared/novel-team/ledger")

# 认知分级类型
KNOW_TYPES = ["know", "believe", "suspect", "infer"]


class KnowledgeLedger:
    """认知分级系统（know/believe/suspect/infer）"""

    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.db_path = resolve(novel_id).ledger() / "knowledge.json"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> Dict:
        raw = {}
        if self.db_path.exists():
            raw = json.loads(self.db_path.read_text(encoding='utf-8'))
        # 兼容归一化：老账本可能用 "facts"（列表）作认知存储，或缺失 knowledge/memories 键
        # 代码内部统一以 "knowledge" 键（列表）访问，这里做一次键映射，避免 KeyError
        if not isinstance(raw.get("knowledge"), list):
            raw["knowledge"] = raw.get("facts", [])
        if not isinstance(raw.get("memories"), list):
            raw["memories"] = []
        raw.setdefault("novel_id", self.novel_id)
        return raw

    def _save(self):
        tmp = self.db_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.db_path)

    def add_memory(self, content: str, memory_type: str = "chapter",
                  chapter_id: str = "", metadata: Dict = None) -> str:
        """添加记忆到向量库（简化版）"""
        import time
        memory_id = f"M{len(self.data['memories'])+1:04d}"

        # 简化版：不实际调用ChromaDB，只记录元数据
        # 实际需要：
        # 1. 使用ONNX Embedding生成向量
        # 2. 存入ChromaDB collection

        memory = {
            "id": memory_id,
            "content": content,
            "type": memory_type,
            "chapter_id": chapter_id,
            "metadata": metadata or {},
            "created_at": time.time(),
            "embedding": None,  # 实际应存储向量
        }

        self.data["memories"].append(memory)
        self._save()

        return memory_id

    def retrieve_memories(self, query: str, top_k: int = 5,
                         threshold: float = 0.7) -> List[Dict]:
        """语义检索记忆（简化版）"""
        # 简化版：返回最近的top_k条记忆
        # 实际需要：
        # 1. 使用Embedding模型生成查询向量
        # 2. 在ChromaDB中做相似度搜索
        # 3. 过滤低于threshold的结果

        memories = self.data.get("memories", [])

        # 按创建时间排序
        sorted_memories = sorted(
            memories,
            key=lambda m: m.get("created_at", 0),
            reverse=True
        )

        # 返回top_k
        return sorted_memories[:top_k]

    def add(self, character: str, know_type: str, content: str,
            source: str = "", confidence: float = 1.0) -> str:
        """添加认知记录"""
        if know_type not in KNOW_TYPES:
            raise ValueError(f"非法认知类型: {know_type}，可选: {KNOW_TYPES}")

        import time
        knowledge_id = f"K{len(self.data['knowledge'])+1:04d}"

        record = {
            "id": knowledge_id,
            "character": character,
            "type": know_type,
            "content": content,
            "source": source,
            "confidence": confidence,
            "created_at": time.time(),
        }

        self.data["knowledge"].append(record)
        self._save()

        return knowledge_id

    def get_all(self, character: str = None) -> List[Dict]:
        """获取所有认知（可过滤角色）"""
        if character:
            return [k for k in self.data["knowledge"] if k["character"] == character]
        return self.data["knowledge"]

    def check_conflict(self, character: str) -> List[Dict]:
        """检查认知冲突"""
        char_knowledge = self.get_all(character)

        know_facts = [k for k in char_knowledge if k["type"] == "know"]
        believe_facts = [k for k in char_knowledge if k["type"] == "believe"]

        conflicts = []
        for kf in know_facts:
            for bf in believe_facts:
                if kf["content"] != bf["content"] and len(kf["content"]) > 5:
                    conflicts.append({
                        "type": "conflict",
                        "know": kf["content"],
                        "believe": bf["content"],
                    })

        return conflicts


def account_cmd(args):
    """账目管理命令（v2 Phase 1 补上：v1 main() 引用了但从未定义）。

    action:
      add   --entity --item --quantity [--source]  记一笔账目变化
      check --entity --item                        检查最近跳变
      list  --entity（可选）                       列出账目
    """
    ledger = FactLedger(args.novel_id)

    if args.action == "add":
        if not args.entity or not args.item or args.quantity is None:
            print("❌ add 需要 --entity --item --quantity")
            return 1
        ledger.add_account(args.entity, args.item, args.quantity,
                           source=args.source or "")
        print(f"✅ 已记账: {args.entity}:{args.item} {args.quantity:+d}")
        return 0

    elif args.action == "check":
        if not args.entity or not args.item:
            print("❌ check 需要 --entity --item")
            return 1
        msg = ledger.check_account_jump(args.entity, args.item)
        if msg:
            print(f"⚠️ {msg}")
            return 1
        print("✅ 账目无异常跳变")
        return 0

    elif args.action == "list":
        states = ledger.states
        shown = 0
        print(f"\n📒 {args.novel_id} 的账目:")
        for key, st in states.items():
            if not isinstance(st, dict) or "quantity" not in st:
                continue
            if args.entity and st.get("entity") != args.entity:
                continue
            print(f"  {st.get('entity')}:{st.get('item')} = {st['quantity']}")
            shown += 1
        if not shown:
            print("  （空）")
        return 0

    print("❌ 未知操作")
    return 1


def main():
    parser = argparse.ArgumentParser(description="事实账本 + 认知分级系统")
    subparsers = parser.add_subparsers(dest="command")

    # fact命令
    p_fact = subparsers.add_parser("add-fact", help="添加事实")
    p_fact.add_argument("--novel-id", required=True)
    p_fact.add_argument("--category", required=True)
    p_fact.add_argument("--content", required=True)
    p_fact.add_argument("--source", default="")
    # FIX 2026-09-30：测试源写入需显式放行
    p_fact.add_argument("--allow-test", action="store_true",
                        help="允许 source 命中测试黑名单（测试/调试用，默认拒绝）")

    p_list = subparsers.add_parser("list-facts", help="列出事实")
    p_list.add_argument("--novel-id", required=True)
    p_list.add_argument("--category", default=None)
    # FIX 2026-09-30：按 status 过滤
    p_list.add_argument("--status", default=None,
                        choices=["unverified", "verified"],
                        help="按确认状态过滤（缺 status 的历史数据视为 unverified）")

    # FIX 2026-09-30：新增 verify-fact 命令（此前无任何代码路径能确认事实）
    p_verify = subparsers.add_parser("verify-fact", help="人工确认事实（status → verified）")
    p_verify.add_argument("--novel-id", required=True)
    p_verify.add_argument("--id", required=True, help="事实ID，如 F0001")

    p_state = subparsers.add_parser("update-state", help="更新状态")
    p_state.add_argument("--novel-id", required=True)
    p_state.add_argument("--entity", required=True)
    p_state.add_argument("--key", required=True)
    p_state.add_argument("--value", required=True)

    p_get = subparsers.add_parser("get-state", help="获取状态")
    p_get.add_argument("--novel-id", required=True)
    p_get.add_argument("--entity", required=True)
    p_get.add_argument("--key", required=True)

    p_summary = subparsers.add_parser("list-states", help="列出状态")
    p_summary.add_argument("--novel-id", required=True)

    p_report = subparsers.add_parser("report", help="统计报告")
    p_report.add_argument("--novel-id", required=True)

    # account命令
    p_acc = subparsers.add_parser("account", help="账目管理")
    p_acc.add_argument("--novel-id", required=True)
    p_acc.add_argument("action", choices=["add", "check", "list"])
    p_acc.add_argument("--entity", "-e", help="实体名")
    p_acc.add_argument("--item", "-i", help="物品名")
    p_acc.add_argument("--quantity", "-q", type=int, help="数量变化")
    p_acc.add_argument("--source", help="来源")

    # knowledge命令
    p_know = subparsers.add_parser("knowledge", help="认知分级系统")
    p_know.add_argument("--novel-id", required=True)
    p_know.add_argument("action", choices=["add", "list", "check", "summary"])
    p_know.add_argument("--character", "-c", help="角色名")
    p_know.add_argument("--type", "-t", choices=KNOW_TYPES, help="认知类型")
    p_know.add_argument("--content", help="认知内容")
    p_know.add_argument("--source", help="来源")

    args = parser.parse_args()

    if args.command in ["add-fact", "list-facts", "verify-fact", "update-state",
                        "get-state", "list-states", "report"]:
        ledger = FactLedger(args.novel_id)

        if args.command == "add-fact":
            # FIX 2026-09-30：ValueError（空参/测试源）直接抛给调用方，不再静默写入脏数据
            fid = ledger.add_fact(args.category, args.content, args.source,
                                  allow_test=args.allow_test)
            print(f"✅ 已添事实: {fid}")

        elif args.command == "verify-fact":
            # FIX 2026-09-30：人工确认事实
            if ledger.verify_fact(args.id):
                print(f"✅ {args.id} 已确认为 verified")
            else:
                print(f"❌ 未找到事实 {args.id}")
                sys.exit(1)

        elif args.command == "list-facts":
            facts = ledger.list_facts(args.category, status=args.status)
            print(f"\n📋 事实列表 (共{len(facts)}条):")
            for f in facts:
                mark = "✅" if f.get("status") == "verified" else "⏳"
                print(f"  {mark} [{f['id']}] [{f['category']}] {f['content'][:50]}...")

        elif args.command == "update-state":
            ledger.update_state(args.entity, args.key, args.value)
            print(f"✅ 已更新状态: {args.entity}.{args.key} = {args.value}")

        elif args.command == "get-state":
            val = ledger.get_state(args.entity, args.key)
            print(f"{args.entity}.{args.key} = {val or '无'}")

        elif args.command == "list-states":
            print(f"\n📊 {args.novel_id} 的状态:")
            for entity, keys in ledger.states.items():
                print(f"  {entity}:")
                for k, v in keys.items():
                    print(f"    {k}: {v}")

        elif args.command == "report":
            report = ledger.report()
            print(f"\n📈 统计报告:")
            print(f"  事实总数: {report['total_facts']}")
            print(f"  实体数量: {report['total_entities']}")
            print(f"  分类分布: {json.dumps(report['facts_by_category'], ensure_ascii=False)}")

    elif args.command == "knowledge":
        return knowledge_cmd(args)

    elif args.command == "account":
        return account_cmd(args)

    else:
        parser.print_help()


def knowledge_cmd(args):
    """认知分级命令"""
    ledger = KnowledgeLedger(args.novel_id)

    if args.action == "add":
        if not args.character or not args.content:
            print("❌ 需要 --character 和 --content")
            return 1
        kid = ledger.add(args.character, args.type, args.content, args.source)
        print(f"✅ 已添加认知: {kid}")
        return 0

    elif args.action == "list":
        chars = ledger.get_all(args.character)
        print(f"\n📋 {'角色' + args.character if args.character else '全部'}的认知:")
        for k in chars:
            type_label = {"know": "确知", "believe": "相信",
                          "suspect": "怀疑", "infer": "推断"}
            print(f"  [{type_label.get(k['type'], k['type'])}] {k['content'][:50]}...")
        return 0

    elif args.action == "check":
        conflicts = ledger.check_conflict(args.character)
        if conflicts:
            print(f"\n⚠️ 发现 {len(conflicts)} 个认知冲突:")
            for c in conflicts:
                print(f"  冲突: {c['know']} vs {c['believe']}")
        else:
            print("\n✅ 认知一致性检查通过")
        return 0

    elif args.action == "summary":
        total = len(ledger.data["knowledge"])
        by_type = {}
        for ktype in KNOW_TYPES:
            by_type[ktype] = len([k for k in ledger.data["knowledge"]
                                  if k["type"] == ktype])

        print(f"\n📊 认知统计:")
        print(f"  总计: {total}")
        for ktype, count in by_type.items():
            print(f"  {ktype}: {count}")
        return 0

    else:
        print("❌ 未知操作")
        return 1


if __name__ == "__main__":
    main()
