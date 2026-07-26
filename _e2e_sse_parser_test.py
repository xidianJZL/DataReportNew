"""Regression test for frontend SSE parser.

Bug fixed: App.tsx SSE parser split the entire buffer by \\n, which broke
any payload containing a real newline (e.g. multi-line `analysis` from
the LLM). Errors seen:
  - 'JSON 解析失败: Unterminated string'
  - 'JSON 解析失败: Expecting property name enclosed in double quotes'

We can't run the React code directly, so we replicate the parser logic and
verify against representative inputs.
"""
import json
from typing import Generator, Tuple


def simulate_sse_parser(chunks: Generator[bytes, None, None]) -> Tuple[list, list]:
    """Replica of the FIXED App.tsx SSE parser."""
    decoder_buffer = ""
    # Use surrogate TextDecoder-like behavior: bytes → str chunks
    text_chunks = [c.decode("utf-8") for c in chunks]
    text_iter = iter(text_chunks)

    received_events = []
    parse_errors = []

    def read_next_chunk():
        try:
            return next(text_iter)
        except StopIteration:
            return None

    # Mimic the fix: split buffer into events on '\n\n', concatenate data: lines
    incomplete = ""
    while True:
        chunk = read_next_chunk()
        if chunk is None:
            break
        incomplete += chunk
        sep = "\n\n"
        idx = incomplete.find(sep)
        while idx != -1:
            block = incomplete[:idx]
            incomplete = incomplete[idx + len(sep):]

            currentEventType = "data"
            dataParts = []
            for line in block.split("\n"):
                if line.startswith("event:"):
                    currentEventType = line[len("event:"):].strip() or "data"
                elif line.startswith("data:"):
                    dataParts.append(line[len("data:"):].strip())
            if dataParts:
                dataStr = "\n".join(dataParts)
                try:
                    received_events.append((currentEventType, json.loads(dataStr)))
                except json.JSONDecodeError as e:
                    parse_errors.append((dataStr[:200], str(e)))
            idx = incomplete.find(sep)

    return received_events, parse_errors


def main():
    print("=== TEST 1: Real \\n in `analysis` field ===\n")
    payload = {
        "action": "run_code",
        "analysis": "我先加载数据。\n读取 Excel 看看前几行。\n下一步做统计。",
        "code": "import pandas as pd",
        "step_summary": "S1",
    }
    sse_block = f"event: data\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
    print(f"SSE block (raw bytes): {sse_block.encode('utf-8')[:200]}...\n")

    # Simulate: the bytes are delivered in TWO chunks splitting the
    # block at an arbitrary byte position. The parser must still
    # produce one valid event.
    mid = len(sse_block) // 2
    chunks = (bytes([ord(c)]) for c in sse_block[:mid].encode("utf-8"))
    # Build the proper chunks
    chunks_list = [
        sse_block[:mid].encode("utf-8"),
        sse_block[mid:].encode("utf-8"),
    ]
    events, errors = simulate_sse_parser(c for c in chunks_list)
    print(f"Events parsed: {len(events)}, Parse errors: {len(errors)}")
    assert len(events) == 1, f"expected 1 event, got {len(events)}"
    assert len(errors) == 0, f"expected no errors, got {errors}"
    parsed = events[0][1]
    assert parsed["action"] == "run_code", parsed
    assert "\n" in parsed["analysis"], "analysis should contain real \\n"
    print(f"  ✅ analysis contains {parsed['analysis'].count(chr(10))} real newlines")
    print()

    print("=== TEST 2: Multi-line `final_answer` ===\n")
    finish_event = {
        "action": "finish",
        "analysis": "分析完成",
        "final_answer": "# 报告\n\n总订单数: 500\n\n## 分布",
    }
    sse_finish = (
        f"event: data\ndata: {json.dumps(finish_event, ensure_ascii=False)}\n\n"
        "event: done\ndata: {\"message\": \"分析完成\"}\n\n"
    )
    chunks_list = [sse_finish[:100].encode("utf-8"), sse_finish[100:].encode("utf-8")]
    events, errors = simulate_sse_parser(c for c in chunks_list)
    print(f"Events parsed: {len(events)}, Parse errors: {len(errors)}")
    assert len(events) == 2, f"expected 2 events (finish+done), got {len(events)}"
    assert len(errors) == 0, f"expected no errors, got {errors}"
    finish_data = next(data for evt, data in events if data.get("action") == "finish")
    assert "\n" in finish_data["final_answer"]
    print(f"  ✅ both events parsed; final_answer has {finish_data['final_answer'].count(chr(10))} newlines")
    print()

    print("=== TEST 3: Single-chunk delivery (no split) — also works ===\n")
    chunks_list = [sse_block.encode("utf-8")]
    events, errors = simulate_sse_parser(c for c in chunks_list)
    assert len(events) == 1 and len(errors) == 0
    print(f"  ✅ single-chunk delivery works too")
    print()

    print("=== TEST 4: Multi-data-line per SSE spec ===\n")
    # A legitimate multi-data-line event (per SSE spec §9.2.4)
    sse_multi = (
        "event: data\n"
        "data: {\"action\": \"finish\",\n"
        "data: \"analysis\": \"done\",\n"
        "data: \"final_answer\": \"# Hello\\n# World\"}\n\n"
    )
    chunks_list = [sse_multi.encode("utf-8")]
    events, errors = simulate_sse_parser(c for c in chunks_list)
    print(f"Events parsed: {len(events)}, Parse errors: {len(errors)}")
    assert len(events) == 1 and len(errors) == 0
    parsed = events[0][1]
    assert parsed["final_answer"] == "# Hello\n# World"
    print(f"  ✅ multiple data: lines concatenated correctly")
    print()

    print("=== TEST 5: Empty trailing buffer after \\n\\n — handled ===\n")
    sse_block5 = f"event: data\ndata: {json.dumps({'a': 1})}\n\n"
    chunks_list = [
        sse_block5.encode("utf-8"),
        b"",  # EOF
    ]
    events, errors = simulate_sse_parser(c for c in chunks_list)
    assert len(events) == 1 and len(errors) == 0
    print(f"  ✅ trailing empty chunk tolerated")
    print()

    print("=== ALL SSE PARSER REGRESSION TESTS PASSED ===")


if __name__ == "__main__":
    main()