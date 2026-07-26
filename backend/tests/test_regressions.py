"""回归测试 - 覆盖 diagnose 阶段发现的真问题

每个测试对应一个之前已复现的 bug:
- test_h2_pydantic_field_name: Pydantic v2 不允许 model_config 字段名
- test_h1_relative_import: backend 包路径正确,模块间相对导入可工作
- test_h7_code_session: run_code 跨调用保持变量(避免反复 import)
- test_sse_format: SSE 输出格式合规,前后端能正确解析
"""
import json
import asyncio

import pytest

# H2: 关键回归 - Pydantic 模型加载不能因为字段名 model_config 崩溃
def test_h2_pydantic_field_name():
    """回归:AnalysisRequest 改名后字段定义,模块能正常加载"""
    from backend.main import AnalysisRequest
    req = AnalysisRequest(
        goal="test",
        llm_config={"base_url": "x", "api_key": "y", "model_name": "z"}
    )
    assert req.goal == "test"
    assert req.llm_config["base_url"] == "x"
    assert req.file_id is None


# H1: 关键回归 - backend 包导入路径打通
def test_h1_relative_import():
    """回归:从 backend.app 导入能触发相对导入链路"""
    from backend.app import app
    # 所有声明的路由都在
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/health" in paths
    assert "/upload" in paths
    assert "/analyze" in paths


# H7: 关键回归 - 跨调用变量共享
def test_h7_code_session_state():
    """回归:CodeSession 跨调用保留变量,避免反复 import"""
    from backend.tools.run_code import CodeSession
    s = CodeSession()
    r1 = s.run("import pandas as pd\ndf = pd.DataFrame({'a':[1,2,3]})")
    assert r1["error"] is None
    r2 = s.run("_result = df['a'].sum()")
    assert r2["error"] is None, f"second call failed: {r2['error']}"
    assert r2["result"] == 6
    # 验证命名空间里有 df
    snap = s.snapshot()
    assert "df" in snap


def test_h7_code_session_isolated_from_function_call():
    """回归:run_python_code() 不带 namespace 时完全隔离"""
    from backend.tools.run_code import run_python_code
    r1 = run_python_code("x = 1")
    r2 = run_python_code("print(x)")  # 应 NameError,因为 x 不在新 namespace
    assert r2["error"] is not None
    assert "NameError" in r2["error"]


# SSE: 验证 generate_analysis_stream 输出格式
def test_sse_format():
    """回归:SSE 输出格式 - 前端能正确解析 event/data 配对"""
    from backend.main import generate_analysis_stream

    class MockAgent:
        async def run(self, goal, data_info=None):
            yield {"type": "step_start", "step": 1, "max_steps": 3}
            yield {"action": "plan", "analysis": "P", "plan": ["a", "b"]}
            yield {"type": "step_start", "step": 2, "max_steps": 3}
            yield {"action": "finish", "analysis": "F", "final_answer": "R"}
            yield {"type": "complete", "final_answer": "R"}

    async def collect():
        out = []
        async for chunk in generate_analysis_stream(MockAgent(), "x"):
            out.append(chunk)
        return out

    chunks = asyncio.run(collect())
    full = "".join(chunks)

    # 必须含 step、data、done 三种 event
    assert "event: step\n" in full
    assert "event: data\n" in full
    assert "event: done\n" in full

    # 解析每个 event:data 后跟一个有效 JSON
    events = []
    current_event = None
    for line in full.split("\n"):
        if line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:") and current_event:
            payload = line[5:].strip()
            if payload:
                events.append((current_event, json.loads(payload)))
                current_event = None

    # 必须有 step 类型,content 是 {'step': int}
    step_events = [d for ev, d in events if ev == "step"]
    assert len(step_events) >= 2
    assert "step" in step_events[0]

    # 必须有 data 类型,content 有 action 字段
    data_events = [d for ev, d in events if ev == "data"]
    actions = [d.get("action") for d in data_events if d.get("action")]
    assert "plan" in actions
    assert "finish" in actions

    # 必须有 done 类型
    done_events = [d for ev, d in events if ev == "done"]
    assert len(done_events) == 1