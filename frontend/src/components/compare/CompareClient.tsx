"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, ChartBar, ChatCircleDots, Check, HouseLine, Minus, X } from "@phosphor-icons/react";
import { ChatPanel, type Suggestion } from "@/components/chat/ChatPanel";
import { ListingMedia } from "@/components/listing/ListingMedia";
import { listingHref } from "@/components/listing/ListingCard";
import { LinkButton } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import { num, propertyLabel, street, usd, usd2 } from "@/lib/format";
import type { Comparison, Listing, ListingComparison } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useChat } from "@/state/chat";
import { useCompare } from "@/state/compare";

type Row = {
  key: string;
  label: string;
  value: (l: ListingComparison) => number | null;
  show: (l: ListingComparison) => string;
  best?: "min" | "max";
  strong?: boolean;
};

const ROWS: Row[] = [
  { key: "beds", label: "Bedrooms", value: (l) => l.beds, show: (l) => (l.beds != null ? String(l.beds) : "Not listed"), best: "max" },
  { key: "baths", label: "Bathrooms", value: (l) => l.baths, show: (l) => (l.baths != null ? String(l.baths) : "Not listed"), best: "max" },
  { key: "sqft", label: "Interior size", value: (l) => l.sqft, show: (l) => (l.sqft != null ? `${num(l.sqft)} sqft` : "Not listed"), best: "max" },
  { key: "ppsf", label: "Price per sqft", value: (l) => l.price_per_sqft, show: (l) => (l.price_per_sqft != null ? usd(Math.round(l.price_per_sqft)) : "Not available"), best: "min" },
  { key: "year", label: "Year built", value: (l) => l.year_built, show: (l) => (l.year_built != null ? String(l.year_built) : "Not listed"), best: "max" },
  { key: "hoa", label: "HOA / month", value: (l) => l.hoa_fee, show: (l) => (l.hoa_fee != null ? usd(l.hoa_fee) : "Not listed"), best: "min" },
  { key: "monthly", label: "Est. monthly payment", value: (l) => l.est_monthly_payment, show: (l) => (l.est_monthly_payment != null ? usd2(l.est_monthly_payment) : "n/a"), best: "min", strong: true },
];

/** Indexes of the best value in a row. Nothing is highlighted if fewer than two values exist or all tie. */
function bestIndexes(values: (number | null)[], mode: "min" | "max"): Set<number> {
  const known = values.map((v, i) => [v, i] as const).filter(([v]) => v != null) as [number, number][];
  if (known.length < 2) return new Set();
  const nums = known.map(([v]) => v);
  if (new Set(nums).size === 1) return new Set();
  const target = mode === "min" ? Math.min(...nums) : Math.max(...nums);
  return new Set(known.filter(([v]) => v === target).map(([, i]) => i));
}

/** One sentence from the tool's own pros, e.g. "1208 Willow Lane has the lowest price." */
function summary(c: Comparison): string {
  const pick = (needle: string, phrase: string) => {
    const l = c.listings.find((x) => x.pros.some((p) => p.startsWith(needle)));
    return l ? `${street(l)} ${phrase}` : null;
  };
  const parts = [
    pick("Lowest list price", "has the lowest price."),
    pick("Most living space", "offers the most interior space."),
    pick("Newest build", "is the newest build."),
  ].filter(Boolean);
  return parts.length ? parts.join(" ") : "These homes are very close on the numbers we have. Check the details that matter most to you.";
}

const DOWN = [5, 10, 15, 20, 25, 30];
const control = "h-10 rounded-full border border-line bg-canvas px-4 text-sm font-medium text-ink outline-none focus:outline-none focus-visible:outline-none";

const toListing = (l: ListingComparison): Listing => ({
  id: l.id, address: l.address, city: l.city, state: l.state, zip: l.zip, lat: l.lat, lng: l.lng,
  price: l.price, beds: l.beds, baths: l.baths, sqft: l.sqft, year_built: l.year_built,
  property_type: l.property_type, hoa_fee: l.hoa_fee,
});

