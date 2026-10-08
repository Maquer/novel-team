# 小说团队 v2.3.0 落地报告

> 落地日期：2026-09-30
> 版本：v2.3.0
> 状态：🟢 就绪，等待追问启动

---

## 一、本次落地内容

### 新增工具（1个）

| 工具 | 路径 | 大小 | 用途 |
|------|------|------|------|
| `grill-gate-bridge.py` | `tools/` | 19KB | grill-me ↔ 质量门禁系统衔接层 |

### 功能说明

**grill-gate-bridge.py** 是 grill-me 与质量门禁系统的衔接工具，用于：

1. **阈值决策追问**（Phase 0）
   - GQ01：字数下限（soft_min=1500 为什么？）
   - GQ02：AI味阻断线（block_at=16 为什么？）
   - GQ03：AI味预警线（warn_at=13 为什么？）
   - GQ04：超长警告线（warn_above=5500 为什么？）
   - GQ05：其他插件阈值（13个插件的阈值在哪里定义的？）

2. **决策记录落地**
   - 生成 `threshold-decision-{date}.md` 决策文档
   - 包含当前配置、追问记录、决策依据、调优建议

3. **状态检测**
   - 显示当前阈值配置
   - 分析已写章节字数分布
   - 自动预警低于阈值的章节

---

## 二、完整工具链（v2.3.0）

### 世界包构建链

```
grill-world-bridge.py      ← grill-me ↔ 世界包衔接
    ↓
world-logic-builder.py     ← Phase 1→3 主控
    ↓
core-logic.md + iron-laws.md  ← 落地产出
```

### 大纲创作链

```
outline-grill-bridge.py    ← grill-me ↔ 大纲衔接
    ↓
vol-001~005-brief.yaml     ← 卷细纲落地
    ↓
chapter-brief-generator.py ← 单章细纲生成
    ↓
ch-001~XXX-brief.md        ← 写作指令
```

### 质量门禁链

```
grill-gate-bridge.py       ← grill-me ↔ 门禁衔接
    ↓
threshold-decision-{date}.md  ← 阈值决策记录
    ↓
config/novelkit.json       ← 阈值配置（可选调整）
```

### 动态调整链

```
outline-dynamic-adjust.py  ← 进度分析 + 调整建议
    ↓
outline/dynamic-adjustment.json  ← 调整建议输出
```

---

## 三、命令速查

### 世界包构建

```bash
# 启动追问
python3 tools/grill-world-bridge.py start --project helper-creator

# 落地逻辑
python3 tools/grill-world-bridge.py build --project helper-creator

# 查看状态
python3 tools/grill-world-bridge.py status --project helper-creator
```

### 大纲创作

```bash
# 启动追问
python3 tools/outline-grill-bridge.py start --project helper-creator

# 落地细纲
python3 tools/outline-grill-bridge.py build --project helper-creator

# 生成单章细纲
python3 tools/chapter-brief-generator.py --project helper-creator --volume 1 --batch
```

### 质量门禁

```bash
# 启动阈值决策追问
python3 tools/grill-gate-bridge.py start --project helper-creator

# 落地决策记录
python3 tools/grill-gate-bridge.py build --project helper-creator

# 查看阈值状态
python3 tools/grill-gate-bridge.py status --project helper-creator
```

### 统一入口

```bash
# 启动世界包追问
bash scripts/novel-team-start.sh world

# 启动大纲追问
bash scripts/novel-team-start.sh outline

# 启动门禁阈值追问
bash scripts/novel-team-start.sh gate

# 完整流程
bash scripts/novel-team-start.sh full

# 查看所有状态
bash scripts/novel-team-start.sh status
```

---

## 四、当前状态

### 已就绪 ✅

- [x] 6个新工具（语法检查通过）
- [x] 2个新模板
- [x] 5个新文档
- [x] 1个启动脚本
- [x] TEAM.md 注册更新（v2.3.0）
- [x] world-bible.md（已有）
- [x] world-pack.json（已有）
- [x] 角色档案 8个（已有）
- [x] 第一章正文（已有，3534字）
- [x] 第二章正文（已有）

### 待落地 ⏳

- [ ] core-logic.md（Phase 3 产出）
- [ ] iron-laws.md（Phase 3 产出）
- [ ] DECISION-TREE.md（Phase 1+4a+gate 产出）
- [ ] vol-001-brief.yaml（Phase 4b 产出）
- [ ] ch-001-brief.md（Phase 4c 产出）
- [ ] threshold-decision-*.md（gate Phase 产出）

### 当前阈值预警 ⚠️

```
【字数分布分析】
  章节数: 2
  平均字数: 2432
  最小字数: 1311（低于 soft_min=1500）
  最大字数: 3553

⚠️  有章节低于字数阈值，建议运行阈值决策追问
```

---

## 五、下一步行动

### 推荐顺序

```bash
# 步骤1：启动世界包追问（先定铁律）
bash scripts/novel-team-start.sh world
# 然后说 "grill me"

# 步骤2：落地世界逻辑
python3 tools/grill-world-bridge.py build --project helper-creator

# 步骤3：启动大纲追问
bash scripts/novel-team-start.sh outline
# 然后说 "grill me"

# 步骤4：落地大纲文件
python3 tools/outline-grill-bridge.py build --project helper-creator

# 步骤5：生成细纲
python3 tools/chapter-brief-generator.py --project helper-creator --volume 1 --batch

# 步骤6：（可选）启动门禁阈值追问
python3 tools/grill-gate-bridge.py start --project helper-creator
# 然后说 "grill me"
```

---

## 六、grill-me 适用边界总结

| 场景 | grill-me 适用性 | 说明 |
|------|---------------|------|
| **世界包核心逻辑** | ✅ 必须用 | 决定故事的"为什么"，不能猜测 |
| **大纲结构设计** | ✅ 必须用 | 决定五卷/章节数/爽点节奏，需要追问验证 |
| **阈值决策** | ✅ 推荐使用 | 决定门禁松紧，需要数据支撑 |
| **单章细纲生成** | ❌ 不需要 | 已有模板，直接生成 |
| **正文创作** | ❌ 不需要 | 按细纲执行，gate-check 检查 |
| **门禁检查执行** | ❌ 不适用 | 确定性规则，直接运行 |

**核心原则**：grill-me 用于"决策层"（为什么），不用于"执行层"（怎么做）。
