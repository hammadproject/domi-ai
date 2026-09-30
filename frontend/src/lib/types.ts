// Shapes returned by the Domi backend (see backend/app/api and backend/app/tools).

export type PropertyType =
  | "Single Family"
  | "Condo"
  | "Townhouse"
  | "Manufactured"
  | "Multi-Family"
  | "Apartment"
  | "Land";

export interface Listing {
  id: string;
  address: string;
  city: string;
  state: string;
  zip: string | null;
  lat: number | null;
  lng: number | null;
  price: number | null;
  beds: number | null;
  baths: number | null;
  sqft: number | null;
  year_built: number | null;
  property_type: string | null;
  hoa_fee: number | null;
}

export interface ListingDetail extends Listing {
  lot_size: number | null;
  description: string | null;
  features: Record<string, unknown> | null;
}

export interface ListingsPage {
  items: Listing[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface CityStats {
  city: string;
  state: string;
  listing_count: number;
  median_price: number | null;
  min_price: number | null;
  max_price: number | null;
  center_lat: number | null;
  center_lng: number | null;
}

export interface PaymentBreakdown {
  price: number;
  down_payment: number;
  down_payment_pct: number;
  loan_amount: number;
  term_years: number;
  interest_rate: number;
  principal_interest: number;
  property_tax: number;
  insurance: number;
  hoa: number;
  pmi: number;
  pmi_applies: boolean;
  total_monthly: number;
  total_interest_over_term: number;
  assumptions_note: string;
}

export interface TermComparison {
  shorter: PaymentBreakdown;
  longer: PaymentBreakdown;
  monthly_difference: number;
  interest_saved_by_shorter: number;
}

export interface Affordability {
  affordable: boolean;
  max_home_price: number | null;
  max_loan_amount: number | null;
  estimated_monthly_payment: number | null;
  monthly_budget: number;
  binding_limit: "front_end_dti" | "back_end_dti";
  down_payment: number;
  note: string;
}

export interface MortgageDefaults {
  interest_rate: number;
  property_tax_rate: number;
  insurance_annual: number;
  pmi_rate: number;
  front_end_dti: number;
  back_end_dti: number;
  pmi_down_payment_threshold_pct: number;
}

export interface AssumptionOverrides {
  interest_rate?: number;
  property_tax_rate?: number;
  insurance_annual?: number;
  pmi_rate?: number;
  front_end_dti?: number;
  back_end_dti?: number;
}

export interface ListingComparison {
  id: string;
  address: string;
  city: string;
  state: string;
  zip: string | null;
  property_type: string | null;
  lat: number | null;
  lng: number | null;
  price: number | null;
  price_per_sqft: number | null;
  beds: number | null;
  baths: number | null;
  sqft: number | null;
  year_built: number | null;
  hoa_fee: number | null;
  est_monthly_payment: number | null;
  pros: string[];
  cons: string[];
  missing_fields: string[];
}

export interface Comparison {
  listings: ListingComparison[];
  down_payment_pct: number;
  term_years: number;
  payment_note: string;
}

// ---- chat (SSE) ----
export interface ChatListing extends Listing {
  rank: number;
}

export type ChatEvent =
  | { type: "listings"; listings: ChatListing[]; highlight_ids: string[] }
  | { type: "token"; text: string }
  | {
      type: "done";
      session_id: string;
      intent: string;
      llm_calls: number;
      refused: boolean;
      degraded: boolean;
      trace_id: string | null;
      /** for search turns: the filters the results actually used */
      filters: Record<string, string | number> | null;
      relaxations: string[];
    }
  | { type: "error"; code: string; message: string; retry_after?: number };
