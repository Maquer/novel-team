# P0 待办 backlog — 2026-09-23

> 来源：`memory/patterns-20260922.md` + 归档笔记提取
> 规则：每篇研究必须触发至少 1 条 P0 落地（"研-建对赌"）

## Tier 1：iSH 环境刚性约束（8 项）

| # | 项目 | P0 项 | 影响 | 状态 | 行动 |
|---|------|------|------|------|------|
| 1 | TrendRadar | Python 3.12+ 硬门槛 | 99.2% 单人主导，与 re-souo-ju-he 重合 | 已归档 | 等待社区开放 3.11 版本 |
| 2 | PandaStack | 无 /dev/kvm、no Docker Compose、no Apple Silicon | 5/5 本地与此项目全核不可用 | 已归档 | 项目组内做沙箱方案替代 |
| 3 | higgsfield | 28 个月零提交 | 存疑 → 归档 | 已归档 | 关注开发者是否恢复 |
| 4 | archify | iSH realpath ENOENT + Node stderr JSON 解析失败 | 2 个硬坑但全链路可用 | 已归档 | 现有坑的客户端绕行方案 |
| 5 | avoid-ai-writing | 16/23 文件无评测语料，23条"实测"全是散文引用 | 质量评估能力未积淀 | 已归档 | 待找到有效评测方式 |
| 6 | writing-dna-skill | 无 CI/test/度量脚本/评测语料，642 字符超规范 | 源码仓库吞声难 | 已归档 | 需建立真实评测框架 |
| 7 | UPing scroll | pip install-timeout、auto-deprecated、full package writeup | 脚本不稳定 | 已归档 | 升级脚本版本 |
| 8 | Better Claw | 4069 行 / 78 refs / 339 tests / 5005 L1 entries | 框架过大失控 | 已归档 | 拆分子模块 |

## Tier 2：跨项目能力缺口（8 项）

| # | 项目 | P0 项 | 影响 | 状态 | 行动 |
|---|------|------|------|------|------|
| 9 | MDD Sim Gateway | 48 assets/6 平台发布工程（含 Docker 发布 workflow） | 可作为跨平台分发参照 | 已归档 | 迁移到 minis-cli |
| 10 | Video-shotcraft | Remotion 需 headless Chrome + GPU | 视频生成路径 | 已归档 | 尝试 iSH 无 GPU 替代方案 |
| 11 | DASH iOS | 同一代码路径 iOS 模拟器 +真机 SDK | 两类 iSH 不可用 | 已归档 | 评估 phone harp API 替代 |
| 12 | Easel ZJU-REAL | 112 skills、no CI、Apache-2.0 | 开源但无测试 | 已归档 | 若开发入库可迁移 |
| 13 | Edict | 33 entries、22 commits、1 contributor | 共识水平低 | 已归档 | 进展缓慢 |
| 14 | flyhack | 30k memories / 34 stars / 多层分发 | 小众但有意可参考 | 已归档 | 跳过 |
| 15 | It'sAi | 1483 lines / 293 refs / 4 metrics | 高级别文献级设计 | 已归档 | 跳过 |
| 16 | KLP | deepseek v3.7、web UI、desc ≤9 chars | 无需立即 |

## Tier 3：组件级技术债（4 项）

| # | 项目 | P0 项 | 影响 | 状态 | 行动 |
|---|------|------|------|------|------|
| 17 | Veriton | no Docker Compose / no iPython kernel | 无任何替代路径 | 已归档 | 超时待审查 |
| 18 | Symbolics | 使用 curl 废弃 raw.githubusercontent.com | git clone 不再可用 | 已归档 | 使用 github-raw.sh |
| 19 | Google Cache | API query 401 错误 | 反爬策略失效 | 已归档 | 复核或替代方案 |
| 20 | Go MDX Source Code | 2 分钟内完成、大语言模型训练 | iSH 上不了 | 已归档 | 改动缓慢 |

## Tier 4：次优先级

| # | 项目 | P0 项 | 影响 | 状态 | 行动 |
|---|------|------|------|------|------|
| 21 | AI decoder | Gemini-3.5 模型 | 直接功能对比 | 已归档 | 跳过 |
| 22 | Click Freshchat | 7 metrics + PR | 工具替代比较 | 已归档 | 跳过 |
| 23 | Magic-Cloud | 无 HTTP 监听 假桥架检测 安全可靠性 | 安全领域增补 | 已归档 | 采集信息 |
| 24 | Git 全局配置残留 | SOCKS5 代理导致 clone 失败 | 环境问题 | 已归档 | 已清除 |
| 25 | DASH iOS | iSH 跑不了 | 同 11 | 已归档 | 同 11 |
| 26 | M8 Windows Tool | 97 star、37 commit、k MDP 模板 | 工具性参考 | 已归档 | 跳过 |

## 执行计划

### 第一批优先（P0 1-8）：即启动

1. **TrendRadar → Python 3.12+ 等待**：在观察组多轮迭代后，若 AMD Radeon Cloud 版本能降至 3.11 以下，直接接入 re-souo-ju-he
2. **archify 绕行**：参考 ITSKILL.md 第三行的 realpath 和 stderr JSON 坑，编写 minis 侧的客户端包装
3. **avoid-ai-writing → 建立真实评测语料**：收集 30 篇+ 样本，找到有效检测/评分方式
4. **writing-dna-skill → 建立评测框架**：从 cc-thinking anti-fabrication gate 模式借鉴，定义 5 维度打分表

### 第二批（P0 9-16）：观察 2 周

- MDD Sim Gateway 发布工程 → minis-cli 多平台分发可参考
- Video-shotcraft / DASH iOS：iSH 环境约束，直接标记不可行

### 第三批（P0 17-26）：超时处理

- Veriton → 评估是否可由 iSH 替代方案覆盖
- Symbolics → 迁移 github-raw.sh

---