export function CompareClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const compare = useCompare();
  const chat = useChat();

  // ids are repeated ?id= params (listing ids contain commas); the URL wins, else the Explore tray
  const urlIds = useMemo(() => searchParams.getAll("id").filter(Boolean).slice(0, 3), [searchParams]);
  const ids = urlIds.length ? urlIds : compare.items.map((i) => i.id);
  const idsKey = ids.join("|");

  const defaults = useAsync((s) => api.mortgageDefaults(s), "mortgage-defaults");
  const [down, setDown] = useState(20);
  const [term, setTerm] = useState(30);
  const [rateIn, setRateIn] = useState<string | null>(null);
  const rate = rateIn ?? (defaults.data ? String(defaults.data.interest_rate) : "");

  // debounce the rate so typing doesn't fire a request per keystroke
  const rateNum = Number(rate);
  const validRate = rate !== "" && Number.isFinite(rateNum) && rateNum >= 0 && rateNum <= 30;
  const [debouncedRate, setDebouncedRate] = useState<number | null>(null);
  useEffect(() => {
    if (!validRate) return;
    const t = setTimeout(() => setDebouncedRate(rateNum), 350);
    return () => clearTimeout(t);
  }, [rateNum, validRate]);

  const enabled = ids.length >= 2 && debouncedRate !== null;
  const result = useAsync(
    (signal) => api.compare({ listing_ids: ids, down_payment_pct: down, term_years: term, interest_rate: debouncedRate ?? undefined }, signal),
    JSON.stringify([idsKey, down, term, debouncedRate]),
    enabled,
  );
  const cmp = result.data;

  const removeId = (id: string) => {
    compare.remove(id);
    const next = ids.filter((x) => x !== id);
    router.replace(
      next.length ? `/compare?${new URLSearchParams(next.map((x) => ["id", x])).toString()}` : "/compare",
      { scroll: false },
    );
  };

  // ---- the Ask Domi widget: closed by default; opens as a side panel ----
  const [chatOpen, setChatOpen] = useState(false);
  const { setInlineChat, setContext, clearContext } = chat;
  useEffect(() => {
    setInlineChat(true); // this page has its own widget, so the floating drawer steps aside
    return () => setInlineChat(false);
  }, [setInlineChat]);
  const compared = useMemo(() => cmp?.listings.map(toListing) ?? [], [cmp]);
  useEffect(() => {
    if (!chatOpen || compared.length === 0) return;
    setContext(compared);
    return () => clearContext();
  }, [chatOpen, compared, setContext, clearContext]);

  const suggestions: Suggestion[] = [
    "Explain the payment differences between these homes",
    "Which has the lowest monthly cost?",
    "Compare the price per square foot",
  ];
  const ask = (message: string) => {
    setChatOpen(true);
    void chat.send(message, { context: compared });
  };

  const best = (row: Row, list: ListingComparison[]) => (row.best ? bestIndexes(list.map(row.value), row.best) : new Set<number>());
  const priceBest = cmp ? bestIndexes(cmp.listings.map((l) => l.price), "min") : new Set<number>();

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 pb-24 pt-5 sm:px-8">
      <div className={chatOpen ? "lg:grid lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-5" : ""}>
        <div className="min-w-0">
          <h1 className="font-display text-3xl font-bold text-ink sm:text-4xl">Find your fit, side by side.</h1>
          <p className="mt-1 text-ink-soft">Compare up to three homes using listing facts and shared payment assumptions.</p>

          {ids.length < 2 ? (
            <EmptyState
              title="Pick two or three homes"
              body={ids.length === 1 ? "You have one home selected. Choose at least one more on Explore to compare." : "Tick the Compare box on any listing in Explore, then come back here."}
              actions={<LinkButton href="/explore">Browse homes</LinkButton>}
              compact
            />
          ) : (
            <>
              <section aria-label="Shared payment assumptions" className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-3 rounded-card border border-line bg-surface px-5 py-3.5">
                <h2 className="font-display text-xl font-bold text-ink">Payment assumptions</h2>
                <label className="flex items-center gap-2 text-sm text-ink-soft">
                  Down payment
                  <select value={down} onChange={(e) => setDown(Number(e.target.value))} className={control}>
                    {DOWN.map((d) => (<option key={d} value={d}>{d}%</option>))}
                  </select>
                </label>
                <label className="flex items-center gap-2 text-sm text-ink-soft">
                  Rate
                  <span className="focus-ring-within flex h-10 w-24 items-center rounded-full border border-line bg-canvas px-4">
                    <input inputMode="decimal" value={rate} onChange={(e) => setRateIn(e.target.value)} aria-invalid={rate !== "" && !validRate} className="min-w-0 flex-1 bg-transparent text-sm font-medium text-ink outline-none focus:outline-none focus-visible:outline-none" />
                    <span className="text-sm text-ink-soft" aria-hidden>%</span>
                  </span>
                </label>
                <label className="flex items-center gap-2 text-sm text-ink-soft">
                  Term
                  <select value={term} onChange={(e) => setTerm(Number(e.target.value))} className={control}>
                    <option value={30}>30 years</option>
                    <option value={15}>15 years</option>
                  </select>
                </label>
                <p className="ml-auto max-w-[34ch] text-xs text-muted">Includes configured taxes, insurance, HOA and PMI where they apply. Not a loan offer.</p>
              </section>
              {rate !== "" && !validRate && <p role="alert" className="mt-2 text-sm text-danger">Enter a rate between 0 and 30.</p>}

              {result.status === "error" && !cmp ? (
                <ErrorState error={result.error} onRetry={result.reload} title="We couldn't compare these homes" compact />
              ) : !cmp ? (
                <div className="mt-4 grid gap-4 md:grid-cols-3" aria-busy="true">
                  {ids.map((id) => (<Skeleton key={id} className="h-[480px] w-full rounded-card" />))}
                </div>
              ) : (
                <>
                  <ul
                    className={`mt-4 grid auto-cols-[minmax(270px,1fr)] grid-flow-col gap-4 overflow-x-auto pb-2 transition-opacity ${result.status === "loading" ? "opacity-60" : ""}`}
                  >
                    {cmp.listings.map((l, idx) => (
                      <li key={l.id} className="flex flex-col rounded-card border border-line bg-surface p-3 shadow-soft">
                        <div className="relative">
                          <ListingMedia listing={l} maxW={420} maxH={130} className="h-28 w-full rounded-2xl" />
                          <button type="button" onClick={() => removeId(l.id)} aria-label={`Remove ${street(l)} from the comparison`} className="absolute right-2 top-2 grid size-8 place-items-center rounded-full bg-surface text-ink shadow-soft hover:bg-sage">
                            <X size={14} weight="bold" aria-hidden />
                          </button>
                        </div>
                        <div className="px-1.5 pt-3">
                          <h3 className="font-display text-xl font-bold leading-tight text-ink">{street(l)}</h3>
                          <p className="text-sm text-muted">{l.city}, {l.state} &nbsp;{propertyLabel(l.property_type)}</p>
                          <p className={`-ml-2.5 mt-2 inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1 font-display text-2xl font-bold text-ink ${priceBest.has(idx) ? "bg-sage" : ""}`}>
                            {usd(l.price)}
                            {priceBest.has(idx) && (
                              <>
                                <Check size={18} weight="bold" className="text-sage-ink" aria-hidden />
                                <span className="sr-only">(lowest price)</span>
                              </>
                            )}
                          </p>
                        </div>

                        <dl className="mt-3 px-1.5">
                          {ROWS.map((row) => {
                            const isBest = best(row, cmp.listings).has(idx);
                            return (
                              <div key={row.key} className="flex items-center justify-between gap-3 py-1.5">
                                <dt className={`text-sm ${row.strong ? "font-semibold text-ink" : "text-muted"}`}>{row.label}</dt>
                                <dd className={`tabular inline-flex items-center gap-1 rounded-lg px-2 py-0.5 text-right text-[15px] ${row.strong ? "font-semibold" : "font-medium"} ${isBest ? "bg-sage text-sage-ink" : "text-ink"}`}>
                                  {row.show(l)}
                                  {isBest && (
                                    <>
                                      <Check size={14} weight="bold" aria-hidden />
                                      <span className="sr-only">(best value in this row)</span>
                                    </>
                                  )}
                                </dd>
                              </div>
                            );
                          })}
                        </dl>

                        <div className="mt-2 flex-1 border-t border-line px-1.5 pt-3">
                          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">Fact-based tradeoffs</h4>
                          <ul className="mt-2 space-y-1.5 text-sm text-ink-soft">
                            {l.pros.slice(0, 3).map((p) => (
                              <li key={p} className="flex gap-2"><Check size={15} weight="bold" className="mt-0.5 shrink-0 text-sage-ink" aria-hidden />{p}</li>
                            ))}
                            {l.cons.slice(0, 2).map((p) => (
                              <li key={p} className="flex gap-2"><Minus size={15} weight="bold" className="mt-0.5 shrink-0 text-muted" aria-hidden />{p}</li>
                            ))}
                            {l.pros.length === 0 && l.cons.length === 0 && <li className="text-muted">Too close to call on the listed facts.</li>}
                          </ul>
                        </div>

                        <Link href={listingHref(l.id)} className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-primary text-sm font-medium text-on-primary transition-[background-color,transform] hover:bg-primary-hover active:scale-[0.98]">
                          View property <ArrowRight size={15} weight="bold" aria-hidden />
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-muted">{cmp.payment_note}</p>

                  <section className="mt-5 flex flex-col gap-4 rounded-card bg-sage p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
                    <div className="flex items-start gap-4">
                      <span className="grid size-11 shrink-0 place-items-center rounded-full bg-surface text-primary"><HouseLine size={24} aria-hidden /></span>
                      <div>
                        <h2 className="font-display text-xl font-bold text-ink">Need help weighing the details?</h2>
                        <p className="mt-1 max-w-[60ch] text-ink-soft">{summary(cmp)}</p>
                      </div>
                    </div>
                    <div className="flex flex-col gap-3 sm:flex-row">
                      <button type="button" onClick={() => ask("Explain the payment differences between these homes")} className="inline-flex h-11 items-center justify-center gap-2 whitespace-nowrap rounded-full border border-primary/30 bg-surface px-5 text-sm font-medium text-ink transition-[background-color,transform] hover:bg-canvas active:scale-[0.98]">
                        <ChartBar size={16} aria-hidden /> Explain payment differences
                      </button>
                      <LinkButton href="/explore">Refine my search <ArrowRight size={16} weight="bold" aria-hidden /></LinkButton>
                    </div>
                  </section>
                </>
              )}
            </>
          )}
        </div>

        {chatOpen && (
          <aside aria-label="Ask Domi" className="mt-5 h-[560px] lg:sticky lg:top-24 lg:mt-0 lg:h-[calc(100dvh-7.5rem)]">
            <ChatPanel className="h-full" suggestions={suggestions} onClose={() => setChatOpen(false)} />
          </aside>
        )}
      </div>

      {!chatOpen && (
        <button
          type="button"
          onClick={() => setChatOpen(true)}
          className="fixed bottom-5 right-5 z-[var(--z-fab,35)] inline-flex h-12 items-center gap-2 rounded-full bg-primary px-5 text-[15px] font-medium text-on-primary shadow-lift transition-[background-color,transform] hover:bg-primary-hover active:scale-[0.97]"
        >
          <ChatCircleDots size={20} aria-hidden /> Ask Domi
        </button>
      )}

    </div>
  );
}
