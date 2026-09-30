import { API_URL, ApiError, toApiError } from "./api";
import type { ChatEvent } from "./types";

export interface ChatRequest {
  message: string;
  session_id?: string;
  context_listing_ids?: string[];
  /** the filters currently shown on the page; they replace Domi's remembered ones */
  filters?: Record<string, string | number>;
}

/**
 * POST /api/chat and read the Server-Sent Events stream. (EventSource can't POST, so the
 * stream is parsed by hand.) Pre-stream failures (422, 429, 503) throw an ApiError; failures
 * during the turn arrive as an `error` event.
 */
export async function streamChat(
  req: ChatRequest,
  onEvent: (e: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(req),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("Network error", 0, "network");
  }
  if (!res.ok) throw await toApiError(res);
  if (!res.body) throw new ApiError("Empty response", 502, "empty_stream");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const flush = (block: string) => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trim());
    }
    if (!data.length) return;
    try {
      const payload = JSON.parse(data.join("\n"));
      onEvent({ type: event, ...payload } as ChatEvent);
    } catch {
      /* ignore a malformed block rather than killing the stream */
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      flush(buffer.slice(0, sep));
      buffer = buffer.slice(sep + 2);
    }
  }
  if (buffer.trim()) flush(buffer);
}
