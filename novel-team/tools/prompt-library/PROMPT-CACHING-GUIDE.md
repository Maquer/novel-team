# 小说团队 · 提示词库（Prompt Caching优化版）

> 基于Long-Novel-GPT多轮注入模式优化

---

## 设计原则

### 1. 多轮注入（Prompt Caching）
将固定内容拆分为多轮对话，让LLM缓存固定部分：
```
第1轮：小说简介（固定）→ 缓存
第2轮：核心设定（固定）→ 缓存
第3轮：上下文（动态）
第4轮：当前任务（动态）
```

### 2. 变量替换
使用 `{variable}` 格式，运行时替换：
- `{summary}` - 小说简介
- `{world_setting}` - 世界观设定
- `{character_setting}` - 主角设定
- `{context}` - 前后章节上下文
- `{chapter_outline}` - 本章大纲
- `{draft_chapter}` - 待扩写章节
- `{expanded_chapter}` - 待精修章节

---

## 模板列表

### 大纲创作模板

**文件**：`categories/outline-context.yaml`

```yaml
# 多轮注入模式
user:
下面是**小说简介**。

**小说简介**
{summary}

assistant:
收到，我会参考小说简介进行创作。

user:
下面是**核心设定**。

**核心设定**
- 世界背景：{world_background}
- 力量体系：{power_system}
- 主要势力：{factions}

assistant:
收到，我会参考核心设定进行创作。

user:
下面是**主角设定**。

**主角设定**
- 姓名：{protagonist_name}
- 性格：{personality}
- 金手指：{golden_finger}

assistant:
收到，我会参考主角设定进行创作。

user:
请创作完整大纲。

**要求**
- 至少50章
- 每章有章节名、核心事件、爽点/钩子
- 标注伏笔和转折点
- 主角成长路线清晰

assistant:
开始创作大纲...
```

### 章节创作模板

**文件**：`categories/chapter-context.yaml`

```yaml
# 多轮注入模式
user:
下面是**小说简介**。
{summary}

assistant:
收到。

user:
下面是**前后章节上下文**。

**前章结尾**
{previous_ending}

**后章大纲**
{next_outline}

assistant:
收到，我会考虑到和前后章节的连贯。

user:
下面是**本章大纲**。

**章节名**
{chapter_name}

**核心事件**
{core_event}

**爽点/钩子**
{hook}

assistant:
收到，我会根据大纲进行创作。

user:
请创作本章初稿。

**要求**
- 字数：300-500字
- 开篇钩子
- 结尾悬念
- 无AI味

assistant:
开始创作...
```

### 剧情扩写模板

**文件**：`categories/expand-context.yaml`

```yaml
# 多轮注入模式
user:
下面是**小说简介**。
{summary}

assistant:
收到。

user:
下面是**上下文**。
{context}

assistant:
收到。

user:
下面是**待扩写章节**。
{draft_chapter}

assistant:
收到。

user:
请扩写本章，要求：
1. 保持原有情节
2. 增加细节描写（环境、动作、心理、对话）
3. 字数扩充到1000-1500字
4. 去除AI味

assistant:
开始扩写...
```

### 正文精修模板

**文件**：`categories/polish-context.yaml`

```yaml
# 多轮注入模式
user:
下面是**待精修正文**。
{expanded_chapter}

assistant:
收到。

user:
请执行两遍式润色：

**第一遍：清除AI模式**
- 删除"不禁/仿佛/映入眼帘"等套话
- 用具体行动替代抽象描述
- 删除过度比喻

**第二遍：审查剩余AI味**
问自己："这段文字哪些地方还是明显AI生成的感觉？"
列出3-5条具体问题，再次修改。

assistant:
开始精修...
```

### 审阅模板

**文件**：`categories/review-context.yaml`

```yaml
system:
现在你是一个网文主编，正在审稿。

在审稿时，由于作者只提交了一个正文片段，所以只评判该片段的格式、文笔、画面感，不评判结构和情节。

考虑角度：
1. 场景描写是否够具体？是否有画面感。
2. 人物刻画如何？是否有外貌、动作、心理、语言等细节描写。
3. 对话是否自然？是否贴合人物性格。
4. 节奏是否合理？是否有拖沓或仓促。

user:
下面是待审阅章节。
{chapter_text}

assistant:
开始审阅...
```

---

## 使用方法

### 1. 构建上下文
```bash
python tools/context-manager.py build --project-id my-novel
```

### 2. 生成Prompt
```bash
# 章节创作
python tools/context-manager.py generate \
  --project-id my-novel \
  --chapter 1 \
  --mode draft \
  --output chapter-1-prompt.txt

# 剧情扩写
python tools/context-manager.py generate \
  --project-id my-novel \
  --chapter 1 \
  --mode expand

# 正文精修
python tools/context-manager.py generate \
  --project-id my-novel \
  --chapter 1 \
  --mode polish
```

### 3. 查看状态
```bash
python tools/context-manager.py status --project-id my-novel
```

### 4. 估算成本
```bash
python tools/context-manager.py estimate --project-id my-novel
```

---

## Prompt Caching优化技巧

### 1. 固定内容前置
将不变化的内容（简介、设定）放在前面，让LLM缓存。

### 2. 分段注入
每次只注入一个新信息块，让LLM逐步构建上下文。

### 3. 确认回应
每个注入后等待LLM确认（"收到"），确保缓存生效。

### 4. 控制长度
单轮注入不超过2000字符，避免缓存失效。

---

## 版本

- v1.0.0 (2026-09-27) - 基于Long-Novel-GPT多轮注入模式重构
