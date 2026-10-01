"use client";

import { TileMap } from "@/components/map/TileMap";
import { Skeleton } from "@/components/ui/Skeleton";
import { api } from "@/lib/api";
import { usdCompact } from "@/lib/format";
import { useAsync } from "@/lib/use-async";

/** A real map of Dallas with real price pins (from the live listings), for the feature cell. */
export function MapCellPreview() {
  const cities = useAsync((s) => api.cities(s), "cities");
  const res = useAsync((s) => api.listings({ city: "Dallas", page_size: 50 }, s), "dallas-pins");
  const dallas = cities.data?.find((c) => c.city === "Dallas");

  if (res.status === "loading" && !res.data) return <Skeleton className="mt-5 min-h-[16rem] w-full flex-1 rounded-3xl" />;
  if (!dallas || dallas.center_lat == null || dallas.center_lng == null) return null;

  // the six homes nearest the city centre, so the pins read as a cluster, framed around them
  const near = (res.data?.items ?? [])
    .filter((l) => l.lat != null && l.lng != null)
    .map((l) => ({ l, d: Math.hypot(l.lat! - dallas.center_lat!, (l.lng! - dallas.center_lng!) * 0.85) }))
    .sort((a, b) => a.d - b.d)
    .slice(0, 6)
    .map((x) => x.l);
  if (near.length < 2) return null;

  const lats = near.map((l) => l.lat!);
  const lngs = near.map((l) => l.lng!);
  const span = Math.max(Math.max(...lats) - Math.min(...lats), Math.max(...lngs) - Math.min(...lngs));
  const zoom = span < 0.02 ? 14 : span < 0.05 ? 13 : span < 0.1 ? 12 : 11;

  return (
    <TileMap
      lat={(Math.max(...lats) + Math.min(...lats)) / 2}
      lng={(Math.max(...lngs) + Math.min(...lngs)) / 2}
      zoom={zoom}
      maxW={560}
      maxH={640}
      eager
      pins={near.map((l) => ({ lat: l.lat!, lng: l.lng!, label: usdCompact(l.price) }))}
      className="mt-5 min-h-[16rem] w-full flex-1 rounded-3xl border border-on-primary/15"
    />
  );
}
