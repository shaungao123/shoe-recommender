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
  scores: CatalogScores | null;
}

/** One reviewer's ratings. Ratings are 0-10; outdoor_pct is 0-100. */
export interface CatalogScores {
  source: string;
  overall: number | null;
  traction: number | null;
  cushion: number | null;
  support: number | null;
  fit: number | null;
  materials: number | null;
  outdoor_pct: number | null;
  expert_review_count: number | null;
}

export interface AttributedExcerpt {
  source: string;
  text: string;
}

export interface SourceLink {
  source: string;
  url: string;
}

export interface ShoeDetail extends CatalogShoe {
  source_url: string | null;
  specs: Record<string, unknown>;
  extra_metadata: {
    pros: AttributedExcerpt[];
    cons: AttributedExcerpt[];
    review_text: AttributedExcerpt[];
    metrics: Record<string, Record<string, unknown>>;
    sources: SourceLink[];
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
  sort: CatalogSort;
}

export const CATALOG_SORT_OPTIONS = [
  { value: "newest", label: "Newest" },
  { value: "score_overall", label: "Top rated" },
  { value: "score_traction", label: "Best traction" },
  { value: "score_cushion", label: "Best cushion" },
  { value: "score_support", label: "Best support" },
  { value: "score_fit", label: "Best fit" },
  { value: "score_outdoor", label: "Best outdoors" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
] as const;

export type CatalogSort = (typeof CATALOG_SORT_OPTIONS)[number]["value"];

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

const SOURCE_NAMES: Record<string, string> = {
  thehoopsgeek: "The Hoops Geek",
  runrepeat: "RunRepeat",
  weartesters: "WearTesters",
  basketballshoespecs: "Basketball Shoe Specs",
};

export function sourceName(source: string): string {
  return SOURCE_NAMES[source] ?? source;
}

// The tags that read as a reviewer's overall take, most useful first.
const HIGHLIGHT_TAGS = ["summary", "our verdict", "overall", "best for", "intro"];
const MAX_EXCERPT_CHARS = 240;

function shortenExcerpt(text: string): string {
  if (text.length <= MAX_EXCERPT_CHARS) return text;
  const cut = text.slice(0, MAX_EXCERPT_CHARS);
  const sentenceEnd = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("! "), cut.lastIndexOf("? "));
  if (sentenceEnd >= 80) return cut.slice(0, sentenceEnd + 1);
  return `${cut.slice(0, cut.lastIndexOf(" "))}…`;
}

/** One short overall take per reviewer, without the pipeline's "[tag]" prefixes. */
export function reviewHighlights(reviewText: AttributedExcerpt[], limit = 3): AttributedExcerpt[] {
  const bestBySource = new Map<string, { rank: number; text: string }>();
  for (const { source, text } of reviewText) {
    const match = text.match(/^\[([^\]]+)\]\s*/);
    const rank = match ? HIGHLIGHT_TAGS.indexOf(match[1].toLowerCase()) : -1;
    if (rank === -1) continue;
    const current = bestBySource.get(source);
    if (!current || rank < current.rank) {
      bestBySource.set(source, { rank, text: text.slice(match![0].length) });
    }
  }
  return [...bestBySource.entries()]
    .sort(([, a], [, b]) => a.rank - b.rank)
    .slice(0, limit)
    .map(([source, { text }]) => ({ source, text: shortenExcerpt(text) }));
}

const CATALOG_RETURN_KEY = "catalog-return-query";

/** Remembers the current filters so a shoe page can link back to the same view. */
export function rememberCatalogView(query: string): void {
  try {
    window.sessionStorage.setItem(CATALOG_RETURN_KEY, query);
  } catch {
    // Storage can be unavailable; the back link then just opens the full catalog.
  }
}

export function catalogReturnPath(): string {
  try {
    const query = window.sessionStorage.getItem(CATALOG_RETURN_KEY);
    return query ? `/catalog?${query}` : "/catalog";
  } catch {
    return "/catalog";
  }
}

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
  const sort = CATALOG_SORT_OPTIONS.find((option) => option.value === params.get("sort"))?.value;
  return {
    query: params.get("search") ?? "",
    brand: params.get("brand") ?? "",
    budgetMax: params.get("budget_max") ?? "",
    position: params.get("position") ?? "",
    playstyle: params.get("playstyle") ?? "",
    outdoor: params.get("outdoor") ?? "",
    cut: params.get("cut") ?? "",
    width: params.get("width") ?? "",
    sort: sort ?? EMPTY_CATALOG_FILTERS.sort,
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
