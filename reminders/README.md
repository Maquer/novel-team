# 定时任务触发系统 · 模式 1（含心跳状态分流）

## ⚠️ 所有时间戳使用北京时间（Asia/Shanghai）

**架构**：my-place cron → Bark push → iOS 通知 → 用户 tap → Minis 唤起终端 → 用户按 Enter 执行

---

## 文件清单

| 文件 | 用途 |
|------|------|
| `config.php` | 任务配置（改这里） |
| `cron.php` | cron 入口（无需修改） |
| `README.md` | 本文档 |
| `log.jsonl` | 执行日志（自动生成） |

---

## 部署步骤

### 1. 上传到 my-place.us

目录：`/home/mp_42909509/public_html/reminders/`

上传方式：
- cPanel → File Manager → 上传
- FTP 上传

### 2. 修改 config.php

编辑任务列表，改 `time` 和 `command`：

```php
[
    'id'      => 'daily-backup-0900',
    'time'    => '09:00',
    'title'   => '[gzh] 09:00 备份就绪',
    'body'    => '今日 workspace 备份任务待执行',
    'command' => 'bash /var/minis/shared/workspace-backup.sh',
],
```

**command 是 Minis 终端里要执行的命令**，例如：
- `bash /var/minis/shared/workspace-backup.sh` — 备份
- `python3 /var/minis/shared/memory-l2-rollup.py` — L2 周报
- `echo "hello"` — 简单测试

### 3. cPanel Cron 配置

cPanel → Cron Jobs → Add New Cron Job：

```
命令：*/5 * * * * /usr/bin/php /home/mp_42909509/public_html/reminders/cron.php >> /dev/null 2>&1
```

**每 5 分钟触发一次**。cron.php 内部匹配当前时间，只在配置的时间点触发 Bark push。

### 4. 验证

```bash
# 手动触发测试通知（在 iSH 或 my-place SSH 里）
curl -s "https://api.day.app/Av8DkzMpStcsmsW3KfqEMc/Test/测试通知?url=minis%3A%2F%2Fopen_terminal%3Finit_command=echo%20hello%20world&isArchive=1"
```

iOS 收到 Bark 通知 → tap → Minis 打开终端 → 预填 `echo hello world` → 按 Enter 执行。

### 5. 查看日志

```bash
# 查看最近执行记录
tail -20 /home/mp_42909509/public_html/reminders/log.jsonl
```

---

## URL 结构说明

Bark push URL：
```
https://api.day.app/{key}/{title}/{body}?isArchive=1&url={minis://url}
```

minis:// URL（编码后）：
```
minis://open_terminal%3Finit_command={command 编码}
```

**关键点**：
- `?` 和 `=` 用 `%3F` 和 `%3D` 编码
- 命令内容用 `urlencode` 编码
- 空格用 `+` 或 `%20`

---

## 常见问题

**Q: 时间不精确？**
cron.php 每 5 分钟检查一次，最坏延迟 4 分钟。要精确到 1 分钟，改 cron 为 `* * * * *`。

**Q: 通知没收到？**
1. 检查 Bark iOS App 是否开启通知权限
2. 检查 cPanel cron 是否运行（看 log.jsonl）
3. 检查 Bark key 是否正确

**Q: 命令在终端里没执行？**
用户 tap 通知后 Minis 打开到终端，命令已预填但需**按 Enter** 执行。这是设计选择（用户确认）。

**Q: 想自动执行不需要用户确认？**
需要走 Shortcuts URL 触发器方案，但受 10 次/天免费额度限制。

---

## 后续扩展

- 添加更多任务到 config.php
- 复杂命令写脚本放到 `/var/minis/shared/`
- Bark push 回执通知（任务完成后）
- 失败告警（cron 失败时通知）

---

**部署时间**：约 15 分钟
**维护成本**：改 config.php 即可，无需改 cron.php
