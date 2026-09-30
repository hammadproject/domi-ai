"use client";

import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react";
import { BreakdownBar, breakdownParts } from "@/components/afford/Breakdown";
import { Skeleton } from "@/components/ui/Skeleton";
import { api } from "@/lib/api";
import { usd, usd2 } from "@/lib/format";
import { useAsync } from "@/lib/use-async";

/** A live call to the real mortgage tool, priced at Austin's median listing. */
export function PaymentMini() {
  const est = useAsync(async (signal) => {
    const cities = await api.cities(signal);
    const austin = cities.find((c) => c.city === "Austin") ?? cities[0];
    if (!austin?.median_price) throw new Error("no price data");
    return api.estimate({ price: austin.median_price, down_payment_pct: 20 }, signal);
  }, "payment-mini");
  const b = est.data;

  return (
    <div>
      {b ? (
        <>
          <p className="text-sm text-ink-soft">
            A {usd(b.price)} home, {b.down_payment_pct}% down, {b.term_years}-year loan
          </p>
          <p className="mt-1 font-display text-5xl font-bold leading-none text-ink">
            {usd2(b.total_monthly)}
            <span className="text-2xl font-semibold text-ink-soft"> / mo</span>
          </p>
          <BreakdownBar parts={breakdownParts(b)} className="mt-5" />
          <ul className="mt-4 grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
            {breakdownParts(b)
              .filter((p) => p.value > 0)
              .map((p) => (
                <li key={p.key} className="flex items-center justify-between gap-2">
                  <span className="inline-flex items-center gap-2 text-ink-soft">
                    <span className="size-2.5 rounded-full" style={{ background: p.color }} aria-hidden />
                    {p.label}
                  </span>
                  <span className="tabular font-medium text-ink">{usd2(p.value)}</span>
                </li>
              ))}
          </ul>
        </>
      ) : est.status === "error" ? (
        <p className="text-ink-soft">Try the calculator to see a monthly estimate with editable assumptions.</p>
      ) : (
        <div aria-hidden>
          <Skeleton className="h-4 w-56" />
          <Skeleton className="mt-3 h-12 w-64" />
          <Skeleton className="mt-5 h-3 w-full rounded-full" />
          <Skeleton className="mt-4 h-4 w-3/4" />
        </div>
      )}
      <Link href="/affordability" className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-sage-ink underline-offset-4 hover:underline">
        Open the calculator <ArrowRight size={14} weight="bold" aria-hidden />
      </Link>
    </div>
  );
}
