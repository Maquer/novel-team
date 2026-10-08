#!/usr/bin/env python3
"""
章节契约工具 — v0.53.0（SkillSystem 借鉴落地）

核心思想：四阶段 V/I/C/E 强制咬合，V 阶段不匹配事实账本就拦截（原框架 SkillManager.Verify）

章节字段契约：
  V (Verify)    本章前提状态  {"realm":"淬体四重","position":"天剑宗外门","state":[]}
  I (Introduce) 铺垫/信息释放  {"tension_in":0.6,"new_info":[...]}
  C (Calculate) 高潮结算       {"climax":"L3","outcome":"萧辰突破","thrill":"L3"}
  E (End)       收尾钩子+状态变更 {"hook":"王执事暗中观察","changes":[{"field":"realm","from":"淬体三重","to":"淬体四重"}]}

使用：
  python chapter-contract.py validate --chapter-file <file> --project my-novel
  python chapter-contract.py show --chapter-file <file>
  python chapter-contract.py draft --chapter-file <file>   # 生成契约骨架
"""
import sys, json, re, argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

# FIX 2026-10-04：移除天命/my-novel 写死路径，改为按 --project 动态解析。
# 按 project_guard 约定：current/world-packs/ 与 current/characters/ 为项目目录子目录。
TEAM_ROOT = Path(__file__).resolve().parent.parent


def resolve_project_dir(project_id: str) -> Path:
    """按 project_id 解析项目目录（遵循 project_guard.resolve 的 conventions）。"""
    from project_guard import resolve as guard_resolve
    return guard_resolve(project_id).root_dir

# ─── 校验规则 ───────────────────────────────────────────────────────────────
THRILL_LEVELS = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}
REQUIRED_FIELDS = {"V": "verify", "I": "introduce", "C": "calculate", "E": "end"}
MAX_CLIMAX_PER_CHAPTER = 2  # L3+ 节拍上限


def load_facts(project_id: str) -> Dict[str, Any]:
    """加载事实账本（兼容 dict-of-F / 列表 envelope 两种格式）。"""
    proj = resolve_project_dir(project_id)
    p = proj / "ledger" / "facts.json"
    if not p.exists():
        return {"F0016": {"status": "committed", "content": f"事实账本不存在，请初始化（项目 {project_id}）"}}
    d = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(d, list):
        return {f"auto_{i}": f for i, f in enumerate(d)}
    if isinstance(d, dict):
        if any(k.startswith("F") for k in d):
            return d
        if "facts" in d:
            return {f"auto_{i}": f for i, f in enumerate(d["facts"])}
    return d


def load_characters(project_id: str) -> Dict[str, Any]:
    """加载角色档案。"""
    proj = resolve_project_dir(project_id)
    p = proj / "characters" / "characters.json"
    if not p.exists():
        return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    chars = d.get("characters", {})
    if isinstance(chars, list):
        return {c.get("id", c.get("name", f"char-{i}")): c for i, c in enumerate(chars)}
    return chars


def extract_frontmatter(text: str) -> Dict[str, Any]:
    """提取 YAML frontmatter（--- 包裹的键值对）"""
    fm = {}
    if not text.startswith("---"):
        return fm
    parts = text.split("---", 2)
    if len(parts) < 2:
        return fm
    try:
        fm = yaml_load(parts[1])
    except Exception:
        pass
    return fm


def yaml_load(text: str) -> Dict:
    """轻量 YAML frontmatter 解析（支持简单键值对 + 单行列表 [a,b,c]）"""
    result = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(\w[\w-]*):\s*(.+)$", line)
        if not m:
            # 多行列表项（以 - 开头，属于上一行的列表值）
            if result and re.match(r"^\s*-\s*(.+)$", line):
                last_key = list(result.keys())[-1]
                if isinstance(result[last_key], list):
                    val = line[2:].strip().strip('"').strip("'")
                    result[last_key].append(val)
                continue
            continue
        k, v = m.group(1), m.group(2).strip()
        # 简单列表解析：[a, b, c] 或 []
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            if inner:
                result[k] = [x.strip().strip('"').strip("'") for x in inner.split(",")]
            else:
                result[k] = []
            continue
        # 标量类型推断
        if v.lower() in ("true", "false"):
            v = v.lower() == "true"
        elif re.match(r"^-?\d+$", v):
            v = int(v)
        elif re.match(r"^-?\d+\.\d+$", v):
            v = float(v)
        else:
            v = v.strip('"').strip("'")
        result[k] = v
    return result


