"use client";

import Link from "next/link";
import { useEffect, useMemo } from "react";
import { ArrowLeft, Bathtub, Bed, CalendarBlank, ChatCircleDots, Check, Ruler, Scales, Tree } from "@phosphor-icons/react";
import { ChatPanel, type Suggestion } from "@/components/chat/ChatPanel";
import { PaymentCard } from "@/components/detail/PaymentCard";
import { TileMap } from "@/components/map/TileMap";
import { Button, LinkButton } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import { cityLine, num, propertyLabel, street, usd } from "@/lib/format";
import type { ListingDetail } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useChat } from "@/state/chat";
import { useCompare } from "@/state/compare";

function DetailSkeleton() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-8 sm:px-8" aria-busy="true">
      <Skeleton className="h-4 w-56" />
      <Skeleton className="mt-6 h-14 w-2/3 max-w-xl" />
      <Skeleton className="mt-4 h-5 w-96 max-w-full" />
      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_380px]">
        <Skeleton className="h-[420px] w-full rounded-card" />
        <Skeleton className="h-[420px] w-full rounded-card" />
      </div>
    </div>
  );
}

function Fact({ icon, value, label }: { icon: React.ReactNode; value: string; label: string }) {
  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <span className="grid size-11 shrink-0 place-items-center rounded-full bg-sage text-sage-ink">{icon}</span>
      <span>
        <span className="block text-lg font-semibold leading-tight text-ink">{value}</span>
        <span className="block text-[13px] text-muted">{label}</span>
      </span>
    </li>
  );
}

