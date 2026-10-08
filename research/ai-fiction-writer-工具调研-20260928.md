# ai-fiction-writer 工具调研与融合建议

**调研日期**：2026-09-28
**项目地址**：https://github.com/Wooooooooood/ai-fiction-writer
**Stars**：52 | **Forks**：9 | **License**：MIT | **语言**：Python | **最后推送**：2026-06-28

---

## 一、项目定位

一套面向长篇网络小说的「人机协作」创作系统，将创作流程拆解为 **10 个独立 Skill**：

| # | Skill | 解决什么问题 | 关键输出 |
|---|-------|------------|---------|
| 1 | `novel-analyze` | 不知道写什么、不会设计爽点 | 市场趋势报告、对标书拆文、模块库 |
| 2 | `novel-outline` | 结构松散、节奏失控 | 卷章大纲、细纲、爽点与钩子规划 |
| 3 | `novel-character` | 角色 OOC、关系混乱 | 角色卡、关系图谱、角色弧线 |
| 4 | `novel-knowledge` | 时代背景错漏、物价/品牌穿帮 | 时间线、物价表、品牌对照 |
| 5 | `novel-worldbuilding` | 世界观崩坏、地图矛盾 | 世界总览、动态迷雾地图、历法 |
| 6 | `novel-logic` | 前后文不一致、逻辑漏洞 | 微逻辑卡、动作前四问、知情边界 |
| 7 | `novel-progress` | 写到哪忘了、伏笔丢了 | 章节树、字数统计、状态流转 |
| 8 | `novel-writing` | AI 写出的东西和前文不接 | 上下文注入模板、段落级硬阻塞 |
| 9 | `novel-humanizer` | 文字机械、情感直给 | 9 维度评分、质量趋势追踪 |
| 10 | `novel-review` | 不知道改哪里、找不到毒点 | 编辑/读者/平台/作者四维审稿 |

---

## 二、核心创新（本项目独有或最强）

### 创新 1：修改模式（Modify Mode）—— 小改动不走完整流程

**核心设计**：区分「写作模式」和「修改模式」两种工作流。

| 环节 | 写作模式 | 修改模式 |
|------|---------|---------|
| 微逻辑卡 | 必须填写 | 不重写 |
| 动作前四问 | 每段必须 | 不重新过 |
| HTML 注释 | 每段添加 | 按需更新 |
| 逻辑矩阵 | 章末生成 | 涉及逻辑变化时更新 |
| 质检 | 完整 humanizer + review | 用户要求时才跑 |
| 字数同步 | 变化>500字必须同步 | 小改动（<500字）可跳过 |

**状态降级规则**：
- `final` 状态被修改 → 自动降级为 `polishing`
- 小改动（<500字且未涉及关键设定）→ 保持原状态不变，仅记录修改事实
- 涉及关键设定/人物关系转折/时间线 → 无论字数都必须降级

**对现有 novel-team 的借鉴价值**：⭐⭐⭐⭐⭐
> 当前 `gate-check.py` 每次都是全量跑，小改动也要过完整门禁。引入修改模式可大幅降低日常修订的 token 消耗。

---

### 创新 2：动作前四问（Paragraph Four Questions）—— 段落级硬阻塞

在写每一段正文之前，必须通过四个问题的检查：

| 问题 | 作用 | 不通过后果 |
|------|------|-----------|
| **谁在场？** | 明确这段中出现的人物及位置 | 人物凭空出现或消失 |
| **他们刚在哪？** | 与上一段/上一章的时间和空间衔接 | 瞬移、时间跳跃 |
| **他们为什么要这么做？** | 动机符合身份、关系、情绪、目标 | 行为突兀、OOC |
| **这个信息/道具/称呼从哪来的？** | 前文有铺垫，符合知情边界 | 信息穿帮、设定吃书 |

**记录格式**（`.novel/logic/paragraph-checks/ch{NN}-paragraphs.md`）：
```markdown
## 第 N 章段落四问记录

### 段落 1
**正文**：主角推门进来，李总已经在会议室坐了十分钟。
- 谁在场？主角、李总（秘书在门外等候）
- 他们刚在哪？主角从办公室过来，李总从家中直接到会议室
- 为什么要这么做？主角按约来汇报，李总要听方案
- 信息/道具来源？会议室是昨天秘书预订的（ch04）
- **判定**：通过
```

**对现有 novel-team 的借鉴价值**：⭐⭐⭐⭐⭐
> 当前 `guard-v6.py` 是章节级检查，`fact-snapshot.py` 是事实快照。四问机制填补了「段落级硬阻塞」的空白——在写下一段之前就必须通过，而不是写完整章后再找补。

