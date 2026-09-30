# 世界包驱动创作流程 v3.0（框架设计）

> 设计日期：2026-09-30
> 状态：框架已定，工具待实现
> 依赖：grill-me skill（已有）+ novel-team 工具链（已有）

---

## 一、问题诊断

### 为什么前三章不够吸引人？

| 症状 | 根因 | 现有工具覆盖？ |
|------|------|---------------|
| 开篇钩子弱 | 不知道"这故事到底在讲什么" | ❌ 只有骨架，没有核心逻辑 |
| 读者看完不知道看什么 | 第一卷没有具体任务目标 | ❌ 大纲只有五卷节点，无单章细纲 |
| 设定和剧情脱节 | 世界包是"有什么"，不是"为什么" | ❌ 缺铁律/矛盾/代价层 |
| 爽点节奏断档 | 没有每5章L2的细化排布 | ❌ 爽点只在五卷框架标注 |
| 角色行动动机模糊 | 不知道林辰"为什么是杂役" | ❌ 角色档案无背景故事 |

### 核心缺口：世界包缺"核心逻辑层"

```
当前 world-bible.md 结构：
  一、境界体系（有什么）    ← ✅ 有
  二、丹药铁律（规则）      ← ✅ 有
  三、天机阁等级（人物）    ← ✅ 有
  四、大陆势力（阵营）      ← ✅ 有
  五、卷结构（时间轴）      ← ✅ 有
  六、时间空间约定（写作）  ← ✅ 有

缺少的核心逻辑层：
  ❓ 一、力量体系的代价     ← 锻体到聚气，代价是什么？谁定的规矩？
  ❓ 二、社会结构的根源     ← 杂役为什么不能升级？制度从哪来？
  ❓ 三、核心矛盾的发动机   ← 天机阁为什么中立？魔道为什么抢？
  ❓ 四、主角的特殊性      ← 为什么是林辰？血脉秘密怎么来的？
  ❓ 五、第一卷具体任务     ← 不是"站稳脚跟"，是"完成什么具体目标"
```

---

## 二、完整流程框架

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         世界包驱动创作流程 v3.0                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Phase 1  │    │ Phase 2  │    │ Phase 3  │    │ Phase 4  │              │
│  │ 逻辑追问  │───→│ 交叉验证  │───→│ 逻辑落地  │───→│ 细纲生成  │              │
│  │          │    │          │    │          │    │          │              │
│  │ grill-me │    │ 第二模型 │    │ core-   │    │ chapter │              │
│  │ Socratic │    │ cross-   │    │ logic.md│    │ brief.md│              │
│  │ 追问     │    │ validate │    │ +        │    │ (300条)│              │
│  │          │    │          │    │ world-   │    │          │              │
│  │ 输入：    │    │ 输入：    │    │ pack.json│    │ 输出：   │              │
│  │ ·世界骨架 │    │ ·决策树  │    │ 更新     │    │ ·细纲YAML│              │
│  │ ·核心概念│    │ ·逻辑文件│    │          │    │ ·世界包更新│              │
│  │          │    │          │    │ 输入：    │    │ ·首章重写│              │
│  │ 输出：    │    │ 输出：    │    │ ·逻辑文件│    │          │              │
│  │ ·DECISION│    │ ·验证报告│    │ ·角色档案│    │ 每章细纲 │              │
│  │ -TREE.md │    │ ·TODO清单│    │ ·卷规划  │    │ 包含：    │              │
│  │          │    │          │    │          │    │ ·场景    │              │
│  └──────────┘    └──────────┘    └──────────┘    │ ·冲突    │              │
│       ↑                                              │ ·爽点    │              │
│       │         ┌──────────┐                        │ ·钩子    │              │
│       │         │ Phase 5  │                        │ ·信息揭示│              │
│       │         │  正文创作 │                        │          │              │
│       │         │          │                        └──────────┘              │
│       │         │ SOP C+  │                        ┌──────────┐              │
│       │         │ gate-    │───→ Phase 6          │ Phase 6  │              │
│       │         │ check    │    世界包动态更新     │ 世界同步 │              │
│       │         │ PASS     │                        │          │              │
│       │         └──────────┘                        │ world-  │              │
│       │                    ↑                       │ sync.py │              │
│       │                    │                       │ scan    │              │
│       │         ┌──────────┐                        └──────────┘              │
│       │         │ Phase 7  │                                                  │
│       │         │ 单章细纲  │                                                  │
│       │         │ 生成器    │                                                  │
│       │         │          │                                                  │
│       │         │ 输入：    │                                                  │
│       │         │ ·细纲YAML │                                                  │
│       │         │ ·世界包   │                                                  │
│       │         │ ·角色档案 │                                                  │
│       │         │          │                                                  │
│       │         │ 输出：    │                                                  │
│       │         │ ·chapter- │                                                  │
│       │         │ brief.md  │                                                  │
│       │         └──────────┘                                                  │
│       │                                                                       │
│       └───────────────────────────────────────────────────────────────────────┘
│                            循环：每写完一章细纲 → 补全世界包 → 生成下一章细纲   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、Phase 详细说明

