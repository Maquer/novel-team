# tool-emulation.py 使用说明

给**不支持 native tool calling 的模型**启用工具调用。借鉴 genspark2api 的
Inject → Parse → Flatten 三段式，纯 prompt 层实现，零上游改造。

- 脚本：`/var/minis/shared/tool-emulation.py`
- 依赖：`minis-model-use`（已内置）
- 验证日期：2026-09-27

---

## 一、最快上手（30 秒）

```bash
cd /var/minis/shared

# 执行 shell
python3 tool-emulation.py run -p "现在几点，磁盘还剩多少" -u run_shell

# 搜索 + 执行组合
python3 tool-emulation.py run -p "查一下 Genspark 是什么" -u web_search

# 看它怎么跑的（中间轮次默认就打到 stderr，-q 才关）
python3 tool-emulation.py run -p "列出 shared 下前5个文件" -u run_shell
```

输出：stdout 是最终自然语言答案；stderr 是每轮工具调用轨迹。

## 二、内置工具（`-u/--use` 逗号分隔）

| 工具 | 作用 | 参数 |
|------|------|------|
| `run_shell` | 沙箱执行命令 | `cmd` |
| `read_file` | 读文件 | `path` |
| `write_file` | 写文件（覆盖） | `path`, `content` |
| `web_search` | anysearch 联网搜索 | `query` |

## 三、自定义工具（`--tools`）

传标准 OpenAI tools 数组。适合接自己的函数：

```bash
python3 tool-emulation.py run -p "北京天气" --model agnes-2.5-flash --tools '[
 {"type":"function","function":{"name":"get_weather",
  "description":"查天气",
  "parameters":{"type":"object","properties":{"city":{"type":"string"}},
  "required":["city"]}}}]'
```

未提供执行器的工具会返回占位结果（不中断流程）。

## 四、Python 调用（要真实执行自己的函数时用这个）

```python
import importlib.util, json, subprocess
spec = importlib.util.spec_from_file_location("te", "/var/minis/shared/tool-emulation.py")
te = importlib.util.module_from_spec(spec); spec.loader.exec_module(te)

def my_tool(city: str):
    return {"temp": 25, "city": city}          # 真实业务逻辑

tools = [te.BUILTIN_TOOLS["run_shell"][1]]     # 复用内置 schema
resp = te.run_with_tools(
    prompt="上海天气",
    tools=[{"type": "function", "function": {"name": "my_tool",
            "description": "查天气",
            "parameters": {"type": "object",
                           "properties": {"city": {"type": "string"}},
                           "required": ["city"]}}}],
    model="agnes-2.5-flash",
    tool_handlers={"my_tool": my_tool},
    max_turns=8, verbose=True)

print(resp["final_response"])        # 最终答案
print(resp["tool_calls_history"])    # 全部调用轨迹
```

> 文件名有连字符，不能 `import tool_emulation`，必须走上面的 `spec_from_file_location`。

## 五、经 model-router 调用（自动选模型）

```bash
python3 /var/minis/shared/model-router.py route "任务" --tools '[...]'
python3 /var/minis/shared/model-router.py route "任务" --tools '[...]' --model agnes-2.5-flash
```

`--model` 跳过路由直连；不给则按复杂度选（注意 OpenRouter free 常 402/限流，建议显式指定）。

## 六、关键参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--model/-m` | `agnes-2.5-flash` | 目标模型 |
| `--max-turns` | 8 | 工具调用轮数上限，防死循环 |
| `--system/-s` | 空 | 追加在你的 system 之后 |
| `--json` | 关 | 输出完整 JSON（含 `raw_turns` 每轮原始回复） |
| `--quiet/-q` | 关 | 不打中间轮次 |

## 七、三道防护（实测有效，别删）

1. **格式抢救** — 模型写坏 JSON（`"arguments": "cmd": "date"` 这类）时，
   `_lenient_extract` 从畸形串里捞回工具名和参数，不中断。
2. **幻觉闸门** — 回复「想调工具」但解析失败 → 发 `CORRECTION_MSG` 纠正重试（上限 2 次）。
   **没有这道闸门时模型会自己编造假结果**：实测曾凭空写出 `2025-07-18` 的假日期和假 df 输出。
3. **轮数收尾** — 耗尽轮数时禁用工具补一次总结调用，基于已有结果作答并说明未完成部分，
   而不是把 `[CALL ...]` 残留文本当答案吐出。

## 八、已知边界

- **单次回复一个工具调用**。原生 function calling 支持并行，这里改为串行（调用→结果→下一个）。
- **参数无 schema 校验**。原生由 API 强制，这里只靠 prompt 约束 + 抢救式解析。
- **依赖模型守契约**。弱模型可能反复不合规，触发 2 次纠正后放弃。
- **不支持流式**。上游 tool 结果需完整回灌，本层不做增量输出。

## 九、什么时候**不**需要它

Minis 主 Agent（也就是小蒋本身）已有原生工具调用。这个层只在以下场景有价值：

- 脚本/single-shot 里调 `minis-model-use`，想让模型决定跑哪条命令
- 接 kuku2api / genspark2api / OpenRouter free 等**不支持 tools 的上游**
- 给不支持 tools 的小模型加一层「先查再答」的能力

