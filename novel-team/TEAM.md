---
name: novel-team
description: "小说创作团队——以女娲方法论驱动，从网文创作到IP开发的全流程智能体团队。触发：用户说「小说团队」「novel」「写小说」「天命」。\n核心：任务驱动 + 状态可见 + 创意蒸馏 + 数据治理"
version: "v2.0.0"
minis_url: minis://shared/novel-team/TEAM.md
created: 2026-09-27
last_update: 2026-09-29
---

# 小说团队 · TEAM.md

> v2.0.0 | 2026-09-30（架构升级：novelkit 框架层 + 13 插件门禁 + 统一阈值 config + CLI 兼容垫片。删除 v1 上帝对象脚本集，改用可插拔检查插件）
> v0.70.0 | 2026-09-29（团队优化·防短篇+连贯过渡：① SOP 加第7条「场景过渡连贯」准则；② gate-check 加场景跳跃检测（SCENE_JUMP_PATTERNS）；③ 角色灵魂模板加「心理描写指引」；④ 建 chapter-prompt.yaml 标准模板；⑤ 建 world-pack-schema.json 规范）
> v0.69.0 | 2026-09-29（二次清空：删除 multi-model 对比报告 + 验证项目数据全部清除）
> v0.68.0 | 2026-09-29（长篇框架升级：① gate-check 字数门禁升级 soft_min 1500/min_words 2500/critical True；② SOP 加第6条「长篇节奏控制」；③ 大纲模板加 volumes 卷结构；④ gonggong ch1-ch2 扩写至 2100+/1558 字）
> v0.66.0 | 2026-09-29（新项目 gonggong《我的公公叫康熙》：清代宫廷言情·留白式，六章 8094 字，身份反转 + 全篇伏笔闭环；项目骨架：世界包/双角色/大纲/账本齐全；门禁 P0 全绿）
> v0.65.0 | 2026-09-29（zombie-farm 项目落地 + 技术债清理：① 大纲改『延迟揭示+它不止一把』结构；② 第二三章按新悬念重写（ch2 空间与钥匙/ch3 第二把）；③ 第一章融合终版 = agnes 质感底 + 钩子（P0/P1/P2 全绿）；④ 事实账本 16→19 条（空间揭示归 ch2 + 3 条新事实）；⑤ gate-check 修 FactLedger 硬编码 my-novel→self.project_id；⑥ 清 my-novel 18 个 reports 垃圾；⑦ 世界脚本 extend/init-world-tianming 纳入 resolver（去 my-novel 硬编码，加 --project））
> v0.63.0 | 2026-09-29（门禁质量改进·多模型测试驱动：① 字数门禁软化 min 2000→软下限 soft_min 900（900~2000 区间静默通过，根治『凑字数灌水』）；② 新增 cliche 套路/AI腔检测（P2 提示级，命中 9 类黑话不阻断）；③ fact-ledger KeyError BUG 修复（facts→knowledge 键归一化）；④ 多模型实测：仅 agnes-2.5-flash 可完整跑通写作任务，Radeon 全线超时 / OpenRouter free 剩 24token / agnes-2.0 已失效）
> v0.62.0 | 2026-09-29（代际项目守卫落地：project_guard.py 唯一路径入口 + 4 代际命令 + 10 工具路径统一 + 25 顶层目录归位）
> v0.61.0 | 2026-09-29（门禁阻断层清零：修 10 BUG，12/20 章可真实阻断；项目数据全清 636 文件，备份于 shared/novel-team-data-20260929.tar.gz）
> v0.60.0 | 2026-09-28（第1章完成+hook扩展版）
> 核心原则：任务驱动 + 状态可见 + 创意蒸馏 + 数据治理
> 状态：🟢 优秀，可启动创作

---

## 版本登记纪律（v0.52 新增）

提交任何改动前，**先查变更记录表**确认最新已登记版本号，不与自己撞号：

```bash
# 最新登记号在哪：
grep -n "| v0\." TEAM.md | tail -5
# 或 git log 快速看：
git log --oneline TEAM.md | head -3
```

- **规则**：若最新版本号是 X.Y，自己这次改动登记为 X.(Y+1)，不要覆盖已有编号。
- **例外**：如果上一个 commit 已经登记了 X.(Y+1)，则顺延 X.(Y+2)。
- **反例**（本次教训）：09-28 并发会话用 v0.49 标号（Biz Novel Studio），我的节拍校验让位改号 v0.50；若提交前查表，可提前避让或合并。

---

## 本项目是做什么的目是做什么的

从网文创作 → 平台发布 → IP开发的全流程团队。

核心问题：**题材选择、平台策略、爆款公式、IP价值**

---

## 🎭 《天命》核心创作DNA（女娲蒸馏）

> 由女娲方法论提炼自成功网络小说的通用规律，指导《天命》创作决策

### 一、境界体系设计原则

| 原则 | 具体规则 | 《天命》应用 |
|------|---------|-------------|
| **阶梯感** | 每重之间实力差距需可感知，但不可过大（最多差一个小境界） | 淬体九重→炼气四阶，每阶间有明确能力差异 |
| **战力锚点** | 大境界差距=绝对压制（炼气碾压淬体），小境界差距=可逆（同境界靠技巧/装备） | 萧辰淬体三重可战王大淬体四重，但不能敌炼气初期 |
| **瓶颈逻辑** | 每次突破需有明确契机（悟道/奇遇/生死危机），不可凭空升级 | 萧辰首战王大时突破为淬体四重，符合"生死危机触发"原则 |
| **后期膨胀防控** | 每新增一个大境界，前境界战力必须重新标定 | 筑基以上暂不展开，避免前期战力崩坏 |

### 二、节奏控制原则

| 时段 | 内容密度 | 情绪曲线 |
|------|---------|---------|
| **开篇前3章** | 冲突密集+设定释放≤30%+悬念钩子≥2个+**至少1个L2+爽点（破冰）** | 高紧张→小释放→更大悬念 |
| **卷中阶段** | 每3-5章一个小高潮，每15-20章一个卷中高潮 | 平稳中递进，避免连续平淡 |
| **章末** | 必须有"钩子"（新信息/新威胁/情感转折） | 让读者"不得不点开下一章" |

