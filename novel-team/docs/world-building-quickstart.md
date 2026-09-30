# 世界包驱动创作流程 — 快速开始

> 适用场景：新项目启动 / 已有项目世界观重建
> 前置条件：grill-me skill 已激活（当前会话自动可用）

---

## 一、完整执行流程

```
Phase 1          Phase 2         Phase 3         Phase 4         Phase 5
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ 逻辑追问 │────→│ 交叉验证 │────→│ 逻辑落地 │────→│ 细纲生成 │────→│ 正文创作 │
│ grill   │     │ 第二模型 │     │ 写文件  │     │ 每章指令 │     │ SOP C+  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘
    ↓               ↓               ↓               ↓               ↓
DECISION-     VALIDATION-    core-logic.md   ch-001-brief.md   gate-check
TREE.md       REPORT.md      iron-laws.md   ch-002-brief.md   PASS → 发布
                                                          ...
                                                          world-sync
                                                          scan → 同步
```

---

## 二、分步操作指南

### Step 1：执行 Phase 1（逻辑追问）

```bash
# 查看当前状态
python3 /var/minis/shared/novel-team/tools/world-logic-builder.py \
  --project helper-creator status

# 启动追问模式
python3 /var/minis/shared/novel-team/tools/world-logic-builder.py \
  --project helper-creator grill
```

**触发 grill-me**：在对话中说 `grill me` 或 `先追问我`

**追问领域**（见 `templates/world-question-bank.yaml`）：
1. **Q01 力量体系的代价** — 境界差距的根源和代价
2. **Q02 社会结构的根源** — 阶层流动的限制与突破
3. **Q03 核心矛盾的发动机** — 冲突根源与各方立场
4. **Q04 主角的特殊性** — 为什么是林辰
5. **Q05 第一卷具体任务** — 可执行的短期目标

**追问纪律**：
- 每个问题等用户回答后再问下一个
- 每个回答后追问"为什么"，直到触及根源
- 记录所有回答到 `DECISION-TREE.md`
- 用户说"你决定"时停止追问

---

### Step 2：执行 Phase 2（交叉验证）

追问完成后，手动触发第二模型审查：

```bash
# 方式一：自动触发（在对话中说"交叉验证"）
# 方式二：手动用第二模型审 DECISION-TREE.md

minis-model-use run --model glm-5.2 \
  --system "你是世界包逻辑审查员。读以下决策树，找出：①内部矛盾 ②与world-bible.md冲突 ③未覆盖的边条件 ④不可执行的答案。输出问题清单，标注严重程度。" \
  --input <(cat /var/minis/shared/novel-team/novel-team/projects/helper-creator/DECISION-TREE.md)
```

**审查维度**：
| 维度 | 检查内容 | 严重度 |
|------|---------|--------|
| 内部一致性 | 铁律之间是否矛盾 | [严重] |
| 世界包一致性 | 新逻辑是否与 bible 冲突 | [严重] |
| 边条件覆盖 | 是否考虑了边界情况 | [中等] |
| 可执行性 | 答案能否转化为创作指令 | [中等] |

---

### Step 3：执行 Phase 3（逻辑落地）

```bash
# 将决策树答案写入逻辑文件
python3 /var/minis/shared/novel-team/tools/world-logic-builder.py \
  --project helper-creator build
```

**产出文件**：
```
projects/helper-creator/world/
├── core-logic.md       ← 核心逻辑文档（新增）
└── iron-laws.md        ← 铁律清单（新增）
```

**落地后验证**：
```bash
python3 /var/minis/shared/novel-team/tools/world-logic-builder.py \
  --project helper-creator status
```

---

### Step 4：执行 Phase 4（细纲生成）

**先填卷级细纲模板**（手动编辑或使用 AI 辅助）：

