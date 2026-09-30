#!/usr/bin/env python3
# Version: 0.1.0
"""
tool-emulation.py — OpenAI Tool Calling 模拟层 v0.1

当上游模型不支持 native tool calling 时，通过 prompt 注入 + 响应解析实现兼容。

三段式架构（借鉴 genspark2api）：
  1. INJECT   — 工具 schema 注入 system prompt，输出严格 JSON 契约
  2. PARSE    — 解析模型回复，提取 tool_calls（含 finish_reason）
  3. FLATTEN  — 将 OpenAI 协议消息改写为上游能接受的纯文本格式

用法：
  python3 tool-emulation.py emulate --prompt "帮我查天气" \
      --tools '[{"type":"function","function":{"name":"get_weather",...}}]'
  python3 tool-emulation.py demo            # 运行端到端示例
"""

import json
import re
import subprocess
import sys
import os
from pathlib import Path
from typing import Optional

# ===== 配置 =====
# 注意：契约里含大量 JSON 字面括号，因此不用 str.format()，改用 @@TOOLS@@ 占位替换。
TOOL_OUTPUT_CONTRACT = """You can call tools. The runtime executes them and sends back the real result.
You CANNOT execute anything yourself, and you MUST NEVER write a tool result yourself.

WHEN (AND ONLY WHEN) A TOOL IS NEEDED, output EXACTLY ONE LINE:

{"tool_call": {"name": "TOOL_NAME", "arguments": {"param": "value"}}}

RIGHT  {"tool_call": {"name": "run_shell", "arguments": {"cmd": "date"}}}
RIGHT  {"tool_call": {"name": "read_file", "arguments": {"path": "/etc/hosts"}}}
WRONG  {"tool_call": {"name": "run_shell", "arguments": "cmd": "date"}}    <- arguments must be an OBJECT
WRONG  {"api": "openai", "function": "run_shell", "arguments": ...}        <- wrong shape
WRONG  {"tool_call": {...}}  followed by {"stdout": "..."}                 <- NEVER write the result
WRONG  [CALL run_shell({"cmd": "date"})]                                   <- not this format

RULES
1. Output the tool_call line ONLY. No prose, no markdown fences, no explanation, no result.
2. "arguments" is ALWAYS a JSON object, even when empty: {}
3. "name" must be copied verbatim from the tool list below.
4. If no tool is needed, answer in plain text. Never guess what a tool could tell you.
5. Never fabricate output, timestamps, file contents, or numbers.

Tools available:
@@TOOLS@@"""


def _contract(tools_list_text: str) -> str:
    return TOOL_OUTPUT_CONTRACT.replace("@@TOOLS@@", tools_list_text)


CORRECTION_MSG = (
    "Your previous reply was NOT a valid tool call, so nothing was executed.\n"
    "Output ONLY one line:\n"
    '{"tool_call": {"name": "<name from the tool list>", "arguments": { <json object> }}}\n'
    "The value of \"arguments\" must be a JSON object. "
    "Do NOT write the tool result yourself — the runtime does that."
)

# 模型「想调工具但格式写坏」的特征。命中即触发纠正重试，
# 绝不把这类回复当最终答案（否则模型会自己编造工具结果）。
TOOLISH_KEYS = ('"tool_call"', '"tool_call', '"function_call"', '"toolName"', "[CALL ")


def _looks_toolish(text: str, tool_names=()) -> bool:
    """判断回复是否「想调工具」。包含 toolish 关键字或把工具名当值写出都算。"""
    if any(k.lower() in text.lower() for k in TOOLISH_KEYS):
        return True
    for n in tool_names:
        if f'"{n}"' in text:          # "function": "run_shell" 这类坏形状
            return True
    return False


