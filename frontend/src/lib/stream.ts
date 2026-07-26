/**
 * Server-Sent Events (SSE) client-side parser.
 *
 * Encapsulates the protocol-level concerns so UI components can simply
 *   for await (const evt of SSEReader.from(response.body)) {
 *     // evt.event: string
 *     // evt.data:  string (raw payload — caller is responsible for JSON.parse if needed)
 *     // evt.json<T>(): T
 *   }
 *
 * Implements HTML Living Standard §9.2 (Server-Sent Events):
 *   - An event consists of one or more field lines (event:, data:, id:, retry:),
 *     terminated by a blank line (\n\n).
 *   - Multiple `data:` lines within one event are concatenated with U+000A
 *     (line feed) before being delivered to the handler (the previous App.tsx
 *     parser treated each `data:` line as an independent JSON payload — a
 *     subtle violation that broke on any `analysis` or `final_answer` field
 *     containing a real newline).
 *
 * The parser tolerates arbitrary TCP/TLS chunk boundaries — partial events
 * stay buffered in `this.#buffer` until a complete event has arrived.
 */

/** A single SSE field. Each event has zero or more `data:` lines. */
interface SSEField {
  event?: string
  data: string[]
}

/** Delivered, fully-decoded event. */
export interface SSEEvent {
  /** Event type — defaults to "data" per the SSE spec when no `event:` field was sent. */
  event: string
  /** Concatenated data payload (joined by U+000A). May be empty. */
  data: string
  /** Convenience: JSON.parse(evt.data) with caller-specified return type. */
  json<T = unknown>(): T
}

const EVENT_BOUNDARY = '\n\n'

export class SSEReader {
  #buffer = ''
  #decoder = new TextDecoder()

  /** Construct from a `ReadableStream<Uint8Array>` (e.g. `response.body`). */
  static from(body: ReadableStream<Uint8Array> | null): SSEReader {
    const reader = body?.getReader()
    if (!reader) {
      throw new Error('SSEReader: response body is null')
    }
    return new SSEReader(reader)
  }

  readonly #reader: ReadableStreamDefaultReader<Uint8Array>

  private constructor(reader: ReadableStreamDefaultReader<Uint8Array>) {
    this.#reader = reader
  }

  /**
   * Async iterator over SSE events. Returns once the underlying stream closes.
   * Throws if the upstream ReadableStream errors out — UI code should wrap
   * in try/catch the same way it would wrap a raw `fetch().body.getReader()` loop.
   */
  async *[Symbol.asyncIterator](): AsyncGenerator<SSEEvent, void, undefined> {
    try {
      while (true) {
        const { done, value } = await this.#reader.read()
        if (done) break

        this.#buffer += this.#decoder.decode(value, { stream: true })

        // Drain as many complete events as the buffer currently holds.
        // Each event terminates with a blank line (\n\n). We split repeatedly
        // because one chunk may carry multiple events.
        let boundary = this.#buffer.indexOf(EVENT_BOUNDARY)
        while (boundary !== -1) {
          const raw = this.#buffer.slice(0, boundary)
          this.#buffer = this.#buffer.slice(boundary + EVENT_BOUNDARY.length)

          const field = parseEventBlock(raw)
          if (field.data.length > 0) {
            yield toSSEEvent(field)
          }
          boundary = this.#buffer.indexOf(EVENT_BOUNDARY)
        }
      }
      // Flush any trailing partial event block (defensive — server should
      // close on a clean boundary, but we don't want to silently drop data).
      if (this.#buffer.trim().length > 0) {
        const field = parseEventBlock(this.#buffer)
        if (field.data.length > 0) {
          yield toSSEEvent(field)
        }
        this.#buffer = ''
      }
    } finally {
      try {
        this.#reader.releaseLock()
      } catch {
        // Already released or not releasable — safe to ignore.
      }
    }
  }
}

/**
 * Parse the raw lines of a single SSE event block into structured fields.
 *
 * Exposed only for tests / advanced consumers; the main entry point is
 * `SSEReader.from(body)` which yields `SSEEvent` values.
 *
 * Per spec: blank line terminates an event. We pre-cut by the caller, so
 * `block` is everything up to but not including the final `\n\n`.
 */
export function parseEventBlock(block: string): SSEField {
  const field: SSEField = { data: [] }
  // Per SSE spec, lines may be separated by U+000D U+000A, U+000A, or U+000D.
  // Handle each:
  const lines = block.split(/\r\n|\r|\n/)
  for (const line of lines) {
    if (line.length === 0) continue
    // Lines starting with ":" are comments and must be ignored (per spec).
    if (line.startsWith(':')) continue
    const colon = line.indexOf(':')
    if (colon === -1) {
      // Field name with no value — treat the entire line as the field name,
      // value is empty string (per spec).
      if (line === 'data') field.data.push('')
      else if (line === 'event') field.event = ''
      continue
    }
    const name = line.slice(0, colon)
    let value = line.slice(colon + 1)
    // The spec says: if the first character of the value is a U+0020 SPACE,
    // omit it from the value.
    if (value.startsWith(' ')) value = value.slice(1)
    if (name === 'data') field.data.push(value)
    else if (name === 'event') field.event = value
    // 'id' and 'retry' are also valid fields; we don't currently surface them.
  }
  return field
}

function toSSEEvent(field: SSEField): SSEEvent {
  const data = field.data.join('\n')
  return {
    event: field.event?.trim() || 'data',
    data,
    json: <T = unknown>() => JSON.parse(data) as T,
  }
}
