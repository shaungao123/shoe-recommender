/**
 * Typed client for the backend API. Everything goes through here —
 * no direct LLM/DB access from the frontend.
 */

import { MOCK_LATENCY_MS, mockRecommendResponse } from "./mockData";
import type {
  FeedbackRequest,
  RecommendRequest,
  RecommendResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

/** Serve fictional placeholder data instead of calling the backend (dev only). */
export const isMockApi = process.env.NEXT_PUBLIC_USE_MOCK_API === "true";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function getRecommendations(
  request: RecommendRequest,
): Promise<RecommendResponse> {
  if (isMockApi) {
    await delay(MOCK_LATENCY_MS);
    return mockRecommendResponse;
  }
  const res = await fetch(`${API_URL}/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    throw new Error(`POST /recommend failed with status ${res.status}`);
  }
  return (await res.json()) as RecommendResponse;
}

/** Best-effort: feedback loss should never interrupt the user. */
export function sendFeedback(feedback: FeedbackRequest): void {
  if (isMockApi) return;
  void fetch(`${API_URL}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(feedback),
  }).catch(() => {});
}