---

### 创新 3：HTML 注释标注（Draft Phase Logic Tagging）

正文初稿阶段，每个段落前加 HTML 注释作为逻辑追踪标记，定稿前清理：

```markdown
<!-- LOGIC: time=09:15 | loc=公司会议室 | present=主角,李总 | info=主角知道B，李总不知道C -->

主角推门进来，李总已经在会议室坐了十分钟。
```

**字段含义**：
- `time`：当前时间
- `loc`：当前精确地点
- `present`：在场人物
- `info`：关键信息状态
- `pov`：当前视角

**作用**：
- 一眼看出时间是否跳跃
- 一眼看出地点是否合理
- 一眼看出人物是否在场
- 便于后续自动生成逻辑矩阵

**对现有 novel-team 的借鉴价值**：⭐⭐⭐⭐
> 当前没有段落级的逻辑标注机制。此机制可将逻辑追踪下沉到段落粒度，极大降低逻辑错误漏检率。

---

### 创新 4：知情边界追踪（Info Boundary Tracking）

`.novel/tracking/知情边界.md` 防止信息穿帮的核心工具：

```markdown
## 当前各角色知情状态

| 角色 | 知道 | 不知道 | 信息来源 |
|------|------|--------|---------|
| 主角 | A、B、C | D、E | ch01 知道 A，ch03 知道 B，ch04 知道 C |
| 李总 | A、D | B、C、E | ch02 知道 A，ch04 知道 D |
| 秘书 | A | B、C、D、E | 仅知道公开场合信息 |

## 本章信息变化
- ch05-scene01：主角告诉了李总 B → 李总知道 B
- ch05-scene02：秘书偷听到 C → 秘书知道 C（但主角和李总不知道秘书知道）

## 潜在信息冲突预警
- 李总知道 B 后，按他的性格应该立刻行动，不能装作不知道
- 秘书知道 C 是秘密知情，后续不能让她在公开场合"自然"提到 C
```

**对现有 novel-team 的借鉴价值**：⭐⭐⭐⭐⭐
> 当前 `guard-v6.py` 有四道防线但无专门的"知情边界"追踪。此机制专治"角色知道了不该知道的信息"类穿帮。

---

### 创新 5：九维质检评分体系

`novel-humanizer` 的评分维度比现有 `humanizer-check.py` 更全面：

| 维度 | 权重 | 检测要点 | 合格线 |
|------|------|---------|--------|
| 逻辑性 | 18% | 时间线连续、设定一致、新增配角已建档 | 85分 |
| 角色一致性 | 16% | 言行是否符合档案、OOC | 85分 |
| 世界观一致性 | 8% | 地点/势力/规则一致 | 85分 |
| 时代适配度 | 14% | 禁用词、物价合理性、科技产物 | 80分 |
| 对话自然度 | 11% | 口语省略、方言痕迹、符合角色 | 80分 |
| 文学性 | 10% | 五感描写、比喻新鲜度、句式变化 | 75分 |
| 情感表达 | 10% | 避免情感直给、动作替代 | 80分 |
| 节奏感 | 9% | 对话/动作/描写的平衡 | 75分 |
| 去系统化 | 4% | 系统面板、数据流、机械表达 | 90分 |

**对现有 novel-team 的借鉴价值**：⭐⭐⭐⭐
> 当前 `humanizer-check.py` 主要检测 tier_1a AI 词汇，缺少世界观一致性、时代适配度、情感表达等维度。可将其升级为九维评分。

---

### 创新 6：动态迷雾地图解锁

地图不是一次性画完的，而是随正文描写逐步解锁的**迷雾地图**：

| 层级 | 范围 | 初始状态 | 解锁方式 |
|------|------|---------|---------|
| L0 世界图 | 全球/全大陆 | 已解锁 | 项目初始化 |
| L1 区域图 | 省/州/城市集群 | 迷雾 | 正文首次提到 |
| L2 城市图 | 单个城市内部 | 迷雾 | 正文首次进入 |
| L3 场景图 | 建筑、街道、室内 | 迷雾 | 正文首次描写 |
| L4 动态细节 | 场景内物品、人物位置 | 迷雾 | 正文描写到具体细节 |

**解锁流程**：
```
每章写完后 → AI 扫描正文提取地名/新地点 → 生成 map-update-suggestion.md
→ 作者确认 → 写入 .md + .json → 调用 generate_map.py 重新生成 .svg + .html
```

**对现有 novel-team 的借鉴价值**：⭐⭐⭐
> 当前 `story-graph.py` 是静态知识图谱。此机制将地图从"一次性构建"变为"随写作逐步展开"，更贴合长篇小说创作的实际节奏。

