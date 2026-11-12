"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getVerdict, type Verdict, type VerdictLevel } from "@/lib/preferences";
import { createClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/config";

type State =
  | { kind: "loading" }
  | { kind: "signed-out" }
  | { kind: "no-preferences" }
  | { kind: "verdict"; verdict: Verdict }
  | { kind: "hidden" };

const DOT: Record<VerdictLevel, string> = {
  great: "bg-accent",
  worth_a_look: "bg-ink",
  not_for_you: "bg-faint",
};

function Teaser({ href, action }: { href: string; action: string }) {
  return (
    <div className="mt-6 rounded-2xl border border-dashed border-line bg-white p-4">
      <p className="text-sm font-bold text-ink">Would you like this shoe?</p>
      <p className="mt-1 font-serif text-sm text-muted">See if it fits your game, based on your quiz answers.</p>
      <Link href={href} className="mt-3 inline-block text-sm font-bold text-ink underline underline-offset-4 hover:text-accent-deep">
        {action}
      </Link>
    </div>
  );
}

function Line({ mark, text, className }: { mark: string; text: string; className: string }) {
  return (
    <li className="flex gap-2.5 text-sm/[1.45]">
      <span aria-hidden className={`w-3 shrink-0 text-center font-extrabold ${className}`}>{mark}</span>
      <span className="text-ink">{text}</span>
    </li>
  );
}

/** "Would you like it?" for signed-in users with saved preferences; a sign-in or quiz prompt otherwise. */
export function VerdictBox({ shoeId }: { shoeId: number }) {
  const configured = isSupabaseConfigured();
  const [state, setState] = useState<State>(configured ? { kind: "loading" } : { kind: "hidden" });

  useEffect(() => {
    if (!configured) return;
    let active = true;

    const load = async (signedIn: boolean) => {
      if (!signedIn) {
        if (active) setState({ kind: "signed-out" });
        return;
      }
      try {
        const response = await getVerdict(shoeId);
        if (!active) return;
        setState(
          response.verdict ? { kind: "verdict", verdict: response.verdict } : { kind: "no-preferences" },
        );
      } catch {
        if (active) setState({ kind: "hidden" }); // a missing verdict shouldn't break the page
      }
    };

    const supabase = createClient();
    void supabase.auth.getSession().then(({ data }) => load(Boolean(data.session)));
    const { data: subscription } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_IN" || event === "SIGNED_OUT") void load(Boolean(session));
    });
    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, [configured, shoeId]);

  if (state.kind === "hidden") return null;
  if (state.kind === "loading") {
    return <div className="mt-6 h-[132px] animate-pulse rounded-2xl border border-line bg-white" />;
  }
  if (state.kind === "signed-out") {
    return <Teaser href={`/login?next=/catalog/${shoeId}`} action="Sign in to find out" />;
  }
  if (state.kind === "no-preferences") {
    return <Teaser href="/" action="Take the quiz" />;
  }

  const { verdict } = state;
  return (
    <section aria-label="Would you like it?" className="mt-6 rounded-2xl border border-line bg-white p-4">
      <p className="text-xs font-bold tracking-[.08em] text-faint uppercase">Would you like it?</p>
      <p className="mt-2 flex items-center gap-2 text-lg font-extrabold text-ink">
        <span aria-hidden className={`h-2.5 w-2.5 rounded-full ${DOT[verdict.level]}`} />
        {verdict.label}
      </p>
      {(verdict.reasons.length > 0 || verdict.caveats.length > 0 || verdict.unknowns.length > 0) && (
        <ul className="mt-3 flex flex-col gap-1.5">
          {verdict.reasons.map((text) => <Line key={text} mark="✓" text={text} className="text-accent" />)}
          {verdict.caveats.map((text) => <Line key={text} mark="!" text={text} className="text-ink" />)}
          {verdict.unknowns.map((text) => <Line key={text} mark="?" text={text} className="text-faint" />)}
        </ul>
      )}
      <Link href="/profile" className="mt-3 inline-block text-xs font-semibold text-muted underline underline-offset-4 hover:text-ink">
        Based on your saved preferences
      </Link>
    </section>
  );
}