**爽点四层标注（v0.50.0 新增，Progression-Architect 借鉴，见世界包 law_爽点_0001）**

大纲每章标注 `thrill` 字段（本章最高爽点层级），压抑过渡章加 `depress: true`：

| 层级 | 定义 | 频率配额 |
|------|------|---------|
| L1 | 小胜利：任务完成/炼丹成功/杂役打脸 | 每章至少1个 |
| L2 | 中收获：境界小成/新功法/地位提升 | 每3-5章1个 |
| L3 | 大高潮：秘境夺宝/击败强敌/越级挑战 | 每卷2-3次 |
| L4 | 格局跃迁：大境界突破/天命剑解封/真相揭示 | 每卷1次（卷末） |

**硬规则**（outline-precheck.py beats 自动校验，回归测试 `tools/test-outline-precheck.py`）：
- 压抑上限：连续2章无正反馈，第3章必须 L2+（等价"连续失败2次→降难度"）
- 卷=赛季：卷末不清零成长，只升级对手层级与新目标——严禁"换地图功力减半"
- 高潮通胀：连续3章L4=疲劳；连续10章全L1=平淡

### 三、世界观展开原则

- **渐进式揭示**：每个世界观信息首次出现时，必须是剧情需要，而非设定堆砌
- **信息-剧情比例**：设定解释不超过该场景对话的20%，剩余用动作和后果展示
- **留白原则**：不必解释所有背景，给读者想象空间

### 四、角色弧光设计

- **主角核心驱动力**：不是"变强"，而是"完成某个具体目标"（复仇/寻亲/守护）
- **配角功能**：每个配角必须承担至少两个功能（推动剧情+映射主角某一面）
- **反派立体化**：反派必须有合理动机，不能为坏而坏

### 五、文风准则

- **朴实有骨**：用词准确，不堆砌华丽辞藻，句法多变
- **画面优先**：能用动作和细节表现的，不用心理描写
- **对话驱动**：对话承载70%信息量，旁白≤30%
- **助词节奏**："了/的/微微/一样"等助词自然使用，不生硬

---

## 当前阶段

| 阶段 | 状态 | 完成条件 |
|------|------|---------|
| 数据收集 | ✅ 已完成 | 行业数据、读者画像、平台对比已收集 |
| 工具调研 | ✅ 已完成 | 91Writing等创作工具已调研评估 |
| 工具搭建 | ✅ 已完成 | 提示词库+类型系统+SOP已创建 |
| 项目启动 | 🟡 待重启 | 09-27深夜重构清空全部正文，框架/世界包/工具链完整，待从第1章重写 |
| 第1章创作 | 🔴 待重写 | 原朴实定稿已随重构91287b6删除，正文不存在 |
| 第2章创作 | 🔴 待重写 | 《擂台》草稿已随重构删除，未恢复 |
| 第3章创作 | 📦 已归档 | 重构后改写的《暗流》无前情属孤儿稿 → `archive/20260928清账/`（可作素材） |
| 创作DNA蒸馏 | ✅ 已完成 | 女娲方法论已应用于TEAM.md |

---

## 已有资产

### 世界设定

| 文件 | 路径 | 说明 |
|------|------|------|
| 世界设定集 | `03-Resources/小说团队/天命-世界设定-玄天大陆.md` | 地理、势力、修炼体系、货币、灵兽、历史秘辛 |
| 角色档案-萧辰 | `03-Resources/小说团队/天命-角色档案-萧辰.md` | 主角详细设定 |
| 角色档案-苏逸 | `03-Resources/小说团队/天命-角色档案-苏逸.md` | 师兄详细设定 |
| 角色档案-王大 | `03-Resources/小说团队/天命-角色档案-王大.md` | 前期反派详细设定 |
| 角色档案-王执事 | `03-Resources/小说团队/天命-角色档案-王执事.md` | 中层反派详细设定 |

### 世界包数据

### 行业数据报告

| 文件 | 大小 | 说明 |
|------|------|------|
| `research/NETWORK-LITERATURE-DATA-COLLECTION-20260927.md` | 281行 | 市场规模/读者画像/平台对比/创作方法论 |
| `research/91Writing-工具调研-20260927.md` | 303行 | AI创作工具功能评估 |
| `research/SOURCE-SITUATION-20260927.md` | 175行 | 书源现状分析 |
| `research/nuwa-diagnosis-inconsistency.md` | - | 女娲数据一致性诊断报告 |

### 创作工具