### Phase 1：逻辑追问（grill-me）

**触发词**：`grill me` / `先追问我` / `世界包构建`

**输入**：
- `world/world-bible.md`（现有骨架）
- `world/core-concept.md`（核心概念）
- `characters/protagonist.json`（主角档案）
- `outline/outline-v1.md`（五卷框架）

**追问领域（5个，固定顺序）**：

```yaml
# templates/world-question-bank.yaml
question_domains:
  - id: Q01
    name: "力量体系的代价"
    goal: "明确境界晋升的具体代价和社会影响"
    starter_question: "锻体九重和聚气初，差距体现在哪些具体方面？谁是这个差距的受益者/受害者？"
    follow_up_pattern:
      - "这个差距为什么存在？是谁定的？"
      - "违反这个规矩的后果是什么？"
      - "有没有人想改变它？为什么没改成？"
      - "主角的处境在这个体系里处于什么位置？"
    expected_output: "权力来源 + 代价机制 + 反抗可能性"

  - id: Q02
    name: "社会结构的根源"
    goal: "明确阶层流动的限制条件"
    starter_question: "林辰是杂役，杂役在这个世界里为什么只能待在丹房？"
    follow_up_pattern:
      - "这个限制是他自己选的，还是制度强加的？"
      - "制度的来源是什么（谁定的/为什么定）？"
      - "有没有绕过这个限制的途径？"
      - "如果主角要改变处境，他需要突破什么？"
    expected_output: "制度来源 + 流动通道 + 主角的突破口"

  - id: Q03
    name: "核心矛盾的发动机"
    goal: "明确故事的冲突根源"
    starter_question: "天机阁为什么选择中立？中立对主角意味着什么？"
    follow_up_pattern:
      - "魔道觊觎鉴灵匣的真正原因是什么？"
      - "阁主玄机子百年坐镇，他在等什么？"
      - "如果主角的金手指暴露，谁会受益/受损？"
      - "主线矛盾的终点是什么？"
    expected_output: "冲突源 + 各方利益 + 终点定位"

  - id: Q04
    name: "主角的特殊性"
    goal: "明确为什么是林辰，而不是别人"
    starter_question: "鉴灵匣为什么认林辰为主？是巧合还是必然？"
    follow_up_pattern:
      - "林辰的血脉/身世有什么特殊之处？"
      - "为什么他恰好是杂役身份？"
      - "他的性格特质如何与辅助之道匹配？"
      - "如果他一开始不是杂役，故事会变成什么样？"
    expected_output: "血脉秘密 + 身份必然性 + 性格匹配"

  - id: Q05
    name: "第一卷具体任务"
    goal: "把"站稳脚跟"变成可执行的具体目标"
    starter_question: "第一卷30章，林辰要在丹房完成什么具体任务？"
    follow_up_pattern:
      - "这个任务的目标是什么？谁定的？"
      - "任务的考核标准是什么？"
      - "任务失败会怎样？成功会怎样？"
      - "任务过程中会遇到什么阻碍？"
      - "任务完成后，主角获得什么？失去什么？"
    expected_output: "任务定义 + 成功/失败条件 + 得失权衡"
```

