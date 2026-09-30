# 小说团队 v2.2.0 落地报告

> 落地日期：2026-09-30
> 版本：v2.2.0
> 状态：🟢 就绪，等待追问启动

---

## 一、本次落地内容总览

### 新增工具（5个）

| 工具 | 路径 | 大小 | 用途 |
|------|------|------|------|
| `grill-world-bridge.py` | `tools/` | 8KB | grill-me ↔ 世界包构建的衔接层 |
| `world-logic-builder.py` | `tools/` | 15KB | Phase 1→3 主控（grill/build/status） |
| `outline-grill-bridge.py` | `tools/` | 15KB | grill-me ↔ 大纲创作的衔接层 |
| `chapter-brief-generator.py` | `tools/` | 15KB | Phase 4 细纲生成器 |
| `outline-dynamic-adjust.py` | `tools/` | 13KB | 大纲动态调整分析器 |

### 新增模板（2个）

| 模板 | 路径 | 大小 | 用途 |
|------|------|------|------|
| `world-question-bank.yaml` | `templates/` | 5KB | 5个追问领域的标准问题库 |
| `chapter-brief-generator-SKILL.md` | `templates/` | 4KB | 细纲生成器使用说明 |

### 新增文档（4个）

| 文档 | 路径 | 大小 | 用途 |
|------|------|------|------|
| `world-building-flow-v3.md` | `docs/` | 23KB | 完整七阶段流程设计文档 |
| `world-building-quickstart.md` | `docs/` | 8KB | 快速开始指南 |
| `grill-world-bridge-guide.md` | `docs/` | 6KB | 桥接工具使用说明 |
| `grill-full-workflow-guide.md` | `docs/` | 5KB | 全流程衔接说明 |

### 新增脚本（1个）

| 脚本 | 路径 | 大小 | 用途 |
|------|------|------|------|
| `novel-team-start.sh` | `scripts/` | 4KB | 统一启动入口 |

### 更新文件（1个）

| 文件 | 变更 |
|------|------|
| `TEAM.md` | 注册新工具链（v2.2.0）、更新版本号 |

---

## 二、流程架构

```
Phase 1: grill-me 世界包追问
    ↓ DECISION-TREE.md（世界逻辑部分）
Phase 2: 交叉验证（第二模型）
Phase 3: 逻辑落地 → core-logic.md + iron-laws.md
    ↓
Phase 4a: grill-me 大纲追问
    ↓ DECISION-TREE.md（大纲结构部分）
Phase 4b: 卷细纲落地 → vol-001~005-brief.yaml
Phase 4c: 单章细纲生成 → ch-001~XXX-brief.md
    ↓
Phase 5: 正文创作（SOP C+）
Phase 6: 世界同步（world-sync.py）
Phase 7: 动态调整（outline-dynamic-adjust.py）
```

---

## 三、工具命令速查

### 世界包构建

```bash
# 启动追问
python3 tools/grill-world-bridge.py start --project helper-creator
# 或
python3 tools/world-logic-builder.py grill --project helper-creator

# 落地逻辑文件
python3 tools/grill-world-bridge.py build --project helper-creator
# 或
python3 tools/world-logic-builder.py build --project helper-creator

# 查看状态
python3 tools/world-logic-builder.py status --project helper-creator
```

### 大纲创作

```bash
# 启动大纲追问
python3 tools/outline-grill-bridge.py start --project helper-creator

# 落地卷细纲
python3 tools/outline-grill-bridge.py build --project helper-creator

# 查看大纲状态
python3 tools/outline-grill-bridge.py status --project helper-creator
```

### 细纲生成

```bash
# 生成第 N 章细纲
python3 tools/chapter-brief-generator.py --project helper-creator --chapter 1

# 批量生成第一卷全部细纲
python3 tools/chapter-brief-generator.py --project helper-creator --volume 1 --batch
```

### 动态调整

```bash
# 分析当前进度，生成调整建议
python3 tools/outline-dynamic-adjust.py analyze --project helper-creator

# 查看大纲状态
python3 tools/outline-dynamic-adjust.py status --project helper-creator
```

### 统一入口