| 工具 | 路径 | 说明 | 契约 |
|------|------|------|------|
| 去AI味检测v3 | `tools/novel-humanizer.py` | lieflat 11条 + Novel-Creator 7大类 | `--chapter-file <path>` → JSON |
| 知识图谱 | `tools/story-graph.py` | 8节点类型 + 10边类型 | `--project <name>` → graph.json |
| 事实账本 | `tools/fact-ledger.py` | 四层记忆系统+认知分级 | `--add/--query/--snapshot` |
| 质量门禁 | `tools/quality-gate.py` | 全流程检查+提交机制 | `--chapter <path> --novel-id <id> [--commit]` |
| 门禁检查 | `tools/gate-check.py` | 六道刚性/柔性门禁 | `check --chapter <num> --file <file>` |
| 上下文管理 | `tools/context-manager.py` | 多轮注入+有界完成 | CLI子命令：build/generate/status/estimate/bounded-check |
| 大纲构建 | `tools/outline-builder.py` | 三级大纲+伏笔管理（add-work/add-volume/add-chapter/add-foreshadow/pay-off/tree/stats） | `--project <dir>` + 子命令；示例：`add-chapter -v <vol-id> -n <num> -t <title> [-p <points...>]` |
| 大纲预检 | `tools/outline-precheck.py` | 合同树咬合+**爽点节拍L1-L4**（破冰/压抑上限/里程碑/疲劳/卷末L4） | `check|beats --project <dir> [--strict]` → JSON；回归 `test-outline-precheck.py` |
| 章节契约 | `tools/chapter-contract.py` | SkillSystem V/I/C/E 四段契约校验（前提硬闸/铺垫节奏/多段高潮/钩子有效性） | `validate/show/draft --chapter-file <path>` → JSON；回归 `test-chapter-contract.py` 8断言 |
| 剧情流水线 | `tools/plot-pipeline.py` | **Phase图模型**：Sequence/Parallel/Conditional/Repeat/Delay/WaitUntil；小说段落编排（Hook→Rise→Conflict→Climax→Resolution） | `build/run/status/complete/skip --project <id>` → JSON |
| 剧情触发器 | `tools/plot-trigger.py` | **EventBus+TriggerPlan**：事件→条件评估→排序→执行Action；继承decide-trigger.py扩展全量事件 | `register/fire/list/history --project <id>` → JSON |
| 剧情溯源链 | `tools/plot-trace.py` | **溯源树**：root/parent/cause上下文；正向追踪/反向溯源/一致性检查 | `add/trace-back/trace-forward/check-consistency/graph --project <id>` → JSON |
| 状态修正器 | `tools/state-modifier.py` | **Modifiers系统**：Buff/Debuff动态改写属性；多层叠加+脏标记优化 | `add/apply/list/clear/base/summary --project <id>` → JSON |
| 持续状态 | `tools/continuous-state.py` | **Continuous生命周期**：条件驱动激活/暂停/恢复/移除；跨章节持续剧情状态 | `add/tick/list/pause/resume/resolve/tags/summary --project <id>` → JSON |
| 剧情标签 | `tools/plot-tag.py` | **GameplayTags标签树**：层级结构+实体关联+模糊搜索+路径查询 | `add/link/search/tree/entities/summary --project <id>` → JSON |
| 角色心理 | `tools/character-hfsman.py` | **HFSM分层状态机**：事件驱动转换+guard条件+历史记录；角色弧光一致性 | `create/transition/fire/status/history/summary --project <id>` → JSON |
| 多线叙事 | `tools/narrative-flow.py` | **Flow流程引擎**：Parallel/Race/Sequence/Timeout；多线并行+汇聚+超时收束 | `add/advance/check/graph/summary --project <id>` → JSON |
| 剧情解释 | `tools/plot-explain.py` | **Explain解释树**：因果链追溯+章节报告；审稿时快速定位逻辑断层 | `add/link/explain/chain/report/summary --project <id>` → JSON |
| 批量改词 | `tools/batch-replace-v2.py` | 批量替换+自动备份 | `--find <x> --replace <y> --dir <path>` |

### 外部项目（参考源）

| 项目 | 路径 | 说明 | 借鉴点 |
|------|------|------|--------|
| 91Writing | `/var/minis/shared/91Writing/` | AI小说创作工具（Vue 3，1601⭐） | 创作链设计+提示词模板 |
| StoryForge | `/var/minis/shared/storyforge/` | 多产品线AI创作工作台（TS，780⭐） | 四层记忆+世界引擎派生 |
| Novel-Creator-Skill | `/var/minis/shared/novel-creator-skill/` | 百万字级创作系统（Python，657⭐） | 五层一致性+去AI味润色 |
| Long-Novel-GPT | `/var/minis/shared/Long-Novel-GPT/` | AI一键生成长篇（Python，1239⭐） | 三阶段创作+上下文管理 |
| Casting-Workflow | `/var/minis/shared/Casting-Workflow/` | 熔铸仿写全术（Python CLI，611⭐） | 指纹蒸馏+硬性约束 |
| ai-novel-writer v6 | `/var/minis/shared/ai-novel-writer/` | 世界模拟创作系统（Python，5⭐） | 四道防线+认知分级 |
| worldtree | `/var/minis/shared/worldtree/` | 世界观框架（HTML+JS，0⭐） | 世界包数据格式+一致性检查 |

---

## 核心数据摘要

| 指标 | 数值 |
|------|------|
| 用户规模 | 5.75亿（占网民51.9%）|
| 市场营收 | 495.5亿元（+29.37%）|
| IP改编市场 | 约3676亿元 |
| 海外用户 | 约2亿人 |
| 付费意愿 | 87%有意愿，31%已付费 |
| 热门题材增长率 | 种田文+47%，末日求生+200% |

---

## 工具使用说明

### 1. 质量门禁流程（第N章创作标准流程）

```bash
# 第一步：生成初稿后执行全流程门禁
python3 tools/quality-gate.py --chapter projects/my-novel/chapters/chapter-00{N}.md --novel-id my-novel --commit

# 第二步：查看门禁结果
python3 tools/gate-check.py check --chapter {N} --file projects/my-novel/chapters/chapter-00{N}.md

# 第三步：如有问题，修正后重新执行（最多3轮）
# 第四步：通过后更新fact-ledger
python3 tools/fact-ledger.py add-fact --content "章节{N}关键事件" --category chapter
```

### 2. 章节创作

```bash
# 续写模式
cat tools/prompt-library/categories/chapter.md

# 优化模式
# 同模板，选择模板B
```

### 3. 类型选择

```bash
# 查看可用类型
ls tools/genre-system/presets/

# 读取类型设定
cat tools/genre-system/presets/{type}.json
```

### 4. 创作流程

```bash
# 查看完整SOP
cat docs/SOP-CREATION-FLOW.md
```

### 5. 创作统计（countdown-scheduler扩展）

```bash
# 列出所有小说项目
python3 /var/minis/shared/countdown-scheduler.py novel list

# 添加新小说项目
python3 /var/minis/shared/countdown-scheduler.py novel add --name "小说名" --genre 玄幻 --platform 起点 --target-words 100000

# 记录创作活动
python3 /var/minis/shared/countdown-scheduler.py novel log --project-id {ID} --action write --words 2000 --chapter 1

# 查看创作统计
python3 /var/minis/shared/countdown-scheduler.py novel stats [--project-id {ID}]

# 生成创作报告
python3 /var/minis/shared/countdown-scheduler.py novel report
```

**支持的action类型**：
- `write` - 正文创作
- `outline` - 大纲创作
- `character` - 角色设计
- `worldbuilding` - 世界观构建
- `polish` - 润色优化
- `publish` - 发布

---

## 创作流程（七阶段）

