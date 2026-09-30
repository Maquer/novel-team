# grill-me 全流程承接说明

> 适用场景：世界包构建 + 大纲创作
> 版本：v1.0 | 2026-09-30

---

## 一、grill-me 在整个流程中的位置

```
Phase 1: 世界包核心逻辑追问（grill-me）
    ↓ DECISION-TREE.md（世界逻辑部分）
Phase 2: 交叉验证
Phase 3: 逻辑落地（core-logic.md + iron-laws.md）

Phase 4a: 大纲结构追问（grill-me）← 新增
    ↓ DECISION-TREE.md（大纲结构部分）
Phase 4b: 卷细纲落地（vol-001-brief.yaml ~ vol-005-brief.yaml）
Phase 4c: 单章细纲生成（ch-001-brief.md ~ ch-XXX-brief.md）

Phase 5: 正文创作（SOP C+）
Phase 6: 世界同步（world-sync.py）
Phase 7: 动态调整（outline-dynamic-adjust.py）
```

**关键设计**：
- `DECISION-TREE.md` 是全局共享文件，包含世界逻辑 + 大纲结构两部分
- 两个 bridge 工具分别负责不同阶段的衔接

---

## 二、工具衔接链

| 阶段 | grill-me 输出 | bridge 工具 | 落地文件 |
|------|-------------|------------|---------|
| Phase 1 | DECISION-TREE.md（世界逻辑） | `grill-world-bridge.py` | `core-logic.md` + `iron-laws.md` |
| Phase 4a | DECISION-TREE.md（大纲结构） | `outline-grill-bridge.py` | `vol-00*-brief.yaml` |

**共同点**：
- 都读 `workspace/DECISION-TREE.md`
- 都写 `projects/<id>/` 下的文件
- 都在 grill-me 追问完成后执行 `build` 命令

---

## 三、完整工作流

### 步骤 1：启动世界包追问

```bash
python3 tools/grill-world-bridge.py start --project helper-creator
```

然后在对话中说 `grill me`，回答 5 个世界逻辑问题。

### 步骤 2：落地世界逻辑

```bash
python3 tools/grill-world-bridge.py build --project helper-creator
```

产出：
- `world/core-logic.md`
- `world/iron-laws.md`

### 步骤 3：启动大纲追问

```bash
python3 tools/outline-grill-bridge.py start --project helper-creator
```

然后在对话中说 `grill me`，回答 5 个大纲结构问题。

### 步骤 4：落地大纲文件

```bash
python3 tools/outline-grill-bridge.py build --project helper-creator
```

产出：
- `outline/vol-001-brief.yaml`
- `outline/vol-002-brief.yaml`
- ...
- `outline/vol-005-brief.yaml`

### 步骤 5：生成单章细纲

```bash
python3 tools/chapter-brief-generator.py --project helper-creator --volume 1 --batch
```

产出：
- `outline/ch-001-brief.md`
- `outline/ch-002-brief.md`
- ...
- `outline/ch-030-brief.md`

### 步骤 6：开始创作

```bash
# 读取第1章细纲
cat outline/ch-001-brief.md

# 按细纲创作正文（使用创作提示词）
# ...

# 门禁检查
python3 tools/gate-check.py check --chapter 1 --file chapters/ch001.md
```

---

## 四、DECISION-TREE.md 格式规范

grill-me 输出的决策树必须包含以下两个部分：

```markdown
## 世界逻辑追问

### Q01：力量体系的代价
- **Q**: {问题}
- **A**: {用户回答}
- **Status**: ✅ RESOLVED

### Q02：社会结构的根源
...

## 大纲结构追问

### OQ01：五卷结构
- **Q**: {问题}
- **A**: {用户回答}
- **Status**: ✅ RESOLVED

### OQ02：章节数分配
...
```

**两个 bridge 工具分别读取不同部分**：
- `grill-world-bridge.py` → 读取 `## 世界逻辑追问` 部分
- `outline-grill-bridge.py` → 读取 `## 大纲结构追问` 部分

---

## 五、关键设计原则

### 1. 路径分离（不混用）
```
workspace/DECISION-TREE.md     ← 临时工作区（grill-me 写入）
projects/<id>/DECISION-TREE.md ← 持久化存储（bridge 复制）
```

### 2. 双向检查（防丢失）
```bash
# 检查决策树是否已同步
diff /var/minis/workspace/DECISION-TREE.md \
     /var/minis/shared/novel-team/novel-team/projects/helper-creator/DECISION-TREE.md
```

### 3. 版本纪律（可追溯）
- 每次追问追加版本记录，不覆盖旧版
- `build` 时检查版本号，确保不降级

---

## 六、常见问题

### Q：grill-me 追问完世界逻辑后，能直接追问大纲结构吗？
**A**：可以。grill-me 会追问所有未解决的问题（包括世界逻辑和大纲结构）。两个 bridge 工具分别从决策树中提取对应部分。

### Q：如果追问过程中改变了主意怎么办？
**A**：在决策树中标记为 `❓ UNRESOLVED`，后续继续追问直到 `✅ RESOLVED`。`build` 时会跳过未解决的问题。

### Q：大纲追问和世界包追问能合并吗？
**A**：建议分开。世界包追问关注"为什么"，大纲追问关注"怎么做"。分开追问更清晰，便于回溯。

---

## 七、下一步行动

```bash
# 查看当前状态
python3 tools/grill-world-bridge.py status --project helper-creator
python3 tools/outline-grill-bridge.py status --project helper-creator

# 启动追问（先世界包，后大纲）
python3 tools/grill-world-bridge.py start --project helper-creator
# 然后说 "grill me"

python3 tools/outline-grill-bridge.py start --project helper-creator
# 然后说 "grill me"
```
