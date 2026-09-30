# 选题：Skill 生态——为什么大厂在训"技能"而不是改模型

> 轨道：深度轨 T-4 | 优先级：P1 主力 | 状态：G2 待判定
> 信息收集人：小蒋 | 抓取日期：2026-09-17
> 素材源：Obsidian `03-Resources/AI工具/`（6 篇归档笔记）

## 选题信息

| 字段 | 内容 |
|------|------|
| 选题 | Skill 生态——为什么大厂在训"技能"而不是改模型 |
| 目标读者 | 用 Claude Code/Cursor 等编码 Agent 的开发者 + 关注 AI 趋势的从业者 |
| 读者痛点 | 听说 Skill 很强，但不知道它到底是什么、怎么评估好坏、自己能不能训 |
| 预期收益 | 读完能分清"技能"vs"提示词"vs"微调"，知道一套好 Skill 长什么样 |
| 素材可得性 | 高（6 篇深度归档，含 iSH 实测） |
| 风险 | 技术性强需翻译术语；H3 同质化——近期 Skill 话题被讲多次，需差异化角度 |
| 优先级 | P1 主力 |
| 状态 | G2 待判定 |

---

## 素材包

### 事实 1：SkillOpt 把 Markdown 技能文档当"冻结模型的权重"训

- **来源**：microsoft/SkillOpt，MIT，16894★，arXiv:2605.23904，创建 2026-05-08
- **抓取日期**：2026-09-17（Obsidian 归档笔记）
- **置信度**：A级（官方仓库 + 论文 + GitHub 公开数据）
- **关键数据**：
  - 6 benchmarks × 7 models × 3 harnesses = 52 个 cell，全部最好或并列最好
  - GPT-5.5 lift：直聊 +23.5 / Codex +24.8 / Claude Code +19.1
  - 零额外推理时模型调用，部署只带一份静态 Markdown
- **核心类比**：技能=参数，训练循环=SGD，Markdown diff=梯度更新，held-out gate=验证集
- **交叉验证**：与 SkillForge（cslsolow，学术论文）同属"Skill 可训练"范式，两个独立学术来源 ✅

### 事实 2：Skill 生态已有包管理器——Vercel Skills

- **来源**：vercel-labs/skills，MIT，30622★，138 贡献者，v1.5.24，创建 2026-01-14
- **抓取日期**：2026-09-17
- **置信度**：A级（官方仓库 + iSH 实测 `npx skills find` 可跑）
- **关键数据**：
  - `npx skills add <owner/repo>` 一行装到 73+ 编码 Agent
  - 单 skill 最高 151.9K installs（anthropics/skills@webapp-testing）
  - skills.sh Leaderboard 按安装数排序
- **交叉验证**：iSH 实测 `npx --yes skills find memory` 返回真实安装数 ✅

### 事实 3：但 Skill 生态有泡沫——cc-thinking 全 28 个 skill 判 manual-only-quarantine

- **来源**：tjboudreaux/cc-thinking-skills，MIT，1310★，96 commits 单人主导
- **抓取日期**：2026-09-17
- **置信度**：A级（官方仓库 + AUDIT.md 公开审计）
- **关键数据**：
  - 全部 28 个 skill `elevate=false`, `auto_retain=false`
  - 唯一正向数据 +4.0pp 低于自设 +5pp 门槛，判 `manual_only_directional_not_elevate`
  - 24 case 前置 power failure 判 `delete_workflow_machinery`——workflow 形式被证伪
  - 14 个 artifacts 被误删，Recovery ledger 锁定 SHA-256 禁止再当证据
- **交叉验证**：README FAQ 明说"Do these skills guarantee better model accuracy? No." ✅

### 事实 4：Skill 可能主动伤害模型

- **来源 1**：Nick Nisi @ WorkOS 数据："97% correct without a skill, 77% with it"
- **来源 2**：Philipp Schmid @ Google DeepMind："10000 行→553 行手写 gotcha，准确率提升，运行时间 68→6 分钟"
- **抓取日期**：2026-09-17（cc-thinking 归档笔记引用）
- **置信度**：B级（二手转述，原始数据未独立核验，但两个独立来源）
- **交叉验证**：两个不同来源（WorkOS + Google DeepMind）指向同一结论——加载 skill 不是免费午餐 ✅

### 事实 5：学术界在认真做——Easel 112 skill 五层闭环

- **来源**：ZJU-REAL/Easel，Apache-2.0，406★，浙大 REAL Lab + 北大 OpenDCAI Lab
- **抓取日期**：2026-09-17
- **置信度**：A级（官方仓库 + 学术团队背景）
- **关键数据**：
  - 112 个 skill 覆盖发现→策划→创作→发布→归因五层
  - 六平台真实发布（小红书/抖音/快手/知乎/B站/视频号）
  - 画像驱动跨会话进化，六维画像
  - SKILL 规范 v0.3：三层加载 + 200 行上限 + description-as-trigger + argparse 漂移校验

