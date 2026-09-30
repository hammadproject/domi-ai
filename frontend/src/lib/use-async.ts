"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

export type AsyncState<T> =
  | { status: "loading"; data: T | undefined; error: undefined }
  | { status: "success"; data: T; error: undefined }
  | { status: "error"; data: T | undefined; error: ApiError };

interface Done<T> {
  requestKey: string;
  data: T | undefined; // last successful data, kept while the next request loads
  error: ApiError | undefined;
}

/**
 * Runs `fn` whenever `key` changes; aborts the in-flight request when it does. Status is
 * derived (a result only counts if it answers the *current* key), so there is no "set loading"
 * step inside the effect. The previous data stays visible while the next request loads.
 * `reload()` retries after a failure.
 */
export function useAsync<T>(
  fn: (signal: AbortSignal) => Promise<T>,
  key: string,
  enabled = true,
): AsyncState<T> & { reload: () => void } {
  const [done, setDone] = useState<Done<T> | null>(null);
  const [nonce, setNonce] = useState(0);
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn; // declared before the fetch effect, so it is current when that runs
  });

  const requestKey = `${key}#${nonce}`;
  useEffect(() => {
    if (!enabled) return;
    const ctrl = new AbortController();
    fnRef
      .current(ctrl.signal)
      .then((data) => setDone({ requestKey, data, error: undefined }))
      .catch((e) => {
        if ((e as Error).name === "AbortError") return;
        const error = e instanceof ApiError ? e : new ApiError(String(e), 0, "unknown");
        setDone((prev) => ({ requestKey, data: prev?.data, error }));
      });
    return () => ctrl.abort();
  }, [requestKey, enabled]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const current = done && done.requestKey === requestKey ? done : null;

  if (current?.error) return { status: "error", data: current.data, error: current.error, reload };
  if (current) return { status: "success", data: current.data as T, error: undefined, reload };
  return { status: "loading", data: done?.data, error: undefined, reload };
}
