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
  /** Preference signals only — the API must not exclude strong matches for these. */
  aesthetic_preferences?: AestheticPreferences | null;
}

export type ColorFamily = "neutral" | "dark" | "bright" | "team_colors";
export type VisualDirection = "classic_retro" | "modern_technical" | "minimal";
export type SilhouettePreference = "low" | "mid" | "high";

export interface AestheticPreferences {
  brand: string | null;
  color_family: ColorFamily | null;
  visual_direction: VisualDirection | null;
  silhouette: SilhouettePreference | null;
}

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
