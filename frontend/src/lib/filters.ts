import type { ListingQuery } from "./api";

export type ViewMode = "split" | "grid";

export interface ExploreFilters {
  city?: string; // "Austin" (state implied by the city list)
  state?: string;
  price_min?: number;
  price_max?: number;
  beds_min?: number;
  baths_min?: number;
  sqft_min?: number;
  property_type?: string;
  sort: NonNullable<ListingQuery["sort"]>;
  page: number;
  view: ViewMode;
}

export const DEFAULT_FILTERS: ExploreFilters = { sort: "price_asc", page: 1, view: "split" };

const numParam = (v: string | null) => {
  if (v == null || v === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
};

const SORTS = ["price_asc", "price_desc", "newest", "sqft_desc"] as const;

export function parseFilters(p: URLSearchParams): ExploreFilters {
  const sort = p.get("sort");
  return {
    city: p.get("city") || undefined,
    state: p.get("state") || undefined,
    price_min: numParam(p.get("price_min")),
    price_max: numParam(p.get("price_max")),
    beds_min: numParam(p.get("beds_min")),
    baths_min: numParam(p.get("baths_min")),
    sqft_min: numParam(p.get("sqft_min")),
    property_type: p.get("property_type") || undefined,
    sort: (SORTS as readonly string[]).includes(sort ?? "") ? (sort as ExploreFilters["sort"]) : "price_asc",
    page: Math.max(1, numParam(p.get("page")) ?? 1),
    view: p.get("view") === "grid" ? "grid" : "split",
  };
}

export function filtersToParams(f: ExploreFilters): URLSearchParams {
  const p = new URLSearchParams();
  const set = (k: string, v: string | number | undefined) => {
    if (v !== undefined && v !== "") p.set(k, String(v));
  };
  set("city", f.city);
  set("state", f.state);
  set("price_min", f.price_min);
  set("price_max", f.price_max);
  set("beds_min", f.beds_min);
  set("baths_min", f.baths_min);
  set("sqft_min", f.sqft_min);
  set("property_type", f.property_type);
  if (f.sort !== "price_asc") set("sort", f.sort);
  if (f.page > 1) set("page", f.page);
  if (f.view !== "split") set("view", f.view);
  return p;
}

export function toListingQuery(f: ExploreFilters, pageSize: number): ListingQuery {
  return {
    city: f.city,
    state: f.state,
    price_min: f.price_min,
    price_max: f.price_max,
    beds_min: f.beds_min,
    baths_min: f.baths_min,
    sqft_min: f.sqft_min,
    property_type: f.property_type,
    sort: f.sort,
    page: f.page,
    page_size: pageSize,
  };
}

/** Filters that narrow results (everything except sort, page and view). */
export function activeFilterCount(f: ExploreFilters): number {
  return [f.city, f.price_min, f.price_max, f.beds_min, f.baths_min, f.sqft_min, f.property_type].filter(
    (v) => v !== undefined,
  ).length;
}

export function describeFilters(f: ExploreFilters): string[] {
  const out: string[] = [];
  if (f.city) out.push(f.city);
  if (f.price_max) out.push(`Under $${Math.round(f.price_max / 1000)}k`);
  if (f.price_min) out.push(`Over $${Math.round(f.price_min / 1000)}k`);
  if (f.beds_min) out.push(`${f.beds_min}+ beds`);
  if (f.baths_min) out.push(`${f.baths_min}+ baths`);
  if (f.sqft_min) out.push(`${f.sqft_min.toLocaleString("en-US")}+ sqft`);
  if (f.property_type) out.push(f.property_type);
  return out;
}
