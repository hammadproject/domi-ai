import type { PaymentBreakdown } from "@/lib/types";

export interface Part {
  key: string;
  label: string;
  value: number;
  color: string;
}

/** Segments of the monthly payment. Shades of the one accent (forest) keep the palette locked. */
export function breakdownParts(b: PaymentBreakdown): Part[] {
  return [
    { key: "pi", label: "Principal & interest", value: b.principal_interest, color: "var(--primary)" },
    { key: "tax", label: "Property taxes", value: b.property_tax, color: "color-mix(in srgb, var(--primary) 52%, var(--sage-strong))" },
    { key: "ins", label: "Home insurance", value: b.insurance, color: "color-mix(in srgb, var(--primary) 26%, var(--sage-strong))" },
    { key: "hoa", label: "HOA", value: b.hoa, color: "var(--sage-strong)" },
    { key: "pmi", label: "PMI", value: b.pmi, color: "color-mix(in srgb, var(--sage-strong) 55%, var(--surface))" },
  ];
}

export function BreakdownBar({ parts, className = "" }: { parts: Part[]; className?: string }) {
  const total = parts.reduce((s, p) => s + p.value, 0);
  if (total <= 0) return null;
  return (
    <div
      role="img"
      aria-label={parts
        .filter((p) => p.value > 0)
        .map((p) => `${p.label} ${Math.round((p.value / total) * 100)} percent`)
        .join(", ")}
      className={`flex h-3.5 w-full overflow-hidden rounded-full bg-surface-2 ${className}`}
    >
      {parts
        .filter((p) => p.value > 0)
        .map((p) => (
          <span
            key={p.key}
            style={{ width: `${(p.value / total) * 100}%`, background: p.color }}
            className="h-full transition-[width] duration-500 ease-[var(--ease-out-expo)]"
          />
        ))}
    </div>
  );
}
