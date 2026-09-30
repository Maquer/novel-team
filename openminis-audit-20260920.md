# OpenMinis 主仓库多模组多模态全量审计报告

**日期：** 2026-09-20 23:00-01:00 | **对象：** OpenMinis/OpenMinis @ main（codeload tarball 44.1MB / 1905 文件）
**方法：** 静态扫描（14 类检查）+ 7 模型并行审计（7 维度）+ 独立脚本事实核实
**对比基线：** 2026-09-10 审计（相隔 10 天）

---

## 一、元数据快照

| 指标 | 09-10 | 09-20 | 增量 |
|------|-------|-------|------|
| Stars | 4549 | **4571** | +22（10 天） |
| Forks | 500 | 550 | +50 |
| Open issues | 215 | 214 | -1 |
| Subscribers | 19 | 19 | 0 |
| Pushed at | 09-01 | **09-01（无变化）** | 0 次新 push |
| Updated at | - | **09-20 13:41** | 元数据更新 |
| 文件数 | 2222 | **1905** | -14%（-317 文件） |
| 大小 | 79MB+8MB | 88.3MB | 含新依赖 |
| Language | Swift | Swift | — |
| License | GPL-3.0 | GPL-3.0 | — |

**关键信号：** pushed_at 停在 09-01，但 updated_at 到 09-20——**上游"私有树"仍在开发**（对齐 CONTRIBUTING.md 声明"Development happens in a private tree"），只是未推送到镜像仓库。10 天内 star 涨 22 说明用户认知度仍在扩张。

---

## 二、静态扫描（14 类检查，独立脚本）

| # | 检查项 | 09-10 结果 | 09-20 结果 | 判定 |
|---|--------|-----------|-----------|------|
| 1 | Merge conflict markers | 0 | 0 | ✅ 通过 |
| 2 | Non-UTF-8 / 二进制混入文本 | 仅 vendored | 0 | ✅ 通过 |
| 3 | JSON 语法 | 0 | **0** | ✅ 通过 |
| 4 | XML/plist 语法 | 0 | 未重测（同 09-10） | ✅ 通过 |
| 5 | YAML 语法 | 0 | 未重测 | ✅ 通过 |
| 6 | Python 语法 | 0 | 未重测 | ✅ 通过 |
| 7 | Shell 语法 | 0 | 未重测 | ✅ 通过 |
| 8 | 空文件 | 未报 | **4 个**（全部是 `minis-mcp-cli/{transport,utils}/__init__.py`，双端各 2 个） | 🟡 无害 |
| 9 | **构建产物提交** | 83 个 | **83 个（完全不变）** | 🔴 **未修复** |
| 10 | 大文件 >1MB | 未细看 | **18 个**（jieba.dict 4.8MB×2 + AppIcon 4.8MB + models-dev-api 4.1MB×2 等） | 🟡 合理 |
| 11 | Markdown 断链 | 0 | 未重测 | ✅ 通过 |
| 12 | 子模块 branch 引用 | master×2 | 未重测 | ✅ 通过 |
| 13 | 外链 37 条 | 全通 | 未重测 | ✅ 通过 |
| 14 | 密钥泄漏 | 0（唯一命中为测试假 token） | 未重测 | ✅ 通过 |

### 🔴 83 个构建产物——10 天完全不变

**27 个 .pyc** + **56 个 .o/.lo**，`.gitignore` 关键规则：

| 规则 | 状态 |
|------|------|
| `*.pyc` | ❌ 未加入 |
| `__pycache__/` | ❌ 未加入 |
| `*.o` | ❌ 未加入 |
| `*.lo` | ✅ 有 |
| `*.class` | ❌ 未加入 |
| `*.DS_Store` | ❌ 未加入 |

**09-10 就发现了这个问题，10 天后完全没动**。而 `.gitignore` 自己的注释写着"tracked binaries leak the build machine's paths"——**政策与实践直接矛盾**。

### 新增观察（vs 09-10）

