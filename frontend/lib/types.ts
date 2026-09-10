/**
 * Types mirroring the backend `/recommend` and `/feedback` contracts.
 * Must stay in sync with `backend/app/schemas/recommend.py` and
 * `backend/app/schemas/feedback.py` — change them together.
 */

export interface RecommendRequest {
  /** Free-text playstyle composed from position, style tags, and the user's own words. */
  playstyle: string;
  /** Max price in USD; null means no cap. */
  budget: number | null;
  /** Optional free-text look/colorway preference. */
  aesthetic: string | null;
}

export interface RecommendedShoe {
  id: number;
  brand: string;
  model: string;
  /** USD; null when price data is unavailable. */
  price: number | null;
  image_url: string | null;
  /** Short spec chips, e.g. "Mid cut", "11.2 oz". */
  specs: string[];
  /** The grounded "why this fits you" explanation. */
  explanation: string;
  /** Affiliate-tracked buy link; null until affiliate feeds exist. */
  affiliate_url: string | null;
}

export interface RecommendResponse {
  /** Ranked best-first; expected length 3. */
  recommendations: RecommendedShoe[];
}

export type FeedbackVote = "up" | "down";

export interface FeedbackRequest {
  shoe_id: number;
  vote: FeedbackVote;
}

/** Editorial "trending" card on the home screen (not personalized). */
export interface TrendingShoe {
  brand: string;
  model: string;
  price: string;
  blurb: string;
}