def _lenient_extract(text: str, tool_names) -> tuple:
    """
    从畸形回复里抢救 (name, args_dict)。
    覆盖：arguments 写成裸串、外层键名写错（api/function/tool）、括号不配对。
    救不回来返回 (None, None)。
    """
    name = None
    for n in tool_names:
        if f'"{n}"' in text or f"'{n}'" in text:
            name = n
            break
    if name is None:
        m = re.search(r'"(?:name|function|tool|tool_name)"\s*:\s*"([\w.-]+)"', text)
        if m and m.group(1) in tool_names:
            name = m.group(1)
    if name is None:
        return None, None

    # arguments：先找 "arguments": {...}
    m = re.search(r'"arguments"\s*:\s*\{', text)
    if m:
        depth, start = 0, m.end() - 1
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return name, json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break

    # "arguments" 的值写成了裸串/缺外层括号：截取后补 {} 再试
    m2 = re.search(r'"arguments"\s*:\s*(.+)$', text, re.DOTALL)
    if m2:
        tail = m2.group(1).strip().rstrip(",")
        for cand in (tail, "{" + tail.rstrip("}").rstrip(",").rstrip() + "}"):
            try:
                obj = json.loads(cand)
                if isinstance(obj, dict):
                    return name, obj
            except json.JSONDecodeError:
                continue

    # 最后：从整个文本抓 "参数名": "值"，剔除协议键
    protocol = {"name", "function", "tool", "tool_name", "api", "type", "arguments", "tool_call"}
    props = re.findall(r'"(\w+)"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    args = {k: v for k, v in props if k not in protocol}
    return (name, args) if args else (name, {})


# ===== 辅助：解析 flatten 格式的简单参数 =====

def _parse_simple_args(args_str: str) -> dict:
    """解析 'city=北京, unit=celsius' 或 '{"city":"北京"}' 格式的参数字符串"""
    args_str = args_str.strip()
    if not args_str:
        return {}

    # 优先尝试 JSON
    if args_str.startswith('{'):
        try:
            return json.loads(args_str)
        except json.JSONDecodeError:
            pass

    # key=value, key=value 模式
    result = {}
    pairs = re.split(r',\s*', args_str)
    for pair in pairs:
        if '=' in pair:
            k, v = pair.split('=', 1)
            # 尝试保持数值类型
            v = v.strip()
            try:
                result[k.strip()] = int(v)
            except ValueError:
                try:
                    result[k.strip()] = float(v)
                except ValueError:
                    result[k.strip()] = v
    return result


# ===== 段1：INJECT =====

def inject_tools(tools: list[dict], system_prompt: str) -> tuple[str, str]:
    """
    将工具 schema 注入 system prompt。
    返回 (updated_system_prompt, tools_list_text)。
    """
    # 生成工具列表文本（供模型理解）
    tools_lines = []
    for t in tools:
        fn = t.get("function", {})
        name = fn.get("name", "?")
        desc = fn.get("description", "")
        params = fn.get("parameters", {})
        # 简化的 schema 描述
        props = params.get("properties", {})
        req = params.get("required", [])
        prop_lines = []
        for k, v in props.items():
            ptype = v.get("type", "string")
            pdesc = v.get("description", "")
            req_mark = " (required)" if k in req else ""
            prop_lines.append(f"  - {k} ({ptype}){req_mark}: {pdesc}")
        props_block = "\n".join(prop_lines) if prop_lines else "  (no parameters)"
        tools_lines.append(f"  {name}: {desc}\n    Parameters:\n{props_block}")

    tools_list_text = "\n\n".join(tools_lines)

    contract = _contract(tools_list_text)
    combined = f"{contract}\n\n---\n\n{system_prompt}" if system_prompt else contract

    return combined, tools_list_text


# ===== 段2：PARSE =====

def parse_tool_response(text: str, tools: list[dict]) -> dict:
    """
    解析模型回复，判断是否包含 tool_call，返回 OpenAI 格式的 response 片段。

    返回：
      {
        "role": "assistant",
        "content": "<text>" | None,
        "tool_calls": [<tool_call_obj>] | None,
        "finish_reason": "tool_calls" | "stop"
      }
    """
    tool_names = {t["function"]["name"] for t in tools}

    # 模式 A: {"tool_call": ...}（JSON 契约格式）
    idx = text.find('{"tool_call"')
    # 模式 B: [CALL name(...)]（flatten 格式）
    bracket_match = None
    if idx == -1:
        bm = re.search(r'\[CALL\s+(\w+)\(([^)]*)\)\]', text)
        if bm:
            bracket_match = (bm.group(1), bm.group(2), bm.start())

    if idx == -1 and bracket_match is None:
        return {
            "role": "assistant",
            "content": text.strip(),
            "tool_calls": None,
            "finish_reason": "stop",
        }

    if idx == -1 and bracket_match is not None:
        # 处理 flatten 模式 [CALL name(args)]
        name, args_str, _ = bracket_match
        # 尝试将 args_str 解析为参数名:值 对
        args = _parse_simple_args(args_str)
        if name in tool_names:
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": f"call_{hash(text[:100]) & 0xFFFFFFFF:08x}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}
                }],
                "finish_reason": "tool_calls",
            }
        return {
            "role": "assistant",
            "content": text.strip(),
            "tool_calls": None,
            "finish_reason": "stop",
        }

    if idx == -1:
        return {
            "role": "assistant",
            "content": text.strip(),
            "tool_calls": None,
            "finish_reason": "stop",
        }
        # 未找到 tool_call 模式 → 普通文本
        return {
            "role": "assistant",
            "content": text.strip(),
            "tool_calls": None,
            "finish_reason": "stop",
        }

    # 从 idx 开始找匹配的右括号
    depth = 0
    end_idx = -1
    for i in range(idx, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break

    if end_idx == -1:
        # 括号不匹配 → 降级为普通文本
        return {
            "role": "assistant",
            "content": text.strip(),
            "tool_calls": None,
            "finish_reason": "stop",
        }

    json_str = text[idx:end_idx]
    try:
        parsed = json.loads(json_str)
        tc = parsed.get("tool_call", {})
        name = tc.get("name", "")
        args_raw = tc.get("arguments", "{}")

        # 确保 arguments 是合法 JSON
        if isinstance(args_raw, str):
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                args = {}
        else:
            args = args_raw or {}

        # 验证 tool name
        if name not in tool_names:
            # name 不匹配 → 降级为普通文本
            return {
                "role": "assistant",
                "content": text.strip(),
                "tool_calls": None,
                "finish_reason": "stop",
            }

        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": f"call_{hash(text[:100]) & 0xFFFFFFFF:08x}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}
            }],
            "finish_reason": "tool_calls",
        }
    except (json.JSONDecodeError, KeyError):
        pass

    # 解析失败 → 普通文本
    return {
        "role": "assistant",
        "content": text.strip(),
        "tool_calls": None,
        "finish_reason": "stop",
    }


