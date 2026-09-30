# 倒计时调度器修复 · 2026-09-23

## 触发
用户问"倒计时调度器还有不有升级的必要" → 我分析出三个实际问题 → 用户说"修"。

## 三个问题与修复

### 1. 锁文件在 /tmp（会被清理）
- **原来：** `/tmp/countdown-scheduler-check.lock`
- **现在：** `/var/minis/shared/.scheduler/countdown-scheduler-check.lock`
- **风险：** /tmp 清理后两个会话可能同时跑 check

### 2. 失败静默，无重试
- **原来：** 任务失败只记 history，不重试不通知
- **现在：** 最多重试 3 次，间隔 60min / 120min / 180min（递增退避）
- **3 次全挂：** 自动 `enabled=False`，打印 💀，不会死循环
- **成功后：** `retry_count` 归零
- **实测：** tag-audit 人工挂 3 次 → 第三次后自动禁用，修复 re-enable 即恢复

### 3. prompt 任务空转（fired 全 0）
- **根因：** 4 个 REM 提醒依赖 `minis-scheduled create`，该服务 best-effort，会静默丢失
- **现在：**
  - 触发时把 prompt 内容写入 `pending-prompts.jsonl`（可靠持久化）
  - 同时尝试 `minis-scheduled create` 作为快速通道
  - 下次 check 时自动重试 pending 条目，成功才移除
- **新增函数：** `_retry_pending_prompts()`

## 修改文件
`/var/minis/shared/countdown-scheduler.py`（415 → ~460 行）

## 当前状态
```
10 个任务，9 enabled，0 due（无积压）
历史 17 条
```

## 关键路径
- 调度器：`/var/minis/shared/countdown-scheduler.py`
- 任务状态：`/var/minis/shared/.scheduler/countdown-tasks.json`
- 锁文件：`/var/minis/shared/.scheduler/countdown-scheduler-check.lock`
- 待处理 prompt：`/var/minis/shared/.scheduler/pending-prompts.jsonl`