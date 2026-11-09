const SESSION_KEY = "the-assist-session-id";

/** A random, anonymous browser identifier; no account or personal data required. */
export function getAnonymousSessionId(): string {
  if (typeof window === "undefined") return "server-render";
  const existing = window.localStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const id = crypto.randomUUID();
  window.localStorage.setItem(SESSION_KEY, id);
  return id;
}
