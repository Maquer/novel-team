"""DebtStore — 质量债务账本访问层。

从 tools/quality-debt.py 迁移而来，语义原样保留（含四档质量分类、
阻断级别、gate_result_to_debt 映射规则、QD-{chapter}-{n:03d} ID 分配、
total_open/total_resolved 重算）。

与 v1 不同的地方（有意为之，已评审）：
1. 路径：v1 quality-debt.py 把 BASE_DIR 硬编码为 /var/minis/shared/novel-team
   （tools/quality-debt.py:22），无视 NOVEL_TEAM_ROOT——与 fact-ledger 的 D3
   同类 bug。此处改走 novelkit.core.config.novel_team_root()，
   路径约定本身不变（<root>/ledger/<novel_id>/quality-debt.json）。
   在 OpenMinis 生产环境（NOVEL_TEAM_ROOT 未设置）行为与 v1 完全一致。
2. 写盘改为原子写（tmp+replace），参照 FactStore._save_json；
   v1 直接 write_text，崩溃时可能留下半截 JSON。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from novelkit.core.config import novel_team_root

# 只有这两档阻断创作流程
BLOCKING_LEVELS = {"stop_for_replan", "data_integrity_failure"}

# 四档非阻断质量债务
DEBT_LEVELS = ["local_patch_plan", "continue_with_warning",
               "patchable_obligation_gap", "defer_and_continue"]

LEVEL_DESCRIPTIONS = {
    "local_patch_plan": "本章小修可解决，建议立即修复后继续",
    "continue_with_warning": "问题已记录，不修复即进入下一章",
    "patchable_obligation_gap": "未来章节弥补，当前不阻断",
    "defer_and_continue": "低优先级，静默记录",
    "stop_for_replan": "剧情方向需要重新规划，必须停止",
    "data_integrity_failure": "数据账本损坏，无法继续创作",
}


class DebtStore:
    """质量债务账本。

    四档分类（借鉴 Biz Novel Studio）：
      local_patch_plan         — 本章小修可解决 → 继续下一章
      continue_with_warning    — 记录在案，暂不修复 → 继续下一章
      patchable_obligation_gap — 未来章节弥补 → 继续下一章
      defer_and_continue       — 低优先级，静默记录 → 继续下一章
    两种阻断：
      stop_for_replan          — 需要重新规划（剧情方向问题）
      data_integrity_failure   — 数据账本损坏，无法继续
    """

    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.debt_path = novel_team_root() / "ledger" / novel_id / "quality-debt.json"
        self.debt_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict = self._load()

    # --- IO ---

    def _load(self) -> Dict:
        if self.debt_path.exists():
            return json.loads(self.debt_path.read_text(encoding="utf-8"))
        return {"chapter_debts": {}, "total_open": 0, "total_resolved": 0}

    def _save(self):
        tmp = self.debt_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(self.debt_path)

    def _recount_open(self):
        self._data["total_open"] = sum(
            1 for debts in self._data["chapter_debts"].values()
            for d in debts if d["status"] == "open")

    # --- 债务 ---

    def add_debt(self, chapter: int, level: str, description: str,
                 gate_name: str = "") -> Dict:
        """添加一条质量债务，返回 {"entry", "blocking", "continue_creation", "suggestion"}。"""
        if level not in BLOCKING_LEVELS and level not in DEBT_LEVELS:
            raise ValueError(
                f"未知级别: {level}，可选: {DEBT_LEVELS + list(BLOCKING_LEVELS)}")

        key = str(chapter)
        if key not in self._data["chapter_debts"]:
            self._data["chapter_debts"][key] = []

        entry = {
            "id": f"QD-{chapter}-{len(self._data['chapter_debts'][key])+1:03d}",
            "chapter": chapter,
            "level": level,
            "gate_name": gate_name,
            "description": description,
            "status": "open",
            "created_at": datetime.now().isoformat(),
            "resolved_at": None,
        }
        self._data["chapter_debts"][key].append(entry)
        self._recount_open()
        self._save()

        blocking = level in BLOCKING_LEVELS
        return {
            "entry": entry,
            "blocking": blocking,
            "continue_creation": not blocking,
            "suggestion": LEVEL_DESCRIPTIONS.get(level, ""),
        }

    def resolve_debt(self, debt_id: str, note: str = "") -> Dict:
        """标记债务已修复。返回 {"ok", "debt"} 或 {"ok": False, "error"}。"""
        for chapter_key, debts in self._data["chapter_debts"].items():
            for d in debts:
                if d["id"] == debt_id:
                    d["status"] = "resolved"
                    d["resolved_at"] = datetime.now().isoformat()
                    d["resolve_note"] = note
                    self._recount_open()
                    self._data["total_resolved"] = \
                        self._data.get("total_resolved", 0) + 1
                    self._save()
                    return {"ok": True, "debt": d}
        return {"ok": False, "error": f"未找到债务 {debt_id}"}

    def list_debts(self, chapter: int = None,
                   status: str = "open") -> List[Dict]:
        """列出债务。status 可选 open / resolved / all；按创建时间倒序。"""
        result = []
        chapters = [str(chapter)] if chapter else \
            list(self._data["chapter_debts"].keys())
        for ck in chapters:
            for d in self._data["chapter_debts"].get(ck, []):
                if status == "all" or d["status"] == status:
                    result.append(d)
        return sorted(result, key=lambda x: x["created_at"], reverse=True)

    def gate_result_to_debt(self, gate_result: Dict, chapter: int) -> Dict:
        """将门禁结果转换为质量债务，返回是否可继续。

        映射规则（借鉴 Biz Novel Studio Quality Gate）：
          P0 fail (ai_tone, fact_consistency)  → local_patch_plan（继续）
          P0 fail (character_consistency)      → local_patch_plan（继续）
          P1 fail/warning                      → continue_with_warning
          P2 fail/warning                      → defer_and_continue
          数据账本损坏                          → data_integrity_failure（阻断）
          用户明确要求重新规划                   → stop_for_replan（阻断）
        """
        if gate_result.get("data_integrity_error"):
            self.add_debt(chapter, "data_integrity_failure",
                          gate_result.get("error", "账本数据损坏"))
            return {"continue_creation": False, "reason": "data_integrity_failure"}

        debts_added = []
        p0_fails = gate_result.get("p0_failures", [])
        p1_warns = gate_result.get("p1_warnings", [])
        p2_sugs = gate_result.get("p2_suggestions", [])

        for f in p0_fails:
            r = self.add_debt(chapter, "local_patch_plan", str(f))
            debts_added.append(r["entry"]["id"])

        for w in p1_warns:
            r = self.add_debt(chapter, "continue_with_warning", str(w))
            debts_added.append(r["entry"]["id"])

        for s in p2_sugs:
            r = self.add_debt(chapter, "defer_and_continue", str(s))
            debts_added.append(r["entry"]["id"])

        blocking = any(
            LEVEL_DESCRIPTIONS.get(
                next((d["level"] for d in
                      self._data["chapter_debts"].get(str(chapter), [])
                      if d["id"] == did), ""), "") in BLOCKING_LEVELS
            for did in debts_added
        ) if debts_added else False

        return {
            "continue_creation": True,   # 四档质量债务不阻断
            "blocking": blocking,
            "debts_added": len(debts_added),
            "debt_ids": debts_added,
            "summary": f"第{chapter}章新增 {len(debts_added)} 条质量债务，创作流程继续",
        }

    # --- 统计 ---

    def stats(self) -> Dict:
        """账本统计：未解决/已解决数 + 未解决按级别分布。"""
        by_level: Dict[str, int] = {}
        for debts in self._data["chapter_debts"].values():
            for d in debts:
                if d["status"] == "open":
                    by_level[d["level"]] = by_level.get(d["level"], 0) + 1
        return {
            "novel_id": self.novel_id,
            "total_open": self._data.get("total_open", 0),
            "total_resolved": self._data.get("total_resolved", 0),
            "open_by_level": by_level,
        }
