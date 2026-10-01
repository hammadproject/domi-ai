"use client";

import Link from "next/link";
import { ArrowRight, HouseLine, Sparkle } from "@phosphor-icons/react";
import { listingHref } from "@/components/listing/ListingCard";
import { TileMap } from "@/components/map/TileMap";
import { Skeleton } from "@/components/ui/Skeleton";
import { api } from "@/lib/api";
import { homeFacts, street, usd, usdCompact } from "@/lib/format";
import { useAsync } from "@/lib/use-async";

const EXAMPLE = { city: "Austin", beds_min: 3, price_max: 550_000 } as const;

/**
 * The hero's visual: a real map of Austin with real price pins, and a small example of the
 * conversation, built from a live query. Nothing here is invented: if the backend can't be
 * reached it falls back to a plain map panel with no numbers.
 */
export function HeroPreview() {
  const cities = useAsync((s) => api.cities(s), "cities");
  const res = useAsync(
    (s) => api.listings({ ...EXAMPLE, sort: "price_desc", page_size: 50 }, s),
    "hero-example",
  );
  const austin = cities.data?.find((c) => c.city === EXAMPLE.city);
  const items = (res.data?.items ?? []).filter((l) => l.lat != null && l.lng != null);
  // the seven homes nearest the map centre, so the pins are on screen and read as a cluster
  const cLat = austin?.center_lat ?? 30.2672;
  const cLng = austin?.center_lng ?? -97.7431;
  const pinSample = [...items]
    .sort((a, b) => Math.hypot(a.lat! - cLat, (a.lng! - cLng) * 0.85) - Math.hypot(b.lat! - cLat, (b.lng! - cLng) * 0.85))
    .slice(0, 7);
  const top = res.data?.items[0];
  const loading = res.status === "loading" && !res.data;

  return (
    <div className="relative mx-auto w-full max-w-[640px]">
      <div aria-hidden className="absolute -left-4 -top-4 h-2/3 w-2/3 rounded-[40px] bg-sage" />
      <div className="relative overflow-hidden rounded-[32px] border border-line shadow-lift">
        {loading ? (
          <Skeleton className="h-[360px] w-full rounded-none sm:h-[420px] lg:h-[min(500px,calc(100dvh-9.5rem))]" />
        ) : (
          <TileMap
            lat={austin?.center_lat ?? 30.2672}
            lng={austin?.center_lng ?? -97.7431}
            zoom={12}
            maxW={700}
            maxH={620}
            eager
            pins={pinSample.map((l) => ({ lat: l.lat!, lng: l.lng!, label: usdCompact(l.price) }))}
            className="h-[360px] w-full sm:h-[420px] lg:h-[min(500px,calc(100dvh-9.5rem))]"
          />
        )}

        {top && res.data && (
          <div className="absolute inset-x-3 bottom-3 rounded-[24px] border border-line bg-surface p-4 shadow-lift sm:inset-x-auto sm:bottom-5 sm:left-5 sm:w-[340px]">
            <p className="flex items-center gap-2 text-xs font-medium text-sage-ink">
              <Sparkle size={14} weight="fill" aria-hidden /> Example search
            </p>
            <p className="mt-2 w-fit max-w-full rounded-2xl rounded-bl-md bg-sage px-3.5 py-2 text-sm text-sage-ink">
              3 bedroom homes in Austin under $550k
            </p>
            <div className="mt-3 flex gap-2.5">
              <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-surface-2 text-primary">
                <HouseLine size={16} aria-hidden />
              </span>
              <p className="text-sm text-ink">
                I found {res.data.total.toLocaleString("en-US")} matching {res.data.total === 1 ? "home" : "homes"}. The
                closest to your budget is:
              </p>
            </div>
            <Link
              href={listingHref(top.id)}
              className="mt-3 flex items-center gap-3 rounded-2xl border border-line bg-canvas p-2 transition-colors hover:bg-sage"
            >
              <TileMap lat={top.lat} lng={top.lng} zoom={16} maxW={120} maxH={120} centerPin className="size-14 shrink-0 rounded-xl" />
              <span className="min-w-0 flex-1">
                <span className="block font-display text-xl font-bold leading-none text-ink">{usd(top.price)}</span>
                <span className="block truncate text-xs text-ink-soft">{street(top)}</span>
                <span className="block truncate text-xs text-muted">{homeFacts(top)}</span>
              </span>
              <ArrowRight size={16} className="shrink-0 text-ink-soft" aria-hidden />
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