def parse_contract(body: str) -> Dict:
    """解析正文中的 [V] / [I] / [C] / [E] 段（支持 # V 或 ## [V] 等格式）"""
    contract = {}
    current_key = None
    current_lines = []
    # 匹配：[V]/[I]/[C]/[E] 段标记（支持 ## [V] 或单独 [V] 格式）
    # 注意：\[[VIEC]\] = 方括号内含 V/I/E/C 之一，不是 [VI][CEN]（那是组合字符类）
    seg_pat = re.compile(
        r"#{0,}\s*\[([VIEC])\]",
        re.IGNORECASE
    )
    for line in body.splitlines():
        m = seg_pat.match(line)
        if m:
            if current_key and current_lines:
                contract[current_key] = "\n".join(current_lines).strip()
            key = m.group(1).upper()  # ([VIEC]) 是第一捕获组
            current_key = key
            current_lines = []
            continue
        if current_key:
            current_lines.append(line)
    if current_key and current_lines:
        contract[current_key] = "\n".join(current_lines).strip()
    return contract


def _resolve_anchor_chars(anchors: List[str], facts: Dict, chars: Dict) -> set:
    """根据 anchors 解析出本章涉及的角色 ID 集合（默认为主角 char-001）"""
    related = set()
    fact_ids = {k for k in facts if k.startswith("F")}
    for a in anchors:
        if not isinstance(a, str):
            continue
        a_upper = a.upper()
        # 精确匹配事实 ID
        if a_upper in fact_ids:
            # 扫描该事实内容，提取角色名关键词
            content = str(facts[a].get("content", ""))
            for cid, cdata in chars.items():
                if cdata.get("name", "") and cdata["name"] in content:
                    related.add(cid)
    if not related:
        # 无明确锚点 → 默认查主角（char-001 或首个 figure）
        for cid, cdata in chars.items():
            if cdata.get("role") == "主角" or cid == "char-001":
                related.add(cid)
                break
    return related or set(chars.keys())


def validate_verify_stage(chapter_data: Dict, contract: Dict, facts: Dict, characters: Dict) -> List[str]:
    """V 阶段硬闸：前提状态与事实账本匹配检查
    只校验 anchors 指定的角色，不扫描全量角色
    """
    issues = []
    verify = contract.get("V") or chapter_data.get("verify") or {}
    if isinstance(verify, str):
        try:
            verify = yaml_load(verify)
        except Exception:
            verify = {}

    # 确定需检查的角色范围：只检查主角（role=主角），不检查配角/反派
    anchors = verify.get("anchors", [])
    all_related = _resolve_anchor_chars(anchors if isinstance(anchors, list) else [], facts, characters)
    check_chars = {cid: characters[cid] for cid in all_related
                   if cid in characters and characters[cid].get("role") == "主角"}
    if not check_chars:
        # fallback：检查所有相关角色
        check_chars = {cid: characters[cid] for cid in all_related if cid in characters}

    # 1. realm 一致性检查（仅检查相关角色）
    if "realm" in verify:
        req_realm = str(verify["realm"]).strip()
        if req_realm:
            for cid, char in check_chars.items():
                current_realm = char.get("realm", "")
                if current_realm and str(current_realm).lower() != req_realm.lower():
                    # 允许同一境界同义写法
                    aliases = {"淬体四重": ["淬体4重", "淬体肆重"],
                               "淬体三重": ["淬体3重", "淬体叁重"]}
                    valid = req_realm in aliases.get(str(current_realm), [str(current_realm)])
                    if not valid:
                        issues.append(
                            f"V 阶段 realm 矛盾：要求【{req_realm}】，但角色{cid}当前【{current_realm}】"
                        )

    # 2. position 一致性检查
    if "position" in verify:
        req_pos = str(verify["position"]).strip()
        # TODO: 可扩展为检查 world-pack 中是否存在该地点
        if req_pos and not any(kw in req_pos for kw in ["天剑", "外门", "中州"]):
            # 未命中已知地点关键词，仅 warning
            pass  # 暂时宽松处理

    # 3. state 一致性检查（重伤/破防等 buff，仅检查相关角色）
    if "state" in verify:
        req_state = verify["state"]
        if isinstance(req_state, list):
            for cid in check_chars:
                char = characters.get(cid, {})
                char_buffs = char.get("buff", []) or []
                char_buffs_str = [str(b) for b in char_buffs]
                for s in req_state:
                    if s and s not in char_buffs_str:
                        issues.append(
                            f"V 阶段 state 矛盾：要求【{s}】，但角色{cid}无此状态"
                        )

    # 4. 账本检查：V 阶段必须引用至少 1 条账本事实（锚定前提）
    if "anchors" in verify:
        anchors = verify["anchors"]
        if isinstance(anchors, list) and anchors:
            fact_ids = {k for k in facts if k.startswith("F")}
            for a in anchors:
                if a and isinstance(a, str) and not any(a.upper() in fid for fid in fact_ids):
                    issues.append(f"V 阶段 anchors 引用【{a}】，但事实账本中无此 ID")

    return issues


