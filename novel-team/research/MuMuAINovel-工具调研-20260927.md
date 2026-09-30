# MuMuAINovel 工具调研报告

> 调研时间：2026-09-27
> 来源：https://github.com/xiamuceer-j/MuMuAINovel
> Stars：3082 / Forks：596 / 语言：Python
> 状态：v1.5.6（2025-10-30创建，2026-09-18最后推送）
> License：GPL-3.0

---

## 一、工具概述

### 1.1 基本信息

| 项目 | 内容 |
|------|------|
| 名称 | MuMuAINovel |
| 定位 | 基于 AI 的智能小说创作助手 |
| 技术栈 | FastAPI + React + PostgreSQL + ChromaDB |
| Stars | 3082 ⭐ |
| Forks | 596 |
| 创建时间 | 2025-10-30 |
| 最后推送 | 2026-09-18 |
| License | GPL-3.0 |

### 1.2 核心特色

1. **多AI模型支持**：OpenAI、Gemini、Claude等主流模型
2. **智能向导**：AI自动生成大纲、角色和世界观
3. **角色管理**：人物关系、组织架构可视化管理
4. **章节编辑**：支持创建、编辑、重新生成和润色
5. **世界观设定**：构建完整的故事背景
6. **伏笔管理**：智能追踪剧情伏笔，提醒未回收线索
7. **长期记忆**：基于ChromaDB的向量记忆系统
8. **MCP集成**：Model Context Protocol插件系统

---

## 二、架构设计

### 2.1 技术栈

```
前端：React 18 + Vite
后端：FastAPI + SQLAlchemy (Async)
数据库：PostgreSQL（生产）/ SQLite（开发）
向量库：ChromaDB
Embedding：ONNX (paraphrase-multilingual-MiniLM-L12-v2)
部署：Docker Compose
```

### 2.2 核心模块

| 模块 | 文件 | 功能 |
|------|------|------|
| AI服务 | `services/ai_service.py` | 统一AI接口，支持多provider |
| 记忆服务 | `services/memory_service.py` | 向量记忆，语义检索 |
| 伏笔服务 | `services/foreshadow_service.py` | 伏笔埋设/回收管理 |
| 剧情分析 | `services/plot_analyzer.py` | 章节钩子/冲突/伏笔分析 |
| 章节上下文 | `services/chapter_context_service.py` | RTCO框架智能上下文构建 |
| 职业系统 | `services/career_service.py` | 修仙境界/魔法等级等体系 |
| MCP服务 | `services/mcp_tools_loader.py` | MCP插件加载和执行 |

### 2.3 数据模型

```
Project（项目）→ Outline（大纲）→ Chapter（章节）
    ↓              ↓              ↓
Character（角色）Career（职业）GenerationHistory（生成历史）
    ↓
Relationship（关系）→ Organization（组织）
    ↓
StoryMemory（故事记忆）→ PlotAnalysis（剧情分析）
    ↓
Foreshadow（伏笔）
```

---

## 三、核心创新

### 3.1 RTCO框架（章节上下文构建）

```python
# 章节上下文构建服务核心逻辑
def build_chapter_context(chapter_id, prev_chapters, project):
    """
    RTCO = Relevant Text + Character Options
    
    构建原则：
    1. 只取相关的，不取全部的
    2. 按相似度筛选记忆
    3. 兜底保留top结果
    """
    # 1. 获取前N章内容
    prev_content = get_previous_chapters(prev_count=5)
    
    # 2. 语义检索相关记忆
    memories = memory_service.retrieve(
        query=chapter_outline,
        threshold=0.7,
        fallback_count=3
    )
    
    # 3. 角色状态注入
    characters = get_character_states()
    
    # 4. 伏笔检查
    foreshadows = foreshadow_service.get_active()
    
    return {
        "prev_content": prev_content,
        "memories": memories,
        "characters": characters,
        "foreshadows": foreshadows,
    }
```

### 3.2 伏笔管理系统

```python
class ForeshadowService:
    """伏笔管理服务"""
    
    async def plant_foreshadow(self, chapter_id, content, category):
        """埋设伏笔"""
        # 生成稳定ID：chapter_id + content_hash
        foreshadow_id = generate_stable_id(chapter_id, content)
        
        # 存入数据库
        await db.insert(Foreshadow(...))
        
        # 更新向量记忆
        await memory_service.add_memory(
            content=content,
            memory_type="foreshadow",
            metadata={"chapter": chapter_id}
        )
    
    async def check_recall(self, chapter_id):
        """检查伏笔回收"""
        # 语义匹配已埋设的伏笔
        matched = await self.semantic_match(chapter_id)
        
        # 更新状态
        for m in matched:
            if m["confidence"] > 0.8:
                await self.mark_recalled(m["id"])
```

