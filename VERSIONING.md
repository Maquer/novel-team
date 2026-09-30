# 版本管理规范

> 建立日期：2026-09-30 | 适用范围：skills/ 全部技能、shared/ 全部脚本与项目

## 一、版本号格式（SemVer）

`主版本.次版本.修订号`（`X.Y.Z`）

| 位 | 递增时机 | 例子 |
|----|---------|------|
| **主版本 X** | 不兼容变更：删除命令、改输出格式、改核心行为、删字段 | v1.4.2 → v2.0.0 |
| **次版本 Y** | 向后兼容的新功能：加命令、加参数（有默认值）、加模块 | v1.4.2 → v1.5.0 |
| **修订号 Z** | 向后兼容的修复：修 bug、改文案、调阈值不改行为 | v1.4.2 → v1.4.3 |

**规则**：
- 版本号只增不减，只前进不回滚（回滚也记新版本）
- 每次实质变更必须 bump 版本 + 写 CHANGELOG 条目
- 纯文档改动（改注释、改 README 错字）可不 bump，但要 commit

## 二、版本载体（按对象类型）

### 1. Skill（/var/minis/skills/<name>/）

| 载体 | 字段 | 说明 |
|------|------|------|
| `skill.meta.json` | `version` | **唯一真源**，工具自动读写 |
| `SKILL.md` frontmatter | `version` | 镜像，保持与 meta.json 一致 |
| `CHANGELOG.md` | 标题 `## [x.y.z]` | 每版本一节，倒序 |

### 2. Python/Shell 脚本（/var/minis/shared/*.py|*.sh）

| 载体 | 位置 | 说明 |
|------|------|------|
| 文件头 docstring/注释 | `# Version: x.y.z` | 单文件工具 |
| `VERSION` 文件 | 脚本同目录 | 多文件项目 |

### 3. 项目目录（多文件）

| 载体 | 说明 |
|------|------|
| `CHANGELOG.md` | 项目级变更日志 |
| `.version` 或 `package 版本字段` | 当前版本号 |

## 三、CHANGELOG 条目格式

```markdown
## [1.5.0] - 2026-09-30

### Added
- 新增 xxx 命令

### Changed
- 修改 xxx 默认值从 A 到 B

### Fixed
- 修复 xxx 边界条件崩溃

### Removed
- 移除已废弃的 xxx 命令
```

变更类型固定 4 类：`Added` / `Changed` / `Fixed` / `Removed`。

## 四、git 纪律

- Skill 目录：各自独立 git repo（允许直接 clone 外部上游）
- shared/：统一一个 repo
- commit message 格式：`v1.5.0: 添加 xxx` 或 `[fix] 修复 xxx`
- 打 tag：`git tag -a v1.5.0 -m "描述"`（skill 与 shared 各自打）

## 五、自动化工具

```bash
bash /var/minis/shared/version-tool.sh init <目录>        # 初始化（写 .version + CHANGELOG 骨架）
bash /var/minis/shared/version-tool.sh bump <目录> patch|minor|major  # 升版本 + 插 CHANGELOG 模板
bash /var/minis/shared/version-tool.sh show <目录>        # 查当前版本
bash /var/minis/shared/version-tool.sh audit              # 全量审计：缺版本号/缺 CHANGELOG/git 未初始化
```

## 六、升级时机约定

- 修完一个 bug、改完一个功能 → 当场 `bump`
- 外部 skill 整体更新（如 archify 上游同步）→ `bump` minor 或 major，CHANGELOG 写 upstream 同步
- skill.meta.json 与 SKILL.md frontmatter 版本不一致 → audit 报错，以 meta.json 为准修正
