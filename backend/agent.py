"""
Agent 循环核心模块
实现 LLM 自主决策的 Plan-Execute 循环
"""
import json
import re
from typing import Literal, AsyncGenerator
from openai import AsyncOpenAI

from .tools.run_code import run_python_code, CodeSession


ActionType = Literal["plan", "run_code", "finish"]


def _extract_json_substring(s: str) -> str | None:
    """Return the first balanced top-level ``{...}`` substring of ``s``.

    Brace counting skips over characters inside string literals (with
    ``\\``-escapes honored) so a ``}`` inside a JSON string value does
    not terminate the scan prematurely. Returns ``None`` if no balanced
    object is found.
    """
    start = s.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(s)):
        c = s[i]
        if in_string:
            if escape_next:
                escape_next = False
            elif c == "\\":
                escape_next = True
            elif c == '"':
                in_string = False
            continue
        if c == '"':
            in_string = True
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _strip_markdown_fence(s: str) -> str | None:
    """If ``s`` is wrapped in a ``\\`\\`\\`json ... \\`\\`\\` `` (or plain
    ``\\`\\`\\` ... \\`\\`\\` ``) markdown fence, return the inner contents;
    otherwise return ``None``.
    """
    import re

    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", s, flags=re.DOTALL)
    if not m:
        return None
    return m.group(1)


def _parse_llm_json(raw_content: str):
    """Parse the JSON object an LLM returned for one Agent step.

    Returns the parsed dict on success. On any failure, returns a dict
    of the form ``{"__error__": "<reason>"}`` so the caller can surface
    a single, uniform error path.
    """
    candidates: list[tuple[str, str]] = []  # (label, text)

    # 1. As-is.
    candidates.append(("raw", raw_content))

    # 2. Inside a markdown fence, if present.
    fenced = _strip_markdown_fence(raw_content)
    if fenced is not None and fenced != raw_content:
        candidates.append(("fenced", fenced))

    # 3. First balanced { ... } substring of the raw response.
    extracted = _extract_json_substring(raw_content)
    if extracted is not None:
        candidates.append(("extracted", extracted))

    last_err: json.JSONDecodeError | None = None
    for label, text in candidates:
        try:
            result = json.loads(text, strict=False)
        except json.JSONDecodeError as e:
            last_err = e
            continue
        if isinstance(result, dict):
            return result
        # Multiple top-level JSON objects concatenated → keep first object.
        if isinstance(result, list) and result and isinstance(result[0], dict):
            return result[0]
        last_err = json.JSONDecodeError(
            f"top-level value is {type(result).__name__}, not an object",
            text,
            0,
        )
    return {"__error__": str(last_err) if last_err else "no JSON object found"}


