/** Post-auth destination. Kept out of the OAuth redirectTo URL so Supabase
 * allow-list matching stays exact (`…/auth/callback` with no query string). */

export const AUTH_NEXT_COOKIE = "the-assist-auth-next";

export function safeNextPath(next: string | null | undefined): string {
  if (next && next.startsWith("/") && !next.startsWith("//")) {
    return next;
  }
  return "/profile";
}

/** Absolute callback URL with no query params — must match Redirect URLs. */
export function authCallbackUrl(origin: string = window.location.origin): string {
  return `${origin}/auth/callback`;
}

export function rememberAuthNext(next: string): void {
  document.cookie = `${AUTH_NEXT_COOKIE}=${encodeURIComponent(safeNextPath(next))}; path=/; max-age=600; SameSite=Lax`;
}