---

### 创新 7：蝴蝶效应分叉追踪

在大纲编排中，每个节拍可标记为「分叉点」：

```markdown
#### 节拍 3：[转折] {转折点}（**分叉点**）
- 原历史：{未受干预的走向}
- 新历史：{干预后的走向}
- 触发条件：{触发条件}
- 影响章节：{ch05, ch12, ch23}
```

**对现有 novel-team 的借鉴价值**：⭐⭐⭐
> 当前大纲系统无分叉追踪。多线叙事/蝴蝶效应题材需要此机制。

---

### 创新 8：双备份机制（Markdown + HTML 自动同步）

```
用户编辑 .md（Source of Truth）
    ↓
自动渲染为 .html（AI 消费层）
    ↓
HTML 保留 YAML frontmatter 作为元数据注释
```

**对现有 novel-team 的借鉴价值**：⭐⭐⭐
> 当前 novel-team 以 Markdown 为主，无 HTML 渲染层。此机制让 AI 消费层和人类编辑层分离，减少解析负担。

---

## 三、与现有 novel-team 重叠项对照

| 本项目 Skill | 现有 novel-team 对应物 | 重叠度 | 建议 |
|-------------|---------------------|--------|------|
| `novel-logic` | `guard-v6.py` + `fact-snapshot.py` | 高（30%） | 借鉴：四问机制 + 知情边界追踪 |
| `novel-humanizer` | `novel-humanizer.py` | 高（40%） | 借鉴：九维评分体系 |
| `novel-progress` | `fact-ledger.py` + `chapter-contract.py` | 中（20%） | 借鉴：状态降级规则 + 修改模式 |
| `novel-character` | `character-hfsman.py` | 中（30%） | 借鉴：`risk_rules` 字段 + 知情边界嵌入角色卡 |
| `novel-worldbuilding` | `extend-world-tianming.py` + `init-world-tianming.py` | 中（20%） | 借鉴：迷雾地图解锁 + L4 动态细节 |
| `novel-outline` | `contract-tree.py` + `outline-precheck.py` | 中（25%） | 借鉴：蝴蝶效应分叉追踪 |
| `novel-review` | `gate-check.py` + `quality-gate.py` | 中（20%） | 借鉴：四维审稿体系（编辑/读者/平台/作者） |
| `novel-writing` | `context-manager.py` + `chapter-contract.py` | 中（30%） | 借鉴：十步流程 + 上下文注入模板 |
| `novel-analyze` | 无 | 低（10%） | 可单独开发：扫榜+拆文 |
| `novel-knowledge` | `knowledge-base.py` | 中（40%） | 借鉴：物价锚点检测 + 品牌对照 |

---

## 四、融合优先级建议

### P0 立即执行（填补核心空白）

| 序号 | 借鉴项 | 实现方式 | 预期收益 |
|------|--------|---------|---------|
| P0-1 | **动作前四问机制** | 新建 `tools/paragraph-four-questions.py` | 段落级逻辑硬阻塞，大幅降低穿帮率 |
| P0-2 | **修改模式** | 扩展 `novel-writing/SKILL.md` + `gate-check.py` 增加 `--mode modify` | 小改动不跑完整门禁，节省 60%+ token |
| P0-3 | **知情边界追踪** | 扩展 `fact-ledger.py` 增加 `info_boundary.md` 生成 | 解决"角色知道了不该知道的信息"类穿帮 |

### P1 近期规划（增强质检维度）

| 序号 | 借鉴项 | 实现方式 | 预期收益 |
|------|--------|---------|---------|
| P1-1 | **九维评分升级** | 升级 `novel-humanizer.py` 至九维评分体系 | 质检覆盖逻辑性/时代适配/情感表达等缺失维度 |
| P1-2 | **蝴蝶效应分叉** | 扩展 `novel-outline/SKILL.md` + `contract-tree.py` | 支持多线叙事/蝴蝶效应题材 |
| P1-3 | **HTML 注释标注** | 在 `novel-writing/SKILL.md` 中增加段落级注释规范 | 初稿阶段逻辑可追溯，定稿前自动清理 |

### P2 中期规划（架构增强）

| 序号 | 借鉴项 | 实现方式 | 预期收益 |
|------|--------|---------|---------|
| P2-1 | **动态迷雾地图** | 扩展 `worldbuilding/` 增加 L1-L4 层级 + `generate_map.py` 调用 | 地图随写作逐步展开，减少一次性构建负担 |
| P2-2 | **双备份同步** | 新增 `md-to-html-sync.py` 脚本 | Markdown 人编辑 + HTML AI 消费，双轨并行 |
| P2-3 | **扫榜拆文工具** | 新建 `tools/scan-benchmark.py` | 接入 `novel-analyze` Skill 能力 |