class DataAnalysisAgent:
    """数据分析 Agent - 负责计划制定、代码执行、结果分析"""
    
    SYSTEM_PROMPT = """你是一个专业的数据分析 Agent，擅长使用 Python 进行数据分析、可视化和报告生成。

你的核心职责：
1. 理解用户的数据分析需求
2. 制定分析计划并逐步执行
3. 编写 Python 代码处理数据、生成可视化
4. 根据分析结果给出专业洞察

工作流程：
1. 先理解数据结构和用户需求
2. 制定分析计划（可用 plan action）
3. 编写并执行代码（用 run_code action）
4. 分析执行结果，决定下一步或结束
5. 生成最终报告（用 finish action）

代码执行环境说明（重要）：
- 每次 run_code 共享同一个 Python 命名空间（持久会话）
- 第一步 `import pandas as pd` 后,后续步骤可直接使用 `pd`,无需重新导入
- 加载的数据变量(如 `df`)在后续步骤中会保留,不要重复读取文件
- 如需显式重置环境,在代码中用 `_result = None` 不会重置,但你可以 `del df` 主动清理
- 最终图表请用 ECharts JSON 格式输出,放在 final_answer 的 Markdown 代码块里

重要约束：
- 生成的代码必须可以独立执行
- 数据文件路径通过 tool 结果获取
- 图表使用 ECharts 格式（pyecharts 或手动生成 HTML）
- 始终考虑数据安全和隐私

输出格式要求：
每一轮你必须输出一个严格的 JSON，对象结构如下：
{
  "action": "plan" | "run_code" | "finish",
  "analysis": "你当前的思考和分析理由",
  "code": "当 action=run_code 时要执行的完整 Python 代码",
  "plan": "当 action=plan 时要执行的计划步骤列表",
  "final_answer": "当 action=finish 时给用户的完整分析报告（Markdown 格式，包含 ECharts 配置）",
  "step_summary": "当前步骤的简要总结"
}

注意：
- 不要输出任何解释性文字，只输出 JSON
- code 中不要包含 print 语句用于调试
- 最终报告应包含数据洞察和可视化建议
"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_name: str = "gpt-4o",
        temperature: float = 0.2,
        max_steps: int = 20
    ):
        # 禁用 Windows 系统代理 (避免企业网络下 httpx 走代理导致 127.0.0.1 请求失败)
        import httpx
        _transport = httpx.AsyncHTTPTransport(retries=0)
        _client = httpx.AsyncClient(transport=_transport, trust_env=False)
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=_client,
        )
        self.model_name = model_name
        self.temperature = temperature
        self.max_steps = max_steps

        # 消息历史
        self.messages: list[dict] = []

        # 代码执行会话 - 跨步骤共享变量(模型在 step1 加载的数据在 step2 可直接用)
        self.code_session = CodeSession()

        # 初始化系统消息
        self.messages.append({
            "role": "system",
            "content": self.SYSTEM_PROMPT
        })

    def reset(self):
        """重置对话历史和代码会话"""
        self.messages = [{
            "role": "system",
            "content": self.SYSTEM_PROMPT
        }]
        self.code_session.reset()
    
    async def step(self, user_input: str) -> dict:
        """
        执行单步推理
        返回 LLM 的决策和结果
        """
        # 添加用户消息
        self.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # 调用 LLM
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=self.messages,
            temperature=self.temperature,
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content

        # Parse JSON. Layered strategy — start strict, fall back through
        # progressively more permissive extraction:
        #
        #   1. raw_content as-is (covers the happy path)
        #   2. raw_content inside ```json ... ``` or ``` ... ``` fence
        #   3. the first balanced {...} substring (handles LLM preambles,
        #      trailing explanations, and "Here is the JSON: {...} Hope it
        #      helps" patterns).
        #
        # All passes use strict=False so legitimate-looking responses that
        # contain raw U+000A / U+000D / U+0009 control characters inside
        # string values don't fail — some LLM providers (notably a few
        # third-party OpenAI-compatible APIs and certain local models) emit
        # these characters verbatim even with response_format=json_object.
        # That was the cause of the previous "Invalid control character" bug.
        decision = _parse_llm_json(raw_content)
        if isinstance(decision, dict) and "__error__" in decision:
            return {
                "action": "error",
                "analysis": f"JSON 解析失败: {decision['__error__']}",
                "error": raw_content
            }
        
        action: ActionType = decision.get("action", "finish")
        analysis = decision.get("analysis", "")
        
        result = {
            "action": action,
            "analysis": analysis,
            "step_summary": decision.get("step_summary", ""),
            "raw": decision
        }
        
        if action == "finish":
            result["final_answer"] = decision.get("final_answer", "")
            return result
        
        elif action == "plan":
            result["plan"] = decision.get("plan", [])
            # 将 LLM 的计划追加到对话
            self.messages.append({
                "role": "assistant",
                "content": raw_content
            })
            return result
        
        elif action == "run_code":
            code = decision.get("code", "")
            result["code"] = code

            # 使用共享会话执行,跨步骤保留变量与导入
            code_result = self.code_session.run(code)
            result["code_result"] = code_result
            
            # 将执行结果追加到对话
            self.messages.append({
                "role": "assistant",
                "content": raw_content
            })
            
            tool_feedback = self._format_tool_result(code_result)
            self.messages.append({
                "role": "user",
                "content": tool_feedback
            })
            
            return result
        
        return result
    
    def _format_tool_result(self, code_result: dict) -> str:
        """格式化代码执行结果"""
        stdout = code_result.get("stdout", "")
        error = code_result.get("error", None)
        result = code_result.get("result")
        
        lines = ["代码执行完成：\n"]
        
        if stdout:
            lines.append(f"输出:\n{stdout}")
        
        if error:
            lines.append(f"错误:\n{error}")
        
        if result is not None:
            lines.append(f"结果:\n{result}")
        
        if not stdout and not error and result is None:
            lines.append("(无输出)")
        
        return "\n".join(lines)
    
    async def run(self, user_goal: str, data_info: dict | None = None) -> AsyncGenerator[dict, None]:
        """
        运行完整的 Agent 循环
        生成器模式，逐步返回每一步的结果
        """
        self.reset()
        
        # 构造初始输入
        initial_input = f"我的目标是：{user_goal}"
        if data_info:
            initial_input += f"\n\n数据文件信息：\n{json.dumps(data_info, ensure_ascii=False, indent=2)}"
        
        for step in range(1, self.max_steps + 1):
            # yield 元数据
            yield {
                "type": "step_start",
                "step": step,
                "max_steps": self.max_steps
            }
            
            # 执行一步
            result = await self.step(initial_input)
            initial_input = ""  # 只需要首次传入用户目标
            
            # yield 结果
            yield result
            
            # 检查是否结束
            if result["action"] == "finish":
                yield {"type": "complete", "final_answer": result.get("final_answer", "")}
                break
            elif result["action"] == "error":
                yield {"type": "error", "message": result.get("analysis", "未知错误")}
                break
        else:
            yield {"type": "max_steps", "message": f"达到最大步数 {self.max_steps}"}


def parse_stream_events(content: str) -> list[dict]:
    """
    解析流式输出中的结构化事件
    使用协议化标签将不同类型内容层次化标记
    
    标签格式：
    [THINK] ... [/THINK] - 推理内容
    [DECISION] ... [/DECISION] - 工具决策
    [CODE] ... [/CODE] - 代码内容
    [OUTPUT] ... [/OUTPUT] - 执行输出
    [ANSWER] ... [/ANSWER] - 面向用户的回答
    [PLAN] ... [/PLAN] - 分析计划
    [CHART] ... [/CHART] - 图表配置
    """
    events = []
    
    # 定义正则模式
    patterns = {
        "think": r"\[THINK\](.*?)\[/THINK\]",
        "decision": r"\[DECISION\](.*?)\[/DECISION\]",
        "code": r"\[CODE\](.*?)\[/CODE\]",
        "output": r"\[OUTPUT\](.*?)\[/OUTPUT\]",
        "answer": r"\[ANSWER\](.*?)\[/ANSWER\]",
        "plan": r"\[PLAN\](.*?)\[/PLAN\]",
        "chart": r"\[CHART\](.*?)\[/CHART\]"
    }
    
    for event_type, pattern in patterns.items():
        matches = re.findall(pattern, content, re.DOTALL)
        for match in matches:
            events.append({
                "type": event_type,
                "content": match.strip()
            })
    
    return events