**输出**：
- `DECISION-TREE.md`（决策树，每个问题→答案→分支）
- `TODO.md`（未决问题清单，Phase 2 填入）

---

### Phase 2：交叉验证（第二模型审查）

**触发词**：自动（Phase 1 完成后）或手动（`grill me --review`）

**输入**：
- `DECISION-TREE.md`
- `world/world-bible.md`
- `world/core-logic.md`（Phase 3 生成，Phase 2 检查一致性）

**审查维度**：
```yaml
review_checklist:
  - name: "内部一致性"
    desc: "铁律之间是否有矛盾"
    example: "Q01说境界差一阶=绝对压制，Q03说魔道可以越级挑战 → 矛盾"
  
  - name: "与现有世界包一致性"
    desc: "新逻辑是否与 world-bible.md 冲突"
    example: "Q02说杂役可参加测试，但 world-bible 说杂役无资格 → 矛盾"
  
  - name: "边条件覆盖"
    desc: "是否考虑了边界情况"
    example: "主角使用鉴灵匣时，刻纹增加→暴露风险，这个机制有没有被利用？"
  
  - name: "可执行性"
    desc: "答案是否可以转化为具体创作指令"
    example: "Q05说任务目标是'站稳脚跟'→太模糊，需改为'完成筑基丹炼制任务'"
```

**输出**：
- `VALIDATION-REPORT.md`（验证报告，标注✅/⚠️/❌）
- `DECISION-TREE.md`（更新版，填入修正后答案）

---

### Phase 3：逻辑落地（写文件）

**输入**：
- `DECISION-TREE.md`（Phase 2 验证后）
- `world/world-bible.md`（现有骨架）

**产出文件**：

```
projects/helper-creator/world/
├── world-bible.md          # 保留（骨架层）
├── core-logic.md           # 新增（核心逻辑层，Phase 3 写入）
├── world-pack.json         # 更新（Phase 3 同步写入新条目）
└── iron-laws.md            # 新增（铁律清单，从决策树提取）
```

**core-logic.md 格式**：
```markdown
# 《{书名}》世界核心逻辑

> 生成日期：{date}
> 来源：DECISION-TREE.md
> 状态：{draft|validated|frozen}

## 一、力量体系的代价

### 铁律
1. {从 Q01 提取的法则}
2. ...

### 代价机制
- 晋升代价：{谁付代价？}
- 违规后果：{违反规矩会怎样？}
- 收益归属：{谁从差距中获益？}

## 二、社会结构

### 阶层流动通道
| 通道 | 条件 | 成功率 | 限制 |
|------|------|--------|------|
| {通道名} | {条件} | {X%} | {限制} |

### 主角处境
- 当前位置：{起点}
- 可突破路径：{有哪些路？}
- 主要障碍：{什么阻止他上升？}

## 三、核心矛盾

### 矛盾根源
{一句话概括}

### 各方立场
| 势力 | 立场 | 核心诉求 | 与主角关系 |
|------|------|---------|-----------|
| {势力} | {正/反/中立} | {诉求} | {敌/友/利用} |

## 四、主角特殊性

### 血脉/身世
{为什么是林辰}

### 身份必然性
{为什么是杂役，不是弟子}

### 性格匹配
{他的特质如何与辅助之道契合}

## 五、第一卷任务

### 任务定义
- 目标：{具体可执行的目标}
- 发起者：{谁给的任务}
- 截止时间：{第几章前完成}
- 成功条件：{怎样算完成}
- 失败后果：{失败会怎样}

### 任务阻碍
| 阻碍 | 类型 | 强度 | 出现章节 |
|------|------|------|---------|
| {阻碍名} | {人/事/环境} | {高/中/低} | Ch{X} |

### 任务收益
- 短期：{完成后的即时收益}
- 长期：{对主线的影响}
- 代价：{完成任务的代价}
```