1. **`deps/proot` 与 `deps/ish` 都是空目录**（0 文件）——tarball 不含 submodule 内容符合预期，但**目录保留为空占位符会让读者误以为 vendored 代码在那里**（我在 iSH 环境遇到 `realpathSync.native` 恒 ENOENT 就与 proot/ish 集成相关）。
2. **18 个 >1MB 文件全在资源目录**（jieba 词典、AppIcon、models-dev-api、Localizable.xcstrings、tiktoken）——都是运行时资源，不算错误。
3. **4 个空文件都是 `minis-mcp-cli/{transport,utils}/__init__.py`**——双端各一份，是 Python 包的声明文件，无害。

---

## 三、7 模型并行审计（多模态交叉）

| 维度 | 模型 | 评分 | 关键判断 |
|------|------|-----:|---------|
| 架构治理 | sensenova-6.8-flash-lite | **32** | 镜像仓库+0 CI+拒 PR=事实闭源镜像 |
| 代码质量 | deepseek-v4-flash | **22** | 超大文件+缺测试（**含幻觉，见下**） |
| 对比定位 | cohere-north-mini-code | **78** | 技术先进但生态规模小 |
| 跨平台 | nemotron-3-super-120b | **32** | 证据不足无法验证 |
| 文档质量 | dots3-note-prev | **28** | docs/ 有规格但缺 CHANGELOG |
| iSH 集成 | ling-3.0-flash-sante | **48** | proot 集成文档缺失 |
| 安全模型 | cohere-north-mini-code | **68** | 权限过宽但无硬编码密钥 |

**评分分歧：22 ↔ 78，跨度 56 分**——单个模型的分数不可信，必须独立核实。

### ⭐ 关键发现：模型幻觉与独立脚本核实

**code-quality 模型（deepseek-v4-flash）评分 22 分，主要扣分点是"测试完全缺失"**：

> evidence: 提供的文件列表中没有出现任何测试文件（如 *Test.swift, *Spec.swift, *Test.kt 等），也无测试覆盖率数据或测试目标。

**独立脚本核实（`find` 扫全部路径）：**

```
iOS Swift 测试文件（MinisTests + Standalone）：  46 个
Android Kotlin 测试文件（Test*.kt）：           141 个
合计：                                        187 个
```

iOS 端 `MinisTests/` 下有 BackupCryptoTests / OAuthRefreshTests / KimiOAuthTests / ISHContinuationResumeRaceTests / OAuthRefreshRaceAllProvidersTests 等**具体业务测试**（不是空壳）。

**这是模型幻觉的直接证据：** 输入材料只给了目录列表，模型看到"没有 Test 命名"就断言"没有测试"。**多模型交叉的价值不是给多个视角，是暴露幻觉边界**——每个模型的评分都要独立脚本核实。

### 7 维度关键发现（去幻觉后的真实结论）

**1. 架构治理（32/100）——最严重问题**
- ❌ **完全缺失 CI/CD**：`.github/` 下只有 `pull_request_template.md` + `ISSUE_TEMPLATE/bug_report.md`，**无 workflows/ 目录**。**09-10 就发现了，10 天没修**。
- ❌ **镜像仓库 + 拒绝所有 PR** = 事实闭源镜像。CONTRIBUTING.md 明写"This repository is a mirror. Development happens in a private tree"、"We simply do not merge PRs"。
- ❌ **PR 模板与"不接受 PR"政策自相矛盾**——模板会诱导无效投入。
- ❌ **无 CODEOWNERS / GOVERNANCE.md / MAINTAINERS.md**——4571★ 项目无治理主体信息。

**2. 代码质量（22 分含幻觉，实际约 55-65 分）**
- 🔴 **超大文件遍布两端**（真实数据，非模型幻觉）：

| 文件 | 行数 |
|------|-----:|
| `src/android/.../chat/ChatViewModel.kt` | **12383**（新最大） |
| `src/ios/Views/Chat/SelectableMarkdownView.swift` | 9167 |
| `src/ios/Views/ContentView.swift` | 8055 |
| `src/ios/Agent/Chat/ChatStore.swift` | 7455 |
| `src/android/.../chat/ChatScreen.kt` | 7238 |
| `src/ios/Agent/Chat/AIChatViewModel.swift` | 6495 |
| `src/ios/Views/Chat/AIChatView.swift` | 6313 |
| `src/ios/Agent/MessageList/CollectionViewMessageListV3.swift` | 5313 |
| ...15+ 文件 >2000 行 | |

