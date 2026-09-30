#!/usr/bin/env python3
# Version: 0.1.0
"""archify-selfcheck.py — 送 archify 渲染前的快速闸门

为什么需要：archify 的 `validate` 在 iSH 实测 >215s，而 `render` 对非法 spec 要么
exit=0 且不产出文件（无声失败），要么 exit=1 但把子进程诊断吞掉。把能在 0.1s 内
查出来的错误留给 200s 的慢工具，是纯粹浪费。本脚本查的全是确定性结构问题：

  1. schema 未知字段（archify 各层都是 additionalProperties:false，多一个键直接拒）
  2. 悬空引用（connections.from/to、views.focus 指向不存在的组件）
  3. 枚举值非法（type / variant / route / dot / locale）
  4. 布局冲突：grid 模式同格子、pos 模式矩形重叠、内容越出 viewBox
  5. 类型/坐标缺失

用法:
  archify-selfcheck.py <spec.json> [<spec2.json> ...]
退出码: 0 全通过 / 1 有错误 / 2 用法或文件错误
不查语义（图画得对不对，仍靠人）。
"""
import json
import os
import sys

SCHEMA_DIR = "/var/minis/skills/archify/schemas"

ENUMS = {
    "component.type": {"frontend", "backend", "database", "cloud", "security", "messagebus", "external"},
    "connection.variant": {"default", "emphasis", "security", "dashed"},
    "connection.route": {"auto", "straight", "orthogonal-h", "orthogonal-v"},
    "card.dot": {"cyan", "emerald", "violet", "amber", "rose", "orange", "slate"},
    "meta.locale": {"en", "zh-CN"},
    "meta.animation": {"trace", "none"},
    "meta.visual_preset": {"classic", "signal-flow", "blueprint", "editorial"},
    "meta.quality_profile": {"standard", "showcase"},
}


def schema_props(diagram_type):
    """从 schema 取各层允许字段。archify 任何一层加字段这里自动跟随，无需改脚本。"""
    path = os.path.join(SCHEMA_DIR, f"{diagram_type}.schema.json")
    if not os.path.exists(path):
        return None
    a = json.load(open(path, encoding="utf-8"))
    p = a.get("properties", {})
    out = {"root": set(p.keys()), "root_required": set(a.get("required", []))}
    for sec in ("meta", "layout"):
        if sec in p:
            out[sec] = set(p[sec].get("properties", {}).keys())
    for sec in ("components", "connections", "cards", "boundaries"):
        node = p.get(sec)
        if node and node.get("type") == "array":
            items = node.get("items", {})
            out[sec] = set(items.get("properties", {}).keys())
    return out