---

### Phase 4：细纲生成（从逻辑到章节）

**输入**：
- `world/core-logic.md`（Phase 3 输出）
- `characters/*.json`（角色档案）
- `outline/outline-v1.md`（五卷框架）

**工具**：`tools/chapter-brief-generator.py`（新建）

**输出**：
```
projects/helper-creator/outline/
├── outline-v1.md              # 保留（五卷框架）
├── vol-001-brief.yaml         # 新增（第一卷细纲）
├── ch-001-brief.md            # 新增（第一章单章细纲）
└── vol-001-{chN}-brief.md     # 后续章节细纲
```

**vol-001-brief.yaml 格式**：
```yaml
volume:
  id: vol-001
  title: "初露锋芒"
  chapter_range: [1, 30]
  created: "2026-09-30"
  
  core_task:  # 从 Q05 提取
    goal: "完成筑基丹炼制任务，通过外门弟子考核"
    requester: "孙鹤（丹房管事）"
    deadline: "Ch15 前"
    success: "成功炼制筑基丹 + 通过考核"
    failure: "被逐出天机阁"
  
  thrill_schedule:
    - ch: 1-3   # 破冰期
      target: L2
      design: "展示能力但不暴露"
    - ch: 5     # 第一次小高潮
      target: L2
      design: "暗中解决丹房危机"
    - ch: 10    # 中期转折
      target: L3
      design: "宗门测试一鸣惊人"
    - ch: 15    # 任务截止
      target: L3
      design: "完成筑基丹任务"
    - ch: 20-25 # 第二波
      target: L2-L3
      design: "阁主开始观察"
    - ch: 30    # 卷末大钩子
      target: L4
      design: "阁主暗示"
  
  chapters:
    - chapter: 1
      title: "第三处节点"
      scene: "丹房夜巡"
      characters: ["林辰", "张明德", "陆鸣", "老赵（背景）"]
      conflict: |
        第七号炉火候失控，张明德束手无策。
        陆鸣嘲笑杂役多管闲事。
        林辰必须在"开口救场"和"闭嘴自保"之间选择。
      thrill_level: L1
      thrill_design: |
        - 压抑：陆鸣羞辱林辰（读者愤怒）
        - 释放：林辰点出第三处节点（读者痛快）
        - 余韵：林辰拒绝嘉奖，继续低调（人设立住）
      info_reveal:
        reader_knows: "林辰能看出火候问题，有特殊能力"
        character_knows: "张明德开始留意林辰，但不知原因"
        info_gap: "陆鸣完全不知道林辰的底细"
      hook: "匣身纹路忽然亮了一下——有人来了"
      constraints:
        - "不得提前揭示鉴灵匣功能"
        - "林辰不可主动暴露能力"
        - "场景过渡需自然（禁止硬切）"
      world_logic_reference:
        - "iron_law: 境界差一阶=绝对压制（陆鸣筑基 vs 林辰凡境）"
        - "social_rule: 杂役不得越权指点（林辰的处境约束）"
```

---

### Phase 5：正文创作（SOP C+，已有）

**工具**：`tools/gate-check.py` + `tools/novel-humanizer.py`（已有）

**输入**：
- `outline/ch-{N}-brief.md`（单章细纲）
- `world/core-logic.md`（核心逻辑）
- `characters/*.json`（出场角色档案）

**流程**：按现有 SOP C+ 执行

---

### Phase 6：世界同步（已有）

**工具**：`tools/world-sync.py`（已有）