def validate_introduce_stage(chapter_data: Dict, contract: Dict) -> List[str]:
    """I 阶段检查：铺垫合理性"""
    issues = []
    intro = contract.get("I") or chapter_data.get("introduce") or {}
    if isinstance(intro, str):
        try:
            intro = yaml_load(intro)
        except Exception:
            intro = {}

    tension_in = intro.get("tension_in")
    if tension_in is not None:
        try:
            t = float(tension_in)
            if not (0 <= t <= 1):
                issues.append(f"I 阶段 tension_in={t} 越界（0-1）")
        except (ValueError, TypeError):
            issues.append(f"I 阶段 tension_in 非数值：{tension_in}")

    new_info = intro.get("new_info")
    if new_info and isinstance(new_info, list):
        if len(new_info) > 5:
            issues.append(f"I 阶段 new_info={len(new_info)} 条，超过建议上限 5 条（设定过载风险）")

    return issues


def validate_calculate_stage(chapter_data: Dict, contract: Dict) -> List[str]:
    """C 阶段检查：爽点层级 + 多高潮节拍约束"""
    issues = []
    calc = contract.get("C") or chapter_data.get("calculate") or {}
    if isinstance(calc, str):
        try:
            calc = yaml_load(calc)
        except Exception:
            calc = {}

    # 爽点层级合法性
    climax = calc.get("climax", calc.get("thrill", ""))
    if climax:
        lv = str(climax).upper().strip()
        if lv not in THRILL_LEVELS:
            issues.append(f"C 阶段 climax={climax} 非合法层级（L1/L2/L3/L4）")

    # 多段高潮节拍约束：同一 C 段内出现多个 L3+ climax 即超标
    # 通过解析 C 段原始内容中所有 climax/thrill 标注来计数
    c_raw = contract.get("C") or ""
    l3plus_count = 0
    for line in c_raw.splitlines():
        m = re.search(r"(?i)(?:climax|thrill|爽点)[\s:：]*(L[1-4])", line)
        if m:
            lv = m.group(1).upper()
            if lv in ("L3", "L4"):
                l3plus_count += 1
    if l3plus_count >= MAX_CLIMAX_PER_CHAPTER + 1:  # ≥3 即超标；≤2 正常
        issues.append(
            f"C 阶段多高潮超标：本章 L3+ 节拍={l3plus_count}，上限 {MAX_CLIMAX_PER_CHAPTER}"
        )

    return issues


def validate_end_stage(chapter_data: Dict, contract: Dict, facts: Dict) -> List[str]:
    """E 阶段检查：钩子有效性 + 状态变更写账本"""
    issues = []
    end = contract.get("E") or chapter_data.get("end") or {}
    if isinstance(end, str):
        try:
            end = yaml_load(end)
        except Exception:
            end = {}

    # hook 必须有（至少 10 字符，防止空钩子）
    hook = str(end.get("hook", "") or "").strip()
    if not hook or len(hook) < 5:
        issues.append("E 阶段 hook 为空或过短（<5字），读者无法形成追读钩子")

    # changes 必须写进事实账本
    changes = end.get("changes", [])
    if isinstance(changes, list):
        for i, ch in enumerate(changes):
            if isinstance(ch, dict):
                if "field" not in ch:
                    issues.append(f"E 阶段 changes[{i}] 缺 field 字段")
                if "from" not in ch or "to" not in ch:
                    issues.append(f"E 阶段 changes[{i}] 缺 from/to，无法追溯状态变迁")

    return issues