def check(path):
    errs = []
    try:
        d = json.loads(open(path, encoding="utf-8").read())
    except Exception as e:
        return [f"JSON 解析失败: {e}"], 0, []
    dt = d.get("diagram_type", "architecture")
    sp = schema_props(dt)
    if sp is None:
        errs.append(f"找不到 {dt} 的 schema（archify 已装？）")
        return errs, 0, []

    if sp:
        if dt not in sp["root"]:
            pass
        for k in sp["root_required"] - set(d.keys()):
            if k != "diagram_type":
                errs.append(f"root 缺必填字段 '{k}'")
        for k in d:
            if k not in sp["root"]:
                errs.append(f"root 未知字段 '{k}'")
        for k in d.get("meta", {}):
            if "meta" in sp and k not in sp["meta"]:
                errs.append(f"meta 未知字段 '{k}' —— 允许: {sorted(sp['meta'])}")
        for k in d.get("layout", {}):
            if "layout" in sp and k not in sp["layout"]:
                errs.append(f"layout 未知字段 '{k}'")

    comps = d.get("components", [])
    ids = [c.get("id") for c in comps]
    if len(ids) != len(set(ids)):
        errs.append("组件 id 重复")
    for c in comps:
        cid = c.get("id", "?")
        if sp and "components" in sp:
            for k in c:
                if k not in sp["components"]:
                    errs.append(f"components[{cid}] 未知字段 '{k}'")
        if c.get("type") not in ENUMS["component.type"]:
            errs.append(f"{cid}.type 非法: {c.get('type')}")
        if not c.get("label"):
            errs.append(f"{cid} 缺 label")

    lay = d.get("layout", {})
    grid = lay.get("mode") == "grid"
    cells = {}
    boxes = []
    for c in comps:
        cid = c.get("id", "<缺id>")
        if grid:
            key = (c.get("row"), c.get("col"))
            if None in key:
                errs.append(f"{cid} 用了 grid 布局但缺 row/col")
                continue
            if key in cells:
                errs.append(f"格子冲突: {cid} 与 {cells[key]} 同在 row{key[0]} col{key[1]}")
            cells[key] = cid
            cols = lay.get("cols")
            if isinstance(cols, int) and c.get("col", 0) >= cols:
                errs.append(f"{cid}.col={c['col']} 超出 layout.cols={cols}")
        else:
            pos, size = c.get("pos"), c.get("size", [138, 68])
            if not (isinstance(pos, list) and len(pos) == 2):
                errs.append(f"{cid} 缺 pos（非 grid 布局必须给坐标）")
                continue
            boxes.append((cid, pos[0], pos[1], size[0], size[1]))

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if a[1] < b[1] + b[3] and b[1] < a[1] + a[3] and a[2] < b[2] + b[4] and b[2] < a[2] + a[4]:
                errs.append(f"矩形重叠: {a[0]} / {b[0]}")

    vb = d.get("meta", {}).get("viewBox")
    if isinstance(vb, list) and len(vb) == 2 and boxes:
        mx = max(b[1] + b[3] for b in boxes)
        my = max(b[2] + b[4] for b in boxes)
        if mx > vb[0] or my > vb[1]:
            errs.append(f"内容越出 viewBox: 右下界 {mx},{my} > {vb[0]},{vb[1]}")

    for k in d.get("connections", []):
        kid = k.get("id", "?")
        if sp and "connections" in sp:
            for f in k:
                if f not in sp["connections"]:
                    errs.append(f"connections[{kid}] 未知字段 '{f}'")
        for side in ("from", "to"):
            if k.get(side) not in ids:
                errs.append(f"悬空引用 connections[{kid}].{side} -> {k.get(side)}")
        if k.get("variant") and k["variant"] not in ENUMS["connection.variant"]:
            errs.append(f"connections[{kid}].variant 非法: {k['variant']}")
        if k.get("route") and k["route"] not in ENUMS["connection.route"]:
            errs.append(f"connections[{kid}].route 非法: {k['route']}")

    for v in d.get("meta", {}).get("views", []):
        for f in v.get("focus", []):
            if f not in ids:
                errs.append(f"views[{v.get('id')}].focus 悬空 -> {f}")

    for card in d.get("cards", []):
        if card.get("dot") and card["dot"] not in ENUMS["card.dot"]:
            errs.append(f"card.dot 非法: {card['dot']} (title={card.get('title')})")
        for req in ("title", "items"):
            if not card.get(req):
                errs.append(f"card 缺 {req}")

    loc = d.get("meta", {}).get("locale")
    if loc and loc not in ENUMS["meta.locale"]:
        errs.append(f"meta.locale 非法: {loc}")
    for k in ("animation", "visual_preset", "quality_profile"):
        v = d.get("meta", {}).get(k)
        if v and v not in ENUMS[f"meta.{k}"]:
            errs.append(f"meta.{k} 非法: {v}")

    # 非相邻格的边极可能被 archify 的 clean-flow 判为"边穿过无关节点"而整图拒绝。
    # 不是硬错误（archify 有时能绕），但值得警告——实测因此白跑过 200s 量级的轮次。
    warns = []
    if grid:
        pos_of = {c.get("id", "?"): (c.get("row"), c.get("col")) for c in comps if c.get("row") is not None}
        for k in d.get("connections", []):
            a, b = pos_of.get(k.get("from")), pos_of.get(k.get("to"))
            if not a or not b:
                continue
            dr, dc = abs(a[0] - b[0]), abs(a[1] - b[1])
            if dr + dc > 1:
                warns.append(f"边 {k.get('id')} {k['from']}→{k['to']} 跨 {dr} 行 {dc} 列，"
                             f"很可能被判穿节点（改成只连相邻格，或该关系交给卡片文字）")
    return errs, len(comps), warns


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 2
    bad = 0
    for path in args:
        if not os.path.isfile(path):
            print(f"✗ {path}: 文件不存在")
            bad += 1
            continue
        errs, n, warns = check(path)
        tag = os.path.basename(path)
        for w in warns:
            print(f"  ! {tag}: {w}")
        if errs:
            bad += 1
            print(f"✗ {tag}: {len(errs)} 个结构错误（{n} 组件）")
            for e in errs:
                print(f"    · {e}")
        else:
            print(f"✓ {tag}: 结构自检通过（{n} 组件）")
    if bad:
        print(f"\n结论: {bad} 份 spec 有问题。先修再送 archify —— "
              f"它的 validate 要 200s+，且 render 出错可能不给任何诊断。")
        return 1
    print("\n结论: 全部通过，可送 archify-render.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
