"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  CaretLeft,
  CaretRight,
  ChatCircleDots,
  Columns,
  ListBullets,
  MapTrifold,
  SquaresFour,
  X,
} from "@phosphor-icons/react";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { CompareTray } from "@/components/explore/CompareTray";
import { FilterBar, SORTS } from "@/components/explore/FilterBar";
import { ListingCard, listingHref } from "@/components/listing/ListingCard";
import { ListingMap } from "@/components/map/ListingMap";
import { TileMap } from "@/components/map/TileMap";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { ListingCardSkeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import { DEFAULT_FILTERS, filtersToParams, parseFilters, toListingQuery, type ExploreFilters } from "@/lib/filters";
import { cityLine, homeFacts, street, usd } from "@/lib/format";
import type { Listing } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useChat } from "@/state/chat";
import { useCompare } from "@/state/compare";

type Tab = "list" | "map" | "chat";
const SPLIT_PAGE_SIZE = 50;
const GRID_PAGE_SIZE = 12;

function Pagination({ page, pages, onPage }: { page: number; pages: number; onPage: (p: number) => void }) {
  if (pages <= 1) return null;
  const nums = Array.from({ length: pages }, (_, i) => i + 1).filter(
    (n) => n === 1 || n === pages || Math.abs(n - page) <= 1,
  );
  return (
    <nav aria-label="Pagination" className="flex items-center justify-center gap-1.5 py-4">
      <button type="button" onClick={() => onPage(page - 1)} disabled={page <= 1} className="inline-flex h-10 items-center gap-1 rounded-full px-3 text-sm font-medium text-ink-soft hover:bg-sage disabled:opacity-40">
        <CaretLeft size={14} weight="bold" aria-hidden /> Previous
      </button>
      {nums.map((n, i) => (
        <span key={n} className="flex items-center gap-1.5">
          {i > 0 && n - nums[i - 1] > 1 && <span className="text-muted" aria-hidden>…</span>}
          <button
            type="button"
            onClick={() => onPage(n)}
            aria-current={n === page ? "page" : undefined}
            className={`grid size-10 place-items-center rounded-full text-sm font-medium ${n === page ? "bg-primary text-on-primary" : "text-ink-soft hover:bg-sage"}`}
          >
            {n}
          </button>
        </span>
      ))}
      <button type="button" onClick={() => onPage(page + 1)} disabled={page >= pages} className="inline-flex h-10 items-center gap-1 rounded-full px-3 text-sm font-medium text-ink-soft hover:bg-sage disabled:opacity-40">
        Next <CaretRight size={14} weight="bold" aria-hidden />
      </button>
    </nav>
  );
}

function SelectedPreview({ l, onClose, onAsk }: { l: Listing; onClose: () => void; onAsk: () => void }) {
  return (
    <div className="absolute inset-x-3 bottom-3 z-[600] flex gap-3 rounded-[20px] border border-line bg-surface p-3 shadow-lift">
      <TileMap lat={l.lat} lng={l.lng} zoom={16} maxW={160} maxH={160} centerPin className="size-[84px] shrink-0 rounded-2xl" />
      <div className="min-w-0 flex-1">
        <p className="font-display text-2xl font-bold leading-none text-ink">{usd(l.price)}</p>
        <p className="mt-1 truncate text-sm font-medium text-ink">{street(l)}</p>
        <p className="truncate text-xs text-muted">{cityLine(l)}</p>
        <p className="truncate text-xs text-ink-soft">{homeFacts(l)}</p>
        <div className="mt-2 flex gap-2">
          <button type="button" onClick={onAsk} className="inline-flex h-8 items-center gap-1.5 rounded-full border border-line px-3 text-xs font-medium text-ink hover:bg-sage">
            <ChatCircleDots size={14} aria-hidden /> Ask Domi
          </button>
          <Link href={listingHref(l.id)} className="inline-flex h-8 items-center gap-1.5 rounded-full bg-primary px-3 text-xs font-medium text-on-primary hover:bg-primary-hover">
            View details <ArrowRight size={12} weight="bold" aria-hidden />
          </Link>
        </div>
      </div>
      <button type="button" onClick={onClose} aria-label="Close preview" className="absolute right-2 top-2 grid size-7 place-items-center rounded-full text-ink-soft hover:bg-sage">
        <X size={14} weight="bold" aria-hidden />
      </button>
    </div>
  );
}

