"use client";

import { ArrowCounterClockwise, Bathtub, Bed, CurrencyDollar, House, MapPin, Ruler } from "@phosphor-icons/react";
import { Select, type Option } from "@/components/ui/Select";
import { activeFilterCount, type ExploreFilters } from "@/lib/filters";
import type { CityStats } from "@/lib/types";

const ANY = "";

const money = (v: number) => (v >= 1_000_000 ? `$${v / 1_000_000}M` : `$${v / 1000}k`);

// Labels are short on purpose: the button shows the selected one, so all filters fit one line.
const PRICE_MAX: Option[] = [
  { value: ANY, label: "Any max" },
  ...[250_000, 350_000, 450_000, 550_000, 700_000, 900_000, 1_250_000].map((v) => ({
    value: String(v),
    label: `Up to ${money(v)}`,
  })),
];
const PRICE_MIN: Option[] = [
  { value: ANY, label: "Any min" },
  ...[100_000, 200_000, 300_000, 400_000, 500_000, 750_000].map((v) => ({
    value: String(v),
    label: `${money(v)}+`,
  })),
];
const BEDS: Option[] = [
  { value: ANY, label: "Any beds" },
  ...[1, 2, 3, 4, 5].map((v) => ({ value: String(v), label: `${v}+ beds` })),
];
const BATHS: Option[] = [
  { value: ANY, label: "Any baths" },
  ...[1, 2, 3].map((v) => ({ value: String(v), label: `${v}+ baths` })),
];
export const TYPES: Option[] = [
  { value: ANY, label: "Any type" },
  { value: "Single Family", label: "House" },
  { value: "Condo", label: "Condo" },
  { value: "Townhouse", label: "Townhouse" },
  { value: "Multi-Family", label: "Multi-family" },
  { value: "Manufactured", label: "Manufactured" },
  { value: "Land", label: "Land" },
];
const SQFT: Option[] = [
  { value: ANY, label: "Any size" },
  ...[1000, 1500, 2000, 2500, 3000].map((v) => ({ value: String(v), label: `${v.toLocaleString("en-US")}+ sqft` })),
];
export const SORTS: Option[] = [
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "newest", label: "Newest build" },
  { value: "sqft_desc", label: "Largest first" },
];

const toNum = (v: string) => (v === ANY ? undefined : Number(v));

/** The filters currently applied, as removable chips. Shared by the page and the chat. */
export function activeFilterChips(
  filters: ExploreFilters,
  onChange: (patch: Partial<ExploreFilters>) => void,
): { label: string; clear: () => void }[] {
  const chips: { label: string; clear: () => void }[] = [];
  if (filters.city) chips.push({ label: filters.city, clear: () => onChange({ city: undefined, state: undefined }) });
  if (filters.price_max) chips.push({ label: `Under $${Math.round(filters.price_max / 1000)}k`, clear: () => onChange({ price_max: undefined }) });
  if (filters.price_min) chips.push({ label: `Over $${Math.round(filters.price_min / 1000)}k`, clear: () => onChange({ price_min: undefined }) });
  if (filters.beds_min) chips.push({ label: `${filters.beds_min}+ beds`, clear: () => onChange({ beds_min: undefined }) });
  if (filters.baths_min) chips.push({ label: `${filters.baths_min}+ baths`, clear: () => onChange({ baths_min: undefined }) });
  if (filters.sqft_min) chips.push({ label: `${filters.sqft_min.toLocaleString("en-US")}+ sqft`, clear: () => onChange({ sqft_min: undefined }) });
  if (filters.property_type)
    chips.push({
      label: TYPES.find((t) => t.value === filters.property_type)?.label ?? filters.property_type,
      clear: () => onChange({ property_type: undefined }),
    });
  return chips;
}

/** Every filter, always visible, in one row of compact dropdowns (wraps between controls on narrow screens). */
export function FilterBar({
  filters,
  cities,
  onChange,
  onReset,
}: {
  filters: ExploreFilters;
  cities: CityStats[] | undefined;
  onChange: (patch: Partial<ExploreFilters>) => void;
  onReset: () => void;
}) {
  const cityOptions: Option[] = [
    { value: ANY, label: "All cities" },
    ...(cities ?? []).map((c) => ({ value: c.city, label: `${c.city}, ${c.state}` })),
  ];
  if (filters.city && !cityOptions.some((o) => o.value === filters.city)) {
    cityOptions.push({ value: filters.city, label: filters.city });
  }
  const count = activeFilterCount(filters);

  return (
    <div id="filter-bar" className="flex flex-wrap items-center gap-2" role="group" aria-label="Filters">
      <Select size="sm" label="City" icon={<MapPin aria-hidden />} value={filters.city ?? ANY} options={cityOptions} onChange={(v) => onChange({ city: v || undefined, state: undefined })} />
      <Select size="sm" label="Maximum price" icon={<CurrencyDollar aria-hidden />} value={filters.price_max ? String(filters.price_max) : ANY} options={PRICE_MAX} onChange={(v) => onChange({ price_max: toNum(v) })} />
      <Select size="sm" label="Minimum price" icon={<CurrencyDollar aria-hidden />} value={filters.price_min ? String(filters.price_min) : ANY} options={PRICE_MIN} onChange={(v) => onChange({ price_min: toNum(v) })} />
      <Select size="sm" label="Bedrooms" icon={<Bed aria-hidden />} value={filters.beds_min ? String(filters.beds_min) : ANY} options={BEDS} onChange={(v) => onChange({ beds_min: toNum(v) })} />
      <Select size="sm" label="Bathrooms" icon={<Bathtub aria-hidden />} value={filters.baths_min ? String(filters.baths_min) : ANY} options={BATHS} onChange={(v) => onChange({ baths_min: toNum(v) })} />
      <Select size="sm" label="Property type" icon={<House aria-hidden />} value={filters.property_type ?? ANY} options={TYPES} onChange={(v) => onChange({ property_type: v || undefined })} />
      <Select size="sm" label="Minimum size" icon={<Ruler aria-hidden />} value={filters.sqft_min ? String(filters.sqft_min) : ANY} options={SQFT} onChange={(v) => onChange({ sqft_min: toNum(v) })} />
      <button
        type="button"
        onClick={onReset}
        disabled={count === 0}
        className="inline-flex h-9 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3 text-[12.5px] font-medium text-ink-soft transition-colors hover:bg-sage/60 hover:text-ink disabled:opacity-40"
      >
        <ArrowCounterClockwise size={16} aria-hidden /> Reset
      </button>
    </div>
  );
}