---

## 五、关键设计取舍分析

### 为什么不照搬整套架构？

1. **技术栈差异**：本项目面向 VSCode 插件，我们面向 iSH Python CLI
2. **Skill 数量**：10 个 Skill vs 我们 70 个工具文件，粒度不同
3. **已有覆盖**：`guard-v6.py`/`fact-snapshot.py`/`humanizer-check.py` 等已部分覆盖其能力

### 最值得融合的 3 个设计

1. **修改模式** —— 解决日常修订效率问题，直接影响使用频率
2. **动作前四问** —— 填补段落级硬阻塞空白，是我们当前最大的逻辑漏洞
3. **知情边界追踪** —— 专治信息穿帮，现有 `guard-v6.py` 未覆盖此维度

---

## 六、归档决策

- **归档位置**：`03-Resources/AI工具/AI小说创作助手 ai-fiction-writer.md`（Obsidian）
- **本地安装**：❌ 不装本地 skill（与现有 novel-team 重叠度高，融合进现有工具而非新增 Skill）
- **融合路径**：按 P0/P1/P2 优先级逐步迁移核心创新到 `novel-team/tools/`

---

## 七、项目元数据

| 字段 | 值 |
|------|---|
| 仓库 | https://github.com/Wookeeper/ai-fiction-writer |
| Stars | 52 |
| Forks | 9 |
| License | MIT |
| 语言 | Python |
| 创建时间 | 2026-06-28 |
| 最后推送 | 2026-06-28（~3 个月前，项目可能已停更） |
| 文件数 | 34 个（10 个 SKILL.md + 2 个脚本 + 示例数据） |
| 总大小 | ~94KB（纯文档+脚本，无运行时依赖） |

> ⚠️ **注意**：最后推送日期为 2026-06-28，距今约 3 个月无更新。需评估项目是否仍在维护。

---

## 八、融合实施记录（2026-09-28）

### P0 已完成

| # | 工具 | 文件 | 状态 |
|---|------|------|------|
| P0-1 | 动作前四问 | `tools/paragraph-four-questions.py` (18KB) | ✅ 完成 |
| P0-2 | gate-check 修改模式 | `tools/gate-check.py` (21KB, v1.2) | ✅ 完成 |
| P0-3 | 知情边界追踪 | `tools/info-boundary.py` (16KB) | ✅ 完成 |

### 核心能力验证

**paragraph-four-questions.py**：
- `init` — 初始化章节检查记录
- `check` — 检查单个段落（返回JSON格式判定结果）
- `verify` — 验证整章四问是否全部通过
- `comment` — 生成 HTML 注释标注 `<!-- LOGIC: time=... | loc=... -->`
- `clean` — 清除初稿阶段的 HTML 注释
- `list` — 列出已记录的四问检查
- 支持段落间连续性检查（`--prev` 传递上一段答案）

**gate-check.py v1.2**：
- `--mode write`（默认）— 完整八项检查（protocol/reference/consistency/unknown_entities/description_consistency/blueprint/ai_tone/hook）
- `--mode modify` — 最小化检查：仅跑 fact_consistency/protocol/blueprint，跳过 ai_tone/word_count/hook
- 退出码：0=通过，1=有阻断

**info-boundary.py**：
- `init` — 初始化知情边界数据
- `add-character` — 添加/初始化角色边界
- `update-know` — 角色获得某信息
- `update-dont-know` — 角色失去某信息
- `check-scene` — 检查场景中是否存在信息泄露风险
- `export` — 导出 Markdown 格式（供人阅读）
- `stats` — 统计信息

### 使用示例

```bash
# 四问检查
python3 paragraph-four-questions.py init --novel-id my-novel --chapter 3
python3 paragraph-four-questions.py check --novel-id my-novel --chapter 3 \
  --text "萧辰踏入演武场..." \
  --who "萧辰、王执事" \
  --where "萧辰从宿舍步行5分钟到演武场" \
  --why "按约定时间前来接受测灵根" \
  --info "约定测灵根是前文ch02已交代"

# 知情边界
python3 info-boundary.py add-character --novel-id my-novel --name 萧辰 --dont-know "血煞门阴谋"
python3 info-boundary.py update-know --novel-id my-novel --character 萧辰 --info "发现铁剑异动" --source "ch03"
python3 info-boundary.py check-scene --novel-id my-novel --characters "萧辰,王执事,旁听弟子" --info "天剑宗秘技"

# 门禁（修改模式）
python3 gate-check.py check --file ch03.md --mode modify
```