export function ExploreClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const chat = useChat();
  const compare = useCompare();

  const filters = useMemo(() => parseFilters(new URLSearchParams(searchParams.toString())), [searchParams]);
  const focusParam = searchParams.get("focus");

  const [moreOpen, setMoreOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("list");
  const [selectedId, setSelectedId] = useState<string | null>(focusParam);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const split = filters.view === "split";
  const pageSize = split ? SPLIT_PAGE_SIZE : GRID_PAGE_SIZE;

  const update = useCallback(
    (patch: Partial<ExploreFilters>, keepPage = false) => {
      const next = { ...filters, ...patch, page: keepPage ? (patch.page ?? filters.page) : 1 };
      router.replace(`/explore?${filtersToParams(next).toString()}`, { scroll: false });
    },
    [filters, router],
  );
  const reset = () => update({ ...DEFAULT_FILTERS, view: filters.view, sort: filters.sort });

  const cities = useAsync((signal) => api.cities(signal), "cities");
  const query = toListingQuery(filters, pageSize);
  const results = useAsync((signal) => api.listings(query, signal), JSON.stringify(query));
  const items = useMemo(() => results.data?.items ?? [], [results.data]);

  // A question from the landing page (?q=...) is asked once, then removed from the URL.
  const q = searchParams.get("q");
  const askedRef = useRef<string | null>(null);
  const { send: sendChat } = chat;
  useEffect(() => {
    if (!q || askedRef.current === q) return;
    askedRef.current = q;
    const next = new URLSearchParams(searchParams.toString());
    next.delete("q");
    router.replace(`/explore?${next.toString()}`, { scroll: false });
    setTab("chat");
    void sendChat(q);
  }, [q, searchParams, router, sendChat]);

  // When Domi runs a search, the filter bar and list follow what it actually found.
  const syncedRef = useRef<string | null>(chat.lastSearch?.messageId ?? null);
  const lastSearch = chat.lastSearch;
  useEffect(() => {
    if (!lastSearch || syncedRef.current === lastSearch.messageId) return;
    syncedRef.current = lastSearch.messageId;
    const f = lastSearch.filters;
    const num = (k: string) => (typeof f[k] === "number" ? (f[k] as number) : undefined);
    const next: ExploreFilters = {
      ...DEFAULT_FILTERS,
      view: filters.view,
      sort: filters.sort,
      city: typeof f.city === "string" ? f.city : undefined,
      price_min: num("price_min"),
      price_max: num("price_max"),
      beds_min: num("beds_min"),
      baths_min: num("baths_min"),
      sqft_min: num("sqft_min"),
      property_type: typeof f.property_type === "string" ? f.property_type : undefined,
    };
    router.replace(`/explore?${filtersToParams(next).toString()}`, { scroll: false });
  }, [lastSearch, filters.view, filters.sort, router]);

  // Tell the chat which filters are on screen, so Domi builds on what you see.
  const { setUiFilters } = chat;
  const uiFilters = useMemo(() => {
    const out: Record<string, string | number> = {};
    for (const k of ["city", "price_min", "price_max", "beds_min", "baths_min", "sqft_min", "property_type"] as const) {
      const v = filters[k];
      if (v !== undefined) out[k] = v;
    }
    return out;
  }, [filters]);
  useEffect(() => {
    setUiFilters(uiFilters);
    return () => setUiFilters(null);
  }, [uiFilters, setUiFilters]);

  // the floating chat button hides while the chat is shown inline
  const { setInlineChat } = chat;
  useEffect(() => {
    setInlineChat(split);
    return () => setInlineChat(false);
  }, [split, setInlineChat]);

  // everything we can show on the map: the page of results plus homes from Domi's answers
  const chatListings = useMemo(
    () => chat.messages.flatMap((m) => m.listings ?? []),
    [chat.messages],
  );
  const mapListings = useMemo(() => {
    const seen = new Set(items.map((i) => i.id));
    const extra = chatListings.filter((l) => !seen.has(l.id) && seen.add(l.id));
    return [...items, ...extra];
  }, [items, chatListings]);
  const byId = useMemo(() => new Map(mapListings.map((l) => [l.id, l])), [mapListings]);
  const selected = selectedId ? (byId.get(selectedId) ?? null) : null;

  const select = useCallback(
    (id: string) => {
      setSelectedId(id);
      const l = byId.get(id);
      if (l) chat.setContext([l]); // a clicked pin or card becomes what Domi is asked about
    },
    [byId, chat],
  );
  const deselect = () => {
    if (selected && chat.context.length === 1 && chat.context[0].id === selected.id) chat.clearContext();
    setSelectedId(null);
  };

  // scroll the list to a home picked on the map
  useEffect(() => {
    if (!selectedId) return;
    const el = listRef.current?.querySelector(`[data-listing-id="${CSS.escape(selectedId)}"]`);
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedId]);

  const askAbout = (l: Listing) => {
    chat.setContext([l]);
    if (split) setTab("chat");
    else chat.openDrawer();
  };

  const fitKey = `${items.map((i) => i.id).join(",")}#${chat.highlightIds.join(",")}`;
  const total = results.data?.total ?? 0;
  const loading = results.status === "loading" && !results.data;
  const failed = results.status === "error" && !results.data;
  const empty = results.status === "success" && items.length === 0;

  const cardFor = (l: Listing, variant: "list" | "grid") => (
    <ListingCard
      key={l.id}
      listing={l}
      variant={variant}
      selected={selectedId === l.id}
      picked={chat.highlightIds.includes(l.id)}
      compareChecked={compare.has(l.id)}
      compareDisabled={compare.isFull}
      onCompareToggle={() => compare.toggle(l)}
      onSelect={() => select(l.id)}
      onHover={setHoveredId}
      onAsk={variant === "grid" ? () => askAbout(l) : undefined}
    />
  );

  const emptyState = (
    <EmptyState
      title="No exact matches yet"
      body="Try a higher budget, fewer bedrooms, or a different city. You can also ask Domi to loosen things for you."
      actions={
        <>
          <Button onClick={() => setMoreOpen(true)}>Edit filters</Button>
          <Button variant="secondary" onClick={reset}>Reset search</Button>
        </>
      }
    />
  );
  const errorState = <ErrorState error={results.error} onRetry={results.reload} title="We couldn't load homes" />;

  const header = (
    <div className="flex flex-wrap items-center justify-between gap-3 px-1 pb-3">
      <h2 className="font-display text-3xl font-bold text-ink" aria-live="polite">
        {loading ? "Finding homes" : failed ? "Homes" : `${total.toLocaleString("en-US")} ${total === 1 ? "matching home" : "matching homes"}`}
      </h2>
      <div className="flex items-center gap-2">
        <Select label="Sort results" value={filters.sort} options={SORTS} onChange={(v) => update({ sort: v as ExploreFilters["sort"] })} className="min-w-[11.5rem]" />
      </div>
    </div>
  );

  return (
    <div className={`mx-auto w-full max-w-[1400px] px-4 pt-8 sm:px-8 ${split ? "pb-28 lg:pb-24" : "pb-28"}`}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl font-bold text-ink sm:text-5xl">Let&apos;s find your place.</h1>
          <p className="mt-2 text-lg text-ink-soft">Search, refine, and explore with Domi.</p>
        </div>
        <div className="hidden items-center rounded-full border border-line bg-surface p-1 sm:flex" role="group" aria-label="View">
          <button type="button" onClick={() => update({ view: "split" }, true)} aria-pressed={split} className={`inline-flex h-9 items-center gap-1.5 rounded-full px-3.5 text-sm font-medium ${split ? "bg-sage text-sage-ink" : "text-ink-soft hover:text-ink"}`}>
            <Columns size={16} aria-hidden /> Map &amp; chat
          </button>
          <button type="button" onClick={() => update({ view: "grid" }, true)} aria-pressed={!split} className={`inline-flex h-9 items-center gap-1.5 rounded-full px-3.5 text-sm font-medium ${!split ? "bg-sage text-sage-ink" : "text-ink-soft hover:text-ink"}`}>
            <SquaresFour size={16} aria-hidden /> Grid
          </button>
        </div>
      </div>

      <div className="mt-6">
        <FilterBar filters={filters} cities={cities.data} onChange={(p) => update(p)} onReset={reset} moreOpen={moreOpen} onToggleMore={() => setMoreOpen((v) => !v)} />
      </div>

      {!split && (
        <div className="mt-8">
          {header}
          {failed ? errorState : empty ? emptyState : (
            <>
              <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                {loading
                  ? Array.from({ length: 6 }, (_, i) => <ListingCardSkeleton key={i} variant="grid" />)
                  : items.map((l) => cardFor(l, "grid"))}
              </div>
              <Pagination page={results.data?.page ?? 1} pages={results.data?.pages ?? 1} onPage={(p) => update({ page: p }, true)} />
            </>
          )}
        </div>
      )}

      {split && (
        <div className="mt-6 lg:grid lg:h-[calc(100dvh-19.5rem)] lg:min-h-[640px] lg:grid-cols-[minmax(330px,410px)_minmax(0,1fr)_minmax(330px,390px)] lg:gap-4">
          {/* list */}
          <section aria-label="Results" className={`${tab === "list" ? "block" : "hidden"} min-h-0 flex-col lg:flex`}>
            <div className="flex min-h-0 flex-1 flex-col rounded-card border border-line bg-canvas/50 p-3 lg:overflow-hidden">
              {header}
              <div ref={listRef} className="min-h-0 flex-1 space-y-3 lg:overflow-y-auto lg:pr-1">
                {failed ? errorState : empty ? emptyState : loading
                  ? Array.from({ length: 4 }, (_, i) => <ListingCardSkeleton key={i} />)
                  : items.map((l) => cardFor(l, "list"))}
                {!loading && !failed && !empty && (
                  <Pagination page={results.data?.page ?? 1} pages={results.data?.pages ?? 1} onPage={(p) => update({ page: p }, true)} />
                )}
              </div>
            </div>
          </section>

          {/* map */}
          <section aria-label="Map" className={`${tab === "map" ? "block" : "hidden"} h-[calc(100dvh-16rem)] min-h-[420px] lg:block lg:h-auto`}>
            <div className="relative h-full overflow-hidden rounded-card border border-line">
              <ListingMap
                listings={mapListings}
                pickedIds={chat.highlightIds}
                selectedId={selectedId}
                hoveredId={hoveredId}
                onSelect={select}
                fitKey={fitKey}
                className="h-full w-full"
              />
              {selected && <SelectedPreview l={selected} onClose={deselect} onAsk={() => askAbout(selected)} />}
            </div>
          </section>

          {/* chat */}
          <section aria-label="Ask Domi" className={`${tab === "chat" ? "block" : "hidden"} h-[calc(100dvh-14rem)] min-h-[460px] lg:block lg:h-auto`}>
            <ChatPanel
              className="h-full"
              onShowOnMap={(id) => {
                setSelectedId(id);
                setTab("map");
              }}
            />
          </section>
        </div>
      )}

      <CompareTray lifted={split} />

      {split && (
        <nav aria-label="Switch panel" className="fixed inset-x-0 bottom-0 z-[var(--z-tabs,36)] border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] lg:hidden">
          <ul className="mx-auto flex max-w-md items-stretch justify-around px-3 py-2">
            {([
              ["list", "List", ListBullets],
              ["map", "Map", MapTrifold],
              ["chat", "Ask Domi", ChatCircleDots],
            ] as const).map(([id, label, Icon]) => (
              <li key={id} className="flex-1">
                <button
                  type="button"
                  onClick={() => setTab(id)}
                  aria-current={tab === id ? "page" : undefined}
                  className={`flex w-full flex-col items-center gap-0.5 rounded-2xl py-1.5 text-xs font-medium ${tab === id ? "bg-sage text-sage-ink" : "text-ink-soft"}`}
                >
                  <Icon size={22} weight={tab === id ? "fill" : "regular"} aria-hidden />
                  {label}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </div>
  );
}
