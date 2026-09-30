#!/usr/bin/env python3
"""
parse-score-output.py — 解析评分模型输出

用法:
  python3 parse-score-output.py [--raw]

默认输出:
  - 只列 YES 和 HOLD 的选题 (可直接看要不要发)
  - 打印 YES/HOLD/NO 计数
"""
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "score-output.json"
TOPICS = HERE / "topics.md"


def extract_json(text: str):
    """从模型输出里抠出 JSON 数组 (容忍 markdown fence / 前导文字)"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def load_topics():
    """加载 topics.md 最新区块, 建立 id → title 映射"""
    if not TOPICS.exists():
        return {}
    text = TOPICS.read_text(encoding="utf-8")
    blocks = re.findall(r"##\s+[\d\-:\s]+\s+TOP\s+\d+\s*\n(.*?)(?=\n##\s|$)", text, re.DOTALL)
    if not blocks:
        return {}
    mapping = {}
    for i, line in enumerate(blocks[-1].strip().split("\n"), 1):
        line = line.strip()
        m = re.match(r"- x\d+\s+\[([^\]]+)\]\s+(.+)", line)
        if m:
            mapping[i] = f"[{m.group(1)}] {m.group(2)}"
    return mapping


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw", action="store_true", help="打印原始模型输出")
    args = p.parse_args()

    if not OUT.exists():
        sys.exit(f"{OUT} not found. Run pipeline first.")

    data = json.loads(OUT.read_text())
    text = data.get("content") or (data.get("choices", [{}])[0].get("message", {}).get("content", ""))
    if args.raw:
        print(text)
        return

    if not text.strip():
        print("(empty output from model)")
        sys.exit(1)

    result = extract_json(text)
    if result is None:
        print("无法解析 JSON, 模型可能格式漂移")
        print("原始输出:")
        print(text[:500])
        sys.exit(1)

    topics = load_topics()
    yes = [x for x in result if x.get("verdict") == "YES"]
    hold = [x for x in result if x.get("verdict") == "HOLD"]
    no = [x for x in result if x.get("verdict") == "NO"]

    print(f"总计: {len(result)} 条 | YES={len(yes)} HOLD={len(hold)} NO={len(no)}")
    print()
    if yes:
        print(f"🟢 YES ({len(yes)}):")
        for x in yes:
            title = topics.get(x["id"], f"#{x['id']}")
            print(f"  [{x['risk']}] {title}")
            print(f"       角度: {x.get('angle', '')}")
    if hold:
        print(f"\n🟡 HOLD ({len(hold)}):")
        for x in hold:
            title = topics.get(x["id"], f"#{x['id']}")
            print(f"  [{x['risk']}] {title}")
            print(f"       角度: {x.get('angle', '')}")
    print(f"\n🔴 NO: {len(no)} 条 (未展示)")

    # 保存结果
    (HERE / "last-result.json").write_text(json.dumps({
        "yes": yes, "hold": hold, "no_ids": [x["id"] for x in no],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