export function DetailClient({ id }: { id: string }) {
  const listing = useAsync((s) => api.listing(id, s), `listing:${id}`);
  const chat = useChat();
  const compare = useCompare();
  const l = listing.data;

  // Domi is asked about this home while you're here; the floating chat button steps aside.
  const { setContext, clearContext, setInlineChat } = chat;
  useEffect(() => {
    setInlineChat(true);
    return () => setInlineChat(false);
  }, [setInlineChat]);
  useEffect(() => {
    if (!l) return;
    setContext([l]);
    return () => clearContext();
  }, [l, setContext, clearContext]);

  const others = compare.items.filter((i) => l && i.id !== l.id);
  const suggestions = useMemo<Suggestion[]>(() => {
    if (!l) return [];
    const list: Suggestion[] = [
      { label: "Explain the monthly estimate", message: "Explain the monthly estimate for this home" },
      { label: "What is the price per square foot?", message: "What is the price per square foot for this home?" },
    ];
    if (others.length)
      list.push({
        label: "Compare with my other choices",
        message: "Compare these homes",
        context: [l, ...others].slice(0, 3),
      });
    return list;
  }, [l, others]);

  if (listing.status === "error" && !l) {
    if (listing.error.status === 404) {
      return (
        <EmptyState
          title="We couldn't find that home"
          body="It may have sold or been taken off the market. Head back to the results to keep looking."
          actions={<LinkButton href="/explore">Back to results</LinkButton>}
        />
      );
    }
    return <ErrorState error={listing.error} onRetry={listing.reload} title="We couldn't load this home" />;
  }
  if (!l) return <DetailSkeleton />;

  const d: ListingDetail = l;
  const inCompare = compare.has(d.id);
  const ppsf = d.price && d.sqft ? Math.round(d.price / d.sqft) : null;
  const features = d.features ? Object.entries(d.features).filter(([, v]) => v !== null && v !== "" && v !== false) : [];

  const details: [string, string][] = [
    ["Address", street(d)],
    ["City", `${d.city}, ${d.state}`],
    ["Zip code", d.zip ?? "Not listed"],
    ["Property type", propertyLabel(d.property_type)],
    ["Year built", d.year_built ? String(d.year_built) : "Not listed"],
    ["Lot size", d.lot_size ? `${num(d.lot_size)} sqft` : "Not listed"],
    ["HOA", d.hoa_fee != null ? `${usd(d.hoa_fee)}/mo` : "Not listed"],
    ["Price per sqft", ppsf ? usd(ppsf) : "Not available"],
  ];

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 pb-16 pt-6 sm:px-8">
      <div className="flex items-center justify-between gap-4 text-sm">
        <nav aria-label="Breadcrumb" className="min-w-0 truncate text-muted">
          <Link href="/explore" className="hover:text-ink">Explore</Link> /{" "}
          <Link href={`/explore?city=${encodeURIComponent(d.city)}`} className="hover:text-ink">{d.city}</Link> /{" "}
          <span className="text-ink-soft">{street(d)}</span>
        </nav>
        <Link href="/explore" className="inline-flex shrink-0 items-center gap-1.5 font-medium text-ink-soft hover:text-ink">
          <ArrowLeft size={16} aria-hidden /> Back to results
        </Link>
      </div>

      <div className="mt-5 flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
        <div className="min-w-0">
          <h1 className="font-display text-4xl font-bold leading-tight text-ink sm:text-5xl">{street(d)}</h1>
          <p className="mt-2 text-lg text-ink-soft">{cityLine(d)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <p className="font-display text-4xl font-bold text-ink">{usd(d.price)}</p>
          <Button
            onClick={() => compare.toggle(d)}
            disabled={!inCompare && compare.isFull}
            variant={inCompare ? "sage" : "primary"}
            size="lg"
          >
            {inCompare ? <Check size={18} weight="bold" aria-hidden /> : <Scales size={18} aria-hidden />}
            {inCompare ? "In comparison" : "Add to comparison"}
          </Button>
          <a href="#ask-domi" className="inline-flex h-12 items-center gap-2 rounded-full border border-line bg-surface px-6 text-[15px] font-medium text-ink hover:bg-sage">
            <ChatCircleDots size={18} aria-hidden /> Ask Domi
          </a>
        </div>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-8">
          {/* "gallery": the listing source has no photos, so show the home's real location at three scales */}
          <section aria-label="Location views" className="grid gap-3 sm:grid-cols-[3fr_2fr] sm:grid-rows-2">
            <TileMap lat={d.lat} lng={d.lng} zoom={17} maxW={700} maxH={460} centerPin className="min-h-[300px] rounded-card sm:row-span-2 sm:min-h-[420px]" />
            <TileMap lat={d.lat} lng={d.lng} zoom={14} maxW={460} maxH={220} centerPin className="min-h-[150px] rounded-card" />
            <TileMap lat={d.lat} lng={d.lng} zoom={11} maxW={460} maxH={220} centerPin className="min-h-[150px] rounded-card" />
          </section>
          <p className="-mt-5 text-[13px] text-muted">
            This data source doesn&apos;t include listing photos, so these maps show where the home sits, from the street to the wider area.
          </p>

          <section aria-label="Quick facts">
            <h2 className="font-display text-3xl font-bold text-ink">A closer look.</h2>
            <ul className="mt-4 grid grid-cols-2 gap-y-1 rounded-card border border-line bg-surface sm:grid-cols-4">
              <Fact icon={<Bed size={22} aria-hidden />} value={d.beds != null ? String(d.beds) : "n/a"} label={d.beds === 1 ? "bed" : "beds"} />
              <Fact icon={<Bathtub size={22} aria-hidden />} value={d.baths != null ? String(d.baths) : "n/a"} label={d.baths === 1 ? "bath" : "baths"} />
              <Fact icon={<Ruler size={22} aria-hidden />} value={num(d.sqft)} label="sqft" />
              <Fact icon={<CalendarBlank size={22} aria-hidden />} value={d.year_built ? String(d.year_built) : "n/a"} label="year built" />
            </ul>
          </section>

          <section aria-label="Property details">
            <h2 className="font-display text-2xl font-bold text-ink">Property details</h2>
            <dl className="mt-4 grid gap-x-10 gap-y-3 sm:grid-cols-2">
              {details.map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-4">
                  <dt className="text-sm text-muted">{k}</dt>
                  <dd className="text-right text-[15px] font-medium text-ink">{v}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section aria-label="From the listing">
            <h2 className="font-display text-2xl font-bold text-ink">From the listing</h2>
            {d.description ? (
              <p className="mt-3 max-w-[70ch] text-[17px] leading-relaxed text-ink-soft">{d.description}</p>
            ) : (
              <p className="mt-3 max-w-[70ch] text-[17px] leading-relaxed text-ink-soft">
                The listing source doesn&apos;t include a description for this home. Everything shown here comes from its recorded details.
              </p>
            )}
            {features.length > 0 && (
              <ul className="mt-4 flex flex-wrap gap-2">
                {features.map(([k]) => (
                  <li key={k} className="inline-flex items-center gap-1.5 rounded-full bg-sage px-3.5 py-1.5 text-sm font-medium text-sage-ink">
                    <Tree size={14} aria-hidden /> {k}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-label="Location">
            <h2 className="font-display text-2xl font-bold text-ink">Location</h2>
            <TileMap lat={d.lat} lng={d.lng} zoom={15} maxW={760} maxH={300} centerPin className="mt-3 h-[260px] w-full rounded-card border border-line" />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-muted">
                Map data &copy;{" "}
                <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer" className="underline underline-offset-2">OpenStreetMap contributors</a>
              </p>
              <LinkButton href={`/explore?city=${encodeURIComponent(d.city)}&focus=${encodeURIComponent(d.id)}`} variant="secondary" size="sm">
                View on search map
              </LinkButton>
            </div>
          </section>
        </div>

        <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start">
          {d.price ? (
            <PaymentCard price={d.price} hoa={d.hoa_fee} />
          ) : (
            <div className="rounded-card border border-line bg-surface p-6">
              <h2 className="font-display text-2xl font-bold text-ink">What could this cost monthly?</h2>
              <p className="mt-2 text-ink-soft">This listing has no price on record, so there is nothing to estimate.</p>
            </div>
          )}
          <div id="ask-domi" className="scroll-mt-24">
            <ChatPanel className="h-[560px]" suggestions={suggestions} />
          </div>
        </aside>
      </div>
    </div>
  );
}
