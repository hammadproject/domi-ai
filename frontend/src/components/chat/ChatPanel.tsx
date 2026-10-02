"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useNoMotion } from "@/lib/use-no-motion";
import {
  ArrowClockwise,
  ArrowUp,
  HouseLine,
  MapPin,
  Stop,
  Trash,
  X,
} from "@phosphor-icons/react";
import { RichText } from "@/components/chat/RichText";
import { Chip } from "@/components/ui/Chip";
import { TileMap, pinKindOf } from "@/components/map/TileMap";
import { listingHref } from "@/components/listing/ListingCard";
import { homeFacts, street, usd } from "@/lib/format";
import type { ChatListing, Listing } from "@/lib/types";
import { useChat, type ChatMessage } from "@/state/chat";

export type Suggestion = string | { label: string; message: string; context?: Listing[] };

const DEFAULT_SUGGESTIONS: Suggestion[] = [
  "3 bedroom homes in Austin under $550k",
  "What could I afford on a $120k income?",
  "Condos in Phoenix under $300k",
];

function MiniListing({ l, onShowOnMap }: { l: ChatListing; onShowOnMap?: (id: string) => void }) {
  return (
    <div className="flex gap-3 rounded-2xl border border-line bg-canvas p-2">
      <TileMap lat={l.lat} lng={l.lng} zoom={16} maxW={140} maxH={140} centerPin pinKind={pinKindOf(l.property_type)} className="size-[72px] shrink-0 rounded-xl" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-ink">
          <span className="text-ink-soft">#{l.rank}</span> {usd(l.price)}
        </p>
        <p className="text-[13px] leading-snug text-ink-soft">{street(l)}</p>
        <p className="truncate text-xs text-muted">{homeFacts(l)}</p>
        <div className="mt-1 flex gap-3 text-xs font-medium">
          <Link href={listingHref(l.id)} className="text-sage-ink underline underline-offset-2 hover:text-ink">
            View listing
          </Link>
          {onShowOnMap && (
            <button type="button" onClick={() => onShowOnMap(l.id)} className="inline-flex items-center gap-1 text-sage-ink hover:text-ink">
              <MapPin size={12} aria-hidden /> On map
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Bubble({
  m,
  isLast,
  onShowOnMap,
}: {
  m: ChatMessage;
  isLast: boolean;
  onShowOnMap?: (id: string) => void;
}) {
  const chat = useChat();
  const reduce = useNoMotion();
  const anim = reduce
    ? {}
    : { initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] as const } };

  if (m.role === "user") {
    return (
      <motion.div {...anim} className="flex flex-col items-end gap-1">
        {m.about && <span className="max-w-[85%] truncate text-xs text-muted">About {m.about}</span>}
        <p className="max-w-[88%] whitespace-pre-line rounded-2xl rounded-br-md bg-sage px-4 py-2.5 text-[15px] text-sage-ink">
          {m.text}
        </p>
      </motion.div>
    );
  }

  return (
    <motion.div {...anim} className="flex gap-3">
      <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-surface-2 text-primary">
        <HouseLine size={18} aria-hidden />
      </span>
      <div className="min-w-0 flex-1 space-y-3">
        {m.status === "error" ? (
          <div role="alert" className="rounded-2xl rounded-tl-md bg-danger-bg px-4 py-3 text-[15px] text-danger">
            <p>{m.error?.message ?? "Something went wrong."}</p>
            {isLast && (
              <button
                type="button"
                onClick={chat.retry}
                disabled={chat.busy}
                className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-danger/40 px-3 py-1 text-sm font-medium hover:bg-danger/10 disabled:opacity-50"
              >
                <ArrowClockwise size={14} aria-hidden /> Try again
              </button>
            )}
          </div>
        ) : (
          <>
            {m.text ? (
              <RichText text={m.text} />
            ) : (
              <p className="inline-flex items-center gap-1 text-ink-soft" aria-label="Domi is thinking">
                <span className="typing-dot" />
                <span className="typing-dot" />
                <span className="typing-dot" />
              </p>
            )}
            {m.listings && m.listings.length > 0 && (
              <div className="space-y-2">
                {m.listings.map((l) => (
                  <MiniListing key={l.id} l={l} onShowOnMap={onShowOnMap} />
                ))}
              </div>
            )}
            {m.degraded && m.status === "done" && (
              <p className="text-xs text-muted">Domi is busy, so this is a simple list without the usual summary.</p>
            )}
          </>
        )}
      </div>
    </motion.div>
  );
}

export function ChatPanel({
  variant = "panel",
  onClose,
  onShowOnMap,
  suggestions,
  filterChips,
  onResetFilters,
  className = "",
}: {
  variant?: "panel" | "drawer";
  onClose?: () => void;
  onShowOnMap?: (id: string) => void;
  suggestions?: Suggestion[];
  /** The filters currently applied on the page, as removable pills (same style as the filter bar). */
  filterChips?: { label: string; clear: () => void }[];
  onResetFilters?: () => void;
  className?: string;
}) {
  const chat = useChat();
  const [draft, setDraft] = useState("");
  const scroller = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const last = chat.messages.at(-1);

  // keep the newest text in view while it streams
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 160;
    if (nearBottom || chat.messages.length <= 2) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [chat.messages]);

  // when a home is chosen elsewhere (map pin, card), invite a question about it
  const contextKey = chat.context.map((c) => c.id).join(",");
  useEffect(() => {
    if (contextKey) inputRef.current?.focus({ preventScroll: true });
  }, [contextKey]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text || chat.busy) return;
    setDraft("");
    void chat.send(text);
  };

  const ctxLabel =
    chat.context.length === 1 ? street(chat.context[0]) : chat.context.length > 1 ? `${chat.context.length} homes` : null;

  const shown: Suggestion[] =
    suggestions ??
    (chat.context.length
      ? chat.context.length === 1
        ? ["Explain the monthly estimate for this home", "What is the price per square foot?", "How much is the HOA?"]
        : ["Compare these homes", "Which has the lowest monthly payment?"]
      : DEFAULT_SUGGESTIONS);

  return (
    <section
      aria-label="Ask Domi"
      className={`flex min-h-0 flex-col overflow-hidden bg-surface ${variant === "panel" ? "rounded-card border border-line shadow-soft" : ""} ${className}`}
    >
      <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
        <div className="flex items-center gap-2.5">
          <HouseLine size={28} className="text-primary" aria-hidden />
          <h2 className="font-display text-[26px] font-bold leading-none text-ink">Ask Domi</h2>
        </div>
        <div className="flex items-center gap-1.5">
          {chat.busy && (
            <span role="status" className="inline-flex items-center gap-1.5 rounded-full bg-sage px-3 py-1 text-sm text-sage-ink">
              <span className="size-2 rounded-full bg-primary" aria-hidden /> Thinking
            </span>
          )}
          {chat.messages.length > 0 && !chat.busy && (
            <button
              type="button"
              onClick={chat.reset}
              aria-label="Start a new conversation"
              title="Start over"
              className="grid size-9 place-items-center rounded-full text-ink-soft hover:bg-sage"
            >
              <Trash size={18} aria-hidden />
            </button>
          )}
          {onClose && (
            <button type="button" onClick={onClose} aria-label="Close" className="grid size-9 place-items-center rounded-full text-ink-soft hover:bg-sage">
              <X size={20} aria-hidden />
            </button>
          )}
        </div>
      </header>

      <div ref={scroller} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5" aria-live="polite">
        {chat.messages.length === 0 ? (
          <div className="py-6">
            <p className="font-display text-2xl font-bold text-ink">What are you looking for?</p>
            <p className="mt-2 text-[15px] text-ink-soft">
              Describe it the way you would to a friend. Domi answers only from the listings in its database.
            </p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {chat.messages.map((m, i) => (
              <Bubble key={m.id} m={m} isLast={i === chat.messages.length - 1} onShowOnMap={onShowOnMap} />
            ))}
          </AnimatePresence>
        )}
      </div>

      <div className="border-t border-line px-4 pb-4 pt-3">
        {!chat.busy && (last === undefined || last.status !== "streaming") && (chat.messages.length === 0 || chat.context.length > 0 || suggestions) && (
          <div className="mb-3 flex flex-wrap gap-2">
            {shown.map((sg) => {
              const label = typeof sg === "string" ? sg : sg.label;
              const message = typeof sg === "string" ? sg : sg.message;
              const context = typeof sg === "string" ? undefined : sg.context;
              return (
              <button
                key={label}
                type="button"
                onClick={() => void chat.send(message, context ? { context } : undefined)}
                className="rounded-full border border-line bg-canvas px-3.5 py-1.5 text-left text-[13px] font-medium text-ink-soft transition-colors hover:bg-sage hover:text-ink"
              >
                {label}
              </button>
              );
            })}
          </div>
        )}

        {filterChips && filterChips.length > 0 && (
          <ul className="mb-2.5 flex items-center gap-1.5 overflow-x-auto pb-1" aria-label="Active filters">
            {filterChips.map((c) => (
              <li key={c.label} className="shrink-0 whitespace-nowrap">
                <Chip onRemove={c.clear} className="!py-1 text-[13px]">{c.label}</Chip>
              </li>
            ))}
            {onResetFilters && (
              <li className="shrink-0">
                <button type="button" onClick={onResetFilters} className="whitespace-nowrap px-1.5 text-xs font-medium text-sage-ink underline underline-offset-4 hover:text-ink">
                  Reset
                </button>
              </li>
            )}
          </ul>
        )}

        {ctxLabel && (
          <div className="mb-2 inline-flex max-w-full items-center gap-2 rounded-full bg-sage px-3 py-1 text-sm text-sage-ink">
            <MapPin size={14} aria-hidden />
            <span className="truncate">Asking about {ctxLabel}</span>
            <button type="button" onClick={chat.clearContext} aria-label="Stop asking about this home" className="-mr-1 rounded-full p-0.5 hover:bg-sage-strong">
              <X size={12} weight="bold" aria-hidden />
            </button>
          </div>
        )}

        <form onSubmit={submit} className="flex items-center gap-2">
          <label className="sr-only" htmlFor={`chat-input-${variant}`}>
            Message Domi
          </label>
          <input
            id={`chat-input-${variant}`}
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={1000}
            placeholder={chat.messages.length ? "Refine your search…" : "Try: 3 bed under $500k in Dallas"}
            autoComplete="off"
            className="h-12 min-w-0 flex-1 rounded-full border border-line bg-canvas px-5 text-[15px] text-ink outline-none transition-colors placeholder:text-muted focus:border-primary"
          />
          {chat.busy ? (
            <button
              type="button"
              onClick={chat.stop}
              aria-label="Stop response"
              className="grid size-12 shrink-0 place-items-center rounded-full border border-line bg-surface text-ink hover:bg-sage"
            >
              <Stop size={18} weight="fill" aria-hidden />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!draft.trim()}
              aria-label="Send message"
              className="grid size-12 shrink-0 place-items-center rounded-full bg-primary text-on-primary transition-[background-color,transform] hover:bg-primary-hover active:scale-95 disabled:opacity-40"
            >
              <ArrowUp size={20} weight="bold" aria-hidden />
            </button>
          )}
        </form>
        <p className="mt-1.5 px-1 text-[11px] leading-snug text-muted">
          Please don&apos;t share personal details. Estimates are illustrative, not loan offers.
        </p>
      </div>
    </section>
  );
}