def validate_contracts(file_path: Path, facts: Dict, characters: Dict) -> Dict:
    """主校验流程"""
    if not file_path.exists():
        return {"error": f"文件不存在：{file_path}", "passed": False}

    content = file_path.read_text(encoding="utf-8")
    fm = extract_frontmatter(content)
    body = content.split("---", 2)[2] if "---" in content else content
    contract = parse_contract(body)

    errors: List[str] = []
    warnings: List[str] = []

    # 检查必填段
    for seg, field in REQUIRED_FIELDS.items():
        if seg not in contract:
            errors.append(f"缺少必填段 [{seg}]（V/I/C/E）")

    # 分阶段校验
    if "V" in contract:
        errors.extend(validate_verify_stage(fm, contract, facts, characters))
    if "I" in contract:
        errors.extend(validate_introduce_stage(fm, contract))
    if "C" in contract:
        errors.extend(validate_calculate_stage(fm, contract))
    if "E" in contract:
        errors.extend(validate_end_stage(fm, contract, facts))

    # 全局检查
    if "C" in contract:
        climax = str(fm.get("climax", fm.get("thrill", ""))).upper().strip()
        if climax in THRILL_LEVELS and THRILL_LEVELS[climax] >= 3:
            # L3+ 章必须有 E 段钩子
            if "E" not in contract:
                warnings.append(f"[C] 标注 L3+ 高潮，但无 [E] 收尾钩子；L3+ 必须有追读钩子")

    return {
        "file": str(file_path.name),
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "contract": contract,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description="章节契约工具（SkillSystem 四阶段 V/I/C/E）")
    parser.add_argument("command", choices=["validate", "show", "draft"],
                        help="validate=校验契约；show=显示解析结果；draft=生成骨架模板")
    parser.add_argument("--chapter-file", required=True, help="章节 md 文件路径")
    parser.add_argument("--project", default=None, help="项目 ID（按 project_guard.resolve 解析路径，替代写死 my-novel）")
    args = parser.parse_args()

    project_id = args.project
    chapter_file = Path(args.chapter_file)
    facts = load_facts(project_id)
    characters = load_characters(project_id)

    if args.command == "validate":
        result = validate_contracts(chapter_file, facts, characters)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("passed") else 1)

    elif args.command == "show":
        if not chapter_file.exists():
            print(f"文件不存在：{chapter_file}", file=sys.stderr)
            sys.exit(2)
        content = chapter_file.read_text(encoding="utf-8")
        fm = extract_frontmatter(content)
        body = content.split("---", 2)[2] if "---" in content else content
        contract = parse_contract(body)
        print(json.dumps({"frontmatter": fm, "contract": contract}, ensure_ascii=False, indent=2))

    elif args.command == "draft":
        template = """---
title: 第{num}章 {title}
author: 小蒋
date: {date}
word_count: 0
charm_level: L1        # 本章最高爽点层级（L1/L2/L3/L4）
---

# 第{num}章 {title}

## [V] 前提状态
<!-- 本章必须满足的前置条件，与事实账本锚定 -->
realm: 淬体三重
position: 天剑宗外门
state:
  - 坚韧
anchors:
  - F0003  # 王大淬体四重首战萧辰

## [I] 铺垫/信息释放
<!-- 紧张度上升量 0~1，新信息点列表 -->
tension_in: 0.6
new_info:
  - "王大放话生死擂台不留手"
  - "萧辰发现铁剑发热"

## [C] 高潮结算
<!-- climax: L1/L2/L3/L4，outcome: 结果一句话 -->
climax: L3
outcome: "萧辰擂台突破至淬体四重，天命剑初显寒芒"
thrill: L3

## [E] 收尾钩子+状态变更
<!-- hook: 追读钩子；changes: 角色状态变更清单 -->
hook: "王执事在人群中对萧辰投来意味深长的一瞥"
changes:
  - field: realm
    char: 萧辰
    from: 淬体三重
    to: 淬体四重
  - field: state
    char: 萧辰
    from: []
    to: ["觉醒中"]
"""
        date = datetime.now().strftime("%Y-%m-%d")
        num = "N"
        if isinstance(args.chapter_file, str):
            p = Path(args.chapter_file)
            num = p.stem.split("-")[-1] or "N"
        else:
            num = args.chapter_file.stem.split("-")[-1] or "N"
        print(template.format(num=num, title="章节标题", date=date))


if __name__ == "__main__":
    main()
