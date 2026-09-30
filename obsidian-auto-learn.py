#!/usr/bin/env python3
# Version: 0.1.0
"""
Obsidian 自动学习管道 — 扫描新/已修改笔记 → 摩擦度评分 → 路由 → 蒸馏 → 审核 → 归档 → 升级等级。

全自动运行，无需人工干预：
  1. 扫描 Obsidian 中新增或修改的笔记（与上次扫描比对 mtime）
  2. 摩擦度评分（借鉴 TeamAI 的 Session Friction 设计）——判断是否有学习价值
  3. 根据摩擦度路由：高摩擦→完整蒸馏 / 中摩擦→降阈值蒸馏 / 低摩擦→仅摘要 / 零摩擦→跳过
  4. 自动评分（内容质量）并决定是否批准
  5. 已批准的卡片自动归档到对应 PARA 目录
  6. 根据学习活跃度自动升级 Obsidian 等级

用法:
  python3 /var/minis/shared/obsidian-auto-learn.py
  python3 /var/minis/shared/obsidian-auto-learn.py --force  # 强制重新扫描全部笔记
  python3 /var/minis/shared/obsidian-auto-learn.py --dry-run  # 仅预览，不写入
  python3 /var/minis/shared/obsidian-auto-learn.py --json
"""

import json, os, sys
from datetime import datetime

# 摩擦度评分模块（借鉴 TeamAI 的 Session Friction 设计）
import importlib.util
_friction_spec = importlib.util.spec_from_file_location('friction_score', '/var/minis/shared/friction-score.py')
_friction_mod = importlib.util.module_from_spec(_friction_spec)
_friction_spec.loader.exec_module(_friction_mod)


OBSIDIAN_ROOT = "/var/minis/mounts/loong"
STATE_FILE = "/var/minis/shared/.auto-learn-state.json"
DASHBOARD = sys.modules.get("second_brain_dashboard")

# 自动批准阈值：内容长度 ≥ 80 字 + 含至少 1 条主张
AUTO_APPROVE_MIN_SCORE = 80
AUTO_APPROVE_MIN_LEN = 80
AUTO_APPROVE_MIN_CLAIMS = 1

# 渐进式策略模式
MODES = {
    "manual": {"label": "手动", "desc": "仅建议，全部等待人工确认"},
    "semi": {"label": "半自动", "desc": "高频模式自动批，低频/边界待人工确认"},
    "auto": {"label": "全自动", "desc": "当前行为 — 达到阈值自动批准"},
}
# 2026-09-04 变更：默认从 auto 改为 manual，避免自动批量蒸馏污染 PARA 目录
# 之前 13 天堆积 234 个未审核 draft 卡片（已批量清理），根本原因是 DEFAULT_MODE="auto" 静默批准归档
# 想自动批时使用: python3 obsidian-auto-learn.py --mode semi / --mode auto
DEFAULT_MODE = "manual"

# 归档路径推断（按优先级）
DIR_HINTS = [
    (["AI", "Agent", "工具", "Pi", "MCP", "编程"], "03-Resources/AI工具"),
    (["公众号", "排版", "微信"], "03-Resources/公众号文章"),
    (["认知", "框架", "方法", "原理", "大脑", "决策"], "02-Areas/认知思考"),
    (["项目"], "01-Projects"),
    (["日志", "日记", "回顾"], "04-Archives"),
]


def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"scanned": {}, "auto_approved": [], "stats": {"total": 0, "new": 0, "approved": 0, "skipped": 0}}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE) or '.', exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def scan_new_notes(force=False):
    """扫描 Obsidian 中新增/修改的笔记，返回相对路径列表。"""
    state = _load_state()
    scanned = state.get("scanned", {})
    new_notes = []
    all_md = []

    for root, dirs, files in os.walk(OBSIDIAN_ROOT):
        for f in files:
            if not f.endswith('.md'):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, OBSIDIAN_ROOT)
            all_md.append(rel)

            mtime = os.path.getmtime(full)
            prev = scanned.get(rel, {})

            if force or prev.get("mtime", 0) < mtime:
                new_notes.append(rel)

    return new_notes, all_md


