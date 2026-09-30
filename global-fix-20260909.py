#!/usr/bin/env python3
# Version: 0.1.0
# -*- coding: utf-8 -*-
"""GLOBAL.md 2026-09-09 自我认知迭代修复：去重/决策归档/补目/模型状态刷新"""
P = "/var/minis/memory/GLOBAL.md"
s = open(P).read()

EDITS = [
# A. 头部日期
("**最后更新：** 2026-09-09 21:05", "**最后更新：** 2026-09-09 23:30"),
# B. 技能表补目 jue-ce-bi-huan
("| `skills/wu-ceng-jue-ce/` | 五层决策 | 自定义 | 道法术器势（Grill-Me 决策树 + 系统诊断双模式） |",
 "| `skills/wu-ceng-jue-ce/` | 五层决策 | 自定义 | 道法术器势（Grill-Me 决策树 + 系统诊断双模式） |\n| `skills/jue-ce-bi-huan/` | 决策闭环 | 自定义 | 重大决策四阶段串联（苏格拉底诘问→第一性原理→系统全局→批判性审查），输出 DECISION-LOOP.md |"),
# C. 删除 AI工具表尾部 3 行重复
("| **自动签到面板** | — | `自动签到面板 New API中转站每日签到 BingLi37.md` | API 中转站每日签到 |\n| `skills/gongzhonghao-publish/` | 公众号发布流水线 | 自定义 | 创→排→发→推一站式：爆款写作 + 本地排版(wx-toolkit) + 发布检查 + **API直推草稿箱(gzh-api-push.py)** v2.1 |\n| `skills/ponytail/` | ponytail | 自定义 | AI 编程极简技能（7 层极简阶梯，适用于写代码/修 bug/优化脚本/省 token） |\n| `skills/re-souo-ju-he/` | 热搜聚合 | 自定义 | 发现层 skill：抓 B站+抖音热榜（iSH 直连）+ 微博/知乎走浏览器兜底，赛道词过滤出选题 v0.1.0 |",
 "| **自动签到面板** | — | `自动签到面板 New API中转站每日签到 BingLi37.md` | API 中转站每日签到 |"),
# D1. 可用数与核查注记
("### 当前可用（19 个）", "### 当前可用（23 行，以表为准 | 09-09 复测降级 2 个：agnes-2.5-pro / minimax-m3:free）"),
# D2. agnes-2.5-pro 行删除
("| `agnes-2.5-pro` | OpenAI 5 | L2 | 复杂任务、分析、写作 | Agnes 家族旗舰，功能最全 |\n", ""),
# D3. agnes flash 两行标注
("| `agnes-2.5-flash` | OpenAI 5 | L1 | 快速响应、一般任务 | Agnes Flash，性价比 |\n| `agnes-2.0-flash` | OpenAI 5 | L1 | 一般任务 | Agnes 旧版 Flash |",
 "| `agnes-2.5-flash` | OpenAI 5 | L1 | 快速响应、一般任务 | ⚠️ 09-09 未测，同家族 agnes-2.5-pro 已 Invalid key，疑同源失效 |\n| `agnes-2.0-flash` | OpenAI 5 | L1 | 一般任务 | ⚠️ 同上，用前先测 |"),
# D4. glm-5.2 标注
("| `glm-5.2` | OpenCode | L2 | 中文任务、一般对话 | GLM 系列，中文强 ⚠️ 偶尔限速 |",
 "| `glm-5.2` | OpenCode | L2 | 中文任务、一般对话 | GLM 中文强 ⚠️ 09-09 实锤：minis-model-use 子调用 output_text 恒空，脚本场景禁用，主对话可用 |"),
# D5. nemotron 标注
("| `nvidia/nemotron-3.5-lightning:free` | OpenRouter | L1 | 快速响应 | 免费，稳定 |",
 "| `nvidia/nemotron-3.5-lightning:free` | OpenRouter | L1 | 快速响应 | ⚠️ 09-09 复测 Rate limited，暂列观察 |"),
# D6. minimax 两行
("| `minimax/minimax-m3:free` | OpenRouter | L1 | 中文 | 免费 |\n| `minimax/minimax-m2.7:free` | OpenRouter | L1 | 中文 | 免费 |",
 "| `minimax/minimax-m2.7:free` | OpenRouter | L1 | 中文 | ⚠️ 09-09 子调用失败(1s即败)，用前先测 |"),
# D7. deepseek-v4-flash 长prompt注记
("| `deepseek/deepseek-v4-flash` | OpenRouter | L0 | 快速响应 | 免费，余额 $0 可用 |",
 "| `deepseek/deepseek-v4-flash` | OpenRouter | L0 | 快速响应 | 免费可用 ⚠️ 长 prompt 需 max_tokens≥6000，否则思维链吃满返回空 |"),
# D8. glm-5.3-flash 注记（今日主力审计模型）
("| `z-ai/glm-5.3-flash` | OpenRouter | L1 | 中文 | 免费 |",
 "| `z-ai/glm-5.3-flash` | OpenRouter | L1 | 中文 | 免费，09-09 审计主力（3/5 成功，长任务偶发空返回需重试） |"),
# D9. 下线区追加
("| `sensenova-6.7-flash-lite` | sensenova | 404 model route not found（下线） |",
 "| `sensenova-6.7-flash-lite` | sensenova | 404 model route not found（下线） |\n| `minimax/minimax-m3:free` | OpenRouter | 404（09-09 实测，09-06 记录已过期） |\n| `agnes-2.5-pro` | OpenAI 5 | Invalid API key（09-09；09-07 还是余额尽，恶化为 key 失效） |"),
# D10. 路由策略更新
("> ⚠️ **推荐路由策略**：主力 `agnes-2.5-pro`（OpenAI 5）或 `glm-5.2`（OpenCode）；快速响应用 `sensenova-6.8-flash-lite`；简单任务用 `mimo-v2.5` / `cohere-north-mini-code`；轻量/免费备选用 OpenRouter `:free` 模型（nvidia/nemotron-3.5-lightning / minimax-m3 / deepseek-v4-flash）；AMD Radeon Cloud 作多模态+低成本备选（`DeepSeek-V4-Flash-Vision-Exp` 图像 / `MiniCPM5-1B` 极致轻量）。",
 "> ⚠️ **推荐路由策略（09-09 复测版）**：子调用/脚本首选 `z-ai/glm-5.3-flash`（OR free）与 `deepseek/deepseek-v4-flash`（OR free，max_tokens≥6000）；快速响应 `sensenova-6.8-flash-lite`；简单任务 `mimo-v2.5` / `cohere-north-mini-code`；多模态+低成本 AMD Radeon Cloud（`DeepSeek-V4-Flash-Vision-Exp` / `MiniCPM5-1B`）。~~agnes-2.5-pro~~（key 失效）~~minimax-m3~~（404）。脚本场景禁用 glm-5.2（子调用返回空）。主对话模型路由不受此限。"),
# E1. 决策表：删最旧4条
("| 2026-08-23 | Darwin Skill 2.4 升级：失败归因分类器 + 教训抽象去实例化 + 可执行验证 + 去重/help-hurt 淘汰 + 跨模型迁移验证 | 北大 VeriSkill/SESA 论文 → 四机制差距分析 → Darwin v2.4 |\n| 2026-08-23 | Darwin Skill 2.3 升级：双检索路径（OpenSkill）+ 持久决策历史（SkillHone）+ 脱敏评估反馈 | vibe life 公众号文章 → 差距分析 → Darwin v2.3 |\n| 2026-08-22 | 反馈层升级（PEV 确定性传感器+失败飞轮+回归测试） | 益牙yeeyaa 文章 |\n| 2026-08-22 | Skill Registry + Eval Gate + 最小生产结构 三件套落地 | SOTA AI 文章 → Skill 缺口修复 |\n", ""),
# E2. 归档注记追加 + 新决策行
("> ⚠️ 已归档（超过10条上限）：2026-08-12 全量自检 / 08-19 workspace丢失模式 / 08-21 第二大脑架构 / 08-22 MagicMirror² / 08-22 错误模式+Skill生命周期 / 08-22 MCP接口 / 08-23 Darwin 2.1-2.2 / 08-23 Dots Provider\n",
 "> ⚠️ 已归档（超过10条上限）：2026-08-12 全量自检 / 08-19 workspace丢失模式 / 08-21 第二大脑架构 / 08-22 MagicMirror² / 08-22 错误模式+Skill生命周期 / 08-22 MCP接口 / 08-23 Darwin 2.1-2.2 / 08-23 Dots Provider / 08-22 Skill三件套 / 08-22 反馈层PEV / 08-23 Darwin 2.3 / 08-23 Darwin 2.4\n| 2026-09-09 | SOUL.md 第三轮自我认知迭代：规则必须带执行载体（会话启动扫描/写后验证/空输出=故障），新增「数据与模型可靠性」「状态与恢复」 | soul-audit-v3 三维审计 20 findings（E5.0/C5.0/L7.0），根因：依赖\"主动想起\"的跨会话规则全部落空 |\n"),
# F. §六 工具表加行
("| **GLOBAL.md 验证器** | 🟢 新增 | `/var/minis/shared/global-verify.py` | 自动检查 GLOBAL.md 一致性（技能目录/模型/文件引用/决策记录/版本），`python3 global-verify.py` 运行 |",
 "| **GLOBAL.md 验证器** | 🟢 新增 | `/var/minis/shared/global-verify.py` | 自动检查 GLOBAL.md 一致性（技能目录/模型/文件引用/决策记录/版本），`python3 global-verify.py` 运行 |\n| **SOUL 第三轮审计（证据驱动）** | 🟢 新增 | `/var/minis/shared/soul-audit-v3.py` | 4维多模型交叉审计+运行证据包（E实证/S结构/L语言/C覆盖），报告 `shared/soul-audit-v3/report.md` |"),
]

fail = []
for i, (old, new) in enumerate(EDITS):
    n = s.count(old)
    if n != 1:
        fail.append(f"E{i:02d} count={n}")
        continue
    s = s.replace(old, new)
open(P, "w").write(s)
print("applied:", len(EDITS) - len(fail), "/", len(EDITS))
print("FAILED:", fail if fail else "none")
