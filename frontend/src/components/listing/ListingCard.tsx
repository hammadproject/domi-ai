"use client";

import Link from "next/link";
import { ArrowRight, Bathtub, Bed, ChatCircleDots, Ruler } from "@phosphor-icons/react";
import { ListingMedia } from "@/components/listing/ListingMedia";
import { cityLine, homeFacts, num, street, usd } from "@/lib/format";
import type { Listing } from "@/lib/types";

export const listingHref = (id: string) => `/listings/${encodeURIComponent(id)}`;

interface Props {
  listing: Listing;
  variant?: "list" | "grid";
  /** The home currently selected on the map. */
  selected?: boolean;
  /** Part of Domi's latest answer. */
  picked?: boolean;
  compareChecked: boolean;
  compareDisabled: boolean;
  onCompareToggle: () => void;
  onSelect?: () => void;
  onHover?: (id: string | null) => void;
  onAsk?: () => void;
}

function CompareCheck({
  checked,
  disabled,
  onToggle,
  address,
}: {
  checked: boolean;
  disabled: boolean;
  onToggle: () => void;
  address: string;
}) {
  return (
    <label
      className={`inline-flex cursor-pointer items-center gap-2 text-sm font-medium ${disabled && !checked ? "cursor-not-allowed text-muted" : "text-ink-soft hover:text-ink"}`}
      title={disabled && !checked ? "You can compare up to 3 homes" : undefined}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled && !checked}
        onChange={onToggle}
        aria-label={`Compare ${address}`}
        className="size-[18px] cursor-pointer rounded-[5px] border-line accent-[var(--primary)] disabled:cursor-not-allowed"
      />
      Compare
    </label>
  );
}

export function ListingCard({
  listing: l,
  variant = "list",
  selected = false,
  picked = false,
  compareChecked,
  compareDisabled,
  onCompareToggle,
  onSelect,
  onHover,
  onAsk,
}: Props) {
  const ring = selected
    ? "border-primary ring-2 ring-primary/30"
    : picked
      ? "border-sage-strong ring-2 ring-sage-strong"
      : "border-line hover:border-sage-strong";
  const href = listingHref(l.id);

  if (variant === "grid") {
    return (
      <article
        onMouseEnter={() => onHover?.(l.id)}
        onMouseLeave={() => onHover?.(null)}
        className={`group flex flex-col rounded-card border bg-surface p-3 shadow-soft transition-[transform,box-shadow,border-color] duration-300 ease-[var(--ease-out-expo)] hover:-translate-y-0.5 hover:shadow-lift ${ring}`}
      >
        <Link href={href} tabIndex={-1} aria-hidden className="block">
          <ListingMedia listing={l} maxW={420} maxH={200} className="h-44 w-full rounded-2xl" />
        </Link>
        <div className="px-1.5 pb-1 pt-4">
          <p className="font-display text-[28px] font-bold leading-none text-ink">{usd(l.price)}</p>
          <h3 className="mt-2 break-words text-[15px] font-medium leading-snug text-ink">{street(l)}</h3>
          <p className="text-sm text-muted">{cityLine(l)}</p>
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-ink-soft">
            {l.beds != null && (
              <li className="inline-flex items-center gap-1.5"><Bed size={16} aria-hidden />{l.beds} {l.beds === 1 ? "bed" : "beds"}</li>
            )}
            {l.baths != null && (
              <li className="inline-flex items-center gap-1.5"><Bathtub size={16} aria-hidden />{l.baths} {l.baths === 1 ? "bath" : "baths"}</li>
            )}
            {l.sqft != null && (
              <li className="inline-flex items-center gap-1.5"><Ruler size={16} aria-hidden />{num(l.sqft)} sqft</li>
            )}
            {l.beds == null && l.baths == null && l.sqft == null && <li>{l.property_type ?? "Details not listed"}</li>}
          </ul>
        </div>
        <div className="mt-auto flex flex-col gap-3 px-1.5 pt-3">
          <Link
            href={href}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-full bg-primary text-sm font-medium text-on-primary transition-[background-color,transform] hover:bg-primary-hover active:scale-[0.98]"
          >
            View property <ArrowRight size={16} weight="bold" aria-hidden />
          </Link>
          <div className="flex items-center justify-between pb-1">
            <CompareCheck checked={compareChecked} disabled={compareDisabled} onToggle={onCompareToggle} address={street(l)} />
            {onAsk && (
              <button type="button" onClick={onAsk} className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft hover:text-ink">
                <ChatCircleDots size={16} aria-hidden /> Ask Domi
              </button>
            )}
          </div>
        </div>
      </article>
    );
  }

  return (
    <article
      onMouseEnter={() => onHover?.(l.id)}
      onMouseLeave={() => onHover?.(null)}
      data-listing-id={l.id}
      className={`flex gap-4 rounded-card border bg-surface p-3 transition-[border-color,box-shadow] duration-300 ${ring}`}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-label={`Show ${street(l)} on the map`}
        className="block h-auto w-[132px] shrink-0 self-stretch overflow-hidden rounded-2xl sm:w-[156px]"
      >
        <ListingMedia listing={l} maxW={200} maxH={200} className="h-full min-h-[148px] w-full" />
      </button>
      <div className="flex min-w-0 flex-1 flex-col">
        <p className="font-display text-[26px] font-bold leading-none text-ink">{usd(l.price)}</p>
        <h3 className="mt-1.5 break-words text-[15px] font-medium leading-snug text-ink">{street(l)}</h3>
        <p className="truncate text-sm text-muted">{cityLine(l)}</p>
        <p className="mt-1.5 text-sm text-ink-soft">{homeFacts(l)}</p>
        <div className="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-2 pt-3">
          <Link
            href={href}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-full bg-primary px-4 text-sm font-medium text-on-primary transition-[background-color,transform] hover:bg-primary-hover active:scale-[0.98]"
          >
            View details <ArrowRight size={15} weight="bold" aria-hidden />
          </Link>
          <CompareCheck checked={compareChecked} disabled={compareDisabled} onToggle={onCompareToggle} address={street(l)} />
        </div>
      </div>
    </article>
  );
}