### 3.3 向量记忆系统

```python
class MemoryService:
    """向量记忆服务"""
    
    def __init__(self):
        # ChromaDB持久化客户端
        self.client = chromadb.PersistentClient(path="data/chroma_db")
        # ONNX Embedding模型
        self.embedding_model = OnnxEmbeddingModel()
    
    async def add_memory(self, user_id, project_id, memory_id, content, memory_type, metadata):
        """添加记忆"""
        collection = self.get_collection(user_id, project_id)
        
        # 生成向量
        embedding = self.embedding_model.encode(content)
        
        # 存入ChromaDB
        collection.add(
            ids=[memory_id],
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata]
        )
    
    async def retrieve(self, query, top_k=5, threshold=0.7):
        """语义检索"""
        collection = self.get_collection(user_id, project_id)
        
        # 查询向量
        results = collection.query(
            query_embeddings=[self.embedding_model.encode(query)],
            n_results=top_k,
            where=filter_conditions
        )
        
        # 过滤低相似度结果
        return [r for r in results if r["similarity"] > threshold]
```

### 3.4 多Provider统一接口

```python
class AIService:
    """AI服务统一接口"""
    
    def __init__(self, provider="openai", **kwargs):
        self.provider = self._get_provider(provider)
    
    def _get_provider(self, name):
        providers = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "gemini": GeminiProvider,
        }
        return providers[name](**kwargs)
    
    async def generate_text(self, prompt, **kwargs):
        """统一生成接口"""
        return await self.provider.generate(prompt, **kwargs)
    
    async def stream_generate(self, prompt, **kwargs):
        """流式生成接口"""
        async for chunk in self.provider.stream(prompt, **kwargs):
            yield chunk
```

### 3.5 MCP插件系统

```python
class MCPToolsLoader:
    """MCP工具加载器"""
    
    async def load_tools(self, user_id):
        """加载用户启用的MCP插件工具"""
        plugins = await self.get_user_plugins(user_id)
        enabled_plugins = [p for p in plugins if p.enabled]
        
        tools = []
        for plugin in enabled_plugins:
            plugin_tools = await self.load_plugin_tools(plugin)
            tools.extend(plugin_tools)
        
        return tools
```

---

## 四、与小说团队的关联

### 4.1 可借鉴功能

| 功能 | 借鉴价值 | 实现难度 |
|------|---------|---------|
| **伏笔管理系统** | ⭐⭐⭐⭐⭐ | 中（需开发foreshadow服务）|
| **向量记忆系统** | ⭐⭐⭐⭐⭐ | 中（需集成ChromaDB）|
| **RTCO框架** | ⭐⭐⭐⭐ | 高（需重构上下文构建）|
| **剧情分析服务** | ⭐⭐⭐⭐ | 中（可借鉴prompt设计）|
| **职业等级体系** | ⭐⭐⭐ | 低（可扩展类型系统）|
| **多Provider接口** | ⭐⭐⭐ | 低（已有router）|
| **MCP插件系统** | ⭐⭐⭐ | 高（需评估必要性）|

### 4.2 iSH可行性

| 维度 | 评估 | 说明 |
|------|------|------|
| Python后端 | ⚠️ 部分可行 | FastAPI+PostgreSQL需在服务器部署 |
| 向量记忆 | ⚠️ 部分可行 | ChromaDB可跑，但需评估资源 |
| MCP系统 | ❌ 不可行 | 依赖外部协议 |
| 前端界面 | ❌ 不可行 | React需浏览器环境 |
| 核心服务 | ✅ 可借鉴 | 服务逻辑可移植到Python脚本 |

### 4.3 建议行动

#### P0（立即执行）
1. **借鉴伏笔管理系统**
   - 开发foreshadow-service.py
   - 支持伏笔埋设/回收/检查
   - 集成到context-manager

2. **借鉴向量记忆思路**
   - 评估是否集成ChromaDB
   - 或开发简化版语义检索
   - 扩展fact-ledger支持语义搜索

3. **借鉴RTCO框架**
   - 重构context-manager.py
   - 实现"只取相关，不取全部"原则
   - 添加相似度筛选和兜底机制

#### P1（近期规划）
4. **开发剧情分析服务**
   - 借鉴plot_analyzer.py的prompt设计
   - 自动识别钩子/冲突/伏笔
   - 集成到humanizer-check

