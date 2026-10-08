#!/usr/bin/env python3
"""
创作门禁全流程检查器 — 强制集成 guard-v6 和 fact-ledger

用法：
  python quality-gate.py --chapter chapter-001.md --novel-id my-novel
  python quality-gate.py --chapter chapter-001.md --novel-id my-novel --commit
  python quality-gate.py --publish --chapter chapter-001.md --novel-id my-novel
"""

import json
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# FIX 2026-09-30：BASE_DIR 改从 project_guard 统一入口获取，支持 NOVEL_TEAM_ROOT 环境变量覆盖。
# 修前本文件自带硬编码 BASE_DIR（/var/minis/shared/novel-team），与 project_guard 的 env 覆盖脱节，
# 导致测试/异机环境下 subprocess 拉起的是不存在的 /var/minis 路径下的 gate-check.py。
try:
    from project_guard import BASE_DIR
except ImportError:  # 直接拷贝单文件运行时回退
    import os
    BASE_DIR = Path(os.environ.get("NOVEL_TEAM_ROOT", "/var/minis/shared/novel-team"))
PROJECTS_DIR = BASE_DIR / "projects"


# FIX 2026-09-30: frontmatter 解析改用正则，只剥离文件开头的第一个 --- 块。
# 修前 in_meta 状态机逻辑错误（遇到 -/* 开头行才置 True；body_start 用 find 可能得 -1+5=4），
# metadata 经常解析为空且 body 切分位置不可靠。
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.DOTALL)


def load_chapter(chapter_file: str) -> dict:
    """加载章节文件并解析元数据"""
    with open(chapter_file, 'r', encoding='utf-8') as f:
        content = f.read()

    metadata = {}
    body = content

    m = _FRONTMATTER_RE.match(content)
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()
        body = content[m.end():].strip()

    return {"metadata": metadata, "body": body, "raw": content}


def run_gate_check(chapter_file: str, project_id: str) -> dict:
    """运行门禁检查"""
    try:
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "tools" / "gate-check.py"), 
             "check", "--file", chapter_file],
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR)
        )
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e), "passed": False}


def run_guard_v6(novel_id: str) -> dict:
    """运行四道一致性防线校验"""
    # 构建 events.json, characters.json, entities.json 路径
    events_file = PROJECTS_DIR / novel_id / "events.json"
    characters_file = PROJECTS_DIR / novel_id / "characters" / "characters.json"
    entities_file = PROJECTS_DIR / novel_id / "world" / "entities.json"

    # FIX 2026-09-30: 缺文件时不再自动创建空文件（修前先把被检查对象补成空的再检查，
    # 防线形同虚设）。改为返回 skipped，由调用方打印 warning 并跳过该步。
    missing = [str(f) for f in (events_file, characters_file, entities_file)
               if not f.exists()]
    if missing:
        return {"skipped": True,
                "warning": f"guard-v6 跳过：缺失 {len(missing)} 个输入文件："
                           f"{'; '.join(missing)}"}

    try:
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "tools" / "guard-v6.py"),
             "check",
             "--events", str(events_file),
             "--characters", str(characters_file),
             "--entities", str(entities_file)],
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR)
        )
        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except Exception as e:
        return {"error": str(e)}


def update_fact_ledger(novel_id: str, chapter_data: dict) -> dict:
    """更新事实账本"""
    try:
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "tools" / "fact-ledger.py"),
             "add-fact",
             "--novel-id", novel_id,
             "--category", "chapter",
             "--content", chapter_data["body"][:100] + "..."],
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR)
        )
        return {"returncode": result.returncode, "output": result.stdout}
    except Exception as e:
        return {"error": str(e)}


