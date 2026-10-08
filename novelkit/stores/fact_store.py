"""FactStore — 事实账本访问层。

从 tools/fact-ledger.py 的 FactLedger 迁移而来，语义原样保留
（含 2026-09-30 全量修复：max+1 ID 分配、测试源黑名单、status 状态机、
原子写 tmp+replace、历史数据缺 status 视为 unverified）。

两处与 v1 不同的地方（有意为之，已评审）：
1. 路径：v1 FactLedger 把根路径硬编码为 /var/minis/shared/novel-team，
   无视 NOVEL_TEAM_ROOT（tools/fact-ledger.py:41，而它自己的注释却写着
   "代际项目守卫（唯一路径入口）"）。此处改走 novelkit.core.config.novel_team_root()，
   路径约定本身不变（<root>/ledger/<novel_id>/facts.json），与 gate-check
   的读取路径（gate-check.py:401）保持一致。在 OpenMinis 生产环境
   （NOVEL_TEAM_ROOT 未设置）行为与 v1 完全一致。
2. _sync 事件发射的目标目录：v1 写 <repo>/.events/，此处保持。

注意：事实账本使用全局 ledger 目录，不走 project_guard 的代际目录——
这是为了与 gate-check 的读取路径一致（v1 审计时已统一过一次，不再改）。
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from novelkit.core.config import novel_team_root


class FactStore:
    """事实账本。"""

    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        base = novel_team_root() / "ledger" / novel_id
        self.facts_path = base / "facts.json"
        self.states_path = base / "states.json"
        self.facts_path.parent.mkdir(parents=True, exist_ok=True)
        self.facts: Dict[str, Dict] = self._load_json(self.facts_path)
        self.states: Dict[str, Dict] = self._load_json(self.states_path)

    # --- IO ---

    def _load_json(self, path: Path) -> Dict:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _save_json(self, path: Path, data: Dict):
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    # --- 事实 ---

    def _next_fact_num(self) -> int:
        nums = []
        for fid in self.facts.keys():
            if fid.startswith("F") and fid[1:].isdigit():
                nums.append(int(fid[1:]))
        return max(nums, default=0) + 1

    @staticmethod
    def _is_test_source(source: str) -> bool:
        s = (source or "").strip()
        if not s:
            return False
        if s.lower() == "test":
            return True
        if "测试" in s:
            return True
        return False

    def add_fact(self, category: str, content: str, source: str = "",
                 allow_test: bool = False) -> str:
        """添加事实。返回事实 ID（如 F0001）。"""
        if not (category or "").strip():
            raise ValueError("category 不能为空")
        if not (content or "").strip():
            raise ValueError("content 不能为空")
        if not allow_test and self._is_test_source(source):
            raise ValueError(
                f"source '{source}' 命中测试源黑名单，拒绝写入"
                f"（如确需写入请传 allow_test=True）"
            )
        fact_id = f"F{self._next_fact_num():04d}"
        fact = {
            "id": fact_id,
            "category": category,
            "content": content,
            "source": source,
            "status": "unverified",
            "created_at": datetime.now().isoformat(),
            "verified": False,
        }
        self.facts[fact_id] = fact
        self._save_json(self.facts_path, self.facts)
        self._emit_event("FACT_ADDED", fact_id=fact_id, category=category,
                         content=content[:200])
        return fact_id

    def list_facts(self, category: str = None, status: str = None) -> List[Dict]:
        facts = list(self.facts.values())
        if category:
            facts = [f for f in facts if f["category"] == category]
        if status:
            facts = [f for f in facts if f.get("status", "unverified") == status]
        return facts

    def verify_fact(self, fact_id: str) -> bool:
        fact = self.facts.get(fact_id)
        if not fact:
            return False
        fact["status"] = "verified"
        fact["verified"] = True
        fact["verified_at"] = datetime.now().isoformat()
        self._save_json(self.facts_path, self.facts)
        return True

    # --- 状态 / 账目 ---

    def update_state(self, entity: str, key: str, value: str):
        if entity not in self.states:
            self.states[entity] = {}
        self.states[entity][key] = value
        self._save_json(self.states_path, self.states)

    def get_state(self, entity: str, key: str) -> Optional[str]:
        return self.states.get(entity, {}).get(key)

    def add_account(self, entity: str, item: str, quantity: int, source: str = ""):
        key = f"{entity}:{item}"
        if key not in self.states:
            self.states[key] = {"entity": entity, "item": item,
                                "quantity": 0, "history": []}
        old_qty = self.states[key]["quantity"]
        new_qty = old_qty + quantity
        self.states[key]["quantity"] = new_qty
        self.states[key]["history"].append({
            "change": quantity,
            "old": old_qty,
            "new": new_qty,
            "source": source,
            "timestamp": datetime.now().isoformat(),
        })
        self._save_json(self.states_path, self.states)

    def check_account_jump(self, entity: str, item: str,
                           allowed_jump_ratio: float = 0.5) -> Optional[str]:
        key = f"{entity}:{item}"
        if key not in self.states:
            return None
        history = self.states[key].get("history", [])
        if len(history) < 2:
            return None
        old_qty, new_qty = history[-2]["new"], history[-1]["new"]
        if old_qty == 0:
            return None
        jump_ratio = abs(new_qty - old_qty) / abs(old_qty)
        if jump_ratio > allowed_jump_ratio:
            return (f"账目跳变检测: {entity}:{item} 从 {old_qty} 变为 {new_qty} "
                    f"(跳变{jump_ratio * 100:.1f}%)")
        return None

    def report(self) -> Dict:
        counts: Dict[str, int] = {}
        for f in self.facts.values():
            cat = f["category"]
            counts[cat] = counts.get(cat, 0) + 1
        return {
            "novel_id": self.novel_id,
            "total_facts": len(self.facts),
            "total_entities": len(self.states),
            "facts_by_category": counts,
        }

    # --- 内部 ---

    def _emit_event(self, event: str, **payload):
        """事件发射：失败不阻塞主流程（v1 语义保留）。"""
        try:
            events_dir = Path(__file__).resolve().parents[2] / ".events"
            events_dir.mkdir(parents=True, exist_ok=True)
            evt = {"event": event, "timestamp": datetime.now().isoformat(),
                   **payload}
            with open(events_dir / f"{self.novel_id}.jsonl", "a",
                       encoding="utf-8") as f:
                f.write(json.dumps(evt, ensure_ascii=False) + "\n")
        except Exception:
            pass