```bash
# 启动世界包追问
bash scripts/novel-team-start.sh world

# 启动大纲追问
bash scripts/novel-team-start.sh outline

# 完整流程
bash scripts/novel-team-start.sh full

# 查看状态
bash scripts/novel-team-start.sh status
```

---

## 四、当前状态

### 已就绪 ✅

- [x] 5个新工具（语法检查通过）
- [x] 2个新模板
- [x] 4个新文档
- [x] 1个启动脚本
- [x] TEAM.md 注册更新
- [x] world-bible.md（已有）
- [x] world-pack.json（已有）
- [x] 角色档案 8个（已有）
- [x] 第一章正文（已有，3534字）

### 待落地 ⏳

- [ ] core-logic.md（Phase 3 产出）
- [ ] iron-laws.md（Phase 3 产出）
- [ ] DECISION-TREE.md（Phase 1+4a 产出）
- [ ] vol-001~005-brief.yaml（Phase 4b 产出）
- [ ] ch-001~030-brief.md（Phase 4c 产出）

### 待创作 ✍️

- [ ] 第1章重写（基于新世界逻辑）
- [ ] 第2~30章创作
- [ ] gate-check 门禁验证

---

## 五、关键设计原则

### 1. 路径分离

```
workspace/DECISION-TREE.md    ← 临时工作区（grill-me 写入）
projects/<id>/DECISION-TREE.md ← 持久化存储（bridge 复制）
```

### 2. 双向检查

```bash
# 检查决策树是否已同步
diff /var/minis/workspace/DECISION-TREE.md \
     /var/minis/shared/novel-team/novel-team/projects/helper-creator/DECISION-TREE.md
```

### 3. 版本纪律

- 每次追问追加版本记录，不覆盖旧版
- `build` 时检查版本号，确保不降级
- `core-logic.md` 每次更新版本号递增（v1.0 → v1.1 → v2.0）

---

## 六、下一步行动

### 立即执行（推荐顺序）

```bash
# 步骤1：启动世界包追问
bash scripts/novel-team-start.sh world

# 然后说 "grill me"，回答5个问题

# 步骤2：落地世界逻辑
python3 tools/grill-world-bridge.py build --project helper-creator

# 步骤3：启动大纲追问
bash scripts/novel-team-start.sh outline

# 然后说 "grill me"，回答5个问题

# 步骤4：落地大纲文件
python3 tools/outline-grill-bridge.py build --project helper-creator

# 步骤5：生成第一卷细纲
python3 tools/chapter-brief-generator.py --project helper-creator --volume 1 --batch

# 步骤6：开始创作
cat outline/ch-001-brief.md
# 按细纲创作正文
```

### 预期产出

| 文件 | 大小预估 | 用途 |
|------|---------|------|
| `core-logic.md` | ~5KB | 世界核心逻辑文档 |
| `iron-laws.md` | ~3KB | 铁律清单（对接 gate-check） |
| `vol-001-brief.yaml` | ~2KB | 第一卷细纲 |
| `ch-001-brief.md` | ~1KB | 第1章写作指令 |
| ... | ... | ... |
| `ch-030-brief.md` | ~1KB | 第30章写作指令 |

---

## 七、与现有工具的集成

### gate-check.py 新增检查项

| 铁律 ID | gate-check 插件 | 检查方式 |
|--------|----------------|---------|
| IL001 | fact_consistency | 境界匹配检查 |
| IL002 | fact_consistency | 同境界胜负合理性 |
| SL001 | protocol | 行为合理性检查 |
| SL002 | forbidden_words | 越级资源检测 |
| CL002 | hook | 金手指暴露风险 |
| PL001 | fact_consistency | 知情边界检查 |
| PL002 | discipline | 刻纹计数检查 |

### chapter-brief.md 字段映射

| 细纲字段 | 对应 gate-check 检查 |
|---------|-------------------|
| `世界包约束` | fact_consistency + forbidden_words |
| `写作禁忌` | discipline + protocol |
| `爽点层级` | hook（章末钩子有效性） |
| `信息揭示` | info_boundary（知情边界） |

---

**落地完成，等待用户确认启动追问。**