5. **扩展职业等级体系**
   - 在genre-system基础上增加职业体系
   - 支持修仙境界/魔法等级/技能树

6. **开发多Provider统一接口**
   - 抽象AI服务接口
   - 支持动态切换Provider
   - 统一错误处理和重试

#### P2（长期规划）
7. **评估完整部署**
   - 如需GUI，考虑Electron打包
   - 或开发Web版本（FastAPI+React）
   - Docker Compose一键部署

---

## 五、与其他工具对比

| 维度 | 91Writing | StoryForge | Novel-Creator | Long-Novel-GPT | AI-Novel-Writer | Casting-Workflow | NovelCraft | ai-novel-writer v6 | MuMuAINovel |
|------|-----------|------------|---------------|----------------|-----------------|------------------|------------|---------------------|-------------|
| Stars | 1601⭐ | 780⭐ | 657⭐ | 1239⭐ | 1135⭐ | 611⭐ | 0⭐ | 5⭐ | **3082⭐** |
| 类型 | Web应用 | Web应用 | CLI工具 | Web应用 | 桌面应用 | CLI管道 | Skill | CLI工具 | **全栈Web** |
| 核心 | 提示词模板 | 记忆系统 | 五层一致性 | 三阶段创作 | 可控工作流 | 指纹蒸馏 | 极简创作 | 世界模拟 | **完整创作平台** |
| 特色 | 流程设计 | 版本保护 | 知识图谱 | 成本跟踪 | 系统合同 | 100%原创 | 人格系统 | 四道防线 | **伏笔+记忆+MCP** |
| iSH可行 | ❌ | ❌ | ⚠️ 部分 | ⚠️ 部分 | ❌ | ✅ 完全 | ✅ 完全 | ✅ 完全 | ⚠️ 部分 |
| 工程规模 | 中 | 大 | 中 | 中 | 大 | 小 | 小 | 中 | **大** |

---

## 六、关键发现

### 6.1 伏笔管理的工程化

MuMuAINovel的伏笔系统是同类工具中**最工程化**的实现：
- 稳定ID生成（chapter_id + content_hash）
- 语义匹配回收（相似度阈值）
- 时间线可视化
- 未回收提醒

### 6.2 向量记忆的价值

> "角色的行动依据是认知不是事实。"

MuMuAINovel用ChromaDB实现了：
- 章节内容向量化存储
- 语义检索相关记忆
- 相似度阈值过滤
- 兜底保留top结果

### 6.3 RTCO框架的设计哲学

```
Relevant Text + Character Options

原则：
1. 只取相关的，不取全部的
2. 按相似度筛选
3. 无高分命中时降级保留
```

这与我们之前的"低上下文策略"不谋而合。

### 6.4 多Provider的统一抽象

```python
# 统一接口，底层切换
ai_service = AIService(provider="openai", model="gpt-4o")
ai_service = AIService(provider="anthropic", model="claude-sonnet-4-20250514")
ai_service = AIService(provider="gemini", model="gemini-2.0-flash")
```

---

## 七、结论与建议

### 7.1 核心价值

MuMuAINovel是一个**工程化程度极高、功能完整**的全栈Web创作平台。其伏笔管理系统和向量记忆系统是同类工具中最成熟的实现。

### 7.2 与小说团队的关系

| 维度 | 评估 |
|------|------|
| **可运行** | ⚠️ 部分可行（FastAPI+PostgreSQL需服务器）|
| **可借鉴** | ✅ 高度可借鉴（伏笔+记忆+RTCO）|
| **可复用** | ⚠️ 部分可复用（核心服务逻辑）|

### 7.3 推荐集成路径

1. **短期**：借鉴伏笔管理系统，开发foreshadow-service.py
2. **中期**：实现RTCO框架，重构context-manager
3. **长期**：评估完整部署方案（Web GUI或CLI增强版）

---

## 八、行动建议

### P0 立即执行
1. 开发foreshadow-service.py（伏笔管理）
2. 扩展context-manager支持RTCO框架
3. 集成向量检索思路到fact-ledger

### P1 近期规划
4. 开发plot-analyzer.py（剧情分析）
5. 扩展genre-system支持职业等级
6. 抽象多Provider统一接口

### P2 长期规划
7. 评估完整部署方案
8. 开发Web GUI或增强CLI

---

**报告生成时间**：2026-09-27
**数据来源**：GitHub仓库、README、源代码
**本地路径**：`/var/minis/shared/MuMuAINovel/`（克隆失败，通过API获取）
**报告路径**：`novel-team/research/MuMuAINovel-工具调研-20260927.md`