**触发**：`gate-check PASS` 后自动追加事件

---

### Phase 7：单章细纲生成（新增工具）

**工具**：`tools/chapter-brief-generator.py`（新建）

**输入**：
- 全书细纲（`vol-001-brief.yaml`）
- 世界包（`world/core-logic.md` + `world-pack.json`）
- 角色档案（`characters/*.json`）

**输出**：
- `outline/ch-{N}-brief.md`（单章写作指令）

**单章细纲格式**：
```markdown
# 第{N}章细纲：《{标题}》

> 生成日期：{date}
> 所属卷：{volume}
> 位置：Ch{start}-{end}

## 基础信息
- **章节**：{N}
- **标题**：{title}
- **场景**：{location}
- **时长**：{time_span}
- **字数目标**：{word_count}（2000-3000）

## 出场角色
| 角色 | 境界 | 在场理由 | 本章变化 |
|------|------|---------|---------|
| {name} | {realm} | {reason} | {change} |

## 核心冲突
{一段话描述本章核心冲突}

## 爽点设计
- **层级**：L{N}
- **压抑点**：{什么让读者不舒服？}
- **释放点**：{什么让读者痛快？}
- **余韵**：{释放后留什么？}

## 信息揭示
- **读者知道**：{本章揭示的新信息}
- **角色知道**：{各角色的认知状态}
- **信息差**：{制造悬念的信息差}

## 章末钩子
{让读者点下一章的具体悬念}

## 世界包约束
| 约束类型 | 具体内容 | 违反后果 |
|---------|---------|---------|
| 境界匹配 | {规则} | {P0 阻断} |
| 资源限制 | {规则} | {P1 警告} |
| 知情边界 | {规则} | {P0 阻断} |

## 写作禁忌
- {禁忌1}
- {禁忌2}
- {禁忌3}

## 场景过渡要求
- 上一章结尾：{上章最后一句/情绪}
- 本章开头需衔接：{过渡方式}
- 场景切换点：{哪里需要过渡桥段}
```

---

## 四、工具清单

### 已有工具（可直接使用）
| 工具 | 路径 | 用途 |
|------|------|------|
| `grill-me` skill | `/var/minis/skills/grill-me/` | Phase 1 追问 |
| `world-pack.py` | `tools/world-pack.py` | Phase 3 写入 |
| `world-maintainer.py` | `tools/world-maintainer.py` | Phase 3 去重 |
| `world-sync.py` | `tools/world-sync.py` | Phase 6 同步 |
| `gate-check.py` | `tools/gate-check.py` | Phase 5 门禁 |
| `novel-humanizer.py` | `tools/novel-humanizer.py` | Phase 5 AI味检测 |
| `paragraph-four-questions.py` | `tools/paragraph-four-questions.py` | 段落级逻辑阻塞 |
| `minis-model-use` | CLI | Phase 2 交叉验证 |

### 新建工具（待实现）
| 工具 | 路径 | 用途 | Phase |
|------|------|------|-------|
| `world-logic-builder.py` | `tools/world-logic-builder.py` | Phase 1→3 转换 | 1+3 |
| `chapter-brief-generator.py` | `tools/chapter-brief-generator.py` | Phase 4 细纲生成 | 4 |
| `world-logic-validator.py` | `tools/world-logic-validator.py` | Phase 2 一致性检查 | 2 |

### 新建模板（待实现）
| 模板 | 路径 | 用途 |
|------|------|------|
| `world-question-bank.yaml` | `templates/world-question-bank.yaml` | Phase 1 问题库 |
| `chapter-brief.yaml` | `templates/chapter-brief.yaml` | Phase 4 细纲模板 |
| `core-logic.md` | 项目 `world/core-logic.md` | Phase 3 逻辑文件 |
| `iron-laws.md` | 项目 `world/iron-laws.md` | Phase 3 铁律清单 |

---

## 五、执行纪律