```
构思 → 大纲 → 角色 → 世界 → 章节 → 润色 → 发布
  ↓      ↓      ↓      ↓      ↓      ↓      ↓
选题   架构   设定   背景   创作   优化   分发
```

**各阶段决策点**：见 `docs/SOP-CREATION-FLOW.md`

**非线性支持**：
- 阶段回退：允许跳到任意前置阶段（例：第3章发现问题 → 跳回"角色"阶段修订）
- 依赖重算：修改前置阶段后，自动标记后续阶段为"需重验"
- 状态标签：每个阶段可标记 `draft`/`review`/`frozen`/`archived`

---

## 失败模式编码

> **触发条件**：本章实踩坑经验提炼，用于自动识别创作异常

| 模式 | 触发条件 | 应对策略 | 优先级 |
|------|---------|---------|--------|
| **字数不足** | 输出 < 1800字 | 扩充场景细节、补动作链、加心理描写 | P2 |
| **AI味超标** | Tier 1A > 20 分 | 检查：排比三连？翻译腔？破折号滥用？→ 简化比喻、打散同款句 | P1 |
| **设定不一致** | 境界/时间/空间矛盾 | 调用 fact-ledger.py --snapshot 比对快照 | **P0** |
| **信息重复** | 同一情报多次出现 | 检查：前N章是否已告知？→ 删除冗余或改为"回忆触发" | P1 |
| **时空错乱** | 场景跳切无过渡 | 检查：是否漏掉"时间流逝"描述？→ 补过渡句 | P1 |
| **角色掉线** | 低境界做出高境界能力 | 检查：境界能力边界（炼气=轻身/淬体=不能飞）→ 修正描写 | **P0** |
| **并发故障** | 多个失败同时触发 | **优先级：设定矛盾 > 角色掉线 > AI味 > 字数** | P1 |

### 并发故障降级策略

当多个失败同时触发时，按以下顺序修复：

```
1. 先修复【设定矛盾】（P0）→ 避免后续章节继承错误设定
2. 再修复【角色掉线】（P0）→ 避免实力体系崩坏
3. 然后修复【AI味超标】（P1）→ 改善文风
4. 最后处理【字数不足】（P2）→ 填充内容
```

**防死循环机制**：
- 每轮修复后重新检测，若新引入矛盾则回退
- 最多 3 轮修复，超时转人工介入

---

## 反例黑名单

> **禁止事项**：这些模式一旦出现，必须立即修复

| 类别 | 反例 | 修复方案 |
|------|------|---------|
| **中英混杂** | "rankings"、"status" | 替换为中文（"排名"、"状态"）|
| **破折号滥用** | "——" | 改为逗号或句号 |
| **重复已知信息** | 前面已说的再解释一遍 | 删除或改为"回忆触发" |
| **境界掉线** | 低境界做高境界能力 | 核对境界能力边界 |
| **时空跳切** | 无过渡直接换场景 | 补过渡句（"三天后"、"与此同时"）|
| **弱化副词泛滥** | 缓缓、轻轻、微微、静静 | 删除或改为具体动作 |
| **双像比喻** | "像…又像…" | 只用一个比喻，或删除 |
| **AI味梯度失控** | 排比3处+/翻译腔/句式西化 | 检测工具判定后，按优先级矩阵修复 |

---

## 工具契约规范

> **目的**：确保跨工具数据同步不静默失败

每个脚本必须声明以下契约：

```bash
# 调用协议模板
python {script}.py --action {action} --param {value}
# 返回：{"status": "ok", "data": {...}}
# 失败：exit 1 + "ERROR: {reason}"
```

### 已定义契约

| 工具 | 输入参数 | 返回值 | 前置校验 |
|------|---------|--------|---------|
| `gate-check.py` | `--chapter <num> --file <path> [--flexible]` | JSON: {status, checks[], warnings[]} | chapter文件存在且可读 |
| `quality-gate.py` | `--chapter <path> --novel-id <id> [--commit] [--publish] [--chapter-num <num>]` | JSON: {pass, failed_checks[], suggestions[]} | chapter文件存在 |
| `fact-ledger.py` | `add-fact --content <text> --category <type>` / `list-facts` / `snapshot` | JSON: {fact_id, status} | category为预定义枚举 |
| `novel-humanizer.py` | `--chapter-file <path>` / `--text <text>` | JSON: {score, tier_1a, tier_1b, issues[]} | 文件存在 |
| `story-graph.py` | `add-node --name <n> --type <t>` / `add-edge --from <n1> --to <n2> --type <t>` | JSON: {node_id/edge_id, status} | 节点类型在枚举内 |
| `context-manager.py` | 子命令：`build --project-id <id>` / `generate --project-id <id> --chapter <n> [--mode draft/expand/polish] [--output <path>]` / `status --project-id <id>` / `estimate --project-id <id>` / `bounded-check` | `status`: 人类可读；`generate`: Prompt文本写入 --output；`bounded-check`: PASS/FAIL + 原因 | `--project-id` 对应项目目录存在 |
| `outline-builder.py` | 全局：`--project <dir>`（目录路径，非 novel-id）；子命令：`add-work -t <title> [-s <summary>]` / `add-volume -w <work-id> -n <num> -t <title> [-s <summary>]` / `add-chapter -v <vol-id> -n <num> -t <title> [-p <points...>] [-W <words>]` / `add-foreshadow -c <chap-id> -C <content> [-T <tier>]` / `pay-off -f <foil-id> -c <chap-id>` / `tree` / `stats` | `add-*`: 创建后返回新ID；`tree`/`stats`: 人类可读树状图/汇总 | 依赖ID必须已存在（如 add-chapter 需 volume-id 有效） |

### 已补全契约（2026-09-29，D1 任务）

| 工具 | 补全内容 | 日期 |
|------|---------|------|
| `context-manager.py` | 5个子命令完整签名 + 返回格式 | 2026-09-29 |
| `outline-builder.py` | 修正原错误登记（`--build/--export/--validate` 实际不存在），补全 7 个子命令 | 2026-09-29 |

---

## 下一步行动

### 创作进行中

**当前项目**：《天命》