# ===== 段3：FLATTEN =====

def flatten_messages(messages: list[dict], tool_results: dict | None = None) -> list[dict]:
    """
    将 OpenAI 协议消息改写为纯文本格式，适配不支持 tool_calls 的上游。

    转换规则：
      assistant{tool_calls:[...]}  →  assistant{content: "[CALL name(args)]"}
      tool{tool_call_id, content} →  user{content: "TOOL RESULT: ..."}
    """
    flat = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls")

        if role == "assistant" and tool_calls:
            # 将 tool_calls 转写为结构化 content
            call_lines = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "?")
                args_str = fn.get("arguments", "{}")
                call_lines.append(f"[CALL {name}({args_str})]")
            flat.append({"role": "assistant", "content": "\n".join(call_lines)})

        elif role == "tool" and tool_results:
            # tool 消息 → user 消息
            result = tool_results.get(msg.get("tool_call_id", ""), content)
            flat.append({"role": "user", "content": f"TOOL RESULT:\n{result}"})

        else:
            flat.append(msg)

    return flat


def _build_history(messages: list[dict], tool_results_map: dict) -> list[dict]:
    """
    将完整消息历史（含 tool_results）展平为上游可接受的格式。
    每轮：assistant{tool_calls} → assistant{text}, tool{...} → user{result}
    """
    flat = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls")

        if role == "assistant" and tool_calls:
            call_lines = []
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "?")
                args_str = fn.get("arguments", "{}")
                call_lines.append(f"[CALL {name}({args_str})]")
            flat.append({"role": "assistant", "content": "\n".join(call_lines)})
        elif role == "tool":
            result = tool_results_map.get(msg.get("tool_call_id", ""), content)
            flat.append({"role": "user", "content": f"TOOL RESULT:\n{result}"})
        else:
            flat.append(msg)
    return flat


