/** Typed client and models for the public shoe catalog. */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

export interface CatalogShoe {
  id: number;
  canonical_id: string | null;
  brand: string;
  name: string;
  price: number | null;
  currency: string;
  image_url: string | null;
  affiliate_url: string | null;
  release_year: number | null;
  signature_player: string | null;
  weight_oz: number | null;
  cut_height: string | null;
  width_fit: string | null;
  outdoor_suitability: string | null;
  cushioning_tech: string | null;
  position_tags: string[];
  playstyle_tags: string[];
}

export interface AttributedExcerpt {
  source: string;
  text: string;
}

export interface ShoeDetail extends CatalogShoe {
  source_url: string | null;
  specs: Record<string, unknown>;
  extra_metadata: {
    pros: AttributedExcerpt[];
    cons: AttributedExcerpt[];
    review_text: AttributedExcerpt[];
  };
  created_at: string;
  updated_at: string;
}

export interface CatalogResponse {
  items: CatalogShoe[];
  total: number;
  limit: number;
  offset: number;
}

export interface CatalogFilters {
  query: string;
  brand: string;
  budgetMax: string;
  position: string;
  playstyle: string;
  outdoor: string;
  cut: string;
  width: string;
  sort: "newest" | "price_asc" | "price_desc";
}

export const EMPTY_CATALOG_FILTERS: CatalogFilters = {
  query: "",
  brand: "",
  budgetMax: "",
  position: "",
  playstyle: "",
  outdoor: "",
  cut: "",
  width: "",
  sort: "newest",
};

const CATALOG_SORTS: CatalogFilters["sort"][] = ["newest", "price_asc", "price_desc"];

/** Filters as query params — shared by the API request and the page URL. */
function filterParams(filters: CatalogFilters): URLSearchParams {
  const params = new URLSearchParams();
  const validBudget = Number(filters.budgetMax) >= 0 ? filters.budgetMax : "";
  const values: Record<string, string> = {
    search: filters.query,
    brand: filters.brand,
    budget_max: validBudget,
    position: filters.position,
    playstyle: filters.playstyle,
    outdoor: filters.outdoor,
    cut: filters.cut,
    width: filters.width,
    sort: filters.sort,
  };
  for (const [key, value] of Object.entries(values)) {
    if (value) params.set(key, value);
  }
  return params;
}

function catalogParams(filters: CatalogFilters, offset: number, limit: number): URLSearchParams {
  const params = filterParams(filters);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return params;
}

/** Page URL query for the current view; `shown` restores "Show more" progress. */
export function catalogUrlQuery(filters: CatalogFilters, shown: number, pageSize: number): string {
  const params = filterParams(filters);
  if (filters.sort === EMPTY_CATALOG_FILTERS.sort) params.delete("sort");
  if (shown > pageSize) params.set("shown", String(shown));
  return params.toString();
}

export function catalogFiltersFromUrl(params: { get(name: string): string | null }): CatalogFilters {
  const sort = params.get("sort") as CatalogFilters["sort"] | null;
  return {
    query: params.get("search") ?? "",
    brand: params.get("brand") ?? "",
    budgetMax: params.get("budget_max") ?? "",
    position: params.get("position") ?? "",
    playstyle: params.get("playstyle") ?? "",
    outdoor: params.get("outdoor") ?? "",
    cut: params.get("cut") ?? "",
    width: params.get("width") ?? "",
    sort: sort && CATALOG_SORTS.includes(sort) ? sort : EMPTY_CATALOG_FILTERS.sort,
  };
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) throw new Error(`Catalog request failed (${response.status})`);
  return (await response.json()) as T;
}

export function getCatalog(filters: CatalogFilters, offset = 0, limit = 24, signal?: AbortSignal) {
  return request<CatalogResponse>(`/shoes?${catalogParams(filters, offset, limit)}`, signal);
}

export function getShoe(id: number, signal?: AbortSignal) {
  return request<ShoeDetail>(`/shoes/${id}`, signal);
}
