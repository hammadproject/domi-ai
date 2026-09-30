"use client";

import "leaflet/dist/leaflet.css";
import type { Map as LeafletMap, Marker } from "leaflet";
import { useEffect, useRef, useState } from "react";
import { Crosshair } from "@phosphor-icons/react";
import { cityLine, homeFacts, street, usd, usdCompact } from "@/lib/format";
import type { Listing } from "@/lib/types";

const esc = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

const tipHtml = (l: Listing) =>
  `<div class="domi-tip-card"><strong>${esc(usd(l.price))}</strong>` +
  `${esc(street(l))}<br/><span>${esc(cityLine(l))}</span><br/><span>${esc(homeFacts(l))}</span></div>`;

const pinHtml = (l: Listing) =>
  `<div class="domi-pin"><span class="domi-pin__label">${esc(usdCompact(l.price))}</span></div>`;

interface Props {
  listings: Listing[];
  /** Homes from Domi's latest answer: drawn as highlighted pins. */
  pickedIds: string[];
  selectedId: string | null;
  hoveredId: string | null;
  onSelect: (id: string) => void;
  /** Changes when the result set changes, so the map re-fits its bounds. */
  fitKey: string;
  className?: string;
}

export function ListingMap({ listings, pickedIds, selectedId, hoveredId, onSelect, fitKey, className = "" }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef<Map<string, Marker>>(new Map());
  const leafletRef = useRef<typeof import("leaflet") | null>(null);
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  });
  const [ready, setReady] = useState(false);

  // create the map once
  useEffect(() => {
    let cancelled = false;
    let map: LeafletMap | null = null;
    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !containerRef.current) return;
      leafletRef.current = L;
      map = L.map(containerRef.current, {
        zoomControl: false,
        attributionControl: false,
        scrollWheelZoom: true,
      }).setView([32.3, -97.5], 6);
      L.control.zoom({ position: "bottomleft" }).addTo(map);
      L.control.attribution({ prefix: false, position: "bottomright" }).addTo(map);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).addTo(map);
      mapRef.current = map;
      setReady(true);
    })();
    const markers = markersRef.current;
    return () => {
      cancelled = true;
      markers.clear();
      map?.remove();
      mapRef.current = null;
      setReady(false);
    };
  }, []);

  // keep markers in sync with the listings
  useEffect(() => {
    const L = leafletRef.current;
    const map = mapRef.current;
    if (!ready || !L || !map) return;
    const markers = markersRef.current;
    const wanted = new Map(listings.filter((l) => l.lat != null && l.lng != null).map((l) => [l.id, l]));

    for (const [id, m] of markers) {
      if (!wanted.has(id)) {
        m.remove();
        markers.delete(id);
      }
    }
    for (const [id, l] of wanted) {
      if (markers.has(id)) continue;
      const m = L.marker([l.lat!, l.lng!], {
        icon: L.divIcon({ className: "", html: pinHtml(l), iconSize: [0, 0] }),
        keyboard: true,
        title: `${street(l)}, ${usd(l.price)}`,
      });
      m.bindTooltip(tipHtml(l), {
        direction: "auto",
        offset: [0, -14],
        opacity: 1,
        className: "domi-tip",
      });
      m.on("click", () => onSelectRef.current(id));
      m.addTo(map);
      markers.set(id, m);
    }
  }, [listings, ready]);

  // re-fit when the result set changes
  useEffect(() => {
    const L = leafletRef.current;
    const map = mapRef.current;
    if (!ready || !L || !map) return;
    const pts = listings.filter((l) => l.lat != null && l.lng != null).map((l) => [l.lat!, l.lng!] as [number, number]);
    if (!pts.length) return;
    if (pts.length === 1) map.setView(pts[0], 14, { animate: false });
    else map.fitBounds(L.latLngBounds(pts), { padding: [48, 48], maxZoom: 15, animate: false });
    // fitKey (not listings) on purpose: only re-fit when the *result set* changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey, ready]);

  // highlight states
  useEffect(() => {
    const picked = new Set(pickedIds);
    for (const [id, m] of markersRef.current) {
      const el = m.getElement()?.querySelector<HTMLElement>(".domi-pin");
      if (!el) continue;
      el.classList.toggle("is-pick", picked.has(id));
      el.classList.toggle("is-active", id === selectedId || id === hoveredId);
      m.setZIndexOffset(id === selectedId ? 2000 : id === hoveredId ? 1500 : picked.has(id) ? 1000 : 0);
    }
  }, [pickedIds, selectedId, hoveredId, listings, ready]);

  // bring a selected home into view
  useEffect(() => {
    const map = mapRef.current;
    const m = selectedId ? markersRef.current.get(selectedId) : null;
    if (!map || !m) return;
    const inner = map.getBounds().pad(-0.2);
    if (!inner.contains(m.getLatLng())) map.panTo(m.getLatLng(), { animate: true });
  }, [selectedId, ready]);

  const fitAll = () => {
    const L = leafletRef.current;
    const map = mapRef.current;
    if (!L || !map) return;
    const pts = listings.filter((l) => l.lat != null && l.lng != null).map((l) => [l.lat!, l.lng!] as [number, number]);
    if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [48, 48], maxZoom: 15, animate: false });
  };

  return (
    <div className={`relative isolate overflow-hidden ${className}`}>
      <div ref={containerRef} className="domi-map absolute inset-0" role="region" aria-label="Map of matching homes" />
      <button
        type="button"
        onClick={fitAll}
        aria-label="Show all results"
        className="absolute right-3 top-3 z-[500] grid size-10 place-items-center rounded-full bg-surface text-ink shadow-soft transition-colors hover:bg-sage"
      >
        <Crosshair size={20} aria-hidden />
      </button>
    </div>
  );
}