**已完成**：
- 第1章：定稿（2032字，朴实风格，AI味27分）✅
- 第2章：初稿（2364字，擂台战斗）✅ AI味14分，门禁通过
- 第3章：初稿（2460字）❌ AI味严重超标（tier_1a=32），需重构

**世界构建完成**：
- 玄天大陆世界包：43个条目（地理/势力/修炼/货币/灵兽/历史/秘辛）
- 主要角色档案：萧辰、苏逸、王大、王执事（4个）
- 数据源：`.world-packs/玄天大陆.json`

**待修复**：
- 第3章：初稿（2460字）❌ **AI味严重超标（tier_1a=32）**，需重写或深度优化

**待用户确认**：
1. 是否继续创作第3章？
2. 是否需要调整《天命》的世界观或角色设定？
3. 是否需要进行跨章节一致性审查？

---

## 文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 本书 | `TEAM.md` | 本文件 |
| 行业数据 | `research/NETWORK-LITERATURE-DATA-COLLECTION-20260927.md` | 市场规模/读者画像 |
| 创作SOP | `docs/SOP-CREATION-FLOW.md` | 三阶段流程 |
| 工具契约 | `TEAM.md#工具契约规范` | 本节 |
| 上下文管理 | `tools/context-manager.py` | 多轮注入+有界完成 | CLI子命令：build/generate/status/estimate/bounded-check |
| 提示词库 | `tools/prompt-library/` | 模板索引 |
| 类型系统 | `tools/genre-system/` | 类型定义 |
| CHANGELOG | `CHANGELOG.md` | 版本记录 |

---