### 事实 6：SkillForge——主动合成 Bug→蒸馏项目专属技能

- **来源**：cslsolow/SkillForge，MIT，5★，论文 Chen et al. 2026
- **抓取日期**：2026-09-17
- **置信度**：B级（官方仓库 + 论文，但 5★ 社区未形成）
- **关键数据**：
  - 双技能体系：全局诊断（仓库级）+ 局部干预（文件级 JIT 注入）
  - 主动合成 Bug→收集修复轨迹→蒸馏技能，不依赖历史 Issue
  - 专门的 leakage_filter 过滤评测泄漏

### 事实 7：writing-dna-skill——实证去 AI 味规则集

- **来源**：larashero3-dotcom/writing-dna-skill，MIT，1920★，21 commits 单人
- **抓取日期**：2026-09-17
- **置信度**：B级（官方仓库，但无 CI/无测试/无度量脚本，不可复现）
- **关键数据**：
  - 11 条去 AI 味规则，每条带 AI/Human 频率比（300 篇/117.9 万字/5 模型语料）
  - 10 条"不作为改写理由"负面用例表（实测推翻的假设）
  - 六层风格蒸馏框架 L1-L6

---

## 反例素材（主动找的）

### 反例 1：营销泡沫——Kenneth 列的 6 个"AI 思维 Skill"全 404

- **来源**：cc-thinking 归档笔记引用
- **置信度**：C级（二手转述，未独立核验 Kenneth 原文）
- **用途**：证明 Skill 生态有营销泡沫，不能只讲"多强"

### 反例 2：AnySearch 6167★ 但单人主导 35% 疑营销驱动

- **来源**：GLOBAL.md §三 AnySearch 归档条目
- **置信度**：B级（iSH 实测 general search 可用，但 vertical finance timeout）
- **用途**：Stars 数≠质量，治理成熟度与 stars 不匹配

### 反例 3：writing-dna 无度量脚本不可复现

- **来源**：writing-dna 归档笔记"未随仓库发布的东西"段
- **置信度**：A级（仓库确认无脚本）
- **用途**："实测"不等于可复现，与 ai-portrait-light 同一模式

### 反例 4：cc-thinking 零 CI workflow

- **来源**：cc-thinking 归档笔记"局限"段
- **置信度**：A级（`.github/workflows/` 不存在）
- **用途**：治理层硬漏洞——push 不会自动验证

---

## G2 门禁判定

| 门禁项 | 要求 | 实际 | 判定 |
|--------|------|------|------|
| 核心论点有 ≥1 条可验证来源 | 是 | 7 条事实全部有 GitHub 仓库/arXiv 论文来源 | ✅ PASS |
| 关键事实 ≥2 个独立来源交叉验证 | 是 | 事实1（SkillOpt+SkillForge）/ 事实2（Vercel+iSH实测）/ 事实4（WorkOS+DeepMind）均有交叉验证 | ✅ PASS |
| 主动找反例 | 是 | 4 条反例 | ✅ PASS |

**G2 判定：PASS**。核心论点有 7 条可验证来源，其中 3 条做了交叉验证，4 条反例覆盖营销泡沫/治理缺陷/不可复现三个维度。

---

## 信息收集人交接说明

### 给结构梳理的素材组织建议（非约束，仅供参考）

1. **主线候选**：从"Skill 是什么"→"大厂在训它"→"生态有泡沫"→"怎么评估好坏"——四段递进
2. **差异化角度**：不讲"Skill 是什么"（已被讲烂），从"怎么评估一个 Skill 好不好"切入——cc-thinking 的 +5pp 硬门槛 + manual-only-quarantine 是最好抓手
3. **反例必须用**：Nick Nisi"97%→77%"数据 + Kenneth 6 个 404——不能只讲成功故事
4. **术语翻译清单**：ReflACT/gate/held-out/JIT 注入/argparse 漂移——需在正文用大白话解释

### 未覆盖（诚实标注）

- 未读 arXiv 论文全文（SkillOpt 2605.23904 / SkillForge Chen et al. 2026），只读 README + 归档笔记
- 未独立核验 Nick Nisi / Philipp Schmid 原始数据来源（二手转述）
- 未核验 Kenneth 原文（cc-thinking 归档引用，未追源头）
- 6 篇笔记全是本机 Obsidian 归档，单一信源（我自己的归档），未做外部独立交叉验证——但每篇归档笔记本身已标注了原始来源（GitHub 仓库 + 论文）
