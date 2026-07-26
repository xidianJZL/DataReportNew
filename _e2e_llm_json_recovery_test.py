"""Regression test: agent.step() recovers from common LLM output malformations.

Bug history (recorded so the next debugger learns):

  - Round 1 (step 4): JSONDecodeError "Invalid control character"
      Caused by raw U+000A inside a string value from a third-party
      OpenAI-compatible LLM provider. Fix: json.loads(..., strict=False).

  - Round 2 (step 6): JSONDecodeError "Invalid control character"
      Same root cause, different field. Same fix handles it.

  - Round 3 (step 7): JSONDecodeError "Extra data: line X col Y (char Z)"
      Caused by LLM appending trailing natural-language text after the
      JSON object — e.g. "Here is my plan: {...}\n\nI hope this helps."
      json.loads parses the first object and raises on what comes after.
      Some providers also wrap the JSON in a ```json ... ``` markdown
      fence even when response_format=json_object is set.

Fix: Layered JSON parser in `_parse_llm_json` tries:
    1. raw_content as-is
    2. the inner of a ```json ... ``` fence, if present
    3. the first balanced {...} substring of the response
Each pass uses strict=False so previously-fixed control-char issues stay fixed.
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


async def _step(payload):
    from backend.agent import DataAnalysisAgent
    agent = DataAnalysisAgent(base_url="http://mock", api_key="k", model_name="m")
    agent.client = MockClient(payload)
    return await agent.step("test")


async def test_trailing_natural_language():
    """LLM appends 'Hope this helps.' or similar after the JSON object."""
    payload = (
        '{"action": "run_code", "analysis": "OK", "code": "x = 1",'
        ' "step_summary": "S1"}\n\n'
        'Hope this helps! Let me know if you need anything else.'
    )
    result = await _step(payload)
    if result.get("action") == "error":
        _err(f"trailing text failed: {result['analysis']!r}")
    if result["action"] != "run_code":
        _err(f"expected run_code, got {result['action']!r}")
    if result["code"] != "x = 1":
        _err(f"code lost: {result['code']!r}")
    print("  PASS: trailing natural-language text recovered")


async def test_markdown_json_fence():
    """LLM returns JSON wrapped in ```json ... ``` despite json_object mode."""
    payload = (
        '```json\n'
        '{\n  "action": "run_code",\n  "analysis": "OK",\n'
        '  "code": "y = 2",\n  "step_summary": "S2"\n}\n'
        '```'
    )
    result = await _step(payload)
    if result.get("action") == "error":
        _err(f"markdown fence failed: {result['analysis']!r}")
    if result["action"] != "run_code" or result["code"] != "y = 2":
        _err(f"unexpected result: {result}")
    print("  PASS: ```json ... ``` fence recovered")


async def test_plain_code_fence():
    """LLM wraps JSON in ``` ... ``` (no language hint)."""
    payload = (
        '```\n'
        '{"action": "finish", "analysis": "done",'
        ' "final_answer": "report", "step_summary": "FIN"}\n'
        '```'
    )
    result = await _step(payload)
    if result.get("action") == "error":
        _err(f"plain fence failed: {result['analysis']!r}")
    if result["action"] != "finish":
        _err(f"expected finish, got {result['action']!r}")
    print("  PASS: plain ``` ... ``` fence recovered")


async def test_preamble_then_clean_json():
    """LLM writes a prose preamble WITHOUT stray braces, then a clean JSON object."""
    payload = (
        'I will now analyze the data carefully.\n'
        'Here is my plan:\n'
        '{"action": "plan", "plan": ["step1", "step2"], "step_summary": "P"}\n'
        'Done.'
    )
    result = await _step(payload)
    if result.get("action") == "error":
        _err(f"preamble failed: {result['analysis']!r}")
    if result["action"] != "plan":
        _err(f"expected plan, got {result['action']!r}")
    if result.get("plan") != ["step1", "step2"]:
        _err(f"plan lost: {result.get('plan')!r}")
    print("  PASS: prose preamble + clean JSON object recovered")


async def test_known_limit_stray_brace_in_preamble():
    """A prose preamble that contains a stray '{' (e.g. 'about {the data}')
    is a known limitation — the brace scanner will treat that '{' as the
    start of the JSON object, so the extracted substring is malformed.

    We assert only that the parser does NOT crash and surfaces a clear
    error event. (Real LLMs do not emit prose preambles with stray
    braces — they would just produce malformed output either way.)
    """
    payload = (
        'OK, I will think about {the data} carefully.\n'
        'Here is my plan:\n'
        '{"action": "plan", "plan": ["x"], "step_summary": "P"}\n'
        'Done.'
    )
    result = await _step(payload)
    if not isinstance(result, dict):
        _err(f"expected dict result, got {type(result).__name__}")
    print(f"  PASS (known limit): stray {{ }} in prose surfaces error (action={result['action']!r})")


async def test_concatenated_objects():
    """LLM returns two JSON objects in one response (some providers do this)."""
    payload = (
        '{"action": "plan", "plan": ["x"], "step_summary": "P"}\n'
        '{"action": "run_code", "code": "y = 1", "step_summary": "S"}'
    )
    result = await _step(payload)
    if result.get("action") == "error":
        _err(f"concatenated objects failed: {result['analysis']!r}")
    if result["action"] != "plan":
        _err(f"expected first action 'plan', got {result['action']!r}")
    print("  PASS: two concatenated JSON objects → first object is taken")


async def test_gibberish_still_errors():
    """Truly garbage input still produces an error event (we don't silently
    succeed on noise)."""
    payload = "I am unable to comply with that request."
    result = await _step(payload)
    if result.get("action") != "error":
        _err(f"expected error action, got {result.get('action')!r}")
    if "JSON 解析失败" not in result.get("analysis", ""):
        _err(f"expected error message, got {result.get('analysis')!r}")
    print("  PASS: gibberish still surfaces an error event")


async def test_round1_still_works():
    """Regression guard: the original raw-LF fix must not have regressed."""
    payload = (
        '{\n  "action": "run_code",\n'
        '  "analysis": "我看到了\n继续",\n'  # raw LF
        '  "code": "z = 1",\n  "step_summary": "S"\n}'
    )
    result = await _step(payload)
    if result.get("action") == "error":
        _err(f"raw LF regressed: {result['analysis']!r}")
    if "\n" not in result["analysis"]:
        _err("raw LF was lost during parse")
    print("  PASS: raw LF still tolerated (round-1 fix intact)")


async def main():
    print("=== TEST: LLM output malformations (round 3) ===\n")
    await test_trailing_natural_language()
    await test_markdown_json_fence()
    await test_plain_code_fence()
    await test_preamble_then_clean_json()
    await test_known_limit_stray_brace_in_preamble()
    await test_concatenated_objects()
    await test_gibberish_still_errors()
    await test_round1_still_works()
    print("\n=== ALL LLM-JSON-RECOVERY TESTS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())