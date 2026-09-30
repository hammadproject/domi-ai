import type { Listing } from "./types";

const usdFmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});
const usd2Fmt = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const numFmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export const usd = (n: number | null | undefined) => (n == null ? "Not listed" : usdFmt.format(n));
export const usd2 = (n: number) => usd2Fmt.format(n);
export const num = (n: number | null | undefined) => (n == null ? "n/a" : numFmt.format(n));

/** $489k, $1.2M: for map pins and tight spaces. */
export function usdCompact(n: number | null | undefined): string {
  if (n == null) return "n/a";
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}k`;
  return `$${n}`;
}

export const countLabel = (n: number | null | undefined, unit: string) =>
  n == null ? `${unit} n/a` : `${Number.isInteger(n) ? n : n.toFixed(1)} ${unit}`;

/** "2505 Bluebonnet Ln, Unit 3" from "2505 Bluebonnet Ln, Unit 3, Austin, TX 78704". */
export function street(l: Pick<Listing, "address" | "city">): string {
  const i = l.address.lastIndexOf(`, ${l.city}`);
  return i > 0 ? l.address.slice(0, i) : l.address;
}

export const cityLine = (l: Pick<Listing, "city" | "state" | "zip">) =>
  `${l.city}, ${l.state}${l.zip ? ` ${l.zip}` : ""}`;

export function homeFacts(l: Listing): string {
  const parts = [
    l.beds != null ? countLabel(l.beds, l.beds === 1 ? "bed" : "beds") : null,
    l.baths != null ? countLabel(l.baths, l.baths === 1 ? "bath" : "baths") : null,
    l.sqft != null ? `${num(l.sqft)} sqft` : null,
  ].filter(Boolean);
  return parts.length ? parts.join(", ") : (l.property_type ?? "Details not listed");
}

export const propertyLabel = (t: string | null) =>
  t === "Single Family" ? "Single-family house" : (t ?? "Property");

export function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}
