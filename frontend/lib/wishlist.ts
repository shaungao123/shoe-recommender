/** Authenticated wishlist and profile API client. */

import type { CatalogShoe } from "@/lib/catalog";
import { createClient } from "@/lib/supabase/client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

export interface UserProfile {
  id: string;
  email: string;
  display_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface WishlistItem {
  shoe: CatalogShoe;
  saved_at: string;
}

export interface WishlistResponse {
  items: WishlistItem[];
}

async function accessToken(): Promise<string> {
  const supabase = createClient();
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session?.access_token) {
    throw new Error("Not signed in");
  }
  return data.session.access_token;
}

/** A failed API call; ``status`` lets callers treat 404 as "nothing saved". */
export class ApiError extends Error {
  constructor(readonly status: number) {
    super(`Request failed (${status})`);
  }
}

export async function authRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await accessToken();
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    throw new ApiError(response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function getMe() {
  return authRequest<UserProfile>("/me");
}

export function updateMe(displayName: string | null) {
  return authRequest<UserProfile>("/me", {
    method: "PATCH",
    body: JSON.stringify({ display_name: displayName }),
  });
}

export function getWishlist() {
  return authRequest<WishlistResponse>("/wishlist");
}

export function addToWishlist(shoeId: number) {
  return authRequest<WishlistItem>(`/wishlist/${shoeId}`, { method: "PUT" });
}

export function removeFromWishlist(shoeId: number) {
  return authRequest<void>(`/wishlist/${shoeId}`, { method: "DELETE" });
}
