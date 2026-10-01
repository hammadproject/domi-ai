"use client";

import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react";
import { TileMap } from "@/components/map/TileMap";
import { api } from "@/lib/api";
import { usd } from "@/lib/format";
import type { CityStats } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const CITIES = [
  { name: "Austin", state: "TX" },
  { name: "Dallas", state: "TX" },
  { name: "Phoenix", state: "AZ" },
] as const;

function CityCard({ name, state, stats, className }: { name: string; state: string; stats?: CityStats; className: string }) {
  return (
    <Link
      href={`/explore?city=${name}`}
      className={`group relative isolate block overflow-hidden rounded-[28px] border border-line bg-surface-2 ${className}`}
    >
      <div className="absolute inset-0 transition-transform duration-700 ease-[var(--ease-out-expo)] group-hover:scale-105">
        <TileMap
          lat={stats?.center_lat}
          lng={stats?.center_lng}
          zoom={11}
          maxW={900}
          maxH={520}
          eager
          className="h-full w-full"
        />
      </div>
      <div aria-hidden className="absolute inset-0 bg-gradient-to-t from-[#0c1a13]/85 via-[#0c1a13]/25 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 p-5 sm:p-6">
        <div>
          <h3 className="font-display text-3xl font-bold text-[#f4f6ee] sm:text-4xl">
            {name}, {state}
          </h3>
          {stats && (
            <p className="mt-1 text-sm text-[#e3eadb]">
              {stats.listing_count.toLocaleString("en-US")} homes
              {stats.median_price ? `, median ${usd(stats.median_price)}` : ""}
            </p>
          )}
        </div>
        <span className="grid size-11 shrink-0 place-items-center rounded-full bg-[#f4f6ee] text-[#143025] transition-transform duration-300 group-hover:translate-x-1">
          <ArrowRight size={18} weight="bold" aria-hidden />
        </span>
      </div>
      <span className="sr-only">Browse homes in {name}</span>
    </Link>
  );
}

export function CityCards() {
  const cities = useAsync((s) => api.cities(s), "cities");
  const by = (n: string) => cities.data?.find((c) => c.city === n);
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-5 md:grid-rows-2">
      <CityCard name="Austin" state="TX" stats={by("Austin")} className="min-h-[300px] md:col-span-3 md:row-span-2 md:min-h-[460px]" />
      <CityCard name="Dallas" state="TX" stats={by("Dallas")} className="min-h-[220px] md:col-span-2" />
      <CityCard name="Phoenix" state="AZ" stats={by("Phoenix")} className="min-h-[220px] md:col-span-2" />
    </div>
  );
}

export { CITIES };
