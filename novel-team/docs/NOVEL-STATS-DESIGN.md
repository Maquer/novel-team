# 创作统计模块 · 设计文档

> 扩展 countdown-scheduler.py 实现小说创作全流程统计

---

## 一、设计目标

1. **轻量级**：复用现有调度器架构，无需独立服务
2. **持久化**：数据存储在`.scheduler/`目录，会话启动后可恢复
3. **易记录**：单条命令记录创作活动
4. **可追踪**：支持项目级和时间维度统计

---

## 二、数据模型

### 2.1 小说项目 (`novel-projects.json`)

```json
{
  "projects": [
    {
      "id": "477a528a",
      "name": "小说名称",
      "genre": "玄幻",
      "platform": "起点",
      "target_words": 100000,
      "current_words": 3500,
      "status": "active",
      "created_at": "2026-09-27T07:23:21+08:00",
      "project_dir": "/var/minis/shared/novel-team/projects/小说名称",
      "chapters": [],
      "last_update": "2026-09-27T07:25:00+08:00"
    }
  ],
  "created_at": "2026-09-27T07:23:21+08:00"
}
```

### 2.2 创作日志 (`novel-log.json`)

```json
{
  "entries": [
    {
      "id": "a1b2c3d4",
      "project_id": "477a528a",
      "action": "write",
      "words": 2000,
      "chapter": "1",
      "note": "第一章开篇",
      "timestamp": "2026-09-27T07:24:00+08:00"
    }
  ],
  "created_at": "2026-09-27T07:23:21+08:00"
}
```

---

## 三、命令接口

### 3.1 novel list
列出所有小说项目

```bash
python3 /var/minis/shared/countdown-scheduler.py novel list
```

输出：
```
ID           名称                   类型         字数         状态       创建时间
--------------------------------------------------------------------------------
477a528a     测试小说                 玄幻         0          ✅        2026-09-27

总计 1 个项目
```

### 3.2 novel add
添加新小说项目

```bash
python3 /var/minis/shared/countdown-scheduler.py novel add \
  --name "小说名" \
  --genre 玄幻 \
  --platform 起点 \
  --target-words 100000
```

输出：
```
✅ 小说项目已创建
   ID: 477a528a
   名称: 测试小说
   题材: 玄幻
   平台: 起点
   目标字数: 100,000
   目录: /var/minis/shared/novel-team/projects/测试小说

📁 初始文件结构已创建
```

### 3.3 novel log
记录创作活动

```bash
python3 /var/minis/shared/countdown-scheduler.py novel log \
  --project-id 477a528a \
  --action write \
  --words 2000 \
  --chapter 1 \
  --note "第一章开篇"
```

支持的action：
- `write` - 正文创作
- `outline` - 大纲创作
- `character` - 角色设计
- `worldbuilding` - 世界观构建
- `polish` - 润色优化
- `publish` - 发布

### 3.4 novel stats
查看创作统计

```bash
# 全局统计
python3 /var/minis/shared/countdown-scheduler.py novel stats

# 单项目统计
python3 /var/minis/shared/countdown-scheduler.py novel stats --project-id 477a528a
```

### 3.5 novel report
生成创作报告

```bash
python3 /var/minis/shared/countdown-scheduler.py novel report
```

输出：
```
============================================================
📈 小说创作统计报告
============================================================
报告时间: 2026-09-27 07:23
统计周期: 2026-09-27 ~ 2026-09-27
活跃天数: 1天

【整体数据】
  项目数量: 1个
  总字数: 2,000字
  目标字数: 100,000字
  完成进度: 2.0%
  日均产量: 2,000字/天

【行动分布】
  write: 1次 (100.0%), 贡献2,000字

【项目明细】
  ✅ 测试小说: 2,000/100,000 (2.0%)

============================================================
```

---

## 四、实现细节

### 4.1 文件位置
- 项目数据：`/var/minis/shared/.scheduler/novel-projects.json`
- 创作日志：`/var/minis/shared/.scheduler/novel-log.json`
- 统计摘要：`/var/minis/shared/.scheduler/novel-stats.json`（待实现）

### 4.2 核心函数
```python
def load_novel_projects()     # 加载项目列表
def save_novel_projects(data) # 保存项目列表
def load_novel_log()          # 加载创作日志
def save_novel_log(data)      # 保存创作日志

def cmd_novel_list()          # 列表命令
def cmd_novel_add(rest)       # 添加命令
def cmd_novel_log(rest)       # 记录命令
def cmd_novel_stats(rest)     # 统计命令
def cmd_novel_report()        # 报告命令
```

### 4.3 自动关联
- 项目创建时自动生成初始目录结构
- 记录创作活动时自动更新项目字数和最后更新时间
- 章节信息自动追加到项目的chapters数组

---

## 五、扩展规划

### 5.1 短期（v0.6）
- [ ] 增加定时任务：每日创作提醒
- [ ] 增加数据分析：写作效率趋势图
- [ ] 增加提醒功能：未完成任务提醒

### 5.2 中期（v0.7）
- [ ] 增加项目管理：启用/禁用/归档
- [ ] 增加协作功能：多项目切换
- [ ] 增加导出功能：JSON/CSV导出

### 5.3 长期（v1.0）
- [ ] 增加Web界面
- [ ] 增加数据可视化图表
- [ ] 增加API接口

---

## 六、与其他工具的关系

| 工具 | 关系 |
|------|------|
| countdown-scheduler.py | 核心依赖，提供定时任务能力 |
| prompt-library/ | 创作工具，提供提示词模板 |
| genre-system/ | 类型管理，提供类型定义 |
| SOP-CREATION-FLOW.md | 流程规范，定义创作阶段 |

---

**文档版本**：v0.1.0
**更新日期**：2026-09-27
**作者**：小蒋