## 历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1 | 2026-09-27 | 项目启动，进入内容工具收集阶段 |
| v0.2 | 2026-09-27 | 数据收集完成，进入数据分析阶段 |
| v0.3 | 2026-09-27 | 工具调研完成，等待决策 |
| v0.4 | 2026-09-27 | **工具搭建完成**（提示词库+类型系统+SOP），等待项目启动 |
| v0.5 | 2026-09-27 | **扩展countdown-scheduler.py添加创作统计功能**（novel命令）|
| v0.6 | 2026-09-27 | **调研StoryForge多产品线架构**，借鉴记忆系统与候选采纳机制 |
| v0.7 | 2026-09-27 | **开发fact-ledger.py事实账本工具**，实现四层记忆系统 |
| v0.8 | 2026-09-27 | **调研Novel-Creator-Skill百万字级创作系统**，借鉴五层一致性机制 |
| v0.9 | 2026-09-27 | **实施P0+P1借鉴**：去AI味v3、知识图谱、RAG检索 |
| v0.10 | 2026-09-27 | **调研Long-Novel-GPT三阶段创作流程**，借鉴上下文管理机制 |
| v0.11 | 2026-09-27 | **实施Long-Novel-GPT借鉴**：更新SOP、优化提示词、开发上下文管理器 |
| v0.12 | 2026-09-27 | **调研AI-Novel-Writer桌面应用**，借鉴提示词三级覆盖和工作流设计 |
| v0.13 | 2026-09-27 | **实施P0借鉴**：提示词三级覆盖、有界完成机制、结构化审稿 |
| v0.14 | 2026-09-27 | **调研Casting-Workflow指纹蒸馏**，借鉴硬性约束和后处理工具 |
| v0.15 | 2026-09-27 | **实施Casting-Workflow借鉴**：指纹蒸馏+硬性约束+后处理工具 |
| v0.16 | 2026-09-27 | **调研NovelCraft极简创作**，借鉴作家人格+12条纪律 |
| v0.17 | 2026-09-27 | **调研ai-novel-writer v6世界模拟**，借鉴四道防线+认知分级 |
| v0.18 | 2026-09-27 | **实施ai-novel-writer v6借鉴**：四道防线+认知分级+决策触发 |
| v0.19 | 2026-09-27 | **调研MuMuAINovel全栈平台**，借鉴伏笔管理+向量记忆+RTCO框架 |
| v0.20 | 2026-09-27 | **实施MuMuAINovel借鉴**：伏笔管理+向量记忆+RTCO框架+剧情分析 |
| v0.21 | 2026-09-27 | **调研AI-automatically-generates-novels自动化流水线**，借鉴合同树+程序选优 |
| v0.22 | 2026-09-27 | **实施AI-automatically-generates-novels借鉴**：合同树+硬账台账+多候选选优+熔断 |
| v0.23 | 2026-09-27 | **调研51mazi+MG_Obsidian_plugin**，借鉴批量改词+合并导出+AI辅助 |
| v0.24 | 2026-09-27 | **实施MG_Obsidian_plugin借鉴**：批量改词+合并导出 |
| v0.25 | 2026-09-27 | **调研chinese-novelist-skill**，借鉴三层问答+创作记忆+自动校验 |
| v0.26 | 2026-09-27 | **实施chinese-novelist-skill借鉴**：创作记忆+字数检查+自动校验 |
| v0.27 | 2026-09-27 | **实施51mazi借鉴**：扩展禁词+增强图谱+时间线管理 |
| v0.43 | 2026-09-27 | **大纲版本管理** + 风格保留 + 合同树前置校验 + 预测性分析 |
| v0.44 | 2026-09-27 | **项目结构搭建** + world-init.py + outline-builder.py |
| v0.45 | 2026-09-27 | **团队自我审视会议** + 协作机制重构 |
| v0.46 | 2026-09-27 | **darwin-skill红蓝军对抗**：新增工具契约规范、失败模式编码、反例黑名单、非线性流程 |
| v0.47 | 2026-09-27 | **女娲方法论蒸馏**：新增《天命》创作DNA（境界设计/节奏控制/世界观展开/角色弧光/文风准则）、修复全部数据一致性问题 |
| v0.48 | 2026-09-28 | **第2-3章创作完成**：第2章擂台战通过门禁，第3章获天命剑；账本扩展至14条（※09-28清账修正，三处不实：①成果真实存在过（c9d420e 写入第2-3章），但已随同日重构 `91287b6` 全量删除；②重构后第3章《暗流》在 fb537af 被部分改写为孤儿稿，已归档 `archive/20260928清账/`；③"14条"言过其实——c9d420e 时 facts.json 实测仅 3 条(v4)，后经 0220140 清理剩 1 条，现标记 superseded。详见 v0.51） |
| v0.49 | 2026-09-28 | **Biz Novel Studio 借鉴整合**：新增 quality-debt.py（质量债务四档）、pending-review.py（待确认区）、character-depth.py（角色档案四档+形象演变）、char-context-filter.py（参与者精准筛选）；gate-check.py 改造为"债务记录不阻断"模式 |
| v0.50 | 2026-09-28 | **爽点节拍校验**（Progression-Architect 借鉴）：outline-precheck 新增 thrill L1-L4 节拍检查5规则+回归测试7断言；修复 volumes 结构兼容与 argparse 子命令两个隐性 bug；SOP 阶段二加入节拍决策点；创作DNA 节奏原则加爽点四层表 |
| v0.51 | 2026-09-28 | **账面清账**：git 取证还原真相——第1-3章曾真实写作又随重构 `91287b6` 删除，孤儿第3章归档 `archive/20260928清账/`；事实账本 v6（遗留记录标 superseded + 清账记录）；当前阶段表 3 行"已完成"修正为"待重写/已归档"；v0.48 行三处不实逐条标注；CHANGELOG.md 冻结为历史存档（v0.47 起 TEAM.md 表为唯一变更记录）。**补正（v0.52）**：账本双轨溯源（见下）。 |
| v0.52 | 2026-09-28 | **提交前查表纪律 + 事实账本双轨修复**：
| v0.53 | 2026-09-28 | **章节契约校验**（SkillSystem 借鉴）：新建 chapter-contract.py（V/I/C/E 四段模板+硬闸校验），8 断言全通过；TEAM.md 工具表新增章节契约行；SOP 阶段三加 draft→validate 步骤 |
| v0.56 | 2026-09-28 | **自检优化**：self-check.py 扩展至 21 工具（含 outline-precheck/chapter-contract/plot-*/character-hfsman/narrative-flow/plot-explain）；版本号 v0.52→v0.56；清理冗余脚本（batch-replace/power-model/calc-power-ratio 系列旧版→archive）；pending-review 提案 P001（萧辰首次触发天命剑剑灵）因第3章已归档，标记为 stale |
| v0.53 | 2026-09-28 | **AbilityKit 借鉴整合 P0**：新增 4 个工具（plot-pipeline.py/plot-trigger.py/plot-trace.py/state-modifier.py）+ 回归测试（test-abilitykit-tools.py）+ 研究笔记（research/AbilityKit-借鉴整合报告-20260928.md）。核心借鉴：Pipeline Phase图模型→剧情流水线、Triggering事件总线→剧情触发器、Trace溯源树→剧情溯源链、Modifiers参数修正→状态修正器。TEAM.md 工具表同步更新 |
| v0.54 | 2026-09-28 | **AbilityKit P0回归测试全部通过（20/20）**：(1) 修复plot-pipeline.py PhaseStatus enum JSON序列化（enum→string.value）；(2) 修复plot-trace.py循环引用误报（直接父子关系非循环，改为遍历children_effects链检测）；(3) 修复state-modifier.py ModifierType加载bug（JSON string→enum转换）；(4) 重写test-abilitykit-tools.py用绝对路径（TOOLS_DIR）避免subprocess CWD问题；(5) argparse子命令参数顺序约束（-p须放子命令前)。PlotPipeline 4/4 ✅ / PlotTrigger 4/4 ✅ / PlotTrace 6/6 ✅ / StateModifier 6/6 ✅ |
| v0.55 | 2026-09-28 | **AbilityKit P1+P2落地**：新增5个工具（continuous-state.py/plot-tag.py/character-hfsman.py/narrative-flow.py/plot-explain.py）+ test-abilitykit-tools.py扩展至9工具44项全通过。Continuous：跨章节持续状态生命周期；PlotTag：层级标签树+实体关联；CharacterHFSM：分层状态机+事件驱动转换；NarrativeFlow：多线并行+Race竞速+Timeout收束；PlotExplain：因果链追溯+章节报告。回测旧4工具仍全过（20/20）|
| v0.57 | 2026-09-29 | **grill-me D1/D2治理**：(1) 契约补全：context-manager.py 5子命令完整签名 + outline-builder.py 7子命令参数修正（原`--build/--export/--validate`与实际CLI不符，已更正为`add-work/add-volume/add-chapter/add-foreshadow/pay-off/tree/stats`）；(2) gate-check.py 新增 `--fix-order` 模式 + `generate_fix_order()` 方法，按 P0(设定矛盾>角色掉线>AI味) > P1(字数>禁用词>钩子) > P2 降级策略排序，real ch6 实测通过；(3) 新增 test-degradation.py（D2 测试脚本）|

minis_url: minis://shared/novel-team/TEAM.md
| v0.58 | 2026-09-29 | **⚠️ D1 清账：契约补全是纸面完成，代码从未实现** — v0.57 声称「契约补全」，实测发现只是把命令签名登记进 TEAM.md 表，两个工具均不实现契约协议。实测证据：①`sys.exit` 在两工具中各 **0** 处、`ERROR:` 各 **0** 处 → 失败协议完全缺失；②outline-builder 前置校验 **0** 处（context-manager 1 处），且 `add_volume/add_chapter/add_foreshadow` 存在同型静默降级——`if work_id in self.nodes: ...append()` 父ID不存在时跳过关联但**节点已落盘 + 返回成功 + exit 0**，即契约规范明写的「跨工具数据同步静默失败」在工具内部真实发生。**本次落地**：outline-builder 新增 `ContractViolation` + `_check_parent()`，四方法（add-volume/add-chapter/add-foreshadow/pay-off）前置校验，pay-off 另加「不可重复回收」；`main()` 捕获后 `exit 1` + `stderr` 输出 `ERROR:` 前缀。context-manager dispatch 改为传递 `cmd_*` 返回码（修前 `cmd_build` 的 `return 1` 被调用处丢弃）。**回归实测 4 例**：孤儿卷 exit=1 ✅ / 正常路径 exit=0 ✅ / 重复回收 exit=1 ✅ / 真实项目 tree 不崩 ✅。**顺带发现未修（记为 C9）**：outline-builder 的 work/foreshadow ID 是 `work-{时间戳}`，与 `统一数据格式规范-v1.0.md` 的 `{类型}-{YYYYMMDD}-{序列号}` 不符，且与 volume/chapter 的序列式 ID 体系混用。改 ID 会破坏既有数据，**本次不动**。 |
| v0.59 | 2026-09-29 | **⚠️ C9 清账：大纲工具父子层级从未工作过** — 修 C9（ID体系混用）时实测发现三处同型缺陷，均静默、均 exit 0：
- **C9a ID 体系混用**：work/foreshadow 用 `work-{YYYYMMDDHHMMSS}`（时间戳，无序列号段，同秒碰撞），volume/chapter 用序列式 → 同一工具两套体系，且均不符 `统一数据格式规范` 2.3。
- **C9b 重复ID静默覆盖**：`add-volume -n 1` 连建两次均返回 `vol-001` 并报「✅ 已创建」，第二次**覆盖第一卷**，无任何提示。
- **C9c children 从未落盘（最严重）**：`OutlineNode` dataclass **无 `children` 字段**，`getattr(node,'children',[])` 每次返回新列表，`append` 写入一次性列表即丢；`get_tree` 同样读该字段 → **树恒为空，整个层级渲染是死代码**。

