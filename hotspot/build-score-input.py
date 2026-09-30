#!/usr/bin/env python3
"""
build-score-input.py — 从 topics.md 最新区块构造评分输入 JSON

用法:
  python3 build-score-input.py [--top N] [--model MODEL] [--profile TEXT]
输出:
  /var/minis/shared/hotspot/score-input.json

依赖:
  - topics.md 有内容 (先跑 hot-radar.py feed)
"""
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
TOPICS = HERE / "topics.md"
OUT = HERE / "score-input.json"

SYSTEM = """# Role
你是公众号选题筛选器。

# Task
给定选题池和账号定位, 对每个选题输出 verdict/angle/risk 三字段, 严格 JSON 数组输出.

# Schema (必须完全一致, 不得增删改字段名)
{"id":<int>, "verdict":"YES"|"NO"|"HOLD", "match":<int 1-5>, "angle":"<string>", "risk":"low"|"mid"|"high"}

# Rules
1. match 与账号定位匹配度: 5=直接相关, 3=擦边, 1=无关
2. 涉政/灾难/未证实爆料/明星八卦 → verdict=NO
3. YES 总数 ≤ 3
4. 输出全部 id, 不遗漏
5. angle 用具体视角, 禁用"深度解读/独家揭秘/全面剖析"等空话
6. 无解释文字, 无总结, 只输出 JSON 数组"""

PROFILE_DEFAULT = "AI 自媒体, 读者=用 AI 做内容的创作者与开发者"


def load_latest_block(text: str, top: int):
    """取 topics.md 最后一个 '## 时间 TOP N' 区块"""
    blocks = re.findall(r"##\s+[\d\-:\s]+\s+TOP\s+\d+\s*\n(.*?)(?=\n##\s|$)", text, re.DOTALL)
    if not blocks:
        return []
    lines = [l.strip() for l in blocks[-1].strip().split("\n") if l.strip().startswith("- ")]
    # 格式: - x1 [douyin] 标题
    out = []
    for i, line in enumerate(lines[:top], 1):
        m = re.match(r"- x\d+\s+\[([^\]]+)\]\s+(.+)", line)
        if m:
            out.append(f"{i}. [{m.group(1)}] {m.group(2)}")
    return out


def build_user_msg(topics, profile, ids_count):
    return f"""# 账号定位
{profile}

# 选题池
{chr(10).join(topics)}

# 严格要求
- 字段名必须完全等于 id/verdict/match/angle/risk
- verdict 只能是 YES/NO/HOLD
- match 是 1-5 的整数
- risk 只能是 low/mid/high
- 输出必须是这个格式(示例):
[{{"id":1,"verdict":"YES","match":5,"angle":"从AI开发者视角看X","risk":"low"}},{{"id":2,"verdict":"NO","match":1,"angle":"","risk":"low"}}]
- 输出数组外不得有任何文字, 不得有 markdown 代码块
- 输出全部 {ids_count} 个 id
现在输出:"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--profile", default=PROFILE_DEFAULT)
    args = p.parse_args()

    if not TOPICS.exists():
        sys.exit(f"{TOPICS} not found. Run: hot-radar.py feed first")
    topics = load_latest_block(TOPICS.read_text(encoding="utf-8"), args.top)
    if not topics:
        sys.exit("no topics in topics.md (empty or no TOP block)")

    user = build_user_msg(topics, args.profile, len(topics))
    data = {"messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"wrote {OUT.name}  ({len(topics)} topics)")
    print(f"run: minis-model-use run --model glm-5.2 --input {OUT} --output {OUT.parent/'score-output.json'} --max-tokens 4000")


if __name__ == "__main__":
    main()