### 顺序约束（不可跳步）
```
Phase 1（追问）→ Phase 2（验证）→ Phase 3（落地）→ Phase 4（细纲）→ Phase 5（创作）
    ↓                ↓                ↓
  DECISION-     VALIDATION-       core-
  TREE.md       REPORT.md         logic.md
```

**跳过 Phase 1-3 直接写正文 = 回到之前的失败模式**

### 迭代约束
- 每写完一章细纲，回看 `core-logic.md`，补充缺失逻辑
- 每写完一章正文，运行 `world-sync.py scan`，提取新实体
- 发现逻辑矛盾时，回退到 Phase 2 重新验证

### 版本纪律
- `core-logic.md` 每次更新需版本号递增（v1.0 → v1.1 → v2.0）
- `DECISION-TREE.md` 每次追问后追加版本记录
- `chapter-brief.yaml` 每次更新需对应细纲版本号

---

## 六、与本框架的接口

### Grill-Me 适配
当前 grill-me skill 输出 `DECISION-TREE.md` + `PLAN.md`，本框架直接使用此格式：
- `DECISION-TREE.md` → Phase 2 输入
- `PLAN.md` → Phase 3 执行计划

### novelkit 适配
Phase 5 正文创作时，`chapter-brief.md` 中的 `world_logic_reference` 字段将作为 gate-check 的输入，确保正文不违反核心逻辑。

---

## 七、动态调整机制

### 为什么需要动态调整？

五卷框架是基于"100万字目标 ÷ 2500字/章 = 400章 ÷ 5卷 = 80章/卷"的估算。
创作过程中会发现：

| 现象 | 原因 | 调整方向 |
|------|------|---------|
| 第一卷写不完30章 | 设定释放不够，需要更多铺垫 | 拆分或扩充 |
| 第二卷只写了20章就完结 | 情节密度过高，节奏太快 | 合并或扩展 |
| 某卷爽点太密集 | 读者疲劳，需要缓冲章 | 插入过渡章 |
| 某卷爽点太稀疏 | 读者流失，需要压缩 | 删除冗余章 |

### 动态调整工具

```bash
# 分析当前进度，生成调整建议
python3 tools/outline-dynamic-adjust.py analyze --project helper-creator

# 查看当前大纲状态
python3 tools/outline-dynamic-adjust.py status --project helper-creator
```

**分析维度**：
- 已完成章节数 vs 目标章节数
- 平均每章字数 vs 目标字数（2500字）
- 各卷进度（已完成/进行中/未开始）
- 字数偏离警告（过低/过高）

**输出**：
- `outline/dynamic-adjustment.json` — 调整建议（JSON格式）
- 控制台输出 — 人类可读的状态概览

### 调整流程

```
Phase 4 生成细纲
      ↓
Phase 5 创作正文
      ↓
gate-check PASS
      ↓
每写完10章，运行 analyze
      ↓
根据建议动态调整后续大纲
      ↓
更新 chapter-brief.md
      ↓
继续创作
```

---

## 八、下一步行动

### 立即执行（今天）
1. [x] 创建框架文档 `world-building-flow-v3.md`
2. [x] 创建追问问题库 `templates/world-question-bank.yaml`
3. [x] 创建桥接工具 `tools/grill-world-bridge.py`
4. [x] 创建逻辑构建器 `tools/world-logic-builder.py`
5. [x] 创建细纲生成器 `tools/chapter-brief-generator.py`
6. [x] 创建动态调整工具 `tools/outline-dynamic-adjust.py`
7. [ ] 用 grill-me 跑 Phase 1（5个追问领域）
8. [ ] 生成 Phase 3 输出文件
9. [ ] 生成 Phase 4 第一卷细纲

### 文档更新
1. [ ] 更新 `docs/SOP-CREATION-FLOW.md`，加入动态调整机制
2. [ ] 更新 `TEAM.md`，标记流程升级