def _closing_summary(messages: list[dict], model: str, system_prompt: str) -> str | None:
    """轮数耗尽时，禁用工具再问一次，基于已有工具结果给出总结。失败返回 None。"""
    flat = _build_history(messages, {})
    flat.append({"role": "user", "content": (
        "Tool budget is exhausted. Do NOT call any more tools. "
        "Using ONLY the tool results already above, answer the original request. "
        "State clearly which parts you could not complete.")})
    try:
        path = f"/tmp/tool-close-{os.getpid()}.json"
        Path(path).write_text(json.dumps({"messages": flat}, ensure_ascii=False))
        cmd = ["minis-model-use", "run", "--model", model, "--input", path, "--temperature", "0.3"]
        if system_prompt:
            cmd += ["--system", system_prompt]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        data = json.loads(r.stdout)
        return data["data"]["output_text"].strip() if data.get("ok") else None
    except Exception:
        return None


# ===== 主流程（含多轮循环）=====

def run_with_tools(
    prompt: str,
    tools: list[dict],
    model: str,
    system_prompt: str = "",
    tool_handlers: dict | None = None,
    max_turns: int = 5,
    verbose: bool = False,
) -> dict:
    """
    完整的 tool calling 模拟流程，支持多轮对话直到模型停止调用工具。

    Args:
        prompt: 用户初始输入
        tools: 工具列表（OpenAI format）
        model: 模型 ID
        system_prompt: 可选系统提示
        tool_handlers: {tool_name: callable} 工具执行函数映射
        max_turns: 最大对话轮数（防死循环）
        verbose: 是否打印中间过程

    Returns:
        {
            "final_response": str,   # 最终文本回复
            "tool_calls_history": [...],  # 所有工具调用记录
            "turns": int,            # 实际对话轮数
            "finish_reason": str,
            "raw_turns": [...],      # 每轮原始回复（调试用）
        }
    """
    tool_names = {t["function"]["name"] for t in tools}

    # 预注册默认 handler（打印式）
    handlers = {} if tool_handlers is None else dict(tool_handlers)
    for name in tool_names:
        if name not in handlers:
            handlers[name] = lambda n=name, **kw: json.dumps(
                {"tool": n, "params": kw, "note": "未注册执行器，返回模拟结果"}, ensure_ascii=False
            )

    messages = []
    tool_results_map = {}  # call_id → result_text
    tool_calls_history = []
    raw_turns = []
    corrections = 0
    MAX_CORRECTIONS = 2

    # Step 1: INJECT 并发送首轮
    system_with_tools, _ = inject_tools(tools, system_prompt)
    messages.append({"role": "user", "content": prompt})

    for turn in range(max_turns):
        # 调用模型
        input_path = f"/tmp/tool-emulate-{os.getpid()}-{turn}.json"
        input_json = {
            "messages": messages,
            "tools": tools,
        }
        Path(input_path).write_text(json.dumps(input_json, ensure_ascii=False))

        cmd = ["minis-model-use", "run", "--model", model, "--input", input_path,
               "--temperature", "0.7"]
        if system_with_tools:
            cmd += ["--system", system_with_tools]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            resp = json.loads(result.stdout)
            if not resp.get("ok"):
                raise RuntimeError(f"model-use failed: {resp.get('error', {})}")
            raw_text = resp["data"]["output_text"]
        except (subprocess.TimeoutExpired, json.JSONDecodeError, RuntimeError, FileNotFoundError) as e:
            return {
                "final_response": f"[调用失败] {e}",
                "tool_calls_history": tool_calls_history,
                "turns": turn,
                "finish_reason": "error",
                "raw_turns": raw_turns,
            }

        # PARSE
        parsed = parse_tool_response(raw_text, tools)
        raw_turns.append(raw_text)

        if verbose:
            prefix = "⚠️" if turn == max_turns - 1 else "🔄"
            print(f"  [{prefix}] Turn {turn+1}: finish_reason={parsed['finish_reason']}", file=sys.stderr)

        if parsed["finish_reason"] == "stop":
            # 防幻觉闸门：回复「想调工具」但格式非法时，先抢救，救不回就纠正重试。
            # 绝不把这种回复当最终答案 —— 否则模型会自己编造工具结果。
            if _looks_toolish(raw_text, tool_names) and corrections < MAX_CORRECTIONS:
                corrections += 1
                name, args = _lenient_extract(raw_text, tool_names)
                if name:
                    if verbose:
                        print(f"  🔧 格式畸形，已抢救 {name}({json.dumps(args, ensure_ascii=False)[:60]})", file=sys.stderr)
                    parsed = {
                        "role": "assistant", "content": None,
                        "tool_calls": [{
                            "id": f"call_{hash(raw_text[:100]) & 0xFFFFFFFF:08x}",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
                        }],
                        "finish_reason": "tool_calls",
                    }
                else:
                    if verbose:
                        print("  ⚠️ 工具调用格式非法且无法抢救 → 发纠正提示", file=sys.stderr)
                    messages.append({"role": "assistant", "content": raw_text.strip()[:500]})
                    messages.append({"role": "user", "content": CORRECTION_MSG})
                    continue

            if parsed["finish_reason"] == "stop":
                return {
                    "final_response": parsed["content"],
                    "tool_calls_history": tool_calls_history,
                    "turns": turn + 1,
                    "finish_reason": "stop",
                    "raw_turns": raw_turns,
                }

        # 模型调用了工具
        tc = parsed["tool_calls"][0]
        fn = tc["function"]
        tool_name = fn["name"]
        tool_id = tc["id"]

        tool_calls_history.append({
            "turn": turn + 1,
            "call_id": tool_id,
            "name": tool_name,
            "arguments": fn["arguments"],
        })

        if verbose:
            print(f"  🔧 Call {tool_name}({fn['arguments'][:80]})", file=sys.stderr)

        # 执行工具
        try:
            args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
            handler = handlers.get(tool_name, handlers[list(tool_names)[0]])
            result = handler(**args)
            result_text = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
        except Exception as e:
            result_text = f"[工具执行错误] {tool_name}: {e}"

        tool_results_map[tool_id] = result_text

        # 将当前 assistant 回复和 tool result 都展平后追加到历史
        assistant_flat = [{"role": "assistant", **parsed}]
        flat_asst = _build_history(assistant_flat, tool_results_map)
        messages.extend(flat_asst)

        # 追加 tool result（展平为 user 消息）
        messages.append({
            "role": "user",
            "content": f"TOOL RESULT:\n{result_text}",
        })

    # 达到最大轮数，返回最后一条文本
    # 轮数耗尽：禁用工具补一次收尾调用，让模型基于已有工具结果作答，
    # 而不是把最后一轮的 flatten 残留文本当答案吐出来。
    closing = _closing_summary(messages, model, system_prompt)
    return {
        "final_response": closing or f"[达到最大轮数 {max_turns}] 最后回复: {raw_turns[-1][:200]}",
        "tool_calls_history": tool_calls_history,
        "turns": max_turns,
        "finish_reason": "max_turns",
        "raw_turns": raw_turns,
    }


