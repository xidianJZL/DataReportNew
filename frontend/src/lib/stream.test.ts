// Node 22-native test for the SSEReader module.
//   Run with: node --test frontend/src/lib/stream.test.mjs
//
// This file mirrors the spirit of `_e2e_sse_parser_test.py` — same set
// of failure modes the old App.tsx parser broke on. If this passes, the
// SSEReader extraction is at least as robust as the previous in-line
// logic.

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { SSEReader, parseEventBlock } from './stream.ts'

/** Build a ReadableStream<Uint8Array> from an array of strings (each becomes one chunk).
 *  Mimics the chunked delivery we get from a real HTTP fetch stream. */
function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  let i = 0
  return new ReadableStream({
    pull(controller): void {
      if (i < chunks.length) {
        controller.enqueue(new TextEncoder().encode(chunks[i++]))
      } else {
        controller.close()
      }
    },
  })
}

/** Drain an async iterator into an array (for assertions). */
async function drain<T>(it: AsyncIterable<T>): Promise<T[]> {
  const out: T[] = []
  for await (const evt of it) out.push(evt)
  return out
}

test('TEST 1: real \\n in data payload survives (single chunk)', async () => {
  const payload = {
    action: 'run_code',
    analysis: '我先加载数据。\n读取 Excel 看看前几行。\n下一步做统计。',
    code: 'import pandas as pd',
  }
  const block = `event: data\ndata: ${JSON.stringify(payload)}\n\n`
  const evts = await drain(SSEReader.from(streamFromChunks([block])))
  assert.equal(evts.length, 1, 'exactly one event')
  assert.equal(evts[0].event, 'data')
  const parsed = evts[0].json<{ action: string; analysis: string }>()
  assert.equal(parsed.action, 'run_code')
  assert.ok(parsed.analysis.includes('\n'), 'analysis should preserve real \\n')
})

test('TEST 2: event with multi-line data: fields (per SSE spec)', async () => {
  const block = [
    'event: data',
    'data: {"action": "finish",',
    'data: "final_answer": "Hello\\nWorld"}',
    '',
  ].join('\n')
  const evts = await drain(SSEReader.from(streamFromChunks([block])))
  assert.equal(evts.length, 1)
  assert.equal(evts[0].event, 'data')
  const parsed = evts[0].json<{ final_answer: string }>()
  assert.equal(parsed.final_answer, 'Hello\nWorld')
})

test('TEST 3: event boundary \\\\n\\\\n spans two HTTP chunks', async () => {
  // chunk 1: incomplete first event
  const chunk1 = `event: step\ndata: {"step": 1}\n\nevent: data\ndata: {"acti`
  // chunk 2: completes the data event and adds done event
  const chunk2 = `on": "run_code", "analysis": "x"}\n\nevent: done\ndata: {"message": "分析完成"}\n\n`
  const evts = await drain(SSEReader.from(streamFromChunks([chunk1, chunk2])))
  assert.equal(evts.length, 3, 'three complete events')
  assert.equal(evts[0].json<{ step: number }>().step, 1)
  const finish = evts[1].json<{ action: string; analysis: string }>()
  assert.equal(finish.action, 'run_code')
  assert.equal(evts[2].json<{ message: string }>().message, '分析完成')
})

test('TEST 4: many complete events in one chunk', async () => {
  const payload = '{"action": "finish", "final_answer": "ok"}'
  const chunks = [`event: step\ndata: {"step": 1}\n\n`,
                  `event: step\ndata: {"step": 2}\n\n`,
                  `event: data\ndata: ${payload}\n\n`,
                  `event: done\ndata: {"message": "done"}\n\n`]
  const evts = await drain(SSEReader.from(streamFromChunks(chunks)))
  assert.equal(evts.length, 4)
  assert.deepEqual(evts.map(e => e.event), ['step', 'step', 'data', 'done'])
})

test('TEST 5: parseEventBlock — the pure parser helper', () => {
  const field = parseEventBlock('event: foo\ndata: bar\n: comment-line\ndata: baz')
  assert.equal(field.event, 'foo')
  assert.deepEqual(field.data, ['bar', 'baz'])
})

test('TEST 6: parseEventBlock handles CRLF and CR line endings', () => {
  const crlf = parseEventBlock('event: foo\r\ndata: bar\r\n\r\n')
  assert.equal(crlf.event, 'foo')
  assert.deepEqual(crlf.data, ['bar'])
  const cr = parseEventBlock('event: foo\rdata: bar\r')
  assert.equal(cr.event, 'foo')
  assert.deepEqual(cr.data, ['bar'])
})

test('TEST 7: exactly one leading space after colon is stripped (per spec)', () => {
  // The spec removes at most one leading space. A payload with two
  // leading spaces keeps one (i.e. it would have been authored as
  // `data:  …`  meaning "the value is one leading space + rest").
  const field = parseEventBlock('event: foo\ndata:  has-two-spaces\n')
  assert.equal(field.event, 'foo')
  assert.equal(field.data[0], ' has-two-spaces')
})

test('TEST 7b: zero leading space stays unchanged', () => {
  const field = parseEventBlock('data:nospace\n')
  assert.deepEqual(field.data, ['nospace'])
})

test('TEST 8: empty stream yields zero events', async () => {
  const evts = await drain(SSEReader.from(streamFromChunks([])))
  assert.deepEqual(evts, [])
})

test('TEST 9: json() convenience returns parsed object', async () => {
  const block = `event: data\ndata: {"k": 42, "list": [1,2,3]}\n\n`
  const evts = await drain(SSEReader.from(streamFromChunks([block])))
  const obj = evts[0].json<{ k: number; list: number[] }>()
  assert.equal(obj.k, 42)
  assert.deepEqual(obj.list, [1, 2, 3])
})

test('TEST 10: malformed JSON does not throw, caller decides', async () => {
  const block = `event: data\ndata: not valid json\n\n`
  const evts = await drain(SSEReader.from(streamFromChunks([block])))
  assert.equal(evts.length, 1)
  assert.equal(evts[0].data, 'not valid json')
  assert.throws(() => evts[0].json(), SyntaxError)
})

test('TEST 11: realistic agent stream — multiple steps + finish + done', async () => {
  // Simulate the exact pattern Agent.run() produces
  const blocks = []
  for (let i = 1; i <= 4; i++) {
    blocks.push(`event: step\ndata: {"step": ${i}}\n\n`)
  }
  blocks.push(`event: data\ndata: ${JSON.stringify({
    action: 'finish',
    analysis: 'All done',
    final_answer: '# 报告\n\n总订单数: 500\n\n## Section',
    step_summary: 'FIN',
  })}\n\n`)
  blocks.push(`event: complete\ndata: {"final_answer": "# 报告"}\n\n`)
  blocks.push(`event: done\ndata: {"message": "分析完成"}\n\n`)

  const full = blocks.join('')
  // Also test it split across arbitrary 200-byte chunks
  const chunks = []
  for (let i = 0; i < full.length; i += 200) {
    chunks.push(full.slice(i, i + 200))
  }
  const evts = await drain(SSEReader.from(streamFromChunks(chunks)))
  // 4 step + 1 data(finish) + 1 complete + 1 done = 7
  assert.equal(evts.length, 7)
  const finishEvt = evts.find(e => e.event === 'data' && e.json<{ action: string }>().action === 'finish')
  assert.ok(finishEvt)
  const finish = finishEvt.json<{ final_answer: string }>()
  assert.equal(finish.final_answer, '# 报告\n\n总订单数: 500\n\n## Section')
})