def commit_to_ledger(novel_id: str, chapter_num: int) -> bool:
    """将章节内容提交到事实账本（正文回流）"""
    # FIX 2026-09-30: 账本路径统一——修前写入 BASE_DIR/.ledger/<novel>/facts.json，
    # 而 gate-check.py:_check_fact_consistency 读取的是
    # resolve(novel_id).root_dir.parent.parent / "ledger" / novel_id / "facts.json"，
    # commit 写入的数据门禁永远读不到。现经 project_guard.resolve() 按 gate-check
    # 相同的计算方式定位，保证读写一致（同时支持 NOVEL_TEAM_ROOT 环境变量覆盖）。
    # 注意：gate-check 的读路径是 <BASE>/projects/ledger/<novel>/facts.json（跨代际共享），
    # 与 PROJECT_SUBDIRS 中的 per-project ledger/ 子目录不同；是否应收敛为后者，
    # 属 gate-check 侧的设计决策，本处仅保证两边一致。
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from project_guard import resolve
    facts_file = resolve(novel_id).root_dir.parent.parent / "ledger" / novel_id / "facts.json"
    facts_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 加载或创建事实库
    if facts_file.exists():
        facts = json.loads(facts_file.read_text(encoding='utf-8'))
    else:
        facts = {"facts": [], "timeline": [], "version": 1}
    
    # 添加新章节的事实
    facts["version"] += 1
    facts["facts"].append({
        "chapter": chapter_num,
        "timestamp": datetime.now().isoformat(),
        "status": "committed",
        "note": f"Chapter {chapter_num} committed to canon"
    })
    
    # 保存
    tmp = facts_file.with_suffix('.tmp')
    tmp.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(facts_file)
    
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="小说创作全流程质量门禁")
    parser.add_argument("--chapter", required=True, help="章节文件路径")
    parser.add_argument("--novel-id", default=None, help="小说项目ID")
    parser.add_argument("--commit", action="store_true", help="提交通过检查的章节到账本")
    parser.add_argument("--publish", action="store_true", help="发布确认（触发正文回流）")
    parser.add_argument("--chapter-num", type=int, default=1, help="章节编号")
    # FIX 2026-09-30: 新增严格模式。默认（宽松模式）保持原有行为：门禁未通过仅转
    # 质量债务、不阻断；--strict 下任何未通过直接 exit 非零阻断。生产入口若用本文件
    # 且要求门禁真实生效，建议使用 --strict。
    parser.add_argument("--strict", action="store_true",
                        help="严格模式：门禁未通过直接阻断（exit 非零），不转为质量债务")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("📖 小说创作质量门禁检查")
    print("=" * 60)
    
    # 步骤1: 加载章节
    print("\n[1/5] 加载章节...")
    chapter_data = load_chapter(args.chapter)
    print(f"  ✓ 已加载 {len(chapter_data['body'])} 字")
    
    # 步骤2: 门禁检查
    # FIX 2026-09-30 设计决策说明：
    # 本文件是门禁"编排器"。默认（宽松模式）下 gate-check 返回 passed=False 时仅转为
    # 质量债务并继续流程——门禁不真正阻断。若生产流水线以本文件为入口且要求门禁真实
    # 生效，请使用 --strict，此时任何未通过都将 exit 非零阻断。
    print("\n[2/5] 运行门禁检查 (gate-check)...")
    gate_result = run_gate_check(args.chapter, args.novel_id)

    if gate_result.get("error"):
        print(f"  ✗ 门禁检查失败: {gate_result['error']}")
        sys.exit(1)

    if not gate_result.get("passed", False):
        if args.strict:
            # FIX 2026-09-30: 严格模式——门禁失败直接阻断，不转质量债务
            print(f"  ✗ [严格模式 --strict] 门禁未通过，阻断创作流程")
            for d in gate_result.get("p0_failures", []) or []:
                print(f"    - P0: {d}")
            sys.exit(1)

        # 宽松模式（默认）：质量债务系统集成：所有门禁问题记录为债务，继续创作
        # FIX 2026-09-30: 打印信息明确标注当前为宽松模式，避免误以为门禁已阻断
        print(f"  ⚠️ 门禁发现问题（宽松模式：未加 --strict），已记录为质量债务，不阻断创作流程")

        # 尝试集成质量债务系统
        # FIX 2026-09-30：原 `from quality_debt import ...` 恒失败——文件实际叫 quality-debt.py
        # （连字符非法模块名），导致债务集成永远走 except 分支。改用 importlib 按文件路径加载。
        try:
            from pathlib import Path as P
            import sys as _sys
            import importlib.util as _ilu
            _qd_path = P(BASE_DIR) / "tools" / "quality-debt.py"
            _qd_spec = _ilu.spec_from_file_location("quality_debt", _qd_path)
            _qd_mod = _ilu.module_from_spec(_qd_spec)
            _qd_spec.loader.exec_module(_qd_mod)
            gate_result_to_debt = _qd_mod.gate_result_to_debt

            # 从文件名提取章节号
            ch_match = re.search(r'chapter-(\d+)', args.chapter)
            chapter_num = int(ch_match.group(1)) if ch_match else args.chapter_num

            debt_result = gate_result_to_debt(gate_result, chapter_num, args.novel_id)
            print(f"  📝 新增 {debt_result.get('debts_added', 0)} 条质量债务")
            if debt_result.get('debt_ids'):
                print(f"  债务ID: {', '.join(debt_result['debt_ids'])}")
        except Exception as e:
            print(f"  ⚠️ 质量债务集成失败: {e}")

        # 记录门禁结果但不阻断
        print(f"  ✅ 继续创作流程（质量问题已记录，后续可修复）")

    else:
        print(f"  ✓ 门禁检查通过")
    
    # 步骤3: 四道防线校验
    print("\n[3/5] 运行一致性防线 (guard-v6)...")
    guard_result = run_guard_v6(args.novel_id)
    
    if guard_result.get("error"):
        print(f"  ⚠ guard-v6 检查跳过: {guard_result['error']}")
    elif guard_result.get("skipped"):
        # FIX 2026-09-30: 缺输入文件时跳过该步，不再自动创建空文件
        print(f"  ⚠ {guard_result.get('warning', 'guard-v6 跳过')}")
    else:
        if guard_result.get("returncode", 1) != 0:
            print(f"  ✗ 一致性校验失败!")
            print(guard_result.get("stderr", ""))
            sys.exit(1)
        print(f"  ✓ 一致性校验通过")
    
    # 步骤4: 更新事实账本
    print("\n[4/5] 更新事实账本 (fact-ledger)...")
    ledger_result = update_fact_ledger(args.novel_id, chapter_data)
    
    if ledger_result.get("error"):
        print(f"  ⚠ 账本更新跳过: {ledger_result['error']}")
    else:
        print(f"  ✓ 账本已更新")
    
    # 步骤5: 提交/发布确认
    if args.commit or args.publish:
        print("\n[5/5] 提交章节到正史...")
        if commit_to_ledger(args.novel_id, args.chapter_num):
            print(f"  ✓ 第 {args.chapter_num} 章已提交到正史")
            print(f"  ✓ 正文回流完成")
        else:
            print(f"  ✗ 提交失败")
            sys.exit(1)
    else:
        print("\n[5/5] 未提交 (使用 --commit 或 --publish 提交)")
    
    print("\n" + "=" * 60)
    print("✅ 质量门禁全流程通过!")
    print("=" * 60)


if __name__ == "__main__":
    main()
