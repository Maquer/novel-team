# AbilityKit 借鉴整合报告
> 来源：HOBOBO/AbilityKit（游戏战斗工具集，C#/Unity）
> 借鉴日期：2026-09-28
> 策略：归档+核心机制移植，不做整体引入

---

## 一、AbilityKit 简介

**AbilityKit** 是面向中大型战斗项目的可组合工具集，以 Unity UPM Package 组织源码，提供纯 C# Runtime。
核心定位：**不提供固定战斗框架，只提供可组合的底层积木**——技能编排、事件触发、状态修正、溯源追踪等机制。

> 仓库：https://github.com/HOBOBO/AbilityKit
> 与小说团队的关联：战斗流程编排 ↔ 剧情流程编排；技能触发 ↔ 剧情触发；角色状态 ↔ 角色心理状态

---

## 二、模块对照表（游戏→小说）

| AbilityKit 模块 | 小说团队对应机制 | 已有覆盖 | 优先级 |
|-----------------|-----------------|---------|-------|
| **Pipeline**（技能流程编排，Phase图模型） | 剧情流水线 PlotPipeline | ❌ 无 | **P0** |
| **Triggering**（事件→条件→Action执行） | 剧情触发器 PlotTrigger | ⚠️ decide-trigger.py 基础版 | **P0** |
| **Trace**（溯源树，root/parent/owner上下文） | 剧情溯源链 PlotTrace | ⚠️ fact-snapshot.py 部分覆盖 | **P0** |
| **Modifiers**（参数动态修正，Buff/Debuff） | 状态修正器 StateModifier | ❌ 无 | **P1** |
| **Continuous**（持续效果生命周期） | 持续状态系统 ContinuousState | ❌ 无 | **P1** |
| **GameplayTags**（标签组织状态/规则） | 剧情标签系统 PlotTag | ❌ 无 | **P2** |
| **HFSM**（分层状态机，ITriggerable/IAction） | 角色心理状态机 CharacterHFSM | ❌ 无 | **P2** |
| **Flow**（异步事件驱动流程引擎） | 多线叙事流程 NarrativeFlow | ❌ 无 | **P2** |
| **Ability.Explain**（森林树+导航协议） | 剧情解释器 PlotExplain | ❌ 无 | **P2** |

---

## 三、核心借鉴点详解

### 3.1 Pipeline → 剧情流水线（P0）

**AbilityKit 设计**：
- Phase 图模型：Sequence / Parallel / Conditional / Repeat / Delay / WaitUntil / Timeline
- 每个 Phase 有明确生命周期：Execute() → OnUpdate(dt) → IsComplete() → Reset()
- 复合阶段嵌套：SequencePhase 可包含任意 Phase
- 中断支持：IInterruptiblePhase，可被外部打断并恢复

**小说团队适配**：
- Phase = 剧情段落：开场（Hook）→ 发展（Rise）→ 冲突（Conflict）→ 高潮（Climax）→ 收尾（Resolution）
- 支持多线并行（Parallel）：多角色视角交替推进
- 支持条件分支（Conditional）：根据角色选择分叉剧情
- 支持等待（WaitUntil）：等待某个剧情条件满足再继续

**已有基础**：outline-precheck.py 有节拍检查，但缺流程编排引擎

---

### 3.2 Triggering → 剧情触发器（P0）

**AbilityKit 设计**：
- EventBus：统一事件总线，所有战斗事件经此分发
- TriggerRunner：订阅事件→条件评估→执行Action
- TriggerPlan：配置化规则节点树，支持 Priority/Order 排序
- ExecCtx：执行上下文，携带 EventBus + FunctionRegistry + Blackboard

**小说团队适配**：
- 事件类型：chapter_start / scene_change / character_enter / conflict_escalate / foreshadow_recall 等
- 条件：角色状态、剧情进度、时间线位置
- Action：触发动作（写事实账本、推演下一情节、提示决策点）
- 与 decide-trigger.py 的关系：本工具是 extend，decide-trigger 只识别用户决策点，PlotTrigger 覆盖全量剧情事件

---

### 3.3 Trace → 剧情溯源链（P0）

**AbilityKit 设计**：
- TraceNode：每个Effect/Buff/投射物带 root/parent/owner context
- 血缘追踪：从最终结果反查"谁造成的、经过哪些中间环节"
- 用于战斗归因、调试、回放

**小说团队适配**：
- 因果链：事件A → 触发事件B → 导致结果C
- 角色行为溯源：某角色在章节X的行为，追溯到之前的伏笔/设定
- 与 fact-snapshot.py 的区别：快照是"某个时刻的状态"，Trace 是"因果过程"
- 用于：一致性检查（某事件有无合理前因）、作者回溯（为什么这个角色做了这个选择）

---

### 3.4 Modifiers → 状态修正器（P1）

**AbilityKit 设计**：
- 通用参数修正器：Buff/装备/天赋动态改写技能参数
- 脏标记优化：参数变化时只重算受影响的部分
- 多层叠加：多个 Modifier 按优先级合并

