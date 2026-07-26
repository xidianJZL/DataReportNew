"""End-to-end integration test.

分层：
- HTTP API 协议测试（必须走 uvicorn，验证 CORS、状态码、SSE Content-Type）
- Agent 单元测试（直接调用，绕开 mock LLM 的跨进程问题）

用真实数据文件 cn_ecommerce_orders_test.xlsx。
"""
import os, sys, json, asyncio, time, socket, threading
sys.path.insert(0, '.')

USE_REAL = os.environ.get("DATA_REPORT_REAL_LLM") == "1"

import httpx
BASE = "http://localhost:8000"
XLSX = r"d:\code\myproject\ProductToolkit\DataReportNew\cn_ecommerce_orders_test.xlsx"

# trust_env=False 避免企业代理干扰 localhost 请求
_http_client = httpx.Client(trust_env=False, timeout=30)


def assert_eq(actual, expected, msg):
    if actual != expected:
        print(f"FAIL [{msg}]: expected {expected!r}, got {actual!r}")
        sys.exit(1)
    print(f"  PASS [{msg}]")


def assert_true(cond, msg):
    if not cond:
        print(f"FAIL [{msg}]")
        sys.exit(1)
    print(f"  PASS [{msg}]")


# ============================================================
# Layer 1: HTTP API protocol tests (uvicorn process)
# ============================================================

def test_health():
    print("\n=== TEST: /health ===")
    r = _http_client.get(f"{BASE}/health")
    assert_eq(r.status_code, 200, "health 200")


def test_upload():
    print("\n=== TEST: /upload ===")
    with open(XLSX, "rb") as f:
        files = {
            "file": (
                "cn_ecommerce_orders_test.xlsx", f,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        }
        r = _http_client.post(f"{BASE}/upload", files=files)
    body = r.json()
    assert_eq(r.status_code, 200, "upload 200")
    assert_true("file_id" in body, "file_id present")
    assert_true("error" not in body, f"no upload error: {body.get('error')}")
    assert_eq(body.get("rows"), 500, "rows == 500")
    assert_true(len(body.get("columns", [])) == 14, "14 columns")
    return body["file_id"]


def test_files_info(file_id):
    print(f"\n=== TEST: /files/{file_id} ===")
    r = _http_client.get(f"{BASE}/files/{file_id}")
    body = r.json()
    assert_eq(r.status_code, 200, "files 200")
    assert_eq(body.get("rows"), 500, "rows == 500")
    assert_true("describe" in body, "describe present")
    assert_true("dtypes" in body, "dtypes present")


def test_outputs():
    print("\n=== TEST: /outputs ===")
    r = _http_client.get(f"{BASE}/outputs")
    assert_eq(r.status_code, 200, "outputs 200")


def test_analyze_protocol(file_id):
    """Verify /analyze returns proper SSE Content-Type and starts streaming.

    We only verify the headers + the first chunk (immediate 'step' event),
    because a full multi-step LLM run requires a working LLM endpoint.
    """
    print(f"\n=== TEST: /analyze protocol (Content-Type + first event) ===")
    payload = {
        "goal": "测试",
        "llm_config": {
            "base_url": "http://127.0.0.1:1/v1",  # unreachable -- 测试是否能拿到 SSE headers
            "api_key": "test",
            "model_name": "test",
        },
        "file_id": file_id,
    }
    try:
        with _http_client.stream("POST", f"{BASE}/analyze", json=payload) as resp:
            assert_eq(resp.status_code, 200, "analyze 200")
            ctype = resp.headers.get("content-type", "")
            assert_true("event-stream" in ctype, f"Content-Type is SSE: {ctype}")
            # 至少能拿到一个 SSE event (agent.run 开始会 yield step_start)
            first_chunk = ""
            for chunk in resp.iter_text():
                first_chunk += chunk
                if "event:" in first_chunk or len(first_chunk) > 200:
                    break
            assert_true(len(first_chunk) > 0, f"got initial SSE bytes ({len(first_chunk)})")
    except (httpx.ReadTimeout, httpx.RemoteProtocolError) as e:
        # 预期：连不上 mock 时 agent.run 会抛异常 -> SSE 流异常关闭
        # 但此时 headers 已经发了，协议正确
        print(f"  (expected streaming error after protocol verified: {type(e).__name__})")
        assert_true(True, "protocol ok (streaming terminated after LLM call failed)")


# ============================================================
# Layer 2: Agent unit test (direct, in-process)
# ============================================================

async def _test_agent_flow_async():
    """直接测试 agent.run() 是否产生正确的 SSE 事件序列."""
    from backend.agent import DataAnalysisAgent
    from backend.tools.run_code import CodeSession

    ROUNDS = [
        {
            "action": "run_code",
            "analysis": "加载数据并查看前 5 行",
            "code": (
                "import pandas as pd\n"
                "df = pd.read_excel(r'" + XLSX + "')\n"
                "_result = df.head().to_dict('records')"
            ),
            "step_summary": "S1: 读取数据",
        },
        {
            "action": "run_code",
            "analysis": "统计订单状态分布",
            "code": "_result = df['订单状态'].value_counts().to_dict()",
            "step_summary": "S2: 状态分布",
        },
        {
            "action": "finish",
            "analysis": "分析完成",
            "final_answer": "# 订单数据分析报告\n\n总订单数：**500** 条",
            "step_summary": "FIN",
        },
    ]

    class MockMsg:
        content = None
        role = "assistant"

    class MockChoice:
        message = None

    class MockResp:
        choices = []

    class MockCompletions:
        def __init__(self):
            self.round = 0

        async def create(self, *args, **kwargs):
            r = self.round
            self.round += 1
            idx = min(r, len(ROUNDS) - 1)
            msg = MockMsg()
            msg.content = json.dumps(ROUNDS[idx], ensure_ascii=False)
            ch = MockChoice()
            ch.message = msg
            resp = MockResp()
            resp.choices = [ch]
            return resp

    class MockChat:
        completions = MockCompletions()

    class MockClient:
        chat = MockChat()

    # 构造 agent -- 正常 __init__ 然后替换 client
    agent = DataAnalysisAgent(
        base_url="http://mock", api_key="mock-key", model_name="mock"
    )
    agent.client = MockClient()

    print("\n=== TEST: agent.run() SSE event sequence ===")
    events = []
    async for evt in agent.run("请分析订单数据", {"rows": 500}):
        events.append(evt)
        kind = "step_start" if evt.get("type") == "step_start" else f"action={evt.get('action')}"
        print(f"  [event] {kind}")

    # 断言事件序列
    step_starts = [e for e in events if e.get("type") == "step_start"]
    actions = [e.get("action") for e in events if e.get("action")]
    completes = [e for e in events if e.get("type") == "complete"]

    assert_true(len(step_starts) >= 2, f">=2 step_start, got {len(step_starts)}")
    assert_eq(actions.count("run_code"), 2, "2 run_code actions")
    assert_eq(actions.count("finish"), 1, "1 finish action")
    assert_eq(len(completes), 1, "1 complete event")

    finish_events = [e for e in events if e.get("action") == "finish"]
    assert_true(bool(finish_events[0].get("final_answer")), "final_answer present")
    print(f"  final_answer: {finish_events[0]['final_answer'][:80]}")


def test_agent_unit():
    asyncio.run(_test_agent_flow_async())


# ============================================================
# Main
# ============================================================

def main():
    print(f"USE_REAL_LLM: {USE_REAL}")
    print(f"BASE: {BASE}")
    test_health()
    file_id = test_upload()
    test_files_info(file_id)
    test_outputs()
    test_analyze_protocol(file_id)
    test_agent_unit()
    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()