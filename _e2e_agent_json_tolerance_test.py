"""Regression test: agent.step() tolerates raw control characters in LLM output.

Bug: Some LLM providers (e.g. third-party OpenAI-compatible APIs) return
JSON containing raw U+000A / U+000D / U+0009 characters inside string
values, even when response_format=json_object is requested. Python's
default json.loads is strict and raises "Invalid control character",
which the agent surfaces as an error event with analysis="JSON 解析失败:
Invalid control character..." — surfacing as step 6 in the user's UI.

Fix: json.loads(raw_content, strict=False) tolerates raw control chars
in string values, treating them the same as their escaped counterparts.

This test feeds a hand-crafted raw_content with embedded \\n into
agent.step() and asserts the result is a properly-parsed decision dict,
not an error event.
"""
import asyncio, sys, json
sys.path.insert(0, '.')


class MockMsg:
    def __init__(self, content):
        self.content = content
        self.role = "assistant"


class MockChoice:
    def __init__(self, msg):
        self.message = msg


class MockResp:
    def __init__(self, choices):
        self.choices = choices


class MockCompletions:
    def __init__(self, payload):
        self.payload = payload

    async def create(self, *args, **kwargs):
        return MockResp([MockChoice(MockMsg(self.payload))])


class MockChat:
    def __init__(self, payload):
        self.completions = MockCompletions(payload)


class MockClient:
    def __init__(self, payload):
        self.chat = MockChat(payload)


def _err(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


async def test_raw_lf_in_analysis_value():
    """LLM returns JSON with a raw LF inside the `analysis` string value."""
    from backend.agent import DataAnalysisAgent

    # Hand-crafted LLM output: real U+000A inside string values, like a
    # buggy LLM would emit. Without strict=False, json.loads rejects this.
    payload = (
        '{'
        '\n  "action": "run_code",'
        '\n  "analysis": "我看到了数据\n继续分析",'  # ← raw LF here
        '\n  "code": "x = 1",'
        '\n  "step_summary": "S1"'
        '\n}'
    )
    assert "\n" in payload and "\\n" not in payload, "precondition: payload contains raw LF, no escapes"

    agent = DataAnalysisAgent(base_url="http://mock", api_key="k", model_name="m")
    agent.client = MockClient(payload)

    result = await agent.step("test")

    if result.get("action") == "error":
        _err(f"agent.step() returned error event: {result.get('analysis')!r}")

    assert_eq = lambda actual, expected, msg: (
        _err(f"{msg}: expected {expected!r}, got {actual!r}") if actual != expected else None
    )

    assert_eq(result["action"], "run_code", "action preserved")
    assert_eq(result["analysis"], "我看到了数据\n继续分析", "analysis preserves raw LF")
    assert_eq(result["code"], "x = 1", "code preserved")
    assert_eq(result["step_summary"], "S1", "step_summary preserved")
    print("  PASS: raw LF in analysis value parses correctly")


async def test_raw_cr_in_string_value():
    """Raw \\r inside a string value should also be accepted."""
    from backend.agent import DataAnalysisAgent

    payload = '{\n  "action": "plan",\n  "analysis": "plan A\rplan B",\n  "plan": ["p1"]\n}'
    agent = DataAnalysisAgent(base_url="http://mock", api_key="k", model_name="m")
    agent.client = MockClient(payload)

    result = await agent.step("test")
    if result.get("action") == "error":
        _err(f"agent.step() returned error: {result.get('analysis')!r}")
    if result["action"] != "plan":
        _err(f"expected action=plan, got {result.get('action')!r}")
    print("  PASS: raw CR in string value parses correctly")


async def test_truly_malformed_json_still_errors():
    """JSON that's genuinely malformed (not just raw control chars) should still error."""
    from backend.agent import DataAnalysisAgent

    # Missing closing brace
    payload = '{"action": "finish", "analysis": "x"'
    agent = DataAnalysisAgent(base_url="http://mock", api_key="k", model_name="m")
    agent.client = MockClient(payload)

    result = await agent.step("test")
    if result.get("action") != "error":
        _err(f"expected error action, got {result.get('action')!r}")
    if "JSON 解析失败" not in result.get("analysis", ""):
        _err(f"expected error message about JSON parse failure, got {result.get('analysis')!r}")
    print("  PASS: genuinely malformed JSON still produces error event")


async def main():
    print("=== TEST: raw control chars in LLM JSON output (agent.step) ===\n")
    await test_raw_lf_in_analysis_value()
    print()
    await test_raw_cr_in_string_value()
    print()
    await test_truly_malformed_json_still_errors()
    print()
    print("=== ALL AGENT JSON-PARSE TOLERANCE TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())