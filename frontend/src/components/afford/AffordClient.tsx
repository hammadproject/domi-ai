"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, CaretDown, ChartBar, HouseLine, Lock } from "@phosphor-icons/react";
import { BreakdownBar, breakdownParts } from "@/components/afford/Breakdown";
import { Button, LinkButton } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorState } from "@/components/ui/States";
import { api } from "@/lib/api";
import { usd, usd2 } from "@/lib/format";
import type { Affordability } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

const money = (s: string) => {
  const n = Number(s.replace(/[$,\s]/g, ""));
  return s.trim() !== "" && Number.isFinite(n) ? n : NaN;
};
const round = (n: number) => Math.round(n);

function Field({
  id, label, value, onChange, prefix, suffix, hint, invalid, className = "",
}: {
  id: string; label: string; value: string; onChange: (v: string) => void;
  prefix?: string; suffix?: string; hint?: string; invalid?: boolean; className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1 block text-[13px] font-medium text-ink-soft">{label}</label>
      <div className={`focus-ring-within flex h-10 items-center rounded-xl border bg-canvas px-3 ${invalid ? "border-danger" : "border-line"}`}>
        {prefix && <span className="mr-1.5 text-ink-soft" aria-hidden>{prefix}</span>}
        <input
          id={id}
          inputMode="decimal"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={invalid || undefined}
          aria-describedby={hint ? `${id}-hint` : undefined}
          className="h-full min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none focus:outline-none focus-visible:outline-none"
        />
        {suffix && <span className="ml-1.5 text-ink-soft" aria-hidden>{suffix}</span>}
      </div>
      {hint && <p id={`${id}-hint`} className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

function useDebounced<T>(value: T, ms = 350): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function AffordClient() {
  const sp = useSearchParams();
  const defaults = useAsync((s) => api.mortgageDefaults(s), "mortgage-defaults");
  const cities = useAsync((s) => api.cities(s), "cities");
  const d = defaults.data;

  // ---- calculator inputs ----
  // Each field is "what the person typed, or else the default": defaults are derived during
  // render (from the server's assumptions and the price), never copied into state by effects.
  const [priceIn, setPriceIn] = useState<string | null>(sp.get("price"));
  const defaultPrice = useMemo(() => {
    const medians = (cities.data ?? [])
      .map((c) => c.median_price)
      .filter((m): m is number => m != null)
      .sort((a, b) => a - b);
    return medians.length ? String(Math.round(medians[Math.floor(medians.length / 2)] / 5000) * 5000) : "";
  }, [cities.data]);
  const price = priceIn ?? defaultPrice;
  const priceNum = money(price);

  // linked down payment: one source of truth (what was typed and in which unit); the other unit is derived
  const [downIn, setDownIn] = useState<{ mode: "pct" | "amt"; value: string }>({
    mode: "pct",
    value: sp.get("down") ?? "20",
  });
  const typedDown = money(downIn.value);
  const downPct =
    downIn.mode === "pct"
      ? downIn.value
      : Number.isFinite(typedDown) && priceNum > 0
        ? String(Math.round((typedDown / priceNum) * 1000) / 10)
        : "";
  const downAmt =
    downIn.mode === "amt"
      ? downIn.value
      : Number.isFinite(typedDown) && Number.isFinite(priceNum)
        ? String(round((priceNum * typedDown) / 100))
        : "";

  const [rateIn, setRateIn] = useState<string | null>(sp.get("rate"));
  const [taxIn, setTaxIn] = useState<string | null>(null);
  const [insIn, setInsIn] = useState<string | null>(null);
  const [pmiIn, setPmiIn] = useState<string | null>(null);
  const [term, setTerm] = useState<15 | 30>(sp.get("term") === "15" ? 15 : 30);
  const [hoa, setHoa] = useState(sp.get("hoa") ?? "0");
  const [feesOpen, setFeesOpen] = useState(true);

  const rate = rateIn ?? (d ? String(d.interest_rate) : "");
  const tax = taxIn ?? (d && Number.isFinite(priceNum) ? String(round((priceNum * d.property_tax_rate) / 100)) : "");
  const ins = insIn ?? (d ? String(d.insurance_annual) : "");
  const pmi = pmiIn ?? (d ? String(d.pmi_rate) : "");

  const downNum = money(downAmt);
  const rateNum = Number(rate);
  const taxNum = money(tax);
  const insNum = money(ins);
  const hoaNum = money(hoa || "0");
  const pmiNum = Number(pmi);

  const errors = {
    price: !(priceNum > 0 && priceNum <= 100_000_000) && price !== "" ? "Enter a price above $0." : "",
    down: Number.isFinite(downNum) && Number.isFinite(priceNum) && (downNum < 0 || downNum > priceNum) ? "Down payment can't exceed the price." : "",
    rate: rate !== "" && !(rateNum >= 0 && rateNum <= 30) ? "Enter a rate from 0 to 30." : "",
  };
  const ready =
    priceNum > 0 && Number.isFinite(downNum) && downNum >= 0 && downNum <= priceNum && rateNum >= 0 && rateNum <= 30 &&
    Number.isFinite(taxNum) && Number.isFinite(insNum) && Number.isFinite(hoaNum) && pmiNum >= 0 && d !== undefined;

  const body = useMemo(
    () =>
      ready
        ? {
            price: priceNum, down_payment: downNum, term_years: term, hoa_monthly: hoaNum,
            interest_rate: rateNum, property_tax_rate: (taxNum / priceNum) * 100,
            insurance_annual: insNum, pmi_rate: pmiNum,
          }
        : null,
    [ready, priceNum, downNum, term, hoaNum, rateNum, taxNum, insNum, pmiNum],
  );
  const debounced = useDebounced(body);
  const key = JSON.stringify(debounced);

  const est = useAsync((s) => api.estimate(debounced!, s), `est:${key}`, debounced !== null);
  const terms = useAsync(
    (s) => {
      const { term_years: _t, ...rest } = debounced!;
      void _t;
      return api.compareTerms(rest, s);
    },
    `terms:${key}`,
    debounced !== null,
  );
  const b = est.data;

  // ---- how much could I afford ----
  const [income, setIncome] = useState("");
  const [debts, setDebts] = useState("");
  const [avail, setAvail] = useState("");
  const [dtiIn, setDtiIn] = useState<string | null>(null);
  const dti = dtiIn ?? (d ? String(Math.round(d.back_end_dti * 100)) : "");
  const [afford, setAfford] = useState<{ status: "idle" | "loading" | "error" | "done"; data?: Affordability; error?: unknown }>({ status: "idle" });
  const incomeNum = money(income);
  const availNum = money(avail);
  const debtsNum = money(debts || "0");
  const affordReady = incomeNum > 0 && Number.isFinite(availNum) && availNum >= 0 && Number.isFinite(debtsNum) && debtsNum >= 0;

  const runAfford = async () => {
    if (!affordReady) return;
    setAfford({ status: "loading" });
    try {
      const data = await api.affordability({
        annual_income: incomeNum, down_payment: availNum, monthly_debts: debtsNum,
        hoa_monthly: Number.isFinite(hoaNum) ? hoaNum : 0, term_years: term,
        ...(rateNum >= 0 && rateNum <= 30 ? { interest_rate: rateNum } : {}),
        ...(Number.isFinite(insNum) ? { insurance_annual: insNum } : {}),
        back_end_dti: Number(dti) / 100,
      });
      setAfford({ status: "done", data });
    } catch (e) {
      setAfford({ status: "error", error: e });
    }
  };

  const t = terms.data;

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 pb-16 pt-5 sm:px-8">
      <h1 className="font-display text-3xl font-bold text-ink sm:text-4xl">Make room in your budget.</h1>
      <p className="mt-1 max-w-[60ch] text-ink-soft">Explore monthly payments and what you may be able to afford.</p>

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
        {/* ---------- calculator ---------- */}
        <section aria-label="Mortgage calculator" className="rounded-card border border-line bg-surface p-5 sm:p-6">
          <h2 className="font-display text-2xl font-bold text-ink">Mortgage calculator</h2>
          <div className="mt-4 grid gap-x-4 gap-y-3.5 sm:grid-cols-3">
            <Field id="price" label="Purchase price" value={price} onChange={setPriceIn} prefix="$" invalid={Boolean(errors.price)} hint={errors.price} />
            <Field id="down-pct" label="Down payment %" value={downPct} onChange={(v) => setDownIn({ mode: "pct", value: v })} suffix="%" />
            <Field id="down-amt" label="Down payment $" value={downAmt} onChange={(v) => setDownIn({ mode: "amt", value: v })} prefix="$" invalid={Boolean(errors.down)} hint={errors.down || undefined} />
            <Field id="rate" label="Interest rate" value={rate} onChange={setRateIn} suffix="%" invalid={Boolean(errors.rate)} hint={errors.rate} />
            <div>
              <span className="mb-1.5 block text-[13px] font-medium text-ink-soft" id="term-label">Loan term</span>
              <div role="group" aria-labelledby="term-label" className="flex h-10 rounded-full border border-line bg-canvas p-1">
                {([15, 30] as const).map((y) => (
                  <button key={y} type="button" onClick={() => setTerm(y)} aria-pressed={term === y} className={`flex-1 rounded-full text-sm font-medium transition-colors ${term === y ? "bg-sage text-sage-ink" : "text-ink-soft hover:text-ink"}`}>
                    {y} years
                  </button>
                ))}
              </div>
            </div>
            <Field id="hoa" label="Monthly HOA" value={hoa} onChange={setHoa} prefix="$" />
          </div>

          <div className="mt-5 border-t border-line pt-4">
            <button type="button" onClick={() => setFeesOpen((v) => !v)} aria-expanded={feesOpen} className="flex w-full items-center justify-between text-left">
              <span className="text-[17px] font-semibold text-ink">Taxes &amp; insurance</span>
              <CaretDown size={18} className={`transition-transform ${feesOpen ? "rotate-180" : ""}`} aria-hidden />
            </button>
            {feesOpen && (
              <div className="mt-3 grid gap-x-4 gap-y-3.5 sm:grid-cols-3">
                <Field id="tax" label="Property tax / yr" value={tax} onChange={setTaxIn} prefix="$" />
                <Field id="ins" label="Insurance / yr" value={ins} onChange={setInsIn} prefix="$" />
                <Field id="pmi" label="PMI rate / yr" value={pmi} onChange={setPmiIn} suffix="%" />
              </div>
            )}
          </div>

        </section>

        {/* ---------- results ---------- */}
        <section aria-label="Estimated monthly payment" className="rounded-card border border-line bg-sage p-5 sm:p-6" aria-live="polite">
          <h2 className="font-display text-2xl font-bold text-ink">Estimated monthly payment</h2>
          {defaults.status === "error" && !d ? (
            <ErrorState error={defaults.error} onRetry={defaults.reload} compact title="Couldn't load the assumptions" />
          ) : est.status === "error" && !b ? (
            <ErrorState error={est.error} onRetry={est.reload} compact title="Couldn't calculate" />
          ) : !b ? (
            <div className="mt-6" aria-hidden>
              <Skeleton className="h-16 w-72 !bg-surface/50" />
              <Skeleton className="mt-6 h-3.5 w-full !bg-surface/50" />
              <Skeleton className="mt-6 h-24 w-full !bg-surface/50" />
            </div>
          ) : (
            <>
              <p className={`font-display mt-2 text-5xl font-bold leading-none text-ink transition-opacity ${est.status === "loading" ? "opacity-60" : ""}`}>
                {usd2(b.total_monthly)}
                <span className="text-3xl font-semibold text-ink-soft"> / mo</span>
              </p>
              <BreakdownBar parts={breakdownParts(b)} className="mt-4 !bg-surface/60" />
              <ul className="mt-3 space-y-1.5">
                {breakdownParts(b)
                  .filter((p) => p.value > 0 || ['pi', 'tax', 'ins'].includes(p.key))
                  .map((p) => (
                  <li key={p.key} className="flex items-center justify-between gap-3 text-[15px]">
                    <span className="inline-flex items-center gap-2.5 text-ink-soft">
                      <span className="size-3 rounded-full" style={{ background: p.color }} aria-hidden />
                      {p.label}
                    </span>
                    <span className="tabular font-medium text-ink">{usd2(p.value)}</span>
                  </li>
                ))}
              </ul>
              {b.pmi_applies && <p className="mt-3 text-sm text-sage-ink">PMI is included because the down payment is under 20%.</p>}

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                {t ? (
                  [t.shorter, t.longer].map((x, i) => (
                    <div key={x.term_years} className={`rounded-2xl border bg-surface p-3 ${x.term_years === term ? "border-primary ring-1 ring-primary" : "border-line"}`}>
                      <p className="text-sm font-semibold text-ink">{x.term_years} years</p>
                      <p className="font-display text-xl font-bold text-ink">{usd2(x.total_monthly)}<span className="text-base font-semibold text-ink-soft"> / mo</span></p>
                      <p className="mt-0.5 text-xs text-ink-soft">{i === 0 ? "Higher payment, less interest" : "Lower payment, more interest"}: {usd(x.total_interest_over_term)} over the loan</p>
                    </div>
                  ))
                ) : (
                  <Skeleton className="h-28 w-full sm:col-span-2 !bg-surface/50" />
                )}
              </div>
              {t && (
                <p className="mt-3 text-sm text-sage-ink">
                  The {t.shorter.term_years}-year loan costs {usd2(Math.abs(t.monthly_difference))} more each month and saves about {usd(t.interest_saved_by_shorter)} in interest.
                </p>
              )}
              <p className="mt-4 border-t border-sage-strong pt-3 text-xs text-sage-ink">{b.assumptions_note} Estimates are illustrative, not loan offers.</p>
            </>
          )}
        </section>
      </div>

      {/* ---------- how much could I afford ---------- */}
      <section aria-label="How much home could I afford" className="mt-4 grid gap-5 rounded-card border border-line bg-surface p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div>
          <h2 className="font-display text-2xl font-bold text-ink">How much home could I afford?</h2>
          <p className="mt-2 max-w-[48ch] text-ink-soft">Based on your income, debts and down payment, see a price range that may fit your budget.</p>
          <div className="mt-4 grid gap-x-4 gap-y-3.5 sm:grid-cols-2">
            <Field id="income" label="Annual gross income" value={income} onChange={setIncome} prefix="$" />
            <Field id="debts" label="Monthly debt payments" value={debts} onChange={setDebts} prefix="$" hint="Cards, car loans, student loans." />
            <Field id="avail" label="Available down payment" value={avail} onChange={setAvail} prefix="$" />
            <div>
              <span className="mb-1 block text-[13px] font-medium text-ink-soft">Max total debt-to-income</span>
              <Select variant="field" label="Max total debt-to-income" value={dti} options={[28, 33, 36, 41, 43, 45, 50].map((v) => ({ value: String(v), label: `${v}%` }))} onChange={(v) => setDtiIn(v)} />
              <p className="mt-1 text-xs text-muted">Includes housing, debts and this new loan.</p>
            </div>
          </div>
          <Button onClick={runAfford} disabled={!affordReady || afford.status === "loading"} className="mt-5">
            {afford.status === "loading" ? "Estimating" : "Estimate affordability"}
          </Button>
        </div>

        <div className="flex min-h-[260px] flex-col justify-center rounded-2xl bg-sage p-6" aria-live="polite">
          {afford.status === "error" ? (
            <ErrorState error={afford.error as Error} onRetry={runAfford} compact title="Couldn't estimate" />
          ) : afford.status === "done" && afford.data ? (
            afford.data.affordable ? (
              <>
                <p className="text-sm font-medium text-sage-ink">You may be able to afford a home up to about</p>
                <p className="font-display mt-1 text-5xl font-bold text-ink">{usd(afford.data.max_home_price)}</p>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div><dt className="text-sage-ink">Loan amount</dt><dd className="text-lg font-semibold text-ink">{usd(afford.data.max_loan_amount)}</dd></div>
                  <div><dt className="text-sage-ink">Estimated payment</dt><dd className="text-lg font-semibold text-ink">{usd2(afford.data.estimated_monthly_payment ?? 0)}/mo</dd></div>
                  <div className="col-span-2"><dt className="text-sage-ink">Monthly housing budget</dt><dd className="text-lg font-semibold text-ink">{usd2(afford.data.monthly_budget)}</dd></div>
                </dl>
                <p className="mt-3 text-sm text-sage-ink">
                  Your {afford.data.binding_limit === "front_end_dti" ? "housing-to-income" : "total debt-to-income"} limit sets this budget.
                </p>
                <Button variant="secondary" size="sm" className="mt-4 self-start" onClick={() => afford.data?.max_home_price && setPriceIn(String(Math.round(afford.data.max_home_price)))}>
                  Use this price in the calculator
                </Button>
              </>
            ) : (
              <>
                <p className="font-display text-2xl font-bold text-ink">Not enough room in this budget yet</p>
                <p className="mt-2 text-ink-soft">
                  Under these limits your monthly housing budget is {usd2(afford.data.monthly_budget)}, which does not cover the base costs of a home. A larger down payment or lower monthly debts would help.
                </p>
              </>
            )
          ) : (
            <>
              <HouseLine size={36} className="text-primary" aria-hidden />
              <p className="font-display mt-3 text-2xl font-bold text-ink">Your estimated budget appears here.</p>
              <p className="mt-1 text-ink-soft">Based on income, existing debts, down payment and the loan assumptions on this page.</p>
            </>
          )}
          <p className="mt-5 flex items-start gap-2 border-t border-sage-strong pt-3 text-xs text-sage-ink">
            <Lock size={14} className="mt-0.5 shrink-0" aria-hidden />
            Calculated by the mortgage tool. Personal financial inputs are not sent to the AI model.
          </p>
        </div>
      </section>

      <section className="mt-4 flex flex-col gap-4 rounded-card bg-sage p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
        <div className="flex items-start gap-4">
          <span className="grid size-11 shrink-0 place-items-center rounded-full bg-surface text-primary"><ChartBar size={24} aria-hidden /></span>
          <div>
            <h2 className="font-display text-xl font-bold text-ink">Ready to see homes in your range?</h2>
            <p className="mt-1 text-ink-soft">
              {afford.status === "done" && afford.data?.affordable && afford.data.max_home_price
                ? `Browse homes up to about ${usd(afford.data.max_home_price)}, or line a few up side by side.`
                : "Browse homes on the map, or line a few up side by side."}
            </p>
          </div>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row">
          <LinkButton variant="secondary" href="/compare">Compare homes</LinkButton>
          <LinkButton
            href={
              afford.status === "done" && afford.data?.affordable && afford.data.max_home_price
                ? `/explore?price_max=${Math.round(afford.data.max_home_price)}`
                : "/explore"
            }
          >
            Browse homes <ArrowRight size={16} weight="bold" aria-hidden />
          </LinkButton>
        </div>
      </section>
    </div>
  );
}
