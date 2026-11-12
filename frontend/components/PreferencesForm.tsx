"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState, type ReactNode } from "react";

import { Chip } from "@/components/Chip";
import {
  BRANDS,
  BUDGETS,
  COURTS,
  CUTS,
  FOOT_WIDTHS,
  NO_LIMIT,
  POSITIONS,
  PRIORITIES,
  STYLE_TAGS,
} from "@/components/screens/IntakeScreen";
import {
  EMPTY_PREFERENCES,
  getPreferences,
  savePreferences,
  type Position,
  type Preferences,
  type SavedPreferences,
  type Style,
} from "@/lib/preferences";

const MAX_PRIORITIES = 2;
const inputClass =
  "w-full rounded-xl border-[1.5px] border-line bg-white px-4 py-3.5 text-[15px]/[1.4] outline-none focus:border-ink";

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-2.5 text-xs font-bold tracking-[.05em] text-muted uppercase">
        {label}
        {hint && <span className="ml-2 font-semibold tracking-normal normal-case text-faint">{hint}</span>}
      </div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

/** Pick one, or tap the selected chip again to clear it. */
function single<T>(current: T | null, value: T): T | null {
  return current === value ? null : value;
}

function toggle<T>(values: T[], value: T, max = Infinity): T[] {
  if (values.includes(value)) return values.filter((v) => v !== value);
  return values.length >= max ? values : [...values, value];
}

function answersOf(saved: SavedPreferences): Preferences {
  const answers: Partial<SavedPreferences> = { ...saved };
  delete answers.updated_at;
  return answers as Preferences;
}

function budgetLabel(budget: number | null): string {
  return budget === null ? NO_LIMIT : `$${budget}`;
}

export function PreferencesForm() {
  const [prefs, setPrefs] = useState<Preferences>(EMPTY_PREFERENCES);
  const [status, setStatus] = useState<"loading" | "empty" | "saved" | "error">("loading");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");

  useEffect(() => {
    let active = true;
    getPreferences()
      .then((saved) => {
        if (!active) return;
        if (saved) {
          setPrefs(answersOf(saved));
          setStatus("saved");
        } else {
          setStatus("empty");
        }
      })
      .catch(() => active && setStatus("error"));
    return () => {
      active = false;
    };
  }, []);

  const update = (patch: Partial<Preferences>) => {
    setPrefs((current) => ({ ...current, ...patch }));
    setSaveState("idle");
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaveState("saving");
    try {
      setPrefs(answersOf(await savePreferences(prefs)));
      setStatus("saved");
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  };

  if (status === "loading") {
    return <div className="mt-8 h-64 animate-pulse rounded-2xl border border-line bg-white" />;
  }
  if (status === "error") {
    return (
      <div className="mt-8 rounded-2xl border border-line bg-white p-6 text-sm font-semibold text-ink">
        We couldn’t load your preferences. Refresh to try again.
      </div>
    );
  }

  return (
    <section className="mt-8 rounded-2xl border border-line bg-white p-6 sm:p-8">
      <h2 className="text-[22px]/tight font-extrabold tracking-[-.01em]">Your game</h2>
      <p className="mt-2 font-serif text-[15px]/normal text-muted">
        {status === "empty" ? (
          <>
            Nothing saved yet. Fill this in or{" "}
            <Link href="/" className="font-semibold text-ink underline underline-offset-4">
              take the quiz
            </Link>{" "}
            — shoe pages then tell you whether each shoe suits you.
          </>
        ) : (
          "Shoe pages use these to tell you whether a shoe suits you. Your latest quiz updates them too."
        )}
      </p>

      <form onSubmit={(event) => void onSubmit(event)} className="mt-6 flex flex-col gap-6">
        <Field label="Position">
          {POSITIONS.map((label) => {
            const value = label.toLowerCase() as Position;
            return (
              <Chip key={label} label={label} selected={prefs.positions.includes(value)}
                onClick={() => update({ positions: toggle(prefs.positions, value) })} />
            );
          })}
        </Field>
        <Field label="Style">
          {STYLE_TAGS.map((label) => {
            const value = label.toLowerCase() as Style;
            return (
              <Chip key={label} label={label} selected={prefs.styles.includes(value)}
                onClick={() => update({ styles: toggle(prefs.styles, value) })} />
            );
          })}
        </Field>
        <label className="block">
          <span className="mb-2.5 block text-xs font-bold tracking-[.05em] text-muted uppercase">In your own words</span>
          <textarea value={prefs.description} maxLength={500} rows={2} className={inputClass}
            placeholder="e.g. quick first step, finish through contact"
            onChange={(event) => update({ description: event.target.value })} />
        </label>
        <Field label="Court">
          {COURTS.map(([value, label]) => (
            <Chip key={value} label={label} selected={prefs.court === value}
              onClick={() => update({ court: single(prefs.court, value) })} />
          ))}
        </Field>
        <Field label="Priorities" hint={`Pick up to ${MAX_PRIORITIES}`}>
          {PRIORITIES.map(([value, label]) => (
            <Chip key={value} label={label} selected={prefs.priorities.includes(value)}
              onClick={() => update({ priorities: toggle(prefs.priorities, value, MAX_PRIORITIES) })} />
          ))}
        </Field>
        <Field label="Budget" hint="Used by the quiz, not the shoe-page verdict">
          {BUDGETS.map((label) => (
            <Chip key={label} label={label} selected={budgetLabel(prefs.budget) === label}
              onClick={() => update({ budget: label === NO_LIMIT ? null : Number(label.replace(/\D/g, "")) })} />
          ))}
        </Field>
        <Field label="Foot width">
          {FOOT_WIDTHS.map(([value, label]) => (
            <Chip key={value} label={label} selected={prefs.foot_width === value}
              onClick={() => update({ foot_width: single(prefs.foot_width, value) })} />
          ))}
        </Field>
        <Field label="Favorite brand">
          {BRANDS.map((brand) => (
            <Chip key={brand} label={brand} selected={prefs.preferred_brand === brand}
              onClick={() => update({ preferred_brand: single(prefs.preferred_brand, brand) })} />
          ))}
        </Field>
        <Field label="Cut">
          {CUTS.map(([value, label]) => (
            <Chip key={value} label={label} selected={prefs.preferred_cut === value}
              onClick={() => update({ preferred_cut: single(prefs.preferred_cut, value) })} />
          ))}
        </Field>
        <label className="block">
          <span className="mb-2.5 block text-xs font-bold tracking-[.05em] text-muted uppercase">Anything else</span>
          <textarea value={prefs.note} maxLength={500} rows={2} className={inputClass}
            placeholder="e.g. recovering from an ankle sprain, flat feet"
            onChange={(event) => update({ note: event.target.value })} />
        </label>

        <div className="flex flex-wrap items-center gap-4">
          <button type="submit" disabled={saveState === "saving"}
            className="cursor-pointer rounded-full bg-accent px-6 py-[15px] text-[15px]/none font-bold text-white transition-colors hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-40">
            Save preferences
          </button>
          {saveState === "saved" && <span className="text-sm font-semibold text-muted">Preferences saved.</span>}
          {saveState === "error" && <span className="text-sm font-semibold text-ink">Couldn’t save. Try again.</span>}
        </div>
      </form>
    </section>
  );
}
