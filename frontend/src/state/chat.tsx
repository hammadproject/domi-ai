"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ApiError } from "@/lib/api";
import { streamChat } from "@/lib/chat-stream";
import type { ChatEvent, ChatListing, Listing } from "@/lib/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  status: "streaming" | "done" | "error";
  listings?: ChatListing[];
  error?: { message: string; code: string; retryAfter: number | null };
  degraded?: boolean;
  refused?: boolean;
  /** Address of the home the user was asking about, when one was in context. */
  about?: string;
}

export interface SearchSync {
  /** id of the assistant message that produced it, so each search is applied once */
  messageId: string;
  filters: Record<string, string | number>;
  relaxations: string[];
}

interface ChatContextValue {
  messages: ChatMessage[];
  busy: boolean;
  /** Homes Domi is currently being asked about (detail page, map pin, compare tray). */
  context: Listing[];
  setContext: (listings: Listing[]) => void;
  /** A page that shows search filters registers them here; they go with every message. */
  setUiFilters: (filters: Record<string, string | number> | null) => void;
  clearContext: () => void;
  /** Ids of the listings in Domi's latest answer, used to highlight map pins. */
  highlightIds: string[];
  /** The latest search Domi ran: lets a page sync its filters to what the chat found. */
  lastSearch: SearchSync | null;
  send: (text: string, opts?: { context?: Listing[] }) => Promise<void>;
  stop: () => void;
  retry: () => void;
  reset: () => void;
  drawerOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
  /** True while a page shows the chat inline (Explore split view): the floating drawer hides. */
  inlineChat: boolean;
  setInlineChat: (v: boolean) => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

const SESSION_KEY = "domi-session";

function sessionId(): string {
  try {
    const existing = sessionStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const fresh = crypto.randomUUID().replace(/-/g, "");
    sessionStorage.setItem(SESSION_KEY, fresh);
    return fresh;
  } catch {
    return crypto.randomUUID().replace(/-/g, "");
  }
}

let counter = 0;
const nextId = () => `m${Date.now().toString(36)}${(counter++).toString(36)}`;

/** Ids of the listings in the newest assistant answer that had any. */
function latestPickIds(messages: ChatMessage[]): string[] {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role === "assistant" && m.listings && m.listings.length) return m.listings.map((x) => x.id);
  }
  return [];
}

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const [context, setContextState] = useState<Listing[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [inlineChat, setInlineChat] = useState(false);
  const [lastSearch, setLastSearch] = useState<SearchSync | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastRequest = useRef<{ text: string; context: Listing[] } | null>(null);
  const sessionRef = useRef<string | null>(null);
  const uiFiltersRef = useRef<Record<string, string | number> | null>(null);

  const patch = useCallback((id: string, fn: (m: ChatMessage) => ChatMessage) => {
    setMessages((all) => all.map((m) => (m.id === id ? fn(m) : m)));
  }, []);

  const send = useCallback(
    async (text: string, opts?: { context?: Listing[] }) => {
      const clean = text.trim();
      if (!clean || busy) return;
      const ctx = (opts?.context ?? context).slice(0, 3);
      lastRequest.current = { text: clean, context: ctx };
      sessionRef.current ??= sessionId();

      const userMsg: ChatMessage = {
        id: nextId(),
        role: "user",
        text: clean,
        status: "done",
        about: ctx.length === 1 ? ctx[0].address : ctx.length > 1 ? `${ctx.length} homes` : undefined,
      };
      const botId = nextId();
      setMessages((all) => [...all, userMsg, { id: botId, role: "assistant", text: "", status: "streaming" }]);
      setBusy(true);

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      const onEvent = (e: ChatEvent) => {
        if (e.type === "listings") {
          patch(botId, (m) => ({ ...m, listings: e.listings }));
        } else if (e.type === "token") {
          patch(botId, (m) => ({ ...m, text: m.text + e.text }));
        } else if (e.type === "done") {
          patch(botId, (m) => ({ ...m, status: "done", degraded: e.degraded, refused: e.refused }));
          if (e.filters) setLastSearch({ messageId: botId, filters: e.filters, relaxations: e.relaxations ?? [] });
        } else if (e.type === "error") {
          patch(botId, (m) => ({
            ...m,
            status: "error",
            error: { message: e.message, code: e.code, retryAfter: e.retry_after ?? null },
          }));
        }
      };

      try {
        await streamChat(
          {
            message: clean,
            session_id: sessionRef.current,
            context_listing_ids: ctx.map((l) => l.id),
            ...(uiFiltersRef.current ? { filters: uiFiltersRef.current } : {}),
          },
          onEvent,
          ctrl.signal,
        );
        // a stream that ended without `done` or `error` (connection dropped mid-answer)
        patch(botId, (m) =>
          m.status === "streaming"
            ? m.text
              ? { ...m, status: "done" }
              : { ...m, status: "error", error: { message: "The answer was cut off. Please try again.", code: "cut_off", retryAfter: null } }
            : m,
        );
      } catch (e) {
        if ((e as Error).name === "AbortError") {
          patch(botId, (m) => ({ ...m, status: "done", text: m.text || "Stopped." }));
        } else {
          const err = e instanceof ApiError ? e : new ApiError(String(e), 0, "unknown");
          patch(botId, (m) => ({
            ...m,
            status: "error",
            error: { message: err.friendly, code: err.code, retryAfter: err.retryAfter },
          }));
        }
      } finally {
        abortRef.current = null;
        setBusy(false);
      }
    },
    [busy, context, patch],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  // These are called from other components' effects, so their identity must never change
  // (a new function each render would re-run those effects forever).
  const setContext = useCallback((l: Listing[]) => setContextState(l.slice(0, 3)), []);
  const clearContext = useCallback(() => setContextState([]), []);
  const setUiFilters = useCallback((f: Record<string, string | number> | null) => {
    uiFiltersRef.current = f;
  }, []);
  const openDrawer = useCallback(() => setDrawerOpen(true), []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  const retry = useCallback(() => {
    const last = lastRequest.current;
    if (!last || busy) return;
    // drop the failed exchange, then ask again
    setMessages((all) => all.slice(0, -2));
    void send(last.text, { context: last.context });
  }, [busy, send]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setContextState([]);
    setLastSearch(null);
    try {
      sessionStorage.removeItem(SESSION_KEY);
    } catch {
      /* storage unavailable */
    }
    sessionRef.current = null;
  }, []);

  const highlightIds = useMemo(() => latestPickIds(messages), [messages]);

  const value = useMemo<ChatContextValue>(
    () => ({
      messages,
      busy,
      context,
      setContext,
      setUiFilters,
      clearContext,
      highlightIds,
      lastSearch,
      send,
      stop,
      retry,
      reset,
      drawerOpen,
      openDrawer,
      closeDrawer,
      inlineChat,
      setInlineChat,
    }),
    [
      messages, busy, context, highlightIds, lastSearch, send, stop, retry, reset, drawerOpen,
      inlineChat, setContext, setUiFilters, clearContext, openDrawer, closeDrawer,
    ],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used inside <ChatProvider>");
  return ctx;
}