```yaml
# projects/helper-creator/outline/vol-001-brief.yaml
volume:
  id: vol-001
  title: "初露锋芒"
  chapter_range: [1, 30]
  core_task:
    goal: "完成筑基丹炼制任务，通过外门弟子考核"
    requester: "孙鹤（丹房管事）"
    deadline: "Ch15 前"
    success: "成功炼制筑基丹 + 通过考核"
    failure: "被逐出天机阁"

  thrill_schedule:
    - ch: 1-3; target: L2; design: "展示能力但不暴露"
    - ch: 5;  target: L2; design: "暗中解决丹房危机"
    - ch: 10; target: L3; design: "宗门测试一鸣惊人"
    - ch: 15; target: L3; design: "完成筑基丹任务"
    - ch: 20; target: L2; design: "阁主开始观察"
    - ch: 30; target: L4; design: "阁主暗示异常"

  chapters:
    - chapter: 1
      title: "第三处节点"
      scene: "丹房夜巡"
      characters: ["林辰", "张明德", "陆鸣"]
      conflict: "第七号炉火候失控，林辰指出问题但被嘲笑"
      thrill_level: L1
      info_reveal: "林辰能看出火候问题，有特殊能力"
      hook: "匣身纹路忽然亮了一下——有人来了"
```

**然后批量生成细纲**：
```bash
python3 /var/minis/shared/novel-team/tools/chapter-brief-generator.py \
  --project helper-creator --volume 1 --batch
```

---

### Step 5：执行 Phase 5（正文创作）

```bash
# 读取第 N 章细纲
cat projects/helper-creator/outline/ch-00{N}-brief.md

# 按细纲创作正文
# （用创作提示词 + 细纲内容 → 生成正文）

# 门禁检查
python3 tools/gate-check.py check --chapter {N} \
  --file projects/helper-creator/chapters/ch{N:03d}.md
```

---

### Step 6：执行 Phase 6（世界同步）

```bash
# gate-check PASS 后自动触发
python3 tools/world-sync.py --novel-id helper-creator scan
python3 tools/world-sync.py --novel-id helper-creator list
# 人工 approve/reject
```

---

## 三、关键约束

### 顺序约束（不可跳步）
```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
   ↑                                    ↓
   └──────── 每章回看 core-logic ────────┘
```

**跳过 Phase 1-3 直接写正文 = 回到之前的失败模式**

### 版本纪律
| 文件 | 更新时机 | 版本规则 |
|------|---------|---------|
| `core-logic.md` | Phase 3 每次落地 | v1.0 → v1.1 → v2.0 |
| `DECISION-TREE.md` | Phase 1 每次追问 | 追加版（不覆盖） |
| `iron-laws.md` | Phase 3 每次落地 | 与 core-logic 同步 |
| `ch-{N}-brief.md` | Phase 4 每次生成 | 按章节号递增 |

### 迭代纪律
- 每写完一章细纲 → 回看 `core-logic.md` → 补充缺失逻辑
- 每写完一章正文 → 运行 `world-sync.py scan` → 提取新实体
- 发现逻辑矛盾 → 回退到 Phase 2 重新验证

---

## 四、工具速查

| 命令 | 用途 |
|------|------|
| `world-logic-builder.py --project X status` | 查看逻辑状态 |
| `world-logic-builder.py --project X grill` | 启动追问 |
| `world-logic-builder.py --project X build` | 落地逻辑文件 |
| `chapter-brief-generator.py --project X --chapter N` | 生成第 N 章细纲 |
| `chapter-brief-generator.py --project X --volume N --batch` | 批量生成整卷细纲 |
| `world-sync.py --novel-id X scan` | 世界包同步 |

---

## 五、当前状态（helper-creator）

```
✅ world-bible.md       7227B  骨架层
✅ core-concept.md      990B   核心概念
✅ world-pack.json      4740B  结构化数据
✅ 角色档案             8 个
❌ core-logic.md        不存在  ← Phase 3 待产出
❌ iron-laws.md         不存在  ← Phase 3 待产出
❌ DECISION-TREE.md     不存在  ← Phase 1 待产出
❌ vol-001-brief.yaml   不存在  ← Phase 4 待填
❌ ch-*-brief.md        0 个    ← Phase 4 待生成
```

**下一步**：执行 `world-logic-builder.py --project helper-creator grill`，然后说 `grill me`。