**本次落地**：① work/foreshadow 改为序列式（`work-{n:04d}`/`foil-{n:04d}`），`_next_seq()` 从现有ID扫描派生（确定性、无时间戳碰撞）；② 新增 `_check_unique()` 去重守卫，四类实体全覆盖；③ `_build_tree_node` 改为按 `parent_id` 反查派生子节点；④ 移除三处失效的 children/foreshadowings 反向写入（后者类型还是 `List[Dict]` 却被写入字符串ID）。

**C9d 真实数据损坏（已备份+最小修复）**：`projects/my-novel/outline/outline.json` 中 **work 节点根本不存在**，`vol-001` 声明 parent=`work-001` → 孤儿；4 条伏笔用旧路径格式 `fs-*`、`planted_at` 为裸章节号 `'1'/'3'/'4'/'17'`（非章节ID），且 fs-004 指向不存在的第17章 → **证据表明这份数据至少由两条代码路径写入**。处置：原文件备份至 `archive/20260929清账/outline.json.pre-C9`；补建 `work-0001`（《天命》）并把 vol-001 parent 改指；4 条旧伏笔**不编造映射**，原样移入 `_legacy_foreshadowings` 段并标注 `_legacy_note` 待人工核对。修复后 tree 首次正常渲染 3 层。

**规范同步修订**：`统一数据格式规范-v1.0.md` 2.3 节改 v1.1——按「是否有序数位置」把实体分两类：无内部序数用 `{类型}-{YYYYMMDD}-{序列号}`（fact/char/world），**有内部序数用 `{类型}-{序数}`（work/vol/chapter/foil）**。原规范让章节编号随创建日期漂移，与「第一章」的叙事含义冲突，属语义错误。

**回测**：完整链路 work→vol→2章→伏笔 tree 三层正确 ✅ / 重复卷·重复章·重复回收均 exit=1 ✅ / 真实数据 tree 不崩 ✅ |
| v0.60 | 2026-09-29 | **⚠️ D2 清账：降级策略排序声明大部分未生效** — 验 v0.57 的 D2 登记，实测 5 项缺陷：
- **D2a 同级别次级排序从未生效（核心）**：`generate_fix_order()` 的 `sort` 只用 `priority`（1/2/3），同级别内退化为**插入顺序**。实测按「AI味→角色掉线→设定矛盾」乱序输入，输出照旧乱序 → 文档声明的「设定矛盾(P0) > 角色掉线(P0) > AI味(P0) > 字数(P1) > 禁用词(P1) > 钩子(P1)」**只有跨级部分成立，同级次级链全部失效**。
- **D2b 同 gate 去重丢弃问题**：去重键是 `gate`，同 gate 的第二个不同问题被静默丢弃（实测 2 条设定矛盾只留 1 条）。对「指导修复」的排序列表来说这是真丢数据。
- **D2c stdout 被污染**：`📡 已发射事件 CHAPTER_GATE_PASSED` 打印到 **stdout**，破坏契约「返回 JSON」——实测全部 20 章 `json.load` 直接 parse fail。
- **D2d test-degradation.py 不存在**：v0.57 登记了，文件从来没建过（与 D1 纸面完成同型）。

**本次落地**：① 加 `GATE_SUB_PRIORITY` 表（14 个 gate 全映射）+ 排序键改 `(priority, sub_priority)`，次级链生效；② 去重键改为 `(level, gate, label, detail)`，只合并真正重复行，同 gate 不同问题全部保留；③ 事件行改 `stderr`，stdout 恢复纯 JSON；④ 新建 `test-degradation.py`（11 项断言，含「修前从未生效」的次级排序反向断言）。**回归**：test-degradation 11/11 ✅ / test-outline-c9 10/10 ✅ / 三工具语法 ✅。

**未修（记为 D2e，需重构）**：禁用词分级三重不一致——① 文档声明 `禁用词(P1)`；② 实际跑在 `unknown_entities` gate 下（`_check_unknown_entities` L298），而该 gate 不在 `p1_gates`（L101），故落 **P2**；③ `generate_fix_order` 又通过 `GATE_LABELS` 把它映射成 `forbidden_words`，**分类出的 gate 名与产出它的 gate 名不是同一个**。修此需决定禁用词归属哪个 gate 并调整 p1/p2 gate 列表，属结构重构，且会改变 20 章的分级统计，**本次不动，登记待决**。
| v0.61 | 2026-09-29 | **🔴 门禁阻断层清零 + 项目数据全清** — 验「运行机制」时的实测发现：阻断层 0% 生效，随后修 10 个 BUG 并清空全部项目数据。**修前**：20/20 章无条件 `passed=True`、P0=0；**修后**：**12/20 章被真实阻断**（`block_reason=data_integrity_failure`），16/20 有 P1。

