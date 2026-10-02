"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, Info } from "@phosphor-icons/react";
import { BreakdownBar, breakdownParts } from "@/components/afford/Breakdown";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import { usd, usd2 } from "@/lib/format";
import { useAsync } from "@/lib/use-async";

const DOWN = [0, 5, 10, 15, 20, 25, 30];

/** Live monthly estimate for one home, from POST /api/mortgage/estimate. */
export function PaymentCard({ price, hoa }: { price: number; hoa: number | null }) {
  const defaults = useAsync((s) => api.mortgageDefaults(s), "mortgage-defaults");
  const [down, setDown] = useState(20);
  const [term, setTerm] = useState(30);
  // the server's default rate, until the person types their own
  const [rateIn, setRateIn] = useState<string | null>(null);
  const rate = rateIn ?? (defaults.data ? String(defaults.data.interest_rate) : "");

  const rateNum = Number(rate);
  const validRate = rate !== "" && Number.isFinite(rateNum) && rateNum >= 0 && rateNum <= 30;
  const est = useAsync(
    (signal) =>
      api.estimate(
        { price, down_payment_pct: down, term_years: term, hoa_monthly: hoa ?? 0, interest_rate: rateNum },
        signal,
      ),
    JSON.stringify([price, down, term, hoa, rateNum]),
    validRate,
  );
  const b = est.data;
  const calcHref = `/affordability?price=${price}&down=${down}&term=${term}&hoa=${hoa ?? 0}${validRate ? `&rate=${rateNum}` : ""}`;

  const field = "h-11 w-full rounded-xl border border-line bg-canvas px-3 text-[14px] text-ink outline-none focus:border-primary";
  const label = "mb-1.5 block text-[12.5px] font-medium text-ink-soft";

  return (
    <section aria-label="Monthly cost estimate" className="rounded-card border border-line bg-surface p-6 shadow-soft">
      <h2 className="font-display text-2xl font-bold text-ink">What could this cost monthly?</h2>
      <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4">
        <div>
          <span className={label}>Home price</span>
          <p className="flex h-11 items-center rounded-xl bg-surface-2 px-3 text-[14px] font-medium text-ink">{usd(price)}</p>
        </div>
        <div>
          <span className={label}>Down payment</span>
          <Select variant="field" label="Down payment" value={String(down)} options={DOWN.map((d) => ({ value: String(d), label: `${d}%` }))} onChange={(v) => setDown(Number(v))} />
        </div>
        <div>
          <label htmlFor="pc-rate" className={label}>Interest rate (%)</label>
          <input
            id="pc-rate"
            inputMode="decimal"
            value={rate}
            onChange={(e) => setRateIn(e.target.value)}
            aria-invalid={rate !== "" && !validRate}
            className={field}
          />
        </div>
        <div>
          <span className={label}>Loan term</span>
          <Select variant="field" label="Loan term" value={String(term)} options={[{ value: "30", label: "30 years" }, { value: "15", label: "15 years" }]} onChange={(v) => setTerm(Number(v))} />
        </div>
      </div>
      {rate !== "" && !validRate && <p role="alert" className="mt-2 text-sm text-danger">Enter a rate between 0 and 30.</p>}

      <div className="mt-5 rounded-2xl bg-sage p-5" aria-live="polite">
        <p className="flex items-center gap-1.5 text-sm font-medium text-sage-ink">
          Estimated payment <Info size={14} aria-hidden />
        </p>
        {est.status === "error" && !b ? (
          <ErrorState error={est.error} onRetry={est.reload} compact title="Couldn't calculate" />
        ) : b ? (
          <>
            <p className="font-display mt-1 text-5xl font-bold leading-none text-ink">
              {usd2(b.total_monthly)}
              <span className="text-2xl font-semibold text-ink-soft"> / mo</span>
            </p>
            <BreakdownBar parts={breakdownParts(b)} className="mt-4 !bg-surface/60" />
            <p className="mt-3 text-[12.5px] leading-snug text-sage-ink">
              Principal and interest {usd2(b.principal_interest)}, taxes {usd2(b.property_tax)}, insurance {usd2(b.insurance)}
              {b.hoa ? `, HOA ${usd2(b.hoa)}` : ""}
              {b.pmi_applies ? `, PMI ${usd2(b.pmi)}` : ""}.
            </p>
          </>
        ) : (
          <div aria-hidden>
            <Skeleton className="mt-2 h-12 w-56 !bg-surface/50" />
            <Skeleton className="mt-4 h-3.5 w-full !bg-surface/50" />
          </div>
        )}
      </div>

      <Link
        href={calcHref}
        className="mt-4 inline-flex h-12 w-full items-center justify-center gap-2 rounded-full bg-primary text-[14px] font-medium text-on-primary transition-[background-color,transform] hover:bg-primary-hover active:scale-[0.98]"
      >
        Open mortgage calculator <ArrowUpRight size={16} weight="bold" aria-hidden />
      </Link>
      <p className="mt-3 text-center text-xs text-muted">Estimates are illustrative, not loan offers.</p>
    </section>
  );
}
