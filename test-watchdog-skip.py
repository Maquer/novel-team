#!/usr/bin/env python3
# Version: 0.1.0
"""model-watchdog --skip-dead 黄金测试：已知输入 → 断言已知输出，不联网。"""
import sys, importlib.util
from datetime import datetime, timezone, timedelta

spec = importlib.util.spec_from_file_location("mw", "/var/minis/shared/model-watchdog.py")
mw = importlib.util.module_from_spec(spec)
sys.argv = ["mw"]
spec.loader.exec_module(mw)

def iso(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

PASS, FAIL = [], []
def check(name, got, want):
    (PASS if got == want else FAIL).append(f"{name}: got={got} want={want}")

# --- _decide_skip 判定表 ---
p_ok        = {"status": "ok",            "probed_at": iso(10), "changed_at": iso(10)}
p_key_5d    = {"status": "invalid_key",   "probed_at": iso(5),  "changed_at": iso(5)}
p_key_1d    = {"status": "invalid_key",   "probed_at": iso(1),  "changed_at": iso(1)}
p_key_40d   = {"status": "invalid_key",   "probed_at": iso(1),  "changed_at": iso(40)}
p_key_nohis = {"status": "invalid_key"}
p_rate_10d  = {"status": "rate_limited",  "probed_at": iso(10), "changed_at": iso(10)}
p_timeout   = {"status": "timeout",       "probed_at": iso(10), "changed_at": iso(10)}
p_nf_5d     = {"status": "not_found",     "probed_at": iso(5),  "changed_at": iso(5)}
p_skip_key  = {"status": "skipped", "prev_status": "invalid_key",
               "probed_at": iso(5), "changed_at": iso(5)}

check("skip_days=0 全探测",        mw._decide_skip("m", {"m": p_key_5d}, 0),  False)
check("新模型无历史不跳过",         mw._decide_skip("m", {}, 3),               False)
check("ok 状态永不跳过",           mw._decide_skip("m", {"m": p_ok}, 3),      False)
check("永久失效5天>=3 → 跳过",     mw._decide_skip("m", {"m": p_key_5d}, 3),  True)
check("永久失效仅1天<3 → 探测",    mw._decide_skip("m", {"m": p_key_1d}, 3),  False)
check("持续40天 → 强制复测",       mw._decide_skip("m", {"m": p_key_40d}, 3), False)
check("无 changed_at → 探测",      mw._decide_skip("m", {"m": p_key_nohis}, 3), False)
check("瞬时 rate_limited 不跳过",  mw._decide_skip("m", {"m": p_rate_10d}, 3), False)
check("瞬时 timeout 不跳过",       mw._decide_skip("m", {"m": p_timeout}, 3),  False)
check("not_found 5天 → 跳过",      mw._decide_skip("m", {"m": p_nf_5d}, 3),   True)
check("上轮skipped 按其真实状态跳过", mw._decide_skip("m", {"m": p_skip_key}, 3), True)

# --- detect_changes: skipped 不得伪造告警 ---
prev = {"m": dict(p_key_5d, tier=1, label="x", provider="P")}
cur  = {"m": dict(p_key_5d, tier=1, label="x", provider="P",
                  status="skipped", prev_status="invalid_key")}
ch = mw.detect_changes(cur, prev)[0]
check("skipped → unchanged",     ch["change_type"], "unchanged")
check("skipped 不改写 new_status", ch["new_status"], "invalid_key")

# --- summarize: skipped 不进 unavailable ---
s = mw.summarize({"a": {"status": "ok", "tier": 0, "provider": "P"},
                  "b": {"status": "skipped", "tier": 1, "provider": "P"},
                  "c": {"status": "timeout", "tier": 1, "provider": "P"}})
check("alive 只数 ok",        s["available_count"], 1)
check("skipped 不算异常",      s["unavailable_count"], 1)
check("skipped 单独计数",      s["skipped_count"], 1)

# --- 真实 state 回归：当前 101 模型在 skip_days=3 下的跳过数应为 0
#     (本轮所有失效模型的 changed_at 都是刚刚写入的，未满 3 天 → 全部重探)
live = mw.load_current()
n_skip = sum(1 for mid in live if mw._decide_skip(mid, live, 3))
check("真实state skip_days=3 首轮跳过0（防刚失效即盲）", n_skip, 0)
n_skip30 = sum(1 for mid in live if mw._decide_skip(mid, live, 0))
check("skip_days=0 跳过0", n_skip30, 0)

print(f"✅ PASS {len(PASS)}")
for f in FAIL:
    print("❌", f)
print(f"总计 {len(PASS)+len(FAIL)}，失败 {len(FAIL)}")
sys.exit(1 if FAIL else 0)
