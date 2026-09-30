# OpenMinis 主仓库全量静态体检报告

**日期：** 2026-09-10 | **对象：** OpenMinis/OpenMinis @ main（codeload tarball，2222 文件，79MB src + 8MB deps）
**方法：** 自研静态扫描（词法级 Swift/Kotlin 括号平衡器 + 多格式解析器 + 工程一致性检查），全程带黄金测试验证扫描器本身。
**边界：** iSH 无法编译 Swift/Kotlin，属静态体检；deps/ish、deps/proot 两子模块内容不在 tarball 内未扫。

## 一、确定问题（3 项，均非致命）

| # | 问题 | 证据 | 严重度 |
|---|------|------|--------|
| 1 | **83 个构建产物被提交进仓库**：27×`.pyc`（scripts/__pycache__ 7 + iOS/Android default_mount 各 5，minis-mcp-cli 随 app 分发）+ 56×`.o/.lo`（deps/lame-3.100） | find 计数；.gitignore 无 `*.pyc`/`__pycache__/`/`*.o`/`*.lo` 规则 | 中。与 .gitignore 自身注释"tracked binaries leak the build machine's paths"政策直接矛盾 |
| 2 | **README.md:188 OkHttp 外链真实 404** | `square.github.io` 根域 200、`/okhttp/` 404，二次复测一致 | 低。建议改指 github.com/square/okhttp |
| 3 | **测试代码随 app 分发**：`default_mount/usr/local/lib/minis-mcp-cli/test_startup_timeout.py`、`test_http_reinit.py` 及其 pyc 打进 iOS/Android 资产 | ls | 低（体积/噪音） |

## 二、观察项（不算错误）

- **无任何 GitHub Actions CI**（.github 下仅 issue 模板）——4.3K★ 双端项目，Swift/Kotlin 改动零自动化验证。本次扫描能过是运气+人肉纪律，建议至少加 macos runner 的 `xcodebuild build` + android `assembleDebug`
- 本地化覆盖不均（xcstrings 2164 keys）：es 96% / zh-Hans 93% / en 93% / zh-Hant 74% / ja 73% / ko 72% / de·fr·ru 70%。9 个零翻译 key 全是符号/占位（`''`/`·`/`•`/`128000` 等），有意为之
- encoding 报告的非 UTF-8/lame 的 56 个 .o 均系 vendored 上游（lame 原始 tarball 自带），非本项目引入的错误

## 三、通过项（干净）

- **语法/解析零 fatal**：JSON 13、XML/plist 45+6、YAML、TOML（gradle 版本目录）、Python 27、Shell 19 全部合法；JSON 无重复键
- **Swift/Kotlin 1063 文件**括号/引号/字符串/插值（Swift `\( )`、raw string `#"..."#`、正则字面量、Kotlin backtick 函数名/`$模板`/Char 字面量）词法级平衡检查全过。初扫 19 个 flagged 全部复核为扫描器自身误报（修正 3 个词法规则后全绿）
- **Xcode 工程一致性**：pbxproj 全部文件引用存在（唯一例外 `deps/resources/alpine-rootfs.zip` 为构建生成物，与 gitignore 声明一致）
- **AndroidManifest 一致性**：14 组件全部可解析（3 个 activity-alias 有 targetActivity 无需类文件；ShizukuProvider 来自库 manifest 合并）
- **跨平台资源无漂移**：iOS 与 Android default_mount 文件集合一致，仅 9 个平台固有差异文件（xdg-open 类 wrapper 等）+ Android 多一个 proot 需要的 etc/hostname——均合理
- 无合并冲突标记、无同目录大小写冲突、无真实密钥泄漏（唯一命中为测试假 token `a1b2c3d4...`）、Markdown 相对链接 0 断链、子模块 branch 引用（master×2）与远端一致
- 外链 37 条：GitHub 域全 200；403=知乎/MacStories 反爬、000=本机网络限制（AppStore/Telegram），非断链

## 四、未验证声明

- 语义级编译错误（类型/引用错误）静态扫不出——无 CI 的情况下这是最大盲区，也是建议加 CI 的核心论据
- ish-arm64、proot 子模块内部未扫
- .strings 老格式文件（10×lproj）无现成解析器，未验语法

## 五、扫描工具（可复用）

- `/tmp/om_scan.py` — 通用仓库静态扫描（14 类检查）
- `/tmp/om_brace5.py` — 词法级 Swift/Kotlin 括号平衡器（黄金测试过：good.swift 含插值/raw string/正则/注释引号 → OK；bad.kt → 报错）
- `/tmp/om_deep.py` — pbxproj/manifest/xcstrings/case-collision 深度检查
