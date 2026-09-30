import { House } from "@phosphor-icons/react/ssr";
import type { ReactNode } from "react";
import { offsetFromCenter, tilesAround } from "@/lib/tiles";

export interface StaticPin {
  lat: number;
  lng: number;
  label?: string;
}

/**
 * A static, non-interactive OpenStreetMap view centred on lat/lng, built from plain tile
 * images (no Leaflet instance). Used for listing thumbnails, the hero and city cards, where
 * dozens of maps can be on screen at once.
 *
 * Tiles are positioned with calc(50% + Npx), so it fills whatever box it is placed in;
 * maxW/maxH only bound how many tiles are requested.
 */
export function TileMap({
  lat,
  lng,
  zoom = 15,
  maxW = 420,
  maxH = 280,
  pins = [],
  centerPin = false,
  eager = false,
  className = "",
  children,
}: {
  lat: number | null | undefined;
  lng: number | null | undefined;
  zoom?: number;
  maxW?: number;
  maxH?: number;
  pins?: StaticPin[];
  centerPin?: boolean;
  /** Load tiles immediately (above the fold) instead of lazily. */
  eager?: boolean;
  className?: string;
  children?: ReactNode;
}) {
  if (lat == null || lng == null) {
    return (
      <div
        role="img"
        aria-label="No map location available"
        className={`relative grid place-items-center overflow-hidden bg-sage text-sage-ink ${className}`}
      >
        <House size={34} aria-hidden />
      </div>
    );
  }
  const tiles = tilesAround(lat, lng, zoom, maxW, maxH);
  return (
    <div className={`relative isolate overflow-hidden bg-surface-2 ${className}`}>
      <div className="osm-layer absolute inset-0" aria-hidden>
      {tiles.map((t) => (
        // eslint-disable-next-line @next/next/no-img-element -- third-party map tiles, sized by position
        <img
          key={t.key}
          src={t.url}
          alt=""
          width={256}
          height={256}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          draggable={false}
          className="osm-tile absolute max-w-none select-none"
          style={{ left: `calc(50% + ${t.dx}px)`, top: `calc(50% + ${t.dy}px)` }}
        />
      ))}
      </div>
      {pins.map((p, i) => {
        const { dx, dy } = offsetFromCenter({ lat, lng }, p, zoom);
        return (
          <span
            key={i}
            className="absolute -translate-x-1/2 -translate-y-full rounded-full border border-line bg-surface px-2 py-1 text-[11px] font-semibold text-ink shadow-soft"
            style={{ left: `calc(50% + ${dx}px)`, top: `calc(50% + ${dy}px)` }}
          >
            {p.label}
          </span>
        );
      })}
      {centerPin && (
        <span className="absolute left-1/2 top-1/2 grid size-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-primary text-on-primary shadow-lift ring-4 ring-surface/80">
          <House size={18} weight="fill" aria-hidden />
        </span>
      )}
      {children}
    </div>
  );
}
