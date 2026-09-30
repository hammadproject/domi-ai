import type {
  AssumptionOverrides,
  Affordability,
  CityStats,
  Comparison,
  ListingDetail,
  ListingsPage,
  MortgageDefaults,
  PaymentBreakdown,
  TermComparison,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

/** A failed request, carrying what the UI needs to explain it and offer a retry. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly requestId: string | null = null,
    public readonly retryAfter: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get isNetwork() {
    return this.status === 0;
  }
  get isRateLimited() {
    return this.status === 429;
  }
  get isBusy() {
    return this.code === "high_demand";
  }

  /** A sentence that is safe and kind to show to a person. */
  get friendly(): string {
    if (this.isNetwork) return "Domi can't reach its servers right now. Check your connection, or try again in a moment.";
    if (this.isRateLimited)
      return `That was a lot of requests at once. Please wait ${this.retryAfter ?? 30} seconds and try again.`;
    if (this.isBusy) return "Domi is seeing high demand right now. Please try again a little later.";
    if (this.status >= 500) return "Something went wrong on our side. Please try again.";
    return this.message;
  }
}

export async function toApiError(res: Response): Promise<ApiError> {
  let code = "http_error";
  let message = `Request failed (${res.status}).`;
  let requestId = res.headers.get("x-request-id");
  try {
    const body = await res.json();
    const err = body?.error;
    if (err) {
      code = err.code ?? code;
      message = err.message ?? message;
      requestId = err.request_id ?? requestId;
      if (Array.isArray(err.details) && err.details.length) {
        message = err.details.map((d: { message: string }) => d.message).join(" ");
      }
    }
  } catch {
    /* body was not JSON */
  }
  const retry = Number(res.headers.get("retry-after"));
  return new ApiError(message, res.status, code, requestId, Number.isFinite(retry) && retry > 0 ? retry : null);
}

async function request<T>(
  path: string,
  init: { method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: init.method ?? (init.body === undefined ? "GET" : "POST"),
      headers: init.body === undefined ? undefined : { "Content-Type": "application/json" },
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
      signal: init.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError("Network error", 0, "network");
  }
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

// ---- GET de-duplication -------------------------------------------------------------
// Several components on one page ask for the same thing (e.g. the city list). Share the
// in-flight request and reuse a successful answer briefly, so one page load = one request.
// (Errors are never cached, and each caller can still abort its own wait.)
const GET_TTL_MS = 45_000;
const recentGets = new Map<string, { at: number; promise: Promise<unknown> }>();

function withAbort<T>(promise: Promise<T>, signal?: AbortSignal): Promise<T> {
  if (!signal) return promise;
  return new Promise<T>((resolve, reject) => {
    const aborted = () => reject(new DOMException("Aborted", "AbortError"));
    if (signal.aborted) return aborted();
    signal.addEventListener("abort", aborted, { once: true });
    promise.then(
      (v) => {
        signal.removeEventListener("abort", aborted);
        resolve(v);
      },
      (e) => {
        signal.removeEventListener("abort", aborted);
        reject(e);
      },
    );
  });
}

function sharedGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const hit = recentGets.get(path);
  if (hit && Date.now() - hit.at < GET_TTL_MS) return withAbort(hit.promise as Promise<T>, signal);
  const promise = request<T>(path).catch((e) => {
    recentGets.delete(path);
    throw e;
  });
  recentGets.set(path, { at: Date.now(), promise });
  return withAbort(promise, signal);
}

export interface ListingQuery {
  city?: string;
  state?: string;
  price_min?: number;
  price_max?: number;
  beds_min?: number;
  baths_min?: number;
  sqft_min?: number;
  property_type?: string;
  sort?: "price_asc" | "price_desc" | "newest" | "sqft_desc";
  page?: number;
  page_size?: number;
}

export function listingsQueryString(q: ListingQuery): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  }
  return p.toString();
}

export const api = {
  listings: (q: ListingQuery, signal?: AbortSignal) =>
    sharedGet<ListingsPage>(`/api/listings?${listingsQueryString(q)}`, signal),
  listing: (id: string, signal?: AbortSignal) =>
    sharedGet<ListingDetail>(`/api/listings/${encodeURIComponent(id)}`, signal),
  cities: (signal?: AbortSignal) => sharedGet<CityStats[]>("/api/cities", signal),
  mortgageDefaults: (signal?: AbortSignal) =>
    sharedGet<MortgageDefaults>("/api/mortgage/defaults", signal),
  estimate: (
    body: {
      price: number;
      down_payment?: number;
      down_payment_pct?: number;
      term_years?: number;
      hoa_monthly?: number;
    } & AssumptionOverrides,
    signal?: AbortSignal,
  ) => request<PaymentBreakdown>("/api/mortgage/estimate", { body, signal }),
  compareTerms: (
    body: {
      price: number;
      down_payment?: number;
      down_payment_pct?: number;
      hoa_monthly?: number;
    } & AssumptionOverrides,
    signal?: AbortSignal,
  ) => request<TermComparison>("/api/mortgage/compare-terms", { body, signal }),
  affordability: (
    body: {
      annual_income: number;
      down_payment: number;
      monthly_debts?: number;
      hoa_monthly?: number;
      term_years?: number;
    } & AssumptionOverrides,
    signal?: AbortSignal,
  ) => request<Affordability>("/api/mortgage/affordability", { body, signal }),
  compare: (
    body: { listing_ids: string[]; down_payment_pct?: number; term_years?: number } & AssumptionOverrides,
    signal?: AbortSignal,
  ) => request<Comparison>("/api/compare", { body, signal }),
};
