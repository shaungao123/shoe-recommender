/**
 * Saved quiz answers ("preferences") and the personal verdict on shoe pages.
 *
 * Quiz answers are kept in this browser until they can be saved to the
 * account: right away when signed in, otherwise on the next sign-in if the
 * account has nothing saved yet.
 */

import { budgetValue, knownAnswers, type IntakeState } from "@/components/screens/IntakeScreen";
import { createClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import type { Court, Cut, FootWidth, Priority } from "@/lib/types";
import { ApiError, authRequest } from "@/lib/wishlist";

export type Position = "guard" | "wing" | "big";
export type Style = "slasher" | "shooter" | "all-around" | "post" | "defender" | "speedster" | "leaper";

export interface Preferences {
  positions: Position[];
  styles: Style[];
  description: string;
  court: Court | null;
  priorities: Priority[];
  budget: number | null;
  foot_width: FootWidth | null;
  preferred_brand: string | null;
  preferred_cut: Cut | null;
  note: string;
}

export interface SavedPreferences extends Preferences {
  updated_at: string;
}

export type VerdictLevel = "great" | "worth_a_look" | "not_for_you";

export interface Verdict {
  level: VerdictLevel;
  label: string;
  reasons: string[];
  caveats: string[];
  unknowns: string[];
}

export interface VerdictResponse {
  has_preferences: boolean;
  verdict: Verdict | null;
}

export const EMPTY_PREFERENCES: Preferences = {
  positions: [],
  styles: [],
  description: "",
  court: null,
  priorities: [],
  budget: null,
  foot_width: null,
  preferred_brand: null,
  preferred_cut: null,
  note: "",
};

const PENDING_KEY = "assist.pendingPreferences";

export function intakeToPreferences(intake: IntakeState): Preferences {
  return {
    positions: knownAnswers(intake.positions).map((p) => p.toLowerCase() as Position),
    styles: knownAnswers(intake.styles).map((s) => s.toLowerCase() as Style),
    description: intake.freeText.trim(),
    court: intake.court,
    priorities: intake.priorities,
    budget: budgetValue(intake.budget),
    foot_width: intake.footWidth,
    preferred_brand: intake.brand,
    preferred_cut: intake.cut,
    note: intake.note.trim(),
  };
}

/** null when the account has nothing saved yet. */
export async function getPreferences(): Promise<SavedPreferences | null> {
  try {
    return await authRequest<SavedPreferences>("/me/preferences");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function savePreferences(preferences: Preferences) {
  return authRequest<SavedPreferences>("/me/preferences", {
    method: "PUT",
    body: JSON.stringify(preferences),
  });
}

export function getVerdict(shoeId: number) {
  return authRequest<VerdictResponse>(`/me/verdict/${shoeId}`);
}

async function isSignedIn(): Promise<boolean> {
  if (!isSupabaseConfigured()) return false;
  const { data } = await createClient().auth.getSession();
  return Boolean(data.session);
}

function readPending(): Preferences | null {
  try {
    const raw = window.localStorage.getItem(PENDING_KEY);
    return raw ? (JSON.parse(raw) as Preferences) : null;
  } catch {
    return null;
  }
}

function writePending(preferences: Preferences | null) {
  try {
    if (preferences) window.localStorage.setItem(PENDING_KEY, JSON.stringify(preferences));
    else window.localStorage.removeItem(PENDING_KEY);
  } catch {
    // Storage blocked (private mode): the answers just aren't carried over.
  }
}

/** After a finished quiz: save to the account now, or keep for the next sign-in. Never throws. */
export async function rememberQuizAnswers(intake: IntakeState): Promise<void> {
  const preferences = intakeToPreferences(intake);
  try {
    if (await isSignedIn()) {
      await savePreferences(preferences);
      writePending(null);
      return;
    }
  } catch {
    // Fall through: keep them locally and retry on the next sign-in.
  }
  writePending(preferences);
}

/** On sign-in: save answers from a logged-out quiz, unless the account already has some. Never throws. */
export async function carryOverQuizAnswers(): Promise<void> {
  const pending = readPending();
  if (!pending) return;
  try {
    if ((await getPreferences()) === null) {
      await savePreferences(pending);
    }
    writePending(null);
  } catch {
    // Keep them for the next attempt.
  }
}