# 预加载 distill 模块（单次导入，性能优化）
import importlib.util
_distill_spec = importlib.util.spec_from_file_location('distill', '/var/minis/shared/obsidian-distill.py')
_distill_mod = importlib.util.module_from_spec(_distill_spec)
_distill_spec.loader.exec_module(_distill_mod)


def _distill_text(text, rel_path):
    """调用 distill 模块的 distill() 函数。"""
    card, card_md = _distill_mod.distill(text, source_file=rel_path)
    if card is None:
        return None, 0, []
    return card, card.get("score", 0), card.get("claims", [])


def _auto_approve_card(card, score, claims):
    content = card.get("content_preview", card.get("title", ""))
    return (
        score >= AUTO_APPROVE_MIN_SCORE and
        len(content) >= AUTO_APPROVE_MIN_LEN and
        len(claims) >= AUTO_APPROVE_MIN_CLAIMS
    )


def _infer_archive_dir(title, tags):
    """根据标题和标签推断归档目录。"""
    text = title + ' '.join(tags)
    for kws, folder in DIR_HINTS:
        for kw in kws:
            if kw in text:
                return folder
    return "00-Inbox"


def _mark_scanned(rel_path):
    state = _load_state()
    state.setdefault("scanned", {})
    full = os.path.join(OBSIDIAN_ROOT, rel_path)
    state["scanned"][rel_path] = {
        "mtime": os.path.getmtime(full),
        "ts": datetime.now().isoformat(),
    }
    _save_state(state)


def _compute_friction(text):
    """
    摩擦度评分（借鉴 TeamAI 的 Session Friction）。
    判断这段内容是否有"学习价值"——是否创造了新认知、分析了新事物。

    返回: (score, level, action, reason)
    - level: high/medium/low/empty
    - action: distill/distill_light/summarize/skip
    """
    score, level, breakdown = _friction_mod.friction_score(text)
    action, reason = _friction_mod.get_action(level)
    return (score, level, action, reason, breakdown)


def _get_mode(mode_str):
    """获取渐进式策略模式。返回 (mode_key, config)。"""
    mode_str = (mode_str or DEFAULT_MODE).lower()
    if mode_str not in MODES:
        mode_str = DEFAULT_MODE
    return mode_str, MODES.get(mode_str, MODES[DEFAULT_MODE])


def _decide_approval(card, score, claims, mode_key):
    """
    渐进式决策：
    - manual: 所有卡片都走"待人工确认"，不自动批准
    - semi: 高分且高频模式自动批；低分/边界/新类型走人工
    - auto: 达到阈值自动批准（当前行为）
    返回 (approved: bool, reason: str)
    """
    auto_pass = _auto_approve_card(card, score, claims)
    title = card.get("title", "")
    tags = card.get("tags", [])
    content = card.get("content_preview", card.get("title", ""))

    if mode_key == "manual":
        return (False, "手动模式：所有卡片等待人工确认")

    if mode_key == "semi":
        if auto_pass:
            # 半自动：高频模式自动批
            # 精确匹配高频领域标签（避免子串误判）
            high_freq_tags = ["AI", "工具", "Agent", "框架", "方法", "原理"]
            if any(t in high_freq_tags for t in tags) or any(hf in title for hf in high_freq_tags):
                return (True, "半自动：高频模式 + 达标 → 自动批准")
            # 标题长度 ≥ 10 且内容 ≥ 200 字也自动批
            if len(title) >= 10 and len(content) >= 200:
                return (True, "半自动：内容充足 → 自动批准")
            return (False, "半自动：边界案例 → 等待人工确认")
        return (False, "半自动：未达阈值 → 等待人工确认")

    # auto 模式（默认）
    if auto_pass:
        return (True, "全自动：达到阈值 → 自动批准")
    return (False, "全自动：未达阈值 → 跳过")


