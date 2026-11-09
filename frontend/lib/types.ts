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
  /** Optional free-text look preference; the quiz no longer asks for one. */
  aesthetic: string | null;
  /** The fields below reorder results; they never exclude shoes. */
  court: Court | null;
  /** At most two. */
  priorities: Priority[];
  foot_width: FootWidth | null;
  preferred_brand: string | null;
  preferred_cut: Cut | null;
}

export type Court = "indoor" | "outdoor" | "both";
export type Priority = "traction" | "cushion" | "support" | "lightweight";
export type FootWidth = "narrow" | "standard" | "wide";
export type Cut = "low" | "mid" | "high";

/** A short, source-attributed excerpt supporting a recommendation. */
export interface EvidenceExcerpt {
  text: string;
  source: string | null;
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
  /** Source material used to support the explanation, when the API supplies it. */
  evidence?: EvidenceExcerpt[];
  /** Affiliate-tracked buy link; null until affiliate feeds exist. */
  affiliate_url: string | null;
  /** Short factual reasons this shoe fits the shopper's answers, e.g. "9.3 traction". */
  match_reasons?: string[];
}

export interface RecommendResponse {
  /** Ranked best-first; expected length 3. */
  recommendations: RecommendedShoe[];
}

export type FeedbackVote = "up" | "down";

export type FeedbackReason =
  | "not_my_playstyle"
  | "too_expensive"
  | "not_my_style"
  | "fit_or_comfort"
  | "other";

export interface FeedbackRequest {
  session_id: string;
  shoe_id: number;
  vote: FeedbackVote;
  request: RecommendRequest;
  reason?: FeedbackReason;
  comment?: string;
}

export interface ProductEvent {
  session_id: string;
  name:
    | "quiz_started"
    | "quiz_step_completed"
    | "quiz_submitted"
    | "recommendations_shown"
    | "recommendation_viewed"
    | "feedback_submitted"
    | "buy_link_intent"
    | "recommendation_error"
    | "catalog_viewed"
    | "catalog_filtered"
    | "shoe_detail_viewed"
    | "buy_link_unavailable";
  properties?: Record<string, string | number | boolean | null>;
}

/** Editorial "trending" card on the home screen (not personalized). */
export interface TrendingShoe {
  brand: string;
  model: string;
  price: string;
  blurb: string;
}