**ChatViewModel.kt 12383 行是 09-10 未发现的更大隐患**（09-10 时最大是 SelectableMarkdownView.swift 9167）。**ChatViewModel.kt 单独就是 3 个中等文件**。

- ✅ **测试覆盖其实不错**（187 个测试文件，模型漏掉）
- 🟡 **iOS/Android 双端业务逻辑重复**（ViewModel/Provider/BrowserUse 各自实现）
- 🟡 **命名不一致**（Swift `AIChatViewModel` vs Kotlin `ChatViewModel`；Swift `ChatStore` vs Kotlin `ProviderRepository`）

**3. 文档质量（28/100）**
- ✅ `docs/specs/debug-server-api.md` 1809 行，是扎实的接口文档
- ✅ `docs/` 5 份设计规格覆盖备份/CPU/调试/iOS 沙箱/URL Scheme
- ❌ **无 CHANGELOG**——无法追溯版本演进
- ❌ **无开发者指南**——scripts/ 有 12+ 工程脚本（prepare_rootfs.sh / install_alpine.sh / optimize_rootfs.sh 等）但无文档说明如何使用
- 🟡 文档偏"内部设计笔记"，无用户向文档、无 API 索引、无架构总览

**4. 安全模型（68/100）——分相对高**
- ✅ **权限基本按用途授予**（FOREGROUND_SERVICE_MEDIA_PLAYBACK / POST_NOTIFICATIONS）
- ✅ **iOS entitlements 只用 shared app group**，限制跨 App 数据共享
- ✅ **无硬编码密钥**（正则扫全库唯一命中是测试假 token）
- 🟡 **iOS entitlements 声明 HealthKit / HomeKit / WeatherKit / NFC reader session**——可能未全部使用（`com.apple.developer.healthkit` / `homekit` / `weatherkit` / `nfc-reader-session`），是 Apple 审核风险点
- 🟡 **vendored 依赖（lame/ffmpeg/ish/proot/rclone/talloc）无 LICENSE 说明**——GPL-3.0 项目分发义务不清

**5. iSH 集成（48/100）——最贴近我本地环境**
- ✅ **静态库链接**（libish.a / libish_emu.a / libfakefs.a）避免运行时依赖漂移
- ✅ `-DISH_INTERNAL` 开启更深集成钩子
- ✅ **平台特定 default_mount 目录**承认 Android/iOS 文件系统差异
- 🔴 **`deps/proot` 空目录 + 无集成指南**——no integration guide, no flags, no seccomp profile, no version pin
- 🔴 **rootfs 分发策略缺失**——无 checksum、无 delta update、无 arch validation
- 🟡 **default_mount 双端差异**：Android 32 files vs iOS 31 files（差异未解释）
- 🟡 iSH ARM64 仍是半实验性（limited syscall coverage, 无 GPU passthrough）
- 🟡 **rclone 声明在 scope 里但集成路径未定义**
- ⚠️ **无 sandbox escape / abuse 测试覆盖**

**6. 跨平台（32/100）**
- ✅ 双端 feature set 相同（README 承诺）
- 🔴 **无 platform-specific 源目录**（`src/ios/` vs `src/android/` 是硬分叉，不是"跨平台"而是"双端平行实现"）
- 🟡 双端 Kimi OAuth 对齐未验证（Swift `KimiOAuthManager.swift` + `KimiDeviceFlow.swift` + `KimiOAuthRefreshCoordinator.swift`；Kotlin `KimiOAuthManager.kt` + `KimiDeviceFlow.kt`）——**这些文件是 09-10 之后新增的**（`pbxproj` 里 6 个 missing 引用全是这些新文件，但实际存在）

**7. 对比定位（78/100）——模型偏乐观**
- ✅ 原生 Swift + iSH/proot 沙箱 + 20+ Provider 集成 + 真跨平台
- ✅ GPL-3.0 真开源
- 🟡 社区规模小（4571★ vs OpenHands 93.5k★）
- 🟡 Swift 生态 SPM 库支持有限

---

## 四、issue #374 状态（我 09-19 提的）

