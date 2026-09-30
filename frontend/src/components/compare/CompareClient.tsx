"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, ChartBar, Check, HouseLine, Minus, X } from "@phosphor-icons/react";
import { TileMap } from "@/components/map/TileMap";
import { listingHref } from "@/components/listing/ListingCard";
import { Button, LinkButton } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import { num, propertyLabel, street, usd, usd2 } from "@/lib/format";
import type { Comparison, ListingComparison } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useChat } from "@/state/chat";
import { useCompare } from "@/state/compare";

type Row = {
  key: string;
  label: string;
  value: (l: ListingComparison) => number | null;
  show: (l: ListingComparison) => string;
  best?: "min" | "max";
  bold?: boolean;
};

const ROWS: Row[] = [
  { key: "beds", label: "Bedrooms", value: (l) => l.beds, show: (l) => (l.beds != null ? String(l.beds) : "Not listed"), best: "max" },
  { key: "baths", label: "Bathrooms", value: (l) => l.baths, show: (l) => (l.baths != null ? String(l.baths) : "Not listed"), best: "max" },
  { key: "sqft", label: "Interior size", value: (l) => l.sqft, show: (l) => (l.sqft != null ? `${num(l.sqft)} sqft` : "Not listed"), best: "max" },
  { key: "ppsf", label: "Price per sqft", value: (l) => l.price_per_sqft, show: (l) => (l.price_per_sqft != null ? usd(Math.round(l.price_per_sqft)) : "Not available"), best: "min" },
  { key: "year", label: "Year built", value: (l) => l.year_built, show: (l) => (l.year_built != null ? String(l.year_built) : "Not listed"), best: "max" },
  { key: "hoa", label: "HOA / month", value: (l) => l.hoa_fee, show: (l) => (l.hoa_fee != null ? usd(l.hoa_fee) : "Not listed"), best: "min" },
  { key: "monthly", label: "Est. monthly payment", value: (l) => l.est_monthly_payment, show: (l) => (l.est_monthly_payment != null ? usd2(l.est_monthly_payment) : "n/a"), best: "min", bold: true },
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

export function CompareClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const compare = useCompare();
  const chat = useChat();

  const urlIds = useMemo(() => searchParams.getAll("id").filter(Boolean).slice(0, 3), [searchParams]);
  // The URL wins (shareable); otherwise use whatever was ticked on Explore.
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

  const { setInlineChat } = chat;
  useEffect(() => {
    setInlineChat(false);
  }, [setInlineChat]);

  const ask = (message: string) => {
    if (!cmp) return;
    chat.setContext(
      cmp.listings.map((l) => ({
        id: l.id, address: l.address, city: l.city, state: l.state, zip: l.zip, lat: l.lat, lng: l.lng,
        price: l.price, beds: l.beds, baths: l.baths, sqft: l.sqft, year_built: l.year_built,
        property_type: l.property_type, hoa_fee: l.hoa_fee,
      })),
    );
    chat.openDrawer();
    void chat.send(message);
  };

  const field = "h-11 w-full rounded-xl border border-line bg-canvas px-3 text-[15px] text-ink outline-none focus:border-primary";

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 pb-24 pt-8 sm:px-8">
      <h1 className="font-display text-4xl font-bold text-ink sm:text-5xl">Find your fit, side by side.</h1>
      <p className="mt-2 max-w-[60ch] text-lg text-ink-soft">
        Compare up to three homes using listing facts and shared payment assumptions.
      </p>

      {ids.length < 2 ? (
        <EmptyState
          title="Pick two or three homes"
          body={
            ids.length === 1
              ? "You have one home selected. Choose at least one more on Explore to compare."
              : "Tick the Compare box on any listing in Explore, then come back here."
          }
          actions={<LinkButton href="/explore">Browse homes</LinkButton>}
        />
      ) : (
        <>
          <section aria-label="Shared payment assumptions" className="mt-8 flex flex-wrap items-end gap-x-5 gap-y-4 rounded-card border border-line bg-surface p-5">
            <h2 className="font-display mr-2 text-2xl font-bold text-ink">Shared payment assumptions</h2>
            <div className="w-28">
              <label htmlFor="cmp-down" className="mb-1.5 block text-[13px] font-medium text-ink-soft">Down payment</label>
              <select id="cmp-down" value={down} onChange={(e) => setDown(Number(e.target.value))} className={field}>
                {DOWN.map((d) => (<option key={d} value={d}>{d}%</option>))}
              </select>
            </div>
            <div className="w-32">
              <label htmlFor="cmp-rate" className="mb-1.5 block text-[13px] font-medium text-ink-soft">Interest rate (%)</label>
              <input id="cmp-rate" inputMode="decimal" value={rate} onChange={(e) => setRateIn(e.target.value)} aria-invalid={rate !== "" && !validRate} className={field} />
            </div>
            <div className="w-32">
              <label htmlFor="cmp-term" className="mb-1.5 block text-[13px] font-medium text-ink-soft">Loan term</label>
              <select id="cmp-term" value={term} onChange={(e) => setTerm(Number(e.target.value))} className={field}>
                <option value={30}>30 years</option>
                <option value={15}>15 years</option>
              </select>
            </div>
            <p className="ml-auto max-w-[34ch] text-xs text-muted">
              Estimates include the configured taxes, insurance, HOA and PMI where they apply. Not a loan offer.
            </p>
          </section>
          {rate !== "" && !validRate && <p role="alert" className="mt-2 text-sm text-danger">Enter a rate between 0 and 30.</p>}

          {result.status === "error" && !cmp ? (
            <ErrorState error={result.error} onRetry={result.reload} title="We couldn't compare these homes" />
          ) : !cmp ? (
            <div className="mt-6 grid gap-4 md:grid-cols-3" aria-busy="true">
              {ids.map((id) => (<Skeleton key={id} className="h-[520px] w-full rounded-card" />))}
            </div>
          ) : (
            <>
              <div className={`mt-6 overflow-x-auto rounded-card border border-line bg-surface transition-opacity ${result.status === "loading" ? "opacity-60" : ""}`}>
                <table className="w-full min-w-[720px] border-collapse text-left">
                  <caption className="sr-only">Comparison of {cmp.listings.length} homes</caption>
                  <thead>
                    <tr>
                      <th scope="col" className="w-[17%] p-4 align-bottom text-sm font-medium text-muted">Property</th>
                      {cmp.listings.map((l) => (
                        <th key={l.id} scope="col" className="p-3 align-top font-normal">
                          <div className="relative">
                            <TileMap lat={l.lat} lng={l.lng} zoom={15} maxW={420} maxH={170} centerPin className="h-36 w-full rounded-2xl" />
                            <button type="button" onClick={() => removeId(l.id)} aria-label={`Remove ${street(l)}`} className="absolute right-2 top-2 grid size-8 place-items-center rounded-full bg-surface/95 text-ink shadow-soft hover:bg-sage">
                              <X size={14} weight="bold" aria-hidden />
                            </button>
                          </div>
                          <div className="mt-3 flex items-baseline justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate font-display text-xl font-bold text-ink">{street(l)}</p>
                              <p className="text-sm text-muted">{l.city}, {l.state}</p>
                              <p className="text-xs text-muted">{propertyLabel(l.property_type)}</p>
                            </div>
                            <p className={`shrink-0 rounded-xl px-2.5 py-1 font-display text-xl font-bold text-ink ${bestIndexes(cmp.listings.map((x) => x.price), "min").has(cmp.listings.indexOf(l)) ? "bg-sage" : ""}`}>
                              {usd(l.price)}
                            </p>
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {ROWS.map((row) => {
                      const best = row.best ? bestIndexes(cmp.listings.map(row.value), row.best) : new Set<number>();
                      return (
                        <tr key={row.key} className="align-middle">
                          <th scope="row" className={`px-4 py-3 text-sm ${row.bold ? "font-semibold text-ink" : "font-medium text-muted"}`}>{row.label}</th>
                          {cmp.listings.map((l, i) => (
                            <td key={l.id} className={`px-4 py-3 text-[15px] tabular ${row.bold ? "font-semibold" : ""} ${best.has(i) ? "bg-sage font-semibold text-sage-ink" : "text-ink"}`}>
                              {row.show(l)}
                              {best.has(i) && <span className="sr-only"> (best value in this row)</span>}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                    <tr className="align-top">
                      <th scope="row" className="px-4 py-4 text-sm font-medium text-muted">Fact-based tradeoffs</th>
                      {cmp.listings.map((l) => (
                        <td key={l.id} className="px-4 py-4">
                          <ul className="space-y-1.5 text-sm text-ink-soft">
                            {l.pros.slice(0, 3).map((p) => (
                              <li key={p} className="flex gap-2"><Check size={15} weight="bold" className="mt-0.5 shrink-0 text-sage-ink" aria-hidden />{p}</li>
                            ))}
                            {l.cons.slice(0, 2).map((p) => (
                              <li key={p} className="flex gap-2"><Minus size={15} weight="bold" className="mt-0.5 shrink-0 text-muted" aria-hidden />{p}</li>
                            ))}
                            {l.pros.length === 0 && l.cons.length === 0 && <li className="text-muted">Too close to call on the listed facts.</li>}
                          </ul>
                        </td>
                      ))}
                    </tr>
                    <tr>
                      <td />
                      {cmp.listings.map((l) => (
                        <td key={l.id} className="p-4">
                          <Link href={listingHref(l.id)} className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-full bg-primary text-sm font-medium text-on-primary transition-[background-color,transform] hover:bg-primary-hover active:scale-[0.98]">
                            View property <ArrowRight size={15} weight="bold" aria-hidden />
                          </Link>
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-muted">{cmp.payment_note}</p>

              <section className="mt-8 flex flex-col gap-5 rounded-card bg-sage p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8">
                <div className="flex items-start gap-4">
                  <span className="grid size-12 shrink-0 place-items-center rounded-full bg-surface text-primary"><HouseLine size={26} aria-hidden /></span>
                  <div>
                    <h2 className="font-display text-2xl font-bold text-ink">Need help weighing the details?</h2>
                    <p className="mt-1 max-w-[60ch] text-ink-soft">{summary(cmp)}</p>
                  </div>
                </div>
                <div className="flex flex-col gap-3 sm:flex-row">
                  <Button variant="secondary" onClick={() => ask("Explain the payment differences between these homes")}>
                    <ChartBar size={16} aria-hidden /> Explain payment differences
                  </Button>
                  <LinkButton href="/explore">Refine my search <ArrowRight size={16} weight="bold" aria-hidden /></LinkButton>
                </div>
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}