# ===== Demo =====

DEMO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称，如北京、上海"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "description": "温度单位"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": "搜索最新新闻",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "搜索关键词"},
                    "limit": {"type": "integer", "description": "返回条数", "default": 5},
                },
            },
        },
    },
]


def demo():
    print("=" * 60)
    print("tool-emulation.py — Demo (多轮工具调用)")
    print("=" * 60)

    # 定义一个简单工具执行器
    def mock_search(query: str, limit: int = 3):
        results = {
            "genspark2api": f"GitHub 项目 genspark2api，{limit} 条结果",
            "model-router": "Minis 模型路由引擎",
            "tool-emulation": "本工具库",
        }
        return {"results": list(results.items())[:limit], "query": query}

    # 测试 1：简单问答（无工具）
    print("\n[测试 1] 无工具调用")
    resp = run_with_tools(
        prompt="你好，介绍一下自己",
        tools=DEMO_TOOLS,
        model="agnes-2.5-flash",
        verbose=True,
    )
    print(f"  turns: {resp['turns']}, finish: {resp['finish_reason']}")
    print(f"  response[:100]: {resp['final_response'][:100]}...")

    # 测试 2：单轮工具调用
    print("\n[测试 2] 单轮工具调用（查天气）")
    resp = run_with_tools(
        prompt="帮我查一下北京的天气，用摄氏度",
        tools=DEMO_TOOLS,
        model="agnes-2.5-flash",
        tool_handlers={"get_weather": lambda city, unit="celsius": {"city": city, "temp": 25, "unit": unit},
                       "search_news": lambda keyword, limit=3: {"keyword": keyword, "news": [f"新闻关于{keyword}"]}},
        verbose=True,
    )
    print(f"  turns: {resp['turns']}, finish: {resp['finish_reason']}")
    print(f"  tool_calls: {len(resp['tool_calls_history'])} 次")
    for tc in resp['tool_calls_history']:
        print(f"    → {tc['name']}({tc['arguments'][:60]})")
    print(f"  final[:120]: {resp['final_response'][:120]}...")

    # 测试 3：多轮工具调用
    print("\n[测试 3] 多轮工具调用（先搜天气，再搜新闻）")
    resp = run_with_tools(
        prompt="先查北京天气，再搜索 genspark2api 的新闻",
        tools=DEMO_TOOLS,
        model="agnes-2.5-flash",
        tool_handlers={"get_weather": lambda city, unit="celsius": {"city": city, "temp": 25, "unit": unit},
                       "search_news": lambda keyword, limit=3: {"keyword": keyword, "news": [f"genspark2api: OpenAI兼容API桥接"]}},
        verbose=True,
    )
    print(f"  turns: {resp['turns']}, finish: {resp['finish_reason']}")
    print(f"  tool_calls: {len(resp['tool_calls_history'])} 次")
    for tc in resp['tool_calls_history']:
        print(f"    Turn {tc['turn']}: {tc['name']}({tc['arguments'][:60]})")
    print(f"  final[:150]: {resp['final_response'][:150]}...")

    # 测试 4：无匹配工具名时降级
    print("\n[测试 4] 工具名不匹配时降级为文本")
    bad_tools = [{"type": "function", "function": {"name": "unknown_tool", "description": "不存在", "parameters": {"type": "object", "properties": {}}}}]
    resp = run_with_tools(
        prompt="帮我用 unknown_tool 做什么",
        tools=bad_tools,
        model="agnes-2.5-flash",
        verbose=True,
    )
    print(f"  finish: {resp['finish_reason']}, turns: {resp['turns']}")
    print(f"  has tool_calls: {len(resp['tool_calls_history']) > 0}")
    print(f"  response[:80]: {resp['final_response'][:80]}...")

    print("\n✅ 所有测试完成")


