# 玄天大陆 · SkillSystem 借鉴整合报告

> 来源：dongweiPeng/SkillSystem（373★，Unity C#，2018，游戏技能系统框架）
> 整合时间：2026-09-28
> 定位：**纯方法论借鉴，不装本地 Skill**（Unity/C# 环境错位 + 代码已 8 年未更新）
> 对应世界包：`.world-packs/玄天大陆.json`（87→92，新增 law/power/thing 5 条目）

---

## 一、仓库速览

| 维度 | 数据 |
|------|------|
| Stars | 373 / Forks 89 |
| 语言 | C# 100%（Unity） |
| 创建 | 2018-06-08 / 最后 push 2018-06-11 |
| 规模 | 1006 文件 / 3.6 MB |
| License | 无（个人框架） |

**核心模块**：
- `SkillManager`（单例）：技能生命周期调度器
- `Skill`（ISkill）：执行单元，4 阶段 Verify→Sing→Caculate→End
- `Entity`：角色实体（HP/MP/Fight/Defence/Crit + Buff 列表）
- `Attribute`：技能数据容器（CostMp/CD/AffectRound/AtRound/Value/Mute/Segment）
- `Task` + `TaskManager`：条件驱动任务队列（TimeCondition/LogicCondition/TriggerCondition/EventCondition）
- `IVerify`：前置验证接口（MpVerify 等，优先级排序）
- `SkillTable`：技能表（目前仅 Cost+Id，设计为 Excel 导入）

---

## 二、三个领域错位（决定不装本地 Skill）

1. **技术栈错位**：Unity C#，iSH 不可用（对齐 higgsfield/watermarks-remover 同型）
2. **代码成熟度低**：SkillTable 只有 Id+Cost 两个字段，无 CD/类型/描述/标签/范围，"完整流程"名不副实
3. **与现有小说工具链零重叠**：novel-team 是 Python CLI，SkillSystem 是 Unity 编辑器插件，两者没有可复用的代码边界

---

## 三、方法层迁移（P1 借鉴 4 项）

### 3.1 四阶段 → 章节契约模板（P1）

**原框架**：`Verify(前提校验) → Sing(吟唱铺垫) → Caculate(伤害结算) → End(收尾回调)`

**小说版**：每章 4 个必填段，强制结构化，避免"写到哪算哪"：

| 阶段 | 小说等价 | 必填字段 | 示例（萧辰） |
|------|---------|---------|------------|
| **V 前提** | 本章前提状态 | `prereq: [已淬体三重/天命剑未激活]` | 主角当前境界、状态、目标 |
| **I 铺垫** | 压抑/信息释放 | `tension_in: 0~1`（本章紧张度上升量） | 被王大嘲讽→触发大比规则→夜观星象 |
| **C 结算** | 高潮/后果 | `climax: L2/L3/L4` + `outcome: 结果描述` | 擂台突破至淬体四重 + 天命剑初现寒芒 |
| **E 收尾** | 钩子/状态回写 | `hook: 新悬念` + `changes: [境界变更]` | 王执事暗中观察 + 事实账本 + 下章预告 |

**价值**：让每章有明确的"输入→输出"，而不是"开头结尾"——对齐 tianming-novel-ai-writer 的 12 类变更声明思路，但更轻量。

### 3.2 前置验证 → 大纲硬闸（P1）

**原框架**：`IVerify.Verify(caster, target, attribute)` 返回 true/false，失败则 Interrupt。

**小说版**：chapter-contract.py 加"V 阶段"检查——如果本章前提状态（境界/位置/状态）与事实账本不匹配，**不进入创作，先修复账本**。

举例：
- 账本写着"淬体四重"，大纲 V 阶段写"淬体三重" → 报错：前提矛盾
- 账本无"天命剑已激活"，大纲 I 阶段写"天命剑寒芒大作" → 报错：无前提

这是 gate-check.py 的**语义级扩展**（gate-check 目前只验 AI 味/字数/段落）。

### 3.3 多段打击 → 章节多高潮（P2）

**原框架**：`Attribute.Segment` = 一次技能多段伤害（如三连击），每段独立计算。

**小说版**：一章允许"多高潮节拍"（非冲突），比如：
- L3 高潮：大比胜利突破
- L2 次高潮：天命剑显威王执事震惊
- L1 收尾：王放狠话

**校验规则**：同一章内 L3+ 节拍 ≤2 个，否则高潮通胀。

### 3.4 Buff 追踪 → 角色状态账本（P2）

**原框架**：`Entity.m_BuffList` 列表，每个 buff 有 `AtRound`（生效回合）和 `Skill`（来源），回合推进时自动结算。

**小说版**：角色档案加 `buff` 字段——不是"负面效果"，而是**状态追踪**：
- `重伤`：境界战力暂时 -20%，3 章后自然恢复
- `破防`：防御力临时失效，对手 L4 暴击率翻倍
- `觉醒`：天命剑封印解除 1 层，激活折寿减少 10%

**规则**：状态变更必须写进账本，状态结束也必须写进账本（否则状态残留 bug）。

---

## 四、诚实边界

1. **SkillSystem 本身是半成品**：SkillTable 仅 Id+Cost，无类型/描述/标签/范围/冷却/音效/图标；`DamageCondtion.cs` 源码取不到（可能是空实现或路径错误）；README 只有 5 行中文要点。
2. **移植不等于复制**：原框架是为"回合制/即时制战斗"设计的，小说是"线性叙事"，直接照搬会僵化；本文档的迁移都是**松散类比**，不是代码级移植。
3. **与 Progression-Architect 的差异**：前者管"怎么设计一套成长系统"（方法论），后者管"怎么设计一套技能释放机制"（工程结构）——两架互补但不重叠，本报告只取后者。

---

## 五、落地物清单

| 物 | 位置 | 状态 |
|----|------|------|
| 章节契约模板（V/I/C/E 四段） | `tools/chapter-contract.py`（新建） | ⏳ P1 待实施（需用户确认后） |
| 前置硬闸校验（账本→V 阶段匹配） | `tools/chapter-contract.py` 内置 | ⏳ P1 同上 |
| 角色 buff 追踪字段 | `characters/characters.json` schema 扩展 | ⏳ P2 待写 |
| 多高潮节拍约束 | `tools/outline-precheck.py` 扩展 | ⏳ P2 同上 |
| 本归档笔记 | `03-Resources/AI工具/游戏技能系统框架 SkillSystem dongweiPeng.md` | ✅ 本次写入 |