def _update_stats(state, delta):
    s = state.setdefault("stats", {"total": 0, "new": 0, "approved": 0, "skipped": 0})
    for k, v in delta.items():
        s[k] = s.get(k, 0) + v
    # 确保 total = approved + skipped（修正历史 bug）
    s["total"] = s.get("approved", 0) + s.get("skipped", 0)


def _update_obsidian_level():
    """根据学习活跃度自动升级 Obsidian 等级。"""
    learn_path = "/var/minis/shared/.learning-store.json"
    if not os.path.exists(learn_path):
        return None
    with open(learn_path, 'r', encoding='utf-8') as f:
        store = json.load(f)
    obs_entry = next((e for e in store.get("entries", []) if e["topic"] == "Obsidian"), None)
    if not obs_entry:
        return None

    level = obs_entry.get("level", 1)
    sessions = obs_entry.get("sessions", 0)

    # 升级逻辑：sessions 累计 ≥ 8 时从 Lv.3 升到 Lv.4
    if level < 4 and sessions >= 8:
        obs_entry["level"] = 4
        obs_entry["notes"].append({
            "ts": datetime.now().isoformat(),
            "note": f"自动学习管道累计 {sessions} 次会话，等级自动升级至 Lv.4 精通"
        })
        obs_entry["last_updated"] = datetime.now().isoformat()
        store["sessions"].append({
            "ts": datetime.now().isoformat(),
            "topic": "Obsidian",
            "note": f"等级自动升级 → Lv.4 (sessions={sessions})"
        })
        with open(learn_path, 'w', encoding='utf-8') as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
        return 4

    return level


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Obsidian 自动学习管道')
    parser.add_argument('--force', action='store_true', help='强制重新扫描全部笔记')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不写入')
    parser.add_argument('--json', '-j', action='store_true', help='JSON 输出')
    parser.add_argument('--mode', type=str, default=DEFAULT_MODE,
                        help=f'渐进式策略模式: manual/semi/auto (默认 {DEFAULT_MODE})')
    args = parser.parse_args()

    mode_key, mode_cfg = _get_mode(args.mode)

    print("=" * 50)
    print(f"  📚 自动学习管道 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  🎛️  模式: {mode_cfg['label']}（{mode_cfg['desc']}）")
    print("=" * 50)

    # Step 1: 扫描
    new_notes, all_md = scan_new_notes(force=args.force)
    state = _load_state()

    print(f"\n  扫描: {len(all_md)} 篇笔记，{len(new_notes)} 篇新/已修改")

    if args.dry_run and new_notes:
        print(f"\n  [DRY-RUN] 以下笔记将被处理:")
        for n in new_notes:
            print(f"    {n}")

    if not new_notes:
        print("  ✅ 无新笔记，无需处理")
        # 仍更新 Obsidian 等级
        new_level = _update_obsidian_level()
        if new_level:
            print(f"  🌳 Obsidian 等级: Lv.{new_level}")
        return

    results = {"processed": 0, "approved": 0, "skipped": 0, "level": None}

    # Step 2: 摩擦度评分 → 路由 → 蒸馏 + 批准
    friction_stats = {"high": 0, "medium": 0, "low": 0, "empty": 0}

    for rel in new_notes:
        full = os.path.join(OBSIDIAN_ROOT, rel)
        try:
            with open(full, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
        except Exception:
            _mark_scanned(rel)
            continue

        # === 摩擦度评分（TeamAI 范式） ===
        f_score, f_level, f_action, f_reason, f_breakdown = _compute_friction(text)
        friction_stats[f_level] = friction_stats.get(f_level, 0) + 1

        # 摩擦度路由
        if f_action == "skip":
            _mark_scanned(rel)
            _update_stats(state, {"skipped": 1})
            results["skipped"] += 1
            print(f"  ⏭️  {rel.split('/')[-1][:30]} — 零摩擦，跳过 ({f_reason})")
            results["processed"] += 1
            continue

        if f_action == "summarize":
            # 仅记录摘要，不蒸馏
            _mark_scanned(rel)
            _update_stats(state, {"skipped": 1})
            results["skipped"] += 1
            # 提取第一行或标题作为摘要
            first_line = text.split('\n')[0].strip()[:60]
            print(f"  📋 {rel.split('/')[-1][:30]} — 低摩擦，仅记录摘要 (摩擦:{f_score:+d})")
            print(f"     {f_reason}")
            results["processed"] += 1
            continue

        # === 蒸馏 ===
        card, score, claims = _distill_text(text, rel)
        if card is None:
            _mark_scanned(rel)
            _update_stats(state, {"skipped": 1})
            results["skipped"] += 1
            continue

        card["score"] = score
        card["claims"] = claims
        card["file"] = full
        card["source_file"] = rel
        card["friction"] = {"score": f_score, "level": f_level}

        # 摩擦度调整批准决策
        if f_action == "distill_light":
            # 中摩擦：降低自动批准阈值（score >= 50 即可，而非默认的 80）
            auto_approve, approve_reason = _decide_approval(
                card, max(score, 50), claims, mode_key)
            approve_reason = f"[中摩擦] {approve_reason}"
        else:
            auto_approve, approve_reason = _decide_approval(card, score, claims, mode_key)
            approve_reason = f"[{f_level}摩擦] {approve_reason}"

        if auto_approve:
            # 自动批准并归档
            archive_dir = _infer_archive_dir(
                card.get("title", ""),
                card.get("tags", [])
            )
            card["status"] = "approved"
            card["archived"] = archive_dir
            card["approved_at"] = datetime.now().isoformat()

            # 保存到 Inbox 或目标目录
            if args.dry_run:
                print(f"\n  [DRY-RUN] 📐 {card['title']}")
                print(f"           评分: {score} | 主张: {len(claims)} 条 | → {archive_dir}/")
                print(f"           {approve_reason}")
            else:
                card_md = card.get("content_md", f"# {card.get('title','?')}\n")
                out_dir = os.path.join(OBSIDIAN_ROOT, archive_dir)
                os.makedirs(out_dir, exist_ok=True)
                safe_title = card.get('title','?')[:30].replace('/', '-').replace('\\', '-').replace(':', '-')
                out_path = os.path.join(out_dir, f"{card['id']}-{safe_title}.md")
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(card_md)
                # 更新 distill store
                _distill_mod._save_store(_distill_mod._load_store())
                _distill_mod._load_store()["cards"].append(card)
                _distill_mod._save_store(_distill_mod._load_store())
                print(f"  ✅ {card['title'][:30]} → {archive_dir}/ (评分:{score})")
                print(f"     {approve_reason}")

            _mark_scanned(rel)
            _update_stats(state, {"approved": 1})
            results["approved"] += 1
        else:
            _mark_scanned(rel)
            _update_stats(state, {"skipped": 1})
            results["skipped"] += 1
            print(f"  ⏭️  {card.get('title','?')[:30]}（评分:{score}，{approve_reason}）")

        results["processed"] += 1

    # Step 3: 更新 Obsidian 等级
    new_level = _update_obsidian_level()
    results["level"] = new_level
    _save_state(state)

    # 汇总
    print(f"\n  📊 处理: {results['processed']} 篇 | ✅ 批准: {results['approved']} | ⏭️ 跳过: {results['skipped']}")
    fr = friction_stats
    print(f"  🔥 摩擦度: 🔴高:{fr.get('high',0)} 🟡中:{fr.get('medium',0)} 🟢低:{fr.get('low',0)} ⚪零:{fr.get('empty',0)}")
    if new_level:
        print(f"  🌳 Obsidian 等级: Lv.{new_level}")

    if args.json:
        print("\n" + json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()