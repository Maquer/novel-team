# grill-me 与 world-logic-builder 衔接说明

> 问题：grill-me 是会话行为模式，world-logic-builder 是文件工具，两者如何衔接？

---

## 一、核心矛盾

| 组件 | 运行环境 | 输出位置 | 输入位置 |
|------|---------|---------|---------|
| `grill-me` skill | 当前会话 | `/var/minis/workspace/DECISION-TREE.md` | ❌ 无 |
| `world-logic-builder.py` | iSH 终端 | — | `projects/<id>/DECISION-TREE.md` |
| `chapter-brief-generator.py` | iSH 终端 | — | `projects/<id>/core-logic.md` |

**问题**：grill-me 的决策树在 workspace，但逻辑落地工具在项目目录下读。

---

## 二、衔接方案：三层桥梁

### 方案 A：手动衔接（最简）

```bash
# Step 1: 在对话中说 "grill me"，追问 5 个领域
# grill-me 会把决策树写到 /var/minis/workspace/DECISION-TREE.md

# Step 2: 复制决策树到项目目录
cp /var/minis/workspace/DECISION-TREE.md \
   /var/minis/shared/novel-team/novel-team/projects/helper-creator/DECISION-TREE.md

# Step 3: 落地逻辑文件
python3 tools/world-logic-builder.py --project helper-creator build
```

### 方案 B：桥接脚本（推荐）

```bash
# 启动追问
python3 tools/grill-world-bridge.py start --project helper-creator

# 在对话中说 "grill me"，追问完成后：
python3 tools/grill-world-bridge.py build --project helper-creator

# 或一步到位
python3 tools/grill-world-bridge.py run --project helper-creator
```

**bridge 脚本做了什么**：
1. `start`：打印追问指引，提示用户激活 grill-me
2. `build`：自动复制 `workspace/DECISION-TREE.md` → 项目目录，然后调用 `world-logic-builder.py build`
3. `run`：组合 start + 提示用户主动执行 grill-me

### 方案 C：自动衔接（需修改 grill-me skill）

在 grill-me 的 Act 1 输出时，同时写入两个位置：

```python
# DECISION-TREE.md 写入逻辑（grill-me 修改）
workspace_tree = Path("/var/minis/workspace/DECISION-TREE.md")
project_tree = Path(f"/var/minis/shared/novel-team/novel-team/projects/{PROJECT_ID}/DECISION-TREE.md")

# 双写
workspace_tree.write_text(content, encoding="utf-8")
project_tree.parent.mkdir(parents=True, exist_ok=True)
project_tree.write_text(content, encoding="utf-8")
```

**问题**：grill-me 不知道当前项目 ID（helper-creator？my-novel？还是新项目？）。

---

## 三、推荐使用方案 B（桥接脚本）

### 完整工作流

```
┌─────────────────────────────────────────────────────────────────────┐
│                        世界包构建全流程                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ① 终端：启动桥接脚本                                               │
│     $ python3 tools/grill-world-bridge.py start --project helper-creator
│                                                                     │
│  ② 对话：激活 grill-me                                              │
│     用户：grill me                                                  │
│     小蒋：🍳 进入 Grill-Me 模式                                      │
│           先搞清楚再动手。关于《辅助之道》世界包，我有个问题：        │
│           Q1: 林辰是杂役，为什么只能待在丹房？                       │
│                                                                     │
│  ③ 对话：用户回答 5 个领域的追问                                    │
│     （每个回答后追问"为什么"，直到触及根源）                        │
│                                                                     │
│  ④ 对话：追问完成                                                   │
│     小蒋：DECISION-TREE.md 已写入 /var/minis/workspace/             │
│                                                                     │
│  ⑤ 终端：落地逻辑文件                                               │
│     $ python3 tools/grill-world-bridge.py build --project helper-creator
│     ✅ 已复制到项目目录                                             │
│     ✅ 已写入 core-logic.md                                         │
│     ✅ 已写入 iron-laws.md                                          │
│                                                                     │
│  ⑥ 终端：生成细纲                                                   │
│     $ python3 tools/chapter-brief-generator.py --project helper-creator --volume 1 --batch
│     ✅ 已生成 ch-001-brief.md ~ ch-030-brief.md                     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 四、文件位置对照

| 文件 | workspace | 项目目录 | 用途 |
|------|-----------|---------|------|
| `DECISION-TREE.md` | ✅ 写入 | ✅ bridge 复制 | 追问记录 |
| `core-logic.md` | ❌ | ✅ 落地 | 核心逻辑文档 |
| `iron-laws.md` | ❌ | ✅ 落地 | 铁律清单 |
| `ch-{N}-brief.md` | ❌ | ✅ 生成 | 单章写作指令 |
| `vol-001-brief.yaml` | ❌ | 手动填写 | 卷级细纲 |

---

## 五、关键设计原则

### 1. 路径分离（不混用）
- `workspace/`：临时工作区，会话内使用
- `projects/<id>/`：持久化存储，项目级使用
- bridge 脚本负责两者的同步

### 2. 双向检查（防丢失）
```bash
# 检查决策树是否已同步
diff /var/minis/workspace/DECISION-TREE.md \
     /var/minis/shared/novel-team/novel-team/projects/helper-creator/DECISION-TREE.md
```

### 3. 版本纪律
- 每次追问追加版本记录，不覆盖旧版
- `build` 时检查版本号，确保不降级

---

## 六、下一步

```bash
# 启动追问
python3 tools/grill-world-bridge.py start --project helper-creator

# 然后说 "grill me"
```

要现在启动吗？
