#!/usr/bin/env python3
"""
outline-precheck.py 回归测试（反向断言优先）

用法：python3 tools/test-outline-precheck.py
退出码：0=全部通过；1=有回归（改 outline-precheck.py 后必跑）

断言设计（badcase 必须全部被抓到，正向必须不报）：
  B1 破冰失败（前3章无L2+）        必须报警
  B2 压抑超限（连续3章无正反馈）    必须报警
  B3 里程碑缺失（连续6+章仅L1）     必须报警
  B4 爽点疲劳（连续3章L4）          必须报警
  B5 卷缺L4                        必须报警
  G1 健康大纲（交替节拍）           必须 0 节拍类警告
  N1 未标注大纲                     必须报"跳过"而非崩溃
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
TOOL = HERE / "outline-precheck.py"

PASS, FAIL = 0, []


def run_beats(chapters, vol_title="测试卷"):
    proj = Path(tempfile.mkdtemp()) / "proj"
    (proj / "outline").mkdir(parents=True)
    outline = {"project_id": "t", "volumes": [
        {"num": 1, "title": vol_title, "chapters": chapters}]}
    (proj / "outline" / "outline.json").write_text(
        json.dumps(outline, ensure_ascii=False), encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(TOOL), "beats", "--project", str(proj)],
        capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(f"tool crashed: {out.stderr[:300]}")
    return json.loads(out.stdout)


def expect(cond, name, detail=""):
    global PASS
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL.append(name)
        print(f"  ❌ {name} {detail}")


def ch(num, thrill, depress=False):
    c = {"num": num, "title": f"第{num}章", "summary": "t", "thrill": thrill}
    if depress:
        c["depress"] = True
    return c


def msgs(r):
    return " | ".join(r["warnings"] + r["risks"])


print("== 反向断言（badcase 必须被抓到）==")

# B1-B5 复合坏样本（卷1：破冰失败/压抑超限/里程碑缺失/L4疲劳；卷2：缺L4）
bad = []
bad += [ch(n, "L1") for n in range(1, 4)]           # B1
bad += [ch(n, "L1", depress=True) for n in range(4, 7)]   # B2
bad += [ch(n, "L1") for n in range(7, 14)]          # B3
bad += [ch(n, "L4") for n in range(14, 17)]         # B4
bad += [ch(n, "L2") for n in range(17, 21)]
r = run_beats(bad)
m = msgs(r)
expect("破冰失败" in m, "B1 破冰失败被抓到")
expect("压抑超限" in m, "B2 压抑超限被抓到")
expect("里程碑缺失" in m, "B3 里程碑缺失被抓到")
expect("爽点疲劳" in m, "B4 爽点疲劳被抓到")

vol2 = [ch(n, "L2") for n in range(1, 16)]          # 15章全L2 → B5 卷缺L4
proj2 = Path(tempfile.mkdtemp()) / "proj"
(proj2 / "outline").mkdir(parents=True)
(proj2 / "outline" / "outline.json").write_text(json.dumps(
    {"volumes": [{"num": 2, "title": "无L4卷",
                  "chapters": [dict(c, num=n) for n, c in enumerate(vol2, 1)]}]},
    ensure_ascii=False), encoding="utf-8")
out = subprocess.run([sys.executable, str(TOOL), "beats", "--project", str(proj2)],
                     capture_output=True, text=True, timeout=30)
m2 = msgs(json.loads(out.stdout))
expect("L4格局跃迁" in m2, "B5 卷缺L4被抓到")

print("== 正向断言（健康大纲不得误报）==")
good = [ch(1, "L3"), ch(2, "L1"), ch(3, "L2")]          # 破冰OK
good += [ch(n, "L1") for n in range(4, 8)]
good.append(ch(8, "L2"))                                  # 里程碑OK
good += [ch(n, "L1") for n in range(9, 13)]
good.append(ch(13, "L3"))
good += [ch(n, "L1") for n in range(14, 18)]
good.append(ch(18, "L2"))
good += [ch(n, "L1") for n in range(19, 23)]
good.append(ch(23, "L4"))                                 # 卷末L4 OK
r = run_beats(good)
beat_warns = [w for w in r["warnings"]
              if any(k in w for k in ("破冰", "压抑", "里程碑", "疲劳", "格局跃迁"))]
expect(not beat_warns, "G1 健康大纲 0 节拍误报", str(beat_warns))

print("== 边界（未标注大纲 → 跳过不崩溃）==")
r = run_beats([ch(n, "") for n in range(1, 6)])
expect("跳过" in msgs(r), "N1 未标注大纲报跳过")

print(f"\n结果: {PASS} 通过 / {len(FAIL)} 失败")
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