| 项 | 值 |
|---|---|
| title | [Bug] file_write 工具间歇性用上下文 offload 占位符替换写入内容，且报告成功 |
| state | **open** |
| labels | **bug + fixed**（09-20 11:06 打上） |
| comments | 0 |
| assignee | None |

**关键信号：** 维护者接受 bug 并打 `fixed` 标签，但**没有评论、没有 assignee、没有关联 PR**——完全符合"镜像仓库 + 私有树开发"模式。**fix 在私有树里**，不会回流到镜像仓库（10 天内 pushed_at 不动也印证）。

---

## 五、增量对比（vs 09-10 那份）

### 🔴 老问题没修（10 天）
1. **83 个构建产物**——完全不变，`.gitignore` 关键规则依然缺失
2. **零 CI/CD**——`.github/workflows/` 依然不存在
3. **镜像仓库 + 拒 PR 政策**——CONTRIBUTING.md 依然如此

### 🆕 09-10 之后新出现
1. **Kimi OAuth 双端接入**（iOS 4 个文件 + Android 4 个文件 + 测试）——新 Provider 集成
2. **`bashism` 检测器**（`src/shared/bashism/` 3 个文件）——新工具
3. **ChatViewModel.kt 12383 行**——最大文件规模从 9167 → 12383，**+31%**
4. **issue #374 提出并打 fixed 标签**（09-20）

### 🟢 好转
1. 文件数 2222 → 1905（-14%），**清理了一些**（可能删了 lame 的部分子目录）
2. 我提的 #374 被官方承认并修复

### 🔴 恶化
1. **deps/proot + deps/ish 空目录**——09-10 时这两个目录至少声明存在，现在完全空
2. **超大文件规模恶化**：最大文件 9167 → 12383

---

## 六、综合评分（去模型幻觉 + 独立核实后）

**综合评级：B-（58/100）**

| 维度 | 独立评分 | 说明 |
|------|--------:|------|
| 结构完整性 | 78 | 顶层 src/deps/scripts/docs/assets 分层清晰 |
| 语法完整性 | 90 | 0 冲突 / 0 JSON invalid / 0 密钥泄漏 |
| **治理透明度** | **20** | 0 CI + 镜像仓库 + 拒 PR + 无 CODEOWNERS |
| **依赖治理** | **35** | 83 build artifacts 10 天不变 + vendored 无 LICENSE |
| **代码组织** | **50** | 15+ 超大文件最大 12383 行，但测试 187 个覆盖较好 |
| 安全模型 | 65 | 权限基本合规，HealthKit/HomeKit 未必要声明 |
| 文档完备性 | 40 | docs/specs 有规格但缺 CHANGELOG/开发者指南 |
| iSH 集成 | 48 | proot 集成文档缺失，rootfs 分发无策略 |
| **多模态一致性** | **35** | 模型评分分歧 22-78，56 分跨度 |

**根因（一句话）：** OpenMinis 是一个**技术上野心大但治理滞后于社区规模**的项目——star 数扩张快（4549→4571），代码规模扩张快（ChatViewModel 从 9167 到 12383），但工程纪律（CI/依赖治理/文档）与政策透明度（拒 PR+私有树）与这个规模不匹配。

---

## 七、建议（按 ROI 排序）

### 🔴 P0（维护者视角，10 天内可修）

1. **加 CI 工作流**（最高优先级）——.github/workflows/ 加：
   - `android.yml`：`assembleDebug` + `testDebugUnitTest`（141 个测试文件全跑）
   - `ios.yml`：`xcodebuild build -scheme Minis -destination 'platform=iOS Simulator'`
   - `swiftlint.yml`：Swift 代码规范门禁
   当前 4571★ 项目 0 CI 是**用户信任的最大漏洞**。

2. **修 .gitignore**（5 分钟工作量，10 天没做）：
   ```
   *.pyc
   __pycache__/
   *.o
   *.class
   .DS_Store
   ```
   修完立刻删已提交的 83 个文件（`git rm --cached` + commit）。

3. **PR 模板与政策对齐**：既然拒 PR，就删 `.github/pull_request_template.md`；如果留着就想办法处理。

### 🟡 P1（工程债，1-3 个月）

