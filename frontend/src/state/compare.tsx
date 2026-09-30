"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import type { Listing } from "@/lib/types";

export const MAX_COMPARE = 3;
const KEY = "domi-compare";

// ---- a tiny external store over localStorage (also syncs across browser tabs) ----
const listeners = new Set<() => void>();
const EMPTY: Listing[] = [];
let cachedRaw: string | null | undefined;
let cachedItems: Listing[] = EMPTY;

function read(): Listing[] {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(KEY);
  } catch {
    return cachedItems; // storage unavailable: keep what we have in memory
  }
  if (raw === cachedRaw) return cachedItems;
  cachedRaw = raw;
  try {
    cachedItems = raw ? (JSON.parse(raw) as Listing[]).slice(0, MAX_COMPARE) : EMPTY;
  } catch {
    cachedItems = EMPTY;
  }
  return cachedItems;
}

function write(items: Listing[]) {
  cachedItems = items.length ? items : EMPTY;
  try {
    const raw = items.length ? JSON.stringify(items) : null;
    if (raw) localStorage.setItem(KEY, raw);
    else localStorage.removeItem(KEY);
    cachedRaw = raw;
  } catch {
    cachedRaw = undefined; // private mode: the selection lives in memory for this visit
  }
  listeners.forEach((l) => l());
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  const onStorage = (e: StorageEvent) => e.key === KEY && cb();
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", onStorage);
  };
}

const subscribeNever = () => () => {};

interface CompareContextValue {
  items: Listing[];
  has: (id: string) => boolean;
  toggle: (l: Listing) => void;
  remove: (id: string) => void;
  clear: () => void;
  isFull: boolean;
  /** False during server render and hydration, so markup matches; true afterwards. */
  ready: boolean;
}

const CompareContext = createContext<CompareContextValue | null>(null);

export function CompareProvider({ children }: { children: ReactNode }) {
  const items = useSyncExternalStore(subscribe, read, () => EMPTY);
  const ready = useSyncExternalStore(subscribeNever, () => true, () => false);

  const toggle = useCallback((l: Listing) => {
    const cur = read();
    if (cur.some((x) => x.id === l.id)) write(cur.filter((x) => x.id !== l.id));
    else if (cur.length < MAX_COMPARE) write([...cur, l]);
  }, []);

  const value = useMemo<CompareContextValue>(
    () => ({
      items,
      has: (id) => items.some((x) => x.id === id),
      toggle,
      remove: (id) => write(read().filter((x) => x.id !== id)),
      clear: () => write([]),
      isFull: items.length >= MAX_COMPARE,
      ready,
    }),
    [items, toggle, ready],
  );

  return <CompareContext.Provider value={value}>{children}</CompareContext.Provider>;
}

export function useCompare(): CompareContextValue {
  const ctx = useContext(CompareContext);
  if (!ctx) throw new Error("useCompare must be used inside <CompareProvider>");
  return ctx;
}