**10 个 BUG（均实测证实）**：
- **B1 阻断路径死代码**：`data_integrity_error` 只赋值 `None`，3 处引用全是读，`if` 分支永不进 → 阻断层 0% 生效。落地：扫描 `BLOCK_GATES=fact_consistency/ai_tone/protocol`，任一 `status==fail` 即设值。
- **B2 `_collect_errors` 无 p1/p2 桶**：只分 all/p0，P1/P2 fail 只进 `all` → summary 与 `--fix-order` 读不到。落地：三桶按 `_classify_gate` 归位。
- **B3 `word_count` 非独立门禁**：嵌在 `_check_consistency` 里以 `consistency` 上报，而 `p1_gates` 只认 `word_count` → 字数不足被判 P2。落地：拆为独立 `_check_word_count`。
- **B4 禁用词非独立门禁（D2e）**：嵌在 `_check_unknown_entities` 下落 P2，与文档声明 P1 矛盾，且 `GATE_LABELS` 映射成 `forbidden_words`（分类出的 gate 名与产出它的 gate 名不同）。落地：拆为独立 `_check_forbidden_words`，D2e 随结构修复自动消除。
- **B5 空 detail 项**：`'; '.join(...)` 在 details 为空时产出 `"[P2] "`。落地：strip 后跳过空串。
- **B6 `fact_consistency` 双重死代码**：在 `p0_gates` 却**无任何实现函数**。落地：新增 `_check_fact_consistency`，两条真实可检路径——① 提前引用（本章引用 `source` 章节号 > 本章号的事实 → 剧情时间线倒流）② 提前揭示（hidden/planned 实体出现在正文）。实体名提取剥离「（隐藏）」注记，否则匹配不到正文真名。
- **B7 `_evaluate_results` 返回值被丢弃**：构建了四档债务 dict 但函数只 return bool，`will_block`/`block_reason`/`debts_recorded` 全丢。落地：挂 `self.last_evaluation` 并合并进返回体。
- **B8 summary 漏计 P1/P2**：只读 `warnings.p1/p2`（仅收 `status=="warning"`），漏 `errors.p1/p2`（收 `status=="fail"`），两桶互不重叠。实测 ch001 `errors.p1` 有 1 条但 summary `p1_warnings=0`。落地：两桶都计入。
- **B9 `--novel-id` 在 check 命令完全不解析**：硬编码 `GateChecker("my-novel")` → 任何项目的门禁都读 my-novel 的账本与事件。**多项目隔离在门禁层断裂**，事件文件名同样硬编码。落地：解析 `--novel-id` 且事件按 `{novel_id}.jsonl` 分文件。
- **B10 构造函数有文件系统副作用**：`__init__` 里 `status_dir.mkdir(parents=True)` → 仅实例化即把已删除项目目录"复活"（实测 rm -rf projects 后跑一次门禁即重建）。落地：移除，改两处写入点惰性创建。

**回归**：test-degradation 12/12 ✅ / test-outline-c9 ✅ / 全部工具 `py_compile` ✅。B9 修复后退出码语义变化（0=通过，1=被阻断），test-degradation 断言已同步。
| v0.62 | 2026-09-29 | **🟢 代际项目守卫落地** — 解决「一个项目散在 15+ 顶层目录」的结构性污染。**核心设计**：代际模型（单一项目进程），`projects/<id>/current/` 活副本 + `gen-00N/` 历史副本，manifest.json 单一真相源。**落地**：(1) 新建 `project_guard.py`（17KB，100 行核心逻辑），实现 `resolve()` 唯一路径入口 + `ProjectRoot` 命名空间（25 个子目录访问器）+ 4 个代际命令（archive/new/rollback/reset）；(2) 改造 10 个工具的路径来源（gate-check/fact-ledger/context-manager/md-to-html-sync/narrative-flow/plot-tag/plot-trace/team-manager/test-workflow-optimization/world-sync），从硬编码 `Path(f"/var/minis/shared/novel-team/projects/...")` 统一为 `resolve(project_id).xxx()`；(3) 25 个顶层数据目录归位到 `current/` 下（`.flow/` → `current/flow/`、`.tags/` → `current/tags/` 等），数据已清空零迁移成本。**架构优势**：(a) 单一项目进程（线性代际，无并行 fork），无合并需求；(b) fail-closed（archived 代际写入抛异常）；(c) manifest 是唯一真相源，状态是字段不是目录名。**未改造**：`extend-world-tianming.py`/`init-world-tianming.py`（项目专用脚本，非通用工具）。**回归**：全部 11 个工具 `py_compile` ✅，4 个代际命令实测通过（new→archive→rollback→list 全链路）。 |

**项目数据全清**：清除 636 个文件（860→224），含 `projects/`(329)、`.events/`(222)、`ledger/`、`reports/`、`archive/`、`memory/`、`.backups/`，及顶层 **22 个隐藏数据目录**（`.butterfly`/`.contract-tree`/`.fact-snapshots`/`.foreshadow`/`.pending-world`/`.pipeline`/`.trace`/`.world-packs`/`.modifiers`/`.tracking`/`.timeline`/`.tags`/`.triggers`/`.flow`/`.continuous`/`.explain`/`.hfsman`/`.md-sync`/`.map-unlocker`/`.preference-memory`/`.ledger`）。**保留**：`tools/`(94)、`docs/`(61)、`research/`(25)、`souls/`(4)、`team/`、`templates/`、`scripts/`、`config/`、`TEAM.md`、`CHANGELOG.md`。

**备份**：`/var/minis/shared/novel-team-data-20260929.tar.gz`（187KB / 707 条目 / sha256 `c037b85ae37b000e`），可随时整包还原。

**待办（未做，需决策）**：项目生命周期机制仍缺——manifest.json + 状态机 + `project-guard.py` 入口闸门。B9 修好了「传错项目读错账本」，但「失败/重构/预建/现存项目共享一套目录」的结构性污染未解，需先定 my-novel 当前状态再落地。 |


**方法论印证**：D1（v0.57 登记 → 纸面完成）→ D2（v0.57 登记 → 一半纸面 + 核心排序声明失效）。**团队已连续 3 次出现「文档登记领先于代码实现」**，且每次都是**声明的核心卖点恰好是失效的那部分**。 |