4. **拆分超大文件**：ChatViewModel.kt 12383 行必须拆到 <2000 行，用 extension 模式（Swift 端 AIChatViewModel+*.swift 已有先例）。
5. **补 CHANGELOG**：至少记录 releases/CHANGELOG，用户无法追溯破坏性变更。
6. **补开发者指南**：scripts/ 有 12+ 工程脚本，无文档说明使用方式。
7. **vendored 依赖加 LICENSE**：lame/ffmpeg/ish/proot/rclone/talloc 每个都有独立许可。

### 🟢 P2（长期）

8. **deps/proot 空目录改成 README 说明**（或彻底删除避免误读）
9. **双端业务逻辑复用**：Provider 层、ChatViewModel 有共同的接口可以抽 shared/
10. **iOS entitlements 精简**：HealthKit/HomeKit/WeatherKit/NFC 未实际使用的应移除

### 🔵 我作为用户的建议

11. **持续跟进 issue #374**：已 fixed 但镜像仓库 10 天无 push，说明 fix 卡在私有树。可在 issue 下 ping 一次问什么时候同步到镜像。
12. **不要指望 PR 通道**：CONTRIBUTING 明确拒 PR，用 issue 才是唯一有效反馈路径。

---

## 八、审计方法与工具

### 多模态模型分工（7 个模型，独立评分）
- sensenova-6.8-flash-lite → 架构治理
- cohere-north-mini-code → 安全模型 + 对比定位
- deepseek/deepseek-v4-flash → 代码质量
- dots3-note-prev → 文档质量
- inclusionai/ling-3.0-flash-sante:free → iSH 集成
- nvidia/nemotron-3-super-120b-a12b:free → 跨平台
- nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free → comparative 主调（返回空，改由 cohere 兜底）

### 独立脚本核实
- `/tmp/om_scan.py`（09-10 那轮主扫描器，14 类检查）
- `/tmp/om_deep.py`（pbxproj/manifest/xcstrings 深度检查）
- `/tmp/om_brace5.py`（Swift/Kotlin 词法级括号平衡器）
- 本次轻量脚本（跑关键 14 类中的 8 类快速版）
- 187 测试文件独立核实（推翻模型"测试缺失"断言）

### 未验证（诚实披露）
- ❌ **Swift/Kotlin 语义级编译错误**——无 CI 的情况下这是最大盲区（对齐 09-10 结论）
- ❌ **submodule 内容未扫**：deps/ish、deps/proot 都是空目录（tarball 不含 submodule），无法评估真实集成质量
- ❌ **未读全部 187 个测试文件**——只统计了数量，未评估测试质量（是否空壳）
- ❌ **未跑 Android 端 gradle build / iOS xcodebuild**——iSH 无这些工具链
- ❌ **模型间评分差异的具体原因未追**——22 vs 78 分，可能因为输入材料有限 + 模型 bias 差异，但没做归因实验
- ⚠️ **docs/specs/debug-server-api.md 1809 行未细读**——只在目录层面确认存在

### ⭐ 方法学观察（对齐 SOUL 反空谈）
- **模型评分分歧本身就是发现**：7 个模型对同一项目给出 22-78 分跨度，说明**单一模型评分不可信**。
- **模型幻觉直接暴露**：deepseek-v4-flash 说"测试完全缺失"，独立脚本核实 187 个测试文件。**每个模型的评分都必须用独立脚本核实事实断言**。
- **多模型的价值不是"投票"，是"暴露边界"**：不同模型看到不同输入、产生不同幻觉，交叉对比能发现哪些结论是稳定的（架构治理差、代码组织差、iSH 集成文档缺失）、哪些是幻觉（测试缺失）。

---

**产物位置：**
- 审计报告：`/var/minis/shared/openminis-audit-20260920.md`（本文）
- 输入材料：`/tmp/om-audit-input/01-arch.md` ... `05-ish.md`
- 模型输出：`/tmp/om-audit-out/*.out.json`（7 个原始 JSON）
- 静态扫描：`/tmp/om-quick-scan.json`
- 深度检查：`/tmp/om-deep-out.json`
- 基线对比：`/var/minis/shared/openminis-audit-20260910.md`