# ===== CLI =====

_BUILTIN_HANDLERS = {}


def _h_run_shell(cmd: str, timeout: int = 30):
    """内置工具：执行 shell 命令"""
    r = subprocess.run(["/bin/sh", "-c", cmd], capture_output=True, text=True, timeout=timeout)
    return {"stdout": r.stdout[:4000], "stderr": r.stderr[:1000], "exit_code": r.returncode}


def _h_read_file(path: str):
    """内置工具：读取文件"""
    try:
        return {"content": Path(path).read_text()[:20000]}
    except Exception as e:
        return {"error": str(e)}


def _h_write_file(path: str, content: str):
    """内置工具：写入文件"""
    try:
        Path(path).write_text(content)
        return {"ok": True, "bytes": len(content.encode())}
    except Exception as e:
        return {"error": str(e)}


def _h_web_search(query: str, max_results: int = 5):
    """内置工具：anysearch 网页搜索"""
    r = subprocess.run(
        ["python3", "/var/minis/skills/anysearch/scripts/anysearch_cli.py",
         "search", query, "--max_results", str(max_results)],
        capture_output=True, text=True, timeout=60)
    return {"result": r.stdout[:6000] or r.stderr[:500]}


def _tool(name, desc, **params):
    """构造 OpenAI tool schema。params: {param: (type, description)}，全部必填。"""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": {k: {"type": t, "description": d} for k, (t, d) in params.items()},
                "required": list(params.keys()),
            },
        },
    }


