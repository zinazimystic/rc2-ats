export interface SSEEvent {
  event: string;
  data: string;
}

/**
 * Incremental Server-Sent-Events parser. Feed decoded text chunks via push();
 * handles events/lines split across chunks, \r\n, lone \r, comments, BOM and unknown fields.
 */
export function createSSEParser(onEvent: (e: SSEEvent) => void) {
  let buf = "";
  let event = "";
  let data: string[] = [];
  let first = true;

  const dispatch = () => {
    if (data.length) onEvent({ event: event || "message", data: data.join("\n") });
    event = "";
    data = [];
  };
  const line = (l: string) => {
    if (l === "") return dispatch();
    if (l.startsWith(":")) return;
    const i = l.indexOf(":");
    const field = i < 0 ? l : l.slice(0, i);
    let value = i < 0 ? "" : l.slice(i + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  };

  return {
    push(chunk: string) {
      buf += chunk;
      if (first && buf.length) {
        if (buf.charCodeAt(0) === 0xfeff) buf = buf.slice(1);
        first = false;
      }
      let start = 0;
      for (let i = 0; i < buf.length; i++) {
        const c = buf[i];
        if (c !== "\n" && c !== "\r") continue;
        if (c === "\r") {
          if (i === buf.length - 1) break; // may be the first half of \r\n: wait for more
          line(buf.slice(start, i));
          if (buf[i + 1] === "\n") i++;
        } else line(buf.slice(start, i));
        start = i + 1;
      }
      buf = buf.slice(start);
    },
    end() {
      if (buf) line(buf.replace(/\r$/, ""));
      buf = "";
      dispatch();
    },
  };
}

/** Read a fetch body to completion, invoking onEvent per SSE event. Throws on read errors/abort. */
export async function readSSE(body: ReadableStream<Uint8Array>, onEvent: (e: SSEEvent) => void) {
  const reader = body.getReader();
  const dec = new TextDecoder("utf-8");
  const parser = createSSEParser(onEvent);
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      parser.push(dec.decode(value, { stream: true }));
    }
    parser.push(dec.decode());
    parser.end();
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* ignore */
    }
  }
}
