"use client";

import Link from "next/link";
import { ArrowRight, Scales, X } from "@phosphor-icons/react";
import { TileMap } from "@/components/map/TileMap";
import { street, usd } from "@/lib/format";
import { useCompare } from "@/state/compare";

/** Floating "homes selected" bar. Sits above the mobile tab bar when `lifted`. */
export function CompareTray({ lifted = false }: { lifted?: boolean }) {
  const { items, remove, clear } = useCompare();
  if (items.length === 0) return null;
  const ready = items.length >= 2;
  // repeated id= params: listing ids contain commas, so a comma-separated list would be ambiguous
  const href = `/compare?${new URLSearchParams(items.map((i) => ["id", i.id])).toString()}`;

  return (
    <div
      role="region"
      aria-label="Homes selected for comparison"
      className={`fixed inset-x-3 z-[var(--z-tray,30)] mx-auto flex max-w-[1100px] flex-wrap items-center gap-3 rounded-[24px] border border-line bg-surface p-3 shadow-lift sm:inset-x-6 sm:flex-nowrap sm:px-5 ${lifted ? "bottom-[76px] lg:bottom-4" : "bottom-4"}`}
    >
      <div className="min-w-[7rem]">
        <p className="font-display text-xl font-bold leading-tight text-ink">
          {items.length} {items.length === 1 ? "home" : "homes"} selected
        </p>
        <button type="button" onClick={clear} className="text-xs font-medium text-muted underline underline-offset-2 hover:text-ink">
          Clear all
        </button>
      </div>
      <ul className="flex min-w-0 flex-1 gap-2 overflow-x-auto">
        {items.map((l) => (
          <li key={l.id} className="flex min-w-[190px] items-center gap-2.5 rounded-2xl border border-line bg-canvas p-1.5 pr-2">
            <TileMap lat={l.lat} lng={l.lng} zoom={15} maxW={90} maxH={90} className="size-11 shrink-0 rounded-xl" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-ink">{usd(l.price)}</p>
              <p className="truncate text-xs text-muted">{street(l)}</p>
            </div>
            <button type="button" onClick={() => remove(l.id)} aria-label={`Remove ${street(l)} from comparison`} className="grid size-7 place-items-center rounded-full text-ink-soft hover:bg-sage">
              <X size={14} weight="bold" aria-hidden />
            </button>
          </li>
        ))}
      </ul>
      {ready ? (
        <Link
          href={href}
          className="inline-flex h-12 shrink-0 items-center justify-center gap-2.5 whitespace-nowrap rounded-full bg-primary px-6 text-[14px] font-semibold text-on-primary shadow-soft transition-[background-color,transform,box-shadow] hover:bg-primary-hover hover:shadow-lift active:scale-[0.97]"
        >
          <Scales size={20} aria-hidden />
          Compare {items.length} homes
          <ArrowRight size={16} weight="bold" aria-hidden />
        </Link>
      ) : (
        <span className="inline-flex h-12 shrink-0 items-center gap-2 rounded-full border border-dashed border-line px-5 text-sm text-muted">
          <Scales size={18} aria-hidden /> Pick one more to compare
        </span>
      )}
    </div>
  );
}