BUILTIN_TOOLS = {
    "run_shell": (_h_run_shell, _tool(
        "run_shell", "在 Linux 沙箱执行 shell 命令，返回 stdout/stderr/exit_code",
        cmd=("string", "要执行的 shell 命令"))),
    "read_file": (_h_read_file, _tool(
        "read_file", "读取指定路径文件的文本内容",
        path=("string", "文件绝对路径"))),
    "write_file": (_h_write_file, _tool(
        "write_file", "将内容写入指定路径文件（覆盖写入）",
        path=("string", "文件绝对路径"),
        content=("string", "要写入的文本内容"))),
    "web_search": (_h_web_search, _tool(
        "web_search", "搜索互联网获取最新信息，返回摘要与链接",
        query=("string", "搜索关键词"))),
}


def cmd_run(argv):
    """tool-emulation.py run --prompt "任务" [--model M] [--use run_shell,web_search | --tools J]"""
    import argparse
    ap = argparse.ArgumentParser(prog="tool-emulation.py run")
    ap.add_argument("--prompt", "-p", required=True)
    ap.add_argument("--model", "-m", default="agnes-2.5-flash")
    ap.add_argument("--system", "-s", default="")
    ap.add_argument("--use", "-u", help="使用内置工具，逗号分隔：run_shell,read_file,write_file,web_search")
    ap.add_argument("--tools", help="自定义 OpenAI tools JSON 数组")
    ap.add_argument("--max-turns", type=int, default=8)
    ap.add_argument("--json", action="store_true", help="输出完整 JSON（含中间轮次）")
    ap.add_argument("--quiet", "-q", action="store_true")
    a = ap.parse_args(argv)

    tools, handlers = [], {}
    if a.use:
        for name in [x.strip() for x in a.use.split(",") if x.strip()]:
            if name not in BUILTIN_TOOLS:
                print(f"[错误] 未知内置工具 '{name}'，可选: {', '.join(BUILTIN_TOOLS)}", file=sys.stderr)
                sys.exit(2)
            h, schema = BUILTIN_TOOLS[name]
            tools.append(schema)
            handlers[name] = h
    elif a.tools:
        try:
            tools = json.loads(a.tools)
        except json.JSONDecodeError as e:
            print(f"[错误] --tools JSON 解析失败: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        print("[错误] 必须指定 --use 或 --tools", file=sys.stderr)
        sys.exit(2)

    resp = run_with_tools(
        prompt=a.prompt, tools=tools, model=a.model,
        system_prompt=a.system, tool_handlers=handlers,
        max_turns=a.max_turns, verbose=not a.quiet)

    if a.json:
        print(json.dumps(resp, indent=2, ensure_ascii=False))
    else:
        print(resp["final_response"])
        if resp["tool_calls_history"]:
            print(f"\n--- {resp['turns']} 轮 / {len(resp['tool_calls_history'])} 次工具调用 ---", file=sys.stderr)
            for tc in resp["tool_calls_history"]:
                print(f"  T{tc['turn']}: {tc['name']} {tc['arguments'][:100]}", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "demo":
        demo()
    elif cmd == "run":
        cmd_run(sys.argv[2:])
    else:
        print("tool-emulation.py — 无原生 tool calling 的模型启用工具调用\n")
        print("命令:")
        print("  run   执行带工具的任务")
        print("  demo  运行端到端示例\n")
        print("示例:")
        print('  python3 tool-emulation.py run -p "现在几点，磁盘用量" -u run_shell')
        print('  python3 tool-emulation.py run -p "查GPT-6定价" -u web_search,run_shell')
        print('  python3 tool-emulation.py run -p "任务" --tools \'[{...}]\' -m agnes-2.5-flash')
        print()
        print("内置工具:", ", ".join(BUILTIN_TOOLS))
