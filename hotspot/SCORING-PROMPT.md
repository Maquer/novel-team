# 热点→选题 AI 评分 Prompt

配合 `hot-radar.py feed` 使用。产出 `topics.md` 后，把当日区块投喂给大模型。

## 实测结论 (2026-09-18)

| 模型 | Schema 遵循 | 输出质量 | 备注 |
|---|---|---|---|
| **glm-5.2** | ✅ 完美 | ✅ 最好 | 有 HOLD 判断、angle 具体到"AI Agent 拆解加息"这种可执行方向 |
| **deepseek/deepseek-v4-flash** | ✅ 完美 | ⚠️ 保守 | YES 阈值高，只挑最直接的匹配 |
| **sensenova-6.8-flash-lite** | ✅ 完美 | ⚠️ 保守 | 输出前有空行，需 strip |
| **deepseek-v4-flash** (sensenova 通道) | ❌ 漂移 | ❌ 用自选字段 | 弃用 |

**关键发现：格式漂移的解药 = user message 末尾给"硬约束 + 具体格式示例"，不是 system prompt。** system prompt 里放规则定义，user 末尾复述硬约束 + 一条示例 = 三个模型全通过。

## 使用方式

```bash
# 1. 抓榜 + 追加到 topics.md
python3 /var/minis/shared/hotspot/hot-radar.py feed

# 2. 拼接输入 (user 消息末尾放硬约束)
python3 /var/minis/shared/hotspot/build-score-input.py

# 3. 投喂给模型
minis-model-use run --model glm-5.2 \
  --input /var/minis/shared/hotspot/score-input.json \
  --output /var/minis/shared/hotspot/score-output.json \
  --max-tokens 4000
```

## System Prompt (固定)

```
# Role
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
6. 无解释文字, 无总结, 只输出 JSON 数组
```

## User Message 模板 (必须完整包含硬约束)

```
# 账号定位
{ACCOUNT_PROFILE}

# 选题池
{TOPICS_FROM_FEED}

# 严格要求
- 字段名必须完全等于 id/verdict/match/angle/risk
- verdict 只能是 YES/NO/HOLD
- match 是 1-5 的整数
- risk 只能是 low/mid/high
- 输出必须是这个格式(示例):
[{"id":28,"verdict":"YES","match":5,"angle":"从AI开发者视角看新架构的工程取舍","risk":"low"},{"id":1,"verdict":"NO","match":1,"angle":"","risk":"low"}]
- 输出数组外不得有任何文字, 不得有 markdown 代码块
- 输出全部 N 个 id
现在输出:
```

## glm-5.2 实测输出样例 (输入 7 条热点)

```json
[{"id":1,"verdict":"NO","match":1,"angle":"","risk":"low"},
 {"id":4,"verdict":"NO","match":2,"angle":"","risk":"low"},
 {"id":12,"verdict":"HOLD","match":3,"angle":"用AI Agent拆解加息影响，演示财经类AI内容的检索、推理与事实校验工作流","risk":"mid"},
 {"id":17,"verdict":"HOLD","match":2,"angle":"聚焦智驾/座舱AI能力作为AI落地案例，给创作者提供产品向选题切入","risk":"low"},
 {"id":18,"verdict":"NO","match":1,"angle":"","risk":"low"},
 {"id":27,"verdict":"NO","match":1,"angle":"","risk":"low"},
 {"id":28,"verdict":"YES","match":5,"angle":"从AI创作者与开发者视角，反思模型变强如何倒逼我们重新理解创造力、判断与协作","risk":"low"}]
```

## 后处理 Python (解析 JSON 输出)

```python
import json, re
raw = json.load(open("score-output.json"))
text = (raw.get("content") or
        (raw.get("choices",[{}])[0].get("message",{}).get("content",""))).strip()
# 剥掉可能的 ```json fence
text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
# 剥掉前导空行/文字
m = re.search(r"\[.*\]", text, re.DOTALL)
result = json.loads(m.group())
yes = [x for x in result if x["verdict"] == "YES"]
hold = [x for x in result if x["verdict"] == "HOLD"]
print(f"YES={len(yes)} HOLD={len(hold)} NO={len(result)-len(yes)-len(hold)}")
```

## 迭代建议 (跑一周后)

- **YES 命中率**: 发出去有阅读量的比例
- **NO 漏报率**: 本可追但被误判 NO 的
- **risk 误判率**: 标 NO 但其实安全的

三项 < 10% 说明 prompt 到位, 否则针对性加规则。