**小说团队适配**：
- 角色状态修正：受伤→战斗力下降；恋爱中→判断力下降；获得秘籍→技能提升
- 情节参数修正：场景氛围 modifier（紧张/轻松）、节奏 modifier（快进/慢放）
- 多 modifier 叠加：角色同时处于"受伤"+ "愤怒"状态，需综合评估

---

### 3.5 Continuous → 持续状态（P1）

**AbilityKit 设计**：
- 条件驱动的激活/阻止/暂停/恢复/移除
- Tag 规则控制：特定 GameplayTag 存在时激活，不存在时阻止
- 保留 explain 结果：每轮 Tick 记录为什么继续/停止

**小说团队适配**：
- 持续性剧情状态："追杀中"、"逃亡中"、"热恋中"——这些状态跨章节持续
- 激活条件：某个事件发生后进入该状态
- 终止条件：完成某个目标或触发某个事件
- 暂停/恢复：暂时中断追杀但后续恢复

---

### 3.6 GameplayTags → 剧情标签（P2）

**AbilityKit 设计**：
- 标签树形结构：支持层级和组织
- 按标签查询：FindTags("HasBuff.Fire") 返回所有带火系Buff的角色
- 用于规则配置引用，避免硬编码

**小说团队适配**：
- 剧情标签：#复仇线 / #感情线 / #成长线 / #伏笔_天命剑
- 角色标签：#主角 / #反派 / #中立 / #已死
- 世界标签：#玄天大陆 / #天剑宗 / #血煞门
- 用途：快速检索、批量过滤、剧情线分析

---

### 3.7 HFSM → 角色心理状态机（P2）

**AbilityKit 设计**：
- 分层状态机：每个状态可嵌套子状态机
- ITriggerable：事件驱动状态转换
- IAction：行为层，返回 Running/Success/Failure
- Decorator AOP：BeforeEnter/AfterEnter/BeforeExit/AfterExit 钩子

**小说团队适配**：
- 角色心理状态：平静→愤怒→崩溃→觉醒（层次结构）
- 触发条件：受到攻击→进入"愤怒"；被背叛→进入"崩溃"
- 状态持久化：跨章节保持心理状态，影响后续行为
- 用于：角色弧光的一致性保障

---

### 3.8 Flow → 多线叙事（P2）

**AbilityKit 设计**：
- IFlowNode 节点树：Sequence / Race / Parallel / If / Timeout / Await
- WAKE/PUMP 事件驱动：节点等待外部信号再继续
- FlowContext：作用域内数据传递

**小说团队适配**：
- 多线叙事：主角线 / 配角线 / 反派线 并行推进
- 汇聚点：多条线在某章节交汇
- 异步等待：等待某个支线完成后再推进主线
- 超时处理：某条线长时间无进展→自动收束

---

### 3.9 Ability.Explain → 剧情解释器（P2）

**AbilityKit 设计**：
- 森林树+导航协议：将复杂执行链路可视化
- 用于调试：某效果为什么生效/没生效

**小说团队适配**：
- 剧情逻辑可解释：某章为什么这样写？追溯到大纲→触发器→Phase 执行路径
- 用于审稿：快速定位逻辑断层

---

## 四、实施计划

### P0（本次实施）
- [x] `tools/plot-pipeline.py` — 剧情流水线引擎（Phase图模型）
- [x] `tools/plot-trigger.py` — 剧情触发器（EventBus+TriggerPlan）
- [x] `tools/plot-trace.py` — 剧情溯源链（因果链追踪）
- [ ] 更新 `TEAM.md` 工具表和SOP
- [ ] 写回归测试

### P1（后续）
- [ ] `tools/state-modifier.py` — 状态修正器
- [ ] `tools/continuous-state.py` — 持续状态系统

### P2（后续）
- [ ] `tools/plot-tag.py` — 剧情标签系统
- [ ] `tools/character-hfsman.py` — 角色心理状态机
- [ ] `tools/narrative-flow.py` — 多线叙事流程
- [ ] `tools/plot-explain.py` — 剧情解释器

---

## 五、重要边界说明

1. **不照搬代码**：AbilityKit 是 C#/Unity，本团队是 Python，只借鉴设计模式和抽象
2. **游戏→小说映射是有损的**：战斗的"伤害计算"不等价于剧情的"情感冲击"，需适配
3. **Phase 模型是核心遗产**：无论什么类型小说，章节流程编排都是刚需
4. **Trace 是差异化优势**：现有工具（fact-snapshot/fact-ledger）偏"状态记录"，缺"因果追踪"
5. **triggering 是 decide-trigger 的超集**：未来 decide-trigger.py 可降级为 plot-trigger 的子集

---

## 六、引用来源

- AbilityKit: https://github.com/HOBOBO/AbilityKit
- 本团队现有相关工具:
  - tools/decide-trigger.py（决策触发判定）
  - tools/fact-snapshot.py（15维事实快照）
  - tools/foreshadow-service.py（伏笔管理）
  - tools/plot-simulation-v2.py（剧情推演）
  - tools/gate-check.py（六道门禁）
  - tools/outline-precheck.py（大纲预检+节拍校验）
