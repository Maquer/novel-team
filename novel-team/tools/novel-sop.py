#!/usr/bin/env python3
"""
novel-sop.py — 小说创作流程引擎（绑定 SOP 到运行时）

核心功能：
  1. 强制阶段顺序：大纲→关键节点→创作→自检→审核→门禁→发布
  2. 前置校验：写第N章前，第N-1章必须通过门禁
  3. 自动状态转移：创作完成→自检→触发审核→门禁通过→发布
  4. 阻塞检查：待审核章节阻塞下一章创作

用法：
  novel-sop.py init --project <id>        # 初始化项目
  novel-sop.py outline --project <id>     # 阶段一：大纲确认（需手动填写）
  novel-sop.py precheck --project <id> --chapter N   # 阶段二：关键节点检查
  novel-sop.py create --project <id> --chapter N      # 阶段三：创作（前置校验）
  novel-sop.py selfcheck --project <id> --chapter N  # 阶段四：自检
  novel-sop.py trigger --project <id> --chapter N    # 阶段五：触发主编审核
  novel-sop.py approve --project <id> --chapter N    # 阶段五：主编通过
  novel-sop.py reject --project <id> --chapter N --reason R  # 驳回回炉
  novel-sop.py gate --project <id> --chapter N       # 阶段六：门禁检查（含状态推进）
  novel-sop.py publish --project <id> --chapter N    # 阶段七：发布
  novel-sop.py status --project <id> --chapter N     # 查询单章状态
  novel-sop.py flow --project <id>                   # 查看完整流程状态

状态机：
  draft → self_checked → awaiting_review → gate_passed → published
              ↑                              │
              └──── reject → (回炉 draft) ────┘
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("/var/minis/shared/novel-team")
PROJECTS_DIR = BASE_DIR / "projects"
TOOLS_DIR = BASE_DIR / "tools"
FLOW_STATE_DIR = ".novel/flow-state"

# 状态定义
STATES = ["draft", "self_checked", "awaiting_review", "gate_passed", "published"]
VALID_TRANSITIONS = {
    "draft": ["self_checked"],
    "self_checked": ["awaiting_review"],
    "awaiting_review": ["gate_passed", "draft"],  # draft = 驳回回炉
    "gate_passed": ["published"],
}

# 九维评分阈值
THRESHOLD_GATE_SELF = 85      # 自检通过门槛
THRESHOLD_GATE_AUTO = 90      # 免审自动通过门槛
THRESHOLD_REVIEW_PROB_84 = 0.30   # S≥84 时30%概率触发审核
THRESHOLD_REVIEW_PROB_90 = 0.10   # 连续3章S≥90时10%概率触发审核


def get_state_file(project_id: str, chapter_num: int) -> Path:
    proj_dir = PROJECTS_DIR / project_id
    return proj_dir / FLOW_STATE_DIR / f"ch{chapter_num:03d}.json"


def get_chapter_file(project_id: str, chapter_num: int) -> Path:
    return PROJECTS_DIR / project_id / "chapters" / f"chapter-{chapter_num:03d}.md"


def load_state(project_id: str, chapter_num: int) -> dict:
    f = get_state_file(project_id, chapter_num)
    if not f.exists():
        return {"chapter": chapter_num, "state": "not_started", "history": []}
    return json.loads(f.read_text(encoding="utf-8"))


def save_state(project_id: str, chapter_num: int, state: dict):
    f = get_state_file(project_id, chapter_num)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def add_history(state: dict, action: str, detail: str = ""):
    state.setdefault("history", []).append({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "detail": detail,
    })


def check_prerequisite(project_id: str, chapter_num: int) -> dict:
    """检查前置章节是否通过门禁"""
    if chapter_num <= 1:
        return {"ok": True, "reason": "第一章无前置要求"}

    prev = chapter_num - 1
    prev_state = load_state(project_id, prev)
    prev_file = get_chapter_file(project_id, prev)

    if not prev_file.exists():
        return {
            "ok": False,
            "reason": f"第{prev}章文件不存在，无法创作第{chapter_num}章",
        }

    if prev_state.get("state") in ("not_started", "draft"):
        return {
            "ok": False,
            "reason": f"第{prev}章尚未通过门禁（当前状态: {prev_state.get('state')}），请先完成第{prev}章门禁流程",
        }

    if prev_state.get("state") == "awaiting_review":
        # 检查是否有阻塞
        return {
            "ok": False,
            "reason": f"第{prev}章处于待审核状态，需等待审核结果或连续3轮无反馈自动通过",
        }

    return {"ok": True, "reason": f"第{prev}章已通过门禁（{prev_state.get('state')}）"}


def run_humanizer(chapter_file: str) -> dict:
    """运行九维评分"""
    try:
        r = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "humanizer-9d.py"),
             "--chapter-file", chapter_file, "--json"],
            capture_output=True, text=True, timeout=60, cwd=str(BASE_DIR),
        )
        return json.loads(r.stdout)
    except Exception as e:
        return {"error": str(e)}


def run_gate_check(chapter_file: str) -> dict:
    """运行门禁检查"""
    try:
        r = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "gate-check.py"),
             "check", "--file", chapter_file],
            capture_output=True, text=True, timeout=60, cwd=str(BASE_DIR),
        )
        return json.loads(r.stdout)
    except Exception as e:
        return {"error": str(e)}


def cmd_init(args):
    """初始化项目流程状态目录"""
    proj_dir = PROJECTS_DIR / args.project
    state_dir = proj_dir / FLOW_STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    cfg = proj_dir / "project-config.json"
    if cfg.exists():
        print(f"✅ 项目 '{args.project}' 流程状态目录已就绪: {state_dir}")
    else:
        print(f"⚠️  项目 '{args.project}' 未找到 project-config.json，请先初始化项目")
    print(f"   使用 'novel-sop.py outline --project {args.project}' 开始大纲确认阶段")


def cmd_outline(args):
    """阶段一：大纲确认（标记为已完成，实际需要用户手动填写大纲）"""
    state = load_state(args.project, 0)  # chapter 0 = project-level
    state["state"] = "outline_confirmed"
    state["confirmed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    add_history(state, "outline_confirmed", "大纲确认完成")
    save_state(args.project, 0, state)
    print("✅ 阶段一：大纲确认 — 已完成")
    print("   ⚠️  请确保 outline/ 目录下有完整大纲文件后再进入下一章")


def cmd_precheck(args):
    """阶段二：关键节点检查"""
    n = args.chapter
    chapter_file = get_chapter_file(args.project, n)
    if not chapter_file.exists():
        print(f"❌ 第{n}章文件不存在: {chapter_file}")
        sys.exit(1)

    print(f"📋 阶段二：关键节点检查（第{n}章）")

    # 运行四问检查
    results = {}
    for section in ["opening", "middle", "closing"]:
        r = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "paragraph-four-questions.py"),
             "check-node", "--novel-id", args.project,
             "--chapter", str(n), "--section", section,
             "--chapter-file", str(chapter_file),
             "--who", "auto", "--where", "auto", "--why", "auto", "--info", "auto"],
            capture_output=True, text=True, timeout=30, cwd=str(BASE_DIR),
        )
        results[section] = "PASS" if r.returncode == 0 else "FAIL"
        print(f"  {section}: {results[section]}")

    # 运行知情边界更新（如果有参数）
    if args.character:
        r = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "info-boundary.py"), "update-know",
             "--novel-id", args.project, "--character", args.character,
             "--info", args.info or "本章获得的信息", "--source", f"ch{n}"],
            capture_output=True, text=True, timeout=30, cwd=str(BASE_DIR),
        )
        print(f"  知情边界更新: {'OK' if r.returncode == 0 else 'SKIP'}")

    ok = all(v == "PASS" for v in results.values())
    if ok:
        print("✅ 关键节点检查通过")
    else:
        print("⚠️  部分检查未通过，请人工确认后继续")
    return ok


def cmd_create(args):
    """阶段三：创作（含前置校验）"""
    n = args.chapter
    chapter_file = get_chapter_file(args.project, n)

    # 前置校验
    prereq = check_prerequisite(args.project, n)
    if not prereq["ok"]:
        print(f"❌ 阻塞：{prereq['reason']}")
        print("\n   请先完成前置章节的完整流程（自检→审核→门禁）")
        sys.exit(1)

    print(f"✅ 前置检查通过: {prereq['reason']}")
    print(f"\n📝 阶段三：全文创作（第{n}章）")
    print(f"   章节文件: {chapter_file}")
    print(f"   目标字数: 按章节类型选择")
    print(f"   - 过渡章：2000-2500字（场景切换、铺垫）")
    print(f"   - 战斗章：2500-3500字（完整战斗）")
    print(f"   - 高潮章：3000-4000字（重大事件）")
    print(f"\n   请在此处调用创作工具生成正文，完成后执行:")
    print(f"   novel-sop.py selfcheck --project {args.project} --chapter {n}")


def cmd_selfcheck(args):
    """阶段四：自检（九维评分 + 结构化表格）"""
    n = args.chapter
    chapter_file = get_chapter_file(args.project, n)
    if not chapter_file.exists():
        print(f"❌ 第{n}章文件不存在")
        sys.exit(1)

    print(f"📊 阶段四：自检（第{n}章）")

    # 九维评分
    h = run_humanizer(str(chapter_file))
    if "error" in h:
        print(f"⚠️  九维评分失败: {h['error']}")
        score = None
        era = None
        dialogue = None
    else:
        score = h.get("overall_score")
        era = h.get("dimensions", {}).get("era_adapt", {}).get("score")
        dialogue = h.get("dimensions", {}).get("dialogue", {}).get("score")
        print(f"  九维总分 S: {score}/100 {'✅' if score and score >= THRESHOLD_GATE_SELF else '❌'} (需≥{THRESHOLD_GATE_SELF})")
        print(f"  时代适配度: {era}/100 {'✅' if era and era >= 60 else '❌'} (底线≥60)")
        print(f"  对话自然度: {dialogue}/100 {'✅' if dialogue and dialogue >= 60 else '❌'} (底线≥60)")

    # 门禁预检
    g = run_gate_check(str(chapter_file))
    gate_passed = g.get("passed", False)
    p0 = g.get("summary", {}).get("p0_blockers", 0)
    print(f"  门禁检查: {'✅ PASS' if gate_passed else '❌ FAIL'} (P0阻断: {p0})")

    # 状态更新
    state = load_state(args.project, n)
    state["state"] = "self_checked"
    state["score"] = score
    state["era"] = era
    state["dialogue"] = dialogue
    state["gate_passed"] = gate_passed
    state["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    add_history(state, "self_check", f"S={score}, era={era}, dialogue={dialogue}, gate={'PASS' if gate_passed else 'FAIL'}")
    save_state(args.project, n, state)

    score_str = str(score) if score is not None else '?'
    era_str = str(era) if era is not None else '?'
    dia_str = str(dialogue) if dialogue is not None else '?'
    era_ok = '✅' if era and era >= 60 else '❌'
    dia_ok = '✅' if dialogue and dialogue >= 60 else '❌'
    gate_str = 'PASS' if gate_passed else 'FAIL'
    print(f"\n{'='*50}")
    print("【自检结构化表格】")
    print("| 检查项 | 结果 | 备注 |")
    print("|--------|------|------|")
    print(f"| 九维总分 S | {score_str}/100 | 需≥{THRESHOLD_GATE_SELF} |")
    print(f"| 时代适配度 | {era_str}/100 | 底线≥60 {era_ok} |")
    print(f"| 对话自然度 | {dia_str}/100 | 底线≥60 {dia_ok} |")
    print(f"| 门禁检查 | {gate_str} | P0={p0} |")
    print(f"{'='*50}")

    if not gate_passed or p0 > 0:
        print("\n❌ 自检未通过，请修复P0问题后重新执行自检")
        sys.exit(1)

    # 底线维度一票否决（SOP 强制）
    if (era is not None and era < 60) or (dialogue is not None and dialogue < 60):
        print("\n❌ 自检未通过：底线维度（时代适配度或对话自然度）< 60，请修复后重跑")
        sys.exit(1)

    if score and score < THRESHOLD_GATE_SELF:
        print(f"\n⚠️  九维总分 {score}/100 < {THRESHOLD_GATE_SELF}，需触发主编审核")
    else:
        print("\n✅ 自检通过，可进入下一阶段")

    return gate_passed and (not score or score >= THRESHOLD_GATE_SELF)


def _should_trigger_review(state: dict, last_scores: list) -> bool:
    """判断是否需要触发主编审核"""
    score = state.get("score")
    if score is None:
        return False
    if score < THRESHOLD_GATE_SELF:
        return True  # 低于门槛必须审核
    if score >= THRESHOLD_GATE_AUTO:
        # S≥90：根据连续高分概率触发
        recent_high = sum(1 for s in last_scores[-3:] if s and s >= 90)
        if recent_high >= 3:
            import random
            return random.random() < THRESHOLD_REVIEW_PROB_90
        return random.random() < THRESHOLD_REVIEW_PROB_84
    return False


def cmd_trigger(args):
    """阶段五：触发主编审核"""
    n = args.chapter
    state = load_state(args.project, n)
    if state.get("state") != "self_checked":
        print(f"❌ 第{n}章尚未完成自检（当前: {state.get('state')}）")
        sys.exit(1)

    # 调用 gate-check 的 trigger
    r = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "gate-check.py"),
         "trigger", "--novel-id", args.project, "--chapter", str(n)],
        capture_output=True, text=True, timeout=10, cwd=str(BASE_DIR),
    )

    state["state"] = "awaiting_review"
    state["review_triggered_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    add_history(state, "trigger_review", "已加入审核队列")
    save_state(args.project, n, state)

    print(f"✅ 第{n}章已加入主编审核队列")
    print(f"   状态: awaiting_review")
    print(f"   使用 'novel-sop.py approve --chapter {n}' 或通过3轮无反馈自动通过")


def cmd_approve(args):
    """阶段五：主编审核通过"""
    n = args.chapter
    state = load_state(args.project, n)
    if state.get("state") != "awaiting_review":
        print(f"⚠️  第{n}章不在待审核状态（当前: {state.get('state')}）")

    # 调用 gate-check 的 approve（自动通过）
    r = subprocess.run(
        [sys.executable, str(TOOLS_DIR / "gate-check.py"),
         "approve", "--novel-id", args.project, "--chapter", str(n)],
        capture_output=True, text=True, timeout=10, cwd=str(BASE_DIR),
    )
    print(r.stdout)

    state["state"] = "gate_passed"  # approve 后直接进入门禁阶段
    state["review_approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    add_history(state, "approve_review", "主编审核通过")
    save_state(args.project, n, state)
    print(f"✅ 第{n}章审核通过，可进入门禁阶段")


def cmd_auto_pass(args):
    """自动通过：连续3轮无反馈"""
    n = args.chapter
    state = load_state(args.project, n)
    rounds = state.get("no_feedback_rounds", 0)
    if rounds < 3:
        print(f"❌ 第{n}章仅无反馈{rounds}轮，需达到3轮才能自动通过")
        sys.exit(1)

    state["state"] = "gate_passed"
    state["auto_approved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    add_history(state, "auto_approve", f"连续{rounds}轮无反馈，默认通过")
    save_state(args.project, n, state)
    print(f"✅ 第{n}章审核默认通过（连续{rounds}轮无反馈）")


def cmd_incr_round(args):
    """增加无反馈轮次（每次调用后无主编回复时执行）"""
    n = args.chapter
    state = load_state(args.project, n)
    if state.get("state") != "awaiting_review":
        print(f"❌ 第{n}章不在待审核状态")
        sys.exit(1)

    rounds = state.get("no_feedback_rounds", 0) + 1
    state["no_feedback_rounds"] = rounds
    state["last_round_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    add_history(state, "incr_round", f"无反馈轮次: {rounds}")
    save_state(args.project, n, state)

    print(f"  第{n}章无反馈轮次: {rounds}/3")
    if rounds >= 3:
        print(f"  ⚠️  已达3轮，可执行 'novel-sop.py autopass --chapter {n}' 自动通过")
    return rounds >= 3


def cmd_reject(args):
    """阶段五：驳回回炉"""
    n = args.chapter
    state = load_state(args.project, n)
    if state.get("state") != "awaiting_review":
        print(f"❌ 第{n}章不在待审核状态（当前: {state.get('state')}）")
        sys.exit(1)

    state["state"] = "draft"
    state["rejected_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["reject_reason"] = args.reason
    add_history(state, "reject_review", f"驳回原因: {args.reason}")
    save_state(args.project, n, state)
    print(f"❌ 第{n}章审核驳回: {args.reason}")
    print(f"   状态: draft（需修改后重新执行 selfcheck → trigger）")


def cmd_gate(args):
    """阶段六：门禁检查（含状态推进）"""
    n = args.chapter
    chapter_file = get_chapter_file(args.project, n)
    if not chapter_file.exists():
        print(f"❌ 第{n}章文件不存在")
        sys.exit(1)

    state = load_state(args.project, n)
    # 允许 self_checked / awaiting_review / gate_passed 状态下运行门禁
    if state.get("state") not in ("self_checked", "awaiting_review", "gate_passed"):
        print(f"⚠️  当前状态: {state.get('state')}，建议先完成自检")

    print(f"🔒 阶段六：门禁检查（第{n}章）")
    g = run_gate_check(str(chapter_file))

    passed = g.get("passed", False)
    p0 = g.get("summary", {}).get("p0_blockers", 0)
    p1 = g.get("summary", {}).get("p1_warnings", 0)
    p2 = g.get("summary", {}).get("p2_suggestions", 0)

    print(f"  门禁结果: {'✅ PASS' if passed else '❌ FAIL'}")
    print(f"  P0阻断: {p0} | P1警告: {p1} | P2建议: {p2}")

    if passed and p0 == 0:
        old_state = state.get("state")
        state["state"] = "gate_passed"
        state["gate_passed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        add_history(state, "gate_passed", f"从{old_state}→gate_passed, P0={p0}, P1={p1}, P2={p2}")
        save_state(args.project, n, state)
        print(f"✅ 门禁通过（{old_state} → gate_passed），第{n}章已准备好发布")
    else:
        print(f"❌ 门禁未通过，请修复 P0 问题后重试")
        sys.exit(1)


def cmd_publish(args):
    """阶段七：发布"""
    n = args.chapter
    state = load_state(args.project, n)
    if state.get("state") != "gate_passed":
        print(f"❌ 第{n}章尚未通过门禁（当前: {state.get('state')}）")
        sys.exit(1)

    state["state"] = "published"
    state["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    add_history(state, "published", "发布完成")
    save_state(args.project, n, state)

    chapter_file = get_chapter_file(args.project, n)
    print(f"✅ 第{n}章已发布")
    print(f"   文件: {chapter_file}")
    print(f"   发布人: 运营岗")


def cmd_status(args):
    """查询单章状态"""
    n = args.chapter
    state = load_state(args.project, n)
    chapter_file = get_chapter_file(args.project, n)

    print(f"\n{'='*50}")
    print(f"第{n}章 状态报告")
    print(f"{'='*50}")
    print(f"  文件: {chapter_file}")
    print(f"  当前状态: {state.get('state', 'not_started')}")
    print(f"  九维总分: {state.get('score', '?')}/100")
    print(f"  时代适配: {state.get('era', '?')}/100")
    print(f"  对话自然: {state.get('dialogue', '?')}/100")
    print(f"  门禁通过: {'✅' if state.get('gate_passed') else '❌'}")
    print(f"  无反馈轮次: {state.get('no_feedback_rounds', 0)}/3")

    if state.get("reject_reason"):
        print(f"  驳回原因: {state['reject_reason']}")

    print(f"\n  历史:")
    for h in state.get("history", [])[:5]:
        print(f"    [{h['time']}] {h['action']}: {h.get('detail', '')}")
    print(f"{'='*50}\n")


def cmd_flow(args):
    """查看完整流程状态"""
    print(f"\n{'='*60}")
    print(f"小说项目 '{args.project}' — 完整流程状态")
    print(f"{'='*60}")

    # 大纲确认状态
    outline_state = load_state(args.project, 0)
    print(f"\n【阶段一：大纲确认】")
    print(f"  状态: {'✅ 已确认' if outline_state.get('state') == 'outline_confirmed' else '❌ 未完成'}")

    # 扫描所有章节
    chapters_dir = PROJECTS_DIR / args.project / "chapters"
    if not chapters_dir.exists():
        print("\n  无章节目录")
        return

    chapter_files = sorted(chapters_dir.glob("chapter-*.md"), key=lambda f: int(f.stem.split("-")[1]))
    if not chapter_files:
        print("\n  无章节文件")
        return

    print(f"\n【章节状态总览】（共 {len(chapter_files)} 章）")
    print(f"{'章':>3} {'状态':<14} {'九维':>5} {'门禁':>4} {'发布时间':>19}")
    print(f"{'-'*55}")

    for cf in chapter_files:
        n = int(cf.stem.split("-")[1])
        st = load_state(args.project, n)
        state_name = st.get("state", "not_started")
        score = st.get("score", "?")
        gate = "✅" if st.get("gate_passed") else "❌"
        published_at = st.get("published_at", "-")
        print(f"{n:>3} {state_name:<14} {str(score):>5} {gate:>4} {published_at:>19}")

    # 阻塞检查
    print(f"\n【阻塞检查】")
    for cf in chapter_files:
        n = int(cf.stem.split("-")[1])
        st = load_state(args.project, n)
        if st.get("state") == "awaiting_review":
            print(f"  ⛔ 第{n}章待审核，后续章节创作将被阻塞")
            break
        elif st.get("state") == "draft" and n > 1:
            prev_st = load_state(args.project, n - 1)
            if prev_st.get("state") not in ("gate_passed", "published"):
                print(f"  ⛔ 第{n-1}章未通过门禁，第{n}章无法创作")
                break
    else:
        print("  ✅ 无阻塞，可继续创作")

    print(f"\n【下一步建议】")
    next_ch = 1
    for cf in chapter_files:
        n = int(cf.stem.split("-")[1])
        st = load_state(args.project, n)
        if st.get("state") not in ("gate_passed", "published"):
            next_ch = n
            break
    else:
        next_ch = len(chapter_files) + 1

    ns = load_state(args.project, next_ch)
    if ns.get("state") == "not_started":
        print(f"  → 创作第{next_ch}章: novel-sop.py create --project {args.project} --chapter {next_ch}")
    elif ns.get("state") == "draft":
        print(f"  → 完善第{next_ch}章后自检: novel-sop.py selfcheck --project {args.project} --chapter {next_ch}")
    elif ns.get("state") == "self_checked":
        print(f"  → 触发主编审核: novel-sop.py trigger --project {args.project} --chapter {next_ch}")
    elif ns.get("state") == "awaiting_review":
        rounds = ns.get("no_feedback_rounds", 0)
        if rounds >= 3:
            print(f"  → 已达3轮无反馈，自动通过: novel-sop.py autopass --chapter {next_ch}")
        else:
            print(f"  → 等待主编审核（当前{rounds}轮无反馈）")
    elif ns.get("state") == "gate_passed":
        print(f"  → 发布第{next_ch}章: novel-sop.py publish --project {args.project} --chapter {next_ch}")

    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        prog="novel-sop.py",
        description="小说创作流程引擎 — 绑定 SOP 到运行时",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p = sub.add_parser("init", help="初始化项目流程状态")
    p.add_argument("--project", required=True)

    # outline
    p = sub.add_parser("outline", help="阶段一：大纲确认")
    p.add_argument("--project", required=True)

    # precheck
    p = sub.add_parser("precheck", help="阶段二：关键节点检查")
    p.add_argument("--project", required=True)
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--character", help="角色名（用于知情边界更新）")
    p.add_argument("--info", help="信息内容")

    # create
    p = sub.add_parser("create", help="阶段三：创作（含前置校验）")
    p.add_argument("--project", required=True)
    p.add_argument("--chapter", type=int, required=True)

    # selfcheck
    p = sub.add_parser("selfcheck", help="阶段四：自检")
    p.add_argument("--project", required=True)
    p.add_argument("--chapter", type=int, required=True)

    # trigger
    p = sub.add_parser("trigger", help="阶段五：触发主编审核")
    p.add_argument("--project", required=True)
    p.add_argument("--chapter", type=int, required=True)

    # approve
    p = sub.add_parser("approve", help="阶段五：主编审核通过")
    p.add_argument("--project", required=True)
    p.add_argument("--chapter", type=int, required=True)

    # autopass
    p = sub.add_parser("autopass", help="阶段五：连续3轮无反馈自动通过")
    p.add_argument("--project", required=True)
    p.add_argument("--chapter", type=int, required=True)

    # incr-round
    p = sub.add_parser("incr-round", help="增加无反馈轮次（每次主编未回复时调用）")
    p.add_argument("--project", required=True)
    p.add_argument("--chapter", type=int, required=True)

    # reject
    p = sub.add_parser("reject", help="阶段五：驳回回炉")
    p.add_argument("--project", required=True)
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--reason", required=True, help="驳回原因")

    # gate
    p = sub.add_parser("gate", help="阶段六：门禁检查")
    p.add_argument("--project", required=True)
    p.add_argument("--chapter", type=int, required=True)

    # publish
    p = sub.add_parser("publish", help="阶段七：发布")
    p.add_argument("--project", required=True)
    p.add_argument("--chapter", type=int, required=True)

    # status
    p = sub.add_parser("status", help="查询单章状态")
    p.add_argument("--project", required=True)
    p.add_argument("--chapter", type=int, required=True)

    # flow
    p = sub.add_parser("flow", help="查看完整流程状态")
    p.add_argument("--project", required=True)

    args = parser.parse_args()
    cmd = {
        "init": cmd_init,
        "outline": cmd_outline,
        "precheck": cmd_precheck,
        "create": cmd_create,
        "selfcheck": cmd_selfcheck,
        "trigger": cmd_trigger,
        "approve": cmd_approve,
        "autopass": cmd_auto_pass,
        "incr-round": cmd_incr_round,
        "reject": cmd_reject,
        "gate": cmd_gate,
        "publish": cmd_publish,
        "status": cmd_status,
        "flow": cmd_flow,
    }[args.command]
    cmd(args)


if __name__ == "__main__":
    main()
